import { listen } from "@tauri-apps/api/event";

const statusEl = document.querySelector<HTMLElement>("#status");
const isZh = navigator.language.toLowerCase().startsWith("zh");

if (statusEl) {
  statusEl.textContent = isZh
    ? "正在验证内置 Runtime V1 并启动本地编辑器..."
    : "Verifying the packaged Runtime V1 and starting the local editor...";
}

void listen<string>("sidecar-error", (event) => {
  if (statusEl) {
    statusEl.classList.add("error");
    statusEl.textContent = isZh
      ? `无法启动本地后端。请确认完整的 Runtime V1 包位于 FigureSmith 旁边。\n${event.payload}`
      : `Could not start the local backend. Ensure a complete Runtime V1 pack is installed beside FigureSmith.\n${event.payload}`;
  }
});
