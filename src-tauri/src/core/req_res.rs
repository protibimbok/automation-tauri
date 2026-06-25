use std::{
    collections::HashMap,
    future::Future,
    sync::{LazyLock, Mutex},
    time::Duration,
};

use serde_json::Value;
use tokio::sync::oneshot;
use tokio::time::timeout;

use crate::{core::Facade, error_log, sidecar::BusMessage};

use super::registry::Registry;

pub struct RequestStates {
    pending_requests: HashMap<String, oneshot::Sender<Value>>,
    counter: std::sync::atomic::AtomicUsize,
}

impl RequestStates {
    fn new() -> Self {
        Self {
            pending_requests: HashMap::new(),
            counter: std::sync::atomic::AtomicUsize::new(0),
        }
    }

    fn insert(
        &mut self,
        timeout_duration: Duration,
    ) -> (
        String,
        impl std::future::Future<Output = Result<Value, String>>,
    ) {
        let (tx, rx) = oneshot::channel::<Value>();
        let id = self
            .counter
            .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        let id = id.to_string();
        let id_clone = id.clone();
        self.pending_requests.insert(id.clone(), tx);
        let waiter = async move {
            match timeout(timeout_duration, rx).await {
                Ok(Ok(value)) => Ok(value),
                Ok(Err(_)) => Err(String::from(format!("#{} channel closed", id_clone))),
                Err(_) => Err(String::from(format!("#{} timeout", id_clone))),
            }
        };
        (id, waiter)
    }

    fn respond(&mut self, id: String, value: Value) {
        if let Some(tx) = self.pending_requests.remove(&id) {
            tx.send(value).unwrap();
        }
    }
}

static PENDING_REQUESTS: LazyLock<Mutex<RequestStates>> =
    LazyLock::new(|| Mutex::new(RequestStates::new()));

pub fn new_request(timeout_duration: Duration) -> (String, impl Future<Output = Result<Value, String>>) {
    PENDING_REQUESTS.lock().unwrap().insert(timeout_duration)
}

pub fn get_message_handler(
    registry: &Registry,
    facade: Facade,
    rt: tokio::runtime::Handle,
) -> Box<dyn Fn(String) + Send + Sync + 'static> {
    let (event_handlers, request_handlers) = registry.clone_sidecar_handlers();
    let rt_for_message = rt.clone();

    let on_message = move |message: String| {
        let message = message.trim();
        let Ok(msg) = serde_json::from_str::<BusMessage>(&message) else {
            error_log!("invalid json: {message}");
            return;
        };

        match msg.kind.as_str() {
            "event" => {
                if let Some(handlers) = event_handlers.get(&msg.route) {
                    for handler in handlers.clone() {
                        let payload = msg.payload.clone();
                        let facade = facade.clone();
                        rt_for_message.spawn(async move {
                            handler.call(facade, payload).await;
                        });
                    }
                } else {
                    error_log!("no handler for event: {}", msg.route);
                }
            }
            "request" => {
                if let Some(handler) = request_handlers.get(&msg.route).cloned() {
                    let payload = msg.payload.clone();
                    let facade = facade.clone();
                    rt_for_message.spawn(async move {
                        match handler.call(facade.clone(), payload).await {
                            Ok(res) => {
                                facade.send(msg.to_response(res));
                            }
                            Err(e) => {
                                error_log!("request handler error: {e}");
                            }
                        }
                    });
                } else {
                    error_log!("no handler for request: {}", msg.route);
                }
            }
            "response" => {
                if msg.id == "" {
                    error_log!("response message has no id");
                    return;
                }

                PENDING_REQUESTS
                    .lock()
                    .unwrap()
                    .respond(msg.id, msg.payload);
            }
            _ => error_log!("unknown message kind: {}", msg.kind),
        }
    };
    Box::new(on_message)
}

