import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { Button } from '@/components/ui/button';
import { getAggregatedStats, getSimulationCount, clearSimulationHistory, exportHistoryAsJSON } from '@/lib/simulationHistory';
import { Trash2, Download } from 'lucide-react';

interface HistoricalPerformanceProps {
  onUpdate?: () => void;
}

const AGENT_COLORS: Record<string, string> = {
  'LLM-Powered': '#8b5cf6', // Purple
  'Rule-Based': '#3b82f6',  // Blue
  'Hybrid': '#10b981',      // Green
};

export function HistoricalPerformance({ onUpdate }: HistoricalPerformanceProps) {
  const [stats, setStats] = React.useState(() => {
    const result = getAggregatedStats();
    return Array.isArray(result) ? result : [];
  });
  const [simulationCount, setSimulationCount] = React.useState(() => getSimulationCount());

  // Refresh stats when component mounts or when onUpdate is called
  React.useEffect(() => {
    const refreshStats = () => {
      const result = getAggregatedStats();
      setStats(Array.isArray(result) ? result : []);
      setSimulationCount(getSimulationCount());
    };

    refreshStats();

    // Listen for storage events from other tabs
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'ant_simulation_history') {
        refreshStats();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [onUpdate]);

  const handleClearHistory = () => {
    if (window.confirm('Are you sure you want to clear all simulation history?')) {
      clearSimulationHistory();
      setStats([]);
      setSimulationCount(0);
    }
  };

  const handleExport = () => {
    try {
      const json = exportHistoryAsJSON();
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `simulation-history-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export history:', error);
    }
  };

  if (simulationCount === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>📊 Historical Performance</CardTitle>
          <CardDescription>
            Run simulations to see aggregate performance data (last 15 runs)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <p className="text-lg mb-2">No simulation history yet</p>
            <p className="text-sm">Start running simulations to build performance data</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Prepare data for the chart
  const chartData = stats.map(stat => ({
    name: stat.agentType,
    'Total Food Collected': stat.totalFood,
    'Average per Run': stat.averageFood,
    'Simulations': stat.runCount,
  }));

  return (
    <Card>
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle>📊 Historical Performance Analysis</CardTitle>
            <CardDescription>
              Aggregate data from last {simulationCount} simulation{simulationCount !== 1 ? 's' : ''}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline" 
              size="sm"
              onClick={handleExport}
              title="Export data as JSON"
            >
              <Download className="h-4 w-4" />
            </Button>
            <Button 
              variant="destructive" 
              size="sm"
              onClick={handleClearHistory}
              title="Clear all history"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {stats.map((stat) => (
            <div 
              key={stat.agentType}
              className="p-4 rounded-lg border bg-card"
              style={{ borderLeftWidth: '4px', borderLeftColor: AGENT_COLORS[stat.agentType] }}
            >
              <div className="font-semibold text-sm mb-2">{stat.agentType}</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-muted-foreground text-xs">Total Food</div>
                  <div className="font-bold text-lg">{stat.totalFood}</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">Avg/Run</div>
                  <div className="font-bold text-lg">{stat.averageFood}</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">Runs</div>
                  <div className="font-medium">{stat.runCount}</div>
                </div>
                <div>
                  <div className="text-muted-foreground text-xs">Range</div>
                  <div className="font-medium text-xs">{stat.minFood}-{stat.maxFood}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Bar Chart */}
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis 
              yAxisId="left"
              label={{ value: 'Food Collected', angle: -90, position: 'insideLeft' }}
            />
            <YAxis 
              yAxisId="right"
              orientation="right"
              label={{ value: 'Number of Runs', angle: 90, position: 'insideRight' }}
            />
            <Tooltip 
              formatter={(value, name) => {
                if (name === 'Average per Run') {
                  return [Number(value).toFixed(1), name];
                }
                return [value, name];
              }}
            />
            <Legend />
            <Bar 
              yAxisId="left"
              dataKey="Total Food Collected" 
              name="Total Food"
              radius={[8, 8, 0, 0]}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-total-${index}`} fill={AGENT_COLORS[entry.name] || '#6b7280'} />
              ))}
            </Bar>
            <Bar 
              yAxisId="left"
              dataKey="Average per Run" 
              name="Avg per Run"
              radius={[8, 8, 0, 0]}
              opacity={0.6}
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-avg-${index}`} fill={AGENT_COLORS[entry.name] || '#6b7280'} />
              ))}
            </Bar>
            <Bar 
              yAxisId="right"
              dataKey="Simulations" 
              name="Number of Runs"
              fill="#94a3b8"
              radius={[8, 8, 0, 0]}
              opacity={0.3}
            />
          </BarChart>
        </ResponsiveContainer>

        {/* Footer Info */}
        <div className="mt-4 text-xs text-muted-foreground text-center">
          Showing data from the last {simulationCount} of 15 maximum stored simulations
        </div>
      </CardContent>
    </Card>
  );
}

