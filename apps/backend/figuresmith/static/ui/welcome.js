(function () {
  "use strict";

  var FS = window.FigureSmithUI;
  FS.ensureBridge();
  FS.renderNav("welcome");

  var I18N = {
    en: {
      tagline: "Local scientific figure desktop",
      title: "Welcome to FigureSmith",
      subtitle:
        "First-run setup checks your environment, imports local SAM3 / RMBG weights, and optionally configures an OpenAI-compatible generation provider. You can skip any step.",
      start: "Start setup",
      skip: "Skip for now",
      goto_create: "Go to Create",
      back: "Back",
      next: "Next",
      skip_step: "Skip step",
      finish: "Finish",
      step_env: "Environment check",
      step_env_copy: "Detect platform, Python, CUDA/GPU, and installed model packs.",
      step_sam3: "Import SAM3",
      step_sam3_copy: "Import a local sam3.pt / .pth checkpoint. Remote SAM is not offered.",
      step_rmbg: "Import RMBG",
      step_rmbg_copy: "Import a local RMBG-2.0 ZIP or model directory.",
      step_provider: "Generation provider (optional)",
      step_provider_copy:
        "OpenAI-compatible keys stay in the Create page session for this phase. No new plaintext API key storage is written to settings.json.",
      step_done: "Ready",
      step_done_copy: "Onboarding complete. Continue to Create or manage models anytime.",
      refresh: "Refresh status",
      import_desktop: "Import with desktop picker",
      import_models_page: "Open Models page",
      gpu_ok: "CUDA GPU detected",
      gpu_missing: "No CUDA GPU",
      sam3_ok: "SAM3 installed",
      sam3_missing: "SAM3 not installed",
      rmbg_ok: "RMBG installed",
      rmbg_missing: "RMBG not installed",
      offline_on: "Strict offline: on",
      mark_done: "Mark setup complete",
      provider_note:
        "Provider API keys are entered on the Create / Import pages and are not newly persisted to settings.json in Phase 5.",
      loading: "Loading system status…",
      error: "Failed to load system status",
    },
    zh: {
      tagline: "本地科研插图桌面端",
      title: "欢迎使用 FigureSmith / 图匠",
      subtitle:
        "首次启动将检查环境、导入本地 SAM3 / RMBG 权重，并可选配置 OpenAI 兼容生成服务。任意步骤都可跳过。",
      start: "开始配置",
      skip: "暂时跳过",
      goto_create: "进入创建",
      back: "上一步",
      next: "下一步",
      skip_step: "跳过此步",
      finish: "完成",
      step_env: "环境检查",
      step_env_copy: "检测平台、Python、CUDA/GPU 与已安装模型。",
      step_sam3: "导入 SAM3",
      step_sam3_copy: "导入本地 sam3.pt / .pth。不提供远程 SAM 选项。",
      step_rmbg: "导入 RMBG",
      step_rmbg_copy: "导入本地 RMBG-2.0 ZIP 或模型目录。",
      step_provider: "生成模型（可选）",
      step_provider_copy:
        "OpenAI 兼容密钥仍在创建页会话中填写。本阶段不会把 API Key 新写入明文 settings.json。",
      step_done: "完成",
      step_done_copy: "引导已完成。可进入创建，或随时到模型页管理权重。",
      refresh: "刷新状态",
      import_desktop: "使用桌面选择器导入",
      import_models_page: "打开模型页",
      gpu_ok: "已检测到 CUDA GPU",
      gpu_missing: "未检测到 CUDA GPU",
      sam3_ok: "SAM3 已安装",
      sam3_missing: "SAM3 未安装",
      rmbg_ok: "RMBG 已安装",
      rmbg_missing: "RMBG 未安装",
      offline_on: "严格离线：开启",
      mark_done: "标记配置完成",
      provider_note:
        "Provider API Key 在创建/导入页填写；阶段五不会新增明文写入 settings.json。",
      loading: "正在加载系统状态…",
      error: "无法加载系统状态",
    },
  };

  function t(key) {
    return FS.t(I18N, key);
  }

  function applyStaticI18n() {
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
  }

  var status = null;
  var stepIndex = 0;
  var STEPS = ["env", "sam3", "rmbg", "provider", "done"];

  var wizardPanel = document.getElementById("wizardPanel");
  var stepTitle = document.getElementById("stepTitle");
  var stepCopy = document.getElementById("stepCopy");
  var stepList = document.getElementById("stepList");
  var stepBody = document.getElementById("stepBody");
  var stepAlert = document.getElementById("stepAlert");
  var progress = document.getElementById("wizardProgress");
  var btnStart = document.getElementById("btnStart");
  var btnSkip = document.getElementById("btnSkip");
  var btnBack = document.getElementById("btnBack");
  var btnNext = document.getElementById("btnNext");
  var btnSkipStep = document.getElementById("btnSkipStep");

  function showAlert(msg, kind) {
    if (!msg) {
      stepAlert.hidden = true;
      stepAlert.textContent = "";
      return;
    }
    stepAlert.hidden = false;
    stepAlert.className = "fs-alert" + (kind ? " " + kind : "");
    stepAlert.textContent = msg;
  }

  async function loadStatus() {
    status = await FS.api("/api/system/status");
    return status;
  }

  async function markOnboarding(completed) {
    await FS.api("/api/system/onboarding", {
      method: "POST",
      body: { completed: !!completed },
    });
  }

  function renderStepList() {
    stepList.innerHTML = "";
    var labels = {
      env: t("step_env"),
      sam3: t("step_sam3"),
      rmbg: t("step_rmbg"),
      provider: t("step_provider"),
      done: t("step_done"),
    };
    STEPS.forEach(function (id, idx) {
      var row = document.createElement("div");
      row.className = "fs-step";
      if (idx === stepIndex) row.classList.add("is-current");
      if (idx < stepIndex) row.classList.add("is-done");
      row.innerHTML =
        '<div class="fs-step-num">' +
        (idx < stepIndex ? "✓" : idx + 1) +
        '</div><div><strong>' +
        labels[id] +
        "</strong></div>";
      stepList.appendChild(row);
    });
    if (progress) {
      progress.style.width = Math.round(((stepIndex + 1) / STEPS.length) * 100) + "%";
    }
  }

  function kv(label, value) {
    return (
      '<div class="fs-status-row"><span>' +
      label +
      "</span><span>" +
      value +
      "</span></div>"
    );
  }

  function renderEnvBody() {
    var s = status || {};
    var locale = FS.getLocale();
    var gpuMsg = s.gpu_available
      ? t("gpu_ok") + (s.gpu_name ? " — " + s.gpu_name : "")
      : locale === "zh"
        ? (s.messages && s.messages.gpu_missing_zh) || t("gpu_missing")
        : (s.messages && s.messages.gpu_missing_en) || t("gpu_missing");

    var html = '<div class="fs-status-list">';
    html += kv("Product", (s.product || "FigureSmith") + " " + (s.version || ""));
    html += kv(
      "Platform",
      ((s.platform && s.platform.system) || "?") +
        " / " +
        ((s.platform && s.platform.machine) || "?")
    );
    html += kv("Python", s.python || "?");
    html += kv("GPU", s.gpu_available ? s.gpu_name || "CUDA" : t("gpu_missing"));
    html += kv("CUDA", s.cuda_version || "—");
    html += kv(
      "VRAM",
      s.vram_total_mb != null ? s.vram_free_mb + " / " + s.vram_total_mb + " MB free/total" : "—"
    );
    html += kv("SAM3", s.sam3_loaded ? t("sam3_ok") : t("sam3_missing"));
    html += kv("RMBG", s.rmbg_loaded ? t("rmbg_ok") : t("rmbg_missing"));
    html += kv("Offline", s.strict_offline ? t("offline_on") : "off");
    html += "</div>";
    html +=
      '<div class="fs-btn-row"><button type="button" class="fs-btn" id="btnRefreshStatus">' +
      t("refresh") +
      "</button></div>";
    stepBody.innerHTML = html;
    if (!s.gpu_available) {
      showAlert(gpuMsg, "warn");
    } else {
      showAlert("", null);
    }
    var btn = document.getElementById("btnRefreshStatus");
    if (btn) {
      btn.addEventListener("click", async function () {
        try {
          await loadStatus();
          renderCurrentStep();
        } catch (err) {
          showAlert(String(err.message || err), "bad");
        }
      });
    }
  }

  function renderImportBody(kind) {
    var installed = kind === "sam3" ? status && status.sam3_loaded : status && status.rmbg_loaded;
    var html = "";
    html +=
      '<p class="fs-muted">' +
      (installed
        ? kind.toUpperCase() + " ✓"
        : FS.isDesktop()
          ? t("import_desktop")
          : t("import_models_page")) +
      "</p>";
    html += '<div class="fs-btn-row">';
    if (FS.isDesktop()) {
      html +=
        '<button type="button" class="fs-btn primary" id="btnDesktopImport">' +
        t("import_desktop") +
        "</button>";
    }
    html +=
      '<a class="fs-btn" href="/models.html">' + t("import_models_page") + "</a>";
    html +=
      '<button type="button" class="fs-btn" id="btnRefreshStatus">' + t("refresh") + "</button>";
    html += "</div>";
    stepBody.innerHTML = html;
    showAlert(installed ? "" : null, installed ? "ok" : null);
    if (installed) showAlert(kind.toUpperCase() + " OK", "ok");

    var refresh = document.getElementById("btnRefreshStatus");
    if (refresh) {
      refresh.addEventListener("click", async function () {
        await loadStatus();
        renderCurrentStep();
      });
    }
    var di = document.getElementById("btnDesktopImport");
    if (di) {
      di.addEventListener("click", async function () {
        try {
          di.disabled = true;
          if (kind === "sam3") {
            await FS.tauriInvoke("import_sam3_model", {});
          } else {
            // Prefer archive; user can also use models page for folder.
            try {
              await FS.tauriInvoke("import_rmbg_archive", {});
            } catch (err) {
              if (String(err).indexOf("cancelled") !== -1) throw err;
              await FS.tauriInvoke("import_rmbg_folder", {});
            }
          }
          await loadStatus();
          renderCurrentStep();
        } catch (err) {
          if (String(err).indexOf("cancelled") !== -1) return;
          showAlert(String(err.message || err), "bad");
        } finally {
          di.disabled = false;
        }
      });
    }
  }

  function renderProviderBody() {
    stepBody.innerHTML =
      '<p class="fs-muted">' +
      t("provider_note") +
      '</p><div class="fs-btn-row"><a class="fs-btn" href="/">' +
      t("goto_create") +
      "</a></div>";
    showAlert("", null);
  }

  function renderDoneBody() {
    stepBody.innerHTML =
      '<div class="fs-btn-row">' +
      '<button type="button" class="fs-btn primary" id="btnMarkDone">' +
      t("mark_done") +
      "</button>" +
      '<a class="fs-btn" href="/">' +
      t("goto_create") +
      "</a>" +
      '<a class="fs-btn" href="/models.html">' +
      t("import_models_page") +
      "</a></div>";
    showAlert("", null);
    var btn = document.getElementById("btnMarkDone");
    if (btn) {
      btn.addEventListener("click", async function () {
        try {
          await markOnboarding(true);
          showAlert("OK", "ok");
          window.location.href = "/";
        } catch (err) {
          showAlert(String(err.message || err), "bad");
        }
      });
    }
  }

  function renderCurrentStep() {
    var id = STEPS[stepIndex];
    var titles = {
      env: t("step_env"),
      sam3: t("step_sam3"),
      rmbg: t("step_rmbg"),
      provider: t("step_provider"),
      done: t("step_done"),
    };
    var copies = {
      env: t("step_env_copy"),
      sam3: t("step_sam3_copy"),
      rmbg: t("step_rmbg_copy"),
      provider: t("step_provider_copy"),
      done: t("step_done_copy"),
    };
    stepTitle.textContent = titles[id];
    stepCopy.textContent = copies[id];
    btnBack.disabled = stepIndex === 0;
    btnNext.textContent = stepIndex >= STEPS.length - 1 ? t("finish") : t("next");
    renderStepList();
    if (id === "env") renderEnvBody();
    else if (id === "sam3") renderImportBody("sam3");
    else if (id === "rmbg") renderImportBody("rmbg");
    else if (id === "provider") renderProviderBody();
    else renderDoneBody();
  }

  async function openWizard(startAt) {
    wizardPanel.hidden = false;
    stepIndex = startAt || 0;
    try {
      await loadStatus();
      // Smart start: jump past installed models when beginning.
      if (stepIndex === 0 && status) {
        /* keep env first */
      }
      renderCurrentStep();
    } catch (err) {
      showAlert(t("error") + ": " + (err.message || err), "bad");
    }
  }

  btnStart.addEventListener("click", function () {
    openWizard(0);
  });

  btnSkip.addEventListener("click", async function () {
    try {
      await markOnboarding(true);
    } catch (_e) {}
    window.location.href = "/";
  });

  btnBack.addEventListener("click", function () {
    if (stepIndex > 0) {
      stepIndex -= 1;
      renderCurrentStep();
    }
  });

  btnSkipStep.addEventListener("click", function () {
    if (stepIndex < STEPS.length - 1) {
      stepIndex += 1;
      renderCurrentStep();
    }
  });

  btnNext.addEventListener("click", async function () {
    if (stepIndex >= STEPS.length - 1) {
      try {
        await markOnboarding(true);
        window.location.href = "/";
      } catch (err) {
        showAlert(String(err.message || err), "bad");
      }
      return;
    }
    stepIndex += 1;
    renderCurrentStep();
  });

  applyStaticI18n();

  // Auto-enter wizard when onboarding incomplete; otherwise keep landing.
  loadStatus()
    .then(function (s) {
      if (s && s.onboarding_completed) {
        // already done — leave hero actions
        return;
      }
      // Auto-open wizard for first run
      openWizard(0);
    })
    .catch(function () {
      /* stay on hero */
    });
})();
