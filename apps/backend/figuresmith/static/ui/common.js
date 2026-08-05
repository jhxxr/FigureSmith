/**
 * FigureSmith shared UI helpers (Phase 5).
 * Auth: the desktop document-start bridge owns credential attachment. Browser
 * development remains anonymous when the backend auth bypass is enabled.
 */
(function (global) {
  "use strict";

  var FS = global.FigureSmithUI || {};
  var THEME_KEY = "figuresmith_theme_v1";
  var THEME_VALUES = { light: true, dark: true, system: true };
  var mediaQuery = null;
  var mediaHandler = null;

  FS.isDesktop = function () {
    try {
      return !!(
        global.__TAURI__ ||
        (global.__TAURI_INTERNALS__ && global.__TAURI_INTERNALS__.invoke) ||
        global.__FIGURESMITH_DESKTOP_READY__
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

  FS.getThemePreference = function () {
    try {
      var stored = global.localStorage.getItem(THEME_KEY);
      if (stored && THEME_VALUES[stored]) return stored;
    } catch (_e) {}
    return "system";
  };

  FS.resolveTheme = function (pref) {
    var preference = pref || FS.getThemePreference();
    if (preference === "light" || preference === "dark") return preference;
    try {
      if (global.matchMedia && global.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
    } catch (_e) {}
    return "light";
  };

  function detachSystemListener() {
    if (mediaQuery && mediaHandler) {
      try {
        if (mediaQuery.removeEventListener) {
          mediaQuery.removeEventListener("change", mediaHandler);
        } else if (mediaQuery.removeListener) {
          mediaQuery.removeListener(mediaHandler);
        }
      } catch (_e) {}
    }
    mediaQuery = null;
    mediaHandler = null;
  }

  function attachSystemListener() {
    detachSystemListener();
    if (!global.matchMedia) return;
    try {
      mediaQuery = global.matchMedia("(prefers-color-scheme: dark)");
      mediaHandler = function () {
        if (FS.getThemePreference() === "system") {
          FS.applyTheme();
        }
      };
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener("change", mediaHandler);
      } else if (mediaQuery.addListener) {
        mediaQuery.addListener(mediaHandler);
      }
    } catch (_e) {
      mediaQuery = null;
      mediaHandler = null;
    }
  }

  FS.applyTheme = function () {
    var preference = FS.getThemePreference();
    var resolved = FS.resolveTheme(preference);
    var root = document.documentElement;
    root.setAttribute("data-theme", resolved);
    root.setAttribute("data-theme-preference", preference);
    root.style.colorScheme = resolved;
    if (preference === "system") {
      attachSystemListener();
    } else {
      detachSystemListener();
    }
    var mounts = document.querySelectorAll("[data-fs-theme-switch]");
    for (var i = 0; i < mounts.length; i++) {
      FS.renderThemeSwitch(mounts[i]);
    }
    return resolved;
  };

  FS.setThemePreference = function (pref) {
    var next = THEME_VALUES[pref] ? pref : "system";
    try {
      global.localStorage.setItem(THEME_KEY, next);
    } catch (_e) {}
    return FS.applyTheme();
  };

  FS.renderThemeSwitch = function (container) {
    if (!container) return;
    var locale = FS.getLocale();
    var preference = FS.getThemePreference();
    var labels =
      locale === "zh"
        ? { light: "浅色", dark: "深色", system: "系统" }
        : { light: "Light", dark: "Dark", system: "System" };
    var options = ["light", "dark", "system"];
    container.setAttribute("data-fs-theme-switch", "");
    container.classList.add("fs-theme-switch");
    container.innerHTML = "";
    options.forEach(function (code) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "fs-chip" + (preference === code ? " is-active" : "");
      b.setAttribute("data-theme-option", code);
      b.setAttribute("aria-pressed", preference === code ? "true" : "false");
      b.textContent = labels[code];
      b.addEventListener("click", function () {
        FS.setThemePreference(code);
      });
      container.appendChild(b);
    });
  };

  FS.authHeaders = function (extra) {
    return Object.assign({ Accept: "application/json" }, extra || {});
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
    langWrap.className = "fs-lang-switch";
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

    var themeWrap = document.createElement("span");
    themeWrap.setAttribute("data-fs-theme-switch", "");
    themeWrap.className = "fs-theme-switch";
    themeWrap.style.display = "inline-flex";
    themeWrap.style.gap = "6px";
    nav.appendChild(themeWrap);
    FS.renderThemeSwitch(themeWrap);
  };

  global.FigureSmithUI = FS;

  function bootTheme() {
    FS.applyTheme();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootTheme);
  } else {
    bootTheme();
  }
})(window);
