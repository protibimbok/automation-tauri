use std::{process::ChildStdin, time::Duration};

use super::req_res::new_request;
use crate::sidecar::{BusMessage, ToSidecar};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Emitter};

/// Structured envelope pushed to the React UI via Tauri events.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UiEvent {
    pub route: String,
    pub payload: Value,
}

#[derive(Clone)]
pub struct Facade {
    bus: ToSidecar,
    app: AppHandle,
}

impl Facade {
    pub fn new(stdin: ChildStdin, app: AppHandle) -> Self {
        let bus = ToSidecar::start(stdin);
        Self { bus, app }
    }

    /// Push a structured event to the React UI on `daemon://{channel}`.
    pub fn push_ui(&self, channel: &str, route: &str, payload: Value) {
        let event = format!("daemon://{channel}");
        let _ = self.app.emit(
            &event,
            UiEvent {
                route: route.to_string(),
                payload,
            },
        );
    }

    /// Push using the route prefix as channel (`browser.closed` → `daemon://browser`).
    pub fn push_ui_route(&self, route: &str, payload: Value) {
        let channel = route.split('.').next().unwrap_or(route);
        self.push_ui(channel, route, payload);
    }

    #[allow(unused)]
    pub fn dispatch(&self, event: &str, payload: Value) {
        self.bus
            .send(BusMessage::event(event.to_string(), payload).to_string());
    }

    #[allow(unused)]
    pub async fn request(&self, route: &str, payload: Value) -> Result<Value, String> {
        self.request_with_timeout(route, payload, Duration::from_secs(10)).await
    }

    pub async fn request_with_timeout(
        &self,
        route: &str,
        payload: Value,
        timeout: Duration,
    ) -> Result<Value, String> {
        let (id, waiter) = new_request(timeout);
        self.bus
            .send(BusMessage::request(id, route.to_string(), payload).to_string());
        waiter.await
    }

    pub fn send(&self, body: BusMessage) {
        self.bus.send(body.to_string());
    }
}
