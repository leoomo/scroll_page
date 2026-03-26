use serde::{Deserialize, Serialize};

const PYTHON_API_BASE: &str = "http://127.0.0.1:8765";

#[derive(Default)]
pub struct AppState {
    pub connected: bool,
}

#[derive(Serialize, Deserialize)]
pub struct GazeData {
    pub raw_x: Option<f64>,
    pub raw_y: Option<f64>,
    pub screen_y: Option<f64>,
    pub zone: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct StateData {
    pub state: String,
    pub gaze_point: Option<(f64, f64)>,
}

#[derive(Serialize, Deserialize)]
pub struct Config {
    pub scroll_zone_ratio: f64,
    pub dwell_time_ms: i32,
    pub scroll_distance: i32,
    pub scroll_interval_ms: i32,
    pub detection_confidence: f64,
    pub up_scroll_enabled: bool,
    pub up_scroll_ratio: f64,
    pub up_dwell_time_ms: i32,
    pub up_scroll_distance: i32,
    pub up_scroll_interval_ms: i32,
}

#[tauri::command]
async fn get_gaze() -> Result<GazeData, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/gaze", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json::<GazeData>().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_state() -> Result<StateData, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/state", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json::<StateData>().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn calibrate_top() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibrate/top", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn calibrate_bottom() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibrate/bottom", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_config() -> Result<Config, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/config", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json::<Config>().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn set_enabled(enabled: bool) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let url = if enabled {
        format!("{}/api/enable", PYTHON_API_BASE)
    } else {
        format!("{}/api/disable", PYTHON_API_BASE)
    };
    let response = client.post(&url).send().await.map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn check_connection() -> Result<bool, String> {
    let client = reqwest::Client::new();
    match client.get(format!("{}/api/state", PYTHON_API_BASE)).send().await {
        Ok(_) => Ok(true),
        Err(_) => Ok(false),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_gaze,
            get_state,
            calibrate_top,
            calibrate_bottom,
            get_config,
            set_enabled,
            check_connection,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
