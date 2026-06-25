#![allow(unused)]

use std::future::Future;

use serde::Serialize;
use serde_json::Value;
use async_trait::async_trait;

use super::facade::{Facade};

#[allow(unused)]
pub trait ReqHandler: Sync + Send {
    async fn handle(
        &self,
        app: Facade,
        payload: serde_json::Value,
    ) -> Result<serde_json::Value, String>;
}

#[async_trait]
pub trait ErasedReqHandler: Send + Sync {
    async fn call(&self, app: Facade, payload: Value) -> Result<Value, String>;
}

pub struct TypedReqHandler<Req, Res, F> {
    f: F,
    _req: std::marker::PhantomData<Req>,
    _res: std::marker::PhantomData<Res>,
}

impl<Req, Res, F> TypedReqHandler<Req, Res, F> {
    pub fn new(f: F) -> Self {
        Self { f, _req: Default::default(), _res: Default::default() }
    }
}

#[async_trait]
impl<Req, Res, F, Fut> ErasedReqHandler for TypedReqHandler<Req, Res, F>
where
    Req: serde::de::DeserializeOwned + Send + Sync + 'static,
    Res: Serialize + Send + Sync + 'static,
    F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
    Fut: Future<Output = Result<Res, String>> + Send,
{
    async fn call(&self, app: Facade, payload: Value) -> Result<Value, String> {
        let req: Req =
            serde_json::from_value(payload).map_err(|e| e.to_string())?;

        let res = (self.f)(app, req).await?;

        serde_json::to_value(res).map_err(|e| e.to_string())
    }
}

/* ======= Event Handlers ======= */


pub trait EvtHandler: Sync + Send {
    async fn handle(
        &self,
        app: Facade,
        payload: serde_json::Value,
    ) -> ();
}


#[async_trait]
pub trait ErasedEvtHandler: Send + Sync {
    async fn call(&self, app: Facade, payload: Value);
}

pub struct TypedEvtHandler<Req, F, Fut> {
    f: F,
    _req: std::marker::PhantomData<Req>,
    _fut: std::marker::PhantomData<Fut>,
}

impl<Req, F, Fut> TypedEvtHandler<Req, F, Fut> {
    pub fn new(f: F) -> Self {
        Self { f, _req: Default::default(), _fut: Default::default() }
    }
}

#[async_trait]
impl<Req, F, Fut> ErasedEvtHandler for TypedEvtHandler<Req, F, Fut>
where
    Req: serde::de::DeserializeOwned + Send + Sync + 'static,
    F: Fn(Facade, Req) -> Fut + Send + Sync + 'static,
    Fut: Future<Output = ()> + Send + Sync + 'static,
{
    async fn call(&self, app: Facade, payload: Value) {
        let req: Req =
            serde_json::from_value(payload).map_err(|e| e.to_string()).unwrap();

        (self.f)(app, req).await;
    }
}