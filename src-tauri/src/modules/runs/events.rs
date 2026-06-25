use serde_json::{json, Value};

use crate::core::BuilderApp;
use crate::error_log;
use crate::db::{append_log, set_input_status, set_pause_info, set_status, upsert_item};

use super::UI_CHANNEL;

pub(super) fn register(app: &mut BuilderApp) {
    let db = app.db.clone();

    let services_status_db = db.clone();
    app.on_event("task.status", move |facade, payload: Value| {
        let pool = services_status_db.clone();
        async move {
            if let Some(run_id) = payload.get("run_id").and_then(Value::as_str) {
                let run_id = run_id.to_string();
                let status = payload
                    .get("status")
                    .and_then(Value::as_str)
                    .unwrap_or("running")
                    .to_string();
                let error = payload.get("error").and_then(Value::as_str).map(str::to_string);
                let pause_info = payload
                    .get("pause_info")
                    .filter(|value| !value.is_null())
                    .cloned();
                tokio::spawn(async move {
                    let _ = set_status(&pool, &run_id, &status, error.as_deref()).await;
                    if let Some(pause_info) = pause_info.as_ref() {
                        let _ = set_pause_info(&pool, &run_id, Some(pause_info)).await;
                    }
                    let _ = append_log(&pool, &run_id, &format!("Status: {status}")).await;
                });
            }
            facade.push_ui(UI_CHANNEL, "task.status", payload);
        }
    });

    let services_item_db = db.clone();
    app.on_event("task.item", move |facade, payload: Value| {
        let pool = services_item_db.clone();
        async move {
            let Some(run_id) = payload.get("run_id").and_then(Value::as_str) else {
                return;
            };
            let Some(input_id) = payload.get("input_id").and_then(Value::as_str) else {
                return;
            };
            let Some(item_key) = payload.get("item_key").and_then(Value::as_str) else {
                return;
            };
            let ordinal = payload.get("ordinal").and_then(Value::as_i64).unwrap_or(0) as i32;
            let data = payload.get("data").cloned().unwrap_or_else(|| json!({}));
            let run_id = run_id.to_string();
            let input_id = input_id.to_string();
            let item_key = item_key.to_string();
            let facade = facade.clone();
            tokio::spawn(async move {
                match upsert_item(&pool, &run_id, &input_id, &item_key, ordinal, &data).await {
                    Ok(Some(item)) => {
                        if let Ok(value) = serde_json::to_value(item) {
                            facade.push_ui(UI_CHANNEL, "task.item", value);
                        }
                    }
                    Ok(None) => {}
                    Err(err) => error_log!("task.item persist failed: {err}"),
                }
            });
        }
    });

    let services_input_db = db.clone();
    app.on_event("task.input_status", move |facade, payload: Value| {
        let pool = services_input_db.clone();
        async move {
            if let (Some(run_id), Some(input_id), Some(status)) = (
                payload.get("run_id").and_then(Value::as_str),
                payload.get("input_id").and_then(Value::as_str),
                payload.get("status").and_then(Value::as_str),
            ) {
                let run_id = run_id.to_string();
                let input_id = input_id.to_string();
                let status = status.to_string();
                let cursor = payload
                    .get("cursor")
                    .filter(|value| !value.is_null())
                    .cloned();
                tokio::spawn(async move {
                    let _ =
                        set_input_status(&pool, &run_id, &input_id, &status, cursor.as_ref()).await;
                });
            }
            facade.push_ui(UI_CHANNEL, "task.input_status", payload);
        }
    });

    let services_log_db = db.clone();
    app.on_event("task.log", move |facade, payload: Value| {
        let pool = services_log_db.clone();
        async move {
            if let (Some(run_id), Some(line)) = (
                payload.get("run_id").and_then(Value::as_str),
                payload.get("line").and_then(Value::as_str),
            ) {
                let run_id = run_id.to_string();
                let line = line.to_string();
                tokio::spawn(async move {
                    let _ = append_log(&pool, &run_id, &line).await;
                });
            }
            facade.push_ui(UI_CHANNEL, "task.log", payload);
        }
    });

    app.on_event("task.progress", move |facade, payload: Value| async move {
        facade.push_ui(UI_CHANNEL, "task.progress", payload);
    });
}
