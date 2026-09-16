import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { TumorHuntGrid } from '../components/TumorHuntGrid';
import { BUILD_INFO, IS_PREVIEW_MODE, API_BASE_URL } from '../lib/runtime';

const API_BASE = API_BASE_URL;

interface HuntConfig {
  domain_size: number;
  n_nanobots: number;
  agent_type: string;
  selected_model: string;
  use_queen: boolean;
  use_llm_queen: boolean;
  max_steps: number;
  initial_cells: number;
  wave_interval: number;
  cells_per_wave: number;
  max_waves: number;
  drug_kill_threshold: number;
  nanobot_speed: number;
  drug_payload: number;
  drug_delivery_rate: number;
  pheromone_decay: number;
}

const DEFAULT_CONFIG: HuntConfig = {
  domain_size: 600,
  n_nanobots: 10,
  agent_type: 'Rule-Based',
  selected_model: 'meta-llama/Llama-3.3-70B-Instruct',
  use_queen: false,
  use_llm_queen: false,
  max_steps: 150,
  initial_cells: 10,
  wave_interval: 25,
  cells_per_wave: 6,
  max_waves: 4,
  drug_kill_threshold: 3.0,
  nanobot_speed: 40.0,
  drug_payload: 30.0,
  drug_delivery_rate: 5.0,
  pheromone_decay: 0.08,
};

