import assert from "node:assert/strict";
import test from "node:test";

import { resolveRuntimeConfig } from "../src/lib/runtimeConfig.ts";

test("documented frontend mode activates the preview guard", () => {
  const runtime = resolveRuntimeConfig(
    { MODE: "production", VITE_FRONTEND_MODE: "preview" },
    "preview.example",
  );

  assert.equal(runtime.frontendMode, "preview");
  assert.equal(runtime.isPreviewMode, true);
  assert.equal(runtime.apiBaseUrl, "");
  assert.equal(runtime.previewHostname, "preview.example");
});

test("local runtime defaults to the documented API service", () => {
  const runtime = resolveRuntimeConfig({ MODE: "development" }, "localhost");

  assert.equal(runtime.frontendMode, "local");
  assert.equal(runtime.isPreviewMode, false);
  assert.equal(runtime.apiBaseUrl, "http://127.0.0.1:8001");
});

test("production defaults to the serving origin instead of the user's localhost", () => {
  const runtime = resolveRuntimeConfig({ MODE: "production" }, "app.example");

  assert.equal(runtime.frontendMode, "production");
  assert.equal(runtime.isPreviewMode, false);
  assert.equal(runtime.apiBaseUrl, "");
});

test("explicit API and legacy preview overrides remain compatible", () => {
  const runtime = resolveRuntimeConfig(
    {
      MODE: "production",
      VITE_PREVIEW_MODE: "true",
      VITE_API_BASE_URL: "https://api.example/",
    },
    "app.example",
  );

  assert.equal(runtime.isPreviewMode, true);
  assert.equal(runtime.apiBaseUrl, "https://api.example");
});
