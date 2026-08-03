//! Python sidecar process lifecycle for FigureSmith desktop.
//!
//! - Bind host is always `127.0.0.1` (never `0.0.0.0`)
//! - Session token is generated in-memory and passed only via child env
//! - Token is never logged
//! - On exit: POST /api/shutdown, then force-kill process tree if needed

use rand::RngCore;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::io::{BufRead, BufReader, Read};
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

#[derive(Debug, Clone)]
struct RuntimeLayout {
    root: PathBuf,
    backend_dir: PathBuf,
    vendor_dir: PathBuf,
    main_py: PathBuf,
    python: PathBuf,
    release: bool,
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
    pub fn start(runtime_root: PathBuf) -> Result<Self, String> {
        let port = find_free_port()?;
        let token = generate_token();
        let sse_ticket = generate_token();
        let sse_ticket_expires_at = unix_now_secs().saturating_add(SSE_TICKET_TTL_SECS);
        let layout = resolve_runtime_layout(&runtime_root)?;
        let python = layout.python.clone();
        let main_py = layout.main_py.clone();
        let backend_dir = layout.backend_dir.clone();
        let vendor_dir = layout.vendor_dir.clone();
        let vendor_parent = vendor_dir
            .parent()
            .ok_or_else(|| "vendor runtime path has no parent".to_string())?;
        let pythonpath = format!(
            "{}{}{}{}{}",
            backend_dir.display(),
            path_sep(),
            vendor_parent.display(),
            path_sep(),
            vendor_dir.display()
        );

        // Build child env carefully — never log token. Release mode uses only
        // the verified embedded interpreter; development mode may use an
        // explicitly resolved external Python. In both modes, discard inherited
        // source-path hooks so packaged application code wins deterministically.
        let mut cmd = Command::new(&python);
        scrub_python_path(&mut cmd);
        let dev_mode = std::env::var("FIGURESMITH_DEV_MODE").ok();
        cmd.arg("-B")
            .arg(main_py.as_os_str())
            .arg("--host")
            .arg(BIND_HOST)
            .arg("--port")
            .arg(port.to_string())
            .current_dir(&layout.root)
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
            .env("FIGURESMITH_RUNTIME_ROOT", &layout.root)
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("PYTHONUNBUFFERED", "1")
            // Ensure tests/dev bypass does not leak into desktop child.
            .env_remove("FIGURESMITH_DISABLE_AUTH")
            // Do not inherit an accidental development mode from the shell;
            // the explicit value below is the only mode the child receives.
            .env_remove("FIGURESMITH_DEV_MODE");

        if layout.release {
            cmd.env("FIGURESMITH_DEV_MODE", "0");
            cmd.env("FIGURESMITH_RELEASE_MODE", "1");
            if let Some(python_dir) = python.parent() {
                let inherited = std::env::var_os("PATH").unwrap_or_default();
                let mut paths = vec![python_dir.to_path_buf()];
                paths.extend(std::env::split_paths(&inherited));
                let joined = std::env::join_paths(paths)
                    .map_err(|err| format!("cannot construct embedded runtime DLL path: {err}"))?;
                cmd.env("PATH", joined);
            }
        } else if let Some(value) = dev_mode.as_deref() {
            cmd.env("FIGURESMITH_DEV_MODE", value);
        }

        // Data dir: prefer explicit env; otherwise store next to the desktop
        // executable (installed location) so large models are not forced
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
            "[FigureSmith] starting sidecar: mode={} python={} host={} port={} token_len={} strict_offline=1",
            if layout.release { "release" } else { "development" },
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

fn scrub_python_path(command: &mut Command) {
    // PYTHONPATH/PYTHONSTARTUP can make a different checkout win over the
    // application pack. Packages themselves remain resolved from the selected
    // user environment.
    command.env_remove("PYTHONPATH");
    command.env_remove("PYTHONHOME");
    command.env_remove("PYTHONSTARTUP");
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

const DEFAULT_BOOTSTRAP_IMPORTS: &[(&str, &str)] = &[
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pydantic", "pydantic"),
    ("python-multipart", "multipart"),
];

#[derive(Debug, Clone)]
struct PythonCandidate {
    program: PathBuf,
    prefix_args: Vec<String>,
    label: String,
}

fn push_python_candidate(
    candidates: &mut Vec<PythonCandidate>,
    program: PathBuf,
    prefix_args: Vec<String>,
    label: impl Into<String>,
) {
    let key = format!("{} {:?}", program.display(), prefix_args);
    if candidates.iter().any(|candidate| {
        format!(
            "{} {:?}",
            candidate.program.display(),
            candidate.prefix_args
        ) == key
    }) {
        return;
    }
    candidates.push(PythonCandidate {
        program,
        prefix_args,
        label: label.into(),
    });
}

fn push_python_path(
    candidates: &mut Vec<PythonCandidate>,
    path: PathBuf,
    label: impl Into<String>,
) {
    if path.is_file() {
        push_python_candidate(candidates, path, Vec::new(), label);
    }
}

fn append_python_launcher_paths(candidates: &mut Vec<PythonCandidate>) {
    if !cfg!(windows) {
        return;
    }
    let Ok(output) = Command::new("py").args(["-0p"]).output() else {
        return;
    };
    if !output.status.success() {
        return;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    for line in text.lines() {
        let lower = line.to_ascii_lowercase();
        let Some(end) = ["python.exe", "pythonw.exe"]
            .iter()
            .filter_map(|suffix| lower.rfind(suffix).map(|index| index + suffix.len()))
            .max()
        else {
            continue;
        };
        let Some(start) = lower
            .find("\\\\")
            .or_else(|| lower.find(":\\").map(|index| index.saturating_sub(1)))
        else {
            continue;
        };
        let raw = line[start..end].trim().trim_matches('"');
        push_python_path(
            candidates,
            PathBuf::from(raw),
            format!("Python launcher ({raw})"),
        );
    }
}

fn append_where_python_paths(candidates: &mut Vec<PythonCandidate>) {
    if !cfg!(windows) {
        return;
    }
    for command in ["python", "python3", "python3.12"] {
        let Ok(output) = Command::new("where.exe").arg(command).output() else {
            continue;
        };
        if !output.status.success() {
            continue;
        }
        for line in String::from_utf8_lossy(&output.stdout).lines() {
            let raw = line.trim().trim_matches('"');
            let lower = raw.to_ascii_lowercase();
            if lower.ends_with("python.exe") || lower.ends_with("pythonw.exe") {
                push_python_path(
                    candidates,
                    PathBuf::from(raw),
                    format!("where.exe {command} ({raw})"),
                );
            }
        }
    }
}

fn append_known_environment_paths(candidates: &mut Vec<PythonCandidate>) {
    let mut roots = Vec::new();
    for name in ["CONDA_PREFIX", "VIRTUAL_ENV"] {
        if let Some(value) = std::env::var_os(name) {
            roots.push(PathBuf::from(value));
        }
    }
    for index in 1..=32 {
        let name = format!("CONDA_PREFIX_{index}");
        if let Some(value) = std::env::var_os(name) {
            roots.push(PathBuf::from(value));
        }
    }
    if let Some(home) = std::env::var_os("USERPROFILE").or_else(|| std::env::var_os("HOME")) {
        let home = PathBuf::from(home);
        roots.extend([
            home.join(".conda").join("envs"),
            home.join(".virtualenvs"),
            home.join("anaconda3"),
            home.join("miniconda3"),
            home.join("anaconda3").join("envs"),
            home.join("miniconda3").join("envs"),
        ]);
        if cfg!(windows) {
            roots.push(
                home.join("AppData")
                    .join("Local")
                    .join("Programs")
                    .join("Python"),
            );
        }
    }
    if let Some(local_app_data) = std::env::var_os("LOCALAPPDATA") {
        roots.push(
            PathBuf::from(local_app_data)
                .join("Programs")
                .join("Python"),
        );
    }

    for root in roots {
        push_python_path(
            candidates,
            root.join("python.exe"),
            format!("environment ({})", root.display()),
        );
        push_python_path(
            candidates,
            root.join("Scripts").join("python.exe"),
            format!("environment ({})", root.display()),
        );
        let Ok(entries) = fs::read_dir(&root) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            push_python_path(
                candidates,
                path.join("python.exe"),
                format!("environment ({})", path.display()),
            );
            push_python_path(
                candidates,
                path.join("Scripts").join("python.exe"),
                format!("environment ({})", path.display()),
            );
        }
    }
}

fn external_python_candidates(runtime_root: &Path) -> Vec<PythonCandidate> {
    let mut candidates = Vec::new();
    if let Ok(raw) = std::env::var("FIGURESMITH_PYTHON") {
        let value = raw.trim();
        if !value.is_empty() {
            push_python_candidate(
                &mut candidates,
                PathBuf::from(value),
                Vec::new(),
                "FIGURESMITH_PYTHON",
            );
            return candidates;
        }
    }

    for path in [
        runtime_root
            .join(".venv")
            .join("Scripts")
            .join("python.exe"),
        runtime_root.join(".venv").join("bin").join("python"),
        runtime_root
            .join("apps")
            .join("backend")
            .join(".venv")
            .join("Scripts")
            .join("python.exe"),
        runtime_root
            .join("apps")
            .join("backend")
            .join(".venv")
            .join("bin")
            .join("python"),
    ] {
        push_python_path(
            &mut candidates,
            path.clone(),
            format!("project environment ({})", path.display()),
        );
    }

    append_python_launcher_paths(&mut candidates);
    append_where_python_paths(&mut candidates);
    append_known_environment_paths(&mut candidates);
    if cfg!(windows) {
        push_python_candidate(
            &mut candidates,
            PathBuf::from("py"),
            vec!["-3.12".into()],
            "Windows Python launcher (3.12)",
        );
    }
    for command in ["python", "python3", "python3.12"] {
        push_python_candidate(
            &mut candidates,
            PathBuf::from(command),
            Vec::new(),
            format!("PATH command {command}"),
        );
    }
    candidates
}

fn python_candidates(runtime_root: &Path) -> Vec<PythonCandidate> {
    external_python_candidates(runtime_root)
}

fn bootstrap_imports(runtime_root: &Path) -> Result<Vec<(String, String)>, String> {
    let contract_candidates = [
        runtime_root.join("app/backend/figuresmith/runtime/dependencies.json"),
        runtime_root.join("apps/backend/figuresmith/runtime/dependencies.json"),
    ];
    let Some(path) = contract_candidates.iter().find(|path| path.is_file()) else {
        return Ok(DEFAULT_BOOTSTRAP_IMPORTS
            .iter()
            .map(|(distribution, import_name)| ((*distribution).into(), (*import_name).into()))
            .collect());
    };
    let text = fs::read_to_string(path)
        .map_err(|err| format!("dependency contract unreadable: {} ({err})", path.display()))?;
    let value: serde_json::Value = serde_json::from_str(&text).map_err(|err| {
        format!(
            "dependency contract invalid JSON: {} ({err})",
            path.display()
        )
    })?;
    let packages = value
        .get("packages")
        .and_then(|value| value.as_array())
        .ok_or_else(|| "dependency contract packages are missing".to_string())?;
    let mut imports = Vec::new();
    for package in packages {
        if package.get("scope").and_then(|value| value.as_str()) != Some("bootstrap") {
            continue;
        }
        let distribution = package
            .get("distribution")
            .and_then(|value| value.as_str())
            .ok_or_else(|| "dependency contract distribution is missing".to_string())?;
        let import_name = package
            .get("import")
            .and_then(|value| value.as_str())
            .ok_or_else(|| "dependency contract import name is missing".to_string())?;
        imports.push((distribution.to_string(), import_name.to_string()));
    }
    if imports.is_empty() {
        return Err("dependency contract has no bootstrap packages".into());
    }
    Ok(imports)
}

fn probe_python_candidate(
    candidate: &PythonCandidate,
    imports: &[(String, String)],
) -> Result<PathBuf, String> {
    let imports_json = serde_json::to_string(imports)
        .map_err(|err| format!("dependency probe encoding failed: {err}"))?;
    let probe = r#"
import importlib.util
import json
import platform
import sys

items = json.loads(sys.argv[1])
missing = []
for distribution, import_name in items:
    try:
        present = importlib.util.find_spec(import_name) is not None
    except Exception:
        present = False
    if not present:
        missing.append(distribution)
print(json.dumps({
    "executable": sys.executable,
    "version": platform.python_version(),
    "major": sys.version_info.major,
    "minor": sys.version_info.minor,
    "missing": missing,
}, separators=(",", ":")))
"#;

    let mut command = Command::new(&candidate.program);
    command
        .args(&candidate.prefix_args)
        .arg("-c")
        .arg(probe)
        .arg(imports_json)
        .env_remove("PYTHONPATH")
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONSTARTUP")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let output = command
        .output()
        .map_err(|err| format!("{} unavailable: {err}", candidate.label))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let detail = stderr
            .lines()
            .last()
            .unwrap_or("probe exited unsuccessfully");
        return Err(format!(
            "{} rejected the probe: {}",
            candidate.label, detail
        ));
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let value = stdout
        .lines()
        .rev()
        .find_map(|line| serde_json::from_str::<serde_json::Value>(line).ok())
        .ok_or_else(|| format!("{} returned no Python probe result", candidate.label))?;
    let major = value
        .get("major")
        .and_then(|value| value.as_u64())
        .unwrap_or(0);
    let minor = value
        .get("minor")
        .and_then(|value| value.as_u64())
        .unwrap_or(0);
    if !(major == 3 && (10..13).contains(&minor)) {
        return Err(format!(
            "{} uses unsupported Python {}.{}; FigureSmith requires 3.10-3.12",
            candidate.label, major, minor
        ));
    }
    let missing = value
        .get("missing")
        .and_then(|value| value.as_array())
        .map(|values| {
            values
                .iter()
                .filter_map(|value| value.as_str())
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    if !missing.is_empty() {
        return Err(format!(
            "{} is missing bootstrap packages: {}",
            candidate.label,
            missing.join(", ")
        ));
    }
    let executable = value
        .get("executable")
        .and_then(|value| value.as_str())
        .map(PathBuf::from)
        .filter(|path| path.is_file())
        .or_else(|| {
            candidate
                .program
                .is_file()
                .then(|| candidate.program.clone())
        })
        .ok_or_else(|| {
            format!(
                "{} did not report a usable Python executable",
                candidate.label
            )
        })?;
    Ok(executable)
}

fn resolve_python(runtime_root: &Path) -> Result<PathBuf, String> {
    let imports = bootstrap_imports(runtime_root)?;
    let candidates = python_candidates(runtime_root);
    if candidates.is_empty() {
        return Err(
            "No development Python candidates found. Set FIGURESMITH_PYTHON for dev mode.".into(),
        );
    }
    let mut diagnostics = Vec::new();
    for candidate in &candidates {
        match probe_python_candidate(candidate, &imports) {
            Ok(path) => return Ok(path),
            Err(error) => diagnostics.push(error),
        }
    }
    Err(format!(
        "No supported development Python environment is ready for FigureSmith. Tried: {}",
        diagnostics.join("; ")
    ))
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

fn env_flag(name: &str) -> bool {
    std::env::var(name)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

const RUNTIME_REQUIRED_FILES: &[&str] = &[
    "python/python.exe",
    "python/python312._pth",
    "app/backend/main.py",
    "app/vendor/autofigure_edit/server.py",
    "app/backend/figuresmith/runtime/dependencies.json",
];
const SUPPORTED_RUNTIME_VARIANTS: &[&str] = &["cpu", "cu128"];

#[derive(Debug, Clone)]
struct ManifestFileEntry {
    path: String,
    size_bytes: u64,
    sha256: String,
}

fn normalize_manifest_path(value: &str) -> Result<String, String> {
    if value.is_empty() || value.contains('\\') || value.contains(':') || value.starts_with('/') {
        return Err(format!("runtime manifest contains invalid path: {value}"));
    }
    let parts: Vec<&str> = value.split('/').collect();
    if parts
        .iter()
        .any(|part| part.is_empty() || *part == "." || *part == "..")
    {
        return Err(format!("runtime manifest contains unsafe path: {value}"));
    }
    Ok(parts.join("/"))
}

fn runtime_file_is_forbidden(relative: &str) -> Option<&'static str> {
    let lower = relative.to_ascii_lowercase();
    let in_site_packages = lower.starts_with("python/lib/site-packages/");
    let parts: Vec<&str> = lower.split('/').collect();
    let extension = Path::new(&lower)
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("");
    if [
        "pt",
        "pth",
        "onnx",
        "safetensors",
        "gguf",
        "ckpt",
        "h5",
        "pb",
        "bin",
    ]
    .contains(&extension)
        && lower != "python/python312._pth"
        && !(in_site_packages && matches!(extension, "pth" | "bin"))
    {
        return Some("weight-like file");
    }
    let universally_forbidden = parts.iter().any(|part| {
        matches!(
            *part,
            ".git"
                | ".mypy_cache"
                | ".pytest_cache"
                | ".ruff_cache"
                | ".staging"
                | ".trash"
                | "__pycache__"
                | "node_modules"
                | "target"
                | ".venv"
                | "venv"
        )
    });
    let mutable_outside_site_packages = !in_site_packages
        && parts
            .iter()
            .any(|part| matches!(*part, "outputs" | "uploads"));
    if universally_forbidden || mutable_outside_site_packages {
        return Some("cache, build, or mutable-data directory");
    }
    if parts.starts_with(&["app", "resources", "models"]) {
        return Some("model staging directory");
    }
    if lower.ends_with(".whl") {
        return Some("loose wheel");
    }
    None
}

fn collect_runtime_files(root: &Path) -> Result<Vec<(String, PathBuf)>, String> {
    fn visit(
        root: &Path,
        directory: &Path,
        files: &mut Vec<(String, PathBuf)>,
    ) -> Result<(), String> {
        let mut entries = fs::read_dir(directory)
            .map_err(|err| {
                format!(
                    "cannot read application directory {}: {err}",
                    directory.display()
                )
            })?
            .collect::<Result<Vec<_>, _>>()
            .map_err(|err| {
                format!(
                    "cannot enumerate application directory {}: {err}",
                    directory.display()
                )
            })?;
        entries.sort_by_key(|entry| entry.file_name());
        for entry in entries {
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path).map_err(|err| {
                format!("cannot inspect application file {}: {err}", path.display())
            })?;
            let file_type = metadata.file_type();
            if file_type.is_symlink() {
                return Err(format!(
                    "application pack contains a symlink: {}",
                    path.display()
                ));
            }
            if file_type.is_dir() {
                visit(root, &path, files)?;
                continue;
            }
            if !file_type.is_file() {
                return Err(format!(
                    "application pack contains unsupported entry: {}",
                    path.display()
                ));
            }
            let relative = path
                .strip_prefix(root)
                .map_err(|_| format!("application file escapes root: {}", path.display()))?
                .to_string_lossy()
                .replace('\\', "/");
            if relative == "runtime-manifest.json" {
                continue;
            }
            if let Some(reason) = runtime_file_is_forbidden(&relative) {
                return Err(format!(
                    "application file rejected ({}): {}",
                    reason, relative
                ));
            }
            files.push((relative, path));
        }
        Ok(())
    }

    let mut files = Vec::new();
    visit(root, root, &mut files)?;
    files.sort_by_key(|(relative, _)| relative.to_ascii_lowercase());
    Ok(files)
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path)
        .map_err(|err| format!("cannot open application file {}: {err}", path.display()))?;
    let mut digest = Sha256::new();
    let mut buffer = [0u8; 1024 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|err| format!("cannot read application file {}: {err}", path.display()))?;
        if count == 0 {
            break;
        }
        digest.update(&buffer[..count]);
    }
    Ok(digest
        .finalize()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect())
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
}

fn validate_runtime_manifest(runtime_root: &Path) -> Result<(), String> {
    let manifest_path = runtime_root.join("runtime-manifest.json");
    let text = fs::read_to_string(&manifest_path).map_err(|err| {
        format!(
            "runtime manifest unreadable: {} ({err})",
            manifest_path.display()
        )
    })?;
    let value: serde_json::Value = serde_json::from_str(&text).map_err(|err| {
        format!(
            "runtime manifest invalid JSON: {} ({err})",
            manifest_path.display()
        )
    })?;
    if value.get("schema").and_then(|v| v.as_u64()) != Some(2) {
        return Err("unsupported runtime manifest schema; Runtime V1 requires schema 2".into());
    }
    if value.get("product").and_then(|v| v.as_str()) != Some("FigureSmith") {
        return Err("runtime manifest product is not FigureSmith".into());
    }
    if value.get("version").and_then(|v| v.as_str()) != Some(env!("CARGO_PKG_VERSION")) {
        return Err(format!(
            "runtime manifest version does not match desktop version {}",
            env!("CARGO_PKG_VERSION")
        ));
    }
    let variant = value
        .get("variant")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "runtime manifest variant is missing".to_string())?;
    if !SUPPORTED_RUNTIME_VARIANTS.contains(&variant) {
        return Err("runtime manifest variant must be cpu or cu128".into());
    }
    if value.get("runtime_complete").and_then(|v| v.as_bool()) != Some(true) {
        return Err("runtime manifest does not declare a self-contained runtime".into());
    }
    let python = value
        .get("python")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "runtime manifest Python metadata is missing".to_string())?;
    if python
        .get("version")
        .and_then(|v| v.as_str())
        .filter(|v| !v.trim().is_empty())
        .is_none()
        || !python
            .get("source_sha256")
            .and_then(|v| v.as_str())
            .is_some_and(valid_sha256)
    {
        return Err("runtime manifest Python metadata is invalid".into());
    }
    let locks = value
        .get("locks")
        .and_then(|v| v.as_object())
        .ok_or_else(|| "runtime manifest lock metadata is missing".to_string())?;
    if locks.len() != 3
        || ["requirements", "sources", "wheelhouse"]
            .iter()
            .any(|name| {
                !locks
                    .get(*name)
                    .and_then(|v| v.as_str())
                    .is_some_and(valid_sha256)
            })
    {
        return Err("runtime manifest lock metadata is invalid".into());
    }
    if value.get("contains_weights").and_then(|v| v.as_bool()) != Some(false) {
        return Err("runtime manifest does not prove contains_weights=false".into());
    }
    if value.get("contains_cache").and_then(|v| v.as_bool()) != Some(false) {
        return Err("runtime manifest does not prove contains_cache=false".into());
    }
    let files = value
        .get("files")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "runtime manifest file inventory is missing".to_string())?;
    let file_count = value
        .get("file_count")
        .and_then(|v| v.as_u64())
        .ok_or_else(|| "runtime manifest file_count is missing".to_string())?;
    if file_count != files.len() as u64 {
        return Err("runtime manifest file_count does not match files".into());
    }

