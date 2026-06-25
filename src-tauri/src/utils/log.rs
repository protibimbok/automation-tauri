use std::collections::VecDeque;
use std::sync::{LazyLock, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{json, Value};

use crate::core::{BuilderApp, Facade};

const MAX_LINES: usize = 500;

static LOG_BUFFER: LazyLock<Mutex<VecDeque<Value>>> =
    LazyLock::new(|| Mutex::new(VecDeque::new()));

fn now_ts() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .unwrap_or(0.0)
}

pub fn push_stderr_line(facade: &Facade, message: &str) {
    let payload = json!({
        "ts": now_ts(),
        "level": "info",
        "source": "stderr",
        "message": message,
    });

    if let Ok(mut buffer) = LOG_BUFFER.lock() {
        buffer.push_back(payload.clone());
        while buffer.len() > MAX_LINES {
            buffer.pop_front();
        }
    }

    facade.push_ui_route("log.line", payload);
}

pub fn log_module(app: &mut BuilderApp) {
    app.route("log.lines", |_facade, _payload: Value| async move {
        let lines: Vec<Value> = LOG_BUFFER
            .lock()
            .map(|buffer| buffer.iter().cloned().collect())
            .unwrap_or_default();
        Ok(json!({ "ok": true, "lines": lines }))
    });
}
