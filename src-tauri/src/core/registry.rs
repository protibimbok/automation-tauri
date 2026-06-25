use std::collections::HashMap;
use std::future::Future;
use std::sync::Arc;
use serde::Serialize;


use crate::core::handler::TypedEvtHandler;

use super::handler::{ErasedReqHandler, ErasedEvtHandler, TypedReqHandler};
use super::facade::Facade;

pub type EventHandlers = HashMap<String, Vec<Arc<dyn ErasedEvtHandler>>>;
pub type RequestHandlers = HashMap<String, Arc<dyn ErasedReqHandler>>;

pub struct Registry {
    frontend_request_handlers: RequestHandlers,
    sidecar_event_handlers: EventHandlers,
    sidecar_request_handlers: RequestHandlers,
}

impl Registry {
    pub fn new() -> Self {
        Self { frontend_request_handlers: HashMap::new(), sidecar_event_handlers: HashMap::new(), sidecar_request_handlers: HashMap::new() }
    }

    pub fn route<Req, Res, F, Fut>(
        &mut self,
        route: impl Into<String>,
        handler: F,
    )
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        Res: Serialize + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = Result<Res, String>> + Send + 'static,
    {
        self.frontend_request_handlers.insert(
            route.into(),
            Arc::new(TypedReqHandler::new(handler)),
        );
    }

    #[allow(unused)]
    pub fn on_event<Req, F, Fut>(
        &mut self,
        event: impl Into<String>,
        handler: F,
    )
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = ()> + Send + Sync + 'static,
    {
        self.sidecar_event_handlers.entry(event.into())
        .or_insert_with(|| Vec::new()).push(Arc::new(TypedEvtHandler::<Req, F, Fut>::new(handler)));
    }

    #[allow(unused)]
    pub fn on_request<Req, Res, F, Fut>(
        &mut self,
        route: impl Into<String>,
        handler: F,
    )
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        Res: Serialize + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = Result<Res, String>> + Send + 'static,
    {
        self.sidecar_request_handlers.insert(
            route.into(),
            Arc::new(TypedReqHandler::new(handler)),
        );
    }

    pub(super) fn get_route_handlers(&self) -> RequestHandlers {
        self.frontend_request_handlers.clone()
    }

    pub(super) fn clone_sidecar_handlers(&self) -> (EventHandlers, RequestHandlers) {
        (
            self.sidecar_event_handlers.clone(),
            self.sidecar_request_handlers.clone(),
        )
    }
}