    let mut expected = HashMap::<String, ManifestFileEntry>::new();
    for entry in files {
        let object = entry
            .as_object()
            .ok_or_else(|| "runtime manifest file entry is not an object".to_string())?;
        if object.len() != 3
            || !["path", "size_bytes", "sha256"]
                .iter()
                .all(|name| object.contains_key(*name))
        {
            return Err("runtime manifest file entry has unexpected fields".into());
        }
        let path = object
            .get("path")
            .and_then(|v| v.as_str())
            .ok_or_else(|| "runtime manifest file path is missing".to_string())?;
        let path = normalize_manifest_path(path)?;
        let key = path.to_ascii_lowercase();
        if expected.contains_key(&key) {
            return Err(format!("runtime manifest lists a file twice: {path}"));
        }
        let size_bytes = object
            .get("size_bytes")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| format!("runtime manifest size is invalid: {path}"))?;
        let sha256 = object
            .get("sha256")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("runtime manifest SHA-256 is missing: {path}"))?;
        if !valid_sha256(sha256) {
            return Err(format!("runtime manifest SHA-256 is invalid: {path}"));
        }
        expected.insert(
            key,
            ManifestFileEntry {
                path,
                size_bytes,
                sha256: sha256.to_string(),
            },
        );
    }

    for required in RUNTIME_REQUIRED_FILES {
        if !expected.contains_key(&required.to_ascii_lowercase()) {
            return Err(format!(
                "runtime manifest is missing required file: {required}"
            ));
        }
    }
    for (lock_name, relative) in [
        (
            "requirements",
            format!("locks/requirements-win-py312-{variant}.lock.json"),
        ),
        ("sources", format!("locks/sources-{variant}.lock.json")),
        (
            "wheelhouse",
            format!("locks/wheelhouse-{variant}.manifest.json"),
        ),
    ] {
        let entry = expected
            .get(&relative.to_ascii_lowercase())
            .ok_or_else(|| format!("runtime manifest is missing required file: {relative}"))?;
        if locks.get(lock_name).and_then(|v| v.as_str()) != Some(entry.sha256.as_str()) {
            return Err(format!(
                "runtime manifest {lock_name} lock digest does not match {relative}"
            ));
        }
    }

    let actual_files = collect_runtime_files(runtime_root)?;
    let mut actual = HashMap::<String, (String, PathBuf)>::new();
    for (relative, path) in actual_files {
        let key = relative.to_ascii_lowercase();
        if actual.insert(key, (relative.clone(), path)).is_some() {
            return Err(format!(
                "application pack has case-colliding file: {relative}"
            ));
        }
    }
    if actual.len() != expected.len() {
        let missing = expected
            .keys()
            .filter(|key| !actual.contains_key(*key))
            .take(10)
            .cloned()
            .collect::<Vec<_>>();
        let extra = actual
            .keys()
            .filter(|key| !expected.contains_key(*key))
            .take(10)
            .cloned()
            .collect::<Vec<_>>();
        return Err(format!(
            "runtime file inventory mismatch (missing={:?}; extra={:?})",
            missing, extra
        ));
    }
    for (key, entry) in expected {
        let Some((actual_path, path)) = actual.get(&key) else {
            return Err(format!("runtime manifest file is missing: {}", entry.path));
        };
        let size = fs::metadata(path)
            .map_err(|err| format!("cannot stat application file {}: {err}", actual_path))?
            .len();
        if size != entry.size_bytes {
            return Err(format!("runtime manifest size mismatch: {}", entry.path));
        }
        if sha256_file(path)? != entry.sha256 {
            return Err(format!("runtime manifest SHA-256 mismatch: {}", entry.path));
        }
    }
    Ok(())
}

