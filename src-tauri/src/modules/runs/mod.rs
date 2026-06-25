mod events;
mod payload;
mod routes;
mod types;

use std::time::Duration;

use crate::core::BuilderApp;

pub(crate) const TASK_TIMEOUT: Duration = Duration::from_secs(30);
pub(crate) const UI_CHANNEL: &str = "runs";

pub fn runs_module(app: &mut BuilderApp) {
    routes::register(app);
    events::register(app);
}
