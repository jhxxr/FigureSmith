import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const RUST_COMMANDS = new URL("../src-tauri/src/commands.rs", import.meta.url);

function renderBridge(apiBase, token, sseTicket) {
  const source = readFileSync(RUST_COMMANDS, "utf8");
  const rawStart = source.indexOf('r#"(function()');
  assert.notEqual(rawStart, -1, "document-start bridge template not found");
  const start = rawStart + 3;
  const end = source.indexOf('"#', start);
  assert.notEqual(end, -1, "document-start bridge terminator not found");
  return source
    .slice(start, end)
    .replaceAll("{api_base_js}", JSON.stringify(apiBase))
    .replaceAll("{token_js}", JSON.stringify(token))
    .replaceAll("{sse_ticket_js}", JSON.stringify(sseTicket))
    .replaceAll("{{", "{")
    .replaceAll("}}", "}");
}

class HeadersMock {
  constructor(init) {
    this.values = new Map();
    if (!init) return;
    if (init instanceof HeadersMock) {
      for (const [key, value] of init.values) this.values.set(key, value);
    } else if (typeof init.entries === "function") {
      for (const [key, value] of init.entries()) this.values.set(String(key).toLowerCase(), String(value));
    } else if (Array.isArray(init)) {
      for (const [key, value] of init) this.values.set(String(key).toLowerCase(), String(value));
    } else {
      for (const [key, value] of Object.entries(init)) this.values.set(key.toLowerCase(), String(value));
    }
  }

  has(key) {
    return this.values.has(String(key).toLowerCase());
  }

  get(key) {
    return this.values.get(String(key).toLowerCase()) ?? null;
  }

  set(key, value) {
    this.values.set(String(key).toLowerCase(), String(value));
  }

  entries() {
    return this.values.entries();
  }
}

class RequestMock {
  constructor(input, init = {}) {
    if (input instanceof RequestMock) {
      this.url = input.url;
      this.method = input.method;
      this.body = input.body;
      this.signal = input.signal;
      this.credentials = input.credentials;
      this.cache = input.cache;
      this.redirect = input.redirect;
      this.referrer = input.referrer;
      this.headers = new HeadersMock(input.headers);
    } else {
      this.url = new URL(String(input), "http://127.0.0.1:45678/").href;
      this.method = init.method ?? "GET";
      this.body = init.body ?? null;
      this.signal = init.signal ?? null;
      this.credentials = init.credentials ?? "same-origin";
      this.cache = init.cache ?? "default";
      this.redirect = init.redirect ?? "follow";
      this.referrer = init.referrer ?? "about:client";
      this.headers = new HeadersMock(init.headers);
    }
    if (init.headers) this.headers = new HeadersMock(init.headers);
    if (init.method) this.method = init.method;
    if (Object.prototype.hasOwnProperty.call(init, "body")) this.body = init.body;
  }
}

function createWindow() {
  const calls = { fetch: [], events: [] };
  const origin = "http://127.0.0.1:45678";
  const window = {
    location: { origin, href: `${origin}/index.html` },
    fetch(input, init) {
      calls.fetch.push({ input, init });
      return Promise.resolve({ ok: true });
    },
    EventSource: class {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSED = 2;

      constructor(url, config) {
        calls.events.push({ url: String(url), config });
      }
    },
  };
  window.top = window;
  return { window, calls, origin };
}

function installBridge() {
  const state = createWindow();
  const context = {
    window: state.window,
    URL,
    Request: RequestMock,
    Headers: HeadersMock,
    Error,
    Promise,
    Object,
    String,
  };
  vm.runInNewContext(
    renderBridge(state.origin, "session-secret", "sse-ticket"),
    context,
    { filename: "desktop-bridge.initialization.js" },
  );
  return state;
}

test("fetch attaches Bearer only to exact-origin API requests", async () => {
  const { window, calls } = installBridge();

  await window.fetch("/api/models");
  assert.equal(calls.fetch[0].init.headers.get("authorization"), "Bearer session-secret");

  await window.fetch("https://example.com/api/models");
  assert.equal(calls.fetch[1].init, undefined);

  await window.fetch("http://127.0.0.1:45679/api/models");
  assert.equal(calls.fetch[2].init, undefined);
});

test("Request input preserves body and request options", async () => {
  const { window, calls } = installBridge();
  const signal = { aborted: false };
  const request = new RequestMock("/api/jobs", {
    method: "POST",
    body: "payload",
    signal,
    credentials: "include",
    cache: "no-store",
    redirect: "manual",
    referrer: "https://referrer.invalid/",
    headers: { "X-Test": "kept" },
  });

  await window.fetch(request);
  const forwarded = calls.fetch[0].input;
  assert.ok(forwarded instanceof RequestMock);
  assert.equal(forwarded.method, "POST");
  assert.equal(forwarded.body, "payload");
  assert.equal(forwarded.signal, signal);
  assert.equal(forwarded.credentials, "include");
  assert.equal(forwarded.cache, "no-store");
  assert.equal(forwarded.redirect, "manual");
  assert.equal(forwarded.referrer, "https://referrer.invalid/");
  assert.equal(forwarded.headers.get("x-test"), "kept");
  assert.equal(forwarded.headers.get("authorization"), "Bearer session-secret");
});

test("EventSource attaches only the scoped ticket on exact-origin event paths", () => {
  const { window, calls } = installBridge();

  new window.EventSource("/api/events/job-1");
  assert.equal(new URL(calls.events[0].url).searchParams.get("fs_ticket"), "sse-ticket");
  assert.equal(new URL(calls.events[0].url).searchParams.has("fs_token"), false);

  new window.EventSource("http://127.0.0.1:45679/api/events/job-1");
  assert.equal(new URL(calls.events[1].url).searchParams.has("fs_ticket"), false);

  new window.EventSource("https://example.com/api/events/job-1");
  assert.equal(new URL(calls.events[2].url).searchParams.has("fs_ticket"), false);
});