fn packaged_runtime_root(base: &Path) -> Result<PathBuf, String> {
    let base = base.canonicalize().map_err(|err| {
        format!(
            "resource directory is not accessible: {} ({err})",
            base.display()
        )
    })?;
    let direct = base.join("runtime-manifest.json");
    let nested = base.join("runtime").join("runtime-manifest.json");
    match (direct.is_file(), nested.is_file()) {
        (true, false) => Ok(base),
        (false, true) => Ok(base.join("runtime")),
        (true, true) => Err(format!(
            "resource directory contains ambiguous application packs: {}",
            base.display()
        )),
        (false, false) => Err(format!(
            "application runtime manifest missing under {}",
            base.display()
        )),
    }
}

fn resolve_application_layout(
    runtime_root: PathBuf,
    release: bool,
) -> Result<RuntimeLayout, String> {
    if release {
        validate_runtime_manifest(&runtime_root)?;
    }
    let (backend_dir, vendor_dir) = if runtime_root.join("app").join("backend").is_dir() {
        (
            runtime_root.join("app").join("backend"),
            runtime_root
                .join("app")
                .join("vendor")
                .join("autofigure_edit"),
        )
    } else if !release {
        (
            runtime_root.join("apps").join("backend"),
            runtime_root.join("vendor").join("autofigure_edit"),
        )
    } else {
        return Err(format!(
            "packaged application backend is missing under {}",
            runtime_root.display()
        ));
    };
    let main_py = backend_dir.join("main.py");
    if !main_py.is_file() {
        return Err(format!("backend entry not found: {}", main_py.display()));
    }
    if !vendor_dir.join("server.py").is_file() {
        return Err(format!("vendor entry not found: {}", vendor_dir.display()));
    }
    let python = if release {
        let embedded = runtime_root.join("python").join("python.exe");
        if !embedded.is_file() {
            return Err(format!(
                "packaged runtime interpreter is missing: {}",
                embedded.display()
            ));
        }
        embedded
    } else {
        resolve_python(&runtime_root)?
    };
    Ok(RuntimeLayout {
        root: runtime_root,
        backend_dir,
        vendor_dir,
        main_py,
        python,
        release,
    })
}

