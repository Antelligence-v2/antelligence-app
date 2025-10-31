import React, { useMemo, useRef, useEffect } from 'react';
import { Scene3D } from './Scene3D';
import { TumorSphere } from './TumorSphere';
import { BloodVessel3D } from './BloodVessel3D';
import { Nanobot3D } from './Nanobot3D';
import { TumorCell3D, TumorCellsInstanced } from './TumorCell3D';
import { SubstrateField3D } from './SubstrateField3D';
import { NanobotTrailManager } from './NanobotTrail';
import { Label3D } from './Label3D';

interface NanobotState {
  id: number;
  position: [number, number];
  state: string;
  drug_payload: number;
  is_llm: boolean;
}

interface TumorCellState {
  id: number;
  position: [number, number, number];
  phase: string;
  is_alive: boolean;
}

interface VesselState {
  position: [number, number, number];
  supply_radius: number;
}

interface SubstrateData {
  oxygen?: number[][];
  drug?: number[][];
  trail?: number[][];
  alarm?: number[][];
  recruitment?: number[][];
  chemokine_signal?: number[][];
  toxicity_signal?: number[][];
  max_values?: Record<string, number>;
}

interface TumorSimulation3DProps {
  domainSize: number;
  nanobots: NanobotState[];
  tumorCells: TumorCellState[];
  vessels: VesselState[];
  substrateData: SubstrateData | null;
  selectedSubstrate: string;
  tumorRadius?: number;
  detailedMode?: boolean;
}

