import { resolveRuntimeConfig } from "./runtimeConfig";

export type BuildInfo = {
  mode: string;
  frontendMode: string;
  apiBaseUrl: string;
  buildLabel: string;
  gitSha: string;
  previewHostname: string;
};

const runtimeHostname =
  typeof window === "undefined" ? "unknown" : window.location.hostname || "unknown";
const runtime = resolveRuntimeConfig(import.meta.env, runtimeHostname);

export const FRONTEND_MODE = runtime.frontendMode;
export const IS_PREVIEW_MODE = runtime.isPreviewMode;
export const API_BASE_URL = runtime.apiBaseUrl;
export const PREVIEW_HOSTNAME = runtime.previewHostname;

export const BUILD_INFO: BuildInfo = Object.freeze({
  mode: runtime.mode,
  frontendMode: runtime.frontendMode,
  apiBaseUrl: runtime.apiBaseUrl,
  buildLabel: runtime.buildLabel,
  gitSha: runtime.gitSha,
  previewHostname: runtime.previewHostname,
});