fn resolve_runtime_layout(base: &Path) -> Result<RuntimeLayout, String> {
    let base = base
        .canonicalize()
        .map_err(|err| format!("runtime root is not accessible: {} ({err})", base.display()))?;
    if base.join("runtime-manifest.json").is_file() {
        return resolve_application_layout(base, true);
    }
    if base.join("runtime").join("runtime-manifest.json").is_file() {
        return resolve_application_layout(base.join("runtime"), true);
    }
    resolve_application_layout(base, false)
}

/// Resolve the application pack through the Tauri Resource directory.
pub fn resolve_release_runtime_root(resource_dir: Option<PathBuf>) -> Result<PathBuf, String> {
    let mut candidates = Vec::new();
    if let Some(resource) = resource_dir {
        candidates.push(resource);
    }
    if let Ok(executable) = std::env::current_exe() {
        if let Some(parent) = executable.parent() {
            candidates.push(parent.to_path_buf());
        }
    }
    let mut diagnostics = Vec::new();
    for candidate in candidates {
        match packaged_runtime_root(&candidate) {
            Ok(runtime_root) => {
                validate_runtime_manifest(&runtime_root)?;
                return Ok(runtime_root);
            }
            Err(error) => diagnostics.push(error),
        }
    }
    Err(format!(
        "companion Runtime V1 pack is unavailable beside the application; refusing PATH, Python, and source fallback ({})",
        diagnostics.join("; ").chars().take(1200).collect::<String>()
    ))
}

