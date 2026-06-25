use std::path::{Path, PathBuf};

use chrono::Utc;
use sqlx::SqlitePool;
use uuid::Uuid;

use super::models::{SessionInfo, SessionRow};

pub const DEFAULT_CHROME_SESSION_ID: &str = "default-chrome";
pub const DEFAULT_CHROME_SESSION_NAME: &str = "Default Chrome";

pub fn uses_system_profile(session_id: &str) -> bool {
    session_id == DEFAULT_CHROME_SESSION_ID
}

pub fn now_iso() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

pub fn session_dir(sessions_root: &Path, session_id: &str) -> PathBuf {
    sessions_root.join(session_id)
}

pub fn storage_state_path(sessions_root: &Path, session_id: &str) -> PathBuf {
    session_dir(sessions_root, session_id).join("storage_state.json")
}

pub fn chrome_profile_path(sessions_root: &Path, session_id: &str) -> PathBuf {
    session_dir(sessions_root, session_id).join("chrome-profile")
}

pub fn has_storage(sessions_root: &Path, session_id: &str) -> bool {
    let state_path = storage_state_path(sessions_root, session_id);
    if state_path.is_file() {
        if let Ok(content) = std::fs::read_to_string(&state_path) {
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(cookies) = value.get("cookies").and_then(|v| v.as_array()) {
                    if !cookies.is_empty() {
                        return true;
                    }
                }
            }
        }
    }

    let profile = chrome_profile_path(sessions_root, session_id);
    profile.is_dir()
        && std::fs::read_dir(&profile)
            .map(|mut entries| entries.next().is_some())
            .unwrap_or(false)
}

fn to_info(session: SessionRow, sessions_root: &Path) -> SessionInfo {
    let session_id = session.id.clone();
    session.into_info(has_storage(sessions_root, &session_id))
}

pub async fn reset_running_on_startup(pool: &SqlitePool) -> Result<(), String> {
    let now = now_iso();
    sqlx::query(
        "UPDATE sessions SET status = 'idle', active_run_count = 0, updated_at = ? WHERE active_run_count > 0",
    )
    .bind(&now)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn get_default_chrome_session(
    pool: &SqlitePool,
    sessions_root: &Path,
) -> Result<Option<SessionInfo>, String> {
    let row = sqlx::query_as::<_, SessionRow>(
        "SELECT id, platform, name, status, active_run_count, last_checked_at, created_at, updated_at
         FROM sessions WHERE id = ?",
    )
    .bind(DEFAULT_CHROME_SESSION_ID)
    .fetch_optional(pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(row.map(|session| to_info(session, sessions_root)))
}

pub async fn list_sessions(
    pool: &SqlitePool,
    sessions_root: &Path,
    platform: &str,
) -> Result<Vec<SessionInfo>, String> {
    let rows = sqlx::query_as::<_, SessionRow>(
        "SELECT id, platform, name, status, active_run_count, last_checked_at, created_at, updated_at
         FROM sessions WHERE platform = ? ORDER BY name ASC",
    )
    .bind(platform)
    .fetch_all(pool)
    .await
    .map_err(|e| e.to_string())?;

    let mut sessions: Vec<SessionInfo> = rows
        .into_iter()
        .map(|row| to_info(row, sessions_root))
        .collect();

    if let Some(default_chrome) = get_default_chrome_session(pool, sessions_root).await? {
        if !sessions
            .iter()
            .any(|session| session.id == DEFAULT_CHROME_SESSION_ID)
        {
            sessions.insert(0, default_chrome);
        }
    }

    Ok(sessions)
}

pub async fn get_session(
    pool: &SqlitePool,
    sessions_root: &Path,
    session_id: &str,
) -> Result<SessionInfo, String> {
    let row = sqlx::query_as::<_, SessionRow>(
        "SELECT id, platform, name, status, active_run_count, last_checked_at, created_at, updated_at
         FROM sessions WHERE id = ?",
    )
    .bind(session_id)
    .fetch_one(pool)
    .await
    .map_err(|e| e.to_string())?;

    Ok(to_info(row, sessions_root))
}

pub async fn create_default_chrome_session(
    pool: &SqlitePool,
    sessions_root: &Path,
    platform: &str,
) -> Result<SessionInfo, String> {
    if get_default_chrome_session(pool, sessions_root)
        .await?
        .is_some()
    {
        return Err("Default Chrome already exists".into());
    }

    let now = now_iso();
    let dir = session_dir(sessions_root, DEFAULT_CHROME_SESSION_ID);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    sqlx::query(
        "INSERT INTO sessions (id, platform, name, status, created_at, updated_at)
         VALUES (?, ?, ?, 'idle', ?, ?)",
    )
    .bind(DEFAULT_CHROME_SESSION_ID)
    .bind(platform)
    .bind(DEFAULT_CHROME_SESSION_NAME)
    .bind(&now)
    .bind(&now)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;

    get_session(pool, sessions_root, DEFAULT_CHROME_SESSION_ID).await
}

pub async fn create_session(
    pool: &SqlitePool,
    sessions_root: &Path,
    platform: &str,
    name: &str,
) -> Result<SessionInfo, String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("session name is required".into());
    }

    let id = Uuid::new_v4().to_string();
    let dir = session_dir(sessions_root, &id);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;

    let now = now_iso();
    let result = sqlx::query(
        "INSERT INTO sessions (id, platform, name, status, created_at, updated_at)
         VALUES (?, ?, ?, 'idle', ?, ?)",
    )
    .bind(&id)
    .bind(platform)
    .bind(trimmed)
    .bind(&now)
    .bind(&now)
    .execute(pool)
    .await;

    if let Err(e) = result {
        let message = e.to_string();
        if message.contains("UNIQUE") {
            return Err(format!(
                "a session named '{trimmed}' already exists for {platform}"
            ));
        }
        return Err(message);
    }

    get_session(pool, sessions_root, &id).await
}

