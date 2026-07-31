//! Python sidecar process lifecycle for FigureSmith desktop.
//!
//! - Bind host is always `127.0.0.1` (never `0.0.0.0`)
//! - Session token is generated in-memory and passed only via child env
//! - Token is never logged
//! - On exit: POST /api/shutdown, then force-kill process tree if needed

use rand::RngCore;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

/// Always loopback for desktop spawn — refuse any other host.
const BIND_HOST: &str = "127.0.0.1";
const SSE_TICKET_TTL_SECS: u64 = 10 * 60;

#[derive(Debug, Clone)]
pub struct SessionInfo {
    pub port: u16,
    pub api_base: String,
    /// One-time process session token (memory only; never persist).
    pub token: String,
    /// Short-lived credential used only in the EventSource query string.
    pub sse_ticket: String,
}

pub struct SidecarState {
    inner: Arc<Mutex<SidecarInner>>,
}

struct SidecarInner {
    child: Option<Child>,
    port: u16,
    token: String,
    sse_ticket: String,
    ready: bool,
}

/// Owns a newly spawned child until startup has completed.
///
/// `std::process::Child` does not kill the OS process when it is dropped. The
/// guard closes that leak on every startup error path, including a readiness
/// timeout or an early Python import failure.
struct PendingChild {
    child: Option<Child>,
}

impl PendingChild {
    fn new(child: Child) -> Self {
        Self { child: Some(child) }
    }

    fn child_mut(&mut self) -> Result<&mut Child, String> {
        self.child
            .as_mut()
            .ok_or_else(|| "sidecar child ownership was lost during startup".to_string())
    }

    fn into_child(mut self) -> Result<Child, String> {
        self.child
            .take()
            .ok_or_else(|| "sidecar child ownership was lost during startup".to_string())
    }
}

impl Drop for PendingChild {
    fn drop(&mut self) {
        let Some(mut child) = self.child.take() else {
            return;
        };
        if let Ok(Some(_)) = child.try_wait() {
            return;
        }
        let pid = child.id();
        force_kill_tree(pid);
        let _ = child.kill();
        let _ = child.wait();
    }
}

impl SidecarState {
    pub fn start(repo_root: PathBuf) -> Result<Self, String> {
        let port = find_free_port()?;
        let token = generate_token();
        let sse_ticket = generate_token();
        let sse_ticket_expires_at = unix_now_secs().saturating_add(SSE_TICKET_TTL_SECS);
        let python = resolve_python(&repo_root)?;
        let main_py = repo_root.join("apps").join("backend").join("main.py");
        if !main_py.is_file() {
            return Err(format!(
                "backend entry not found: {} (set FIGURESMITH_REPO_ROOT?)",
                main_py.display()
            ));
        }

        let backend_dir = repo_root.join("apps").join("backend");
        let vendor_dir = repo_root.join("vendor").join("autofigure_edit");
        let pythonpath = format!(
            "{}{}{}",
            backend_dir.display(),
            path_sep(),
            vendor_dir.display()
        );

        // Build child env carefully — never log token.
        let mut cmd = Command::new(&python);
        let dev_mode = std::env::var("FIGURESMITH_DEV_MODE").ok();
        cmd.arg(main_py.as_os_str())
            .arg("--host")
            .arg(BIND_HOST)
            .arg("--port")
            .arg(port.to_string())
            .current_dir(&repo_root)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .env("FIGURESMITH_SESSION_TOKEN", &token)
            .env("FIGURESMITH_SSE_TICKET", &sse_ticket)
            .env(
                "FIGURESMITH_SSE_TICKET_EXPIRES_AT",
                sse_ticket_expires_at.to_string(),
            )
            .env("FIGURESMITH_STRICT_OFFLINE", "1")
            .env("FIGURESMITH_FORCE_LOCAL_SAM", "1")
            .env("FIGURESMITH_HOST", BIND_HOST)
            .env("FIGURESMITH_PORT", port.to_string())
            .env("HF_HUB_OFFLINE", "1")
            .env("TRANSFORMERS_OFFLINE", "1")
            .env("HF_DATASETS_OFFLINE", "1")
            .env("NO_PROXY", "127.0.0.1,localhost,::1")
            .env("no_proxy", "127.0.0.1,localhost,::1")
            .env("PYTHONPATH", &pythonpath)
            .env("PYTHONUNBUFFERED", "1")
            // Ensure tests/dev bypass does not leak into desktop child.
            .env_remove("FIGURESMITH_DISABLE_AUTH")
            // Do not inherit an accidental development mode from the shell;
            // the explicit value below is the only mode the child receives.
            .env_remove("FIGURESMITH_DEV_MODE");

        if let Some(value) = dev_mode.as_deref() {
            cmd.env("FIGURESMITH_DEV_MODE", value);
        }

        // Data dir: prefer explicit env; otherwise store next to the desktop
        // executable (install/portable location) so large models are not forced
        // onto %LOCALAPPDATA% on C:.
        if let Ok(data_dir) = std::env::var("FIGURESMITH_DATA_DIR") {
            if !data_dir.trim().is_empty() {
                cmd.env("FIGURESMITH_DATA_DIR", data_dir);
            }
        } else if let Ok(exe) = std::env::current_exe() {
            if let Some(parent) = exe.parent() {
                if let Some(root) = parent.to_str() {
                    cmd.env("FIGURESMITH_INSTALL_ROOT", root);
                }
            }
        }

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
            cmd.creation_flags(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP);
        }

