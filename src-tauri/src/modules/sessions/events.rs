use serde_json::Value;

use crate::core::BuilderApp;
use crate::db::mark_idle;

pub(super) fn register(app: &mut BuilderApp) {
    let db = app.db.clone();

    let services_closed_db = db.clone();
    app.on_event("session.closed", move |facade, payload: Value| {
        let db = services_closed_db.clone();
        async move {
            if let Some(session_id) = payload.get("session_id").and_then(Value::as_str) {
                let pool = db.clone();
                let sid = session_id.to_string();
                tokio::spawn(async move {
                    let _ = mark_idle(&pool, &sid).await;
                });
            }
            facade.push_ui_route("session.closed", payload);
        }
    });

    app.on_event("session.updated", |facade, payload: Value| async move {
        facade.push_ui_route("session.updated", payload);
    });
}
