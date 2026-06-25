use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::core::{Facade, Registry};
use crate::core::registry::RequestHandlers;


#[derive(Debug, Serialize, Deserialize)]
pub struct FrontendRequest {
    route: String,
    payload: Value,
}

pub struct UiApp {
    facade: Facade,
    handlers: RequestHandlers,
}

impl UiApp {
    pub fn new(facade: Facade, registry: &Registry) -> Self {
        let handlers = registry.get_route_handlers();
        Self { facade, handlers }
    }

    pub async fn handle_request(&self, request: FrontendRequest) -> Result<Value, String> {
        if let Some(handler) = self.handlers.get(&request.route).cloned() {
            handler.call(self.facade.clone(), request.payload).await
        } else {
            Err(format!("No handler found for route: {}", request.route))
        }
    }
}