        eprintln!(
            "[FigureSmith] starting sidecar: python={} host={} port={} token_len={} strict_offline=1",
            python.display(),
            BIND_HOST,
            port,
            token.len()
        );

        let child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn Python sidecar: {e}"))?;
        let mut pending = PendingChild::new(child);

        // Drain stdout/stderr so the child cannot block on full pipes.
        // Redact token if it ever appears (should not).
        if let Some(stdout) = pending.child_mut()?.stdout.take() {
            let token_for_redact = token.clone();
            let ticket_for_redact = sse_ticket.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!(
                        "[sidecar] {}",
                        redact_many(&line, &[&token_for_redact, &ticket_for_redact])
                    );
                }
            });
        }
        if let Some(stderr) = pending.child_mut()?.stderr.take() {
            let token_for_redact = token.clone();
            let ticket_for_redact = sse_ticket.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    eprintln!(
                        "[sidecar:err] {}",
                        redact_many(&line, &[&token_for_redact, &ticket_for_redact])
                    );
                }
            });
        }

        let base = format!("http://{BIND_HOST}:{port}");
        wait_for_ready(pending.child_mut()?, &base, &token, Duration::from_secs(90))?;
        let child = pending.into_child()?;

        eprintln!("[FigureSmith] sidecar ready at {base}/api/desktop/ready");

        let inner = Arc::new(Mutex::new(SidecarInner {
            child: Some(child),
            port,
            token,
            sse_ticket,
            ready: true,
        }));

        Ok(Self { inner })
    }

    /// Begin monitoring after the state has been associated with the Tauri app.
    /// The callback is invoked only for an unexpected post-ready child loss.
    pub fn start_liveness_monitor<F>(&self, on_unexpected_exit: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        spawn_liveness_monitor(Arc::clone(&self.inner), Arc::new(on_unexpected_exit));
    }

    pub fn session(&self) -> Result<SessionInfo, String> {
        let g = self
            .inner
            .lock()
            .map_err(|_| "sidecar state lock poisoned".to_string())?;
        Ok(SessionInfo {
            port: g.port,
            api_base: format!("http://{BIND_HOST}:{}", g.port),
            token: g.token.clone(),
            sse_ticket: g.sse_ticket.clone(),
        })
    }

    /// Best-effort graceful shutdown then process-tree kill.
    pub fn shutdown(&self) {
        let (port, token, mut child_opt) = {
            let mut g = match self.inner.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            g.ready = false;
            let port = g.port;
            let token = g.token.clone();
            let child = g.child.take();
            (port, token, child)
        };

        if port > 0 {
            let url = format!("http://{BIND_HOST}:{port}/api/shutdown");
            // Ignore errors — process may already be dead.
            let _ = ureq::post(&url)
                .set("Authorization", &format!("Bearer {token}"))
                .set("Content-Type", "application/json")
                .timeout(Duration::from_secs(2))
                .send_string("{}");
        }

        if let Some(mut child) = child_opt.take() {
            let deadline = Instant::now() + Duration::from_secs(3);
            loop {
                match child.try_wait() {
                    Ok(Some(_)) => {
                        eprintln!("[FigureSmith] sidecar exited after shutdown");
                        return;
                    }
                    Ok(None) if Instant::now() < deadline => {
                        thread::sleep(Duration::from_millis(100));
                    }
                    _ => break,
                }
            }

            let pid = child.id();
            eprintln!("[FigureSmith] force-stopping sidecar pid={pid}");
            force_kill_tree(pid);
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        self.shutdown();
    }
}

