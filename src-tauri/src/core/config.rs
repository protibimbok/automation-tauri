use std::path::PathBuf;
use tauri::path::BaseDirectory;
use tauri::{AppHandle, Manager};
pub struct Config {
    pub dev: bool,
    pub sidecar_bundle: PathBuf,
    pub project_root: PathBuf,
    pub db_path: PathBuf,
    pub sessions_dir: PathBuf,
}

impl Config {
    pub fn init(app: &AppHandle) -> Self {
        let data_dir = app
            .path()
            .app_data_dir()
            .map_err(|e| format!("app_data_dir: {e}"))
            .unwrap();
        std::fs::create_dir_all(&data_dir)
            .map_err(|e| e.to_string())
            .unwrap();

        let project_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_else(|| PathBuf::from("."));

        let sidecar_bundle = app
            .path()
            .resolve("sidecar", BaseDirectory::Resource)
            .unwrap_or_else(|_| data_dir.join("sidecar"));

        Self {
            dev: cfg!(debug_assertions),
            sidecar_bundle,
            project_root,
            db_path: data_dir.join("tauri-py.db"),
            sessions_dir: data_dir.join("sessions"),
        }
    }
}
