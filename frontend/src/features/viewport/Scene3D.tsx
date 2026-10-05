import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { Line, OrbitControls } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useTheme } from "next-themes";
import * as THREE from "three";
import type { Frame, Frames } from "@/api/engine";
import { framePair, frameAgentIds } from "./decode";
import { fieldImage, themeRgb } from "./canvas";
import { FIELD_STYLE } from "./styles";

const SCALE = 1 / 100; // 100 um per scene unit
const TRAIL = 16;

type Vec3 = [number, number, number];

/** Engine (x, y, z) in um -> scene (x, up, z), centered on the tumor. Engine z is "up". */
function toScene(center: number[], x: number, y: number, z: number | undefined): Vec3 {
  const cz = center[2] ?? 0;
  return [(x - center[0]) * SCALE, ((z ?? cz) - cz) * SCALE, (y - center[1]) * SCALE];
}

const rgb = (name: string) => {
  const [r, g, b] = themeRgb(name);
  return new THREE.Color(r / 255, g / 255, b / 255);
};

// Cell rows: [x, y, phase, id, z?]; bot rows: [x, y, state, payload, target, z?].
const PHASE_COLOR = ["--muted-foreground", "--warning", "--surface-3", "--danger"];

function Cells({ frame, center }: { frame: Frame; center: number[] }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const cells = frame.world.cells as number[][];
  const { resolvedTheme } = useTheme();
  const palette = useMemo(() => PHASE_COLOR.map(rgb), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const o = new THREE.Object3D();
    cells.forEach((c, i) => {
      o.position.set(...toScene(center, c[0], c[1], c[4]));
      o.scale.setScalar(c[2] >= 2 ? 0.55 : 1); // dead cells shrink
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
      m.setColorAt(i, palette[c[2]] ?? palette[0]);
    });
    m.count = cells.length;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.computeBoundingSphere(); // keep raycasts (clicks) accurate as instances move
  }, [cells, center, palette]);

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, Math.max(1, cells.length)]}>
      <sphereGeometry args={[0.085, 14, 14]} />
      <meshStandardMaterial roughness={0.55} metalness={0.05} transparent opacity={0.9} />
    </instancedMesh>
  );
}

function Bots({ rows, center, ids, selected, onSelect }: {
  rows: number[][];
  center: number[];
  ids: string[];
  selected: string | null;
  onSelect: (agent: string) => void;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const { resolvedTheme } = useTheme();
  const color = useMemo(() => rgb("--primary"), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const o = new THREE.Object3D();
    rows.forEach((b, i) => {
      o.position.set(...toScene(center, b[0], b[1], b[5]));
      o.scale.setScalar(ids[i] === selected ? 1.8 : 1);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    m.count = rows.length;
    m.instanceMatrix.needsUpdate = true;
    m.computeBoundingSphere(); // bots move every frame; stale bounds make clicks miss
  }, [rows, center, ids, selected]);

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, Math.max(1, rows.length)]}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        if (e.instanceId !== undefined && ids[e.instanceId]) onSelect(ids[e.instanceId]);
      }}
    >
      <sphereGeometry args={[0.06, 16, 16]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={2.2} toneMapped={false} />
    </instancedMesh>
  );
}

