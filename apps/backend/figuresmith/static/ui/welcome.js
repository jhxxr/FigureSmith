(function () {
  "use strict";

  var FS = window.FigureSmithUI;
  FS.ensureBridge();
  FS.renderNav("welcome");

  var I18N = {
    en: {
      tagline: "Local scientific figure desktop",
      eyebrow: "A local figure workspace",
      title: "Welcome to FigureSmith",
      subtitle: "Check the selected Python environment, then bring in local model files when you are ready.",
      start: "Check readiness",
      skip: "Do this later",
      goto_create: "Go to Create",
      back: "Back",
      next: "Next",
      skip_step: "Skip step",
      finish: "Finish",
      step_env: "Environment",
      step_env_copy: "FigureSmith uses your Python installation. Check the service packages first, then review model packages and GPU support.",
      step_sam3: "Import SAM3",
      step_sam3_copy: "Import a local SAM3 checkpoint. Remote model downloads are not offered.",
      step_rmbg: "Import RMBG",
      step_rmbg_copy: "Import a local RMBG-2.0 ZIP or model directory.",
      step_provider: "Generation provider",
      step_provider_copy: "Provider keys stay in the Create page session and are not newly written to settings.json.",
      step_done: "Ready",
      step_done_copy: "Your workspace is set up. You can return here whenever the Python or model environment changes.",
      refresh: "Refresh status",
      import_desktop: "Choose a file",
      import_models_page: "Open Models",
      gpu_ok: "CUDA GPU ready",
      gpu_missing: "No CUDA GPU",
      sam3_ok: "SAM3 ready",
      sam3_missing: "SAM3 not imported",
      rmbg_ok: "RMBG ready",
      rmbg_missing: "RMBG not imported",
      offline_on: "Strict offline on",
      mark_done: "Finish setup",
      provider_note: "Open Create to configure a generation provider for this session.",
      loading: "Checking your workspace...",
      error: "Could not load workspace status",
      status_eyebrow: "Workspace status",
      status_title: "Ready when you are",
      status_checking: "Checking",
      status_ready: "Ready",
      status_attention: "Needs attention",
      setup_eyebrow: "First-run setup",
      footer: "FigureSmith is independent open-source software based on AutoFigure-Edit.",
      python: "Python",
      python_ready: "Service environment ready",
      python_missing: "Service packages missing",
      model_env: "Model environment",
      model_env_ready: "Model packages detected",
      model_env_missing: "Model packages missing",
      gpu: "GPU",
      models: "Model files",
      dependencies: "Environment packages",
      dependency_title: "User-managed Python environment",
      install_hint: "Install the missing packages in the selected environment:",
      copy_command: "Copy install command",
      copied: "Copied",
      external_python: "Using the isolated FigureSmith environment",
      environment: "Environment",
      environment_path: "Environment path",
      isolated_environment: "Isolated user environment",
      base_python: "Existing Python is used only as the base",
      refresh_failed: "Status refresh failed",
      no_missing: "No missing packages detected",
      sam3_install_hint: "SAM3 is installed separately from its upstream project after the model packages are ready.",
      importing_model: "Importing and verifying model files...",
      import_complete: "Model files imported and verified",
      model_path: "Local path",
      model_not_imported: "No local model files imported yet.",
    },
    zh: {
      tagline: "本地科研插图桌面端",
      eyebrow: "本地科研插图工作台",
      title: "欢迎使用 FigureSmith / 图匠",
      subtitle: "先确认已选 Python 环境，再按需导入本地模型文件。",
      start: "检查环境",
      skip: "稍后处理",
      goto_create: "进入创建",
      back: "上一步",
      next: "下一步",
      skip_step: "跳过此步",
      finish: "完成",
      step_env: "运行环境",
      step_env_copy: "FigureSmith 使用你本机的 Python。先检查服务包，再查看模型包和 GPU 支持。",
      step_sam3: "导入 SAM3",
      step_sam3_copy: "导入本地 SAM3 权重。不提供远程模型下载。",
      step_rmbg: "导入 RMBG",
      step_rmbg_copy: "导入本地 RMBG-2.0 ZIP 或模型目录。",
      step_provider: "生成服务",
      step_provider_copy: "Provider Key 保留在创建页会话中，不会新增写入 settings.json。",
      step_done: "完成",
      step_done_copy: "工作区已配置。Python 或模型环境变化后，可以随时回到这里检查。",
      refresh: "刷新状态",
      import_desktop: "选择文件",
      import_models_page: "打开模型页",
      gpu_ok: "CUDA GPU 已就绪",
      gpu_missing: "未检测到 CUDA GPU",
      sam3_ok: "SAM3 已就绪",
      sam3_missing: "尚未导入 SAM3",
      rmbg_ok: "RMBG 已就绪",
      rmbg_missing: "尚未导入 RMBG",
      offline_on: "严格离线已开启",
      mark_done: "完成配置",
      provider_note: "进入创建页，为本次会话配置生成服务。",
      loading: "正在检查工作区...",
      error: "无法加载工作区状态",
      status_eyebrow: "工作区状态",
      status_title: "准备就绪",
      status_checking: "检查中",
      status_ready: "已就绪",
      status_attention: "需要处理",
      setup_eyebrow: "首次配置",
      footer: "FigureSmith / 图匠是基于 AutoFigure-Edit 的独立开源软件。",
      python: "Python",
      python_ready: "服务环境已就绪",
      python_missing: "缺少服务包",
      model_env: "模型环境",
      model_env_ready: "已检测到模型包",
      model_env_missing: "缺少模型包",
      gpu: "GPU",
      models: "模型文件",
      dependencies: "环境包",
      dependency_title: "用户管理的 Python 环境",
      install_hint: "请在当前选中的环境中安装缺少的包：",
      copy_command: "复制安装命令",
      copied: "已复制",
      external_python: "使用 FigureSmith 独立环境",
      environment: "环境",
      environment_path: "环境目录",
      isolated_environment: "用户目录中的独立环境",
      base_python: "现有 Python 仅作为创建基座",
      refresh_failed: "刷新状态失败",
      no_missing: "未发现缺少的包",
      sam3_install_hint: "模型包就绪后，还需要根据模型版本从 SAM3 上游项目单独安装。",
      importing_model: "正在导入并校验模型文件...",
      import_complete: "模型文件已导入并校验",
      model_path: "本地路径",
      model_not_imported: "还没有导入本地模型文件。",
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
  var statusRequest = null;
  var stepIndex = 0;
  var STEPS = ["env", "sam3", "rmbg", "provider", "done"];

  var wizardPanel = document.getElementById("wizardPanel");
  var stepTitle = document.getElementById("stepTitle");
  var stepCopy = document.getElementById("stepCopy");
  var stepCounter = document.getElementById("stepCounter");
  var stepList = document.getElementById("stepList");
  var stepBody = document.getElementById("stepBody");
  var stepAlert = document.getElementById("stepAlert");
  var progress = document.getElementById("wizardProgress");
  var progressWrap = document.querySelector(".fs-progress[role=progressbar]");
  var btnStart = document.getElementById("btnStart");
  var btnSkip = document.getElementById("btnSkip");
  var btnBack = document.getElementById("btnBack");
  var btnNext = document.getElementById("btnNext");
  var btnSkipStep = document.getElementById("btnSkipStep");
  var setupSummary = document.getElementById("setupSummary");
  var setupBadge = document.getElementById("setupBadge");
  var setupHint = document.getElementById("setupHint");

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

  async function loadStatus(force) {
    if (!force && status) return status;
    if (statusRequest) return statusRequest;
    statusRequest = FS.api("/api/system/status")
      .then(function (value) {
        status = value || {};
        renderSummary(status);
        return status;
      })
      .finally(function () {
        statusRequest = null;
      });
    return statusRequest;
  }

  async function refreshStatus() {
    try {
      await loadStatus(true);
      renderCurrentStep();
    } catch (err) {
      showAlert(t("refresh_failed") + ": " + (err.message || err), "bad");
    }
  }

  async function markOnboarding(completed) {
    await FS.api("/api/system/onboarding", {
      method: "POST",
      body: { completed: !!completed },
    });
  }

  function statusCard(label, value, kind) {
    var card = document.createElement("div");
    card.className = "fs-status-card";
    var labelEl = document.createElement("div");
    labelEl.className = "fs-status-card-label";
    labelEl.textContent = label;
    var valueEl = document.createElement("div");
    valueEl.className = "fs-status-card-value" + (kind ? " " + kind : "");
    valueEl.textContent = value;
    card.appendChild(labelEl);
    card.appendChild(valueEl);
    return card;
  }

  function dependencyState(s) {
    var deps = s.dependencies || {};
    var missingBootstrap = deps.missing_bootstrap || [];
    var missingModels = deps.missing_models || [];
    return {
      deps: deps,
      bootstrapReady: deps.bootstrap_ready !== false && missingBootstrap.length === 0,
      modelsReady: deps.models_ready !== false && missingModels.length === 0,
      missingBootstrap: missingBootstrap,
      missingModels: missingModels,
    };
  }

  function renderSummary(s) {
    if (!setupSummary) return;
    var state = dependencyState(s);
    var ready = state.bootstrapReady;
    setupSummary.innerHTML = "";
    setupSummary.appendChild(
      statusCard(
        t("python"),
        state.bootstrapReady ? (s.python || "Python") : t("python_missing"),
        state.bootstrapReady ? "ok" : "bad"
      )
    );
    setupSummary.appendChild(
      statusCard(
        t("model_env"),
        state.modelsReady ? t("model_env_ready") : t("model_env_missing"),
        state.modelsReady ? "ok" : "warn"
      )
    );
    setupSummary.appendChild(
      statusCard(
        t("gpu"),
        s.gpu_available ? s.gpu_name || t("gpu_ok") : t("gpu_missing"),
        s.gpu_available ? "ok" : "warn"
      )
    );
    setupSummary.appendChild(
      statusCard(
        t("models"),
        s.sam3_loaded && s.rmbg_loaded ? "SAM3 + RMBG" : t("sam3_missing"),
        s.sam3_loaded && s.rmbg_loaded ? "ok" : "warn"
      )
    );
    if (setupBadge) {
      setupBadge.textContent = ready ? t("status_ready") : t("status_attention");
      setupBadge.className = "fs-badge " + (ready ? "ok" : "warn");
    }
    if (setupHint) {
      setupHint.textContent = ready
        ? state.modelsReady
          ? (state.deps.managed_environment ? t("external_python") : t("base_python"))
          : t("model_env_missing")
        : t("python_missing");
    }
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
      row.setAttribute("role", "listitem");
      if (idx === stepIndex) row.classList.add("is-current");
      if (idx < stepIndex) row.classList.add("is-done");
      var number = document.createElement("span");
      number.className = "fs-step-num";
      number.textContent = idx < stepIndex ? "✓" : String(idx + 1);
      var label = document.createElement("strong");
      label.textContent = labels[id];
      row.appendChild(number);
      row.appendChild(label);
      stepList.appendChild(row);
    });
    if (progress) progress.style.width = Math.round(((stepIndex + 1) / STEPS.length) * 100) + "%";
    if (progressWrap) progressWrap.setAttribute("aria-valuenow", String(Math.round(((stepIndex + 1) / STEPS.length) * 100)));
    if (stepCounter) stepCounter.textContent = stepIndex + 1 + " / " + STEPS.length;
  }

  function appendKv(parent, label, value) {
    var row = document.createElement("div");
    row.className = "fs-status-row";
    var name = document.createElement("span");
    name.textContent = label;
    var val = document.createElement("strong");
    val.textContent = value;
    row.appendChild(name);
    row.appendChild(val);
    parent.appendChild(row);
  }

  function addButton(parent, text, className, handler) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "fs-btn" + (className ? " " + className : "");
    button.textContent = text;
    button.addEventListener("click", handler);
    parent.appendChild(button);
    return button;
  }

  function renderEnvBody() {
    var s = status || {};
    var state = dependencyState(s);
    var deps = state.deps;
    stepBody.innerHTML = "";

    var grid = document.createElement("div");
    grid.className = "fs-status-detail";
    appendKv(grid, t("python"), s.python || "?");
    appendKv(grid, t("environment"), deps.managed_environment ? t("isolated_environment") : t("base_python"));
    appendKv(grid, t("environment_path"), deps.managed_environment_root || "?");
    appendKv(grid, "Executable", s.python_executable || "?");
    appendKv(grid, "Service", state.bootstrapReady ? t("python_ready") : t("python_missing"));
    appendKv(grid, t("gpu"), s.gpu_available ? s.gpu_name || t("gpu_ok") : t("gpu_missing"));
    appendKv(grid, "CUDA", s.cuda_version || "-");
    appendKv(grid, t("models"), s.sam3_loaded && s.rmbg_loaded ? "SAM3 + RMBG" : t("sam3_missing"));
    stepBody.appendChild(grid);

    var panel = document.createElement("div");
    panel.className = "fs-dependency-panel";
    var heading = document.createElement("h3");
    heading.textContent = t("dependency_title");
    panel.appendChild(heading);
    var missing = state.missingBootstrap.concat(state.missingModels);
    if (!missing.length) {
      var good = document.createElement("p");
      good.className = "fs-muted";
      good.textContent = t("no_missing");
      panel.appendChild(good);
    } else {
      var copy = document.createElement("p");
      copy.className = "fs-muted";
      copy.textContent = t("install_hint");
      panel.appendChild(copy);
      var list = document.createElement("div");
      list.className = "fs-missing-list";
      missing.forEach(function (name) {
        var item = document.createElement("span");
        item.className = "fs-badge warn";
        item.textContent = name;
        list.appendChild(item);
      });
      panel.appendChild(list);
      var command = document.createElement("code");
      command.className = "fs-command";
      command.textContent = deps.install_command || "python -m pip install -r requirements-runtime.txt";
      panel.appendChild(command);
      if (state.missingModels.indexOf("sam3") !== -1) {
        var sam3Note = document.createElement("p");
        sam3Note.className = "fs-muted fs-dependency-note";
        sam3Note.textContent = t("sam3_install_hint");
        panel.appendChild(sam3Note);
      }
      var actions = document.createElement("div");
      actions.className = "fs-btn-row";
      addButton(actions, t("copy_command"), "", async function () {
        try {
          await navigator.clipboard.writeText(command.textContent);
          this.textContent = t("copied");
          setTimeout(function () { if (document.body.contains(actions)) renderCurrentStep(); }, 1200);
        } catch (_err) {
          showAlert(command.textContent, "warn");
        }
      });
      panel.appendChild(actions);
    }
    stepBody.appendChild(panel);

    var actions = document.createElement("div");
    actions.className = "fs-btn-row";
    addButton(actions, t("refresh"), "", refreshStatus);
    stepBody.appendChild(actions);

    if (!state.bootstrapReady) {
      showAlert(
        FS.getLocale() === "zh"
          ? "当前 Python 不能启动 FigureSmith 服务，请先安装服务包。"
          : "The selected Python cannot start FigureSmith yet. Install the service packages first.",
        "bad"
      );
    } else if (!state.modelsReady || !s.gpu_available) {
      showAlert(
        FS.getLocale() === "zh"
          ? "编辑器可以使用；模型推理环境仍需要按需准备。"
          : "The editor is available; the model inference environment still needs attention.",
        "warn"
      );
    } else {
      showAlert("", null);
    }
  }

  function modelRecord(kind) {
    var models = status && status.models && status.models.models;
    if (!Array.isArray(models)) return null;
    var id = kind === "sam3" ? "sam3" : "rmbg-2.0";
    return models.find(function (item) {
      return item && (item.id === id || String(item.id || "").toLowerCase().indexOf(kind) !== -1);
    }) || null;
  }

  function renderImportBody(kind) {
    var model = modelRecord(kind);
    var installed = model ? !!model.installed : (kind === "sam3" ? status && status.sam3_loaded : status && status.rmbg_loaded);
    stepBody.innerHTML = "";
    var panel = document.createElement("div");
    panel.className = "fs-import-panel";
    var copy = document.createElement("div");
    var heading = document.createElement("h3");
    heading.textContent = kind === "sam3" ? "SAM3" : "RMBG";
    var note = document.createElement("p");
    note.className = "fs-muted";
    note.textContent = installed ? (kind === "sam3" ? t("sam3_ok") : t("rmbg_ok")) : (kind === "sam3" ? t("sam3_missing") : t("rmbg_missing"));
    copy.appendChild(heading);
    copy.appendChild(note);

    var filePanel = document.createElement("div");
    filePanel.className = "fs-model-file";
    var fileState = document.createElement("strong");
    fileState.className = installed ? "ok" : "warn";
    fileState.textContent = installed ? (kind === "sam3" ? t("sam3_ok") : t("rmbg_ok")) : t("model_not_imported");
    filePanel.appendChild(fileState);
    var filePath = model && (model.path || model.directory);
    if (filePath) {
      var pathLabel = document.createElement("span");
      pathLabel.textContent = t("model_path");
      filePanel.appendChild(pathLabel);
      var pathValue = document.createElement("code");
      pathValue.className = "fs-model-path";
      pathValue.textContent = filePath;
      filePanel.appendChild(pathValue);
    }
    copy.appendChild(filePanel);

    var importProgress = document.createElement("div");
    importProgress.className = "fs-import-progress";
    importProgress.hidden = true;
    var importBar = document.createElement("span");
    importBar.className = "fs-import-progress-bar";
    var importLabel = document.createElement("span");
    importLabel.className = "fs-import-progress-label";
    importProgress.appendChild(importBar);
    importProgress.appendChild(importLabel);
    copy.appendChild(importProgress);
    panel.appendChild(copy);

    var actions = document.createElement("div");
    actions.className = "fs-btn-row";
    if (FS.isDesktop()) {
      addButton(actions, t("import_desktop"), "primary", async function () {
        var button = this;
        importProgress.hidden = false;
        importProgress.classList.remove("is-complete", "is-error");
        importLabel.textContent = t("importing_model");
        button.disabled = true;
        try {
          if (kind === "sam3") {
            await FS.tauriInvoke("import_sam3_model", {});
          } else {
            try {
              await FS.tauriInvoke("import_rmbg_archive", {});
            } catch (err) {
              if (String(err).toLowerCase().indexOf("cancel") !== -1) throw err;
              await FS.tauriInvoke("import_rmbg_folder", {});
            }
          }
          importProgress.classList.add("is-complete");
          importLabel.textContent = t("import_complete");
          await loadStatus(true);
          renderCurrentStep();
        } catch (err) {
          if (String(err).toLowerCase().indexOf("cancel") === -1) {
            importProgress.classList.add("is-error");
            importLabel.textContent = String(err.message || err);
            showAlert(String(err.message || err), "bad");
          } else {
            importProgress.hidden = true;
          }
        } finally {
          button.disabled = false;
        }
      });
    }
    var modelsLink = document.createElement("a");
    modelsLink.className = "fs-btn";
    modelsLink.href = "/models.html";
    modelsLink.textContent = t("import_models_page");
    actions.appendChild(modelsLink);
    addButton(actions, t("refresh"), "", refreshStatus);
    panel.appendChild(actions);
    stepBody.appendChild(panel);
    showAlert(installed ? (kind === "sam3" ? t("sam3_ok") : t("rmbg_ok")) : "", installed ? "ok" : null);
  }

  function renderProviderBody() {
    stepBody.innerHTML = "";
    var note = document.createElement("p");
    note.className = "fs-muted";
    note.textContent = t("provider_note");
    stepBody.appendChild(note);
    var actions = document.createElement("div");
    actions.className = "fs-btn-row";
    var link = document.createElement("a");
    link.className = "fs-btn primary";
    link.href = "/";
    link.textContent = t("goto_create");
    actions.appendChild(link);
    stepBody.appendChild(actions);
    showAlert("", null);
  }

  function renderDoneBody() {
    stepBody.innerHTML = "";
    var actions = document.createElement("div");
    actions.className = "fs-btn-row";
    addButton(actions, t("mark_done"), "primary", async function () {
      try {
        await markOnboarding(true);
        window.location.href = "/";
      } catch (err) {
        showAlert(String(err.message || err), "bad");
      }
    });
    var create = document.createElement("a");
    create.className = "fs-btn";
    create.href = "/";
    create.textContent = t("goto_create");
    actions.appendChild(create);
    var models = document.createElement("a");
    models.className = "fs-btn";
    models.href = "/models.html";
    models.textContent = t("import_models_page");
    actions.appendChild(models);
    stepBody.appendChild(actions);
    showAlert("", null);
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
    stepIndex = typeof startAt === "number" ? startAt : 0;
    try {
      await loadStatus();
      renderCurrentStep();
      stepTitle.focus();
    } catch (err) {
      showAlert(t("error") + ": " + (err.message || err), "bad");
    }
  }

  btnStart.addEventListener("click", function () { openWizard(0); });
  btnSkip.addEventListener("click", async function () {
    try { await markOnboarding(true); } catch (_err) {}
    window.location.href = "/";
  });
  btnBack.addEventListener("click", function () {
    if (stepIndex > 0) { stepIndex -= 1; renderCurrentStep(); }
  });
  btnSkipStep.addEventListener("click", function () {
    if (stepIndex < STEPS.length - 1) { stepIndex += 1; renderCurrentStep(); }
  });
  btnNext.addEventListener("click", async function () {
    if (stepIndex >= STEPS.length - 1) {
      try { await markOnboarding(true); window.location.href = "/"; }
      catch (err) { showAlert(String(err.message || err), "bad"); }
      return;
    }
    stepIndex += 1;
    renderCurrentStep();
  });

  applyStaticI18n();
  loadStatus()
    .then(function (s) {
      if (!s || !s.onboarding_completed) openWizard(0);
    })
    .catch(function (err) {
      if (setupHint) setupHint.textContent = t("error");
      showAlert(String(err.message || err), "bad");
    });
})();
