use serde_json::Value;

use crate::core::BuilderApp;

pub fn sidecar_module(app: &mut BuilderApp) {
    app.on_event("sidecar_ready", |facade, payload: Value| async move {
        facade.push_ui_route("sidecar_ready", payload);
    });
}