function Trails({ frames, index, center, ids, selected }: { frames: Frame[]; index: number; center: number[]; ids: string[]; selected: string | null }) {
  const { resolvedTheme } = useTheme();
  const color = useMemo(() => rgb("--primary"), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps
  const paths = useMemo(() => {
    const out: Vec3[][] = [];
    for (let f = Math.max(0, index - TRAIL + 1); f <= index; f++) {
      (frames[f].world.bots as number[][]).forEach((b, i) => (out[i] ??= []).push(toScene(center, b[0], b[1], b[5])));
    }
    return out;
  }, [frames, index, center]);
  return (
    <>
      {paths.map((points, i) => points.length > 1 && (
        <Line key={i} points={points} color={color} lineWidth={ids[i] === selected ? 2.5 : 1.2} transparent opacity={ids[i] === selected ? 0.9 : 0.4} />
      ))}
    </>
  );
}

/** Live spatial signals ("found", "claimed", ...) as small diamonds that fade as they expire. */
function Signals({ marks, center }: { marks: Frame["signals"]; center: number[] }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const { resolvedTheme } = useTheme();
  const palette = useMemo(() => ({ found: rgb("--primary"), claimed: rgb("--warning"), other: rgb("--info") }), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps
  const capacity = Math.max(1, marks.length);
  useLayoutEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const o = new THREE.Object3D();
    marks.forEach((s, i) => {
      o.position.set(...toScene(center, s[0], s[1], s[5] as number | undefined));
      o.scale.setScalar(0.5 + Math.min(1, Number(s[4]) / 20) * 0.5);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
      const kind = s[2] as string;
      m.setColorAt(i, kind === "claimed" ? palette.claimed : kind === "found" ? palette.found : palette.other);
    });
    m.count = marks.length;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    m.computeBoundingSphere();
  }, [marks, center, palette]);
  if (marks.length === 0) return null;
  return (
    <instancedMesh key={capacity > 64 ? Math.ceil(capacity / 64) : 1} ref={mesh} args={[undefined, undefined, Math.max(64, Math.ceil(capacity / 64) * 64)]}>
      <octahedronGeometry args={[0.035]} />
      <meshBasicMaterial transparent opacity={0.75} toneMapped={false} />
    </instancedMesh>
  );
}

function Vessels({ vessels, center }: { vessels: number[][]; center: number[] }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const { resolvedTheme } = useTheme();
  const color = useMemo(() => rgb("--danger"), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const m = mesh.current;
    if (!m) return;
    const o = new THREE.Object3D();
    vessels.forEach((v, i) => {
      o.position.set(...toScene(center, v[0], v[1], v[2]));
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
    m.computeBoundingSphere();
  }, [vessels, center]);
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, Math.max(1, vessels.length)]}>
      <torusGeometry args={[0.07, 0.018, 8, 24]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
    </instancedMesh>
  );
}

