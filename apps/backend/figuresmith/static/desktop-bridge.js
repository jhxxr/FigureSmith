/**
 * FigureSmith desktop bridge compatibility loader.
 *
 * The Tauri shell installs the authenticated wrapper at document start. This
 * file remains for ordinary browser development and older cached pages, but
 * it deliberately has no token-bearing global fallback. A late script cannot
 * safely establish a desktop session after application code has run.
 */
(function () {
  "use strict";

  if (window.__FIGURESMITH_BRIDGE_INSTALLED__) {
    return;
  }
  window.__FIGURESMITH_BRIDGE_INSTALLED__ = true;

  // A valid desktop page is already wrapped by the Rust document-start
  // initialization script. Do not re-wrap it or inspect private state.
  if (window.__FIGURESMITH_DESKTOP_READY__) return;
})();
