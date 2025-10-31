import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment, Stats } from '@react-three/drei';

interface Scene3DProps {
  children: React.ReactNode;
  className?: string;
  showStats?: boolean;
  showGrid?: boolean;
}

export function Scene3D({ children, className, showStats = false, showGrid = true }: Scene3DProps) {
  return (
    <div className={className}>
      <Canvas
        camera={{ 
          position: [0, 800, 0], // Top-down view (high on Y axis, looking down)
          fov: 45,
          near: 0.1,
          far: 3000
        }}
        style={{ background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)' }}
        shadows
        performance={{ min: 0.5 }}
      >
        {/* Enhanced Lighting Setup */}
        <ambientLight intensity={0.3} color="#ffffff" />
        
        {/* Main directional light (sun) */}
        <directionalLight 
          position={[50, 50, 25]} 
          intensity={1.5}
          castShadow
          shadow-mapSize={[4096, 4096]}
          shadow-camera-far={1000}
          shadow-camera-left={-200}
          shadow-camera-right={200}
          shadow-camera-top={200}
          shadow-camera-bottom={-200}
          color="#ffffff"
        />
        
        {/* Fill light (soft blue) */}
        <directionalLight 
          position={[-30, -30, 20]} 
          intensity={0.4}
          color="#4f46e5"
        />
        
        {/* Rim light (warm) */}
        <pointLight 
          position={[0, 0, 100]} 
          intensity={0.8}
          color="#fbbf24"
          distance={500}
        />
        
        {/* Environment for realistic reflections */}
        <Environment preset="studio" />
        
        {/* Scene content with loading fallback */}
        <Suspense fallback={null}>
          {children}
        </Suspense>
        
        {/* Grid helper - positioned below the scene */}
        {showGrid && (
          <gridHelper args={[600, 20, 0xf1f5f9, 0xe2e8f0]} position={[0, -100, 0]} />
        )}
        
        {/* Enhanced Camera Controls - Allow top-down view */}
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={150}
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