fn path_sep() -> &'static str {
    if cfg!(windows) {
        ";"
    } else {
        ":"
    }
}

fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    hex_encode(&bytes)
}

fn unix_now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0xf) as usize] as char);
    }
    out
}

fn redact_many(line: &str, secrets: &[&str]) -> String {
    let mut redacted = line.to_string();
    for (index, secret) in secrets.iter().enumerate() {
        if secret.is_empty() || !redacted.contains(secret) {
            continue;
        }
        let replacement = if index == 0 {
            "[REDACTED_SESSION_TOKEN]"
        } else {
            "[REDACTED_SSE_TICKET]"
        };
        redacted = redacted.replace(secret, replacement);
    }
    redacted
}

pub fn find_free_port() -> Result<u16, String> {
    let listener = TcpListener::bind((BIND_HOST, 0))
        .map_err(|e| format!("failed to allocate free port on {BIND_HOST}: {e}"))?;
    let port = listener
        .local_addr()
        .map_err(|e| format!("failed to read bound port: {e}"))?
        .port();
    // Listener drops here, freeing the port for the Python process.
    // Small race exists; acceptable for desktop MVP.
    Ok(port)
}

fn resolve_python(repo_root: &Path) -> Result<PathBuf, String> {
    if let Ok(p) = std::env::var("FIGURESMITH_PYTHON") {
        let path = PathBuf::from(p.trim());
        if path.as_os_str().is_empty() {
            // fall through
        } else if path.is_file() {
            return Ok(path);
        } else {
            // Still try — may be a command name resolved later.
            return Ok(path);
        }
    }

    let candidates = [
        repo_root
            .join("apps")
            .join("backend")
            .join(".venv")
            .join("Scripts")
            .join("python.exe"),
        repo_root
            .join("apps")
            .join("backend")
            .join(".venv")
            .join("bin")
            .join("python"),
        repo_root.join(".venv").join("Scripts").join("python.exe"),
        repo_root.join(".venv").join("bin").join("python"),
    ];
    for c in candidates {
        if c.is_file() {
            return Ok(c);
        }
    }

    // PATH fallback
    Ok(PathBuf::from(if cfg!(windows) {
        "python"
    } else {
        "python3"
    }))
}

fn wait_for_ready(
    child: &mut Child,
    base: &str,
    token: &str,
    timeout: Duration,
) -> Result<(), String> {
    // The authenticated application probe proves the outer composition is
    // mounted and the session-token middleware is usable before WebView load.
    let url = format!("{base}/api/desktop/ready");
    let start = Instant::now();
    let mut last_err = String::from("not attempted");
    while start.elapsed() < timeout {
        match child.try_wait() {
            Ok(Some(status)) => {
                return Err(format!("sidecar exited before ready probe: {status}"));
            }
            Err(e) => {
                return Err(format!("failed to inspect sidecar during startup: {e}"));
            }
            Ok(None) => {}
        }

        match ureq::get(&url)
            .set("Authorization", &format!("Bearer {token}"))
            .timeout(Duration::from_secs(2))
            .call()
        {
            Ok(resp) if resp.status() >= 200 && resp.status() < 300 => return Ok(()),
            Ok(resp) if matches!(resp.status(), 401 | 403) => {
                return Err(format!(
                    "sidecar ready probe rejected authentication: HTTP {}",
                    resp.status()
                ));
            }
            Ok(resp) => {
                last_err = format!("ready status {}", resp.status());
            }
            Err(e) => {
                last_err = e.to_string();
            }
        }
        thread::sleep(Duration::from_millis(250));
    }
    Err(format!(
        "sidecar ready check timed out after {:?}: {last_err}",
        timeout
    ))
}

