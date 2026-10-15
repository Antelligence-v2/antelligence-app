import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import {
  abs, color, float, instanceColor, length, max, mix, mx_fractal_noise_float, mx_worley_noise_float, normalView,
  positionViewDirection, positionWorld, smoothstep, texture, uniform, vec3, vec4,
} from "three/tsl";
import type { FieldSeries, ViewModel, WorldEvent } from "../../core/model";
import type { PoseRef } from "../../core/playhead";
import { SelectionRing, Swarm } from "../../core/Swarm";
import { useInstanceColors } from "../../core/instanceColors";
import type { Pose } from "../../core/tracks";
import { botGeometry, cellGeometry } from "./geometry";
import { TUMOR_COLORS } from "./palette";

/** Height nanobots hover at above the tissue. */
const HOVER = 0.24;
/** Moves longer than this (respawn at a vessel) snap instead of sliding, in scene units. */
export const MAX_JUMP = 1.2;

/** Rim glow: 0 facing the camera, 1 at grazing angles. */
const fresnel = (power: number) => float(1).sub(abs(normalView.dot(positionViewDirection))).pow(power);

/** Neutral tissue floor: a faint cellular (Worley) pattern, fading out past the domain. */
function Tissue({ span }: { span: number }) {
  const material = useMemo(() => {
    const m = new THREE.MeshStandardNodeMaterial({ roughness: 0.85, metalness: 0 });
    const xz = positionWorld.xz;
    const cells = mx_worley_noise_float(xz.mul(7.5));
    const fine = mx_worley_noise_float(xz.mul(26)).mul(0.35);
    const haze = mx_fractal_noise_float(vec3(xz.mul(0.9), float(1)), 3, 2, 0.5).mul(0.5).add(0.5);
    const border = smoothstep(0.35, 0.8, cells.add(fine.mul(0.4)));
    const base = mix(color(TUMOR_COLORS.tissue), color(TUMOR_COLORS.tissueLight), border.mul(0.75).add(haze.mul(0.25)));
    const out = max(abs(xz.x), abs(xz.y)).sub(span / 2).max(0);
    const fade = float(1).sub(smoothstep(0, span * 0.25, out).mul(0.75));
    m.colorNode = base.mul(fade);
    return m;
  }, [span]);
  useEffect(() => () => material.dispose(), [material]);
  const size = span * 1.5;
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow material={material}>
        <planeGeometry args={[size, size, 1, 1]} />
      </mesh>
      <mesh position={[0, -0.31, 0]} receiveShadow>
        <boxGeometry args={[size, 0.6, size]} />
        <meshStandardNodeMaterial color={TUMOR_COLORS.base} roughness={1} />
      </mesh>
    </group>
  );
}

/** The tumor boundary: a glassy lens with a glowing rim, and a bright ring where it meets the tissue. */
function Boundary({ radius }: { radius: number }) {
  const lens = useMemo(() => {
    const m = new THREE.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, roughness: 0.1 });
    const rim = fresnel(2.5);
    m.colorNode = vec4(color(TUMOR_COLORS.boundary), rim.mul(0.35).add(0.025));
    m.emissiveNode = color(TUMOR_COLORS.boundary).mul(rim.mul(0.55));
    return m;
  }, []);
  useEffect(() => () => lens.dispose(), [lens]);
  return (
    <group>
      <mesh scale={[1, 0.32, 1]} material={lens} renderOrder={2}>
        <sphereGeometry args={[radius, 64, 32, 0, Math.PI * 2, 0, Math.PI / 2]} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.006, 0]}>
        <ringGeometry args={[radius - 0.012, radius + 0.012, 128]} />
        <meshStandardNodeMaterial color="#000000" emissive={TUMOR_COLORS.boundary} emissiveIntensity={1.4} />
      </mesh>
    </group>
  );
}