export default function TumorHunt() {
  const [config, setConfig] = useState<HuntConfig>(DEFAULT_CONFIG);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showPheromones, setShowPheromones] = useState(true);
  const [waveNotification, setWaveNotification] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const playIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentStepData = results?.history?.[currentStep];
  const totalSteps = results?.history?.length ?? 0;

  // Detect wave spawns by comparing cell counts between steps
  useEffect(() => {
    if (!results || currentStep === 0) return;
    const prev = results.history[currentStep - 1];
    const curr = results.history[currentStep];
    if (prev && curr) {
      const prevAlive = prev.cells?.filter((c: any) => c.is_alive).length ?? 0;
      const currAlive = curr.cells?.filter((c: any) => c.is_alive).length ?? 0;
      const currKilled = curr.metrics?.cells_killed ?? 0;
      const prevKilled = prev.metrics?.cells_killed ?? 0;
      // New cells appeared (alive count went up despite kills)
      if (currAlive + currKilled > prevAlive + prevKilled) {
        const wave = curr.metrics?.waves_spawned ?? 0;
        setWaveNotification(`⚠️ Wave ${wave} arrived! New tumor cells detected.`);
        setTimeout(() => setWaveNotification(null), 3000);
      }
    }
  }, [currentStep, results]);

  // Playback interval
  useEffect(() => {
    if (isPlaying) {
      playIntervalRef.current = setInterval(() => {
        setCurrentStep(s => {
          if (s >= totalSteps - 1) { setIsPlaying(false); return s; }
          return s + 1;
        });
      }, 300);
    } else {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    }
    return () => { if (playIntervalRef.current) clearInterval(playIntervalRef.current); };
  }, [isPlaying, totalSteps]);

  const handleRun = async () => {
    if (IS_PREVIEW_MODE) {
      setError(null);
      setResults(null);
      setCurrentStep(0);
      setIsPlaying(false);
      setProgress(0);
      setWaveNotification('Preview mode only: Tumor Hunt backend stays local.');
      setTimeout(() => setWaveNotification(null), 2500);
      return;
    }

    setIsRunning(true);
    setError(null);
    setResults(null);
    setCurrentStep(0);
    setIsPlaying(false);
    setProgress(0);

    progressIntervalRef.current = setInterval(() => {
      setProgress(p => Math.min(p + 1.5, 90));
    }, 200);

    try {
      const res = await axios.post(`${API_BASE}/simulation/tumor/hunt`, config, { timeout: 300000 });
      setResults(res.data);
      setProgress(100);
      setCurrentStep(0);
      setIsPlaying(true);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Request failed');
    } finally {
      setIsRunning(false);
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    }
  };

  // Find latest pheromone data (look-back)
  let pheromoneTrail: number[][] | null = null;
  let pheromoneRecruitment: number[][] | null = null;
  if (results) {
    for (let i = currentStep; i >= 0; i--) {
      const h = results.history[i];
      if (h?.pheromone_trail) { pheromoneTrail = h.pheromone_trail; }
      if (h?.pheromone_recruitment) { pheromoneRecruitment = h.pheromone_recruitment; }
      if (pheromoneTrail && pheromoneRecruitment) break;
    }
  }

  const metrics = currentStepData?.metrics ?? {};
  const nanobots = currentStepData?.nanobots ?? [];
  const cells = currentStepData?.cells ?? [];
  const aliveCount = cells.filter((c: any) => c.is_alive).length;
  const deadCount = cells.filter((c: any) => !c.is_alive).length;

  const sliderFields: [string, keyof HuntConfig, number, number, number][] = [
    ['Nanobots', 'n_nanobots', 1, 50, 1],
    ['Max Steps', 'max_steps', 20, 500, 10],
    ['Initial Cells', 'initial_cells', 1, 50, 1],
    ['Wave Interval (steps)', 'wave_interval', 5, 100, 5],
    ['Cells per Wave', 'cells_per_wave', 1, 30, 1],
    ['Max Waves', 'max_waves', 1, 20, 1],
    ['Kill Threshold (drug)', 'drug_kill_threshold', 0.5, 20, 0.5],
  ];

  const statItems: [string, string | number, string][] = [
    ['🔴 Cells Alive', aliveCount, '#f87171'],
    ['💀 Cells Killed', deadCount, '#34d399'],
    ['🌊 Wave', metrics.waves_spawned ?? 0, '#60a5fa'],
    ['💉 Drug Delivered', (metrics.total_drug_delivered ?? 0).toFixed(1), '#a78bfa'],
    ['⚡ Efficiency', (metrics.drug_efficiency ?? 0).toFixed(4), '#fbbf24'],
    ['🔍 Searching', metrics.nanobots_searching ?? 0, '#9ca3af'],
    ['🎯 Targeting', metrics.nanobots_targeting ?? 0, '#fbbf24'],
    ['💚 Delivering', metrics.nanobots_delivering ?? 0, '#34d399'],
  ];

  const legendItems: [string, string][] = [
    ['🔴 Alive Tumor Cell', '#ef4444'],
    ['⚫ Killed Cell', '#6b7280'],
    ['🔵 Searching', '#60a5fa'],
    ['🟡 Targeting', '#fbbf24'],
    ['🟢 Delivering', '#34d399'],
    ['🟠 Returning', '#f97316'],
    ['🟣 Reloading', '#a78bfa'],
    ['🟡R Reload Station', '#fbbf24'],
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#0d0d1a', color: 'white', padding: '24px', fontFamily: 'monospace' }}>
      <div style={{ maxWidth: 1300, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 24, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 'bold', color: '#f87171', marginBottom: 4 }}>
              🧬 Tumor Hunt v2
            </h1>
            <p style={{ color: '#9ca3af', fontSize: 14 }}>
              Dynamic wave-based tumor cell spawning. LLM-brained nanobots hunt and eradicate each wave.
            </p>
            {IS_PREVIEW_MODE && (
              <p style={{ color: '#fbbf24', fontSize: 12, marginTop: 6 }}>
                Preview build: {BUILD_INFO.buildLabel}. Backend execution is disabled on the public frontend.
              </p>
            )}
          </div>
          <a
            href="/"
            style={{
              color: '#6b7280', fontSize: 12, textDecoration: 'none',
              border: '1px solid #374151', borderRadius: 4, padding: '6px 12px',
              display: 'inline-block', marginTop: 4,
            }}
          >
            ← Back to Colony
          </a>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 24 }}>
          {/* Left panel — config + stats */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Config card */}
            <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, padding: 16 }}>
              <h3 style={{ color: '#f9fafb', marginBottom: 12, fontSize: 14 }}>Configuration</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <label style={{ fontSize: 12, color: '#9ca3af' }}>
                  Agent Type
                  <select
                    value={config.agent_type}
                    onChange={e => setConfig(c => ({ ...c, agent_type: e.target.value }))}
                    style={{ display: 'block', width: '100%', marginTop: 4, background: '#1f2937', color: 'white', border: '1px solid #374151', borderRadius: 4, padding: '4px 8px', fontSize: 12 }}
                  >
                    <option>Rule-Based</option>
                    <option>LLM-Powered</option>
                    <option>Hybrid</option>
                  </select>
                </label>
                {config.agent_type !== 'Rule-Based' && (
                  <label style={{ fontSize: 12, color: '#9ca3af' }}>
                    Model
                    <select
                      value={config.selected_model}
                      onChange={e => setConfig(c => ({ ...c, selected_model: e.target.value }))}
                      style={{ display: 'block', width: '100%', marginTop: 4, background: '#1f2937', color: 'white', border: '1px solid #374151', borderRadius: 4, padding: '4px 8px', fontSize: 12 }}
                    >
                      <option value="meta-llama/Llama-3.3-70B-Instruct">Llama-3.3-70B</option>
                      <option value="mistralai/Mistral-Large-Instruct-2411">Mistral-Large</option>
                      <option value="deepseek/deepseek-chat">DeepSeek</option>
                    </select>
                  </label>
                )}
                {sliderFields.map(([label, key, min, max, step]) => (
                  <label key={key} style={{ fontSize: 12, color: '#9ca3af' }}>
                    {label}: <span style={{ color: '#f9fafb' }}>{config[key] as number}</span>
                    <input
                      type="range"
                      min={min}
                      max={max}
                      step={step}
                      value={config[key] as number}
                      onChange={e => setConfig(c => ({ ...c, [key]: parseFloat(e.target.value) }))}
                      style={{ display: 'block', width: '100%', marginTop: 2 }}
                    />
                  </label>
                ))}
                <label style={{ fontSize: 12, color: '#9ca3af', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={showPheromones} onChange={e => setShowPheromones(e.target.checked)} />
                  Show Pheromone Overlay
                </label>
              </div>

              <button
                onClick={handleRun}
                disabled={isRunning}
                style={{
                  marginTop: 16, width: '100%', padding: '10px 0',
                  background: isRunning ? '#374151' : '#dc2626',
                  color: 'white', border: 'none', borderRadius: 6,
                  cursor: isRunning ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold', fontSize: 14, fontFamily: 'monospace',
                }}
              >
                {isRunning ? `Running... ${progress.toFixed(0)}%` : '▶ Run Hunt'}
              </button>

              {error && <div style={{ marginTop: 8, color: '#f87171', fontSize: 12 }}>{error}</div>}
            </div>

            {/* Stats card */}
            {results && (
              <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 8, padding: 16 }}>
                <h3 style={{ color: '#f9fafb', marginBottom: 12, fontSize: 14 }}>
                  Live Stats — Step {currentStepData?.step ?? 0}
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {statItems.map(([label, val, color]) => (
                    <div key={label} style={{ background: '#1f2937', borderRadius: 4, padding: '6px 8px' }}>
                      <div style={{ fontSize: 10, color: '#6b7280' }}>{label}</div>
                      <div style={{ fontSize: 16, fontWeight: 'bold', color }}>{val}</div>
                    </div>
                  ))}
                </div>

                {/* Final summary */}
                {!isPlaying && results && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #374151' }}>
                    <div style={{ fontSize: 11, color: '#9ca3af' }}>Final Results</div>
                    <div style={{ fontSize: 12, color: '#f9fafb', marginTop: 4 }}>
                      Kill Rate:{' '}
                      <span style={{ color: '#34d399', fontWeight: 'bold' }}>
                        {((results.kill_rate ?? 0) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#f9fafb' }}>
                      {results.cells_killed} / {results.cells_spawned} cells eliminated in {results.total_steps_run} steps
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right panel — canvas + playback */}
          <div>
            {/* Wave notification */}
            {waveNotification && (
              <div style={{
                marginBottom: 12, padding: '10px 16px',
                background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444',
                borderRadius: 6, color: '#fca5a5', fontSize: 14, fontWeight: 'bold',
              }}>
                {waveNotification}
              </div>
            )}

            {/* Canvas */}
            {results ? (
              <TumorHuntGrid
                domainSize={config.domain_size}
                nanobots={nanobots}
                cells={cells}
                pheromoneTrail={showPheromones ? pheromoneTrail : null}
                pheromoneRecruitment={showPheromones ? pheromoneRecruitment : null}
                showPheromones={showPheromones}
                canvasSize={580}
              />
            ) : (
              <div style={{
                width: 580, height: 580,
                background: '#111827', border: '1px solid #1f2937',
                borderRadius: 8, display: 'flex', alignItems: 'center',
                justifyContent: 'center', color: '#4b5563', fontSize: 14,
              }}>
                {isRunning ? 'Simulation running...' : 'Configure and run the hunt simulation'}
              </div>
            )}

            {/* Playback controls */}
            {results && (
              <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
                <button
                  onClick={() => setCurrentStep(0)}
                  style={{ background: '#1f2937', color: 'white', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', fontSize: 12 }}
                >
                  ⏮
                </button>
                <button
                  onClick={() => setCurrentStep(s => Math.max(0, s - 1))}
                  style={{ background: '#1f2937', color: 'white', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', fontSize: 12 }}
                >
                  ◀
                </button>
                <button
                  onClick={() => setIsPlaying(p => !p)}
                  style={{ background: '#dc2626', color: 'white', border: 'none', borderRadius: 4, padding: '6px 16px', cursor: 'pointer', fontSize: 14 }}
                >
                  {isPlaying ? '⏸' : '▶'}
                </button>
                <button
                  onClick={() => setCurrentStep(s => Math.min(totalSteps - 1, s + 1))}
                  style={{ background: '#1f2937', color: 'white', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', fontSize: 12 }}
                >
                  ▶
                </button>
                <button
                  onClick={() => setCurrentStep(totalSteps - 1)}
                  style={{ background: '#1f2937', color: 'white', border: 'none', borderRadius: 4, padding: '6px 12px', cursor: 'pointer', fontSize: 12 }}
                >
                  ⏭
                </button>
                <div style={{ flex: 1, marginLeft: 8 }}>
                  <input
                    type="range"
                    min={0}
                    max={Math.max(0, totalSteps - 1)}
                    value={currentStep}
                    onChange={e => { setCurrentStep(Number(e.target.value)); setIsPlaying(false); }}
                    style={{ width: '100%' }}
                  />
                </div>
                <span style={{ fontSize: 11, color: '#6b7280', whiteSpace: 'nowrap' }}>
                  {currentStep + 1} / {totalSteps}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Legend */}
        <div style={{ marginTop: 16, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          {legendItems.map(([label, color]) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#9ca3af' }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
