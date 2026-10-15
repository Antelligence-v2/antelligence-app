import * as THREE from "three/webgpu";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

/** A body segment: a sphere squashed to (sx, sy, sz) at z. */
function segment(sx: number, sy: number, sz: number, z: number, y = 0) {
  const g = new THREE.SphereGeometry(1, 14, 10);
  g.scale(sx, sy, sz);
  g.translate(0, y, z);
  return g;
}

/** Pairs of thin legs splayed sideways and down from the body at each z. */
function legs(zs: number[], length: number, thickness: number, y: number) {
  return zs.flatMap((z, i) =>
    [-1, 1].map((side) => {
      const g = new THREE.CylinderGeometry(thickness, thickness * 0.6, length, 5);
      g.rotateZ(side * (Math.PI / 2 - 0.5)); // splay outward and down
      g.rotateY(side * (i - (zs.length - 1) / 2) * 0.45); // fan front/back legs
      g.translate(side * length * 0.42, y - length * 0.18, z);
      return g;
    }),
  );
}

/** Low-poly ant facing +z, standing on y = 0 (about 0.5 units long). */
export function antGeometry(): THREE.BufferGeometry {
  const y = 0.1;
  const merged = mergeGeometries([
    segment(0.1, 0.085, 0.14, -0.15, y + 0.01), // abdomen
    segment(0.055, 0.05, 0.08, 0.0, y), // thorax
    segment(0.06, 0.055, 0.06, 0.12, y + 0.005), // head
    ...legs([-0.04, 0.0, 0.04], 0.26, 0.009, y),
    ...[-1, 1].map((side) => { // antennae
      const g = new THREE.CylinderGeometry(0.006, 0.004, 0.16, 4);
      g.rotateX(Math.PI / 2 - 0.6);
      g.rotateY(side * 0.45);
      g.translate(side * 0.03, y + 0.07, 0.2);
      return g;
    }),
  ])!;
  return merged;
}

/** A small heap of seeds/crumbs centered on y = 0. */
export function foodGeometry(): THREE.BufferGeometry {
  const pieces: Array<[number, number, number, number]> = [
    [0, 0.09, 0, 0.11], [0.11, 0.06, 0.05, 0.075], [-0.09, 0.06, 0.07, 0.07],
    [0.03, 0.05, -0.11, 0.07], [-0.06, 0.16, -0.03, 0.06],
  ];
  return mergeGeometries(pieces.map(([x, y, z, r]) => {
    const g = new THREE.IcosahedronGeometry(r, 1);
    g.translate(x, y, z);
    return g;
  }))!;
}
