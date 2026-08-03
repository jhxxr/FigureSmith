//! FigureSmith desktop library entry (Tauri 2).

mod commands;
mod sidecar;

use commands::{
    build_initialization_script, import_rmbg_archive, import_rmbg_folder, import_sam3_model,
    open_models_directory,
};
use serde::Serialize;
use sidecar::{resolve_runtime_root, SidecarState, StartupProgress};
use std::sync::Once;
use tauri::{
    ipc::CapabilityBuilder,
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    webview::{NewWindowResponse, PageLoadEvent, WebviewWindowBuilder},
    Emitter, Manager, RunEvent, Url, WebviewUrl, WindowEvent,
};

static STARTUP_SCHEDULED: Once = Once::new();

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            import_sam3_model,
            import_rmbg_archive,
            import_rmbg_folder,
            open_models_directory,
        ])
        .on_page_load(|webview, payload| {
            if webview.label() == "splash" && payload.event() == PageLoadEvent::Finished {
                schedule_startup(webview.app_handle().clone());
            }
        })
        .setup(|app| {
            // Build menu: Models import actions (MVP without redesigning vendor UI).
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

            Ok(())
        });

    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building FigureSmith");

    app.run(|app_handle, event| match event {
        RunEvent::Exit | RunEvent::ExitRequested { .. } => {
            if let Some(state) = app_handle.try_state::<SidecarState>() {
                state.shutdown();
            }
        }
        RunEvent::WindowEvent {
            label,
            event: WindowEvent::CloseRequested { .. },
            ..
        } if label == "main" => {
            if let Some(state) = app_handle.try_state::<SidecarState>() {
                state.shutdown();
            }
        }
        _ => {}
    });
}

#[derive(Debug, Clone, Serialize)]
struct StartupStatus {
    phase: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    checked_files: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    total_files: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    detail: Option<String>,
}

fn emit_startup_status(
    app: &tauri::AppHandle,
    phase: &str,
    code: Option<&str>,
    checked_files: Option<usize>,
    total_files: Option<usize>,
    detail: Option<&str>,
) {
    let _ = app.emit(
        "startup-status",
        StartupStatus {
            phase: phase.to_string(),
            code: code.map(str::to_string),
            checked_files,
            total_files,
            detail: detail.map(|value| value.chars().take(500).collect()),
        },
    );
}

fn report_startup_error(app: &tauri::AppHandle, code: &str, message: &str) {
    // Startup errors are intentionally bounded and contain no environment or
    // session-token values. The local splash owns the user-visible rendering.
    let bounded = message.chars().take(500).collect::<String>();
    eprintln!("[FigureSmith] startup failed: {bounded}");
    emit_startup_status(app, "error", Some(code), None, None, Some(&bounded));
    let _ = app.emit("sidecar-error", bounded);
}

fn schedule_startup(app: tauri::AppHandle) {
    STARTUP_SCHEDULED.call_once(|| {
        // Runtime hashing and the blocking sidecar readiness probe must not
        // run on Tauri's setup/UI thread. Scheduling after the Splash page has
        // loaded ensures its status listener can display even fast failures.
        tauri::async_runtime::spawn_blocking(move || start_sidecar(app));
    });
}

fn start_sidecar(app: tauri::AppHandle) {
    emit_startup_status(&app, "locating", None, None, None, None);
    let resource_dir = app.path().resource_dir().ok();
    let runtime_root = match resolve_runtime_root(resource_dir) {
        Ok(root) => root,
        Err(err) => {
            report_startup_error(&app, "runtime-missing", &err);
            return;
        }
    };
    eprintln!(
        "[FigureSmith] runtime root located: {}",
        runtime_root.display()
    );

    emit_startup_status(&app, "verifying", None, Some(0), None, None);
    let progress_app = app.clone();
    let sidecar =
        match SidecarState::start_with_progress(runtime_root, move |progress| match progress {
            StartupProgress::Verifying {
                checked_files,
                total_files,
            } => emit_startup_status(
                &progress_app,
                "verifying",
                None,
                Some(checked_files),
                Some(total_files),
                None,
            ),
            StartupProgress::Starting => {
                emit_startup_status(&progress_app, "starting", None, None, None, None)
            }
        }) {
            Ok(sidecar) => sidecar,
            Err(err) => {
                report_startup_error(&app, classify_sidecar_error(&err), &err);
                return;
            }
        };

    let session = match sidecar.session() {
        Ok(session) => session,
        Err(err) => {
            report_startup_error(&app, "backend-failed", &err);
            return;
        }
    };
    emit_startup_status(&app, "ready", None, None, None, None);

    let main_thread_app = app.clone();
    if let Err(err) = app.run_on_main_thread(move || {
        main_thread_app.manage(sidecar);
        if let Some(state) = main_thread_app.try_state::<SidecarState>() {
            let app_for_monitor = main_thread_app.clone();
            state.start_liveness_monitor(move || {
                eprintln!("[FigureSmith] closing remote UI after sidecar loss");
                if let Some(main) = app_for_monitor.get_webview_window("main") {
                    let _ = main.close();
                }
                app_for_monitor.exit(1);
            });
        }

        // Grant only the four native actions to the exact sidecar origin, then
        // create the authenticated remote window. It stays hidden until its
        // authenticated page has finished loading.
        if let Err(err) = create_remote_main(&main_thread_app, &session) {
            if let Some(state) = main_thread_app.try_state::<SidecarState>() {
                state.shutdown();
            }
            report_startup_error(&main_thread_app, "backend-failed", &err.to_string());
        }
    }) {
        report_startup_error(
            &app,
            "backend-failed",
            &format!("startup handoff failed: {err}"),
        );
    }
}

