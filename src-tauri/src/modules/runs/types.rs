use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Deserialize)]
pub(super) struct ListRunsReq {
    pub platform: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct RunIdReq {
    pub run_id: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct RunItemsReq {
    pub run_id: String,
    pub input_id: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct StartRunReq {
    pub platform: String,
    pub task: String,
    #[serde(default)]
    pub params: Value,
    #[serde(default)]
    pub inputs: Vec<Value>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ControlReq {
    pub run_id: String,
    pub action: String,
}
