import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface PheromoneParticleProps {
  position: [number, number, number];
  color: number;
  opacity: number;
  index: number; // For staggered animation
}

/**
 * Individual pheromone particle with floating animation
 */
export function PheromoneParticle({ position, color, opacity, index }: PheromoneParticleProps) {
  const particleRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshPhongMaterial>(null);
  
  // Animate floating effect with slight variation per particle
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    const offset = index * 0.5; // Stagger particles
    
    if (particleRef.current) {
      // Floating motion - small vertical oscillation
      const floatAmount = Math.sin(time * 2 + offset) * 0.5;
      particleRef.current.position.y = position[1] + floatAmount;
      
      // Subtle pulsing
      const pulse = Math.sin(time * 3 + offset) * 0.15 + 0.85;
      if (materialRef.current) {
        materialRef.current.opacity = opacity * pulse * 0.8;
      }
    }
  });

  return (
    <mesh ref={particleRef} position={position}>
      <sphereGeometry args={[0.8, 6, 6]} />
      <meshPhongMaterial 
        ref={materialRef}
        color={color}
        emissive={color}
        transparent
        opacity={opacity * 0.8}
      />
    </mesh>
  );
}

