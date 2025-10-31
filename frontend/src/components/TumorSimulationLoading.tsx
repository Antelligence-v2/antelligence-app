import React, { useState, useEffect } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import * as THREE from 'three';

interface TumorSimulationLoadingProps {
  isVisible: boolean;
  progress?: number;
  currentStep?: number;
  totalSteps?: number;
}

// Mini 3D components for the loading preview
function LoadingTumorSphere({ show, tumorRadius }: { show: boolean; tumorRadius: number }) {
  if (!show) return null;

  return (
    <group>
      {/* Necrotic core */}
      <mesh>
        <sphereGeometry args={[tumorRadius * 0.25, 16, 16]} />
        <meshPhongMaterial color={0x2d1b69} transparent opacity={0.6} />
      </mesh>
      {/* Hypoxic zone */}
      <mesh>
        <sphereGeometry args={[tumorRadius * 0.7, 16, 16]} />
        <meshPhongMaterial color={0x7c3aed} transparent opacity={0.5} />
      </mesh>
      {/* Viable tumor */}
      <mesh>
        <sphereGeometry args={[tumorRadius, 16, 16]} />
        <meshPhongMaterial color={0xef4444} transparent opacity={0.4} />
      </mesh>
      
      {/* Label */}
      <Html position={[0, tumorRadius + 20, 0]} center>
        <div className="bg-red-600/90 text-white px-3 py-1 rounded-lg text-xs font-bold shadow-lg border border-red-400">
          🔴 Tumor Zones
        </div>
      </Html>
    </group>
  );
}

function LoadingBloodVessel({ show, position }: { show: boolean; position: [number, number, number] }) {
  if (!show) return null;

  return (
    <group position={position}>
      {/* Vessel tube */}
      <mesh>
        <cylinderGeometry args={[5, 5, 30, 8]} />
        <meshPhongMaterial color={0x22c55e} emissive={0x16a34a} />
      </mesh>
      {/* Supply radius */}
      <mesh>
        <sphereGeometry args={[30, 16, 16]} />
        <meshPhongMaterial color={0x22c55e} transparent opacity={0.2} />
      </mesh>
      
      {/* Label */}
      <Html position={[0, 20, 0]} center>
        <div className="bg-green-600/90 text-white px-3 py-1 rounded-lg text-xs font-bold shadow-lg border border-green-400">
          🟢 Blood Vessel
        </div>
      </Html>
    </group>
  );
}

function LoadingTumorCell({ show, position }: { show: boolean; position: [number, number, number] }) {
  if (!show) return null;

  return (
    <group position={position}>
      <mesh>
        <sphereGeometry args={[2, 8, 8]} />
        <meshPhongMaterial color={0xef4444} emissive={0x991b1b} />
      </mesh>
    </group>
  );
}

function LoadingNanobot({ show, position }: { show: boolean; position: [number, number, number] }) {
  if (!show) return null;

  return (
    <group position={position}>
      <mesh>
        <octahedronGeometry args={[3, 0]} />
        <meshPhongMaterial color={0x3b82f6} emissive={0x1e40af} />
      </mesh>
      {/* LLM ring for some */}
      {(position[0] > 0 || position[2] > 0) && (
        <mesh>
          <ringGeometry args={[4, 5, 16]} />
          <meshPhongMaterial color={0xfbbf24} transparent opacity={0.7} />
        </mesh>
      )}
      
      {/* Label */}
      <Html position={[0, 8, 0]} center>
        <div className="bg-blue-600/90 text-white px-3 py-1 rounded-lg text-xs font-bold shadow-lg border border-blue-400">
          💎 Nanobot
        </div>
      </Html>
    </group>
  );
}

