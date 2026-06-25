pub mod migrate;
pub mod models;
pub mod runs;
pub mod sessions;

use std::path::Path;

use sqlx::sqlite::SqliteConnectOptions;
use sqlx::SqlitePool;

pub use models::{RunInfo, SessionInfo};
pub use runs::{
    append_log, bump_rerun, create_run, delete_run, get_run, list_inputs, list_item_keys,
    list_items, list_runs, reset_runs_on_startup, set_input_status, set_pause_info, set_status,
    upsert_item,
};
pub use sessions::{
    clear_active_runs, create_default_chrome_session, create_session, delete_session,
    get_session, list_sessions, mark_checked, mark_idle, mark_running, platform_check_url,
    reset_running_on_startup, session_dir, storage_state_path,
    DEFAULT_CHROME_SESSION_ID,
};

async fn connect_pool(db_path: &Path) -> Result<SqlitePool, String> {
    if let Some(parent) = db_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    let options = SqliteConnectOptions::new()
        .filename(db_path)
        .create_if_missing(true);

    let pool = SqlitePool::connect_with(options)
        .await
        .map_err(|e| e.to_string())?;

    sqlx::query("PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL; PRAGMA busy_timeout = 5000;")
        .execute(&pool)
        .await
        .map_err(|e| e.to_string())?;

    Ok(pool)
}

/// Open the database, apply pending migrations, and reset stale session run state.
pub async fn init(db_path: &Path) -> Result<SqlitePool, String> {
    let pool = connect_pool(db_path).await?;
    let _version = migrate::run(&pool).await?;
    reset_running_on_startup(&pool).await?;
    reset_runs_on_startup(&pool).await?;
    Ok(pool)
}
