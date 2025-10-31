import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface NanobotTrailProps {
  positions: [number, number, number][];
  color?: number;
  opacity?: number;
  maxLength?: number;
}

export function NanobotTrail({ 
  positions, 
  color = 0x3b82f6, 
  opacity = 0.5,
  maxLength = 50 
}: NanobotTrailProps) {
  const trailRef = useRef<THREE.Mesh>(null);
  const lineRef = useRef<THREE.Line>(null);

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

  // Create tube geometry for the trail
  const tubeGeometry = useMemo(() => {
    if (!curve || trailPositions.length < 2) return null;
    
    try {
      const tube = new THREE.TubeGeometry(curve, Math.max(trailPositions.length * 2, 4), 0.5, 6, false);
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
    
    if (lineRef.current && lineRef.current.material) {
      const fade = Math.sin(time * 0.5) * 0.1 + (0.9 - trailPositions.length / maxLength * 0.5);
      (lineRef.current.material as THREE.LineBasicMaterial).opacity = opacity * fade * 0.5;
    }
  });

  if (!tubeGeometry || !curve) return null;

  // Create points array for line
  const linePoints = useMemo(() => {
    return trailPositions.map(pos => new THREE.Vector3(...pos));
  }, [trailPositions]);

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
      
      {/* Line trail for subtle effect */}
      <line ref={lineRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={linePoints.length}
            array={new Float32Array(linePoints.flatMap(p => [p.x, p.y, p.z]))}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial 
          color={color}
          transparent
          opacity={opacity * 0.5}
          linewidth={1}
        />
      </line>
      
      {/* Trail particles */}
      {trailPositions.filter((_, i) => i % 5 === 0).map((pos, index) => (
        <mesh key={index} position={pos}>
          <sphereGeometry args={[0.3, 4, 4]} />
          <meshBasicMaterial 
            color={color}
            transparent
            opacity={opacity * 0.6}
          />
        </mesh>
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
}

export function NanobotTrailManager({ nanobots, trails, detailedMode = false }: NanobotTrailManagerProps) {
  if (!detailedMode || trails.size === 0) return null;

  return (
    <>
      {nanobots.map(nanobot => {
        const trail = trails.get(nanobot.id);
        if (!trail || trail.length < 2) return null;

        // Get color based on state
        const getTrailColor = (state: string) => {
          switch (state) {
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

        return (
          <NanobotTrail
            key={`trail-${nanobot.id}`}
            positions={trail}
            color={getTrailColor(nanobot.state)}
            opacity={0.4}
            maxLength={30}
          />
        );
      })}
    </>
  );
}

