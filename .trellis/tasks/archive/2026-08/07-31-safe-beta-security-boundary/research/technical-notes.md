# Security Boundary Technical Notes

## Selected SVG policy

- Parse with network, DTD, external entity, and huge-tree features disabled.
- Enforce explicit byte/node/depth/attribute limits before canonical output.
- Allow only the SVG geometry/text/defs/gradient/clip/mask elements exercised by
  a checked-in compatibility corpus.
- Reject `script`, `foreignObject`, `iframe`, `object`, `embed`, animation,
  `on*` attributes, external hrefs, active CSS, and protocol-relative URLs.
- Permit href fragments and, only where required, size-limited raster
  `data:image/png|jpeg|webp` values. Never allow SVG data URIs.
- Parse CSS with the existing/pinned structured CSS parser; do not sanitize CSS
  with string matching.
- Re-serialize and parse again. The sanitized bytes are the only bytes rendered
  or published.

Legacy artifacts are sanitized on read or denied. Raw files must not remain
reachable through a static mount. Responses use at least:

```text
Content-Security-Policy: sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
```

## Selected bridge policy

The document-start bootstrap established by the runtime-integration child owns
an immutable `allowedOrigin`. Authentication requires:

```text
url.protocol == "http:"
url.hostname == "127.0.0.1"
url.origin == allowedOrigin
url.pathname is under "/api/"
```

The wrapper must separately test string URLs, URL objects, and `Request`
objects. EventSource uses the same predicate. Query credentials, if retained for
native EventSource compatibility, are short-lived/scoped and filtered from
server access logs; the long-lived bearer may not be logged.

## Strict-offline test model

Tests monkeypatch or intercept all DNS/socket/HTTP creation and use provider
requests with omitted URLs so default resolution is exercised. Provider-returned
remote image URLs and redirects are separate cases. Passing source-string tests
is not sufficient.

## Source anchors

- SVG parse/validation: `vendor/autofigure_edit/autofigure2.py:2623`
- Artifact response: `vendor/autofigure_edit/server.py:442`
- Bridge path-only auth: `apps/backend/figuresmith/static/desktop-bridge.js:27`
- Provider defaults: `vendor/autofigure_edit/autofigure2.py:133`
- Provider image fetch: `vendor/autofigure_edit/autofigure2.py:564`