/** A capillary opening: glowing pore, pulsing core and a ripple of supply spreading out. */
function Vessel({ position, phase }: { position: [number, number, number]; phase: number }) {
  const core = useRef<THREE.Mesh>(null);
  const ripple = useRef<THREE.Mesh>(null);
  const rippleMat = useRef<THREE.MeshStandardNodeMaterial>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime + phase;
    const beat = Math.pow(Math.max(0, Math.sin(t * 2.4)), 6);
    if (core.current) core.current.scale.setScalar(1 + beat * 0.25);
    const r = (t * 0.45) % 1;
    if (ripple.current) ripple.current.scale.setScalar(1 + r * 4);
    if (rippleMat.current) rippleMat.current.emissiveIntensity = (1 - r) * 0.9;
  });
  return (
    <group position={position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, 0]} castShadow>
        <torusGeometry args={[0.1, 0.028, 16, 48]} />
        <meshStandardNodeMaterial color={TUMOR_COLORS.vessel} emissive={TUMOR_COLORS.vessel} emissiveIntensity={0.7} roughness={0.3} />
      </mesh>
      <mesh ref={core} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <circleGeometry args={[0.075, 32]} />
        <meshStandardNodeMaterial color="#000000" emissive={TUMOR_COLORS.vesselCore} emissiveIntensity={1.6} />
      </mesh>
      <mesh ref={ripple} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 0]}>
        <ringGeometry args={[0.1, 0.112, 48]} />
        <meshStandardNodeMaterial ref={rippleMat} color="#000000" emissive={TUMOR_COLORS.vessel} transparent blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
    </group>
  );
}

/** Index of the latest field snapshot at or before each step (-1 before the first). */
function snapshotIndex(series: FieldSeries, steps: number): Int32Array {
  const out = new Int32Array(steps).fill(-1);
  let j = -1;
  for (let s = 0; s < steps; s++) {
    while (j + 1 < series.snapshots.length && series.snapshots[j + 1].step <= s) j++;
    out[s] = j;
  }
  return out;
}

/** Writes one snapshot into an RGBA texture, stretched to its own min..max (like the 2D view). */
function fillTexture(tex: THREE.DataTexture, series: FieldSeries, snap: number) {
  const data = tex.image.data as Uint8Array;
  const values = snap >= 0 ? series.snapshots[snap].values : null;
  let lo = Infinity;
  let hi = -Infinity;
  if (values) for (const v of values) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const range = values && hi > lo ? hi - lo : 0;
  const { width, height } = series;
  for (let z = 0; z < height; z++) {
    for (let x = 0; x < width; x++) {
      const v = range ? Math.round(((values![z * width + x] - lo) / range) * 255) : 0;
      const p = ((height - 1 - z) * width + x) * 4; // plane v runs opposite to world z
      data[p] = data[p + 1] = data[p + 2] = data[p + 3] = v;
    }
  }
  tex.needsUpdate = true;
}

/** A field as light glowing up through the tissue, blended smoothly between recorded steps. */
function FieldGlow({ series, steps, name, playhead }: {
  series: FieldSeries;
  steps: number;
  name: string;
  playhead: React.MutableRefObject<number>;
}) {
  const index = useMemo(() => snapshotIndex(series, steps), [series, steps]);
  const state = useMemo(() => {
    const make = () => {
      const t = new THREE.DataTexture(new Uint8Array(series.width * series.height * 4), series.width, series.height, THREE.RGBAFormat);
      t.magFilter = t.minFilter = THREE.LinearFilter;
      return t;
    };
    const a = make();
    const b = make();
    const blend = uniform(0);
    const m = new THREE.MeshStandardNodeMaterial({ transparent: true, depthWrite: false, roughness: 1 });
    const v = mix(texture(a).r, texture(b).r, blend);
    const glow = smoothstep(0.04, 1, v).pow(0.85);
    m.colorNode = vec4(0, 0, 0, glow.mul(0.8));
    m.emissiveNode = color(TUMOR_COLORS.field[name] ?? TUMOR_COLORS.trail).mul(glow.mul(1.3));
    return { a, b, blend, m, loaded: [-2, -2] };
  }, [series, name]);
  useEffect(() => () => { state.a.dispose(); state.b.dispose(); state.m.dispose(); }, [state]);

  useFrame(() => {
    const p = Math.min(Math.max(playhead.current, 0), steps - 1);
    const s = Math.floor(p);
    const ia = index[s];
    const ib = index[Math.min(s + 1, steps - 1)];
    if (state.loaded[0] !== ia) { fillTexture(state.a, series, ia); state.loaded[0] = ia; }
    if (state.loaded[1] !== ib) { fillTexture(state.b, series, ib); state.loaded[1] = ib; }
    state.blend.value = ia === ib ? 0 : p - s;
  });

  const w = series.width * series.cellSize;
  const h = series.height * series.cellSize;
  const cx = series.origin[0] + ((series.width - 1) / 2) * series.cellSize;
  const cz = series.origin[2] + ((series.height - 1) / 2) * series.cellSize;
  return (
    <mesh position={[cx, 0.012, cz]} rotation={[-Math.PI / 2, 0, 0]} material={state.m} renderOrder={1}>
      <planeGeometry args={[w, h]} />
    </mesh>
  );
}