export const TumorSimulationLoading: React.FC<TumorSimulationLoadingProps> = ({
  isVisible,
  progress = 0,
  currentStep = 0,
  totalSteps = 0
}) => {
  const [stage, setStage] = useState(0);

  // Determine which stage we're in based on progress
  useEffect(() => {
    if (progress < 20) setStage(0); // Tumor
    else if (progress < 40) setStage(1); // Vessels
    else if (progress < 60) setStage(2); // Cells
    else if (progress < 80) setStage(3); // Nanobots
    else setStage(4); // Complete
  }, [progress]);

  const getStageMessage = () => {
    switch (stage) {
      case 0:
        return "Analyzing tumor geometry...";
      case 1:
        return "Mapping blood vessel network...";
      case 2:
        return "Initializing tumor cells...";
      case 3:
        return "Deploying nanobot swarm...";
      case 4:
        return "Finalizing simulation...";
      default:
        return "Initializing...";
    }
  };

  const getStageDescription = () => {
    switch (stage) {
      case 0:
        return "Creating 3D tumor structure with necrotic core, hypoxic zone, and viable regions";
      case 1:
        return "Establishing blood vessels that supply oxygen and drugs to the microenvironment";
      case 2:
        return "Populating tumor cells in different phases (viable, hypoxic, necrotic)";
      case 3:
        return "Launching nanobots that will navigate and deliver drugs to cancer cells";
      case 4:
        return "Preparing visualization data and simulation results";
      default:
        return "";
    }
  };

  if (!isVisible) return null;

  // Sample positions for preview elements
  const vesselPositions: [number, number, number][] = [
    [80, 0, 0],
    [-80, 0, 0],
    [0, 0, 80],
  ];

  const cellPositions: [number, number, number][] = [
    [40, 40, 0],
    [-40, -40, 0],
    [60, -30, 0],
  ];

  const nanobotPositions: [number, number, number][] = [
    [100, 0, 100],
    [-100, 0, -100],
    [0, 0, 120],
  ];

  return (
    <div className="fixed inset-0 bg-slate-900/95 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="w-full max-w-6xl mx-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left side: 3D Preview */}
        <div className="bg-slate-800/90 rounded-2xl p-6 border border-slate-700 shadow-2xl">
          <h3 className="text-white font-bold text-lg mb-4 text-center">🔬 3D Environment Preview</h3>
          <div className="w-full h-[400px] rounded-lg overflow-hidden border-2 border-slate-600">
            <Canvas camera={{ position: [200, 200, 200], fov: 50 }}>
              <ambientLight intensity={0.5} />
              <directionalLight position={[50, 50, 25]} intensity={1.5} />
              <pointLight position={[0, 100, 0]} intensity={0.8} />
              
              {/* Substrate field background */}
              <mesh position={[0, -75, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <planeGeometry args={[300, 300]} />
                <meshBasicMaterial color={0x1e293b} transparent opacity={0.3} />
              </mesh>
              
              {/* Tumor sphere - appears first */}
              <LoadingTumorSphere show={stage >= 0} tumorRadius={60} />
              
              {/* Blood vessels - appear second */}
              {vesselPositions.map((pos, i) => (
                <LoadingBloodVessel key={i} show={stage >= 1} position={pos} />
              ))}
              
              {/* Tumor cells - appear third */}
              {cellPositions.map((pos, i) => (
                <LoadingTumorCell key={i} show={stage >= 2} position={pos} />
              ))}
              
              {/* Nanobots - appear last */}
              {nanobotPositions.map((pos, i) => (
                <LoadingNanobot key={i} show={stage >= 3} position={pos} />
              ))}
              
              <OrbitControls
                enableZoom={false}
                enablePan={false}
                autoRotate
                autoRotateSpeed={0.5}
              />
            </Canvas>
          </div>
        </div>

        {/* Right side: Progress and Info */}
        <div className="bg-slate-800/90 rounded-2xl p-6 border border-slate-700 shadow-2xl flex flex-col justify-between">
          <div className="space-y-6">
            {/* Title */}
            <div className="text-center">
              <h2 className="text-2xl font-bold text-white mb-2">
                🧬 Tumor Nanobot Simulation
              </h2>
              <p className="text-slate-400 text-sm">
                Building your 3D microenvironment
              </p>
            </div>

            {/* Current Stage */}
            <div className="bg-slate-700/50 rounded-lg p-4 border border-slate-600">
              <div className="flex items-center gap-3 mb-2">
                <div className="text-3xl animate-pulse">
                  {stage === 0 && "🔴"}
                  {stage === 1 && "🟢"}
                  {stage === 2 && "🔴"}
                  {stage === 3 && "💎"}
                  {stage === 4 && "✨"}
                </div>
                <div className="flex-1">
                  <h3 className="text-white font-semibold text-lg">
                    {getStageMessage()}
                  </h3>
                  <p className="text-slate-300 text-sm mt-1">
                    {getStageDescription()}
                  </p>
                </div>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-slate-400">
                <span>Progress</span>
                <span className="font-mono">{progress.toFixed(0)}%</span>
              </div>
              <div className="relative w-full bg-slate-700 rounded-full h-4 overflow-hidden border border-slate-600">
                <div 
                  className="h-4 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full transition-all duration-500 relative overflow-hidden"
                  style={{ width: `${progress}%` }}
                >
                  {/* Shimmer effect */}
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-[shimmer_2s_infinite]"></div>
                </div>
              </div>
              {totalSteps > 0 && (
                <div className="text-xs text-slate-400 text-center">
                  Step {currentStep}/{totalSteps} • Estimated time remaining...
                </div>
              )}
            </div>

            {/* Stage Indicators */}
            <div className="grid grid-cols-4 gap-2">
              {[0, 1, 2, 3].map((s) => (
                <div
                  key={s}
                  className={`p-2 rounded-lg text-center transition-all ${
                    stage >= s
                      ? 'bg-blue-500/20 border-2 border-blue-500'
                      : 'bg-slate-700/50 border-2 border-slate-600'
                  }`}
                >
                  <div className="text-xl mb-1">
                    {s === 0 && "🔴"}
                    {s === 1 && "🟢"}
                    {s === 2 && "🔴"}
                    {s === 3 && "💎"}
                  </div>
                  <div className={`text-xs ${stage >= s ? 'text-blue-300' : 'text-slate-500'}`}>
                    {s === 0 && "Tumor"}
                    {s === 1 && "Vessels"}
                    {s === 2 && "Cells"}
                    {s === 3 && "Nanobots"}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Fun Fact / Info */}
          <div className="mt-6 bg-slate-700/50 rounded-lg p-3 border border-slate-600">
            <p className="text-xs text-slate-300 text-center">
              💡 <strong>Did you know?</strong> Each nanobot navigates using pheromone trails and can deliver targeted drug payloads to specific tumor cells.
            </p>
          </div>
        </div>
      </div>

      {/* Add shimmer animation */}
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
};

