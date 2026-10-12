import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import {
  abs, color, float, fract, max, min, mix, mx_fractal_noise_float, positionWorld, smoothstep, step, vec2, vec3,
} from "three/tsl";
import type { ViewModel } from "../../core/model";
import type { PoseRef } from "../../core/playhead";
import { SelectionRing, Swarm } from "../../core/Swarm";
import type { Pose } from "../../core/tracks";
import { antGeometry, foodGeometry } from "./geometry";
import { FORAGING_COLORS } from "./palette";

/** Soil tabletop: noisy two-tone dirt with faint cell lines inside the grid, on a dark plinth. */
function Terrain({ width, height }: { width: number; height: number }) {
  const material = useMemo(() => {
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.95, metalness: 0 });
    const xz = positionWorld.xz;
    const n = mx_fractal_noise_float(vec3(xz.mul(1.6), float(0)), 4, 2, 0.5).mul(0.5).add(0.5);
    const grain = mx_fractal_noise_float(vec3(xz.mul(14), float(3)), 2, 2, 0.5).mul(0.08);
    const soil = mix(color(FORAGING_COLORS.soil), color(FORAGING_COLORS.soilLight), n.add(grain).clamp());
    // Cell lines: distance to the nearest cell border, only inside the grid.
    const g = xz.add(vec2(width / 2, height / 2));
    const f = fract(g);
    const edge = min(min(f.x, f.y), min(float(1).sub(f.x), float(1).sub(f.y)));
    const inside = step(0, g.x).mul(step(g.x, width)).mul(step(0, g.y)).mul(step(g.y, height));
    const line = float(1).sub(smoothstep(0, 0.03, edge)).mul(inside).mul(0.22);
    // Darken the margin outside the play area a little, with a soft falloff.
    const out = max(abs(xz.x).sub(width / 2), abs(xz.y).sub(height / 2)).max(0);
    const margin = float(1).sub(smoothstep(0, 0.9, out).mul(0.35));
    m.colorNode = soil.mul(margin).add(line.mul(0.18));
    return m;
  }, [width, height]);
  useEffect(() => () => material.dispose(), [material]);

  const w = width + 1.6;
  const h = height + 1.6;
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow material={material}>
        <planeGeometry args={[w, h, 1, 1]} />
      </mesh>
      <mesh position={[0, -0.36, 0]} receiveShadow>
        <boxGeometry args={[w, 0.7, h]} />
        <meshStandardNodeMaterial color={FORAGING_COLORS.base} roughness={1} />
      </mesh>
    </group>
  );
}

/** A dirt mound with a dark entrance and a faint glowing ring, at the nest cell. */
function Nest({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh scale={[1, 0.38, 1]} position={[0, -0.06, 0]} castShadow receiveShadow>
        <sphereGeometry args={[0.62, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardNodeMaterial color={FORAGING_COLORS.soilLight} roughness={1} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.176, 0]}>
        <circleGeometry args={[0.13, 24]} />
        <meshBasicNodeMaterial color="#0b0705" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.012, 0]}>
        <ringGeometry args={[0.66, 0.7, 64]} />
        <meshStandardNodeMaterial color={FORAGING_COLORS.nest} emissive={FORAGING_COLORS.nest} emissiveIntensity={0.6} transparent opacity={0.7} />
      </mesh>
    </group>
  );
}

/** The selected agent's field of view (view_k × view_k cells), on the ground around it. */
function ViewSquare({ poses, selected, size }: { poses: PoseRef; selected: string | null; size: number }) {
  const group = useRef<THREE.Group>(null);
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.PlaneGeometry(size, size)), [size]);
  useEffect(() => () => edges.dispose(), [edges]);
  useFrame(() => {
    const g = group.current;
    if (!g) return;
    const pose = selected ? poses.current.byId.get(selected) : undefined;
    g.visible = !!pose;
    if (pose) g.position.set(pose.pos[0], 0.015, pose.pos[2]);
  });
  return (
    <group ref={group} visible={false} rotation={[-Math.PI / 2, 0, 0]}>
      <mesh>
        <planeGeometry args={[size, size]} />
        <meshBasicNodeMaterial color={FORAGING_COLORS.ant} transparent opacity={0.07} depthWrite={false} />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicNodeMaterial color={FORAGING_COLORS.ant} transparent opacity={0.55} />
      </lineSegments>
    </group>
  );
}

const isAnt = (p: Pose) => p.kind === "ant";
const isNextFood = (p: Pose) => p.kind === "food" && !!p.attrs?.next;
const isLaterFood = (p: Pose) => p.kind === "food" && !p.attrs?.next;
const isSignal = (p: Pose) => p.kind === "signal";

