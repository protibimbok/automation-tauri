use sqlx::SqlitePool;

const SCHEMA_VERSION_KEY: &str = "schema_version";

struct Migration {
    version: &'static str,
    up: &'static str,
}

const MIGRATIONS: &[Migration] = &[
    Migration {
        version: "20260619000001",
        up: include_str!("../../migrations/20260619000001_init_sessions/up.sql"),
    },
    Migration {
        version: "20260619000002",
        up: include_str!("../../migrations/20260619000002_init_runs/up.sql"),
    },
];

pub async fn ensure_kv_table(pool: &SqlitePool) -> Result<(), String> {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT NOT NULL
        )",
    )
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn get_schema_version(pool: &SqlitePool) -> Result<String, String> {
    let version = sqlx::query_scalar::<_, String>(
        "SELECT value FROM kv WHERE key = ?",
    )
    .bind(SCHEMA_VERSION_KEY)
    .fetch_optional(pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(version.unwrap_or_else(|| "0".to_string()))
}

async fn write_schema_version(
    executor: impl sqlx::Executor<'_, Database = sqlx::Sqlite>,
    version: &str,
) -> Result<(), String> {
    sqlx::query(
        "INSERT INTO kv (key, value) VALUES (?, ?)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    )
    .bind(SCHEMA_VERSION_KEY)
    .bind(version)
    .execute(executor)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

fn sql_statements(sql: &str) -> Vec<String> {
    sql.split(';')
        .map(str::trim)
        .filter(|statement| !statement.is_empty())
        .map(ToString::to_string)
        .collect()
}

pub async fn run(pool: &SqlitePool) -> Result<String, String> {
    ensure_kv_table(pool).await?;
    let current = get_schema_version(pool).await?;

    let mut applied = current.clone();

    for migration in MIGRATIONS {
        if migration.version <= current.as_str() {
            continue;
        }

        let mut tx = pool.begin().await.map_err(|e| e.to_string())?;

        for statement in sql_statements(migration.up) {
            sqlx::query(&statement)
                .execute(&mut *tx)
                .await
                .map_err(|e| {
                    format!(
                        "migration {} failed on statement {:?}: {e}",
                        migration.version, statement
                    )
                })?;
        }

        write_schema_version(&mut *tx, migration.version).await?;

        tx.commit().await.map_err(|e| e.to_string())?;
        applied = migration.version.to_string();
    }

    Ok(applied)
}
