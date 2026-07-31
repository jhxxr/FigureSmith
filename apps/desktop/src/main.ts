/**
 * Local startup splash.
 *
 * The Rust shell owns sidecar startup, authenticated readiness, dynamic ACL
 * registration, and remote-window creation. This page deliberately performs
 * no IPC call and never receives the session token.
 */

import { listen } from "@tauri-apps/api/event";

const statusEl = document.querySelector("#status");

if (statusEl) {
  statusEl.textContent = "Starting local FigureSmith backend…";
}

void listen<string>("sidecar-error", (event) => {
  if (statusEl) {
    statusEl.textContent = `Failed to start FigureSmith backend:\n${event.payload}`;
  }
});
