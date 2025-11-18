import { useState } from "react";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { ArrowLeft, Play, Download, BarChart3 } from "lucide-react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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
                  max_pheromone_value: antCount * 2.0,
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
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/')}
            className="gap-2 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
              <BarChart3 className="h-4 w-4 text-primary" />
            </div>
            <h1 className="text-lg font-semibold">
              Simulation Comparison Lab
            </h1>
          </div>
          <div className="w-20" />
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Configuration Panel */}
          <div className="lg:col-span-4 space-y-6">
            <Card className="border-border shadow-sm">
              <CardHeader>
                <CardTitle className="text-lg">Batch Configuration</CardTitle>
                <CardDescription>
                  Define parameters for multiple parallel runs
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-3">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">Food Sources</Label>
                  <div className="flex flex-wrap gap-2">
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
                        className="h-8"
                      >
                        {count}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">Agent Count</Label>
                  <div className="flex flex-wrap gap-2">
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
                         className="h-8"
                      >
                        {count}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">Intelligence Model</Label>
                  <div className="flex flex-wrap gap-2">
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
                         className="h-8"
                      >
                        {type}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">Iterations per Config</Label>
                  <Select
                    value={config.iterations.toString()}
                    onValueChange={(value) => setConfig(prev => ({ ...prev, iterations: parseInt(value) }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1 Run</SelectItem>
                      <SelectItem value="2">2 Runs</SelectItem>
                      <SelectItem value="3">3 Runs</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="pt-6 border-t border-border">
                  <div className="flex justify-between items-center mb-4 text-sm">
                    <span className="text-muted-foreground">Total Runs:</span>
                    <span className="font-mono font-bold">{totalRuns}</span>
                  </div>
                  <Button
                    className="w-full"
                    onClick={runComparison}
                    disabled={isRunning || config.foodCounts.length === 0 || config.antCounts.length === 0}
                  >
                    {isRunning ? (
                       <>Processing...</>
                    ) : (
                       <>
                         <Play className="h-4 w-4 mr-2" />
                         Start Batch Processing
                       </>
                    )}
                  </Button>
                </div>

                {isRunning && (
                  <div className="space-y-2 bg-muted/30 p-3 rounded border border-border/50">
                    <div className="text-xs font-mono text-muted-foreground truncate">{currentRun}</div>
                    <Progress value={progress} className="h-1.5" />
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Results Panel */}
          <div className="lg:col-span-8 space-y-8">
            {results.length > 0 ? (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <Card className="border-border shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-base">Resource Acquisition</CardTitle>
                      <CardDescription>Food collected across configurations</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={foodCollectionChart}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                          <XAxis dataKey="config" hide />
                          <YAxis tick={{fontSize: 12}} axisLine={false} tickLine={false} />
                          <Tooltip cursor={{fill: 'transparent'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                          <Bar dataKey="collected" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  <Card className="border-border shadow-sm">
                    <CardHeader>
                      <CardTitle className="text-base">System Efficiency</CardTitle>
                      <CardDescription>Steps vs. Blockchain Latency</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={performanceChart}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                          <XAxis dataKey="config" hide />
                          <YAxis yAxisId="left" orientation="left" tick={{fontSize: 12}} axisLine={false} tickLine={false} />
                          <YAxis yAxisId="right" orientation="right" tick={{fontSize: 12}} axisLine={false} tickLine={false} />
                          <Tooltip cursor={{fill: 'transparent'}} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                          <Bar yAxisId="left" dataKey="steps" fill="var(--secondary)" radius={[4, 4, 0, 0]} />
                          <Bar yAxisId="right" dataKey="latency" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                <Card className="border-border shadow-sm overflow-hidden">
                  <CardHeader className="bg-muted/20 border-b border-border flex flex-row items-center justify-between">
                    <div>
                       <CardTitle className="text-base">Comparative Data Table</CardTitle>
                    </div>
                    <Button size="sm" variant="outline" onClick={exportResults} className="h-8">
                      <Download className="h-3.5 w-3.5 mr-2" />
                      CSV
                    </Button>
                  </CardHeader>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border bg-muted/10">
                          <th className="text-left p-3 font-medium text-muted-foreground">Config ID</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Food</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Agents</th>
                          <th className="text-left p-3 font-medium text-muted-foreground">Model</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Collected</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Steps</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Latency</th>
                          <th className="text-right p-3 font-medium text-muted-foreground">Success</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((result, idx) => (
                          <tr key={idx} className="border-b border-border last:border-0 hover:bg-muted/20 transition-colors">
                            <td className="p-3 font-mono text-xs text-muted-foreground">{result.config}</td>
                            <td className="text-right p-3">{result.foodCount}</td>
                            <td className="text-right p-3">{result.antCount}</td>
                            <td className="p-3">
                              <span className={`px-2 py-1 rounded-full text-[10px] font-medium border ${
                                result.agentType === 'LLM-Powered' 
                                  ? 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800' 
                                  : 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700'
                              }`}>
                                {result.agentType}
                              </span>
                            </td>
                            <td className="text-right p-3 font-semibold">{result.foodCollected}</td>
                            <td className="text-right p-3 text-muted-foreground">{result.stepsToComplete}</td>
                            <td className="text-right p-3 font-mono text-xs">{result.avgLatency}ms</td>
                            <td className="text-right p-3">
                               <span className="text-emerald-600 font-medium">{result.successRate}%</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center min-h-[400px] border-2 border-dashed border-border/50 rounded-xl bg-muted/5">
                <div className="text-center space-y-4 max-w-sm px-4">
                  <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                    <BarChart3 className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold">No Data Available</h3>
                  <p className="text-sm text-muted-foreground">
                    Configure your simulation parameters on the left and click "Start Batch Processing" to generate comparative data.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
