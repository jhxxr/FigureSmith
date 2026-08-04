# Technical Design

## Provider binding model

- Replace fixed provider presets with user-managed named bindings.
- Each binding stores a display name, canonical Base URL, text/image model identifiers, and a secret reference for its API key.
- The run configuration has two independent binding references: `image_provider_binding` and `ai_provider_binding`; they may point to the same binding.
- Persist non-secret binding metadata in app data/settings and persist API keys through the OS credential store or existing secure storage abstraction. Never write plaintext keys to `settings.json`.
- On load, resolve secret references into the in-memory run request only; redact bindings and logs where keys could appear.


- Normalize and validate custom provider base URLs in the vendor integration boundary before request construction.
- Remove only the endpoint loopback restriction; retain URL scheme/credential/parse validation and local model offline behavior unless it blocks API transport.
- Update backend security helper contracts and tests to represent remote HTTP(S) custom endpoints as allowed.

## Data flow

1. UI/session or CLI supplies provider, base URL, and image provider settings.
2. Configuration resolver canonicalizes the supplied URL exactly once.
3. Text/image request builders receive the canonical URL without appending an already-present absolute URL.
4. Security validation checks a valid HTTP(S) endpoint but does not require loopback.
5. Mocked tests verify request targets before any real transport.

## URL contract

- Trim surrounding whitespace.
- Accept absolute `http://` or `https://` URLs and bare host forms where existing CLI behavior supports them.
- Reject empty values, unsupported schemes, credentials, malformed hosts, and accidental concatenated URL strings.
- Remove trailing slash for canonical base URL; preserve a single existing API path such as `/v1`.
- Request code must append endpoint paths using URL joining, never string-prefixing a full URL.

## Compatibility and migration

- Existing loopback URLs remain valid.
- Existing remote providers no longer fail solely due to loopback enforcement.
- Existing strict-offline environment flags may remain for model/download controls, but must not be used to reject configured API endpoints.
- Update security tests, canary tests, and user-facing text that claim remote API endpoints are forbidden.

## Rollback

Revert the endpoint validator relaxation and URL normalization changes independently if downstream compatibility issues appear; no data migration is required and API keys remain session-only.