/// Resolve source files only for an explicit development build.
pub fn resolve_development_runtime_root() -> Result<PathBuf, String> {
    if let Ok(raw) = std::env::var("FIGURESMITH_RUNTIME_DIR") {
        if !raw.trim().is_empty() {
            return Ok(resolve_runtime_layout(Path::new(raw.trim()))?.root);
        }
    }
    let root = resolve_repo_root()?;
    if !root.join("apps/backend/main.py").is_file()
        || !root.join("vendor/autofigure_edit/server.py").is_file()
    {
        return Err("development application source is incomplete".into());
    }
    Ok(root)
}

/// Release binaries never inspect PATH or repository markers for application code.
pub fn resolve_runtime_root(resource_dir: Option<PathBuf>) -> Result<PathBuf, String> {
    if !cfg!(debug_assertions) || env_flag("FIGURESMITH_RELEASE_MODE") {
        resolve_release_runtime_root(resource_dir)
    } else {
        resolve_development_runtime_root()
    }
}

/// Resolve monorepo root from env, cargo manifest, or cwd in development mode.
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

    fn temp_runtime_root(label: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "figuresmith-{label}-{}-{}",
            std::process::id(),
            generate_token()
        ));
        std::fs::create_dir_all(&root).expect("runtime fixture root");
        root
    }

    fn write_runtime_fixture(root: &Path, product: &str, version: &str, schema: u64) {
        let backend = root.join("app").join("backend");
        let vendor = root.join("app").join("vendor").join("autofigure_edit");
        let runtime = backend.join("figuresmith").join("runtime");
        let python = root.join("python");
        let locks = root.join("locks");
        std::fs::create_dir_all(&runtime).expect("runtime fixture");
        std::fs::create_dir_all(&vendor).expect("vendor fixture");
        std::fs::create_dir_all(python.join("Lib/site-packages")).expect("python fixture");
        std::fs::create_dir_all(&locks).expect("locks fixture");
        std::fs::write(backend.join("main.py"), b"# fixture\n").expect("main fixture");
        std::fs::write(vendor.join("server.py"), b"# fixture\n").expect("vendor fixture");
        std::fs::write(
            runtime.join("dependencies.json"),
            br#"{"schema":1,"packages":[]}"#,
        )
        .expect("dependency fixture");
        std::fs::write(python.join("python.exe"), b"embedded python fixture\n")
            .expect("python exe");
        std::fs::write(
            python.join("python312._pth"),
            b"python312.zip\n.\nLib\\site-packages\nimport site\n",
        )
        .expect("pth fixture");
        for name in [
            "requirements-win-py312-cpu.lock.json",
            "sources-cpu.lock.json",
            "wheelhouse-cpu.manifest.json",
        ] {
            std::fs::write(locks.join(name), format!("{name}\n")).expect("lock fixture");
        }

        let mut files = Vec::new();
        for (relative, path) in collect_runtime_files(root).expect("fixture files") {
            files.push(serde_json::json!({
                "path": relative,
                "size_bytes": std::fs::metadata(&path).expect("fixture stat").len(),
                "sha256": sha256_file(&path).expect("fixture hash"),
            }));
        }
        let lock_digest = |name: &str| {
            files
                .iter()
                .find(|entry| entry["path"] == format!("locks/{name}"))
                .and_then(|entry| entry["sha256"].as_str())
                .unwrap()
                .to_string()
        };
        let manifest = serde_json::json!({
            "schema": schema,
            "product": product,
            "version": version,
            "variant": "cpu",
            "platform": "Windows",
            "arch": "x86_64",
            "python": {"version": "3.12.10", "source_sha256": "a".repeat(64)},
            "locks": {
                "requirements": lock_digest("requirements-win-py312-cpu.lock.json"),
                "sources": lock_digest("sources-cpu.lock.json"),
                "wheelhouse": lock_digest("wheelhouse-cpu.manifest.json"),
            },
            "runtime_complete": true,
            "contains_weights": false,
            "contains_cache": false,
            "file_count": files.len(),
            "files": files,
        });
        std::fs::write(
            root.join("runtime-manifest.json"),
            serde_json::to_vec_pretty(&manifest).expect("manifest json"),
        )
        .expect("manifest fixture");
    }

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
    fn release_requires_a_resource_directory() {
        let error = resolve_release_runtime_root(None).expect_err("resource is required");
        assert!(error.contains("refusing PATH, Python, and source fallback"));
    }

    #[test]
    fn release_runtime_manifest_is_validated_with_embedded_python() {
        let root = temp_runtime_root("runtime");
        write_runtime_fixture(&root, "FigureSmith", env!("CARGO_PKG_VERSION"), 2);
        validate_runtime_manifest(&root).expect("valid Runtime V1 pack");
        let layout = resolve_application_layout(root.clone(), true).expect("release layout");
        assert_eq!(layout.python, root.join("python/python.exe"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn release_manifest_rejects_wrong_identity_and_schema_one() {
        let wrong_product = temp_runtime_root("identity");
        write_runtime_fixture(&wrong_product, "OtherProduct", env!("CARGO_PKG_VERSION"), 2);
        let error = validate_runtime_manifest(&wrong_product).expect_err("wrong product");
        assert!(error.contains("product is not FigureSmith"));
        let _ = std::fs::remove_dir_all(wrong_product);

        let schema_one = temp_runtime_root("schema-one");
        write_runtime_fixture(&schema_one, "FigureSmith", env!("CARGO_PKG_VERSION"), 1);
        let error = validate_runtime_manifest(&schema_one).expect_err("schema one");
        assert!(error.contains("requires schema 2"));
        let _ = std::fs::remove_dir_all(schema_one);
    }

    #[test]
    fn release_manifest_rejects_missing_interpreter() {
        let root = temp_runtime_root("missing-python");
        write_runtime_fixture(&root, "FigureSmith", env!("CARGO_PKG_VERSION"), 2);
        std::fs::remove_file(root.join("python/python.exe")).expect("remove interpreter");
        let error = validate_runtime_manifest(&root).expect_err("missing interpreter");
        assert!(error.contains("inventory mismatch"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn release_manifest_rejects_tampered_extra_and_package_namespace_files_correctly() {
        let root = temp_runtime_root("tamper");
        write_runtime_fixture(&root, "FigureSmith", env!("CARGO_PKG_VERSION"), 2);
        std::fs::write(root.join("app/backend/main.py"), b"tampered\n").expect("tamper");
        let error = validate_runtime_manifest(&root).expect_err("tampered file");
        assert!(error.contains("SHA-256 mismatch") || error.contains("size mismatch"));
        let _ = std::fs::remove_dir_all(root);

        let root = temp_runtime_root("package-uploads");
        let package_dir = root.join("python/Lib/site-packages/example/resources/uploads");
        std::fs::create_dir_all(&package_dir).expect("package namespace");
        std::fs::write(
            package_dir.join("types.py"),
            b"# legitimate package namespace\n",
        )
        .expect("package file");
        assert!(collect_runtime_files(&root).is_ok());
        std::fs::create_dir_all(root.join("app/uploads")).expect("mutable uploads");
        std::fs::write(root.join("app/uploads/user.txt"), b"user data\n").expect("user data");
        let error = collect_runtime_files(&root).expect_err("mutable uploads rejected");
        assert!(error.contains("mutable-data"));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn release_manifest_rejects_wrong_version() {
        let root = temp_runtime_root("version");
        write_runtime_fixture(&root, "FigureSmith", "99.99.99", 2);
        let error = validate_runtime_manifest(&root).expect_err("wrong version");
        assert!(error.contains("does not match desktop version"));
        let _ = std::fs::remove_dir_all(root);
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
