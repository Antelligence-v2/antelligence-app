export type RuntimeEnvironment = Record<string, unknown>;

export type ResolvedRuntimeConfig = {
  mode: string;
  frontendMode: string;
  isPreviewMode: boolean;
  apiBaseUrl: string;
  previewHostname: string;
  gitSha: string;
  buildLabel: string;
};

const asString = (value: unknown, fallback = ""): string =>
  value === undefined || value === null ? fallback : String(value);

export function resolveRuntimeConfig(
  env: RuntimeEnvironment,
  runtimeHostname: string,
): ResolvedRuntimeConfig {
  const mode = asString(env.MODE, "production");
  const defaultFrontendMode =
    mode === "development" ? "local" : mode === "preview" ? "preview" : "production";
  const frontendMode = asString(env.VITE_FRONTEND_MODE, defaultFrontendMode).toLowerCase();
  const explicitPreview = asString(env.VITE_PREVIEW_MODE).toLowerCase();
  const isPreviewMode =
    frontendMode === "preview" ||
    mode === "preview" ||
    explicitPreview === "1" ||
    explicitPreview === "true";
  const apiBaseUrl = asString(
    env.VITE_API_BASE_URL,
    frontendMode === "local" ? "http://127.0.0.1:8001" : "",
  ).replace(/\/$/, "");
  const gitSha = asString(env.VITE_GIT_SHA, "unknown");
  const previewHostname = asString(env.VITE_PREVIEW_HOSTNAME, runtimeHostname || "unknown");
  const buildLabel = asString(env.VITE_BUILD_LABEL, `${mode}-${gitSha.slice(0, 8)}`);

  return {
    mode,
    frontendMode,
    isPreviewMode,
    apiBaseUrl,
    previewHostname,
    gitSha,
    buildLabel,
  };
}
