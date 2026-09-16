import React, { useRef, useEffect, useState } from 'react';

interface HuntNanobot {
  id: number;
  position: [number, number];
  state: 'searching' | 'targeting' | 'delivering' | 'returning' | 'reloading';
  drug_payload: number;
  kills: number;
  is_llm: boolean;
  target_id: number | null;
}

interface HuntCell {
  id: number;
  position: [number, number];
  accumulated_drug: number;
  is_alive: boolean;
  wave: number;
}

interface TumorHuntGridProps {
  domainSize: number;
  nanobots: HuntNanobot[];
  cells: HuntCell[];
  pheromoneTrail?: number[][] | null;
  pheromoneRecruitment?: number[][] | null;
  showPheromones?: boolean;
  canvasSize?: number;
}

export const TumorHuntGrid: React.FC<TumorHuntGridProps> = ({
  domainSize,
  nanobots,
  cells,
  pheromoneTrail,
  pheromoneRecruitment,
  showPheromones = true,
  canvasSize = 580,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pulsePhase, setPulsePhase] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => setPulsePhase(p => (p + 0.1) % (Math.PI * 2)), 50);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const scale = canvasSize / domainSize;
    ctx.clearRect(0, 0, canvasSize, canvasSize);

    // Dark background
    ctx.fillStyle = '#0a0a14';
    ctx.fillRect(0, 0, canvasSize, canvasSize);

    // Draw pheromone overlays
    if (showPheromones) {
      if (pheromoneTrail && pheromoneTrail.length > 0) {
        const res = pheromoneTrail.length;
        const cellPx = canvasSize / res;
        for (let x = 0; x < res; x++) {
          for (let y = 0; y < res; y++) {
            const val = (pheromoneTrail[x]?.[y] ?? 0) / 10.0;
            if (val > 0.01) {
              ctx.fillStyle = `rgba(34, 197, 94, ${val * 0.4})`; // green trail
              ctx.fillRect(x * cellPx, y * cellPx, cellPx, cellPx);
            }
          }
        }
      }
      if (pheromoneRecruitment && pheromoneRecruitment.length > 0) {
        const res = pheromoneRecruitment.length;
        const cellPx = canvasSize / res;
        for (let x = 0; x < res; x++) {
          for (let y = 0; y < res; y++) {
            const val = (pheromoneRecruitment[x]?.[y] ?? 0) / 10.0;
            if (val > 0.01) {
              ctx.fillStyle = `rgba(139, 92, 246, ${val * 0.5})`; // purple recruitment
              ctx.fillRect(x * cellPx, y * cellPx, cellPx, cellPx);
            }
          }
        }
      }
    }

    // Draw reload stations (corners)
    const margin = 20 * scale;
    const stationPositions: [number, number][] = [
      [margin, margin],
      [canvasSize - margin, margin],
      [margin, canvasSize - margin],
      [canvasSize - margin, canvasSize - margin],
    ];
    stationPositions.forEach(([sx, sy]) => {
      const pulse = 1 + 0.15 * Math.sin(pulsePhase);
      ctx.beginPath();
      ctx.arc(sx, sy, 12 * pulse, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(251, 191, 36, 0.2)';
      ctx.fill();
      ctx.strokeStyle = '#fbbf24';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      // R label
      ctx.fillStyle = '#fbbf24';
      ctx.font = 'bold 9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('R', sx, sy + 3);
    });

    // Draw tumor cells
    cells.forEach(cell => {
      const cx = cell.position[0] * scale;
      const cy = cell.position[1] * scale;
      const drugPct = cell.accumulated_drug / 3.0; // normalized to kill threshold

      if (cell.is_alive) {
        // Alive cells: red, brighter if partially treated
        const r = Math.floor(239 - drugPct * 100);
        const g = Math.floor(68 + drugPct * 80);
        ctx.beginPath();
        ctx.arc(cx, cy, 6, 0, Math.PI * 2);
        ctx.fillStyle = `rgb(${r}, ${g}, 68)`;
        ctx.fill();
        // Glow for heavily-dosed cells
        if (drugPct > 0.5) {
          ctx.shadowColor = '#fbbf24';
          ctx.shadowBlur = 8;
          ctx.beginPath();
          ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        // Drug accumulation arc
        if (drugPct > 0) {
          ctx.beginPath();
          ctx.arc(cx, cy, 8, -Math.PI / 2, -Math.PI / 2 + drugPct * Math.PI * 2);
          ctx.strokeStyle = '#fbbf24';
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      } else {
        // Dead cells: small dark gray
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(107, 114, 128, 0.4)';
        ctx.fill();
      }
    });

    // Draw nanobots
    const stateColors: Record<string, string> = {
      searching: '#60a5fa',
      targeting: '#fbbf24',
      delivering: '#34d399',
      returning: '#f97316',
      reloading: '#a78bfa',
    };

    nanobots.forEach(bot => {
      const bx = bot.position[0] * scale;
      const by = bot.position[1] * scale;
      const color = stateColors[bot.state] || '#9ca3af';

      // Outer ring for LLM bots
      if (bot.is_llm) {
        ctx.beginPath();
        ctx.arc(bx, by, 11, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(251, 191, 36, 0.6)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Body
      ctx.beginPath();
      ctx.arc(bx, by, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // Drug payload dot
      const drugPct = bot.drug_payload / 30.0;
      ctx.beginPath();
      ctx.arc(bx, by, 3, 0, Math.PI * 2);
      ctx.fillStyle = drugPct > 0.5 ? '#1d4ed8' : '#991b1b';
      ctx.fill();

      // Kill counter badge
      if (bot.kills > 0) {
        ctx.fillStyle = '#ef4444';
        ctx.beginPath();
        ctx.arc(bx + 7, by - 7, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'white';
        ctx.font = 'bold 7px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(String(bot.kills), bx + 7, by - 4);
      }
    });

  }, [nanobots, cells, pheromoneTrail, pheromoneRecruitment, showPheromones, domainSize, canvasSize, pulsePhase]);

  return (
    <canvas
      ref={canvasRef}
      width={canvasSize}
      height={canvasSize}
      style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', background: '#0a0a14' }}
    />
  );
};

export default TumorHuntGrid;
