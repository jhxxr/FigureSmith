import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

const statusEl = document.querySelector<HTMLElement>("#status");
const preparePanel = document.querySelector<HTMLElement>("#prepareEnvPanel");
const prepareButton = document.querySelector<HTMLButtonElement>("#prepareEnvButton");
const prepareHint = document.querySelector<HTMLElement>("#prepareEnvHint");
const isZh = navigator.language.toLowerCase().startsWith("zh");

function setPrepareText(buttonText: string, hintText: string): void {
  if (prepareButton) prepareButton.textContent = buttonText;
  if (prepareHint) prepareHint.textContent = hintText;
}

if (statusEl) {
  statusEl.textContent = isZh
    ? "正在检查 Python 环境并启动本地编辑器..."
    : "Checking Python environments and starting the local editor...";
}

if (prepareButton) {
  prepareButton.addEventListener("click", async () => {
    prepareButton.disabled = true;
    setPrepareText(
      isZh ? "正在创建隔离环境..." : "Creating isolated environment...",
      isZh
        ? "正在用户数据目录创建独立环境并安装 FigureSmith 服务包，请不要关闭窗口。"
        : "Creating a separate environment and installing FigureSmith service packages. Keep this window open.",
    );
    if (statusEl) {
      statusEl.classList.remove("error");
      statusEl.textContent = isZh
        ? "正在创建隔离 Python 环境，完成后会自动重启..."
        : "Creating the isolated Python environment. FigureSmith will restart when it is ready...";
    }
    try {
      await invoke<string>("prepare_managed_python_environment");
    } catch (error) {
      prepareButton.disabled = false;
      setPrepareText(
        isZh ? "重试创建隔离环境" : "Retry isolated environment setup",
        isZh
          ? "原有 Python 环境不会被修改。"
          : "Your existing Python installations are not modified.",
      );
      if (statusEl) {
        statusEl.classList.add("error");
        statusEl.textContent = `${isZh ? "创建失败：" : "Setup failed: "}${String(error)}`;
      }
    }
  });
}

void listen<string>("sidecar-error", (event) => {
  if (statusEl) {
    statusEl.classList.add("error");
    statusEl.textContent = isZh
      ? `无法启动本地后端：\n${event.payload}`
      : `Could not start the local backend:\n${event.payload}`;
  }
  if (preparePanel) preparePanel.hidden = false;
  setPrepareText(
    isZh ? "创建隔离环境并重启" : "Create isolated environment and restart",
    isZh
      ? "FigureSmith 会把环境安装到用户数据目录，不会修改现有 Python 环境。"
      : "FigureSmith installs into its user data directory and does not modify existing Python environments.",
  );
});