/** Per-bot positions at every step, for comet tails sampled at any fractional playhead. */
function botPaths(model: ViewModel) {
  const ids = [...new Set(model.frames.flatMap((f) => f.filter((a) => a.kind === "bot").map((a) => a.id)))];
  const slot = new Map(ids.map((id, i) => [id, i]));
  const xyz = new Float32Array(ids.length * model.steps * 3).fill(NaN);
  model.frames.forEach((frame, s) => {
    for (const a of frame) {
      const i = slot.get(a.id);
      if (i === undefined || a.kind !== "bot") continue;
      xyz.set(a.pos, (i * model.steps + s) * 3);
    }
  });
  return { ids, xyz };
}

const TAIL = 14;
const TAIL_SPACING = 0.22; // steps between tail beads

/** Glowing comet tails behind every nanobot, in each bot's current state color. */
function Tails({ model, poses, playhead, colorOf }: {
  model: ViewModel;
  poses: PoseRef;
  playhead: React.MutableRefObject<number>;
  colorOf: (pose: Pose) => THREE.Color;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const paths = useMemo(() => botPaths(model), [model]);
  const tmp = useMemo(() => ({ o: new THREE.Object3D(), c: new THREE.Color(), d: new THREE.Color() }), []);
  const capacity = Math.max(1, paths.ids.length * TAIL);
  const colors = useInstanceColors(capacity);
  const steps = model.steps;

  useFrame(() => {
    const m = mesh.current;
    if (!m) return;
    const at = (i: number, s: number, k: number) => paths.xyz[(i * steps + s) * 3 + k];
    let n = 0;
    paths.ids.forEach((id, i) => {
      const pose = poses.current.byId.get(id);
      if (!pose) return;
      tmp.c.copy(colorOf(pose));
      for (let k = 1; k <= TAIL; k++) {
        const q = playhead.current - k * TAIL_SPACING;
        if (q < 0) break;
        const s = Math.min(Math.floor(q), steps - 1);
        const s2 = Math.min(s + 1, steps - 1);
        if (Number.isNaN(at(i, s, 0))) break;
        let t = q - s;
        if (Number.isNaN(at(i, s2, 0)) || Math.hypot(at(i, s2, 0) - at(i, s, 0), at(i, s2, 2) - at(i, s, 2)) > MAX_JUMP) {
          if (t >= 0.5) break; // the tail ends at a respawn
          t = 0;
        }
        const fade = 1 - k / (TAIL + 1);
        tmp.o.position.set(at(i, s, 0) + (at(i, s2, 0) - at(i, s, 0)) * t, HOVER, at(i, s, 2) + (at(i, s2, 2) - at(i, s, 2)) * t);
        tmp.o.scale.setScalar(fade * pose.presence);
        tmp.o.updateMatrix();
        m.setMatrixAt(n, tmp.o.matrix);
        m.setColorAt(n, tmp.d.copy(tmp.c).multiplyScalar(fade));
        n++;
      }
    });
    m.count = n;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, capacity]} frustumCulled={false}>
      <instancedBufferAttribute attach="instanceColor" args={colors} />
      <sphereGeometry args={[0.016, 8, 6]} />
      <meshStandardNodeMaterial color="#000000" emissiveNode={instanceColor.mul(1.4)} transparent blending={THREE.AdditiveBlending} depthWrite={false} />
    </instancedMesh>
  );
}