fn classify_sidecar_error(message: &str) -> &'static str {
    if message.starts_with("runtime invalid:") {
        "runtime-invalid"
    } else {
        "backend-failed"
    }
}

fn is_exact_sidecar_origin(url: &Url, api_base: &str) -> bool {
    let Ok(expected) = Url::parse(api_base) else {
        return false;
    };
    url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.username().is_empty()
        && url.password().is_none()
        && url.port().is_some()
        && expected.port().is_some()
        && url.port() == expected.port()
        && expected.scheme() == "http"
        && expected.host_str() == Some("127.0.0.1")
}

fn create_remote_main(app: &tauri::AppHandle, session: &sidecar::SessionInfo) -> tauri::Result<()> {
    let api_base = session.api_base.clone();
    app.add_capability(
        CapabilityBuilder::new(format!("figuresmith-sidecar-{}", session.port))
            .local(false)
            .window("main")
            .remote(format!("{api_base}/*"))
            .permission("allow-import-sam3-model")
            .permission("allow-import-rmbg-archive")
            .permission("allow-import-rmbg-folder")
            .permission("allow-open-models-directory"),
    )?;

    let remote_url = Url::parse(&format!("{api_base}/")).map_err(tauri::Error::InvalidUrl)?;
    let bootstrap = build_initialization_script(session);
    let splash = app.get_webview_window("splash");
    let navigation_origin = api_base.clone();
    let page_origin = api_base.clone();

    WebviewWindowBuilder::new(app, "main", WebviewUrl::External(remote_url))
        .title("FigureSmith")
        .inner_size(1280.0, 860.0)
        .resizable(true)
        .visible(false)
        .initialization_script(bootstrap)
        .on_navigation(move |url| is_exact_sidecar_origin(url, &navigation_origin))
        .on_new_window(|_url, _features| NewWindowResponse::Deny)
        .on_page_load(move |window, payload| {
            if payload.event() == PageLoadEvent::Finished
                && is_exact_sidecar_origin(payload.url(), &page_origin)
            {
                let _ = window.show();
                if let Some(splash) = splash.as_ref() {
                    let _ = splash.close();
                }
            }
        })
        .build()?;

    Ok(())
}

fn build_menu(app: &tauri::AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    let import_sam3 = MenuItem::with_id(
        app,
        "import_sam3",
        "Import SAM3 Checkpoint…",
        true,
        None::<&str>,
    )?;
    let import_rmbg_zip = MenuItem::with_id(
        app,
        "import_rmbg_zip",
        "Import RMBG ZIP…",
        true,
        None::<&str>,
    )?;
    let import_rmbg_folder = MenuItem::with_id(
        app,
        "import_rmbg_folder",
        "Import RMBG Folder…",
        true,
        None::<&str>,
    )?;
    let open_models = MenuItem::with_id(
        app,
        "open_models_dir",
        "Open Models Directory",
        true,
        None::<&str>,
    )?;
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

#[cfg(test)]
mod tests {
    use super::{is_exact_sidecar_origin, Url};

    #[test]
    fn navigation_policy_requires_exact_loopback_origin_and_port() {
        let expected = "http://127.0.0.1:45678";
        assert!(is_exact_sidecar_origin(
            &Url::parse("http://127.0.0.1:45678/").unwrap(),
            expected
        ));
        assert!(!is_exact_sidecar_origin(
            &Url::parse("http://127.0.0.1:45679/").unwrap(),
            expected
        ));
        assert!(!is_exact_sidecar_origin(
            &Url::parse("http://localhost:45678/").unwrap(),
            expected
        ));
        assert!(!is_exact_sidecar_origin(
            &Url::parse("https://127.0.0.1:45678/").unwrap(),
            expected
        ));
    }
}
