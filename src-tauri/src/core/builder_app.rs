#![allow(unused)]

use std::future::Future;
use std::path::PathBuf;

use serde::Serialize;
use serde_json::Value;
use sqlx::SqlitePool;

use crate::core::{Facade, Registry};
use crate::sidecar::BusMessage;

pub struct BuilderApp {
    facade: Facade,
    registry: Registry,
    pub db: SqlitePool,
    pub sessions_dir: PathBuf,
}

impl BuilderApp {
    pub fn new(facade: Facade, registry: Registry, db: SqlitePool, sessions_dir: PathBuf) -> Self {
        Self {
            facade,
            registry,
            db,
            sessions_dir,
        }
    }

    pub fn registry(&self) -> &Registry {
        &self.registry
    }

    pub fn on_event<Req, F, Fut>(&mut self, event: &str, handler: F)
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = ()> + Send + Sync + 'static,
    {
        self.registry.on_event(event, handler);
    }

    pub fn on_request<Req, Res, F, Fut>(&mut self, request: &str, handler: F)
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        Res: Serialize + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = Result<Res, String>> + Send + Sync + 'static,
    {
        self.registry.on_request(request, handler);
    }

    pub fn route<Req, Res, F, Fut>(&mut self, route: &str, handler: F)
    where
        Req: serde::de::DeserializeOwned + Send + Sync + 'static,
        Res: Serialize + Send + Sync + 'static,
        F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = Result<Res, String>> + Send + 'static,
    {
        self.registry.route(route, handler);
    }


    /* ======= Facade Methods ======= */

    pub fn dispatch(&self, event: &str, payload: Value) {
        self.facade.dispatch(event, payload);
    }

    pub async fn request(&self, route: &str, payload: Value) -> Result<Value, String> {
        self.facade.request(route, payload).await
    }

    pub fn send(&self, body: BusMessage) {
        self.facade.send(body);
    }
}