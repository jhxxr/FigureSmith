import { listen } from "@tauri-apps/api/event";

const statusEl = document.querySelector<HTMLElement>("#status");
const splashEl = document.querySelector<HTMLElement>("#splashCard");
const progressEl = document.querySelector<HTMLElement>(".progress");
const isZh = navigator.language.toLowerCase().startsWith("zh");

type StartupPhase = "locating" | "verifying" | "starting" | "ready" | "error";
type StartupCode = "runtime-missing" | "runtime-invalid" | "backend-failed";

interface StartupStatus {
  phase: StartupPhase;
  code?: StartupCode;
  checked_files?: number;
  total_files?: number;
  detail?: string;
}

const PHASE_PROGRESS: Record<StartupPhase, number> = {
  locating: 18,
  verifying: 52,
  starting: 78,
  ready: 100,
  error: 100,
};

function setPhase(phase: StartupPhase): void {
  if (splashEl) {
    splashEl.dataset.phase = phase;
  }
  if (progressEl) {
    progressEl.setAttribute("aria-valuenow", String(PHASE_PROGRESS[phase] ?? 0));
  }
}

function renderStatus(event: StartupStatus): void {
  if (!statusEl) return;

  setPhase(event.phase);
  statusEl.classList.toggle("error", event.phase === "error");
  if (event.phase === "error") {
    const message = event.code === "runtime-missing"
      ? (isZh
        ? "未找到内置 CPU Runtime V1。请重新运行 FigureSmith Setup/MSI；Runtime ZIP 仅用于修复。"
        : "The installed CPU Runtime V1 is missing. Re-run the FigureSmith Setup/MSI installer; the Runtime ZIP is for repair only.")
      : event.code === "runtime-invalid"
        ? (isZh
          ? "内置 Runtime V1 不完整或已被修改。请重新运行 Setup/MSI，或用匹配版本的 CPU Runtime ZIP 修复。"
          : "The installed Runtime V1 is incomplete or modified. Re-run Setup/MSI, or repair it with the matching CPU Runtime ZIP.")
        : (isZh
          ? "Runtime 已验证，但本地后端没有就绪。请重试并检查安装状态。"
          : "Runtime verification passed, but the local backend did not become ready. Retry and check the installation.");
    const detail = event.detail ? `\n${event.detail}` : "";
    statusEl.textContent = `${message}${detail}`;
    return;
  }

  let message: string;
  switch (event.phase) {
    case "locating":
      message = isZh ? "正在定位已安装的 Runtime V1..." : "Locating the installed Runtime V1...";
      break;
    case "verifying": {
      const progress = event.checked_files !== undefined && event.total_files !== undefined
        ? isZh
          ? `已验证 ${event.checked_files.toLocaleString()} / ${event.total_files.toLocaleString()} 个文件`
          : `Verified ${event.checked_files.toLocaleString()} / ${event.total_files.toLocaleString()} files`
        : isZh ? "正在读取 Runtime 清单并准备校验..." : "Reading the Runtime manifest and preparing verification...";
      message = `${isZh ? "正在验证内置 Runtime V1" : "Verifying the packaged Runtime V1"}...\n${progress}`;
      if (
        progressEl &&
        event.checked_files !== undefined &&
        event.total_files !== undefined &&
        event.total_files > 0
      ) {
        const ratio = Math.min(1, Math.max(0, event.checked_files / event.total_files));
        const value = Math.round(24 + ratio * 48);
        progressEl.setAttribute("aria-valuenow", String(value));
        const bar = progressEl.querySelector("span");
        if (bar) {
          (bar as HTMLElement).style.width = `${value}%`;
        }
      }
      break;
    }
    case "starting":
      message = isZh ? "Runtime 校验完成，正在启动本地后端..." : "Runtime verified. Starting the local backend...";
      break;
    case "ready":
      message = isZh ? "本地后端已就绪，正在打开编辑器..." : "Local backend is ready. Opening the editor...";
      break;
    default:
      message = isZh ? "正在准备 FigureSmith..." : "Preparing FigureSmith...";
  }
  statusEl.textContent = message;
}

renderStatus({ phase: "locating" });
void listen<StartupStatus>("startup-status", (event) => renderStatus(event.payload));
