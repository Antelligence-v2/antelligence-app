import * as THREE from "three/webgpu";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

/** Nanobot facing +z: a capsule hull with a ring around its waist and a nose sensor (~0.14 units long). */
export function botGeometry(): THREE.BufferGeometry {
  const hull = new THREE.CapsuleGeometry(0.032, 0.07, 6, 16);
  hull.rotateX(Math.PI / 2);
  const ring = new THREE.TorusGeometry(0.05, 0.008, 8, 32);
  const nose = new THREE.SphereGeometry(0.016, 12, 8);
  nose.translate(0, 0, 0.07);
  return mergeGeometries([hull, ring, nose])!;
}

/** A tumor cell: a slightly squashed, finely faceted blob resting on y = 0. */
export function cellGeometry(): THREE.BufferGeometry {
  const g = new THREE.IcosahedronGeometry(0.07, 3);
  g.scale(1, 0.78, 1);
  g.translate(0, 0.055, 0);
  return g;
}
