import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three/webgpu";
import type { ViewModel } from "./model";
import type { PoseRef } from "./playhead";
import type { CameraPreset } from "./cameraPresets";

/** Camera placements framed to the world's bounds. */
function presetPlacement(preset: CameraPreset, bounds: ViewModel["bounds"]) {
  const center = new THREE.Vector3(
    (bounds.min[0] + bounds.max[0]) / 2, 0, (bounds.min[2] + bounds.max[2]) / 2,
  );
  const span = Math.max(bounds.max[0] - bounds.min[0], bounds.max[2] - bounds.min[2]);
  const offsets: Record<CameraPreset, THREE.Vector3> = {
    overview: new THREE.Vector3(0.55, 0.85, 0.95).multiplyScalar(span),
    top: new THREE.Vector3(0, 1.45, 0.01).multiplyScalar(span),
    low: new THREE.Vector3(0.75, 0.22, 0.6).multiplyScalar(span),
  };
  return { target: center, position: center.clone().add(offsets[preset]) };
}

/**
 * Orbit controls plus smooth moves: to a preset when it changes, and a follow
 * cam that keeps the selected agent centered (the user can still orbit/zoom).
 */
export function CameraRig({ bounds, preset, follow, poses, autoRotate = false }: {
  bounds: ViewModel["bounds"];
  preset: CameraPreset;
  /** Agent id to follow, or null. */
  follow?: string | null;
  poses?: PoseRef;
  autoRotate?: boolean;
}) {
  const camera = useThree((s) => s.camera);
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null);
  const span = Math.max(bounds.max[0] - bounds.min[0], bounds.max[2] - bounds.min[2]);
  const goal = useRef<{ position: THREE.Vector3; target: THREE.Vector3 } | null>(null);
  const tmp = useMemo(() => new THREE.Vector3(), []);

  // A preset change (or new bounds) starts a glide; user input cancels it.
  useEffect(() => {
    goal.current = presetPlacement(preset, bounds);
  }, [preset, bounds]);

  useFrame((_, dt) => {
    const c = controls.current;
    if (!c) return;
    const k = 1 - Math.exp(-dt * 4);
    const g = goal.current;
    if (g) {
      camera.position.lerp(g.position, k);
      c.target.lerp(g.target, k);
      if (camera.position.distanceTo(g.position) < 0.01 * span) goal.current = null;
    }
    const pose = follow && poses ? poses.current.byId.get(follow) : undefined;
    if (pose) {
      // Move camera and target together so the user's orbit angle is kept.
      tmp.set(pose.pos[0], pose.pos[1], pose.pos[2]).sub(c.target).multiplyScalar(k);
      c.target.add(tmp);
      camera.position.add(tmp);
    }
    c.update();
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={span * 0.15}
      maxDistance={span * 3}
      maxPolarAngle={Math.PI * 0.48}
      autoRotate={autoRotate}
      autoRotateSpeed={0.6}
      onStart={() => (goal.current = null)}
    />
  );
}
