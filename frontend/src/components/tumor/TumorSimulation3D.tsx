import React, { useMemo, useRef, useEffect } from 'react';
import { Scene3D } from './Scene3D';
import { TumorSphere } from './TumorSphere';
import { BloodVessel3D } from './BloodVessel3D';
import { Nanobot3D } from './Nanobot3D';
import { TumorCell3D, TumorCellsInstanced } from './TumorCell3D';
import { SubstrateField3D } from './SubstrateField3D';
import { NanobotTrailManager } from './NanobotTrail';
import { Label3D } from './Label3D';
import { ScaleBar3D } from './ScaleBar3D';

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
            {/* Substrate field label - always visible */}
            <Label3D
              position={[-domainSize / 2 + 30, -domainSize / 2 + 20, 0]}
              text={`📊 ${selectedSubstrate.charAt(0).toUpperCase() + selectedSubstrate.slice(1)} Field`}
              color="#e2e8f0"
              fontSize={11}
              backgroundColor="rgba(15, 23, 42, 0.9)"
              show={true}
            />
            {/* Substrate max value - always visible */}
            {substrateData.max_values?.[selectedSubstrate] && (
              <Label3D
                position={[-domainSize / 2 + 30, -domainSize / 2 + 35, 0]}
                text={`Max: ${substrateData.max_values[selectedSubstrate].toFixed(1)}`}
                color="#94a3b8"
                fontSize={10}
                backgroundColor="rgba(15, 23, 42, 0.8)"
                show={true}
              />
            )}
          </>
        )}
        
        {/* Tumor sphere */}
        <TumorSphere 
          tumorRadius={tumorRadius} 
          detailedMode={detailedMode} 
        />
        
        {/* Blood vessels - label only the first one */}
        {vessels3D.map((vessel, index) => (
          <BloodVessel3D
            key={`vessel-${index}`}
            vessel={vessel}
            index={index}
            detailedMode={detailedMode}
            connectedVessels={vessels3D}
            showLabel={index === 0} // Only show label for first vessel
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
        
        {/* Nanobot trails - always visible to show pheromone paths */}
        <NanobotTrailManager
          nanobots={nanobots}
          trails={trailsRef.current}
          detailedMode={detailedMode}
          selectedSubstrate={selectedSubstrate}
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
        
        {/* Grid helper (optional) - updated colors for dark background */}
        {detailedMode && (
          <gridHelper args={[domainSize, 20, 0x475569, 0x64748b]} />
        )}
        
        {/* Scale bar */}
        <ScaleBar3D domainSize={domainSize} />
      </Scene3D>
      
      {/* Enhanced 3D Legend */}
      <div className="mt-4 p-4 bg-white rounded-lg border shadow-sm">
        <h4 className="font-bold text-sm text-gray-600 mb-3">🎮 3D Controls & Legend</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <div className="font-semibold mb-1">Mouse Controls:</div>
            <div>• Left drag: Rotate</div>
            <div>• Right drag: Pan</div>
            <div>• Scroll: Zoom</div>
          </div>
          <div>
            <div className="font-semibold mb-1">🤖 Nanobot States:</div>
            <div>• <span className="text-gray-500">Searching</span> (?)</div>
            <div>• <span className="text-yellow-600">Targeting</span> (→)</div>
            <div>• <span className="text-green-600">Delivering</span> (💊)</div>
            <div>• <span className="text-blue-600">Returning</span> (←)</div>
            <div>• <span className="text-purple-600">Reloading</span> (⚡)</div>
          </div>
          <div>
            <div className="font-semibold mb-1">🔬 Tumor Cell Phases:</div>
            <div>• <span className="text-red-600">Viable</span> (red)</div>
            <div>• <span className="text-purple-600">Hypoxic</span> (purple)</div>
            <div>• <span className="text-gray-600">Necrotic</span> (gray)</div>
            <div>• <span className="text-yellow-600">Apoptotic</span> (yellow)</div>
          </div>
          <div>
            <div className="font-semibold mb-1">Current View:</div>
            <div className="px-2 py-1 bg-blue-50 rounded text-blue-700 font-medium">
              {selectedSubstrate.charAt(0).toUpperCase() + selectedSubstrate.slice(1)} Field
            </div>
            {substrateData?.max_values?.[selectedSubstrate] && (
              <div className="mt-1 text-gray-600 text-xs">
                Max: {substrateData.max_values[selectedSubstrate].toFixed(1)}
              </div>
            )}
            <div className="mt-2 text-gray-500 text-xs">
              {substrateData && substrateData[selectedSubstrate as keyof SubstrateData] 
                ? '✓ Data loaded'
                : '⚠ No data'}
            </div>
          </div>
        </div>
        {detailedMode && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="font-semibold text-xs mb-1">📍 3D Labels (Detailed Mode):</div>
            <div className="text-xs text-gray-600">
              Zone names, nanobot states, vessel info, and scale bar are visible
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

