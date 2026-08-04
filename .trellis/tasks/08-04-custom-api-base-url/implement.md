# Implementation Plan

1. Locate the complete provider/base URL resolution and continuation-image configuration path in `vendor/autofigure_edit/autofigure2.py` and related backend/UI code.
2. Replace preset provider choices with persisted named binding CRUD/configuration, including two independent selections: image-generation API binding and ordinary AI binding.
3. Add secure API-key persistence through the existing OS credential/security abstraction; persist only non-secret metadata in settings/app data and inject secrets only into in-memory run requests.
4. Add one canonical URL normalization helper and route both binding request paths through it; prevent duplicate scheme/host/path concatenation.
5. Relax `figuresmith.security.offline` endpoint validation to allow valid remote HTTP(S) endpoints while preserving malformed URL and credential rejection.
6. Remove/update stale strict-loopback error handling, preset UI, canaries, and docs that assert remote endpoints or fixed providers are required.
7. Add regression tests for binding persistence, secret redaction/storage, independent image/AI bindings, Orbit-style full URL input, URL variants, remote custom endpoint acceptance, request URL construction, and continuation configuration.
8. Run focused pytest suites, then the full relevant test suite and lint/type checks available in the repository.
9. Review the diff for accidental plaintext API-key persistence or unintended local model network changes before task activation/implementation approval.

Validation commands:

- `python -m pytest tests/test_offline_endpoint.py tests/test_strict_offline_network_canary.py tests/test_strict_offline_no_remote_fallback.py`
- `python -m pytest tests`

Risk points:

- `vendor/autofigure_edit/autofigure2.py` has multiple provider-specific request paths; all custom paths must use the same canonical URL.
- Removing endpoint enforcement may conflict with tests/documentation from the prior security boundary; update only the endpoint policy assertions, not local model safety guarantees.
