/* eslint-disable-next-line @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- legacy ant-sim UI with known type errors (async results rendered
// as values, wrong history field names). Removed in step 14 of
// docs/plans/2026-09-27-frontend-refactor-v1.md; do not add new @ts-nocheck files.
import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, BarChart, Bar, ResponsiveContainer, ScatterChart, Scatter, Cell } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface FoodDepletionPoint {
  step: number;
  food_piles_remaining: number;
}

interface PerformanceData {
  food_collected_by_llm: number;
  food_collected_by_rule: number;
  total_api_calls: number;
  efficiency_by_agent_type: Record<string, number>;
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

interface EfficiencyData {
  efficiency_grid: number[][];
  max_efficiency: number;
  hotspot_locations: [number, number][];
}

interface PerformanceChartsProps {
  foodDepletionHistory: FoodDepletionPoint[];
  performanceData?: PerformanceData;
  currentMetrics?: {
    food_collected_by_llm: number;
    food_collected_by_rule: number;
    total_api_calls: number;
  };
  pheromoneData?: PheromoneData | null;
  efficiencyData?: EfficiencyData | null;
}

export const PerformanceCharts: React.FC<PerformanceChartsProps> = ({
  foodDepletionHistory,
  performanceData,
  currentMetrics,
  pheromoneData,
  efficiencyData
}) => {
  // Prepare data for the agent type efficiency chart
  const agentEfficiencyData = React.useMemo(() => {
    const data = [];
    
    if (currentMetrics) {
      data.push(
        { 
          agentType: 'LLM-Powered', 
          foodCollected: currentMetrics.food_collected_by_llm,
          color: '#8884d8'
        },
        { 
          agentType: 'Rule-Based', 
          foodCollected: currentMetrics.food_collected_by_rule,
          color: '#82ca9d'
        }
      );
    } else if (performanceData) {
      data.push(
        { 
          agentType: 'LLM-Powered', 
          foodCollected: performanceData.food_collected_by_llm,
          color: '#8884d8'
        },
        { 
          agentType: 'Rule-Based', 
          foodCollected: performanceData.food_collected_by_rule,
          color: '#82ca9d'
        }
      );
    }
    
    return data;
  }, [currentMetrics, performanceData]);

  // Check if we should show the agent type chart (only if both types have collected food)
  const shouldShowAgentTypeChart = React.useMemo(() => {
    const llmFood = currentMetrics?.food_collected_by_llm ?? performanceData?.food_collected_by_llm ?? 0;
    const ruleFood = currentMetrics?.food_collected_by_rule ?? performanceData?.food_collected_by_rule ?? 0;
    
    // Show chart only if both agent types have collected food
    return llmFood > 0 && ruleFood > 0;
  }, [currentMetrics, performanceData]);

  // Prepare pheromone summary data for chart
  const pheromoneChartData = React.useMemo(() => {
    if (!pheromoneData) return [];
    
    const { max_values } = pheromoneData;
    return [
      { name: 'Trail', value: max_values.trail, color: '#22c55e' }, // Green
      { name: 'Alarm', value: max_values.alarm, color: '#ef4444' }, // Red
      { name: 'Recruitment', value: max_values.recruitment, color: '#3b82f6' }, // Blue
      ...(max_values.fear !== undefined ? [{ name: 'Fear', value: max_values.fear, color: '#f97316' }] : []) // Orange
    ];
  }, [pheromoneData]);

  // Prepare hotspot data for scatter plot
  const hotspotData = React.useMemo(() => {
    if (!efficiencyData?.hotspot_locations) return [];
    
    return efficiencyData.hotspot_locations.map(([x, y], index) => ({
      x,
      y,
      intensity: index < 5 ? 100 : 50 // Highlight top 5 hotspots
    }));
  }, [efficiencyData]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Food Depletion Over Time */}
        <Card>
          <CardHeader>
            <CardTitle>Food Piles Remaining Over Time</CardTitle>
            <CardDescription>
              Track how food resources are depleted throughout the simulation
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={foodDepletionHistory}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="step" 
                  label={{ value: 'Simulation Step', position: 'insideBottom', offset: -5 }}
                />
                <YAxis 
                  label={{ value: 'Food Piles Remaining', angle: -90, position: 'insideLeft' }}
                />
                <Tooltip 
                  labelFormatter={(label) => `Step: ${label}`}
                  formatter={(value) => [value, 'Food Piles']}
                />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="food_piles_remaining" 
                  stroke="#8884d8" 
                  strokeWidth={2}
                  dot={{ fill: '#8884d8', strokeWidth: 2, r: 4 }}
                  name="Food Piles Remaining"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Food Collection by Agent Type - Only show if both types have collected food */}
        {shouldShowAgentTypeChart && (
          <Card>
            <CardHeader>
              <CardTitle>Food Collected by Agent Type</CardTitle>
              <CardDescription>
                Compare efficiency between LLM-powered and rule-based agents
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={agentEfficiencyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    dataKey="agentType"
                    label={{ value: 'Agent Type', position: 'insideBottom', offset: -5 }}
                  />
                  <YAxis 
                    label={{ value: 'Food Collected', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip 
                    formatter={(value) => [value, 'Food Collected']}
                  />
                  <Legend />
                  <Bar 
                    dataKey="foodCollected" 
                    fill="#8884d8"
                    name="Food Collected"
                  />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Pheromone and Efficiency Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pheromone Intensity Levels */}
        {pheromoneChartData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>🧪 Pheromone Intensity Levels</CardTitle>
              <CardDescription>
                Maximum pheromone concentrations by type
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={pheromoneChartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis 
                    label={{ value: 'Intensity', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip 
                    formatter={(value) => [value?.toFixed(2), 'Intensity']}
                  />
                  <Legend />
                  <Bar 
                    dataKey="value" 
                    name="Pheromone Intensity"
                  >
                    {pheromoneChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Foraging Hotspots */}
        {efficiencyData && (
          <Card>
            <CardHeader>
              <CardTitle>🔥 Foraging Hotspots</CardTitle>
              <CardDescription>
                Areas of highest LLM ant activity and food collection
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <ScatterChart>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis 
                    type="number" 
                    dataKey="x" 
                    domain={[0, 20]} 
                    label={{ value: 'X Position', position: 'bottom' }}
                  />
                  <YAxis 
                    type="number" 
                    dataKey="y" 
                    domain={[0, 20]} 
                    label={{ value: 'Y Position', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip 
                    formatter={(value, name, props) => [
                      `(${props.payload.x}, ${props.payload.y})`, 
                      'Hotspot'
                    ]}
                  />
                  <Scatter 
                    data={efficiencyData.hotspot_locations.map(([x, y], index) => ({ x, y, index }))}
                    fill="#ff6b35"
                    name="Hotspots"
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </div>

      {/* API Usage Metrics */}
      <Card>
        <CardHeader>
          <CardTitle>📊 System Performance Metrics</CardTitle>
          <CardDescription>
            Monitor LLM API calls, pheromone activity, and system performance
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-lg">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {(currentMetrics?.total_api_calls ?? performanceData?.total_api_calls ?? 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Total API Calls</div>
            </div>
            
            <div className="bg-green-50 dark:bg-green-950 p-4 rounded-lg">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {(currentMetrics?.food_collected_by_llm ?? performanceData?.food_collected_by_llm ?? 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">LLM Agent Food</div>
            </div>
            
            <div className="bg-orange-50 dark:bg-orange-950 p-4 rounded-lg">
              <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                {(currentMetrics?.food_collected_by_rule ?? performanceData?.food_collected_by_rule ?? 0)}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Rule Agent Food</div>
            </div>
            
            <div className="bg-purple-50 dark:bg-purple-950 p-4 rounded-lg">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {(
                  (currentMetrics?.food_collected_by_llm ?? performanceData?.food_collected_by_llm ?? 0) + 
                  (currentMetrics?.food_collected_by_rule ?? performanceData?.food_collected_by_rule ?? 0)
                )}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">Total Food</div>
            </div>

            {/* Pheromone Activity */}
            {pheromoneData && (
              <>
                <div className="bg-cyan-50 dark:bg-cyan-950 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">
                    {pheromoneData.max_values.trail.toFixed(1)}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Max Trail</div>
                </div>
                
                <div className="bg-red-50 dark:bg-red-950 p-4 rounded-lg">
                  <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                    {pheromoneData.max_values.alarm.toFixed(1)}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Max Alarm</div>
                </div>
                
                {pheromoneData.max_values.fear !== undefined && (
                  <div className="bg-orange-50 dark:bg-orange-950 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-orange-600 dark:text-orange-400">
                      {pheromoneData.max_values.fear.toFixed(1)}
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">Max Fear</div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Efficiency Summary */}
          {efficiencyData && (
            <div className="mt-4 p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
              <h4 className="font-semibold mb-2">🔥 Foraging Efficiency Summary</h4>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                <p>• Maximum efficiency score: {efficiencyData.max_efficiency.toFixed(2)}</p>
                <p>• Active hotspots identified: {efficiencyData.hotspot_locations.length}</p>
                <p>• Most efficient areas show successful LLM ant food collection patterns</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}; 