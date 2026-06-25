use crate::core::BuilderApp;

pub mod runs;
pub mod sessions;

pub fn get_modules() -> Vec<fn(&mut BuilderApp)> {
    vec![sessions::sessions_module, runs::runs_module]
}
