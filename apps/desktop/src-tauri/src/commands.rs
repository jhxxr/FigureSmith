//! Tauri commands: session bridge + model import via native dialogs + HTTP.

use crate::sidecar::SidecarState;
use serde_json::Value;
use std::path::PathBuf;
use std::time::Duration;
use tauri::{AppHandle, State};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

fn api_request(method: &str, url: &str, token: &str, body: Option<Value>) -> Result<Value, String> {
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

async fn pick_file(
    app: &AppHandle,
    filters: Vec<(&str, &[&str])>,
) -> Result<Option<PathBuf>, String> {
    let mut builder = app.dialog().file();
    for (name, exts) in filters {
        builder = builder.add_filter(name, exts);
    }
    let picked = builder.blocking_pick_file();
    picked
        .map(|p| p.into_path())
        .transpose()
        .map_err(|e| e.to_string())
}

async fn pick_folder(app: &AppHandle) -> Result<Option<PathBuf>, String> {
    let picked = app.dialog().file().blocking_pick_folder();
    picked
        .map(|p| p.into_path())
        .transpose()
        .map_err(|e| e.to_string())
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
            std::env::var_os("LOCALAPPDATA")
                .map(|p| PathBuf::from(p).join("FigureSmith").join("models"))
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

/// Build the document-start request bridge for the authenticated sidecar page.
///
/// The token and short-lived SSE ticket are captured by wrapper closures and
/// are never placed on a window-owned session object or in storage. Only
/// exact-origin EventSource requests receive the scoped query credential; the
/// `/api` checks run before any vendor script can issue a fetch.
pub fn build_initialization_script(session: &crate::sidecar::SessionInfo) -> String {
    // JSON serialization prevents token/api values from becoming JavaScript.
    // The session token is generated as hex today, but this remains defensive.
    let token_js = serde_json::to_string(&session.token).unwrap_or_else(|_| "\"\"".into());
    let sse_ticket_js =
        serde_json::to_string(&session.sse_ticket).unwrap_or_else(|_| "\"\"".into());
    let api_base_js = serde_json::to_string(&session.api_base).unwrap_or_else(|_| "\"\"".into());
    format!(
        r#"(function(){{
  "use strict";
  var apiBase = {api_base_js};
  var token = {token_js};
  var sseTicket = {sse_ticket_js};
  var allowedOrigin = null;

  function normalize(value) {{
    try {{
      if (value instanceof Request) return new URL(value.url, window.location.href);
      if (value instanceof URL) return new URL(value.href, window.location.href);
      return new URL(String(value), window.location.href);
    }} catch (_e) {{
      return null;
    }}
  }}

  function bootstrapError() {{
    var error = new Error("AUTH_BOOTSTRAP_FAILED");
    error.code = "AUTH_BOOTSTRAP_FAILED";
    return error;
  }}

  function installFailedBridge() {{
    try {{
      Object.defineProperty(window, "__FIGURESMITH_AUTH_BOOTSTRAP_FAILED__", {{
        value: true,
        configurable: false,
        enumerable: false,
        writable: false
      }});
    }} catch (_e) {{
      window.__FIGURESMITH_AUTH_BOOTSTRAP_FAILED__ = true;
    }}

    var originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {{
      var url = normalize(input);
      var path = url && url.pathname ? url.pathname : "";
      if (path === "/api" || path.indexOf("/api/") === 0) {{
        return Promise.reject(bootstrapError());
      }}
      return originalFetch(input, init);
    }};

    var OriginalEventSource = window.EventSource;
    if (typeof OriginalEventSource === "function") {{
      window.EventSource = function(input, config) {{
        var url = normalize(input);
        var path = url && url.pathname ? url.pathname : "";
        if (path === "/api/events" || path.indexOf("/api/events/") === 0) {{
          throw bootstrapError();
        }}
        return new OriginalEventSource(input, config);
      }};
      window.EventSource.prototype = OriginalEventSource.prototype;
    }}
  }}

  try {{
    var configured = new URL(apiBase);
    if (configured.protocol !== "http:" ||
        configured.hostname !== "127.0.0.1" ||
        !configured.port ||
        configured.username || configured.password ||
        (configured.pathname !== "" && configured.pathname !== "/") ||
        window.top !== window ||
        window.location.origin !== configured.origin) {{
      installFailedBridge();
      return;
    }}
    allowedOrigin = configured.origin;
  }} catch (_e) {{
    installFailedBridge();
    return;
  }}

  function isApiUrl(value) {{
    var url = normalize(value);
    if (!url || url.origin !== allowedOrigin) return false;
    var path = url.pathname || "";
    return path === "/api" || path.indexOf("/api/") === 0;
  }}

  function authHeaders(input, init) {{
    var source = init && init.headers;
    if (!source && input instanceof Request) source = input.headers;
    var headers = new Headers(source || undefined);
    if (!headers.has("Authorization") && !headers.has("authorization")) {{
      headers.set("Authorization", "Bearer " + token);
    }}
    return headers;
  }}

  if (!window.__FIGURESMITH_BRIDGE_INSTALLED__) {{
    var originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {{
      if (!isApiUrl(input)) return originalFetch(input, init);
      var headers = authHeaders(input, init);
      var nextInit = Object.assign({{}}, init || {{}}, {{ headers: headers }});
      if (input instanceof Request) return originalFetch(new Request(input, nextInit));
      return originalFetch(input, nextInit);
    }};

    var OriginalEventSource = window.EventSource;
    if (typeof OriginalEventSource === "function") {{
      function BridgedEventSource(input, config) {{
        var url = normalize(input);
        if (url && url.origin === allowedOrigin &&
            (url.pathname === "/api/events" || url.pathname.indexOf("/api/events/") === 0) &&
            !url.searchParams.has("fs_ticket")) {{
          url.searchParams.set("fs_ticket", sseTicket);
          return new OriginalEventSource(url.toString(), config);
        }}
        return new OriginalEventSource(input, config);
      }}
      BridgedEventSource.prototype = OriginalEventSource.prototype;
      BridgedEventSource.CONNECTING = OriginalEventSource.CONNECTING;
      BridgedEventSource.OPEN = OriginalEventSource.OPEN;
      BridgedEventSource.CLOSED = OriginalEventSource.CLOSED;
      window.EventSource = BridgedEventSource;
    }}

    Object.defineProperty(window, "__FIGURESMITH_BRIDGE_INSTALLED__", {{
      value: true,
      configurable: false,
      enumerable: false,
      writable: false
    }});
    Object.defineProperty(window, "__FIGURESMITH_DESKTOP_READY__", {{
      value: true,
      configurable: false,
      enumerable: false,
      writable: false
    }});
  }}
}})();"#,
    )
}

#[cfg(test)]
mod tests {
    use super::build_initialization_script;
    use crate::sidecar::SessionInfo;

    #[test]
    fn bootstrap_is_document_start_and_does_not_publish_session_object() {
        let script = build_initialization_script(&SessionInfo {
            port: 45678,
            api_base: "http://127.0.0.1:45678".into(),
            token: "token-for-test-only".into(),
            sse_ticket: "ticket-for-test-only".into(),
        });
        assert!(script.contains("window.top !== window"));
        assert!(script.contains("window.location.origin"));
        assert!(script.contains("Authorization"));
        assert!(script.contains("AUTH_BOOTSTRAP_FAILED"));
        assert!(script.contains("Promise.reject(bootstrapError())"));
        assert!(script.contains("token-for-test-only"));
        assert!(script.contains("fs_ticket"));
        assert!(!script.contains("fs_token"));
        assert!(!script.contains("window.__FIGURESMITH__ ="));
        assert!(script.contains("__FIGURESMITH_DESKTOP_READY__"));
    }
}
