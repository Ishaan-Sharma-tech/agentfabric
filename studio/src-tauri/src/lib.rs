// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::{Arc, Mutex};

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let server_child: Arc<Mutex<Option<std::process::Child>>> = Arc::new(Mutex::new(None));
    let server_child_clone = server_child.clone();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(move |_app| {
            // Check if port 8000 is open (i.e. server is already running)
            let is_running = std::net::TcpStream::connect_timeout(
                &"127.0.0.1:8000".parse().unwrap(),
                std::time::Duration::from_millis(200)
            ).is_ok();

            if !is_running {
                println!("AgentFabric FastAPI Server is not running. Starting it...");
                let mut cmd = std::process::Command::new("uv");
                cmd.args(&[
                    "run",
                    "uvicorn",
                    "agent_fabric.server.app:create_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ]);
                cmd.current_dir("..");
                
                #[cfg(target_os = "windows")]
                {
                    // CREATE_NO_WINDOW creation flag for Windows (0x08000000)
                    // Prevents cmd shell window popup
                    use std::os::windows::process::CommandExt;
                    cmd.creation_flags(0x08000000);
                }

                match cmd.spawn() {
                    Ok(child) => {
                        *server_child.lock().unwrap() = Some(child);
                        println!("Started FastAPI server in background.");
                    }
                    Err(e) => {
                        eprintln!("Failed to spawn FastAPI server via uv: {}. Trying fallback 'python -m uvicorn'...", e);
                        let mut cmd2 = std::process::Command::new("python");
                        cmd2.args(&[
                            "-m",
                            "uvicorn",
                            "agent_fabric.server.app:create_app",
                            "--factory",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "8000",
                        ]);
                        cmd2.current_dir("..");
                        #[cfg(target_os = "windows")]
                        {
                            use std::os::windows::process::CommandExt;
                            cmd2.creation_flags(0x08000000);
                        }
                        if let Ok(child) = cmd2.spawn() {
                            *server_child.lock().unwrap() = Some(child);
                            println!("Started FastAPI server in background (fallback).");
                        } else {
                            eprintln!("Could not start Python server. Make sure Python is in PATH.");
                        }
                    }
                }
            } else {
                println!("AgentFabric FastAPI Server is already running on port 8000.");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |_app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            let mut lock = server_child_clone.lock().unwrap();
            if let Some(mut child) = lock.take() {
                println!("Killing FastAPI server child process on app exit...");
                let _ = child.kill();
            }
        }
    });
}
