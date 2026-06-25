use std::time::Duration;

use serde_json::{json, Value};

use crate::core::BuilderApp;
use crate::db::{
    clear_active_runs, create_default_chrome_session, create_session, delete_session,
    get_session, list_sessions, mark_checked, mark_running, storage_state_path,
    DEFAULT_CHROME_SESSION_ID,
};

use super::payload::session_payload_async;
use super::types::{
    CreateDefaultSessionReq, CreateSessionReq, LaunchSessionReq, PlatformReq, SessionCheckResult,
    SessionIdReq, SessionLaunchResult, SessionLiveRun, SessionStatusResult, SessionStopResult,
    SessionSyncResult, StoredCookie,
};

const SESSION_TIMEOUT: Duration = Duration::from_secs(120);

pub(super) fn register(app: &mut BuilderApp) {
    let db = app.db.clone();
    let sessions_dir = app.sessions_dir.clone();

    let services_list_db = db.clone();
    let services_list_dir = sessions_dir.clone();
    app.route("sessions.list", move |_facade, req: PlatformReq| {
        let db = services_list_db.clone();
        let sessions_dir = services_list_dir.clone();
        async move { list_sessions(&db, &sessions_dir, &req.platform).await }
    });

    let services_create_db = db.clone();
    let services_create_dir = sessions_dir.clone();
    app.route("sessions.create", move |_facade, req: CreateSessionReq| {
        let db = services_create_db.clone();
        let sessions_dir = services_create_dir.clone();
        async move {
            create_session(&db, &sessions_dir, &req.platform, &req.name).await
        }
    });

    let services_create_default_db = db.clone();
    let services_create_default_dir = sessions_dir.clone();
    app.route("sessions.create_default", move |facade, req: CreateDefaultSessionReq| {
        let db = services_create_default_db.clone();
        let sessions_dir = services_create_default_dir.clone();
        async move {
            create_default_chrome_session(&db, &sessions_dir, &req.platform).await?;
            let payload = session_payload_async(
                &db,
                &sessions_dir,
                DEFAULT_CHROME_SESSION_ID,
                Some(&req.platform),
                json!({}),
            )
            .await?;
            facade
                .request_with_timeout("session.sync", payload, SESSION_TIMEOUT)
                .await?;
            get_session(&db, &sessions_dir, DEFAULT_CHROME_SESSION_ID).await
        }
    });

    let services_delete_db = db.clone();
    let services_delete_dir = sessions_dir.clone();
    app.route("sessions.delete", move |facade, req: SessionIdReq| {
        let db = services_delete_db.clone();
        let sessions_dir = services_delete_dir.clone();
        async move {
            let session = get_session(&db, &sessions_dir, &req.session_id).await?;
            if session.active_run_count > 0 {
                let payload = session_payload_async(
                    &db,
                    &sessions_dir,
                    &req.session_id,
                    req.platform.as_deref(),
                    json!({}),
                )
                .await?;
                let _ = facade
                    .request_with_timeout("session.stop", payload, SESSION_TIMEOUT)
                    .await;
                clear_active_runs(&db, &req.session_id).await?;
            }
            delete_session(&db, &sessions_dir, &req.session_id).await
        }
    });

    let services_launch_db = db.clone();
    let services_launch_dir = sessions_dir.clone();
    app.route("sessions.launch", move |facade, req: LaunchSessionReq| {
        let db = services_launch_db.clone();
        let sessions_dir = services_launch_dir.clone();
        async move {
            let payload = session_payload_async(
                &db,
                &sessions_dir,
                &req.session_id,
                req.platform.as_deref(),
                json!({ "headless": false, "fresh": req.fresh.unwrap_or(false) }),
            )
            .await?;
            let value = facade
                .request_with_timeout("session.launch", payload, SESSION_TIMEOUT)
                .await?;
            let run_id = value
                .get("run_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();

            if !run_id.is_empty() {
                mark_running(&db, &req.session_id).await?;
            }

            let updated = get_session(&db, &sessions_dir, &req.session_id).await?;
            Ok(SessionLaunchResult {
                session: updated,
                run_id,
                running: value
                    .get("running")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
                url: value
                    .get("url")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
            })
        }
    });

    let services_check_db = db.clone();
    let services_check_dir = sessions_dir.clone();
    app.route("sessions.check", move |facade, req: SessionIdReq| {
        let db = services_check_db.clone();
        let sessions_dir = services_check_dir.clone();
        async move {
            let session = get_session(&db, &sessions_dir, &req.session_id).await?;
            if session.active_run_count > 0 {
                return Err(format!(
                    "session '{}' is in use ({}) — wait for runs to finish before checking",
                    session.name,
                    session.active_run_count
                ));
            }

            let payload = session_payload_async(
                &db,
                &sessions_dir,
                &req.session_id,
                req.platform.as_deref(),
                json!({}),
            )
            .await?;
            let value = facade
                .request_with_timeout("session.check", payload, SESSION_TIMEOUT)
                .await?;
            mark_checked(&db, &req.session_id).await?;

            let updated = get_session(&db, &sessions_dir, &req.session_id).await?;
            Ok(SessionCheckResult {
                session: updated,
                ok: value.get("ok").and_then(Value::as_bool).unwrap_or(false),
                logged_in: value
                    .get("logged_in")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
                url: value
                    .get("url")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                cookie_count: value
                    .get("cookie_count")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as u32,
            })
        }
    });

    let services_sync_db = db.clone();
    let services_sync_dir = sessions_dir.clone();
    app.route("sessions.sync", move |facade, req: SessionIdReq| {
        let db = services_sync_db.clone();
        let sessions_dir = services_sync_dir.clone();
        async move {
            if req.session_id != DEFAULT_CHROME_SESSION_ID {
                return Err("only Default Chrome can sync from the system profile".into());
            }

            let session = get_session(&db, &sessions_dir, &req.session_id).await?;
            if session.active_run_count > 0 {
                return Err(format!(
                    "session '{}' is in use — close the browser before syncing",
                    session.name
                ));
            }

            let payload = session_payload_async(
                &db,
                &sessions_dir,
                &req.session_id,
                req.platform.as_deref(),
                json!({}),
            )
            .await?;
            let value = facade
                .request_with_timeout("session.sync", payload, SESSION_TIMEOUT)
                .await?;

            let updated = get_session(&db, &sessions_dir, &req.session_id).await?;
            Ok(SessionSyncResult {
                session: updated,
                ok: value.get("ok").and_then(Value::as_bool).unwrap_or(false),
                files_copied: value
                    .get("files_copied")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as u32,
                cookie_count: value
                    .get("cookie_count")
                    .and_then(Value::as_u64)
                    .unwrap_or(0) as u32,
            })
        }
    });

    let services_cookies_dir = sessions_dir.clone();
    app.route("sessions.cookies", move |_facade, req: SessionIdReq| {
        let sessions_dir = services_cookies_dir.clone();
        async move {
            let path = storage_state_path(&sessions_dir, &req.session_id);
            if !path.is_file() {
                return Ok(Vec::<StoredCookie>::new());
            }

            let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
            let value: Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;
            let Some(cookies) = value.get("cookies").and_then(Value::as_array) else {
                return Ok(Vec::new());
            };

            Ok(cookies
                .iter()
                .filter_map(|cookie| {
                    let name = cookie.get("name")?.as_str()?.to_string();
                    Some(StoredCookie {
                        name,
                        domain: cookie
                            .get("domain")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                        path: cookie
                            .get("path")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                        value: cookie
                            .get("value")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                        expires: cookie.get("expires").and_then(Value::as_f64),
                        http_only: cookie
                            .get("httpOnly")
                            .and_then(Value::as_bool)
                            .unwrap_or(false),
                        secure: cookie
                            .get("secure")
                            .and_then(Value::as_bool)
                            .unwrap_or(false),
                        same_site: cookie
                            .get("sameSite")
                            .and_then(Value::as_str)
                            .unwrap_or("Lax")
                            .to_string(),
                    })
                })
                .collect())
        }
    });

    let services_status_db = db.clone();
    let services_status_dir = sessions_dir.clone();
    app.route("sessions.status", move |facade, req: PlatformReq| {
        let db = services_status_db.clone();
        let sessions_dir = services_status_dir.clone();
        async move {
            let value = facade
                .request_with_timeout("session.status", json!({}), SESSION_TIMEOUT)
                .await?;

            let mut running_ids = std::collections::HashSet::new();
            let mut instances = Vec::new();
            if let Some(rows) = value.get("instances").and_then(Value::as_array) {
                for row in rows {
                    let Some(session_id) = row.get("session_id").and_then(Value::as_str) else {
                        continue;
                    };
                    let running = row.get("running").and_then(Value::as_bool).unwrap_or(false);
                    if !running {
                        continue;
                    }
                    running_ids.insert(session_id.to_string());
                    instances.push(SessionLiveRun {
                        session_id: session_id.to_string(),
                        run_id: row
                            .get("run_id")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                        running: true,
                        headless: row
                            .get("headless")
                            .and_then(Value::as_bool)
                            .unwrap_or(false),
                        url: row
                            .get("url")
                            .and_then(Value::as_str)
                            .unwrap_or_default()
                            .to_string(),
                    });
                }
            }

            let sessions = list_sessions(&db, &sessions_dir, &req.platform).await?;
            for session in &sessions {
                if session.active_run_count > 0 && !running_ids.contains(&session.id) {
                    clear_active_runs(&db, &session.id).await?;
                }
            }

            let sessions = list_sessions(&db, &sessions_dir, &req.platform).await?;
            Ok(SessionStatusResult { sessions, instances })
        }
    });

    let services_stop_db = db.clone();
    let services_stop_dir = sessions_dir.clone();
    app.route("sessions.stop", move |facade, req: SessionIdReq| {
        let db = services_stop_db.clone();
        let sessions_dir = services_stop_dir.clone();
        async move {
            let payload = session_payload_async(
                &db,
                &sessions_dir,
                &req.session_id,
                req.platform.as_deref(),
                json!({}),
            )
            .await?;
            let value = facade
                .request_with_timeout("session.stop", payload, SESSION_TIMEOUT)
                .await?;
            clear_active_runs(&db, &req.session_id).await?;

            let updated = get_session(&db, &sessions_dir, &req.session_id).await?;
            Ok(SessionStopResult {
                session: updated,
                run_id: value
                    .get("run_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string(),
                running: value
                    .get("running")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
            })
        }
    });
}
