import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Label3D } from './Label3D';

interface TumorCellState {
  id: number;
  position: [number, number, number];
  phase: string;
  is_alive: boolean;
}

interface TumorCell3DProps {
  cell: TumorCellState;
  detailedMode?: boolean;
}

interface TumorCellsInstancedProps {
  cells: TumorCellState[];
  detailedMode?: boolean;
}

// Individual cell component (for small counts)
export function TumorCell3D({ cell, detailedMode = false }: TumorCell3DProps) {
  const cellRef = useRef<THREE.Mesh>(null);
  
  // Get phase-based colors and properties
  const getPhaseProperties = (phase: string) => {
    switch (phase) {
      case "viable":
        return { color: 0xef4444, emissive: 0x991b1b, scale: 1.0 };
      case "hypoxic":
        return { color: 0xa855f7, emissive: 0x6b21a8, scale: 0.8 };
      case "necrotic":
        return { color: 0x6b7280, emissive: 0x374151, scale: 0.6 };
      case "apoptotic":
        return { color: 0xfbbf24, emissive: 0x92400e, scale: 0.7 };
      default:
        return { color: 0xef4444, emissive: 0x991b1b, scale: 1.0 };
    }
  };

  const phaseProps = getPhaseProperties(cell.phase);

  // Enhanced floating animation with phase-specific behavior
  useFrame((state) => {
    if (cellRef.current) {
      const time = state.clock.getElapsedTime();
      
      // Different animation patterns based on phase
      let animationOffset = 0;
      let animationSpeed = 1;
      let animationAmplitude = 0.5;
      
      switch (cell.phase) {
        case "viable":
          animationSpeed = 1.5;
          animationAmplitude = 0.8;
          break;
        case "hypoxic":
          animationSpeed = 0.8;
          animationAmplitude = 0.3;
          break;
        case "necrotic":
          animationSpeed = 0.2;
          animationAmplitude = 0.1;
          break;
        case "apoptotic":
          animationSpeed = 1.2;
          animationAmplitude = 0.6;
          break;
      }
      
      const zOffset = Math.sin(time * animationSpeed + cell.id * 0.1) * animationAmplitude;
      const yOffset = Math.cos(time * animationSpeed * 0.7 + cell.id * 0.1) * animationAmplitude * 0.3;
      
      cellRef.current.position.z = cell.position[2] + zOffset;
      cellRef.current.position.y = cell.position[1] + yOffset;
      cellRef.current.scale.setScalar(phaseProps.scale);
      
      // Gentle rotation for viable cells
      if (cell.phase === "viable") {
        cellRef.current.rotation.y += 0.005;
      }
    }
  });

  if (!cell.is_alive) return null;

  return (
    <group position={[cell.position[0], cell.position[1], cell.position[2]]}>
      {/* Main cell body - LARGER for better visibility */}
      <mesh ref={cellRef}>
        <sphereGeometry args={[3, 8, 8]} />
        <meshPhongMaterial
          color={phaseProps.color}
          emissive={phaseProps.emissive}
          transparent
          opacity={0.9}
          shininess={50}
        />
      </mesh>
      
      {/* Cell phase indicator in detailed mode */}
      {detailedMode && (
        <mesh position={[0, 0, 3]}>
          <sphereGeometry args={[0.5, 4, 4]} />
          <meshBasicMaterial color={phaseProps.color} />
        </mesh>
      )}
      
      {/* Cell membrane in detailed mode */}
      {detailedMode && cell.phase === "viable" && (
        <mesh ref={cellRef}>
          <sphereGeometry args={[2.2, 8, 8]} />
          <meshBasicMaterial 
            color={phaseProps.color} 
            transparent 
            opacity={0.2}
            wireframe
          />
        </mesh>
      )}
      
      {/* Cell phase label (for sample of cells to avoid clutter) */}
      {detailedMode && cell.id % 10 === 0 && (
        <Label3D
          position={[0, 0, 5]}
          text={`${cell.phase.charAt(0).toUpperCase() + cell.phase.slice(1)} Cell`}
          color={phaseProps.color}
          fontSize={8}
          backgroundColor="rgba(255, 255, 255, 0.8)"
          show={true}
        />
      )}
    </group>
  );
}