pub async fn delete_session(
    pool: &SqlitePool,
    sessions_root: &Path,
    session_id: &str,
) -> Result<(), String> {
    let deleted = sqlx::query("DELETE FROM sessions WHERE id = ?")
        .bind(session_id)
        .execute(pool)
        .await
        .map_err(|e| e.to_string())?
        .rows_affected();

    if deleted == 0 {
        return Err(format!("session '{session_id}' not found"));
    }

    if uses_system_profile(session_id) {
        return Ok(());
    }

    let dir = session_dir(sessions_root, session_id);
    if dir.exists() {
        std::fs::remove_dir_all(&dir).map_err(|e| e.to_string())?;
    }

    Ok(())
}

pub async fn mark_running(pool: &SqlitePool, session_id: &str) -> Result<(), String> {
    let now = now_iso();
    let updated = sqlx::query(
        "UPDATE sessions SET active_run_count = active_run_count + 1, status = 'running', updated_at = ? WHERE id = ?",
    )
    .bind(&now)
    .bind(session_id)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?
    .rows_affected();

    if updated == 0 {
        return Err(format!("session '{session_id}' not found"));
    }
    Ok(())
}

pub async fn mark_idle(pool: &SqlitePool, session_id: &str) -> Result<(), String> {
    let now = now_iso();
    sqlx::query(
        "UPDATE sessions SET
            active_run_count = CASE WHEN active_run_count > 0 THEN active_run_count - 1 ELSE 0 END,
            status = CASE WHEN active_run_count > 1 THEN 'running' ELSE 'idle' END,
            updated_at = ?
         WHERE id = ?",
    )
    .bind(&now)
    .bind(session_id)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn clear_active_runs(pool: &SqlitePool, session_id: &str) -> Result<(), String> {
    let now = now_iso();
    sqlx::query(
        "UPDATE sessions SET active_run_count = 0, status = 'idle', updated_at = ? WHERE id = ?",
    )
    .bind(&now)
    .bind(session_id)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub async fn mark_checked(pool: &SqlitePool, session_id: &str) -> Result<(), String> {
    let now = now_iso();
    sqlx::query(
        "UPDATE sessions SET last_checked_at = ?, updated_at = ? WHERE id = ?",
    )
    .bind(&now)
    .bind(&now)
    .bind(session_id)
    .execute(pool)
    .await
    .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn platform_check_url(platform: &str) -> Result<&'static str, String> {
    match platform {
        "linkedin" => Ok("https://www.linkedin.com/feed/"),
        "facebook" => Ok("https://www.facebook.com/"),
        "twitter" => Ok("https://x.com/home"),
        other => Err(format!("unsupported platform '{other}'")),
    }
}
