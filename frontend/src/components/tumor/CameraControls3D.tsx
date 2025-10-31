import React, { useRef, useState } from 'react';
import { useThree, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

interface CameraControls3DProps {
  enableAutoRotate?: boolean;
  autoRotateSpeed?: number;
  enableDamping?: boolean;
  dampingFactor?: number;
}

export function CameraControls3D({ 
  enableAutoRotate = false, 
  autoRotateSpeed = 0.8,
  enableDamping = true,
  dampingFactor = 0.05
}: CameraControls3DProps) {
  const controlsRef = useRef<any>();
  const { camera } = useThree();
  const [isAutoRotating, setIsAutoRotating] = useState(enableAutoRotate);

  // Camera presets
  const cameraPresets = {
    front: () => {
      camera.position.set(0, 0, 600);
      camera.lookAt(0, 0, 0);
    },
    side: () => {
      camera.position.set(600, 0, 0);
      camera.lookAt(0, 0, 0);
    },
    top: () => {
      camera.position.set(0, 600, 0);
      camera.lookAt(0, 0, 0);
    },
    isometric: () => {
      camera.position.set(400, 400, 400);
      camera.lookAt(0, 0, 0);
    },
    close: () => {
      camera.position.set(0, 0, 200);
      camera.lookAt(0, 0, 0);
    }
  };

  // Smooth camera transitions
  useFrame((state, delta) => {
    if (controlsRef.current) {
      controlsRef.current.update();
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={true}
      enableZoom={true}
      enableRotate={true}
      minDistance={150}
      maxDistance={2000}
      minPolarAngle={Math.PI / 6}
      maxPolarAngle={Math.PI - Math.PI / 6}
      autoRotate={isAutoRotating}
      autoRotateSpeed={autoRotateSpeed}
      enableDamping={enableDamping}
      dampingFactor={dampingFactor}
      screenSpacePanning={false}
      keys={{
        LEFT: 'ArrowLeft',
        UP: 'ArrowUp', 
        RIGHT: 'ArrowRight',
        BOTTOM: 'ArrowDown'
      }}
      onStart={() => {
        setIsAutoRotating(false);
      }}
    />
  );
}

// Camera preset buttons component
export function CameraPresetButtons() {
  const { camera } = useThree();

  const handlePreset = (preset: keyof typeof cameraPresets) => {
    const presets = {
      front: () => {
        camera.position.set(0, 0, 600);
        camera.lookAt(0, 0, 0);
      },
      side: () => {
        camera.position.set(600, 0, 0);
        camera.lookAt(0, 0, 0);
      },
      top: () => {
        camera.position.set(0, 600, 0);
        camera.lookAt(0, 0, 0);
      },
      isometric: () => {
        camera.position.set(400, 400, 400);
        camera.lookAt(0, 0, 0);
      },
      close: () => {
        camera.position.set(0, 0, 200);
        camera.lookAt(0, 0, 0);
      }
    };
    
    presets[preset]();
  };

  return (
    <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
      <button
        onClick={() => handlePreset('front')}
        className="px-3 py-1 bg-white/80 hover:bg-white text-gray-700 text-sm rounded shadow-md transition-colors"
      >
        Front
      </button>
      <button
        onClick={() => handlePreset('side')}
        className="px-3 py-1 bg-white/80 hover:bg-white text-gray-700 text-sm rounded shadow-md transition-colors"
      >
        Side
      </button>
      <button
        onClick={() => handlePreset('top')}
        className="px-3 py-1 bg-white/80 hover:bg-white text-gray-700 text-sm rounded shadow-md transition-colors"
      >
        Top
      </button>
      <button
        onClick={() => handlePreset('isometric')}
        className="px-3 py-1 bg-white/80 hover:bg-white text-gray-700 text-sm rounded shadow-md transition-colors"
      >
        ISO
      </button>
      <button
        onClick={() => handlePreset('close')}
        className="px-3 py-1 bg-white/80 hover:bg-white text-gray-700 text-sm rounded shadow-md transition-colors"
      >
        Close
      </button>
    </div>
  );
}