/** A field (drug, pheromone...) as a translucent plane through the tumor center. */
function FieldSlice({ frame, scene, layer }: {
  frame: Frame;
  scene: { domain: number[]; center: number[]; field_shape: number[]; field_slice_z?: number | null };
  layer: string;
}) {
  const { resolvedTheme } = useTheme();
  const encoded = (frame.world.fields as Record<string, { b64: string }> | undefined)?.[layer];
  const texture = useMemo(() => {
    if (!encoded) return null;
    const image = fieldImage(encoded.b64, scene.field_shape[0], scene.field_shape[1], themeRgb(FIELD_STYLE[layer]?.color ?? "--primary"));
    if (!image) return null;
    const t = new THREE.CanvasTexture(image);
    t.colorSpace = THREE.SRGBColorSpace;
    t.minFilter = t.magFilter = THREE.LinearFilter;
    return t;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [encoded?.b64, layer, resolvedTheme]);
  useEffect(() => () => texture?.dispose(), [texture]);
  if (!texture) return null;
  const size = (scene.domain[1] - scene.domain[0]) * SCALE;
  const offset: Vec3 = [
    ((scene.domain[0] + scene.domain[1]) / 2 - scene.center[0]) * SCALE,
    ((scene.field_slice_z ?? scene.center[2] ?? 0) - (scene.center[2] ?? 0)) * SCALE,
    ((scene.domain[0] + scene.domain[1]) / 2 - scene.center[1]) * SCALE,
  ];
  return (
    <mesh position={offset} rotation={[-Math.PI / 2, 0, 0]} renderOrder={-1}>
      <planeGeometry args={[size, size]} />
      <meshBasicMaterial map={texture} transparent depthWrite={false} side={THREE.DoubleSide} toneMapped={false} />
    </mesh>
  );
}

export type CameraPreset = "overview" | "top" | "side";
const PRESETS: Record<CameraPreset, Vec3> = { overview: [4.6, 3.4, 5.2], top: [0, 7.2, 0.01], side: [7.2, 0.4, 0] };

/** Moves the camera when a preset is chosen; the user can orbit freely afterwards. */
function CameraRig({ preset }: { preset: CameraPreset }) {
  const { camera, controls } = useThree();
  useEffect(() => {
    camera.position.set(...PRESETS[preset]);
    camera.lookAt(0, 0, 0);
    (controls as unknown as { target?: THREE.Vector3; update?: () => void } | null)?.target?.set(0, 0, 0);
    (controls as unknown as { update?: () => void } | null)?.update?.();
  }, [preset, camera, controls]);
  return null;
}

/** The tumor boundary: a glassy sphere in 3D, a ring on the ground plane in 2D. */
function Boundary({ radius, is3d }: { radius: number; is3d: boolean }) {
  const { resolvedTheme } = useTheme();
  const color = useMemo(() => rgb("--foreground"), [resolvedTheme]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = radius * SCALE;
  const ring = useMemo(() => Array.from({ length: 97 }, (_, i) => {
    const t = (i / 96) * Math.PI * 2;
    return [Math.cos(t) * r, 0, Math.sin(t) * r] as Vec3;
  }), [r]);
  if (!is3d) return <Line points={ring} color={color} lineWidth={1} transparent opacity={0.25} dashed dashSize={0.08} gapSize={0.06} />;
  return (
    <group>
      <mesh>
        <sphereGeometry args={[r, 48, 48]} />
        <meshPhysicalMaterial color={color} transparent opacity={0.05} roughness={0.1} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <mesh>
        <sphereGeometry args={[r, 18, 12]} />
        <meshBasicMaterial color={color} wireframe transparent opacity={0.03} depthWrite={false} />
      </mesh>
      <Line points={ring} color={color} lineWidth={1} transparent opacity={0.18} />
    </group>
  );
}

/**
 * 3D replay of a tumor run: glassy tumor, cells by phase, vessels, glowing
 * nanobots with trails. Drag to orbit, scroll to zoom, click a bot to select.
 */
export default function Scene3D({ data, position, selected, onSelect, layer = null, preset = "overview", autoRotate = false }: {
  data: Frames;
  position: number;
  selected: string | null;
  onSelect: (agent: string) => void;
  layer?: string | null;
  preset?: CameraPreset;
  autoRotate?: boolean;
}) {
  const scene = data.scene as {
    center: number[]; tumor_radius: number; vessels: number[][]; dimensionality?: number;
    domain: number[]; field_shape: number[]; field_slice_z?: number | null;
  };
  const is3d = scene.dimensionality === 3;
  const { a, b, t } = framePair(data.frames, position);
  const index = data.frames.indexOf(a);
  const ids = useMemo(() => frameAgentIds(data), [data]);
  const center = scene.center;

  // Interpolate bots between frames (z included), snapping long jumps.
  const from = a.world.bots as number[][];
  const to = b.world.bots as number[][];
  const bots = from.map((row, i) => {
    const next = to[i] ?? row;
    const jump = Math.hypot(next[0] - row[0], next[1] - row[1], (next[5] ?? 0) - (row[5] ?? 0));
    if (jump > 120) return t < 0.5 ? row : next;
    const mix = (k: number) => (row[k] ?? 0) + ((next[k] ?? 0) - (row[k] ?? 0)) * t;
    return [mix(0), mix(1), row[2], row[3], row[4], row[5] === undefined ? (undefined as unknown as number) : mix(5)];
  });

  return (
    <div className="aspect-square w-full overflow-hidden rounded-lg bg-surface-2">
      <Canvas camera={{ position: is3d ? [4.6, 3.4, 5.2] : [0, 5.4, 4.2], fov: 40 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[4, 6, 3]} intensity={1.1} />
        <directionalLight position={[-3, -2, -4]} intensity={0.35} />
        <CameraRig preset={preset} />
        {layer && <FieldSlice frame={a} scene={scene} layer={layer} />}
        <Boundary radius={scene.tumor_radius} is3d={is3d} />
        <Vessels vessels={scene.vessels} center={center} />
        <Cells frame={a} center={center} />
        <Signals marks={a.signals} center={center} />
        <Trails frames={data.frames} index={index} center={center} ids={ids} selected={selected} />
        <Bots rows={bots} center={center} ids={ids} selected={selected} onSelect={onSelect} />
        <OrbitControls enableDamping dampingFactor={0.08} minDistance={1.2} maxDistance={12} autoRotate={autoRotate} autoRotateSpeed={0.8} makeDefault />
        <EffectComposer multisampling={4}>
          {/* Only the unlit, over-bright nanobots exceed the threshold, so only they glow. */}
          <Bloom intensity={0.9} luminanceThreshold={1} luminanceSmoothing={0.2} mipmapBlur />
        </EffectComposer>
      </Canvas>
    </div>
  );
}
