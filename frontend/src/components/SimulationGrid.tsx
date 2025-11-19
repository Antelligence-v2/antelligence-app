// src/components/simulation/SimulationGrid.tsx

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import React from "react";

// Define ant interface matching backend data
interface Ant {
  id: number | string;
  pos: [number, number];
  carrying_food: boolean;
  is_llm: boolean;
  is_queen?: boolean;
  steps_since_food?: number;
}

// Define predator interface matching backend data
interface Predator {
  id: number | string;
  pos: [number, number];
  energy: number;
  is_llm: boolean;
  ants_caught: number;
  hunt_cooldown: number;
}

interface EfficiencyData {
  efficiency_grid: number[][];
  max_efficiency: number;
  hotspot_locations: [number, number][];
}

interface PheromoneData {
  trail: number[][];
  alarm: number[][];
  recruitment: number[][];
  fear?: number[][];
  max_values: {
    trail: number;
    alarm: number;
    recruitment: number;
    fear?: number;
  };
}

interface SimulationGridProps {
  gridWidth: number;
  gridHeight: number;
  ants: Ant[];
  food: [number, number][];
  nestPosition?: [number, number];
  predators?: Predator[];
  efficiencyData?: EfficiencyData | null;
  pheromoneData?: PheromoneData | null;
}

