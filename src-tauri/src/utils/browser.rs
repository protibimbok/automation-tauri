use std::time::Duration;

use serde_json::Value;

use crate::core::{BuilderApp, Facade};

fn proxy_request(
    facade: Facade,
    route: &'static str,
    payload: Value,
    timeout: Duration,
) -> impl std::future::Future<Output = Result<Value, String>> {
    async move { facade.request_with_timeout(route, payload, timeout).await }
}

pub fn browser_module(app: &mut BuilderApp) {
    app.route("browser.launch", |facade, payload: Value| async move {
        proxy_request(facade, "browser.launch", payload, Duration::from_secs(120)).await
    });

    app.route("browser.stop", |facade, payload: Value| async move {
        proxy_request(facade, "browser.stop", payload, Duration::from_secs(30)).await
    });

    app.route("browser.status", |facade, payload: Value| async move {
        proxy_request(facade, "browser.status", payload, Duration::from_secs(30)).await
    });

    app.route("browser.recover", |facade, payload: Value| async move {
        proxy_request(facade, "browser.recover", payload, Duration::from_secs(120)).await
    });

    app.route("browser.control", |facade, payload: Value| async move {
        proxy_request(facade, "browser.control", payload, Duration::from_secs(30)).await
    });

    app.route("browser.install.status", |facade, payload: Value| async move {
        proxy_request(facade, "browser.install.status", payload, Duration::from_secs(30)).await
    });

    app.route("browser.install.run", |facade, payload: Value| async move {
        proxy_request(facade, "browser.install.run", payload, Duration::from_secs(600)).await
    });

    app.on_event("browser.closed", |facade, payload: Value| async move {
        facade.push_ui_route("browser.closed", payload);
    });

    app.on_event("browser.updated", |facade, payload: Value| async move {
        facade.push_ui_route("browser.updated", payload);
    });

    app.on_event("browser.install.progress", |facade, payload: Value| async move {
        facade.push_ui_route("browser.install.progress", payload);
    });
}
