import React, { useRef, useMemo, useState, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Label3D } from './Label3D';

interface NanobotState {
  id: number;
  position: [number, number];
  state: string;
  drug_payload: number;
  is_llm: boolean;
}

interface Nanobot3DProps {
  nanobot: NanobotState;
  previousPosition?: [number, number];
  detailedMode?: boolean;
}

export function Nanobot3D({ nanobot, previousPosition, detailedMode = false }: Nanobot3DProps) {
  const nanobotRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const payloadRef = useRef<THREE.Mesh>(null);
  const directionRef = useRef<THREE.Mesh>(null);
  
  // Smooth state transitions
  const [currentColor, setCurrentColor] = useState(0x6b7280);
  const [currentEmissive, setCurrentEmissive] = useState(0x374151);
  const [currentScale, setCurrentScale] = useState(1.0);

  // Convert 2D position to 3D (add small Z offset for visibility)
  const position3D: [number, number, number] = [nanobot.position[0], nanobot.position[1], 5];
  
  // Calculate movement direction for rotation
  const direction = useMemo(() => {
    if (!previousPosition) return [0, 0, 1];
    const dx = nanobot.position[0] - previousPosition[0];
    const dy = nanobot.position[1] - previousPosition[1];
    return [dx, dy, 0];
  }, [nanobot.position, previousPosition]);

  // Get state-based colors and properties
  const getStateProperties = (state: string) => {
    switch (state) {
      case "targeting":
        return { color: 0xfbbf24, emissive: 0x92400e, scale: 1.3, glow: 0.8 };
      case "delivering":
        return { color: 0x10b981, emissive: 0x047857, scale: 1.1, glow: 1.0 };
      case "returning":
        return { color: 0x3b82f6, emissive: 0x1e40af, scale: 1.0, glow: 0.6 };
      case "reloading":
        return { color: 0x8b5cf6, emissive: 0x5b21b6, scale: 1.2, glow: 0.9 };
      default: // searching
        return { color: 0x6b7280, emissive: 0x374151, scale: 1.0, glow: 0.3 };
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
      setCurrentColor(prev => {
        const diff = targetColor - prev;
        return prev + diff * transitionSpeed;
      });
      setCurrentEmissive(prev => {
        const diff = targetEmissive - prev;
        return prev + diff * transitionSpeed;
      });
      setCurrentScale(prev => {
        const diff = targetScale - prev;
        return prev + diff * transitionSpeed;
      });
    };

    const interval = setInterval(updateTransition, 16);
    return () => clearInterval(interval);
  }, [stateProps.color, stateProps.emissive, stateProps.scale]);

  // Enhanced animation with direction-based rotation
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    if (nanobotRef.current) {
      // Enhanced floating animation with state-based behavior
      const floatAmplitude = stateProps.scale > 1.1 ? 0.8 : 0.5;
      const floatSpeed = nanobot.state === "targeting" ? 2.5 : 2.0;
      nanobotRef.current.position.z = 5 + Math.sin(time * floatSpeed + nanobot.id) * floatAmplitude;
      
      // State-based scaling with smooth transition
      nanobotRef.current.scale.setScalar(currentScale);
      
      // Rotate towards movement direction
      if (direction[0] !== 0 || direction[1] !== 0) {
        const angle = Math.atan2(direction[1], direction[0]);
        nanobotRef.current.rotation.z = angle;
        
        // Add tilt for movement
        const speed = Math.sqrt(direction[0] ** 2 + direction[1] ** 2);
        nanobotRef.current.rotation.x = Math.min(speed * 0.1, 0.3);
      }
      
      // Continuous rotation around Y-axis
      nanobotRef.current.rotation.y += 0.02;
    }
    
    // Enhanced LLM ring animation
    if (ringRef.current && nanobot.is_llm) {
      ringRef.current.rotation.z += 0.03;
      ringRef.current.rotation.y += 0.01;
      // Pulsing glow for LLM nanobots
      const glowIntensity = Math.sin(time * 3) * 0.2 + 0.6;
      if (ringRef.current.material) {
        (ringRef.current.material as THREE.MeshPhongMaterial).opacity = glowIntensity;
      }
    }
    
    // Drug payload pulsing
    if (payloadRef.current && nanobot.drug_payload > 0) {
      const pulse = Math.sin(time * 4) * 0.1 + 1.0;
      payloadRef.current.scale.setScalar(pulse);
    }
    
    // Direction indicator
    if (directionRef.current) {
      directionRef.current.position.set(
        direction[0] * 0.3,
        direction[1] * 0.3,
        direction[2] * 0.3 + 3
      );
    }
  });

  // Create a more detailed nanobot shape (rounded octahedron with additional geometry)
  const nanobotGeometry = useMemo(() => {
    const baseGeo = new THREE.OctahedronGeometry(4, 0);
    // Add small detail spheres at vertices for more detail
    return baseGeo;
  }, []);

  return (
    <group position={position3D}>
      {/* Main nanobot body - enhanced model - LARGER SIZE */}
      <mesh ref={nanobotRef}>
        <octahedronGeometry args={[6, 0]} />
        <meshPhongMaterial 
          color={currentColor}
          emissive={currentEmissive}
          transparent
          opacity={0.95}
          shininess={100}
          specular={0xffffff}
        />
      </mesh>
      
      {/* Additional geometry for detail - LARGER */}
      <mesh ref={nanobotRef}>
        <octahedronGeometry args={[5.5, 0]} />
        <meshBasicMaterial 
          color={currentColor}
          transparent
          opacity={0.3}
          wireframe
        />
      </mesh>
      
      {/* Drug payload indicator (inner core) - LARGER */}
      {nanobot.drug_payload > 0 && (
        <mesh ref={payloadRef}>
          <octahedronGeometry args={[4 * (nanobot.drug_payload / 100), 0]} />
          <meshPhongMaterial 
            color={nanobot.drug_payload > 50 ? 0x60a5fa : 0xf87171}
            emissive={nanobot.drug_payload > 50 ? 0x3b82f6 : 0xef4444}
            transparent
            opacity={0.9}
          />
        </mesh>
      )}
      
      {/* Enhanced LLM indicator ring - LARGER */}
      {nanobot.is_llm && (
        <group>
          <mesh ref={ringRef}>
            <ringGeometry args={[9, 11, 32]} />
            <meshPhongMaterial 
              color={0xfbbf24}
              emissive={0xf59e0b}
              transparent
              opacity={0.8}
            />
          </mesh>
          {/* Inner glow ring */}
          <mesh ref={ringRef}>
            <ringGeometry args={[8, 9, 32]} />
            <meshBasicMaterial 
              color={0xfbbf24}
              transparent
              opacity={0.5}
            />
          </mesh>
        </group>
      )}
      
      {/* Direction indicator in detailed mode */}
      {detailedMode && (
        <mesh ref={directionRef}>
          <coneGeometry args={[1, 3, 8]} />
          <meshBasicMaterial 
            color={stateProps.color}
            transparent
            opacity={0.8}
          />
        </mesh>
      )}
      
      {/* State glow effect */}
      {nanobot.state === "targeting" || nanobot.state === "delivering" ? (
        <mesh ref={nanobotRef}>
          <octahedronGeometry args={[5, 0]} />
          <meshBasicMaterial 
            color={stateProps.color}
            transparent
            opacity={0.2}
          />
        </mesh>
      ) : null}
      
      {/* State label in detailed mode */}
      {detailedMode && (
        <Label3D
          position={[0, 0, 12]}
          text={`${nanobot.is_llm ? '🤖 ' : ''}${nanobot.state.toUpperCase()}${nanobot.drug_payload > 0 ? ` (${Math.round(nanobot.drug_payload)}%)` : ''}`}
          color={stateProps.color}
          fontSize={10}
          backgroundColor="rgba(255, 255, 255, 0.95)"
          show={detailedMode}
        />
      )}
    </group>
  );
}