/** Thin beams from each nanobot to the cell it is going after. */
function TargetBeams({ poses, capacity, selected }: { poses: PoseRef; capacity: number; selected: string | null }) {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(Math.max(1, capacity) * 6), 3));
    return g;
  }, [capacity]);
  const focus = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
    return g;
  }, []);
  useEffect(() => () => { geometry.dispose(); focus.dispose(); }, [geometry, focus]);
  const line = useMemo(() => new THREE.LineSegments(geometry, new THREE.LineBasicNodeMaterial({ color: TUMOR_COLORS.trail, transparent: true, opacity: 0.22, depthWrite: false })), [geometry]);
  const lineFocus = useMemo(() => new THREE.LineSegments(focus, new THREE.LineBasicNodeMaterial({ color: "#ffffff", transparent: true, opacity: 0.8, depthWrite: false })), [focus]);
  useEffect(() => () => { (line.material as THREE.Material).dispose(); (lineFocus.material as THREE.Material).dispose(); }, [line, lineFocus]);

  useFrame(() => {
    const pos = geometry.attributes.position as THREE.BufferAttribute;
    const fpos = focus.attributes.position as THREE.BufferAttribute;
    let n = 0;
    lineFocus.visible = false;
    for (const p of poses.current.list) {
      if (p.kind !== "bot" || n >= capacity) continue;
      const target = p.attrs?.target;
      const cell = target === null || target === undefined ? undefined : poses.current.byId.get(`cell:${target}`);
      if (!cell) continue;
      const seg = [p.pos[0], HOVER, p.pos[2], cell.pos[0], 0.08, cell.pos[2]];
      if (p.id === selected) { fpos.set(seg); fpos.needsUpdate = true; lineFocus.visible = true; continue; }
      pos.set(seg, n * 6);
      n++;
    }
    geometry.setDrawRange(0, n * 2);
    pos.needsUpdate = true;
  });

  return (
    <>
      <primitive object={line} frustumCulled={false} />
      <primitive object={lineFocus} frustumCulled={false} />
    </>
  );
}

/** A flash ring where a delivery kills a cell, for a moment after it happens. */
function KillBursts({ events, playhead }: { events: WorldEvent[]; playhead: React.MutableRefObject<number> }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const kills = useMemo(() => events.filter((e) => e.kind === "kill").sort((a, b) => a.step - b.step), [events]);
  const tmp = useMemo(() => ({ o: new THREE.Object3D(), c: new THREE.Color(), base: new THREE.Color(TUMOR_COLORS.cell.apoptotic) }), []);
  const capacity = 64;
  const colors = useInstanceColors(capacity);
  useFrame(() => {
    const m = mesh.current;
    if (!m) return;
    const p = playhead.current;
    let n = 0;
    for (const e of kills) {
      if (e.step > p) break;
      const age = p - e.step;
      if (age > 1.4 || n >= capacity) continue;
      const k = age / 1.4;
      tmp.o.position.set(e.pos[0], 0.03, e.pos[2]);
      tmp.o.rotation.set(-Math.PI / 2, 0, 0);
      tmp.o.scale.setScalar(0.4 + k * 2.6);
      tmp.o.updateMatrix();
      m.setMatrixAt(n, tmp.o.matrix);
      m.setColorAt(n, tmp.c.copy(tmp.base).multiplyScalar((1 - k) * (1 - k)));
      n++;
    }
    m.count = n;
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
  });
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, capacity]} frustumCulled={false}>
      <instancedBufferAttribute attach="instanceColor" args={colors} />
      <ringGeometry args={[0.07, 0.085, 40]} />
      <meshStandardNodeMaterial color="#000000" emissiveNode={instanceColor.mul(2.5)} transparent blending={THREE.AdditiveBlending} depthWrite={false} side={THREE.DoubleSide} />
    </instancedMesh>
  );
}

