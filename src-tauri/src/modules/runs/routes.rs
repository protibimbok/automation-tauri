use serde_json::{json, Value};

use crate::core::BuilderApp;
use crate::db::{
    append_log, create_run, delete_run, get_run, list_inputs, list_items, list_runs, set_status,
};

use super::payload::{restart_run, start_payload};
use super::types::{ControlReq, ListRunsReq, RunIdReq, RunItemsReq, StartRunReq};
use super::TASK_TIMEOUT;

pub(super) fn register(app: &mut BuilderApp) {
    let db = app.db.clone();
    let sessions_dir = app.sessions_dir.clone();

    let services_list_db = db.clone();
    app.route("runs.list", move |_facade, req: ListRunsReq| {
        let db = services_list_db.clone();
        async move { list_runs(&db, req.platform.as_deref()).await }
    });

    let services_get_db = db.clone();
    app.route("runs.get", move |_facade, req: RunIdReq| {
        let db = services_get_db.clone();
        async move { get_run(&db, &req.run_id).await }
    });

    let services_inputs_db = db.clone();
    app.route("runs.inputs", move |_facade, req: RunIdReq| {
        let db = services_inputs_db.clone();
        async move { list_inputs(&db, &req.run_id).await }
    });

    let services_items_db = db.clone();
    app.route("runs.items", move |_facade, req: RunItemsReq| {
        let db = services_items_db.clone();
        async move { list_items(&db, &req.run_id, req.input_id.as_deref()).await }
    });

    let services_start_db = db.clone();
    let services_start_dir = sessions_dir.clone();
    app.route("runs.start", move |facade, req: StartRunReq| {
        let db = services_start_db.clone();
        let sessions_dir = services_start_dir.clone();
        async move {
            let run = create_run(
                &db,
                &req.platform,
                &req.task,
                &req.params,
                &req.inputs,
            )
            .await?;
            append_log(&db, &run.id, "Run started").await.ok();
            let payload = start_payload(&db, &sessions_dir, &run, false).await?;
            if let Err(err) = facade
                .request_with_timeout("tasks.start", payload, TASK_TIMEOUT)
                .await
            {
                set_status(&db, &run.id, "failed", Some(&err)).await.ok();
                append_log(&db, &run.id, &format!("Failed to start: {err}"))
                    .await
                    .ok();
                return Err(err);
            }
            get_run(&db, &run.id).await
        }
    });

    let services_control_db = db.clone();
    let services_control_dir = sessions_dir.clone();
    app.route("runs.control", move |facade, req: ControlReq| {
        let db = services_control_db.clone();
        let sessions_dir = services_control_dir.clone();
        async move {
            match req.action.as_str() {
                "pause" => {
                    let response = facade
                        .request_with_timeout(
                            "tasks.control",
                            json!({ "run_id": req.run_id, "action": "pause" }),
                            TASK_TIMEOUT,
                        )
                        .await?;
                    let found = response.get("found").and_then(Value::as_bool).unwrap_or(false);
                    if found {
                        set_status(&db, &req.run_id, "paused", None).await?;
                    }
                }
                "stop" => {
                    set_status(&db, &req.run_id, "stopping", None).await?;
                    append_log(&db, &req.run_id, "Stopping run").await.ok();
                    facade
                        .request_with_timeout(
                            "tasks.control",
                            json!({ "run_id": req.run_id, "action": "stop" }),
                            TASK_TIMEOUT,
                        )
                        .await?;
                }
                "resume" => {
                    let response = facade
                        .request_with_timeout(
                            "tasks.control",
                            json!({ "run_id": req.run_id, "action": "resume" }),
                            TASK_TIMEOUT,
                        )
                        .await?;
                    let found = response.get("found").and_then(Value::as_bool).unwrap_or(false);
                    if !found {
                        return restart_run(&db, &sessions_dir, &facade, &req.run_id).await;
                    }
                    set_status(&db, &req.run_id, "running", None).await?;
                }
                other => return Err(format!("unknown run action '{other}'")),
            }
            get_run(&db, &req.run_id).await
        }
    });

    let services_restart_db = db.clone();
    let services_restart_dir = sessions_dir.clone();
    app.route("runs.restart", move |facade, req: RunIdReq| {
        let db = services_restart_db.clone();
        let sessions_dir = services_restart_dir.clone();
        async move { restart_run(&db, &sessions_dir, &facade, &req.run_id).await }
    });

    let services_delete_db = db.clone();
    app.route("runs.delete", move |facade, req: RunIdReq| {
        let db = services_delete_db.clone();
        async move {
            let _ = facade
                .request_with_timeout(
                    "tasks.control",
                    json!({ "run_id": req.run_id, "action": "stop" }),
                    TASK_TIMEOUT,
                )
                .await;
            delete_run(&db, &req.run_id).await
        }
    });
}
