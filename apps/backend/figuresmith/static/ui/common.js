/**
 * FigureSmith shared UI helpers (Phase 5).
 * Auth: relies on /figuresmith-bridge.js when window.__FIGURESMITH__ is set.
 */
(function (global) {
  "use strict";

  var FS = global.FigureSmithUI || {};

  FS.isDesktop = function () {
    try {
      return !!(
        global.__TAURI__ ||
        (global.__TAURI_INTERNALS__ && global.__TAURI_INTERNALS__.invoke) ||
        (global.__FIGURESMITH__ && global.__FIGURESMITH__.desktop)
      );
    } catch (_e) {
      return false;
    }
  };

  FS.getLocale = function () {
    try {
      var stored = global.localStorage.getItem("autofigure_locale_v1");
      if (stored === "zh" || stored === "en") return stored;
    } catch (_e) {}
    var lang = (navigator.language || "").toLowerCase();
    return lang.indexOf("zh") === 0 ? "zh" : "en";
  };

  FS.setLocale = function (locale) {
    if (locale !== "zh" && locale !== "en") return;
    try {
      global.localStorage.setItem("autofigure_locale_v1", locale);
    } catch (_e) {}
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  };

  FS.t = function (dict, key) {
    var locale = FS.getLocale();
    var table = (dict && dict[locale]) || (dict && dict.en) || {};
    return table[key] != null ? table[key] : key;
  };

  FS.authHeaders = function (extra) {
    var headers = Object.assign({ Accept: "application/json" }, extra || {});
    try {
      var session = global.__FIGURESMITH__;
      if (session && session.token && !headers.Authorization) {
        headers.Authorization = "Bearer " + session.token;
      }
    } catch (_e) {}
    return headers;
  };

  FS.api = async function (path, options) {
    options = options || {};
    var init = {
      method: options.method || "GET",
      headers: FS.authHeaders(options.headers || {}),
    };
    if (options.body != null) {
      init.headers["Content-Type"] = "application/json";
      init.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
    }
    var res = await fetch(path, init);
    var text = await res.text();
    var data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (_e) {
      data = { raw: text };
    }
    if (!res.ok) {
      var err = new Error((data && (data.detail && data.detail.message)) || text || res.statusText);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  };

  FS.tauriInvoke = async function (cmd, args) {
    // Tauri 2: window.__TAURI__.core.invoke
    var invoke =
      (global.__TAURI__ && global.__TAURI__.core && global.__TAURI__.core.invoke) ||
      (global.__TAURI_INTERNALS__ && global.__TAURI_INTERNALS__.invoke) ||
      null;
    if (!invoke) {
      throw new Error("Tauri invoke unavailable (open in desktop app)");
    }
    return invoke(cmd, args || {});
  };

  FS.ensureBridge = function () {
    if (global.__FIGURESMITH_BRIDGE_INSTALLED__) return;
    try {
      var s = document.createElement("script");
      s.src = "/figuresmith-bridge.js";
      s.async = false;
      document.head.appendChild(s);
    } catch (_e) {}
  };

  FS.renderNav = function (active) {
    var nav = document.querySelector("[data-fs-nav]");
    if (!nav) return;
    var locale = FS.getLocale();
    var labels =
      locale === "zh"
        ? {
            welcome: "欢迎",
            create: "创建",
            import: "导入图",
            models: "模型",
            history: "历史",
            guide: "指南",
          }
        : {
            welcome: "Welcome",
            create: "Create",
            import: "Import",
            models: "Models",
            history: "History",
            guide: "Guide",
          };
    var items = [
      ["welcome", "/welcome.html", labels.welcome],
      ["create", "/", labels.create],
      ["import", "/import.html", labels.import],
      ["models", "/models.html", labels.models],
      ["history", "/history.html", labels.history],
      ["guide", "/guide.html", labels.guide],
    ];
    nav.innerHTML = "";
    items.forEach(function (it) {
      var a = document.createElement("a");
      a.href = it[1];
      a.textContent = it[2];
      if (it[0] === active) a.className = "is-active";
      nav.appendChild(a);
    });
    var langWrap = document.createElement("span");
    langWrap.style.display = "inline-flex";
    langWrap.style.gap = "6px";
    ["zh", "en"].forEach(function (code) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "fs-chip" + (FS.getLocale() === code ? " is-active" : "");
      b.textContent = code === "zh" ? "中文" : "EN";
      b.addEventListener("click", function () {
        FS.setLocale(code);
        global.location.reload();
      });
      langWrap.appendChild(b);
    });
    nav.appendChild(langWrap);
  };

  global.FigureSmithUI = FS;
})(window);
