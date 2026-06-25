mod core;
mod db;
mod macros;
mod modules;
mod sidecar;
mod utils;

use crate::core::{
    get_message_handler, handle_frontend_request, BuilderApp, Config, Facade, Registry, UiApp,
};
use crate::db::init;
use crate::sidecar::{spawn_daemon, FromSidecar};
use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let rt = tokio::runtime::Runtime::new()
                .map_err(|e| format!("failed to create tokio runtime: {e}"))?;
            let handle = rt.handle().clone();

            let config = Config::init(app.handle());
            std::fs::create_dir_all(&config.sessions_dir)
                .map_err(|e| e.to_string())?;

            let db = rt
                .block_on(init(&config.db_path))
                .map_err(|e| format!("failed to initialize database: {e}"))?;

            let child = spawn_daemon(&config)?;

            let facade = Facade::new(child.stdin.unwrap(), app.handle().clone());

            let mut builder_app = BuilderApp::new(
                facade.clone(),
                Registry::new(),
                db,
                config.sessions_dir.clone(),
            );

            utils::browser::browser_module(&mut builder_app);
            utils::log::log_module(&mut builder_app);
            utils::sidecar::sidecar_module(&mut builder_app);
            for module in modules::get_modules() {
                module(&mut builder_app);
            }

            let on_message = get_message_handler(
                builder_app.registry(),
                facade.clone(),
                handle,
            );

            FromSidecar::start(child.stdout.unwrap(), on_message);

            FromSidecar::start_stderr(child.stderr.unwrap(), {
                let facade = facade.clone();
                move |line| {
                    error_log!("{line}");
                    utils::log::push_stderr_line(&facade, &line);
                }
            });

            let ui_app = UiApp::new(facade.clone(), builder_app.registry());
            app.manage(ui_app);
            app.manage(rt);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![handle_frontend_request])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
