#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager};
use std::collections::HashMap;
use std::env;

#[tauri::command]
fn ping() -> String {
    "pong".into()
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Compute a port (static default for simplicity)
            let port = env::var("PORT").unwrap_or_else(|_| "42069".to_string());

            // Compute DATA_DIR under app data directory if not provided
            let app_handle = app.handle();
            let app_data_dir = app_handle
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| app_handle.path().home_dir().unwrap());
            let data_dir = env::var("DATA_DIR")
                .unwrap_or_else(|_| app_data_dir.join("LocalChessAnalyzer").join("data").to_string_lossy().to_string());

            // Attempt to run bundled backend sidecar: we'll resolve per-target binary path
            #[cfg(target_os = "windows")]
            let bin = "lca-backend.exe";
            #[cfg(not(target_os = "windows"))]
            let bin = "lca-backend";

            let mut envs = HashMap::new();
            envs.insert("PORT".into(), port.clone());
            envs.insert("DATA_DIR".into(), data_dir.clone());

            // STOCKFISH_PATH can be provided by the runner if the binary lives inside the app
            if let Ok(sf) = env::var("STOCKFISH_PATH") {
                envs.insert("STOCKFISH_PATH".into(), sf);
            }

            tauri::async_runtime::spawn(async move {
                let _ = tauri::api::process::Command::new_sidecar(bin)
                    .expect("failed to setup sidecar")
                    .envs(envs)
                    .spawn();
            });

            // Let the UI know which port to talk to
            app.get_window("main").map(|w| {
                let _ = w.emit("backend-ready", port);
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![ping])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}


