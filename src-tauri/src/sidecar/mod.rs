mod bus;

#[cfg(windows)]
const DAEMON_EXE: &str = "tauri-py-daemon.exe";
#[cfg(not(windows))]
const DAEMON_EXE: &str = "tauri-py-daemon";

pub use bus::{spawn_daemon, ToSidecar, FromSidecar};
use serde::{Deserialize, Serialize};
use serde_json::Value;


#[derive(Debug, Serialize, Deserialize)]
pub struct BusMessage {
    pub kind: String,
    pub id: String,
    pub route: String,
    pub payload: Value,
}

impl BusMessage {
    pub fn event( name: String, payload: Value) -> Self {
        Self { kind: "event".to_string(), id: "".to_string(), route: name, payload }
    }

    pub fn request( id: String, route: String, payload: Value) -> Self {
        Self { kind: "request".to_string(), id, route, payload }
    }


    pub fn to_response(self, payload: Value) -> Self {
        Self { kind: "response".to_string(), id: self.id, route: self.route, payload }
    }
}

impl ToString for BusMessage {
    fn to_string(&self) -> String {
        serde_json::to_string(self).unwrap()
    }
}
