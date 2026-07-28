/**
 * Minimal splash / bootstrap UI for the Tauri shell.
 *
 * Production flow: Rust starts the Python sidecar, then navigates the WebView
 * to http://127.0.0.1:<port>/ (vendor UI). This page is shown only while the
 * sidecar is starting or if navigation is delayed.
 *
 * Session token is never stored in localStorage.
 */

import { invoke } from "@tauri-apps/api/core";

type SessionInfo = {
  port: number;
  api_base: string;
  token: string;
  ready: boolean;
};

const statusEl = document.querySelector("#status");

function setStatus(msg: string) {
  if (statusEl) statusEl.textContent = msg;
}

async function waitForSession(maxAttempts = 60, delayMs = 500): Promise<SessionInfo> {
  let lastError = "sidecar not ready";
  for (let i = 0; i < maxAttempts; i++) {
    try {
      const session = await invoke<SessionInfo>("get_session");
      if (session && session.ready && session.port > 0) {
        return session;
      }
      lastError = "sidecar reported not ready";
    } catch (err) {
      lastError = String(err);
    }
    setStatus(`Waiting for backend… (${i + 1}/${maxAttempts})\n${lastError}`);
    await new Promise((r) => setTimeout(r, delayMs));
  }
  throw new Error(`Sidecar did not become ready: ${lastError}`);
}

async function main() {
  try {
    setStatus("Contacting Tauri shell…");
    const session = await waitForSession();
    // Inject in-memory session for any remaining same-origin scripts.
    // Token must not be persisted.
    (window as unknown as { __FIGURESMITH__?: Record<string, unknown> }).__FIGURESMITH__ = {
      token: session.token,
      port: session.port,
      apiBase: session.api_base,
    };
    setStatus(`Backend ready on ${session.api_base}\nLoading editor…`);
    // Navigate to vendor UI served by the Python sidecar (same origin for API).
    window.location.href = `${session.api_base}/`;
  } catch (err) {
    setStatus(`Failed to start FigureSmith backend:\n${String(err)}`);
  }
}

void main();
