//! FigureSmith desktop library entry (Tauri 2).

mod commands;
mod sidecar;

use commands::{
    build_initialization_script, import_rmbg_archive, import_rmbg_folder, import_sam3_model,
    open_models_directory,
};
use sidecar::{resolve_runtime_root, SidecarState};
use tauri::{
    ipc::CapabilityBuilder,
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    webview::{NewWindowResponse, PageLoadEvent, WebviewWindowBuilder},
    Emitter, Manager, RunEvent, Url, WebviewUrl, WindowEvent,
};

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

            // Start Python sidecar before the remote UI becomes useful.
            let resource_dir = handle.path().resource_dir().ok();
            let repo = match resolve_runtime_root(resource_dir) {
                Ok(repo) => repo,
                Err(err) => {
                    report_startup_error(app.handle(), &err);
                    return Ok(());
                }
            };
            eprintln!("[FigureSmith] repo root: {}", repo.display());
            let sidecar = match SidecarState::start(repo) {
                Ok(sidecar) => sidecar,
                Err(err) => {
                    eprintln!("[FigureSmith] sidecar start failed: {err}");
                    report_startup_error(app.handle(), &err);
                    return Ok(());
                }
            };
            let session = sidecar.session()?;
            let app_for_monitor = handle.clone();
            sidecar.start_liveness_monitor(move || {
                eprintln!("[FigureSmith] closing remote UI after sidecar loss");
                if let Some(main) = app_for_monitor.get_webview_window("main") {
                    let _ = main.close();
                }
                app_for_monitor.exit(1);
            });
            app.manage(sidecar);

            // Grant only the four native actions to the exact sidecar origin,
            // then create the authenticated remote window with its bridge at
            // document start. The bundled splash remains local-only.
            if let Err(err) = create_remote_main(&handle, &session) {
                if let Some(state) = app.try_state::<SidecarState>() {
                    state.shutdown();
                }
                report_startup_error(app.handle(), &err.to_string());
            }

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

fn report_startup_error(app: &tauri::AppHandle, message: &str) {
    // Startup errors are intentionally bounded and contain no environment or
    // session-token values. The local splash owns the user-visible rendering.
    let bounded = message.chars().take(500).collect::<String>();
    eprintln!("[FigureSmith] startup failed: {bounded}");
    let _ = app.emit("sidecar-error", bounded);
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
