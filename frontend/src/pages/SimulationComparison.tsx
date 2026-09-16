import { useState } from "react";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ArrowLeft, Play, Download } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { BUILD_INFO, IS_PREVIEW_MODE, API_BASE_URL } from "@/lib/runtime";

interface ComparisonConfig {
  foodCounts: number[];
  antCounts: number[];
  agentTypes: string[];
  iterations: number;
}

interface ComparisonResult {
  config: string;
  foodCount: number;
  antCount: number;
  agentType: string;
  foodCollected: number;
  stepsToComplete: number;
  avgLatency: number;
  successRate: number;
}

export default function SimulationComparison() {
  const navigate = useNavigate();
  const [config, setConfig] = useState<ComparisonConfig>({
    foodCounts: [10, 15, 20],
    antCounts: [5, 10, 15],
    agentTypes: ['Rule-Based', 'LLM-Powered'],
    iterations: 1
  });
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<ComparisonResult[]>([]);
  const [currentRun, setCurrentRun] = useState("");

  const totalRuns = config.foodCounts.length * config.antCounts.length * config.agentTypes.length * config.iterations;

  const runComparison = async () => {
    if (IS_PREVIEW_MODE) {
      toast.info("Preview mode is frontend-only. Comparison runs stay on the local backend.");
      return;
    }

    setIsRunning(true);
    setResults([]);
    setProgress(0);
    
    const allResults: ComparisonResult[] = [];
    let completed = 0;

    try {
      for (const foodCount of config.foodCounts) {
        for (const antCount of config.antCounts) {
          for (const agentType of config.agentTypes) {
            for (let iter = 0; iter < config.iterations; iter++) {
              setCurrentRun(`Running: ${foodCount} food, ${antCount} ants, ${agentType} (${iter + 1}/${config.iterations})`);
              
              try {
                const response = await axios.post(`${API_BASE_URL}/simulation/run`, {
                  grid_width: 15,
                  grid_height: 10,
                  n_food: foodCount,
                  n_ants: antCount,
                  agent_type: agentType,
                  selected_model: "gpt-4o-mini",
                  prompt_style: "Adaptive",
                  use_queen: false,
                  use_llm_queen: false,
                  max_steps: 100,
                  pheromone_decay_rate: 0.05,
                  trail_deposit: 2.0,
                  alarm_deposit: 2.0,
                  recruitment_deposit: 2.0,
                  max_pheromone_value: Math.min(antCount * 2.0, 20.0),
                  enable_predators: false,
                  n_predators: 0,
                  predator_type: "Rule-Based",
                  fear_deposit: 2.0,
                  blockchain_enabled: true
                });

                const simResult = response.data;
                const blockchainTxs = simResult.blockchain_transactions || [];
                const avgLatency = blockchainTxs.length > 0
                  ? blockchainTxs.reduce((sum: number, tx: any) => sum + tx.latency_ms, 0) / blockchainTxs.length
                  : 0;
                const successRate = blockchainTxs.length > 0
                  ? (blockchainTxs.filter((tx: any) => tx.success).length / blockchainTxs.length) * 100
                  : 100;

                allResults.push({
                  config: `${foodCount}F-${antCount}A-${agentType}`,
                  foodCount,
                  antCount,
                  agentType,
                  foodCollected: simResult.final_metrics.food_collected,
                  stepsToComplete: simResult.total_steps_run,
                  avgLatency: Math.round(avgLatency),
                  successRate: Math.round(successRate)
                });

                completed++;
                setProgress((completed / totalRuns) * 100);
                setResults([...allResults]);

              } catch (error: any) {
                console.error("Simulation failed:", error);
                toast.error(`Failed: ${foodCount}F, ${antCount}A, ${agentType}`);
              }
            }
          }
        }
      }

      toast.success(`Completed ${completed} simulations!`);
    } catch (error) {
      console.error("Comparison failed:", error);
      toast.error("Comparison failed");
    } finally {
      setIsRunning(false);
      setCurrentRun("");
    }
  };

  const exportResults = () => {
    const csv = [
      ['Config', 'Food Count', 'Ant Count', 'Agent Type', 'Food Collected', 'Steps to Complete', 'Avg Latency (ms)', 'Success Rate (%)'],
      ...results.map(r => [r.config, r.foodCount, r.antCount, r.agentType, r.foodCollected, r.stepsToComplete, r.avgLatency, r.successRate])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulation-comparison-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Group results for charts
  const foodCollectionChart = results.reduce((acc, r) => {
    const existing = acc.find(item => item.config === r.config);
    if (existing) {
      existing.collected = r.foodCollected;
    } else {
      acc.push({ config: r.config, collected: r.foodCollected });
    }
    return acc;
  }, [] as Array<{ config: string; collected: number }>);

  const performanceChart = results.map(r => ({
    config: r.config,
    steps: r.stepsToComplete,
    latency: r.avgLatency
  }));

  return (
    <div className="min-h-screen bg-gradient-to-br from-amber-50 to-orange-100 dark:from-gray-900 dark:to-gray-800">
      {/* Header */}
      <div className="border-b bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            className="gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Simulation
          </Button>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-amber-900 dark:text-amber-100">
              🔬 Simulation Comparison Lab
            </h1>
            {IS_PREVIEW_MODE && (
              <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                Preview build: {BUILD_INFO.buildLabel}. Batch comparisons are disabled on the public frontend.
              </p>
            )}
          </div>
          <div className="w-32" />
        </div>
      </div>

      <div className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Configuration Panel */}
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
              <CardDescription>
                Set up batch comparison parameters
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Food Counts</Label>
                <div className="flex gap-2 mt-2">
                  {[5, 10, 15, 20, 25].map(count => (
                    <Button
                      key={count}
                      size="sm"
                      variant={config.foodCounts.includes(count) ? "default" : "outline"}
                      onClick={() => {
                        setConfig(prev => ({
                          ...prev,
                          foodCounts: prev.foodCounts.includes(count)
                            ? prev.foodCounts.filter(c => c !== count)
                            : [...prev.foodCounts, count]
                        }));
                      }}
                    >
                      {count}
                    </Button>
                  ))}
                </div>
              </div>

              <div>
                <Label>Ant Counts</Label>
                <div className="flex gap-2 mt-2">
                  {[5, 10, 15, 20].map(count => (
                    <Button
                      key={count}
                      size="sm"
                      variant={config.antCounts.includes(count) ? "default" : "outline"}
                      onClick={() => {
                        setConfig(prev => ({
                          ...prev,
                          antCounts: prev.antCounts.includes(count)
                            ? prev.antCounts.filter(c => c !== count)
                            : [...prev.antCounts, count]
                        }));
                      }}
                    >
                      {count}
                    </Button>
                  ))}
                </div>
              </div>

              <div>
                <Label>Agent Types</Label>
                <div className="flex gap-2 mt-2">
                  {['Rule-Based', 'LLM-Powered'].map(type => (
                    <Button
                      key={type}
                      size="sm"
                      variant={config.agentTypes.includes(type) ? "default" : "outline"}
                      onClick={() => {
                        setConfig(prev => ({
                          ...prev,
                          agentTypes: prev.agentTypes.includes(type)
                            ? prev.agentTypes.filter(t => t !== type)
                            : [...prev.agentTypes, type]
                        }));
                      }}
                    >
                      {type}
                    </Button>
                  ))}
                </div>
              </div>

              <div>
                <Label>Iterations per config</Label>
                <Select
                  value={config.iterations.toString()}
                  onValueChange={(value) => setConfig(prev => ({ ...prev, iterations: parseInt(value) }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">1 iteration</SelectItem>
                    <SelectItem value="2">2 iterations</SelectItem>
                    <SelectItem value="3">3 iterations</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="pt-4 border-t">
                <div className="text-sm text-muted-foreground mb-2">
                  Total simulations: {totalRuns}
                </div>
                <Button
                  className="w-full"
                  onClick={runComparison}
                  disabled={isRunning || config.foodCounts.length === 0 || config.antCounts.length === 0}
                >
                  <Play className="h-4 w-4 mr-2" />
                  {isRunning ? 'Running...' : 'Start Comparison'}
                </Button>
              </div>

              {isRunning && (
                <div>
                  <div className="text-xs text-muted-foreground mb-2">{currentRun}</div>
                  <Progress value={progress} />
                </div>
              )}
            </CardContent>
          </Card>

          {/* Results Panel */}
          <div className="lg:col-span-2 space-y-6">
            {results.length > 0 && (
              <>
                <Card>
                  <CardHeader>
                    <div className="flex justify-between items-center">
                      <div>
                        <CardTitle>Food Collection Performance</CardTitle>
                        <CardDescription>Food collected by configuration</CardDescription>
                      </div>
                      <Button size="sm" variant="outline" onClick={exportResults}>
                        <Download className="h-4 w-4 mr-2" />
                        Export CSV
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={foodCollectionChart}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="config" angle={-45} textAnchor="end" height={100} tick={{ fontSize: 10 }} />
                        <YAxis label={{ value: 'Food Collected', angle: -90, position: 'insideLeft' }} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="collected" fill="#f59e0b" name="Food Collected">
                          {foodCollectionChart.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill="#f59e0b" />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Efficiency Metrics</CardTitle>
                    <CardDescription>Steps to complete vs blockchain latency</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={performanceChart}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="config" angle={-45} textAnchor="end" height={100} tick={{ fontSize: 10 }} />
                        <YAxis yAxisId="left" label={{ value: 'Steps', angle: -90, position: 'insideLeft' }} />
                        <YAxis yAxisId="right" orientation="right" label={{ value: 'Latency (ms)', angle: 90, position: 'insideRight' }} />
                        <Tooltip />
                        <Legend />
                        <Bar yAxisId="left" dataKey="steps" fill="#3b82f6" name="Steps to Complete">
                          {performanceChart.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill="#3b82f6" />
                          ))}
                        </Bar>
                        <Bar yAxisId="right" dataKey="latency" fill="#8b5cf6" name="Avg Blockchain Latency">
                          {performanceChart.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill="#8b5cf6" />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Detailed Results</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left p-2">Config</th>
                            <th className="text-right p-2">Food</th>
                            <th className="text-right p-2">Ants</th>
                            <th className="text-left p-2">Type</th>
                            <th className="text-right p-2">Collected</th>
                            <th className="text-right p-2">Steps</th>
                            <th className="text-right p-2">Latency</th>
                            <th className="text-right p-2">Success</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.map((result, idx) => (
                            <tr key={idx} className="border-b hover:bg-muted/50">
                              <td className="p-2 font-mono text-xs">{result.config}</td>
                              <td className="text-right p-2">{result.foodCount}</td>
                              <td className="text-right p-2">{result.antCount}</td>
                              <td className="p-2">
                                <span className={`px-2 py-1 rounded text-xs ${
                                  result.agentType === 'LLM-Powered' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                                }`}>
                                  {result.agentType}
                                </span>
                              </td>
                              <td className="text-right p-2 font-semibold">{result.foodCollected}</td>
                              <td className="text-right p-2">{result.stepsToComplete}</td>
                              <td className="text-right p-2">{result.avgLatency}ms</td>
                              <td className="text-right p-2 text-green-600">{result.successRate}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}

            {results.length === 0 && !isRunning && (
              <Card>
                <CardContent className="py-12 text-center">
                  <div className="text-muted-foreground">
                    <div className="text-4xl mb-4">📊</div>
                    <div>Configure your comparison and click "Start Comparison" to begin</div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