// Instanced rendering component (for large counts)
export function TumorCellsInstanced({ cells, detailedMode = false }: TumorCellsInstancedProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const aliveCells = cells.filter(cell => cell.is_alive);
  
      // Create geometry and materials for each phase - LARGER for better visibility
      const geometries = useMemo(() => {
        const viableGeo = new THREE.SphereGeometry(3, 8, 8);
        const hypoxicGeo = new THREE.SphereGeometry(2.5, 8, 8);
        const necroticGeo = new THREE.SphereGeometry(2, 6, 6);
        const apoptoticGeo = new THREE.SphereGeometry(2.2, 8, 8);
    
    return { viable: viableGeo, hypoxic: hypoxicGeo, necrotic: necroticGeo, apoptotic: apoptoticGeo };
  }, []);
  
  const materials = useMemo(() => {
    const viableMat = new THREE.MeshPhongMaterial({ 
      color: 0xef4444, 
      emissive: 0x991b1b, 
      transparent: true, 
      opacity: 0.8 
    });
    const hypoxicMat = new THREE.MeshPhongMaterial({ 
      color: 0xa855f7, 
      emissive: 0x6b21a8, 
      transparent: true, 
      opacity: 0.8 
    });
    const necroticMat = new THREE.MeshPhongMaterial({ 
      color: 0x6b7280, 
      emissive: 0x374151, 
      transparent: true, 
      opacity: 0.8 
    });
    const apoptoticMat = new THREE.MeshPhongMaterial({ 
      color: 0xfbbf24, 
      emissive: 0x92400e, 
      transparent: true, 
      opacity: 0.8 
    });
    
    return { viable: viableMat, hypoxic: hypoxicMat, necrotic: necroticMat, apoptotic: apoptoticMat };
  }, []);
  
  // Group cells by phase for instanced rendering
  const cellsByPhase = useMemo(() => {
    const groups = {
      viable: [] as TumorCellState[],
      hypoxic: [] as TumorCellState[],
      necrotic: [] as TumorCellState[],
      apoptotic: [] as TumorCellState[]
    };
    
    aliveCells.forEach(cell => {
      if (groups[cell.phase as keyof typeof groups]) {
        groups[cell.phase as keyof typeof groups].push(cell);
      }
    });
    
    return groups;
  }, [aliveCells]);
  
  // Animation for instanced cells
  useFrame((state) => {
    if (!meshRef.current) return;
    
    const time = state.clock.getElapsedTime();
    
    // Update instance matrices for animation
    Object.entries(cellsByPhase).forEach(([phase, phaseCells]) => {
      phaseCells.forEach((cell, index) => {
        const matrix = new THREE.Matrix4();
        const position = new THREE.Vector3(
          cell.position[0],
          cell.position[1] + Math.sin(time * 1 + cell.id * 0.1) * 0.3,
          cell.position[2] + Math.cos(time * 1 + cell.id * 0.1) * 0.3
        );
        
        const scale = phase === "viable" ? 1.0 : 
                     phase === "hypoxic" ? 0.8 : 
                     phase === "necrotic" ? 0.6 : 0.7;
        
        matrix.setPosition(position);
        matrix.scale(new THREE.Vector3(scale, scale, scale));
        
        if (meshRef.current) {
          meshRef.current.setMatrixAt(index, matrix);
        }
      });
    });
    
    if (meshRef.current) {
      meshRef.current.instanceMatrix.needsUpdate = true;
    }
  });
  
  return (
    <>
      {Object.entries(cellsByPhase).map(([phase, phaseCells]) => {
        if (phaseCells.length === 0) return null;
        
        return (
          <instancedMesh
            key={phase}
            ref={phase === "viable" ? meshRef : undefined}
            args={[geometries[phase as keyof typeof geometries], materials[phase as keyof typeof materials], phaseCells.length]}
          />
        );
      })}
    </>
  );
}