fn spawn_liveness_monitor(
    inner: Arc<Mutex<SidecarInner>>,
    on_unexpected_exit: Arc<dyn Fn() + Send + Sync>,
) {
    thread::spawn(move || loop {
        let mut orphaned_child = None;
        let unexpected_exit = {
            let mut g = match inner.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            let Some(child) = g.child.as_mut() else {
                return;
            };
            match child.try_wait() {
                Ok(Some(status)) => {
                    g.ready = false;
                    let _ = g.child.take();
                    eprintln!("[FigureSmith] sidecar exited unexpectedly: {status}");
                    true
                }
                Ok(None) => false,
                Err(err) => {
                    g.ready = false;
                    // `try_wait` can fail without reaping the child. Retain
                    // ownership long enough to terminate and reap it instead
                    // of dropping `Child` and leaking the backend process.
                    orphaned_child = g.child.take();
                    eprintln!("[FigureSmith] sidecar liveness probe failed: {err}");
                    true
                }
            }
        };
        if let Some(mut child) = orphaned_child {
            let pid = child.id();
            force_kill_tree(pid);
            let _ = child.kill();
            let _ = child.wait();
        }
        if unexpected_exit {
            on_unexpected_exit();
            return;
        }
        thread::sleep(Duration::from_millis(500));
    });
}

fn force_kill_tree(pid: u32) {
    #[cfg(windows)]
    {
        let _ = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    #[cfg(not(windows))]
    {
        let _ = Command::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status();
        thread::sleep(Duration::from_millis(200));
        let _ = Command::new("kill")
            .args(["-KILL", &pid.to_string()])
            .status();
    }
}

/// Resolve monorepo root from env, cargo manifest, or cwd.
pub fn resolve_repo_root() -> Result<PathBuf, String> {
    if let Ok(p) = std::env::var("FIGURESMITH_REPO_ROOT") {
        let path = PathBuf::from(p);
        if path.join("apps").join("backend").join("main.py").is_file() {
            return path
                .canonicalize()
                .map_err(|e| format!("FIGURESMITH_REPO_ROOT canonicalize failed: {e}"));
        }
        return Err(format!(
            "FIGURESMITH_REPO_ROOT does not look like FigureSmith root: {}",
            path.display()
        ));
    }

    // apps/desktop/src-tauri → repo root is ../../..
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let candidate = manifest.join("../../..");
    if let Ok(canon) = candidate.canonicalize() {
        if canon.join("apps").join("backend").join("main.py").is_file() {
            return Ok(canon);
        }
    }

    // Walk up from current directory.
    if let Ok(mut dir) = std::env::current_dir() {
        for _ in 0..8 {
            if dir.join("apps").join("backend").join("main.py").is_file() {
                return Ok(dir);
            }
            if !dir.pop() {
                break;
            }
        }
    }

    Err(
        "Could not locate FigureSmith repo root (apps/backend/main.py). \
         Set FIGURESMITH_REPO_ROOT."
            .into(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn free_port_is_nonzero() {
        let p = find_free_port().expect("port");
        assert!(p > 0);
    }

    #[test]
    fn redact_hides_token() {
        let t = "abc123secret";
        assert_eq!(
            redact_many("tok=abc123secret end", &[t]),
            "tok=[REDACTED_SESSION_TOKEN] end"
        );
        assert_eq!(redact_many("clean line", &[t]), "clean line");
    }

    #[test]
    fn hex_token_length() {
        let t = generate_token();
        assert_eq!(t.len(), 64);
        assert!(t.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn liveness_monitor_notifies_after_child_loss() {
        let mut command = if cfg!(windows) {
            let mut command = Command::new("cmd");
            command.args(["/C", "exit", "7"]);
            command
        } else {
            let mut command = Command::new("sh");
            command.args(["-c", "exit 7"]);
            command
        };
        let child = command.spawn().expect("spawn short-lived child");
        let inner = Arc::new(Mutex::new(SidecarInner {
            child: Some(child),
            port: 1,
            token: "test-token".into(),
            sse_ticket: "test-ticket".into(),
            ready: true,
        }));
        let (tx, rx) = std::sync::mpsc::channel();
        spawn_liveness_monitor(
            Arc::clone(&inner),
            Arc::new(move || {
                let _ = tx.send(());
            }),
        );

        assert!(rx.recv_timeout(Duration::from_secs(2)).is_ok());
        assert!(!inner.lock().expect("sidecar lock").ready);
    }
}
