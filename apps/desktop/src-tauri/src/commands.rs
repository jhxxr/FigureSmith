//! Tauri commands: session bridge + model import via native dialogs + HTTP.

use crate::sidecar::SidecarState;
use serde_json::Value;
use std::path::PathBuf;
use std::time::Duration;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

fn api_request(
    method: &str,
    url: &str,
    token: &str,
    body: Option<Value>,
) -> Result<Value, String> {
    let mut req = match method {
        "GET" => ureq::get(url),
        "POST" => ureq::post(url),
        "DELETE" => ureq::delete(url),
        other => return Err(format!("unsupported HTTP method: {other}")),
    };
    req = req
        .set("Authorization", &format!("Bearer {token}"))
        .set("Accept", "application/json")
        .timeout(Duration::from_secs(120));

    let resp = if let Some(b) = body {
        req.set("Content-Type", "application/json")
            .send_json(b)
            .map_err(|e| format!("request failed: {e}"))?
    } else {
        req.call().map_err(|e| format!("request failed: {e}"))?
    };

    let status = resp.status();
    let text = resp
        .into_string()
        .map_err(|e| format!("read body failed: {e}"))?;
    if !(200..300).contains(&status) {
        // Never include Authorization; body should not contain the token.
        return Err(format!("HTTP {status}: {text}"));
    }
    if text.trim().is_empty() {
        return Ok(Value::Null);
    }
    serde_json::from_str(&text).map_err(|e| format!("invalid JSON response: {e}; body={text}"))
}

async fn pick_file(app: &AppHandle, filters: Vec<(&str, &[&str])>) -> Result<Option<PathBuf>, String> {
    let mut builder = app.dialog().file();
    for (name, exts) in filters {
        builder = builder.add_filter(name, exts);
    }
    let picked = builder.blocking_pick_file();
    Ok(picked.map(|p| p.into_path()).transpose().map_err(|e| e.to_string())?)
}

async fn pick_folder(app: &AppHandle) -> Result<Option<PathBuf>, String> {
    let picked = app.dialog().file().blocking_pick_folder();
    Ok(picked.map(|p| p.into_path()).transpose().map_err(|e| e.to_string())?)
}

#[tauri::command]
pub fn get_session(state: State<'_, SidecarState>) -> Result<crate::sidecar::SessionInfo, String> {
    state.session()
}

#[tauri::command]
pub async fn import_sam3_model(
    app: AppHandle,
    state: State<'_, SidecarState>,
    path: Option<String>,
) -> Result<Value, String> {
    let source = match path {
        Some(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => {
            let picked = pick_file(
                &app,
                vec![("SAM3 checkpoint", &["pt", "pth"]), ("All files", &["*"])],
            )
            .await?;
            match picked {
                Some(p) => p,
                None => return Err("cancelled".into()),
            }
        }
    };

    let session = state.session()?;
    let url = format!("{}/api/models/sam3/import", session.api_base);
    let body = serde_json::json!({
        "source_path": source.to_string_lossy(),
    });
    api_request("POST", &url, &session.token, Some(body))
}

#[tauri::command]
pub async fn import_rmbg_archive(
    app: AppHandle,
    state: State<'_, SidecarState>,
    path: Option<String>,
) -> Result<Value, String> {
    let source = match path {
        Some(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => {
            let picked = pick_file(
                &app,
                vec![("RMBG archive", &["zip"]), ("All files", &["*"])],
            )
            .await?;
            match picked {
                Some(p) => p,
                None => return Err("cancelled".into()),
            }
        }
    };

    let session = state.session()?;
    let url = format!("{}/api/models/rmbg/import", session.api_base);
    let body = serde_json::json!({
        "source_path": source.to_string_lossy(),
        "kind": "zip",
    });
    api_request("POST", &url, &session.token, Some(body))
}

#[tauri::command]
pub async fn import_rmbg_folder(
    app: AppHandle,
    state: State<'_, SidecarState>,
    path: Option<String>,
) -> Result<Value, String> {
    let source = match path {
        Some(p) if !p.trim().is_empty() => PathBuf::from(p),
        _ => {
            let picked = pick_folder(&app).await?;
            match picked {
                Some(p) => p,
                None => return Err("cancelled".into()),
            }
        }
    };

    let session = state.session()?;
    let url = format!("{}/api/models/rmbg/import", session.api_base);
    let body = serde_json::json!({
        "source_path": source.to_string_lossy(),
        "kind": "dir",
    });
    api_request("POST", &url, &session.token, Some(body))
}

#[tauri::command]
pub async fn open_models_directory(
    app: AppHandle,
    state: State<'_, SidecarState>,
) -> Result<String, String> {
    let session = state.session()?;
    let url = format!("{}/api/models/paths", session.api_base);
    let paths = api_request("GET", &url, &session.token, None)?;

    // Prefer models root; fall back to parent of sam3 checkpoint path.
    let models_dir = paths
        .get("models_root")
        .or_else(|| paths.get("models_dir"))
        .and_then(|v| v.as_str())
        .map(PathBuf::from)
        .or_else(|| {
            paths
                .get("sam3_checkpoint")
                .and_then(|v| v.as_str())
                .map(PathBuf::from)
                .and_then(|p| p.parent().map(|x| x.to_path_buf()))
                .and_then(|p| p.parent().map(|x| x.to_path_buf()))
        })
        .or_else(|| {
            // Ultimate fallback: default Windows app data layout (display only).
            std::env::var_os("LOCALAPPDATA").map(|p| PathBuf::from(p).join("FigureSmith").join("models"))
        })
        .ok_or_else(|| "could not resolve models directory".to_string())?;

    if !models_dir.exists() {
        std::fs::create_dir_all(&models_dir)
            .map_err(|e| format!("failed to create models dir: {e}"))?;
    }

    app.opener()
        .open_path(models_dir.to_string_lossy().as_ref(), None::<&str>)
        .map_err(|e| format!("failed to open models directory: {e}"))?;

    Ok(models_dir.to_string_lossy().into_owned())
}

/// Inject session + load desktop bridge after WebView navigates to sidecar UI.
pub fn inject_session_bridge(webview: &tauri::Webview, session: &crate::sidecar::SessionInfo) {
    // Escape token for JS string (token is hex, but keep defensive).
    let token_js = serde_json::to_string(&session.token).unwrap_or_else(|_| "\"\"".into());
    let api_base_js = serde_json::to_string(&session.api_base).unwrap_or_else(|_| "\"\"".into());
    let script = format!(
        r#"(function(){{
  try {{
    window.__FIGURESMITH__ = {{
      token: {token_js},
      port: {port},
      apiBase: {api_base_js}
    }};
    if (!window.__FIGURESMITH_BRIDGE_INSTALLED__) {{
      var s = document.createElement('script');
      s.src = '/figuresmith-bridge.js';
      s.async = false;
      document.head.appendChild(s);
    }}
  }} catch (e) {{
    console.error('FigureSmith session inject failed', e);
  }}
}})();"#,
        port = session.port,
    );
    let _ = webview.eval(&script);
}
