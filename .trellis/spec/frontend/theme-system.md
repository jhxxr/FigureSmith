# Theme System (Desktop Web UI)

> Shared light/dark/system theme contract for FigureSmith static UI and vendor main flow.

---

## Scope / Trigger

Applies when changing Welcome / Models / Create / Import / History / Guide / Canvas shell visuals, topbar chrome, or desktop splash styling.

Does **not** apply to SVG-Edit iframe internals (`vendor/**/svg-edit/**`).

---

## Contract

### Storage

| Key | Values | Default if missing/invalid |
|-----|--------|----------------------------|
| `localStorage.figuresmith_theme_v1` | `light` \| `dark` \| `system` | `system` |

Locale stays separate: `localStorage.autofigure_locale_v1` (`zh` \| `en`).

### DOM

| Attribute / style | Meaning |
|-------------------|---------|
| `html[data-theme="light\|dark"]` | **Resolved** appearance |
| `html[data-theme-preference="light\|dark\|system"]` | Stored preference |
| `document.documentElement.style.colorScheme` | Matches resolved theme |

### Runtime API (`FigureSmithUI` in `/fs/common.js`)

| API | Behavior |
|-----|----------|
| `getThemePreference()` | Read storage; invalid → `system` |
| `setThemePreference(pref)` | Persist + `applyTheme()` |
| `resolveTheme(pref?)` | `system` → `matchMedia('(prefers-color-scheme: dark)')` |
| `applyTheme()` | Set DOM attrs + color-scheme; attach/detach media listener; refresh `[data-fs-theme-switch]` mounts |
| `renderThemeSwitch(container)` | Light/Dark/System chips (中文：浅色/深色/系统) |

When preference is `system`, listen to `prefers-color-scheme` changes and re-apply.

### Tokens

- Authority: `apps/backend/figuresmith/static/ui/common.css` (`--fs-*`).
- Light defaults on `:root`; dark overrides under `html[data-theme="dark"]` (and equivalent selectors used in product CSS).
- Vendor `styles.css` maps legacy vars (`--bg-1`, `--ink`, `--accent`, …) to `--fs-*` (or dual assignment). **No** `fonts.googleapis.com` imports; system font stack only.

### Page wiring

1. Load `/fs/common.css` + `/fs/common.js` on pages that share the design system.
2. Call `FigureSmithUI.applyTheme()` early after scripts (inline boot OK).
3. Mount switch via `renderNav` (Welcome/Models) or `renderThemeSwitch` on a topbar node (`[data-fs-theme-switch]`).

Desktop splash (`apps/desktop/index.html`) may inline a token subset with a “keep in sync with common.css” comment because it does not load the backend static mount at cold start.

---

## Create form rules

- Visual regroup / collapse (e.g. Advanced `<details>`) is allowed.
- **Preserve every existing control `id`** and binding/submit behavior in `app.js`.
- Do not delete configuration fields; hide secondary options only via collapse.

---

## Validation & Error Matrix

| Condition | Expected |
|-----------|----------|
| Missing theme key | Resolve as `system` → light or dark from OS |
| Invalid stored value | Treat as `system` |
| Preference `system` + OS flips | Theme updates without reload |
| Preference `light`/`dark` | Ignore OS flips; no media listener needed |
| Offline / no CDN | UI still renders; no Google Fonts request |

---

## Good / Base / Bad

**Good**: One theme runtime in `common.js`; vendor and FS pages both call `applyTheme`; tokens only via `--fs-*`.

**Base**: Default preference `system`; Create ids unchanged after layout polish.

**Bad**: Re-introducing `@import url("https://fonts.googleapis.com/...")`; hard-coding page-only dark hex that breaks light mode; theming SVG-Edit iframe; inventing a second storage key for theme.

---

## Tests / Manual checks

- Toggle Light/Dark/System; refresh; navigate across Welcome ↔ Create ↔ Models — preference sticks.
- `system` follows OS appearance.
- `rg fonts.googleapis` clean under `vendor/autofigure_edit/web`, `apps/backend/figuresmith/static`, `apps/desktop` (exclude third-party svg-edit vendor trees if present).
- Create: binding select/save/delete + Confirm still work with advanced section collapsed/expanded.
- Canvas: shell themed; SVG-Edit iframe appearance unchanged.

---

## Wrong vs Correct

#### Wrong

```css
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans...");
body { background: #0f1317; } /* page locked dark */
```

#### Correct

```js
// common.js
localStorage figuresmith_theme_v1 → applyTheme()
// html[data-theme] + --fs-* tokens in common.css
// vendor styles map --ink: var(--fs-text);
```

---

## Design Decision: Shared runtime over per-page themes

**Context**: Welcome/Models were dark graphite; vendor Create flow was light academic + Google Fonts.

**Decision**: Single preference key and `FigureSmithUI` theme APIs; CSS dual tokens; vendor loads `/fs/common.*`.

**Why**: Cross-page consistency, offline desktop, one control surface next to language chips.