/** Slow drifting specks in the fluid above the tissue, for depth. */
function Motes({ span, count = 140 }: { span: number; count?: number }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const seeds = useMemo(() => {
    let s = 7;
    const rand = () => ((s = (s * 16807) % 2147483647) / 2147483647);
    return Array.from({ length: count }, () => [rand() - 0.5, rand(), rand() - 0.5, rand() * 10, 0.4 + rand() * 0.8]);
  }, [count]);
  const o = useMemo(() => new THREE.Object3D(), []);
  useFrame(({ clock }) => {
    const m = mesh.current;
    if (!m) return;
    const t = clock.elapsedTime;
    seeds.forEach(([x, y, z, ph, sz], i) => {
      o.position.set(x * span * 1.2 + Math.sin(t * 0.13 + ph) * 0.3, 0.15 + ((y + t * 0.012 * sz) % 1) * span * 0.35, z * span * 1.2 + Math.cos(t * 0.11 + ph) * 0.3);
      o.scale.setScalar(sz * (0.7 + 0.3 * Math.sin(t * 1.3 + ph)));
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    m.instanceMatrix.needsUpdate = true;
  });
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, count]} frustumCulled={false}>
      <sphereGeometry args={[0.008, 6, 4]} />
      <meshStandardNodeMaterial color="#000000" emissive={TUMOR_COLORS.mote} emissiveIntensity={0.9} transparent opacity={0.6} blending={THREE.AdditiveBlending} depthWrite={false} />
    </instancedMesh>
  );
}

const isBot = (p: Pose) => p.kind === "bot";
const isCell = (p: Pose) => p.kind === "cell";
const isSignal = (p: Pose) => p.kind === "signal";
/** Stable per-thing phase offset from its position, so breathing and bobbing aren't in sync. */
const phaseOf = (p: Pose) => p.pos[0] * 12.9898 + p.pos[2] * 78.233;

/**
 * A tumor run as a glowing tissue diorama: cells by phase with rim-lit
 * membranes under a glass lens, beating capillaries, nanobots that glow by
 * state and leave comet tails, beams to their targets, flashes on kills, and
 * the selected field glowing up through the tissue.
 */
