import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Label3D } from './Label3D';

interface VesselState {
  position: [number, number, number];
  supply_radius: number;
}

interface BloodVessel3DProps {
  vessel: VesselState;
  index: number;
  detailedMode?: boolean;
  connectedVessels?: VesselState[];
  showLabel?: boolean; // Only show label for one vessel
}

export function BloodVessel3D({ vessel, index, detailedMode = false, connectedVessels = [], showLabel = false }: BloodVessel3DProps) {
  const vesselRef = useRef<THREE.Mesh>(null);
  const supplyRef = useRef<THREE.Mesh>(null);
  const glowRef = useRef<THREE.Mesh>(null);
  
  // Calculate vessel properties
  const vesselLength = 30; // Increased length
  const vesselRadius = 10; // Increased radius for better visibility
  const supplyRadius = vessel.supply_radius;

  // Create curved vessel geometry
  const vesselGeometry = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(-vesselLength / 2, 0, 0),
      new THREE.Vector3(0, Math.sin(index) * 5, Math.cos(index) * 3),
      new THREE.Vector3(vesselLength / 2, 0, 0)
    );
    
    const points = curve.getPoints(32);
    const geometry = new THREE.TubeGeometry(
      new THREE.CatmullRomCurve3(points),
      32,
      vesselRadius,
      8,
      false
    );
    
    return geometry;
  }, [vesselLength, vesselRadius, index]);

  // Enhanced pulsing animation with multiple frequencies
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    // Primary pulse (heartbeat)
    const primaryPulse = Math.sin(time * 1.5 + index * 0.3) * 0.2 + 0.8;
    
    // Secondary pulse (blood flow)
    const secondaryPulse = Math.sin(time * 3 + index * 0.7) * 0.1 + 0.9;
    
    // Combined pulse
    const pulseIntensity = primaryPulse * secondaryPulse;
    
    if (vesselRef.current) {
      vesselRef.current.scale.setScalar(pulseIntensity);
      // Add slight rotation for blood flow effect
      vesselRef.current.rotation.z += 0.001;
    }
    
    if (supplyRef.current) {
      supplyRef.current.scale.setScalar(pulseIntensity);
      // Breathing effect for supply radius
      const breathe = Math.sin(time * 0.8 + index * 0.4) * 0.05 + 1.0;
      supplyRef.current.scale.setScalar(pulseIntensity * breathe);
    }
    
    if (glowRef.current) {
      glowRef.current.scale.setScalar(pulseIntensity * 1.2);
      // Pulsing glow intensity
      const glowIntensity = Math.sin(time * 2 + index * 0.5) * 0.3 + 0.7;
      if (glowRef.current.material) {
        (glowRef.current.material as THREE.MeshPhongMaterial).opacity = 0.1 + glowIntensity * 0.2;
      }
    }
  });

  // Create connection lines to nearby vessels
  const connections = useMemo(() => {
    if (!detailedMode || connectedVessels.length === 0) return null;
    
    const nearbyVessels = connectedVessels.filter((other, otherIndex) => 
      otherIndex !== index && 
      vessel.position.distanceTo(new THREE.Vector3(...other.position)) < supplyRadius * 2
    );
    
    return nearbyVessels.map((other, connectionIndex) => {
      const start = new THREE.Vector3(...vessel.position);
      const end = new THREE.Vector3(...other.position);
      const mid = start.clone().lerp(end, 0.5);
      mid.y += Math.sin(connectionIndex) * 3; // Add curve to connections
      
      const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
      const points = curve.getPoints(20);
      
      return (
        <line key={`connection-${connectionIndex}`}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              count={points.length}
              array={new Float32Array(points.flatMap(p => [p.x, p.y, p.z]))}
              itemSize={3}
            />
          </bufferGeometry>
          <lineBasicMaterial color={0x22c55e} transparent opacity={0.6} />
        </line>
      );
    });
  }, [vessel.position, connectedVessels, index, supplyRadius, detailedMode]);

  return (
    <group position={vessel.position}>
      {/* Main vessel body with curved geometry */}
      <mesh ref={vesselRef}>
        <primitive object={vesselGeometry} />
        <meshPhongMaterial 
          color={0x22c55e}
          emissive={0x16a34a}
          transparent
          opacity={1.0}
          shininess={100}
          specular={0x4ade80}
        />
      </mesh>
      
      {/* Inner vessel lumen - brighter */}
      <mesh ref={glowRef}>
        <primitive object={vesselGeometry} />
        <meshPhongMaterial 
          color={0x4ade80}
          emissive={0x22c55e}
          transparent
          opacity={0.5}
        />
      </mesh>
      
      {/* Supply radius visualization with gradient - more visible */}
      <mesh ref={supplyRef}>
        <sphereGeometry args={[supplyRadius, 32, 32]} />
        <meshPhongMaterial 
          color={0x22c55e} 
          transparent 
          opacity={0.15}
          emissive={0x16a34a}
        />
      </mesh>
      
      {/* Outer supply glow - more visible */}
      <mesh ref={supplyRef}>
        <sphereGeometry args={[supplyRadius * 1.2, 16, 16]} />
        <meshPhongMaterial 
          color={0x22c55e} 
          transparent 
          opacity={0.08}
        />
      </mesh>
      
      {/* Vessel connections */}
      {connections}
      
      {/* Enhanced vessel highlight in detailed mode */}
      {detailedMode && (
        <group>
          {/* Vessel core highlight - brighter */}
          <mesh>
            <primitive object={vesselGeometry} />
            <meshBasicMaterial 
              color={0x4ade80} 
              transparent 
              opacity={0.6}
              wireframe
            />
          </mesh>
          
          {/* Flow direction indicators - larger and brighter */}
          <mesh position={[vesselLength / 2 - 2, 0, 0]}>
            <coneGeometry args={[3, 6, 8]} />
            <meshBasicMaterial color={0x22c55e} />
          </mesh>
          
          {/* Supply radius boundary - more visible */}
          <mesh>
            <sphereGeometry args={[supplyRadius, 16, 16]} />
            <meshBasicMaterial 
              color={0x22c55e} 
              transparent
              opacity={0.2}
              wireframe
            />
          </mesh>
          
          {/* Vessel label */}
          <Label3D
            position={[vesselLength / 2 + 10, 0, 5]}
            text={`Blood Vessel (O₂+Drug)`}
            color="#16a34a"
            fontSize={10}
            backgroundColor="rgba(34, 197, 94, 0.9)"
            show={detailedMode}
          />
        </group>
      )}
      
      {/* Always-visible vessel label (only for first vessel) */}
      {showLabel && (
        <Label3D
          position={[vesselLength / 2 + 8, 0, 5]}
          text={`🟢 Blood Vessel`}
          color="#ffffff"
          fontSize={9}
          backgroundColor="rgba(34, 197, 94, 0.85)"
          show={true}
        />
      )}
    </group>
  );
}
