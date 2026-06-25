mod events;
mod payload;
mod routes;
mod types;

use crate::core::BuilderApp;

pub fn sessions_module(app: &mut BuilderApp) {
    routes::register(app);
    events::register(app);
}
