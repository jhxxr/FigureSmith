/**
 * FigureSmith desktop bridge (Phase 4).
 *
 * When the Tauri shell injects window.__FIGURESMITH__ = { token, port, apiBase },
 * this script wraps window.fetch so vendor UI calls to /api/* include
 * Authorization: Bearer <token>, and wraps EventSource to pass fs_token on
 * /api/events/* only. Token is never written to localStorage.
 */
(function () {
  "use strict";

  if (window.__FIGURESMITH_BRIDGE_INSTALLED__) {
    return;
  }
  window.__FIGURESMITH_BRIDGE_INSTALLED__ = true;

  var originalFetch = window.fetch.bind(window);

  function getSession() {
    try {
      return window.__FIGURESMITH__ || null;
    } catch (_e) {
      return null;
    }
  }

  function needsAuth(url) {
    try {
      var u = new URL(url, window.location.origin);
      var path = u.pathname || "";
      return path === "/api" || path.indexOf("/api/") === 0;
    } catch (_e) {
      return typeof url === "string" && url.indexOf("/api/") !== -1;
    }
  }

  window.fetch = function (input, init) {
    var session = getSession();
    var token = session && session.token ? String(session.token) : "";
    if (!token) {
      return originalFetch(input, init);
    }

    var url =
      typeof input === "string"
        ? input
        : input && typeof input.url === "string"
          ? input.url
          : String(input);

    if (!needsAuth(url)) {
      return originalFetch(input, init);
    }

    init = init ? Object.assign({}, init) : {};
    var headers = new Headers(init.headers || (input && input.headers) || undefined);
    if (!headers.has("Authorization") && !headers.has("authorization")) {
      headers.set("Authorization", "Bearer " + token);
    }
    init.headers = headers;
    return originalFetch(input, init);
  };

  // EventSource cannot set Authorization headers. Append fs_token for
  // /api/events/* only (middleware accepts query token on that prefix).
  var OriginalEventSource = window.EventSource;
  if (typeof OriginalEventSource === "function") {
    function withEventToken(url) {
      var session = getSession();
      var token = session && session.token ? String(session.token) : "";
      if (!token) {
        return url;
      }
      try {
        var u = new URL(url, window.location.origin);
        var path = u.pathname || "";
        if (path !== "/api/events" && path.indexOf("/api/events/") !== 0) {
          return url;
        }
        if (!u.searchParams.has("fs_token") && !u.searchParams.has("token")) {
          u.searchParams.set("fs_token", token);
        }
        return u.toString();
      } catch (_e) {
        return url;
      }
    }

    function BridgedEventSource(url, config) {
      return new OriginalEventSource(withEventToken(url), config);
    }
    BridgedEventSource.prototype = OriginalEventSource.prototype;
    BridgedEventSource.CONNECTING = OriginalEventSource.CONNECTING;
    BridgedEventSource.OPEN = OriginalEventSource.OPEN;
    BridgedEventSource.CLOSED = OriginalEventSource.CLOSED;
    window.EventSource = BridgedEventSource;
  }
})();
