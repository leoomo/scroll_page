use serde::{Deserialize, Serialize};

const PYTHON_API_BASE: &str = "http://127.0.0.1:8765";

#[derive(Default)]
pub struct AppState {
    pub connected: bool,
}

#[derive(Serialize, Deserialize)]
pub struct HeadStateData {
    pub state: String,
    pub head_offset: Option<f64>,
    pub calibrated: bool,
    pub neutral_y: Option<f64>,
    pub enabled: bool,
    pub face_detected: bool,
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
async fn get_state() -> Result<HeadStateData, String> {
    let client = reqwest::Client::new();
    let response = client
        .get(format!("{}/api/state", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    response.json::<HeadStateData>().await.map_err(|e| e.to_string())
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

#[tauri::command]
async fn set_config(config_data: Config) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .put(format!("{}/api/config", PYTHON_API_BASE))
        .json(&config_data)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn calibrate_neutral() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibrate/neutral", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn calibrate_neutral_stop() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibrate/neutral/stop", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn save_calibration() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibration/save", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn reset_calibration() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/calibration/reset", PYTHON_API_BASE))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    response.json().await.map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
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
            get_state,
            get_config,
            set_config,
            set_enabled,
            check_connection,
            calibrate_neutral,
            calibrate_neutral_stop,
            save_calibration,
            reset_calibration,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
