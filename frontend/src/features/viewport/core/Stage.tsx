import { Component, type ReactNode } from "react";
import { Canvas, extend, type ThreeToJSXElements } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import { backendOf, forceWebGL, type Backend } from "./quality";

// Expose three/webgpu classes (node materials etc.) as JSX elements.
declare module "@react-three/fiber" {
  interface ThreeElements extends ThreeToJSXElements<typeof THREE> {}
}
extend(THREE as unknown as Parameters<typeof extend>[0]);

/** Keeps a renderer failure inside the panel: report it and show the fallback. */
class RendererBoundary extends Component<
  { fallback: ReactNode; onError?: (message: string) => void; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error) {
    console.error("[viewport] 3D scene crashed:", error);
    this.props.onError?.(error.message);
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/**
 * The shared 3D canvas: a WebGPURenderer that falls back to WebGL 2 on its own.
 * Children are scene content; worlds never create their own renderer.
 */
export function Stage({ children, fallback = null, onBackend, onError, camera, className, active = true }: {
  children: ReactNode;
  /** Shown instead of the canvas if the renderer throws (e.g. the 2D view). */
  fallback?: ReactNode;
  onBackend?: (backend: Backend) => void;
  onError?: (message: string) => void;
  camera?: { position: [number, number, number]; fov?: number };
  className?: string;
  /** False pauses rendering (the canvas stays mounted, e.g. while the 2D view is shown). */
  active?: boolean;
}) {
  return (
    <RendererBoundary fallback={fallback} onError={onError}>
      <Canvas
        className={className}
        camera={camera ?? { position: [6, 5, 6], fov: 40 }}
        dpr={[1, 2]}
        frameloop={active ? "always" : "never"}
        shadows="percentage"
        gl={async ({ canvas }) => {
          const renderer = new THREE.WebGPURenderer({
            canvas: canvas as HTMLCanvasElement,
            antialias: true,
            alpha: true,
            forceWebGL: forceWebGL(),
          });
          try {
            await renderer.init();
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            console.error("[viewport] renderer init failed:", error);
            onError?.(`renderer init failed: ${message}`);
            throw error;
          }
          // Losing the GPU after init (driver reset, too many live contexts) goes through
          // the same fallback as an init failure instead of leaving a blank panel.
          renderer.onDeviceLost = (info: { message?: string }) => onError?.(`GPU device lost: ${info.message ?? "unknown reason"}`);
          onBackend?.(backendOf(renderer));
          return renderer;
        }}
      >
        {children}
      </Canvas>
    </RendererBoundary>
  );
}
