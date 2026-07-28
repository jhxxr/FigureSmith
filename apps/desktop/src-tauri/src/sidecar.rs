//! Python sidecar process lifecycle for FigureSmith desktop.
//!
//! - Bind host is always `127.0.0.1` (never `0.0.0.0`)
//! - Session token is generated in-memory and passed only via child env
//! - Token is never logged
//! - On exit: POST /api/shutdown, then force-kill process tree if needed

use rand::RngCore;
use serde::Serialize;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

/// Always loopback for desktop spawn — refuse any other host.
const BIND_HOST: &str = "127.0.0.1";

#[derive(Debug, Clone, Serialize)]
pub struct SessionInfo {
    pub port: u16,
    pub api_base: String,
    /// One-time process session token (memory only; never persist).
    pub token: String,
    pub ready: bool,
}

pub struct SidecarState {
    inner: Mutex<SidecarInner>,
}

struct SidecarInner {
    child: Option<Child>,
    port: u16,
    token: String,
    ready: bool,
}

impl SidecarState {
    pub fn start(repo_root: PathBuf) -> Result<Self, String> {
        let port = find_free_port()?;
        let token = generate_token();
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
            .env_remove("FIGURESMITH_DISABLE_AUTH");

        // Data dir: prefer explicit env; otherwise store next to the desktop
        // executable (install/portable location) so large models are not forced
        // onto %LOCALAPPDATA% on C:.
        if let Ok(data_dir) = std::env::var("FIGURESMITH_DATA_DIR") {
            if !data_dir.trim().is_empty() {
                cmd.env("FIGURESMITH_DATA_DIR", data_dir);
            }
        } else if let Ok(exe) = std::env::current_exe() {
            if let Some(parent) = exe.parent() {
                let data = parent.join("data");
                cmd.env("FIGURESMITH_DATA_DIR", data.as_os_str());
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

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn Python sidecar: {e}"))?;

        // Drain stdout/stderr so the child cannot block on full pipes.
        // Redact token if it ever appears (should not).
        if let Some(stdout) = child.stdout.take() {
            let token_for_redact = token.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines().flatten() {
                    eprintln!("[sidecar] {}", redact(&line, &token_for_redact));
                }
            });
        }
        if let Some(stderr) = child.stderr.take() {
            let token_for_redact = token.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().flatten() {
                    eprintln!("[sidecar:err] {}", redact(&line, &token_for_redact));
                }
            });
        }

        let base = format!("http://{BIND_HOST}:{port}");
        wait_for_healthz(&base, Duration::from_secs(90))?;

        eprintln!("[FigureSmith] sidecar healthy at {base}/healthz");

        Ok(Self {
            inner: Mutex::new(SidecarInner {
                child: Some(child),
                port,
                token,
                ready: true,
            }),
        })
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
            ready: g.ready,
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

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0xf) as usize] as char);
    }
    out
}

fn redact(line: &str, token: &str) -> String {
    if token.is_empty() || !line.contains(token) {
        return line.to_string();
    }
    line.replace(token, "[REDACTED_SESSION_TOKEN]")
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
        repo_root
            .join(".venv")
            .join("Scripts")
            .join("python.exe"),
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

fn wait_for_healthz(base: &str, timeout: Duration) -> Result<(), String> {
    // /healthz is public by design (Phase 4).
    let url = format!("{base}/healthz");
    let start = Instant::now();
    let mut last_err = String::from("not attempted");
    while start.elapsed() < timeout {
        match ureq::get(&url).timeout(Duration::from_secs(2)).call() {
            Ok(resp) if resp.status() >= 200 && resp.status() < 300 => return Ok(()),
            Ok(resp) => {
                last_err = format!("healthz status {}", resp.status());
            }
            Err(e) => {
                last_err = e.to_string();
            }
        }
        thread::sleep(Duration::from_millis(250));
    }
    Err(format!(
        "sidecar health check timed out after {:?}: {last_err}",
        timeout
    ))
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
        assert_eq!(redact("tok=abc123secret end", t), "tok=[REDACTED_SESSION_TOKEN] end");
        assert_eq!(redact("clean line", t), "clean line");
    }

    #[test]
    fn hex_token_length() {
        let t = generate_token();
        assert_eq!(t.len(), 64);
        assert!(t.chars().all(|c| c.is_ascii_hexdigit()));
    }
}
