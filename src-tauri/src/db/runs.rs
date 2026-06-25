use serde_json::Value;
use sqlx::SqlitePool;
use uuid::Uuid;

use super::models::{RunInfo, RunInputInfo, RunInputRow, RunItemInfo, RunItemRow, RunRow};
use super::sessions::now_iso;

const LOG_MAX_LINES: usize = 300;

const RUN_COLUMNS: &str = "id, platform, task, status, params, log, pause_info, error, item_count, \
     first_run_at, last_run_at, re_run_count, created_at, updated_at";

fn value_to_text(value: &Value) -> String {
    if value.is_null() {
        "{}".to_string()
    } else {
        value.to_string()
    }
}

/// On startup any run that was mid-flight is interrupted: mark it shutdown so it
/// can be resumed (paused runs keep their checkpoint and stay paused).
pub async fn reset_runs_on_startup(pool: &SqlitePool) -> Result<(), String> {
    let now = now_iso();
    sqlx::query(
        "UPDATE runs SET status = 'shutdown', updated_at = ? WHERE status IN ('running', 'stopping')",
    )
    .bind(&now)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn list_runs(
    pool: &SqlitePool,
    platform: Option<&str>,
) -> Result<Vec<RunInfo>, String> {
    let rows = if let Some(platform) = platform {
        sqlx::query_as::<_, RunRow>(&format!(
            "SELECT {RUN_COLUMNS} FROM runs WHERE platform = ? ORDER BY updated_at DESC"
        ))
        .bind(platform)
        .fetch_all(pool)
        .await
    } else {
        sqlx::query_as::<_, RunRow>(&format!(
            "SELECT {RUN_COLUMNS} FROM runs ORDER BY updated_at DESC"
        ))
        .fetch_all(pool)
        .await
    }
    .map_err(|e| e.to_string())?;

    Ok(rows.into_iter().map(RunRow::into_info).collect())
}

pub async fn get_run(pool: &SqlitePool, run_id: &str) -> Result<RunInfo, String> {
    let row = sqlx::query_as::<_, RunRow>(&format!(
        "SELECT {RUN_COLUMNS} FROM runs WHERE id = ?"
    ))
    .bind(run_id)
    .fetch_optional(pool)
    .await
    .map_err(|e| e.to_string())?;

    row.map(RunRow::into_info)
        .ok_or_else(|| format!("run '{run_id}' not found"))
}

pub async fn list_inputs(
    pool: &SqlitePool,
    run_id: &str,
) -> Result<Vec<RunInputInfo>, String> {
    let rows = sqlx::query_as::<_, RunInputRow>(
        "SELECT id, run_id, ordinal, status, data, cursor, created_at
         FROM run_inputs WHERE run_id = ? ORDER BY ordinal ASC",
    )
    .bind(run_id)
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(rows.into_iter().map(RunInputRow::into_info).collect())
}

pub async fn list_items(
    pool: &SqlitePool,
    run_id: &str,
    input_id: Option<&str>,
) -> Result<Vec<RunItemInfo>, String> {
    let rows = if let Some(input_id) = input_id {
        sqlx::query_as::<_, RunItemRow>(
            "SELECT id, run_id, input_id, item_key, ordinal, data, created_at
             FROM run_items WHERE run_id = ? AND input_id = ? ORDER BY ordinal ASC",
        )
        .bind(run_id)
        .bind(input_id)
        .fetch_all(pool)
        .await
    } else {
        sqlx::query_as::<_, RunItemRow>(
            "SELECT id, run_id, input_id, item_key, ordinal, data, created_at
             FROM run_items WHERE run_id = ? ORDER BY ordinal ASC",
        )
        .bind(run_id)
        .fetch_all(pool)
        .await
    }
    .map_err(|e| e.to_string())?;

    Ok(rows.into_iter().map(RunItemRow::into_info).collect())
}

pub async fn list_item_keys(
    pool: &SqlitePool,
    run_id: &str,
    input_id: &str,
) -> Result<Vec<String>, String> {
    let keys = sqlx::query_scalar::<_, String>(
        "SELECT item_key FROM run_items WHERE run_id = ? AND input_id = ?",
    )
    .bind(run_id)
    .bind(input_id)
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(keys)
}

pub async fn create_run(
    pool: &SqlitePool,
    platform: &str,
    task: &str,
    params: &Value,
    inputs: &[Value],
) -> Result<RunInfo, String> {
    if platform.trim().is_empty() {
        return Err("platform is required".into());
    }
    if task.trim().is_empty() {
        return Err("task is required".into());
    }
    if inputs.is_empty() {
        return Err("at least one input row is required".into());
    }

    let id = Uuid::new_v4().to_string();
    let now = now_iso();

    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;

    sqlx::query(
        "INSERT INTO runs (id, platform, task, status, params, log, first_run_at, last_run_at, created_at, updated_at)
         VALUES (?, ?, ?, 'running', ?, '', ?, ?, ?, ?)",
    )
    .bind(&id)
    .bind(platform)
    .bind(task)
    .bind(value_to_text(params))
    .bind(&now)
    .bind(&now)
    .bind(&now)
    .bind(&now)
    .execute(&mut *tx)
    .await
    .map_err(|e| e.to_string())?;

    for (ordinal, data) in inputs.iter().enumerate() {
        let input_id = Uuid::new_v4().to_string();
        sqlx::query(
            "INSERT INTO run_inputs (id, run_id, ordinal, status, data, created_at)
             VALUES (?, ?, ?, 'pending', ?, ?)",
        )
        .bind(&input_id)
        .bind(&id)
        .bind(ordinal as i32)
        .bind(value_to_text(data))
        .bind(&now)
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    }

    tx.commit().await.map_err(|e| e.to_string())?;

    get_run(pool, &id).await
}

pub async fn set_status(
    pool: &SqlitePool,
    run_id: &str,
    status: &str,
    error: Option<&str>,
) -> Result<(), String> {
    let now = now_iso();
    sqlx::query("UPDATE runs SET status = ?, error = ?, updated_at = ? WHERE id = ?")
        .bind(status)
        .bind(error)
        .bind(&now)
        .bind(run_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn set_pause_info(
    pool: &SqlitePool,
    run_id: &str,
    pause_info: Option<&Value>,
) -> Result<(), String> {
    let now = now_iso();
    let serialized = pause_info.map(|value| value.to_string());
    sqlx::query("UPDATE runs SET pause_info = ?, updated_at = ? WHERE id = ?")
        .bind(serialized)
        .bind(&now)
        .bind(run_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn append_log(pool: &SqlitePool, run_id: &str, line: &str) -> Result<(), String> {
    let now = now_iso();
    let current = sqlx::query_scalar::<_, String>("SELECT log FROM runs WHERE id = ?")
        .bind(run_id)
        .fetch_optional(pool)
        .await
        .map_err(|e| e.to_string())?
        .unwrap_or_default();

    let mut lines: Vec<&str> = if current.is_empty() {
        Vec::new()
    } else {
        current.split('\n').collect()
    };
    let entry = format!("[{now}] {line}");
    lines.push(&entry);
    if lines.len() > LOG_MAX_LINES {
        lines = lines.split_off(lines.len() - LOG_MAX_LINES);
    }
    let next = lines.join("\n");

    sqlx::query("UPDATE runs SET log = ?, updated_at = ? WHERE id = ?")
        .bind(&next)
        .bind(&now)
        .bind(run_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn set_input_status(
    pool: &SqlitePool,
    run_id: &str,
    input_id: &str,
    status: &str,
    cursor: Option<&Value>,
) -> Result<(), String> {
    if let Some(cursor) = cursor {
        sqlx::query(
            "UPDATE run_inputs SET status = ?, cursor = ? WHERE run_id = ? AND id = ?",
        )
        .bind(status)
        .bind(cursor.to_string())
        .bind(run_id)
        .bind(input_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?;
    } else {
        sqlx::query("UPDATE run_inputs SET status = ? WHERE run_id = ? AND id = ?")
            .bind(status)
            .bind(run_id)
            .bind(input_id)
            .execute(pool)
            .await
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Insert a scraped item if new. Returns the persisted row when inserted.
pub async fn upsert_item(
    pool: &SqlitePool,
    run_id: &str,
    input_id: &str,
    item_key: &str,
    ordinal: i32,
    data: &Value,
) -> Result<Option<RunItemInfo>, String> {
    let id = Uuid::new_v4().to_string();
    let now = now_iso();
    let data_text = value_to_text(data);
    let inserted = sqlx::query(
        "INSERT OR IGNORE INTO run_items (id, run_id, input_id, item_key, ordinal, data, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)",
    )
    .bind(&id)
    .bind(run_id)
    .bind(input_id)
    .bind(item_key)
    .bind(ordinal)
    .bind(&data_text)
    .bind(&now)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?
    .rows_affected();

    if inserted > 0 {
        sqlx::query(
            "UPDATE runs SET item_count = item_count + 1, updated_at = ? WHERE id = ?",
        )
        .bind(&now)
        .bind(run_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?;
        return Ok(Some(RunItemInfo {
            id,
            run_id: run_id.to_string(),
            input_id: input_id.to_string(),
            item_key: item_key.to_string(),
            ordinal,
            data: data.clone(),
            created_at: now,
        }));
    }
    Ok(None)
}

/// Mark a run as starting again (resume / restart): bump the re-run counter and
/// flip it back to running.
pub async fn bump_rerun(pool: &SqlitePool, run_id: &str) -> Result<(), String> {
    let now = now_iso();
    let updated = sqlx::query(
        "UPDATE runs SET re_run_count = re_run_count + 1, status = 'running', error = NULL,
            last_run_at = ?, first_run_at = COALESCE(first_run_at, ?), updated_at = ?
         WHERE id = ?",
    )
    .bind(&now)
    .bind(&now)
    .bind(&now)
    .bind(run_id)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?
    .rows_affected();

    if updated == 0 {
        return Err(format!("run '{run_id}' not found"));
    }
    Ok(())
}

pub async fn delete_run(pool: &SqlitePool, run_id: &str) -> Result<(), String> {
    let mut tx = pool.begin().await.map_err(|e| e.to_string())?;
    sqlx::query("DELETE FROM run_items WHERE run_id = ?")
        .bind(run_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    sqlx::query("DELETE FROM run_inputs WHERE run_id = ?")
        .bind(run_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?;
    let deleted = sqlx::query("DELETE FROM runs WHERE id = ?")
        .bind(run_id)
        .execute(&mut *tx)
        .await
        .map_err(|e| e.to_string())?
        .rows_affected();
    tx.commit().await.map_err(|e| e.to_string())?;

    if deleted == 0 {
        return Err(format!("run '{run_id}' not found"));
    }
    Ok(())
}