export function TumorSimulation3D({
  domainSize,
  nanobots,
  tumorCells,
  vessels,
  substrateData,
  selectedSubstrate,
  tumorRadius = 200,
  detailedMode = false,
}: TumorSimulation3DProps) {
  // Track nanobot trails and previous positions
  const trailsRef = useRef<Map<number, [number, number, number][]>>(new Map());
  const previousPositionsRef = useRef<Map<number, [number, number]>>(new Map());
  
  // Update trails and previous positions
  useEffect(() => {
    nanobots.forEach(nanobot => {
      const pos3D: [number, number, number] = [
        nanobot.position[0] - domainSize / 2,
        nanobot.position[1] - domainSize / 2,
        5
      ];
      
      // Update trail
      const trail = trailsRef.current.get(nanobot.id) || [];
      trail.push(pos3D);
      // Keep only last 50 positions
      if (trail.length > 50) trail.shift();
      trailsRef.current.set(nanobot.id, trail);
    });
  }, [nanobots, domainSize]);
  
  // Convert 2D positions to 3D coordinates
  const nanobots3D = useMemo(() => {
    return nanobots.map(nb => ({
      ...nb,
      position: [nb.position[0] - domainSize / 2, nb.position[1] - domainSize / 2, 0] as [number, number, number]
    }));
  }, [nanobots, domainSize]);
  
  // Get previous positions for direction calculation
  const nanobotsWithPrevious = useMemo(() => {
    return nanobots3D.map(nb => ({
      ...nb,
      previousPosition: previousPositionsRef.current.get(nb.id)
    }));
  }, [nanobots3D]);
  
  // Update previous positions
  useEffect(() => {
    nanobots.forEach(nanobot => {
      previousPositionsRef.current.set(nanobot.id, nanobot.position);
    });
  }, [nanobots]);

  const vessels3D = vessels.map(v => ({
    ...v,
    position: [v.position[0] - domainSize / 2, v.position[1] - domainSize / 2, 0] as [number, number, number]
  }));

  // Convert tumor cells to 3D coordinates
  const cells3D = tumorCells.map(cell => ({
    ...cell,
    position: [cell.position[0] - domainSize / 2, cell.position[1] - domainSize / 2, cell.position[2]] as [number, number, number]
  }));

  // Use instanced rendering for large cell counts
  const useInstancedRendering = cells3D.length > 100;

  return (
    <div className="w-full h-full">
      <Scene3D className="w-full h-[600px] border-2 border-gray-300 rounded-lg shadow-2xl">
        {/* Substrate field background */}
        {substrateData && substrateData[selectedSubstrate as keyof SubstrateData] && (
          <>
            <SubstrateField3D
              data={substrateData[selectedSubstrate as keyof SubstrateData] as number[][]}
              maxValue={substrateData.max_values?.[selectedSubstrate] || 1}
              substrateType={selectedSubstrate}
              domainSize={domainSize}
              opacity={
                // Higher opacity for pheromones to make them more visible
                selectedSubstrate === 'trail' || selectedSubstrate === 'alarm' || selectedSubstrate === 'recruitment'
                  ? (detailedMode ? 0.5 : 0.3)
                  : (detailedMode ? 0.3 : 0.15)
              }
            />
            {/* Substrate field label */}
            {detailedMode && (
              <Label3D
                position={[-domainSize / 2 + 30, -domainSize / 2 + 20, 0]}
                text={`📊 ${selectedSubstrate.charAt(0).toUpperCase() + selectedSubstrate.slice(1)} Field`}
                color="#1f2937"
                fontSize={11}
                backgroundColor="rgba(255, 255, 255, 0.9)"
                show={detailedMode}
              />
            )}
          </>
        )}
        
        {/* Tumor sphere */}
        <TumorSphere 
          tumorRadius={tumorRadius} 
          detailedMode={detailedMode} 
        />
        
        {/* Blood vessels */}
        {vessels3D.map((vessel, index) => (
          <BloodVessel3D
            key={`vessel-${index}`}
            vessel={vessel}
            index={index}
            detailedMode={detailedMode}
            connectedVessels={vessels3D}
          />
        ))}
        
        {/* Tumor cells - use instanced rendering for performance */}
        {useInstancedRendering ? (
          <TumorCellsInstanced
            cells={cells3D}
            detailedMode={detailedMode}
          />
        ) : (
          cells3D.map(cell => (
            <TumorCell3D
              key={`cell-${cell.id}`}
              cell={cell}
              detailedMode={detailedMode}
            />
          ))
        )}
        
        {/* Nanobot trails */}
        <NanobotTrailManager
          nanobots={nanobots}
          trails={trailsRef.current}
          detailedMode={detailedMode}
        />
        
        {/* Nanobots */}
        {nanobotsWithPrevious.map((nanobot) => (
          <Nanobot3D
            key={`nanobot-${nanobot.id}`}
            nanobot={nanobot}
            previousPosition={nanobot.previousPosition}
            detailedMode={detailedMode}
          />
        ))}
        
        {/* Grid helper (optional) */}
        {detailedMode && (
          <gridHelper args={[domainSize, 20, 0x888888, 0x888888]} />
        )}
      </Scene3D>
      
      {/* 3D Legend */}
      <div className="mt-4 p-4 bg-white rounded-lg border shadow-sm">
        <h4 className="font-bold text-sm text-gray-600 mb-3">🎮 3D Controls & Legend</h4>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div>
            <div className="font-semibold mb-1">Mouse Controls:</div>
            <div>• Left click + drag: Rotate view</div>
            <div>• Right click + drag: Pan view</div>
            <div>• Scroll: Zoom in/out</div>
          </div>
          <div>
            <div className="font-semibold mb-1">3D Elements:</div>
            <div>• 🔴 Red sphere: Tumor zones</div>
            <div>• 🟢 Green tubes: Blood vessels</div>
            <div>• 💎 Blue/Gold: Nanobots</div>
            <div>• ⭕ Rings: LLM nanobots</div>
            {detailedMode && (
              <>
                <div className="mt-1 pt-1 border-t border-gray-200">
                  <div className="font-semibold">Labels:</div>
                  <div>• Zone names on tumor</div>
                  <div>• Nanobot states shown</div>
                  <div>• Vessel info displayed</div>
                </div>
              </>
            )}
          </div>
          <div>
            <div className="font-semibold mb-1">Current View:</div>
            <div className="px-2 py-1 bg-blue-50 rounded text-blue-700 font-medium">
              {selectedSubstrate.charAt(0).toUpperCase() + selectedSubstrate.slice(1)} Field
            </div>
            <div className="mt-2 text-gray-500">
              {substrateData && substrateData[selectedSubstrate as keyof SubstrateData] 
                ? '✓ Data loaded'
                : '⚠ No data available'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
