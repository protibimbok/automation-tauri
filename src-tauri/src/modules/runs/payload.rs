use std::path::Path;

use serde_json::{json, Value};
use sqlx::SqlitePool;

use crate::core::Facade;
use crate::db::{
    append_log, bump_rerun, get_run, list_inputs, list_item_keys, session_dir, RunInfo,
};

use super::TASK_TIMEOUT;

/// Add the resolved session directory to the params so the sidecar can load
/// the stored cookies for the selected session.
pub(super) fn augment_params(sessions_dir: &Path, params: &Value) -> Value {
    let mut params = params.clone();
    if let Some(session_id) = params.get("session_id").and_then(Value::as_str) {
        let dir = session_dir(sessions_dir, session_id);
        if let Some(obj) = params.as_object_mut() {
            obj.insert(
                "session_dir".to_string(),
                json!(dir.to_string_lossy().to_string()),
            );
        }
    }
    params
}

/// Build the `tasks.start` payload for a run, attaching per-input resume state
/// (saved cursor + already-collected item keys) when resuming.
pub(super) async fn start_payload(
    db: &SqlitePool,
    sessions_dir: &Path,
    run: &RunInfo,
    resume: bool,
) -> Result<Value, String> {
    let inputs = list_inputs(db, &run.id).await?;
    let mut input_payloads = Vec::with_capacity(inputs.len());
    for input in inputs {
        let seen_keys = if resume {
            list_item_keys(db, &run.id, &input.id).await?
        } else {
            Vec::new()
        };
        input_payloads.push(json!({
            "input_id": input.id,
            "ordinal": input.ordinal,
            "data": input.data,
            "cursor": input.cursor,
            "seen_keys": seen_keys,
        }));
    }

    Ok(json!({
        "run_id": run.id,
        "task": run.task,
        "params": augment_params(sessions_dir, &run.params),
        "inputs": input_payloads,
        "resume": resume,
    }))
}

pub(super) async fn restart_run(
    db: &SqlitePool,
    sessions_dir: &Path,
    facade: &Facade,
    run_id: &str,
) -> Result<RunInfo, String> {
    bump_rerun(db, run_id).await?;
    let run = get_run(db, run_id).await?;
    let payload = start_payload(db, sessions_dir, &run, true).await?;
    facade
        .request_with_timeout("tasks.start", payload, TASK_TIMEOUT)
        .await?;
    append_log(db, run_id, "Run resumed").await.ok();
    get_run(db, run_id).await
}
