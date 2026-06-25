mod config;
mod handler;
mod registry;
mod facade;
mod req_res;
mod ui_app;
mod builder_app;

pub use config::Config;
pub use registry::Registry;
pub use facade::{Facade};
pub use ui_app::UiApp;
pub use builder_app::BuilderApp;
pub use req_res::get_message_handler;

use serde_json::Value;
use tauri::State;

use crate::core::ui_app::FrontendRequest;


#[tauri::command]
pub async fn handle_frontend_request(state: State<'_, UiApp>, req: FrontendRequest) -> Result<Value, String> {
    state.handle_request(req).await.map_err(|e| format!("failed to handle frontend request: {e}"))
}