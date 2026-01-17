import React, { Suspense, useRef, useEffect } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Environment, Stats } from '@react-three/drei';
import * as THREE from 'three';

interface Scene3DProps {
  children: React.ReactNode;
  className?: string;
  showStats?: boolean;
  showGrid?: boolean;
  focusedPosition?: [number, number, number] | null;
}

// Camera Controller Component
function CameraController({ focusedPosition }: { focusedPosition?: [number, number, number] | null }) {
  const { camera, controls } = useThree();
  const vec = new THREE.Vector3();

  useFrame(() => {
    if (focusedPosition) {
      // Smoothly move camera target to follow the focused object
      const target = new THREE.Vector3(...focusedPosition);
      
      // If we have OrbitControls, update its target
      // @ts-ignore - OrbitControls type definition might be missing target property access
      if (controls && controls.target) {
        // @ts-ignore
        controls.target.lerp(target, 0.1);
        // @ts-ignore
        controls.update();
      }
    }
  });
  
  return null;
}

export function Scene3D({ children, className, showStats = false, showGrid = true, focusedPosition }: Scene3DProps) {
  return (
    <div className={className}>
      <Canvas
        camera={{ 
          position: [400, 400, 400], // Angled side view (45-degree angle, showing 3D perspective)
          fov: 45,
          near: 0.1,
          far: 3000
        }}
        style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%)' }}
        shadows
        // Optimize WebGL context handling
        gl={{ 
          antialias: true, 
          preserveDrawingBuffer: true,
          powerPreference: 'high-performance',
          failIfMajorPerformanceCaveat: false 
        }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.outputColorSpace = THREE.SRGBColorSpace;
        }}
      >
        {/* Enhanced Lighting Setup - brighter for dark background */}
        <ambientLight intensity={0.5} color="#ffffff" />
        
        {/* Main directional light (sun) - increased intensity */}
        <directionalLight 
          position={[50, 50, 25]} 
          intensity={2.0}
          castShadow
          shadow-mapSize={[4096, 4096]}
          shadow-camera-far={1000}
          shadow-camera-left={-200}
          shadow-camera-right={200}
          shadow-camera-top={200}
          shadow-camera-bottom={-200}
          color="#ffffff"
        />
        
        {/* Fill light (soft blue) - increased intensity */}
        <directionalLight 
          position={[-30, -30, 20]} 
          intensity={0.6}
          color="#60a5fa"
        />
        
        {/* Rim light (warm) - increased intensity */}
        <pointLight 
          position={[0, 0, 100]} 
          intensity={1.0}
          color="#fbbf24"
          distance={500}
        />
        
        {/* Additional top-down light for better visibility */}
        <directionalLight 
          position={[0, 100, 0]} 
          intensity={0.8}
          color="#ffffff"
        />
        
        {/* Environment for realistic reflections - night/apartment for darker scenes */}
        <Environment preset="night" />
        
        {/* Camera Controller for "Click-to-Follow" */}
        <CameraController focusedPosition={focusedPosition} />

        {/* Scene content with loading fallback */}
        <Suspense fallback={null}>
          {children}
        </Suspense>
        
        {/* Grid helper - positioned below the scene - darker colors for visibility on dark background */}
        {showGrid && (
          <gridHelper args={[600, 20, 0x475569, 0x64748b]} position={[0, -100, 0]} />
        )}
        
        {/* Enhanced Camera Controls - Allow top-down view */}
        <OrbitControls
          makeDefault
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={50} // Allowed closer zoom
          maxDistance={2000}
          minPolarAngle={0} // Allow viewing from top (0 degrees)
          maxPolarAngle={Math.PI} // Allow viewing from bottom too
          autoRotate={false}
          autoRotateSpeed={0.8}
          enableDamping={true}
          dampingFactor={0.05}
          screenSpacePanning={false}
          target={[0, 0, 0]} // Look at center
          keys={{
            LEFT: 'ArrowLeft',
            UP: 'ArrowUp', 
            RIGHT: 'ArrowRight',
            BOTTOM: 'ArrowDown'
          }}
        />
        
        {/* Performance stats */}
        {showStats && <Stats />}
      </Canvas>
    </div>
  );
}
