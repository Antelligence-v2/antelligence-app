import { useMemo, useRef, type ReactNode } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import type { Pose } from "./tracks";
import type { PoseRef } from "./playhead";

export interface SwarmStyle {
  color: THREE.Color;
  /** Uniform scale (multiplied by presence for fade in/out). */
  scale?: number;
  /** Extra height above the pose (hops, hovering). */
  lift?: number;
}

/**
 * Draws every pose matching `match` as one instanced mesh: position, heading,
 * scale and color are written per frame from the shared poses (no React renders).
 * Children supply the geometry and material; geometry should face +z.
 */
export function Swarm({ poses, match, style, capacity, selected, onSelect, castShadow = true, children }: {
  poses: PoseRef;
  match: (pose: Pose) => boolean;
  style: (pose: Pose, time: number) => SwarmStyle;
  /** Max instances; fixed for the mesh's lifetime (key the Swarm to change it). */
  capacity: number;
  selected?: string | null;
  onSelect?: (id: string) => void;
  castShadow?: boolean;
  children: ReactNode;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const ids = useRef<string[]>([]);
  const tmp = useMemo(() => ({ o: new THREE.Object3D() }), []);

  useFrame(({ clock }) => {
    const m = mesh.current;
    if (!m) return;
    const time = clock.elapsedTime;
    let n = 0;
    for (const pose of poses.current.list) {
      if (n >= capacity || !match(pose)) continue;
      const s = style(pose, time);
      const scale = (s.scale ?? 1) * pose.presence * (pose.id === selected ? 1.25 : 1);
      tmp.o.position.set(pose.pos[0], pose.pos[1] + (s.lift ?? 0), pose.pos[2]);
      tmp.o.rotation.set(0, pose.heading, 0);
      tmp.o.scale.setScalar(Math.max(scale, 1e-4));
      tmp.o.updateMatrix();
      m.setMatrixAt(n, tmp.o.matrix);
      m.setColorAt(n, s.color);
      ids.current[n] = pose.id;
      n++;
    }
    m.count = n;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    if (onSelect) m.computeBoundingSphere(); // keep clicks accurate as instances move
  });

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, capacity]}
      castShadow={castShadow}
      receiveShadow
      frustumCulled={false}
      onClick={onSelect && ((e: ThreeEvent<MouseEvent>) => {
        if (e.instanceId === undefined) return;
        e.stopPropagation();
        const id = ids.current[e.instanceId];
        if (id) onSelect(id);
      })}
      onPointerOver={onSelect && (() => (document.body.style.cursor = "pointer"))}
      onPointerOut={onSelect && (() => (document.body.style.cursor = ""))}
    >
      {children}
    </instancedMesh>
  );
}

/** A pulsing ring on the ground under the selected pose. */
export function SelectionRing({ poses, selected, color = "#ffffff", radius = 0.42 }: {
  poses: PoseRef;
  selected: string | null;
  color?: string;
  radius?: number;
}) {
  const ring = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    const r = ring.current;
    if (!r) return;
    const pose = selected ? poses.current.byId.get(selected) : undefined;
    r.visible = !!pose;
    if (!pose) return;
    r.position.set(pose.pos[0], 0.02, pose.pos[2]);
    r.scale.setScalar(1 + Math.sin(clock.elapsedTime * 4) * 0.08);
  });
  return (
    <mesh ref={ring} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
      <ringGeometry args={[radius * 0.8, radius, 48]} />
      <meshBasicNodeMaterial color={color} transparent opacity={0.85} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}
