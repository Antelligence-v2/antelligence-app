import React from 'react';
import { Html } from '@react-three/drei';

interface Label3DProps {
  position: [number, number, number];
  text: string;
  color?: string;
  fontSize?: number;
  backgroundColor?: string;
  show?: boolean;
}

export function Label3D({ 
  position, 
  text, 
  color = '#1f2937',
  fontSize = 12,
  backgroundColor = 'rgba(255, 255, 255, 0.9)',
  show = true
}: Label3DProps) {
  if (!show) return null;

  return (
    <Html position={position} center>
      <div
        style={{
          color,
          fontSize: `${fontSize}px`,
          backgroundColor,
          padding: '4px 8px',
          borderRadius: '4px',
          border: `1px solid ${color}`,
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 600,
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
          transform: 'translate(-50%, -50%)',
        }}
      >
        {text}
      </div>
    </Html>
  );
}

interface ZoneLabel3DProps {
  position: [number, number, number];
  zoneName: string;
  radius: number;
  show?: boolean;
}

export function ZoneLabel3D({ position, zoneName, radius, show = true }: ZoneLabel3DProps) {
  if (!show) return null;

  const colors: Record<string, string> = {
    'Necrotic Core': '#2d1b69',
    'Hypoxic Zone': '#7c3aed',
    'Viable Tumor': '#ef4444',
  };

  const color = colors[zoneName] || '#666666';

  return (
    <Html position={[position[0] + radius * 0.8, position[1] + radius * 0.8, position[2]]} center>
      <div
        style={{
          color: '#ffffff',
          fontSize: '11px',
          backgroundColor: color,
          padding: '3px 6px',
          borderRadius: '3px',
          whiteSpace: 'nowrap',
          pointerEvents: 'none',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 700,
          boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
          transform: 'translate(-50%, -50%)',
        }}
      >
        {zoneName}
      </div>
    </Html>
  );
}

