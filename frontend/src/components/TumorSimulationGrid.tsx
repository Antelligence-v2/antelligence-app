import { useEffect, useRef, useState } from "react";

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

interface TumorSimulationGridProps {
  domainSize: number;
  nanobots: NanobotState[];
  tumorCells: TumorCellState[];
  vessels: VesselState[];
  substrateData: SubstrateData | null;
  selectedSubstrate: string;
  tumorRadius?: number;
  detailedMode?: boolean;
}

export function TumorSimulationGrid({
  domainSize,
  nanobots,
  tumorCells,
  vessels,
  substrateData,
  selectedSubstrate,
  tumorRadius = 200,
  detailedMode = false,
}: TumorSimulationGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pulsePhase, setPulsePhase] = useState(0);
  const [nanobotTrails, setNanobotTrails] = useState<Map<number, [number, number][]>>(new Map());

  // Animation for pulsing vessels
  useEffect(() => {
    const interval = setInterval(() => {
      setPulsePhase(prev => (prev + 0.1) % (Math.PI * 2));
    }, 50);
    return () => clearInterval(interval);
  }, []);

  // Track nanobot movement trails
  useEffect(() => {
    const newTrails = new Map(nanobotTrails);
    nanobots.forEach(nanobot => {
      const trail = newTrails.get(nanobot.id) || [];
      trail.push([nanobot.position[0], nanobot.position[1]]);
      // Keep only last 10 positions
      if (trail.length > 10) trail.shift();
      newTrails.set(nanobot.id, trail);
    });
    setNanobotTrails(newTrails);
  }, [nanobots]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Set canvas size
    const size = Math.min(window.innerWidth * 0.6, 800);
    canvas.width = size;
    canvas.height = size;

    // Clear canvas with light background
    ctx.fillStyle = "#fafafa";
    ctx.fillRect(0, 0, size, size);

    // Scale factor to convert µm to pixels
    const scale = size / domainSize;
    const center = [domainSize / 2, domainSize / 2];
    const centerPx = [center[0] * scale, center[1] * scale];

    // Draw tumor boundary regions FIRST (as background)
    // Necrotic core (darkest)
    const necroticRadius = (tumorRadius * 0.25) * scale;
    ctx.fillStyle = "rgba(100, 100, 100, 0.15)";
    ctx.beginPath();
    ctx.arc(centerPx[0], centerPx[1], necroticRadius, 0, Math.PI * 2);
    ctx.fill();

    // Hypoxic zone (purple tint)
    const hypoxicRadius = (tumorRadius * 0.7) * scale;
    ctx.fillStyle = "rgba(168, 85, 247, 0.08)";
    ctx.beginPath();
    ctx.arc(centerPx[0], centerPx[1], hypoxicRadius, 0, Math.PI * 2);
    ctx.fill();

    // Viable tumor region (light red tint)
    const tumorRadiusPx = tumorRadius * scale;
    ctx.fillStyle = "rgba(239, 68, 68, 0.05)";
    ctx.beginPath();
    ctx.arc(centerPx[0], centerPx[1], tumorRadiusPx, 0, Math.PI * 2);
    ctx.fill();

    // Draw tumor boundary (prominent circle)
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.arc(centerPx[0], centerPx[1], tumorRadiusPx, 0, Math.PI * 2);
    ctx.stroke();

    // Add zone labels if in detailed mode
    if (detailedMode) {
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = "#374151";
      ctx.textAlign = "center";
      
      // Necrotic core label
      ctx.fillText("Necrotic Core", centerPx[0], centerPx[1]);
      
      // Hypoxic zone label
      ctx.fillText("Hypoxic Zone", centerPx[0], centerPx[1] - hypoxicRadius / 2);
      
      // Viable tumor label
      ctx.fillText("Viable Tumor", centerPx[0], centerPx[1] - tumorRadiusPx * 0.85);
    }

    // Draw substrate heatmap (with reduced opacity)
    if (substrateData && substrateData[selectedSubstrate as keyof SubstrateData]) {
      const data = substrateData[selectedSubstrate as keyof SubstrateData] as number[][];
      const maxValue = substrateData.max_values?.[selectedSubstrate] || 1;

      if (data && data.length > 0) {
        const gridSize = data.length;
        const cellSize = size / gridSize;

        for (let i = 0; i < gridSize; i++) {
          for (let j = 0; j < gridSize; j++) {
            const value = data[j][i]; // Transposed
            const normalized = Math.min(value / maxValue, 1);

            // Color mapping based on substrate type (reduced opacity for clarity)
            let color;
            const baseOpacity = detailedMode ? 0.4 : 0.25;
            switch (selectedSubstrate) {
              case "oxygen":
                // Blue (low O2/hypoxic) to Red (high O2/normoxic)
                color = `rgba(${255 * normalized}, ${100 * normalized}, ${255 * (1 - normalized)}, ${baseOpacity * normalized})`;
                break;
              case "drug":
                // Orange gradient
                color = `rgba(${255 * normalized}, ${165 * normalized}, 0, ${baseOpacity * normalized})`;
                break;
              case "trail":
                // Emerald green for successful paths
                color = `rgba(16, ${255 * normalized}, 150, ${baseOpacity * normalized})`;
                break;
              case "alarm":
                // Red for danger/problems
                color = `rgba(${255 * normalized}, 0, 0, ${baseOpacity * normalized})`;
                break;
              case "recruitment":
                // Blue for help needed
                color = `rgba(0, ${150 * normalized}, ${255 * normalized}, ${baseOpacity * normalized})`;
                break;
              case "chemokine_signal":
                // Bright green for "come here" signals
                color = `rgba(34, ${255 * normalized}, 100, ${baseOpacity * normalized})`;
                break;
              case "toxicity_signal":
                // Dark red for "stay away" signals
                color = `rgba(${150 * normalized}, 0, ${50 * normalized}, ${baseOpacity * normalized})`;
                break;
              default:
                color = `rgba(128, 128, 128, ${normalized * baseOpacity})`;
            }

            ctx.fillStyle = color;
            ctx.fillRect(i * cellSize, j * cellSize, cellSize, cellSize);
          }
        }
      }
    }

    // Draw grid
    ctx.strokeStyle = "rgba(200, 200, 200, 0.2)";
    ctx.lineWidth = 0.5;
    const gridLines = 20;
    const gridSpacing = size / gridLines;
    for (let i = 0; i <= gridLines; i++) {
      ctx.beginPath();
      ctx.moveTo(i * gridSpacing, 0);
      ctx.lineTo(i * gridSpacing, size);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * gridSpacing);
      ctx.lineTo(size, i * gridSpacing);
      ctx.stroke();
    }

    // Draw blood vessels (ENHANCED - more prominent)
    vessels.forEach((vessel, index) => {
      const x = vessel.position[0] * scale;
      const y = vessel.position[1] * scale;
      const radius = vessel.supply_radius * scale;

      // Pulsing supply radius
      const pulseIntensity = Math.sin(pulsePhase + index * 0.5) * 0.5 + 0.5;
      ctx.fillStyle = `rgba(16, 185, 129, ${0.08 + pulseIntensity * 0.12})`;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();

      // Outer glow
      ctx.fillStyle = `rgba(16, 185, 129, ${0.3 + pulseIntensity * 0.2})`;
      ctx.beginPath();
      ctx.arc(x, y, 12 + pulseIntensity * 4, 0, Math.PI * 2);
      ctx.fill();

      // Main vessel body
      ctx.fillStyle = "#10b981";
      ctx.strokeStyle = "#047857";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(x, y, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Inner highlight
      ctx.fillStyle = "#6ee7b7";
      ctx.beginPath();
      ctx.arc(x - 2, y - 2, 3, 0, Math.PI * 2);
      ctx.fill();

      // Label for vessels in detailed mode
      if (detailedMode) {
        ctx.font = "bold 10px sans-serif";
        ctx.fillStyle = "#047857";
        ctx.textAlign = "center";
        ctx.fillText("O₂+Drug", x, y + radius + 12);
      }
    });

    // Draw tumor cells (sampled, if too many)
    const cellsToShow = tumorCells.length > 200 ? 
      tumorCells.filter((_, i) => i % Math.ceil(tumorCells.length / 200) === 0) : 
      tumorCells;

    cellsToShow.forEach((cell) => {
      const x = cell.position[0] * scale;
      const y = cell.position[1] * scale;

      // Color based on phase
      let color;
      let strokeColor;
      switch (cell.phase) {
        case "viable":
          color = "#ef4444";
          strokeColor = "#991b1b";
          break;
        case "hypoxic":
          color = "#a855f7";
          strokeColor = "#6b21a8";
          break;
        case "necrotic":
          color = "#6b7280";
          strokeColor = "#374151";
          break;
        case "apoptotic":
          color = "#fbbf24";
          strokeColor = "#92400e";
          break;
        default:
          color = "#ef4444";
          strokeColor = "#991b1b";
      }

      ctx.fillStyle = color;
      ctx.strokeStyle = strokeColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });

    // Draw nanobot movement trails (in detailed mode)
    if (detailedMode) {
      nanobots.forEach((nanobot) => {
        const trail = nanobotTrails.get(nanobot.id) || [];
        if (trail.length > 1) {
          ctx.strokeStyle = "rgba(59, 130, 246, 0.3)";
          ctx.lineWidth = 2;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          trail.forEach((pos, i) => {
            const px = pos[0] * scale;
            const py = pos[1] * scale;
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          });
          ctx.stroke();
          ctx.setLineDash([]);
        }
      });
    }

    // Draw nanobots (ENHANCED - larger and clearer)
    nanobots.forEach((nanobot) => {
      const x = nanobot.position[0] * scale;
      const y = nanobot.position[1] * scale;

      // Draw nanobot based on state
      const payloadPercent = nanobot.drug_payload / 100;
      
      // Outer circle (state indication) - LARGER
      let outerColor;
      let stateName = "";
      switch (nanobot.state) {
        case "targeting":
          outerColor = "#fbbf24";
          stateName = "→";
          break;
        case "delivering":
          outerColor = "#10b981";
          stateName = "💊";
          break;
        case "returning":
          outerColor = "#3b82f6";
          stateName = "←";
          break;
        case "reloading":
          outerColor = "#8b5cf6";
          stateName = "⚡";
          break;
        default: // searching
          outerColor = "#6b7280";
          stateName = "?";
      }

      // Glow effect
      ctx.shadowBlur = 8;
      ctx.shadowColor = outerColor;

      // Outer circle (LARGER)
      ctx.fillStyle = outerColor;
      ctx.beginPath();
      ctx.arc(x, y, 7, 0, Math.PI * 2);
      ctx.fill();

      ctx.shadowBlur = 0;

      // Border for definition
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, 7, 0, Math.PI * 2);
      ctx.stroke();

      // Inner circle (payload indicator)
      if (payloadPercent > 0) {
        ctx.fillStyle = payloadPercent > 0.5 ? "#3b82f6" : "#ef4444";
        ctx.beginPath();
        ctx.arc(x, y, 4 * payloadPercent, 0, Math.PI * 2);
        ctx.fill();
      }

      // LLM indicator (gold ring)
      if (nanobot.is_llm) {
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(x, y, 10, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Direction indicator in detailed mode
      if (detailedMode && stateName) {
        ctx.font = "10px sans-serif";
        ctx.fillStyle = "#fff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(stateName, x, y);
      }
    });

    // Draw scale bar (bottom right)
    ctx.fillStyle = "#374151";
    ctx.font = "bold 12px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(`${domainSize} µm`, size - 20, size - 25);
    ctx.strokeStyle = "#374151";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(size - 120, size - 15);
    ctx.lineTo(size - 20, size - 15);
    ctx.stroke();

    // Add substrate legend (top right)
    if (substrateData && substrateData.max_values) {
      const maxVal = substrateData.max_values[selectedSubstrate] || 1;
      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#374151";
      ctx.textAlign = "right";
      ctx.fillText(`${selectedSubstrate.toUpperCase()}`, size - 10, 20);
      ctx.font = "10px sans-serif";
      ctx.fillText(`Max: ${maxVal.toFixed(1)}`, size - 10, 35);
    }

  }, [domainSize, nanobots, tumorCells, vessels, substrateData, selectedSubstrate, tumorRadius, detailedMode, pulsePhase, nanobotTrails]);

  return (
    <div className="flex flex-col items-center">
      <canvas 
        ref={canvasRef} 
        className="border-2 border-gray-300 rounded-lg shadow-2xl bg-white"
      />
      
      {/* Legend below canvas */}
      <div className="mt-6 w-full max-w-3xl">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          {/* Nanobot States */}
          <div className="bg-white rounded-lg border p-3 shadow-sm">
            <h4 className="font-bold text-xs text-gray-600 mb-2">🤖 NANOBOT STATES</h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-gray-500 rounded-full"></div>
                <span className="text-gray-800">Searching (?)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-gray-800">Targeting (→)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-gray-800">Delivering (💊)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span className="text-gray-800">Returning (←)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                <span className="text-gray-800">Reloading (⚡)</span>
              </div>
            </div>
          </div>

          {/* Tumor Zones */}
          <div className="bg-white rounded-lg border p-3 shadow-sm">
            <h4 className="font-bold text-xs text-gray-600 mb-2">🧠 TUMOR ZONES</h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full border-2 border-red-600"></div>
                <span className="text-gray-800">Tumor Boundary</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-200 rounded-full"></div>
                <span className="text-gray-800">Viable Region</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-200 rounded-full"></div>
                <span className="text-gray-800">Hypoxic Zone</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
                <span className="text-gray-800">Necrotic Core</span>
              </div>
            </div>
          </div>

          {/* Key Elements */}
          <div className="bg-white rounded-lg border p-3 shadow-sm">
            <h4 className="font-bold text-xs text-gray-600 mb-2">💡 KEY ELEMENTS</h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full border-2 border-green-700"></div>
                <span className="text-gray-800">Blood Vessel (O₂+Drug)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-gray-800">Viable Cancer Cells</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                <span className="text-gray-800">Hypoxic Cells</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                <span className="text-gray-800">Killed Cells</span>
              </div>
            </div>
          </div>

          {/* Substrate Fields */}
          <div className="bg-white rounded-lg border p-3 shadow-sm">
            <h4 className="font-bold text-xs text-gray-600 mb-2">🧪 SUBSTRATE FIELDS</h4>
            <div className="space-y-1 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span className="text-gray-800">Oxygen (O₂)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
                <span className="text-gray-800">Drug Concentration</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-lime-500 rounded-full"></div>
                <span className="text-gray-800">🟩 Chemokine (Attract)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-600 rounded-full"></div>
                <span className="text-gray-800">🟥 Toxicity (Repel)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Additional info */}
        <div className="mt-3 text-xs text-center text-gray-800 bg-blue-50 rounded p-2">
          💡 <strong>Tip:</strong> Nanobots start at <span className="text-green-600 font-semibold">green vessels</span> (oxygen+drug sources), 
          navigate to <span className="text-purple-600 font-semibold">hypoxic zones</span> (low oxygen), 
          deliver drugs, then return to reload. Watch the pulsing vessels! 
          <span className="text-lime-600 font-semibold">🟩 Chemokine signals</span> attract nanobots to successful delivery sites, 
          while <span className="text-red-600 font-semibold">🟥 toxicity signals</span> repel them from dangerous areas.
        </div>
      </div>
    </div>
  );
}

