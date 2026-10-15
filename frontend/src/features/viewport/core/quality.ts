/**
 * Which GPU backend a scene runs on, and what that allows.
 *
 * WebGPU needs a secure context (HTTPS or localhost); over plain HTTP the
 * renderer silently falls back to WebGL 2. Effects that only exist on WebGPU
 * must check `backend` and degrade, never assume.
 */

export type Backend = "webgpu" | "webgl2";

/** `?renderer=webgl` forces the WebGL 2 backend, to test the fallback path locally. */
export function forceWebGL(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("renderer") === "webgl";
}

let webgl2Support: boolean | undefined;

/** Can this browser render 3D at all? WebGL 2 is the floor; checked once. */
export function canRender3D(): boolean {
  if (webgl2Support === undefined) {
    try {
      webgl2Support = !!document.createElement("canvas").getContext("webgl2");
    } catch {
      webgl2Support = false;
    }
  }
  // WebGPU alone isn't enough: navigator.gpu can exist with no adapter, and the fallback needs WebGL 2.
  return webgl2Support;
}

/** The backend an initialized WebGPURenderer actually ended up on. */
export function backendOf(renderer: { backend: unknown }): Backend {
  return (renderer.backend as { isWebGPUBackend?: boolean }).isWebGPUBackend ? "webgpu" : "webgl2";
}