export const SimulationGrid = ({ 
  gridWidth, 
  gridHeight, 
  ants, 
  food, 
  nestPosition,
  predators = [],
  efficiencyData,
  pheromoneData
}: SimulationGridProps) => {
  const getAntEmoji = (ant: Ant) => {
    if (ant.is_queen) return "👑"; 
    return "🐜";
  };

  const getAntColor = (ant: Ant) => {
    if (ant.is_queen) return "var(--primary)";
    if (ant.carrying_food) return "#f59e0b"; // Amber/Orange for carrying food
    return ant.is_llm ? "#3b82f6" : "#10b981"; // Blue for LLM, green for rule-based
  };

  const cellSize = Math.min(600 / gridWidth, 600 / gridHeight);
  
  const nest = nestPosition || [Math.floor(gridWidth / 2), Math.floor(gridHeight / 2)];

  // Create enhanced efficiency overlay with dynamic heatmap
  const renderEfficiencyOverlay = () => {
    if (!efficiencyData) return null;

    const maxEfficiency = efficiencyData.max_efficiency;
    if (maxEfficiency === 0) return null;

    return (
      <div className="absolute inset-0 pointer-events-none mix-blend-soft-light">
        {efficiencyData.efficiency_grid.map((row, y) =>
          row.map((value, x) => {
            if (value === 0) return null;
            const intensity = Math.min(value / maxEfficiency, 1.0);
            if (intensity < 0.05) return null;
            
            return (
              <div
                key={`efficiency-${x}-${y}`}
                className="absolute"
                style={{
                  left: x * cellSize,
                  top: y * cellSize,
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(245, 158, 11, ${intensity * 0.6})`, // Amber glow
                  borderRadius: '2px',
                }}
              />
            );
          })
        )}
      </div>
    );
  };

  const renderPheromoneOverlay = () => {
    if (!pheromoneData) return null;

    const { trail, alarm, recruitment, fear, max_values } = pheromoneData;
    
    return (
      <div className="absolute inset-0 pointer-events-none">
        {/* Trail pheromones (Green) */}
        {trail.map((row, y) =>
          row.map((value, x) => {
            if (value === 0) return null;
            const intensity = Math.min(value / max_values.trail, 1.0);
            if (intensity < 0.03) return null;
            
            return (
              <div
                key={`trail-${x}-${y}`}
                className="absolute rounded-sm"
                style={{
                  left: x * cellSize,
                  top: y * cellSize,
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(16, 185, 129, ${intensity * 0.5})`,
                  border: intensity > 0.5 ? '1px solid rgba(16, 185, 129, 0.3)' : 'none',
                }}
              />
            );
          })
        )}
        
        {/* Alarm pheromones (Red) */}
        {alarm.map((row, y) =>
          row.map((value, x) => {
            if (value === 0) return null;
            const intensity = Math.min(value / max_values.alarm, 1.0);
            if (intensity < 0.03) return null;
            
            return (
              <div
                key={`alarm-${x}-${y}`}
                className="absolute rounded-sm"
                style={{
                  left: x * cellSize,
                  top: y * cellSize,
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(239, 68, 68, ${intensity * 0.5})`,
                }}
              />
            );
          })
        )}
        
        {/* Recruitment pheromones (Blue) */}
        {recruitment.map((row, y) =>
          row.map((value, x) => {
            if (value === 0) return null;
            const intensity = Math.min(value / max_values.recruitment, 1.0);
            if (intensity < 0.03) return null;
            
            return (
              <div
                key={`recruitment-${x}-${y}`}
                className="absolute rounded-sm"
                style={{
                  left: x * cellSize,
                  top: y * cellSize,
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(59, 130, 246, ${intensity * 0.5})`,
                }}
              />
            );
          })
        )}

        {/* Fear pheromones (Purple) */}
        {fear && fear.map((row, y) =>
          row.map((value, x) => {
            if (value === 0) return null;
            const intensity = Math.min(value / (max_values.fear || 1), 1.0);
            if (intensity < 0.03) return null;
            
            return (
              <div
                key={`fear-${x}-${y}`}
                className="absolute rounded-sm"
                style={{
                  left: x * cellSize,
                  top: y * cellSize,
                  width: cellSize,
                  height: cellSize,
                  backgroundColor: `rgba(168, 85, 247, ${intensity * 0.6})`,
                }}
              />
            );
          })
        )}
      </div>
    );
  };

  return (
    <TooltipProvider>
      <div className="relative flex flex-col items-center">
        <div
          className="relative rounded-xl overflow-hidden shadow-xl border border-border/50"
          style={{
            width: gridWidth * cellSize,
            height: gridHeight * cellSize,
            // Vibrant, multi-color gradient background
            backgroundColor: '#1a1b26', // Deep dark blue/black base
            backgroundImage: `
              linear-gradient(to right, rgba(255, 255, 255, 0.1) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(255, 255, 255, 0.1) 1px, transparent 1px),
              radial-gradient(circle at 0% 0%, rgba(59, 130, 246, 0.15), transparent 50%),
              radial-gradient(circle at 100% 0%, rgba(236, 72, 153, 0.15), transparent 50%),
              radial-gradient(circle at 100% 100%, rgba(16, 185, 129, 0.15), transparent 50%),
              radial-gradient(circle at 0% 100%, rgba(245, 158, 11, 0.15), transparent 50%)
            `,
            backgroundSize: `${cellSize}px ${cellSize}px, ${cellSize}px ${cellSize}px, cover, cover, cover, cover`,
          }}
        >
          {/* Pheromone overlay (bottom layer) */}
          {renderPheromoneOverlay()}

          {/* Efficiency overlay (middle layer) */}
          {renderEfficiencyOverlay()}

          {/* Nest/Home */}
          {!ants.some(ant => ant.is_queen && ant.pos[0] === nest[0] && ant.pos[1] === nest[1]) && (
            <div
              className="absolute flex items-center justify-center text-2xl z-10 animate-pulse"
              style={{
                left: nest[0] * cellSize,
                top: nest[1] * cellSize,
                width: cellSize,
                height: cellSize,
                filter: 'drop-shadow(0 0 8px rgba(255, 255, 255, 0.5))',
              }}
            >
              🏠
            </div>
          )}

          {/* Sugar Cubes */}
          {food.map((pile, index) => (
            <div
              key={`food-${index}`}
              className="absolute flex items-center justify-center text-lg z-10 animate-in zoom-in duration-300"
              style={{
                left: pile[0] * cellSize,
                top: pile[1] * cellSize,
                width: cellSize,
                height: cellSize,
                filter: 'drop-shadow(0 0 4px rgba(16, 185, 129, 0.6))',
              }}
            >
              🍩
            </div>
          ))}

          {/* Ants */}
          {ants.map((ant) => (
            <Tooltip key={ant.id}>
              <TooltipTrigger asChild>
                <div
                  className="absolute transition-all duration-300 ease-out"
                  style={{
                    left: ant.pos[0] * cellSize,
                    top: ant.pos[1] * cellSize,
                    width: cellSize,
                    height: cellSize,
                    fontSize: ant.is_queen ? '1.8rem' : '1.4rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: ant.is_queen ? 30 : 20,
                    filter: ant.carrying_food 
                      ? 'drop-shadow(0 0 4px rgba(245, 158, 11, 0.8))' 
                      : `drop-shadow(0 0 2px ${getAntColor(ant)})`,
                  }}
                >
                  {getAntEmoji(ant)}
                  {ant.carrying_food && !ant.is_queen && (
                    <div className="absolute -top-1 -right-1 text-[10px] leading-none animate-bounce">🍩</div>
                  )}
                </div>
              </TooltipTrigger>
              <TooltipContent className="text-xs bg-popover/95 backdrop-blur-sm">
                <div className="space-y-1">
                  <div><span className="font-semibold">ID:</span> {ant.id}</div>
                  <div><span className="font-semibold">Type:</span> {
                    ant.is_queen ? "Queen" : (ant.is_llm ? "LLM Agent" : "Rule Agent")
                  }</div>
                  <div><span className="font-semibold">Pos:</span> {ant.pos[0]}, {ant.pos[1]}</div>
                </div>
              </TooltipContent>
            </Tooltip>
          ))}

          {/* Predators */}
          {predators.map((predator) => (
            <Tooltip key={predator.id}>
              <TooltipTrigger asChild>
                <div
                  className="absolute transition-all duration-300"
                  style={{
                    left: predator.pos[0] * cellSize,
                    top: predator.pos[1] * cellSize,
                    width: cellSize,
                    height: cellSize,
                    fontSize: '1.6rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 25,
                    filter: 'drop-shadow(0 0 6px rgba(239, 68, 68, 0.6))',
                  }}
                >
                  🕷️
                  {predator.energy < 50 && (
                    <div className="absolute -bottom-1 -right-1 text-[10px]">💤</div>
                  )}
                </div>
              </TooltipTrigger>
              <TooltipContent className="text-xs bg-destructive/90 text-destructive-foreground">
                <div className="space-y-1">
                  <div><span className="font-semibold">ID:</span> {predator.id}</div>
                  <div><span className="font-semibold">Energy:</span> {predator.energy}/100</div>
                </div>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </div>
    </TooltipProvider>
  );
};
