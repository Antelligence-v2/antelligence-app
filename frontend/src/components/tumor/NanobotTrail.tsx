import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { PheromoneParticle } from './PheromoneParticle';

interface NanobotTrailProps {
  positions: [number, number, number][];
  color?: number;
  opacity?: number;
  maxLength?: number;
  showParticles?: boolean; // Option to show pheromone particles
}

export function NanobotTrail({ 
  positions, 
  color = 0x3b82f6, 
  opacity = 0.5,
  maxLength = 50,
  showParticles = true
}: NanobotTrailProps) {
  const trailRef = useRef<THREE.Mesh>(null);

  // Limit trail length
  const trailPositions = useMemo(() => {
    return positions.slice(-maxLength);
  }, [positions, maxLength]);

  if (trailPositions.length < 2) return null;

  // Create smooth curve from positions
  const curve = useMemo(() => {
    if (trailPositions.length < 2) return null;
    
    const points = trailPositions.map(pos => new THREE.Vector3(...pos));
    
    // Use CatmullRom curve for smooth path
    // For 2 points, we can duplicate the first point to make a valid curve
    if (points.length === 2) {
      points.unshift(points[0].clone());
      points.push(points[points.length - 1].clone());
    }
    
    return new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0);
  }, [trailPositions]);

  // Create tube geometry for the trail - thicker for better visibility
  const tubeGeometry = useMemo(() => {
    if (!curve || trailPositions.length < 2) return null;
    
    try {
      // Increased radius from 0.5 to 1.0 for better pheromone visibility
      const tube = new THREE.TubeGeometry(curve, Math.max(trailPositions.length * 2, 4), 1.0, 8, false);
      return tube;
    } catch (e) {
      // Fallback to line if curve creation fails
      return null;
    }
  }, [curve, trailPositions.length]);

  // Animate trail fade
  useFrame((state) => {
    const time = state.clock.getElapsedTime();
    
    if (trailRef.current && trailRef.current.material) {
      // Fade trail over time
      const fade = Math.sin(time * 0.5) * 0.1 + (0.9 - trailPositions.length / maxLength * 0.5);
      (trailRef.current.material as THREE.MeshBasicMaterial).opacity = opacity * fade;
    }
  });

  if (!tubeGeometry || !curve) return null;

  return (
    <group>
      {/* Tube trail */}
      <mesh ref={trailRef}>
        <primitive object={tubeGeometry} />
        <meshBasicMaterial 
          color={color}
          transparent
          opacity={opacity}
        />
      </mesh>
      
      {/* Pheromone particles - animated floating particles */}
      {showParticles && trailPositions.filter((_, i) => i % 3 === 0).map((pos, index) => (
        <PheromoneParticle
          key={index}
          position={pos}
          color={color}
          opacity={opacity}
          index={index}
        />
      ))}
    </group>
  );
}


interface NanobotTrailManagerProps {
  nanobots: Array<{
    id: number;
    position: [number, number];
    state: string;
  }>;
  trails: Map<number, [number, number, number][]>;
  detailedMode?: boolean;
  selectedSubstrate?: string; // Track which pheromone type is selected
}

export function NanobotTrailManager({ 
  nanobots, 
  trails, 
  detailedMode = false,
  selectedSubstrate = 'trail' 
}: NanobotTrailManagerProps) {
  // Always show trails (not just in detailed mode), but with different opacity
  if (trails.size === 0) return null;

  return (
    <>
      {nanobots.map(nanobot => {
        const trail = trails.get(nanobot.id);
        if (!trail || trail.length < 2) return null;

        // Get color based on pheromone type if showing pheromones, otherwise based on state
        const getTrailColor = () => {
          // If showing pheromone substrate, use pheromone-specific colors
          if (selectedSubstrate === 'trail') {
            return 0x10b981; // Emerald green for trail pheromone
          } else if (selectedSubstrate === 'alarm') {
            return 0xef4444; // Red for alarm pheromone
          } else if (selectedSubstrate === 'recruitment') {
            return 0x3b82f6; // Blue for recruitment pheromone
          }
          
          // Otherwise use state-based colors
          switch (nanobot.state) {
            case "targeting":
              return 0xfbbf24;
            case "delivering":
              return 0x10b981;
            case "returning":
              return 0x3b82f6;
            case "reloading":
              return 0x8b5cf6;
            default:
              return 0x6b7280;
          }
        };

        // Different opacity based on mode and pheromone type
        const getOpacity = () => {
          if (selectedSubstrate === 'trail' || selectedSubstrate === 'alarm' || selectedSubstrate === 'recruitment') {
            // More visible when showing pheromones
            return detailedMode ? 0.7 : 0.5;
          }
          // Less visible for regular movement trails
          return detailedMode ? 0.4 : 0.2;
        };

        return (
          <NanobotTrail
            key={`trail-${nanobot.id}`}
            positions={trail}
            color={getTrailColor()}
            opacity={getOpacity()}
            maxLength={50} // Longer trails for better pheromone visualization
          />
        );
      })}
    </>
  );
}

