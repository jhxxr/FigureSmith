//! FigureSmith desktop library entry (Tauri 2).

mod commands;
mod sidecar;

use commands::{
    get_session, import_rmbg_archive, import_rmbg_folder, import_sam3_model, inject_session_bridge,
    open_models_directory,
};
use sidecar::{resolve_repo_root, SidecarState};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    Emitter, Manager, RunEvent, WindowEvent,
};
use tauri::webview::PageLoadEvent;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            get_session,
            import_sam3_model,
            import_rmbg_archive,
            import_rmbg_folder,
            open_models_directory,
        ])
        .on_page_load(|webview, payload| {
            if payload.event() != PageLoadEvent::Finished {
                return;
            }
            if let Some(state) = webview.try_state::<SidecarState>() {
                if let Ok(session) = state.session() {
                    inject_session_bridge(&webview, &session);
                }
            }
        })
        .setup(|app| {
            // Build menu: Models import actions (MVP without redesigning vendor UI).
            let handle = app.handle().clone();
            let menu = build_menu(app.handle())?;
            app.set_menu(menu)?;

            app.on_menu_event(move |app, event| {
                let id = event.id().as_ref();
                match id {
                    "import_sam3" => {
                        let app2 = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let state = match app2.try_state::<SidecarState>() {
                                Some(s) => s,
                                None => return,
                            };
                            let _ = import_sam3_model(app2.clone(), state, None).await;
                        });
                    }
                    "import_rmbg_zip" => {
                        let app2 = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let state = match app2.try_state::<SidecarState>() {
                                Some(s) => s,
                                None => return,
                            };
                            let _ = import_rmbg_archive(app2.clone(), state, None).await;
                        });
                    }
                    "import_rmbg_folder" => {
                        let app2 = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let state = match app2.try_state::<SidecarState>() {
                                Some(s) => s,
                                None => return,
                            };
                            let _ = import_rmbg_folder(app2.clone(), state, None).await;
                        });
                    }
                    "open_models_dir" => {
                        let app2 = app.clone();
                        tauri::async_runtime::spawn(async move {
                            let state = match app2.try_state::<SidecarState>() {
                                Some(s) => s,
                                None => return,
                            };
                            let _ = open_models_directory(app2.clone(), state).await;
                        });
                    }
                    _ => {}
                }
            });

            // Start Python sidecar before the UI becomes useful.
            let repo = resolve_repo_root().map_err(|e| {
                eprintln!("[FigureSmith] {e}");
                e
            })?;
            eprintln!("[FigureSmith] repo root: {}", repo.display());
            let sidecar = SidecarState::start(repo).map_err(|e| {
                eprintln!("[FigureSmith] sidecar start failed: {e}");
                e
            })?;
            let session = sidecar.session()?;
            app.manage(sidecar);

            // Notify frontend that backend is ready (splash may also poll get_session).
            let _ = handle.emit("sidecar-ready", &session);

            Ok(())
        });

    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building FigureSmith");

    app.run(|app_handle, event| {
        match event {
            RunEvent::Exit | RunEvent::ExitRequested { .. } => {
                if let Some(state) = app_handle.try_state::<SidecarState>() {
                    state.shutdown();
                }
            }
            RunEvent::WindowEvent { label, event, .. } => {
                if label == "main" {
                    if let WindowEvent::CloseRequested { .. } = event {
                        if let Some(state) = app_handle.try_state::<SidecarState>() {
                            state.shutdown();
                        }
                    }
                }
            }
            _ => {}
        }
    });
}

fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let import_sam3 =
        MenuItem::with_id(app, "import_sam3", "Import SAM3 Checkpoint…", true, None::<&str>)?;
    let import_rmbg_zip =
        MenuItem::with_id(app, "import_rmbg_zip", "Import RMBG ZIP…", true, None::<&str>)?;
    let import_rmbg_folder = MenuItem::with_id(
        app,
        "import_rmbg_folder",
        "Import RMBG Folder…",
        true,
        None::<&str>,
    )?;
    let open_models =
        MenuItem::with_id(app, "open_models_dir", "Open Models Directory", true, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(app)?;

    let models = Submenu::with_items(
        app,
        "Models",
        true,
        &[
            &import_sam3,
            &import_rmbg_zip,
            &import_rmbg_folder,
            &sep,
            &open_models,
        ],
    )?;

    // Keep a minimal app menu with quit on all platforms.
    let quit = PredefinedMenuItem::quit(app, Some("Quit FigureSmith"))?;
    let app_menu = Submenu::with_items(app, "FigureSmith", true, &[&quit])?;

    Menu::with_items(app, &[&app_menu, &models])
}