export function TumorScene3D({ model, poses, playhead, span, radius, vessels, layer, selected, onSelect }: {
  model: ViewModel;
  poses: PoseRef;
  playhead: React.MutableRefObject<number>;
  /** Domain width in scene units. */
  span: number;
  /** Tumor radius in scene units. */
  radius: number;
  vessels: Array<[number, number, number]>;
  layer: string | null;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const geo = useMemo(() => ({ bot: botGeometry(), cell: cellGeometry(), signal: new THREE.OctahedronGeometry(0.045) }), []);
  useEffect(() => () => Object.values(geo).forEach((g) => g.dispose()), [geo]);
  const colors = useMemo(() => ({
    bot: Object.fromEntries(Object.entries(TUMOR_COLORS.bot).map(([k, v]) => [k, new THREE.Color(v)])) as Record<string, THREE.Color>,
    cell: Object.fromEntries(Object.entries(TUMOR_COLORS.cell).map(([k, v]) => [k, new THREE.Color(v)])) as Record<string, THREE.Color>,
    signal: Object.fromEntries(Object.entries(TUMOR_COLORS.signal).map(([k, v]) => [k, new THREE.Color(v)])) as Record<string, THREE.Color>,
  }), []);
  const botColor = useMemo(() => (p: Pose) => colors.bot[String(p.attrs?.state)] ?? colors.bot.searching, [colors]);
  const capacity = useMemo(() => {
    const most: Record<string, number> = { bot: 1, cell: 1, signal: 1 };
    for (const frame of model.frames) {
      const count: Record<string, number> = {};
      for (const a of frame) count[a.kind] = (count[a.kind] ?? 0) + 1;
      for (const k of Object.keys(most)) most[k] = Math.max(most[k], count[k] ?? 0);
    }
    return most;
  }, [model]);

  // Cells: rim-lit membranes; bots and signals glow in their own instance color.
  const cellMaterial = useMemo(() => {
    const m = new THREE.MeshPhysicalNodeMaterial({ roughness: 0.38, clearcoat: 0.7, clearcoatRoughness: 0.25, sheen: 0.6, sheenRoughness: 0.5 });
    m.emissiveNode = instanceColor.mul(fresnel(2).mul(0.85).add(0.05));
    return m;
  }, []);
  useEffect(() => () => cellMaterial.dispose(), [cellMaterial]);

  const field = layer ? model.fields[layer] : undefined;
  return (
    <>
      <color attach="background" args={[TUMOR_COLORS.sky]} />
      <fog attach="fog" args={[TUMOR_COLORS.sky, span * 1.3, span * 3.5]} />
      <hemisphereLight args={["#ffd6e8", "#1a0612", 0.55]} />
      <directionalLight
        position={[span * 0.35, span * 0.9, span * 0.25]}
        intensity={2.2}
        color="#ffe9f1"
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
      <directionalLight position={[-span * 0.6, span * 0.3, -span * 0.8]} intensity={1.1} color="#5b8cff" />

      <Tissue span={span} />
      {field && layer && <FieldGlow key={layer} series={field} steps={model.steps} name={layer} playhead={playhead} />}
      <Boundary radius={radius} />
      {vessels.map((v, i) => <Vessel key={i} position={v} phase={i * 1.7} />)}

      <Swarm poses={poses} match={isCell} capacity={capacity.cell} style={(p, t) => {
        const phase = String(p.attrs?.phase);
        const dead = phase === "necrotic" ? 0.62 : phase === "apoptotic" ? 0.82 : 1;
        return { color: colors.cell[phase] ?? colors.cell.viable, scale: dead * (1 + Math.sin(t * 1.6 + phaseOf(p)) * 0.045) };
      }}>
        <primitive object={geo.cell} attach="geometry" />
        <primitive object={cellMaterial} attach="material" />
      </Swarm>

      <Tails model={model} poses={poses} playhead={playhead} colorOf={botColor} />
      <TargetBeams poses={poses} capacity={capacity.bot} selected={selected} />
      <KillBursts events={model.events} playhead={playhead} />

      <Swarm poses={poses} match={isBot} capacity={capacity.bot} selected={selected} onSelect={onSelect} style={(p, t) => ({
        color: botColor(p),
        lift: HOVER + Math.sin(t * 3 + phaseOf(p)) * 0.02,
        scale: 0.85 + Math.min(1, Math.max(0, Number(p.attrs?.payload ?? 0) / 20)) * 0.3,
      })}>
        <primitive object={geo.bot} attach="geometry" />
        <meshStandardNodeMaterial roughness={0.22} metalness={0.65} emissiveNode={instanceColor.mul(1.6)} />
      </Swarm>

      <Swarm poses={poses} match={isSignal} capacity={capacity.signal} castShadow={false} style={(p, t) => ({
        color: colors.signal[String(p.attrs?.signal)] ?? colors.signal.other,
        lift: 0.5 + Math.sin(t * 2.2 + phaseOf(p)) * 0.04,
        scale: 0.55 + Math.min(1, Number(p.attrs?.ttl ?? 0) / 20) * 0.6,
      })}>
        <primitive object={geo.signal} attach="geometry" />
        <meshStandardNodeMaterial color="#000000" emissiveNode={instanceColor.mul(1.5)} transparent opacity={0.85} />
      </Swarm>

      <Motes span={span} />
      <SelectionRing poses={poses} selected={selected} color={TUMOR_COLORS.bot.searching} radius={0.16} />
    </>
  );
}
