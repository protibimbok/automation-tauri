use serde::{Deserialize, Serialize};

use crate::db::SessionInfo;

#[derive(Debug, Deserialize)]
pub(super) struct PlatformReq {
    pub platform: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct CreateSessionReq {
    pub platform: String,
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct CreateDefaultSessionReq {
    pub platform: String,
}

#[derive(Debug, Deserialize)]
pub(super) struct SessionIdReq {
    pub session_id: String,
    pub platform: Option<String>,
}

#[derive(Debug, Deserialize)]
pub(super) struct LaunchSessionReq {
    pub session_id: String,
    pub fresh: Option<bool>,
    pub platform: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StoredCookie {
    pub name: String,
    pub domain: String,
    pub path: String,
    pub value: String,
    pub expires: Option<f64>,
    pub http_only: bool,
    pub secure: bool,
    pub same_site: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionLaunchResult {
    pub session: SessionInfo,
    pub run_id: String,
    pub running: bool,
    pub url: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionCheckResult {
    pub session: SessionInfo,
    pub ok: bool,
    pub logged_in: bool,
    pub url: String,
    pub cookie_count: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionLiveRun {
    pub session_id: String,
    pub run_id: String,
    pub running: bool,
    pub headless: bool,
    pub url: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionStatusResult {
    pub sessions: Vec<SessionInfo>,
    pub instances: Vec<SessionLiveRun>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionSyncResult {
    pub session: SessionInfo,
    pub ok: bool,
    pub files_copied: u32,
    pub cookie_count: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionStopResult {
    pub session: SessionInfo,
    pub run_id: String,
    pub running: bool,
}
