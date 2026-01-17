import React, { useRef, useMemo, useState, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Html, Sparkles, Float } from '@react-three/drei';
import { Label3D } from './Label3D';

interface NanobotState {
  id: number;
  position: [number, number, number] | [number, number];
  state: string;
  drug_payload: number;
  is_llm: boolean;
}

interface Nanobot3DProps {
  nanobot: NanobotState;
  previousPosition?: [number, number] | [number, number, number];
  detailedMode?: boolean;
  onClick?: (id: number) => void;
  isFocused?: boolean;
}

export function Nanobot3D({ nanobot, previousPosition, detailedMode = false, onClick, isFocused = false }: Nanobot3DProps) {
  const groupRef = useRef<THREE.Group>(null);
  const coreRef = useRef<THREE.Mesh>(null);
  const shellRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  
  // Smooth state transitions
  const [currentColor, setCurrentColor] = useState(0x6b7280);
  const [currentEmissive, setCurrentEmissive] = useState(0x374151);
  const [currentScale, setCurrentScale] = useState(1.0);

  // Extract Z if available, or use default
  const zPos = nanobot.position[2] !== undefined ? nanobot.position[2] : 5;
  const position3D: [number, number, number] = [nanobot.position[0], nanobot.position[1], zPos];
  
  // Calculate movement direction for rotation
  const direction = useMemo(() => {
    if (!previousPosition) return [0, 0, 1];
    const dx = nanobot.position[0] - previousPosition[0];
    const dy = nanobot.position[1] - previousPosition[1];
    const dz = (nanobot.position[2] || 0) - (previousPosition[2] || 0);
    return [dx, dy, dz];
  }, [nanobot.position, previousPosition]);

  // Get state-based colors and properties
  const getStateProperties = (state: string) => {
    switch (state) {
      case "targeting":
        return { color: 0xfbbf24, emissive: 0xffa500, scale: 1.2, intensity: 2.0 };
      case "delivering":
        return { color: 0x10b981, emissive: 0x34d399, scale: 1.1, intensity: 3.0 };
      case "returning":
        return { color: 0x3b82f6, emissive: 0x60a5fa, scale: 1.0, intensity: 1.5 };
      case "reloading":
        return { color: 0x8b5cf6, emissive: 0xa78bfa, scale: 1.1, intensity: 2.0 };
      default: // searching
        return { color: 0x9ca3af, emissive: 0x4b5563, scale: 1.0, intensity: 1.0 };
    }
  };

  const stateProps = getStateProperties(nanobot.state);

  // Smooth color transitions
  useEffect(() => {
    const targetColor = stateProps.color;
    const targetEmissive = stateProps.emissive;
    const targetScale = stateProps.scale;

    const transitionSpeed = 0.1;
    const updateTransition = () => {
      setCurrentColor(prev => prev + (targetColor - prev) * transitionSpeed);
      setCurrentEmissive(prev => prev + (targetEmissive - prev) * transitionSpeed);
      setCurrentScale(prev => prev + (targetScale - prev) * transitionSpeed);
    };

    const interval = setInterval(updateTransition, 16);
    return () => clearInterval(interval);
  }, [stateProps.color, stateProps.emissive, stateProps.scale]);

  // Animation loop
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    if (groupRef.current) {
      // Rotate towards movement direction
      if (Math.abs(direction[0]) > 0.01 || Math.abs(direction[1]) > 0.01) {
        const angleZ = Math.atan2(direction[1], direction[0]);
        // Smooth rotation
        groupRef.current.rotation.z += (angleZ - groupRef.current.rotation.z) * 0.1;
        
        // Add tilt based on speed (simulated by magnitude of direction if available, or just constant tilt)
        const speed = Math.sqrt(direction[0]**2 + direction[1]**2);
        const targetTilt = Math.min(speed * 0.2, 0.5); // Max tilt 0.5 rad
        groupRef.current.rotation.x = -targetTilt; // Tilt forward
      }
    }

    if (coreRef.current) {
       // Pulse core
       coreRef.current.scale.setScalar(1.0 + Math.sin(time * 3) * 0.1);
    }

    if (shellRef.current) {
      // Rotate shell opposite to movement or just spin
      shellRef.current.rotation.y -= 0.02;
      shellRef.current.rotation.z += 0.01;
    }
    
    if (ringRef.current && nanobot.is_llm) {
        ringRef.current.rotation.x = Math.sin(time) * 0.5;
        ringRef.current.rotation.y += 0.05;
    }
  });

  return (
    <group 
      position={position3D} 
      ref={groupRef}
      onClick={(e) => {
        e.stopPropagation();
        onClick && onClick(nanobot.id);
      }}
      onPointerOver={() => document.body.style.cursor = 'pointer'}
      onPointerOut={() => document.body.style.cursor = 'auto'}
    >
      <Float speed={4} rotationIntensity={0.2} floatIntensity={0.2}>
        {/* Selection Indicator - Ring when focused */}
        {isFocused && (
          <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -5, 0]}>
            <ringGeometry args={[8, 9, 32]} />
            <meshBasicMaterial color="#ffffff" opacity={0.6} transparent side={THREE.DoubleSide} />
          </mesh>
        )}

        {/* Core Payload - Glowing Sphere */}
        <mesh ref={coreRef}>
          <sphereGeometry args={[2.5, 16, 16]} />
          <meshStandardMaterial 
            color={currentColor}
            emissive={currentEmissive}
            emissiveIntensity={stateProps.intensity}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>

        {/* Outer Shell - Glassy Dodecahedron */}
        <mesh ref={shellRef}>
          <dodecahedronGeometry args={[4.5, 0]} />
          <meshPhysicalMaterial 
            color={0xffffff}
            transmission={0.6} // Glass-like
            opacity={0.3}
            transparent
            roughness={0.1}
            thickness={1}
            clearcoat={1}
          />
        </mesh>

        {/* LLM Indicator - Golden Ring */}
        {nanobot.is_llm && (
            <mesh ref={ringRef} rotation={[Math.PI / 2, 0, 0]}>
                <torusGeometry args={[6, 0.3, 8, 32]} />
                <meshStandardMaterial color="#ffd700" emissive="#ffa500" emissiveIntensity={2} />
            </mesh>
        )}
        
        {/* Tech Details - Small cubes or antennas */}
        <group>
             <mesh position={[3.5, 0, 0]}>
                <boxGeometry args={[1, 0.5, 0.5]} />
                <meshStandardMaterial color="#333" />
             </mesh>
             <mesh position={[-3.5, 0, 0]}>
                <boxGeometry args={[1, 0.5, 0.5]} />
                <meshStandardMaterial color="#333" />
             </mesh>
        </group>

        {/* Particle Effects - "Energy Field" */}
        {nanobot.drug_payload > 0 && (
             <Sparkles 
                count={15} 
                scale={8} 
                size={4} 
                speed={0.4} 
                opacity={0.6} 
                color={currentColor}
             />
        )}
      </Float>

      {/* Text Labels */}
      <Label3D
        position={[0, 0, 8]}
        text={`${nanobot.is_llm ? '🤖' : ''} ${nanobot.id}`}
        color="#ffffff"
        fontSize={10}
        backgroundColor="rgba(0,0,0,0.5)"
        show={true}
      />
      
      {detailedMode && (
        <Label3D
          position={[0, 0, 12]}
          text={`${nanobot.state.toUpperCase()} ${Math.round(nanobot.drug_payload)}%`}
          color={stateProps.color.toString(16).replace('0x', '#')}
          fontSize={8}
          backgroundColor="rgba(0,0,0,0.7)"
          show={true}
        />
      )}
    </group>
  );
}
