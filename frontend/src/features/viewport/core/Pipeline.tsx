import { useEffect, useMemo } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three/webgpu";
import { emissive, float, mix, mrt, normalView, output, pass, renderOutput, vec4 } from "three/tsl";
import { ao } from "three/addons/tsl/display/GTAONode.js";
import { bloom } from "three/addons/tsl/display/BloomNode.js";
import { smaa } from "three/addons/tsl/display/SMAANode.js";

export type Quality = "high" | "low";

/**
 * The shared post-processing stack, rendered in one scene pass with MRT:
 *  - ambient occlusion (GTAO, half resolution) grounds objects on surfaces
 *  - bloom driven only by emissive materials, so only "lit" things glow
 *  - SMAA for clean edges after tone mapping
 * "low" skips AO. Works on both WebGPU and the WebGL 2 fallback.
 * Mount inside <Stage>; it takes over rendering (useFrame priority 1).
 */
export function Pipeline({ quality = "high", aoStrength = 0.8, bloomStrength = 0.9 }: {
  quality?: Quality;
  aoStrength?: number;
  bloomStrength?: number;
}) {
  const gl = useThree((s) => s.gl) as unknown as THREE.WebGPURenderer;
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);

  const { pipeline, nodes } = useMemo(() => {
    const p = new THREE.RenderPipeline(gl);
    const scenePass = pass(scene, camera);
    scenePass.setMRT(mrt({ output, emissive, normal: normalView }));
    const color = scenePass.getTextureNode("output");

    let lit = color.rgb;
    let aoPass: ReturnType<typeof ao> | null = null;
    if (quality === "high") {
      aoPass = ao(scenePass.getTextureNode("depth"), scenePass.getTextureNode("normal"), camera);
      aoPass.resolutionScale = 0.5;
      lit = lit.mul(mix(float(1), aoPass.getTextureNode().r, aoStrength));
    }
    const glow = bloom(scenePass.getTextureNode("emissive"), bloomStrength, 0.45, 0);
    const composed = vec4(lit.add(glow.rgb), color.a);

    p.outputColorTransform = false; // tone map before SMAA, which expects display-referred color
    const aa = smaa(renderOutput(composed));
    p.outputNode = aa;
    return { pipeline: p, nodes: [scenePass, aoPass, glow, aa] };
  }, [gl, scene, camera, quality, aoStrength, bloomStrength]);

  // RenderPipeline.dispose() only frees its own quad; each pass owns render targets.
  useEffect(() => () => {
    pipeline.dispose();
    for (const node of nodes) node?.dispose();
  }, [pipeline, nodes]);
  useFrame(() => pipeline.render(), 1);
  return null;
}
