(function () {
  "use strict";

  var FS = window.FigureSmithUI;
  FS.ensureBridge();
  FS.renderNav("models");

  var I18N = {
    en: {
      tagline: "Local model manager",
      title: "Model management",
      subtitle:
        "Import, verify, and remove local SAM3 / RMBG packs. Desktop app uses native file pickers; browser mode can import by absolute path for development only.",
      refresh: "Refresh",
      open_dir: "Open models folder",
      browser_import_title: "Browser / advanced path import",
      browser_import_copy:
        "Available when the desktop shell is not detected. Provide an absolute local path already reachable by the Python backend process.",
      import_sam3: "Import SAM3",
      import_rmbg: "Import RMBG",
      verify: "Verify",
      delete: "Delete",
      installed: "Installed",
      missing: "Not installed",
      desktop_import: "Import (desktop)",
      importing: "Importing and verifying model files...",
      import_complete: "Import and verification complete",
      desktop_only: "Use the FigureSmith desktop app to pick files, or the path import below.",
      confirmed_delete: "Delete this model pack?",
      gpu_missing_title: "GPU notice",
      paths: "Paths",
      app_data: "App data",
    },
    zh: {
      tagline: "本地模型管理",
      title: "模型管理",
      subtitle:
        "导入、校验与删除本地 SAM3 / RMBG。桌面端使用系统文件选择器；浏览器开发模式可用绝对路径导入。",
      refresh: "刷新",
      open_dir: "打开模型目录",
      browser_import_title: "浏览器 / 高级路径导入",
      browser_import_copy:
        "未检测到桌面壳时可用。请填写 Python 后端进程可访问的本地绝对路径。",
      import_sam3: "导入 SAM3",
      import_rmbg: "导入 RMBG",
      verify: "校验",
      delete: "删除",
      installed: "已安装",
      missing: "未安装",
      desktop_import: "导入（桌面）",
      importing: "正在导入并校验模型文件...",
      import_complete: "导入并校验完成",
      desktop_only: "请使用 FigureSmith 桌面端选择文件，或使用下方路径导入。",
      confirmed_delete: "确认删除该模型包？",
      gpu_missing_title: "GPU 提示",
      paths: "路径",
      app_data: "应用数据",
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

  var modelCards = document.getElementById("modelCards");
  var systemSummary = document.getElementById("systemSummary");
  var gpuAlert = document.getElementById("gpuAlert");
  var pageMsg = document.getElementById("pageMsg");
  var browserImport = document.getElementById("browserImport");
  var status = null;
  var models = null;

  function showMsg(text, kind) {
    if (!text) {
      pageMsg.hidden = true;
      pageMsg.textContent = "";
      return;
    }
    pageMsg.hidden = false;
    pageMsg.className = "fs-alert" + (kind ? " " + kind : "");
    pageMsg.textContent = text;
  }

  function findModel(idPart) {
    var list = (models && models.models) || [];
    for (var i = 0; i < list.length; i++) {
      var m = list[i];
      if (!m) continue;
      var id = String(m.id || "").toLowerCase();
      if (id.indexOf(idPart) !== -1) return m;
    }
    return null;
  }

  function renderSummary() {
    var s = status || {};
    systemSummary.innerHTML = "";
    function row(k, v) {
      var div = document.createElement("div");
      div.className = "fs-status-row";
      div.innerHTML = "<span>" + k + "</span><span>" + v + "</span>";
      systemSummary.appendChild(div);
    }
    row("FigureSmith", s.version || "");
    row(
      "GPU",
      s.gpu_available ? s.gpu_name || "CUDA" : FS.getLocale() === "zh" ? "不可用" : "unavailable"
    );
    row(t("app_data"), '<span class="fs-mono">' + (s.app_data_dir || models.app_data_dir || "") + "</span>");
    // fix: row uses text; set carefully
    systemSummary.lastChild.querySelector("span:last-child").textContent =
      s.app_data_dir || (models && models.app_data_dir) || "";
    systemSummary.lastChild.querySelector("span:last-child").className = "fs-mono";

    if (!s.gpu_available) {
      gpuAlert.hidden = false;
      gpuAlert.textContent =
        FS.getLocale() === "zh"
          ? (s.messages && s.messages.gpu_missing_zh) || t("gpu_missing_title")
          : (s.messages && s.messages.gpu_missing_en) || t("gpu_missing_title");
    } else {
      gpuAlert.hidden = true;
    }
  }

  function cardHtml(model, kind) {
    var installed = !!(model && model.installed);
    var title = (model && model.display_name) || kind.toUpperCase();
    var path = (model && (model.path || model.directory)) || "";
    var badge = installed
      ? '<span class="fs-badge ok">' + t("installed") + "</span>"
      : '<span class="fs-badge bad">' + t("missing") + "</span>";
    var html = '<section class="fs-card fs-model-card" data-kind="' + kind + '">';
    html += "<h3>" + title + " " + badge + "</h3>";
    html += '<div class="fs-model-meta">';
    html += "<div>ID: <code>" + ((model && model.id) || kind) + "</code></div>";
    if (model && model.sha256) html += "<div>SHA-256: <code>" + model.sha256 + "</code></div>";
    if (model && model.size_bytes != null)
      html += "<div>Size: " + model.size_bytes + " bytes</div>";
    if (model && model.verified != null)
      html += "<div>Verified: " + (model.verified ? "yes" : "no") + "</div>";
    html +=
      '<div class="fs-path-box fs-mono">' +
      (path || "—") +
      "</div></div>";
    html +=
      '<div class="fs-model-transfer" data-transfer hidden><span class="fs-model-transfer-bar"></span><span data-transfer-label></span></div>';
    html += '<div class="fs-btn-row">';
    if (FS.isDesktop()) {
      html +=
        '<button type="button" class="fs-btn primary" data-act="desktop-import">' +
        t("desktop_import") +
        "</button>";
    }
    html +=
      '<button type="button" class="fs-btn" data-act="verify">' + t("verify") + "</button>";
    html +=
      '<button type="button" class="fs-btn danger" data-act="delete">' + t("delete") + "</button>";
    html += "</div></section>";
    return html;
  }

  function renderCards() {
    var sam3 = findModel("sam3");
    var rmbg = findModel("rmbg");
    modelCards.innerHTML = cardHtml(sam3, "sam3") + cardHtml(rmbg, "rmbg");
    modelCards.querySelectorAll(".fs-model-card").forEach(function (card) {
      var kind = card.getAttribute("data-kind");
      card.querySelectorAll("[data-act]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          handleAction(kind, btn.getAttribute("data-act"), btn);
        });
      });
    });
  }

  async function handleAction(kind, act, btn) {
    var card = btn && btn.closest ? btn.closest(".fs-model-card") : null;
    var transfer = card && card.querySelector("[data-transfer]");
    var transferLabel = transfer && transfer.querySelector("[data-transfer-label]");
    try {
      if (btn) btn.disabled = true;
      showMsg("", null);
      if (act === "desktop-import") {
        if (transfer) {
          transfer.hidden = false;
          transfer.classList.remove("is-complete", "is-error");
        }
        if (transferLabel) transferLabel.textContent = t("importing");
        showMsg(t("importing"), "warn");
        if (kind === "sam3") {
          await FS.tauriInvoke("import_sam3_model", {});
        } else {
          try {
            await FS.tauriInvoke("import_rmbg_archive", {});
          } catch (err) {
            if (String(err).indexOf("cancelled") !== -1) throw err;
            await FS.tauriInvoke("import_rmbg_folder", {});
          }
        }
        if (transfer) transfer.classList.add("is-complete");
        if (transferLabel) transferLabel.textContent = t("import_complete");
        showMsg(t("import_complete"), "ok");
      } else if (act === "verify") {
        var vpath = kind === "sam3" ? "/api/models/sam3/verify" : "/api/models/rmbg/verify";
        await FS.api(vpath, { method: "POST" });
        showMsg("Verify OK", "ok");
      } else if (act === "delete") {
        if (!window.confirm(t("confirmed_delete"))) return;
        var dpath = kind === "sam3" ? "/api/models/sam3" : "/api/models/rmbg";
        await FS.api(dpath, { method: "DELETE" });
        showMsg("Deleted", "ok");
      }
      await refresh();
    } catch (err) {
      if (transfer && act === "desktop-import") transfer.classList.add("is-error");
      if (transferLabel && act === "desktop-import") transferLabel.textContent = String(err.message || err);
      if (String(err).indexOf("cancelled") !== -1) return;
      var detail =
        (err.data && err.data.detail && (err.data.detail.message_en || err.data.detail.message)) ||
        err.message ||
        String(err);
      showMsg(detail, "bad");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function refresh() {
    status = await FS.api("/api/system/status");
    models = status.models || (await FS.api("/api/models"));
    renderSummary();
    renderCards();
  }

  document.getElementById("btnRefresh").addEventListener("click", function () {
    refresh().catch(function (err) {
      showMsg(String(err.message || err), "bad");
    });
  });

  document.getElementById("btnOpenDir").addEventListener("click", async function () {
    try {
      if (FS.isDesktop()) {
        var path = await FS.tauriInvoke("open_models_directory", {});
        showMsg(String(path || "opened"), "ok");
      } else {
        var paths = await FS.api("/api/models/paths");
        showMsg((paths && (paths.models_root || paths.app_data_dir)) || t("desktop_only"), "ok");
      }
    } catch (err) {
      showMsg(String(err.message || err), "bad");
    }
  });

  if (!FS.isDesktop()) {
    browserImport.hidden = false;
    document.getElementById("btnImportSam3Path").addEventListener("click", async function () {
      var p = document.getElementById("sam3Path").value.trim();
      if (!p) return;
      try {
        await FS.api("/api/models/sam3/import", {
          method: "POST",
          body: { source_path: p },
        });
        showMsg("SAM3 import OK", "ok");
        await refresh();
      } catch (err) {
        var detail =
          (err.data && err.data.detail && (err.data.detail.message_en || err.data.detail.message)) ||
          err.message ||
          String(err);
        showMsg(detail, "bad");
      }
    });
    document.getElementById("btnImportRmbgPath").addEventListener("click", async function () {
      var p = document.getElementById("rmbgPath").value.trim();
      if (!p) return;
      try {
        await FS.api("/api/models/rmbg/import", {
          method: "POST",
          body: { source_path: p, kind: "auto" },
        });
        showMsg("RMBG import OK", "ok");
        await refresh();
      } catch (err) {
        var detail =
          (err.data && err.data.detail && (err.data.detail.message_en || err.data.detail.message)) ||
          err.message ||
          String(err);
        showMsg(detail, "bad");
      }
    });
  }

  applyStaticI18n();
  refresh().catch(function (err) {
    showMsg(String(err.message || err), "bad");
  });
})();
