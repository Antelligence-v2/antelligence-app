import React from 'react';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

interface ScaleBar3DProps {
  domainSize: number;
  position?: [number, number, number];
}

export function ScaleBar3D({ domainSize, position = [0, 0, 0] }: ScaleBar3DProps) {
  // Position at bottom right corner
  const barLength = 100; // Length of scale bar in 3D units
  const barWidth = 3;
  const offsetX = domainSize / 2 - 120;
  const offsetY = -domainSize / 2 + 20;
  const offsetZ = -domainSize / 2;

  return (
    <group position={[offsetX, offsetY, offsetZ]}>
      {/* Scale bar line */}
      <mesh position={[barLength / 2, 0, 0]}>
        <boxGeometry args={[barLength, barWidth, barWidth]} />
        <meshBasicMaterial color={0x475569} />
      </mesh>
      
      {/* Scale bar label */}
      <Html position={[barLength / 2, -15, 0]} center>
        <div
          style={{
            color: '#e2e8f0',
            fontSize: '12px',
            fontWeight: 'bold',
            backgroundColor: 'rgba(15, 23, 42, 0.8)',
            padding: '2px 6px',
            borderRadius: '3px',
            whiteSpace: 'nowrap',
            pointerEvents: 'none',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
            transform: 'translate(-50%, 0)',
          }}
        >
          {domainSize} µm
        </div>
      </Html>
      
      {/* Start marker */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[2, barWidth * 2, barWidth * 2]} />
        <meshBasicMaterial color={0x64748b} />
      </mesh>
      
      {/* End marker */}
      <mesh position={[barLength, 0, 0]}>
        <boxGeometry args={[2, barWidth * 2, barWidth * 2]} />
        <meshBasicMaterial color={0x64748b} />
      </mesh>
    </group>
  );
}

