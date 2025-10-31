import React, { useMemo } from 'react';
import * as THREE from 'three';

interface SubstrateField3DProps {
  data: number[][];
  maxValue: number;
  substrateType: string;
  domainSize: number;
  opacity?: number;
}

export function SubstrateField3D({ 
  data, 
  maxValue, 
  substrateType, 
  domainSize, 
  opacity = 0.2 
}: SubstrateField3DProps) {
  // Create a texture from the substrate data
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    const size = data.length;
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) return null;

    // Create image data
    const imageData = ctx.createImageData(size, size);
    const pixels = imageData.data;

    for (let i = 0; i < size; i++) {
      for (let j = 0; j < size; j++) {
        const value = data[j][i]; // Transposed
        const normalized = Math.min(value / maxValue, 1);
        
        const index = (i * size + j) * 4;
        
        // Color mapping based on substrate type
        let r, g, b;
        switch (substrateType) {
          case "oxygen":
            // Blue (low O2) to Red (high O2)
            r = Math.floor(255 * normalized);
            g = Math.floor(100 * normalized);
            b = Math.floor(255 * (1 - normalized));
            break;
          case "drug":
            // Orange gradient
            r = Math.floor(255 * normalized);
            g = Math.floor(165 * normalized);
            b = 0;
            break;
          case "trail":
            // Bright emerald green - more visible
            r = Math.floor(16 + 50 * normalized);
            g = Math.floor(200 + 55 * normalized);
            b = Math.floor(100 + 50 * normalized);
            break;
          case "alarm":
            // Bright red for danger - more visible
            r = Math.floor(200 + 55 * normalized);
            g = Math.floor(50 * normalized);
            b = Math.floor(50 * normalized);
            break;
          case "recruitment":
            // Bright blue for help needed - more visible
            r = Math.floor(50 * normalized);
            g = Math.floor(100 + 55 * normalized);
            b = Math.floor(200 + 55 * normalized);
            break;
          case "chemokine_signal":
            // Bright green for "come here"
            r = 34;
            g = Math.floor(255 * normalized);
            b = 100;
            break;
          case "toxicity_signal":
            // Dark red for "stay away"
            r = Math.floor(150 * normalized);
            g = 0;
            b = Math.floor(50 * normalized);
            break;
          default:
            r = Math.floor(128 * normalized);
            g = Math.floor(128 * normalized);
            b = Math.floor(128 * normalized);
        }
        
        pixels[index] = r;     // Red
        pixels[index + 1] = g; // Green
        pixels[index + 2] = b; // Blue
        pixels[index + 3] = Math.floor(255 * opacity * normalized); // Alpha
      }
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    // Create Three.js texture
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return texture;
  }, [data, maxValue, substrateType, opacity]);

  if (!texture) return null;

  return (
    <mesh position={[0, -domainSize / 2, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[domainSize, domainSize]} />
      <meshBasicMaterial 
        map={texture} 
        transparent 
        opacity={opacity}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}
