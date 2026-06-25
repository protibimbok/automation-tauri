use serde::Serialize;
use serde_json::{json, Value};
use sqlx::FromRow;

fn parse_json_object(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or_else(|_| json!({}))
}

fn parse_json_optional(raw: Option<&str>) -> Option<Value> {
    raw.and_then(|text| serde_json::from_str(text).ok())
}

#[derive(Debug, Clone, FromRow)]
pub struct SessionRow {
    pub id: String,
    pub platform: String,
    pub name: String,
    pub status: String,
    pub active_run_count: i32,
    pub last_checked_at: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionInfo {
    pub id: String,
    pub platform: String,
    pub name: String,
    pub status: String,
    pub active_run_count: i32,
    pub last_checked_at: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub has_storage: bool,
}

impl SessionRow {
    pub fn into_info(self, has_storage: bool) -> SessionInfo {
        SessionInfo {
            id: self.id,
            platform: self.platform,
            name: self.name,
            status: self.status,
            active_run_count: self.active_run_count,
            last_checked_at: self.last_checked_at,
            created_at: self.created_at,
            updated_at: self.updated_at,
            has_storage,
        }
    }
}

#[derive(Debug, Clone, FromRow)]
pub struct RunRow {
    pub id: String,
    pub platform: String,
    pub task: String,
    pub status: String,
    pub params: String,
    pub log: String,
    pub pause_info: Option<String>,
    pub error: Option<String>,
    pub item_count: i32,
    pub first_run_at: Option<String>,
    pub last_run_at: Option<String>,
    pub re_run_count: i32,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RunInfo {
    pub id: String,
    pub platform: String,
    pub task: String,
    pub status: String,
    pub params: Value,
    pub log: String,
    pub pause_info: Option<Value>,
    pub error: Option<String>,
    pub item_count: i32,
    pub first_run_at: Option<String>,
    pub last_run_at: Option<String>,
    pub re_run_count: i32,
    pub created_at: String,
    pub updated_at: String,
}

impl RunRow {
    pub fn into_info(self) -> RunInfo {
        RunInfo {
            id: self.id,
            platform: self.platform,
            task: self.task,
            status: self.status,
            params: parse_json_object(&self.params),
            log: self.log,
            pause_info: parse_json_optional(self.pause_info.as_deref()),
            error: self.error,
            item_count: self.item_count,
            first_run_at: self.first_run_at,
            last_run_at: self.last_run_at,
            re_run_count: self.re_run_count,
            created_at: self.created_at,
            updated_at: self.updated_at,
        }
    }
}

#[derive(Debug, Clone, FromRow)]
pub struct RunInputRow {
    pub id: String,
    pub run_id: String,
    pub ordinal: i32,
    pub status: String,
    pub data: String,
    pub cursor: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RunInputInfo {
    pub id: String,
    pub run_id: String,
    pub ordinal: i32,
    pub status: String,
    pub data: Value,
    pub cursor: Option<Value>,
    pub created_at: String,
}

impl RunInputRow {
    pub fn into_info(self) -> RunInputInfo {
        RunInputInfo {
            id: self.id,
            run_id: self.run_id,
            ordinal: self.ordinal,
            status: self.status,
            data: parse_json_object(&self.data),
            cursor: parse_json_optional(self.cursor.as_deref()),
            created_at: self.created_at,
        }
    }
}

#[derive(Debug, Clone, FromRow)]
pub struct RunItemRow {
    pub id: String,
    pub run_id: String,
    pub input_id: String,
    pub item_key: String,
    pub ordinal: i32,
    pub data: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct RunItemInfo {
    pub id: String,
    pub run_id: String,
    pub input_id: String,
    pub item_key: String,
    pub ordinal: i32,
    pub data: Value,
    pub created_at: String,
}

impl RunItemRow {
    pub fn into_info(self) -> RunItemInfo {
        RunItemInfo {
            id: self.id,
            run_id: self.run_id,
            input_id: self.input_id,
            item_key: self.item_key,
            ordinal: self.ordinal,
            data: parse_json_object(&self.data),
            created_at: self.created_at,
        }
    }
}