/** A small hop while walking: up and down once per step. */
const hop = (p: Pose, height: number) => Math.sin(p.stride * Math.PI) * height;

/**
 * The foraging world as a soil diorama: nest mound, ordered food (the one
 * needed next glows), ants that hop between cells and turn amber while
 * carrying, and "found" signals as small floating beacons.
 */
export function ForagingScene({ model, poses, width, height, nest, viewK, selected, onSelect }: {
  model: ViewModel;
  poses: PoseRef;
  width: number;
  height: number;
  nest: [number, number, number];
  viewK: number;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const geo = useMemo(() => ({ ant: antGeometry(), food: foodGeometry(), signal: new THREE.OctahedronGeometry(0.07) }), []);
  useEffect(() => () => Object.values(geo).forEach((g) => g.dispose()), [geo]);
  const colors = useMemo(() => ({
    ant: new THREE.Color(FORAGING_COLORS.ant),
    carrying: new THREE.Color(FORAGING_COLORS.carrying),
    food: new THREE.Color(FORAGING_COLORS.food),
    foodNext: new THREE.Color(FORAGING_COLORS.foodNext),
    signal: new THREE.Color(FORAGING_COLORS.signal),
  }), []);
  // Instance capacity per kind: the most seen in any frame.
  const capacity = useMemo(() => {
    const most: Record<string, number> = { ant: 1, food: 1, signal: 1 };
    for (const frame of model.frames) {
      const count: Record<string, number> = {};
      for (const a of frame) count[a.kind] = (count[a.kind] ?? 0) + 1;
      for (const k of Object.keys(most)) most[k] = Math.max(most[k], count[k] ?? 0);
    }
    return most;
  }, [model]);

  const span = Math.max(width, height);
  return (
    <>
      <color attach="background" args={[FORAGING_COLORS.sky]} />
      <fog attach="fog" args={[FORAGING_COLORS.sky, span * 1.4, span * 4]} />
      <hemisphereLight args={["#ffe6c7", "#3a2516", 0.9]} />
      <directionalLight
        position={[span * 0.4, span * 0.9, span * 0.3]}
        intensity={2.4}
        color="#fff1dc"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
        shadow-camera-left={-span * 0.8}
        shadow-camera-right={span * 0.8}
        shadow-camera-top={span * 0.8}
        shadow-camera-bottom={-span * 0.8}
        shadow-camera-near={0.1}
        shadow-camera-far={span * 4}
      />

      <Terrain width={width} height={height} />
      <Nest position={nest} />
      <ViewSquare poses={poses} selected={selected} size={viewK} />

      <Swarm poses={poses} match={isLaterFood} capacity={capacity.food} style={() => ({ color: colors.food })}>
        <primitive object={geo.food} attach="geometry" />
        <meshStandardNodeMaterial roughness={0.5} />
      </Swarm>
      <Swarm poses={poses} match={isNextFood} capacity={1} style={(_, t) => ({ color: colors.foodNext, scale: 1.15 + Math.sin(t * 3) * 0.06 })}>
        <primitive object={geo.food} attach="geometry" />
        <meshStandardNodeMaterial roughness={0.4} emissive={FORAGING_COLORS.foodNext} emissiveIntensity={0.55} />
      </Swarm>

      <Swarm poses={poses} match={isAnt} capacity={capacity.ant} selected={selected} onSelect={onSelect} style={(p) => ({
        color: p.attrs?.carrying ? colors.carrying : colors.ant,
        lift: hop(p, 0.06),
      })}>
        <primitive object={geo.ant} attach="geometry" />
        <meshStandardNodeMaterial roughness={0.35} metalness={0.1} />
      </Swarm>

      <Swarm poses={poses} match={isSignal} capacity={capacity.signal} castShadow={false} style={(p, t) => ({
        color: colors.signal,
        lift: 0.55 + Math.sin(t * 2.5 + p.pos[0] * 2 + p.pos[2]) * 0.06,
        scale: 0.6 + Math.min(1, Number(p.attrs?.ttl ?? 0) / 10) * 0.6,
      })}>
        <primitive object={geo.signal} attach="geometry" />
        <meshStandardNodeMaterial emissive={FORAGING_COLORS.signal} emissiveIntensity={1.2} transparent opacity={0.85} />
      </Swarm>

      <SelectionRing poses={poses} selected={selected} color={FORAGING_COLORS.ant} />
    </>
  );
}
