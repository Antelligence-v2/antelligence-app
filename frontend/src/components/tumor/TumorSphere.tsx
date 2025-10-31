import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ZoneLabel3D } from './Label3D';

interface TumorSphereProps {
  tumorRadius: number;
  detailedMode?: boolean;
}

export function TumorSphere({ tumorRadius, detailedMode = false }: TumorSphereProps) {
  const necroticRef = useRef<THREE.Mesh>(null);
  const hypoxicRef = useRef<THREE.Mesh>(null);
  const viableRef = useRef<THREE.Mesh>(null);
  const boundaryRef = useRef<THREE.Mesh>(null);

  // Calculate zone radii
  const necroticRadius = tumorRadius * 0.25;
  const hypoxicRadius = tumorRadius * 0.70;
  const viableRadius = tumorRadius;

  // Subtle pulsing animation for the tumor
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    const pulseIntensity = Math.sin(time * 0.5) * 0.02 + 1.0;
    
    if (necroticRef.current) {
      necroticRef.current.scale.setScalar(pulseIntensity);
    }
    if (hypoxicRef.current) {
      hypoxicRef.current.scale.setScalar(pulseIntensity);
    }
    if (viableRef.current) {
      viableRef.current.scale.setScalar(pulseIntensity);
    }
  });

  return (
    <group>
      {/* Necrotic core (innermost) - Dark, dense, more transparent */}
      <mesh ref={necroticRef}>
        <sphereGeometry args={[necroticRadius, 32, 32]} />
        <meshPhongMaterial 
          color={0x2d1b69} 
          transparent 
          opacity={0.4}
          emissive={0x1a0d3d}
          shininess={30}
          specular={0x4c1d95}
        />
      </mesh>
      
      {/* Hypoxic zone (middle) - Purple, low oxygen, more transparent */}
      <mesh ref={hypoxicRef}>
        <sphereGeometry args={[hypoxicRadius, 32, 32]} />
        <meshPhongMaterial 
          color={0x7c3aed} 
          transparent 
          opacity={0.3}
          emissive={0x5b21b6}
          shininess={50}
          specular={0x8b5cf6}
        />
      </mesh>
      
      {/* Viable tumor (outer) - Red, active cancer cells, most transparent */}
      <mesh ref={viableRef}>
        <sphereGeometry args={[viableRadius, 32, 32]} />
        <meshPhongMaterial 
          color={0xef4444} 
          transparent 
          opacity={0.25}
          emissive={0xdc2626}
          shininess={40}
          specular={0xf87171}
        />
      </mesh>
      
      {/* Tumor boundary - Subtle wireframe, more visible */}
      <mesh ref={boundaryRef}>
        <sphereGeometry args={[viableRadius, 16, 16]} />
        <meshPhongMaterial 
          color={0xef4444} 
          wireframe
          transparent 
          opacity={0.4}
          emissive={0x7f1d1d}
        />
      </mesh>
      
      {/* Additional visual enhancement - Inner glow, more transparent */}
      <mesh>
        <sphereGeometry args={[necroticRadius * 0.8, 16, 16]} />
        <meshPhongMaterial 
          color={0x1e1b4b} 
          transparent 
          opacity={0.3}
          emissive={0x312e81}
        />
      </mesh>
      
      {/* Biological texture - Inner structure lines */}
      <mesh>
        <sphereGeometry args={[viableRadius * 0.95, 32, 32]} />
        <meshPhongMaterial 
          color={0xef4444} 
          wireframe
          transparent 
          opacity={0.1}
          emissive={0x7f1d1d}
        />
      </mesh>
      
      {/* Core highlight */}
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[necroticRadius * 0.3, 8, 8]} />
        <meshPhongMaterial 
          color={0x0f0f23} 
          transparent 
          opacity={0.9}
          emissive={0x1e1b4b}
        />
      </mesh>
      
      {/* Zone labels in detailed mode */}
      {detailedMode && (
        <group>
          {/* Zone labels - positioned around the sphere */}
          <ZoneLabel3D 
            position={[necroticRadius * 0.7, necroticRadius * 0.7, 0]}
            zoneName="Necrotic Core"
            radius={necroticRadius}
            show={detailedMode}
          />
          <ZoneLabel3D 
            position={[hypoxicRadius * 0.8, -hypoxicRadius * 0.8, 0]}
            zoneName="Hypoxic Zone"
            radius={hypoxicRadius}
            show={detailedMode}
          />
          <ZoneLabel3D 
            position={[-viableRadius * 0.9, 0, viableRadius * 0.9]}
            zoneName="Viable Tumor"
            radius={viableRadius}
            show={detailedMode}
          />
          
          {/* Zone indicators (visual markers) */}
          <mesh position={[necroticRadius + 5, 0, 0]}>
            <sphereGeometry args={[3, 8, 8]} />
            <meshBasicMaterial color={0x666666} />
          </mesh>
          
          <mesh position={[hypoxicRadius + 5, 0, 0]}>
            <sphereGeometry args={[2, 8, 8]} />
            <meshBasicMaterial color={0xa855f7} />
          </mesh>
          
          <mesh position={[viableRadius + 5, 0, 0]}>
            <sphereGeometry args={[2, 8, 8]} />
            <meshBasicMaterial color={0xef4444} />
          </mesh>
        </group>
      )}
      
      {/* Cross-section indicators in detailed mode */}
      {detailedMode && (
        <group>
          {/* X-axis cross-section */}
          <mesh position={[viableRadius + 30, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
            <planeGeometry args={[viableRadius * 2, viableRadius * 2]} />
            <meshBasicMaterial color={0xef4444} transparent opacity={0.1} />
          </mesh>
          
          {/* Y-axis cross-section */}
          <mesh position={[0, viableRadius + 30, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <planeGeometry args={[viableRadius * 2, viableRadius * 2]} />
            <meshBasicMaterial color={0xa855f7} transparent opacity={0.1} />
          </mesh>
        </group>
      )}
    </group>
  );
}
