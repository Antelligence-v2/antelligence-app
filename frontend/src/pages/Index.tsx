import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { SimulationSidebar } from "@/components/SimulationSidebar";
import { SimulationControls } from "@/components/SimulationControls";
import { SimulationGrid } from "@/components/SimulationGrid";
import { QueenAntReport } from "@/components/QueenAntReport";
import { PerformanceCharts } from "@/components/PerformanceCharts";
import { ComparisonPanel } from "@/components/ComparisonPanel";
import { HistoricalPerformance } from "@/components/HistoricalPerformance";
import { BlockchainMetrics } from "@/components/BlockchainMetrics";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { SimulationLoading } from "@/components/SimulationLoading";
import { IntroPage } from "@/components/IntroPage";
import { saveSimulationResult } from "@/lib/simulationHistory";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart3, Map, Activity, Zap, Database, Info, Link2 } from "lucide-react";

// The URL of your running FastAPI backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

interface SimulationConfig {
  grid_width: number;
  grid_height: number;
  n_food: number;
  n_ants: number;
  agent_type: string;
  selected_model: string;
  prompt_style: string;
  use_queen: boolean;
  use_llm_queen: boolean;
  max_steps: number;
  
  pheromone_decay_rate: number;
  trail_deposit: number;
  alarm_deposit: number;
  recruitment_deposit: number;
  max_pheromone_value: number;

  enable_predators: boolean;
  n_predators: number;
  predator_type: string;
  fear_deposit: number;

  blockchain_enabled: boolean;
}

const Index = () => {
  const navigate = useNavigate();
  const [showIntro, setShowIntro] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const [config, setConfig] = useState<SimulationConfig>({
    grid_width: 15,
    grid_height: 10,
    n_food: 15,
    n_ants: 10,
    agent_type: "LLM-Powered",
    selected_model: "meta-llama/Llama-3.3-70B-Instruct",
    prompt_style: "Adaptive",
    use_queen: true,
    use_llm_queen: false,
    max_steps: 50,
    
    pheromone_decay_rate: 0.05,
    trail_deposit: 1.0,
    alarm_deposit: 2.0,
    recruitment_deposit: 1.5,
    max_pheromone_value: 10.0,

    enable_predators: false,
    n_predators: 2,
    predator_type: "LLM-Powered",
    fear_deposit: 3.0,

    blockchain_enabled: true,
  });

  const [simulationResults, setSimulationResults] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [loadingStep, setLoadingStep] = useState(0);
  const [loadingTotalSteps, setLoadingTotalSteps] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(300);
  const [isLooping, setIsLooping] = useState(false);

  const [showPheromones, setShowPheromones] = useState(true);
  const [showEfficiency, setShowEfficiency] = useState(true);
  const [activeTab, setActiveTab] = useState("visualization");

  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    setLoadingProgress(0);
    setLoadingStep(0);
    setLoadingTotalSteps(config.max_steps);
    setIsPlaying(false);
    setSimulationResults(null);
    toast.info("Initializing simulation environment...");

    try {
      const progressInterval = setInterval(() => {
        setLoadingProgress(prev => {
          if (prev >= 85) {
            clearInterval(progressInterval);
            return prev;
          }
          const newProgress = prev + 1.5;
          const stepProgress = Math.floor((newProgress / 100) * config.max_steps);
          setLoadingStep(stepProgress);
          return newProgress;
        });
      }, 150);

      const simulationConfig = {
        ...config,
        n_predators: config.enable_predators ? config.n_predators : 0,
      };
      
      const response = await axios.post(`${API_BASE_URL}/simulation/run`, simulationConfig);
      
      clearInterval(progressInterval);
      setLoadingProgress(100);
      setLoadingStep(config.max_steps);

      setSimulationResults(response.data);
      setCurrentStep(0);
      
      saveSimulationResult({
        agent_type: config.agent_type,
        llm_model: config.selected_model,
        simulation_type: "ant" as const,
        config: {
          grid_width: config.grid_width,
          grid_height: config.grid_height,
          n_ants: config.n_ants,
          n_food: config.n_food,
        },
        final_metrics: response.data.final_metrics || {},
        summary: {
          food_collected: response.data.final_metrics?.food_collected || 0,
          steps: response.data.total_steps_run || config.max_steps,
        },
      });
      
      setTimeout(() => {
        setIsLoading(false);
        setLoadingProgress(0);
        setLoadingStep(0);
        setLoadingTotalSteps(0);
        toast.success("Simulation data ready.");
      }, 800);
      
    } catch (error: any) {
      console.error("Simulation API error:", error);
      setIsLoading(false);
      setLoadingProgress(0);
      setLoadingStep(0);
      setLoadingTotalSteps(0);
      toast.error(`Simulation failed: ${error.response?.data?.detail || error.message}`);
    }
  }, [config]);

  const handleReset = () => {
    setIsPlaying(false);
    setSimulationResults(null);
    setCurrentStep(0);
    setLoadingStep(0);
    setLoadingTotalSteps(0);
  };

  const handleStepForward = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(prev => Math.min(prev + 1, simulationResults.history.length - 1));
  }, [simulationResults]);

  const handleStepBackward = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(prev => Math.max(prev - 1, 0));
  }, [simulationResults]);

  const handleReplay = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(0);
    setIsPlaying(true);
  }, [simulationResults]);

  const handleGoToStart = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(0);
    setIsPlaying(false);
  }, [simulationResults]);

  const handleGoToEnd = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(simulationResults.history.length - 1);
    setIsPlaying(false);
  }, [simulationResults]);

  const speedOptions = [
    { label: "0.5x", value: 600 },
    { label: "1x", value: 300 },
    { label: "2x", value: 150 },
    { label: "4x", value: 75 },
  ];

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (!simulationResults || event.target instanceof HTMLInputElement) return;

      switch (event.key) {
        case ' ':
          event.preventDefault();
          setIsPlaying(prev => !prev);
          break;
        case 'ArrowRight':
          event.preventDefault();
          handleStepForward();
          break;
        case 'ArrowLeft':
          event.preventDefault();
          handleStepBackward();
          break;
        case 'Home':
          event.preventDefault();
          handleGoToStart();
          break;
        case 'End':
          event.preventDefault();
          handleGoToEnd();
          break;
        case 'r':
          event.preventDefault();
          handleReplay();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [simulationResults, handleStepForward, handleStepBackward, handleGoToStart, handleGoToEnd, handleReplay]);

  useEffect(() => {
    if (!isPlaying || !simulationResults) return;

    const interval = setInterval(() => {
      setCurrentStep(prevStep => {
        if (prevStep >= simulationResults.history.length - 1) {
          if (isLooping) {
            return 0;
          } else {
            setIsPlaying(false);
            return prevStep;
          }
        }
        return prevStep + 1;
      });
    }, playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, simulationResults, playbackSpeed, isLooping]);

  const currentStepData = simulationResults?.history?.[currentStep];
  
  const metrics = {
    currentStep: currentStepData?.step ?? 0,
    totalSteps: simulationResults?.total_steps_run ?? 0,
    foodCollected: currentStepData?.metrics?.food_collected ?? 0,
    activeAnts: currentStepData?.ants?.length ?? 0,
    apiCalls: currentStepData?.metrics?.total_api_calls ?? 0,
    queenActive: config.use_queen,
    blockchainActive: config.blockchain_enabled && (simulationResults?.blockchain_logs?.length ?? 0) > 0,
  };

  const currentMetrics = currentStepData?.metrics ? {
    food_collected_by_llm: currentStepData.metrics.food_collected_by_llm ?? 0,
    food_collected_by_rule: currentStepData.metrics.food_collected_by_rule ?? 0,
    total_api_calls: currentStepData.metrics.total_api_calls ?? 0,
  } : undefined;

  const getLatestDetailedData = () => {
    if (!simulationResults?.history) return { pheromone: null, efficiency: null };
    
    for (let i = currentStep; i >= 0; i--) {
      const stepData = simulationResults.history[i];
      if (stepData.pheromone_data || stepData.efficiency_data) {
        return {
          pheromone: stepData.pheromone_data,
          efficiency: stepData.efficiency_data
        };
      }
    }
    
    return {
      pheromone: simulationResults.final_pheromone_data,
      efficiency: simulationResults.final_efficiency_data
    };
  };

  const handleEnterSimulation = () => {
    setShowIntro(false);
  };

  const handleBackToIntro = () => {
    setShowIntro(true);
  };

  if (showIntro) {
    return <IntroPage onEnter={handleEnterSimulation} />;
  }

  const latestDetailedData = getLatestDetailedData();

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
      <SimulationLoading 
        isVisible={isLoading}
        progress={loadingProgress}
        currentStep={loadingStep}
        totalSteps={loadingTotalSteps}
      />
      
      <SimulationSidebar
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        settings={config}
        onSettingsChange={setConfig}
        onRunSimulation={runSimulation}
        isLoading={isLoading}
      />

      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="flex-none z-10 bg-background/80 backdrop-blur-sm border-b border-border">
             <SimulationControls
              isRunning={isPlaying}
              onStart={() => simulationResults && setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onStep={handleStepForward}
              onStepBackward={handleStepBackward}
              onReset={handleReset}
              onReplay={handleReplay}
              onGoToStart={handleGoToStart}
              onGoToEnd={handleGoToEnd}
              metrics={metrics}
              isSimulationLoaded={!!simulationResults}
              playbackSpeed={playbackSpeed}
              onSpeedChange={setPlaybackSpeed}
              speedOptions={speedOptions}
              isLooping={isLooping}
              onLoopChange={setIsLooping}
              currentStep={currentStep}
              totalSteps={simulationResults?.history?.length ?? 0}
              onBackToIntro={handleBackToIntro}
            />
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth">
          <div className="max-w-7xl mx-auto space-y-8">
            
            {/* Main Visualization Card */}
            <Card className="border-0 shadow-sm ring-1 ring-gray-200 dark:ring-gray-800 bg-card">
              <CardHeader className="border-b border-border/50 pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2 text-lg font-semibold tracking-tight">
                      <Map className="w-5 h-5 text-primary" />
                      Live Environment
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {simulationResults 
                        ? `Step ${currentStep + 1} / ${simulationResults.history.length} • ${metrics.activeAnts} Agents Active`
                        : "Waiting for simulation execution..."
                      }
                    </CardDescription>
                  </div>
                  
                  {simulationResults && activeTab === "visualization" && (
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        variant={showEfficiency ? "secondary" : "ghost"}
                        onClick={() => setShowEfficiency(!showEfficiency)}
                        className="h-8 text-xs"
                      >
                        Heatmap
                      </Button>
                      <Button 
                        size="sm" 
                        variant={showPheromones ? "secondary" : "ghost"}
                        onClick={() => setShowPheromones(!showPheromones)}
                         className="h-8 text-xs"
                      >
                        Pheromones
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              
              <CardContent className="p-6">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                  <TabsList className="grid w-full grid-cols-2 mb-6">
                    <TabsTrigger value="visualization" className="gap-2">
                      <Map className="w-4 h-4" />
                      Visualization
                    </TabsTrigger>
                    <TabsTrigger value="analysis" className="gap-2">
                      <BarChart3 className="w-4 h-4" />
                      Analysis
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="visualization" className="mt-0">
                    <div className="flex flex-col lg:flex-row gap-8">
                      {/* Grid */}
                      <div className="flex-1 flex items-center justify-center min-h-[400px] bg-muted/30 rounded-xl border border-border/50 p-4">
                        {simulationResults ? (
                          <SimulationGrid
                            gridWidth={config.grid_width}
                            gridHeight={config.grid_height}
                            ants={currentStepData?.ants ?? []}
                            food={currentStepData?.food_positions ?? []}
                            nestPosition={currentStepData?.nest_position ?? [Math.floor(config.grid_width/2), Math.floor(config.grid_height/2)]}
                            predators={currentStepData?.predators ?? []}
                            efficiencyData={showEfficiency ? latestDetailedData.efficiency : null}
                            pheromoneData={showPheromones ? latestDetailedData.pheromone : null}
                          />
                        ) : (
                          <div className="text-center max-w-md mx-auto">
                            <div className="w-16 h-16 bg-muted rounded-2xl flex items-center justify-center mx-auto mb-4">
                               <Zap className="w-8 h-8 text-muted-foreground" />
                            </div>
                            <h3 className="text-lg font-medium text-foreground">Ready to Initialize</h3>
                            <p className="text-sm text-muted-foreground mt-2 mb-6">
                              Configure your agents and environment settings in the sidebar, then launch the simulation.
                            </p>
                            <Button onClick={runSimulation} disabled={isLoading} className="w-full sm:w-auto">
                              {isLoading ? "Processing..." : "Run Simulation"}
                            </Button>
                          </div>
                        )}
                      </div>

                      {/* Legend & Stats */}
                      <div className="w-full lg:w-64 space-y-6">
                        <div className="p-4 rounded-lg bg-muted/40 border border-border/50">
                          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Legend</h4>
                          <div className="space-y-3 text-sm">
                            <div className="flex items-center gap-3">
                               <span className="w-3 h-3 rounded-full bg-blue-500 ring-2 ring-blue-500/20"></span>
                               <span className="text-muted-foreground">Forager Ant</span>
                            </div>
                            <div className="flex items-center gap-3">
                               <span className="w-3 h-3 rounded-full bg-green-500 ring-2 ring-green-500/20"></span>
                               <span className="text-muted-foreground">Food Source</span>
                            </div>
                            <div className="flex items-center gap-3">
                               <span className="w-3 h-3 rounded-full bg-purple-500 ring-2 ring-purple-500/20"></span>
                               <span className="text-muted-foreground">Queen</span>
                            </div>
                            {config.enable_predators && (
                               <div className="flex items-center gap-3">
                                 <span className="w-3 h-3 rounded-full bg-red-500 ring-2 ring-red-500/20"></span>
                                 <span className="text-muted-foreground">Predator</span>
                               </div>
                            )}
                            <div className="h-px bg-border my-2"></div>
                             <div className="flex items-center gap-3">
                               <span className="w-3 h-3 rounded bg-emerald-500/50"></span>
                               <span className="text-muted-foreground">Trail Pheromone</span>
                            </div>
                          </div>
                        </div>

                        {simulationResults && (
                          <div className="p-4 rounded-lg bg-card border border-border/50 shadow-sm">
                            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">Current Status</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Food Collected</span>
                                <span className="font-mono font-medium">{metrics.foodCollected}</span>
                              </div>
                               <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Steps Remaining</span>
                                <span className="font-mono font-medium">{config.max_steps - metrics.currentStep}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </TabsContent>

                  <TabsContent value="analysis" className="mt-0">
                    {simulationResults ? (
                      <div className="grid grid-cols-1 gap-8 animate-fade-in">
                        {config.use_queen && (
                          <QueenAntReport
                            isVisible={config.use_queen}
                            report={currentStepData?.queen_report}
                          />
                        )}
                        
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                           <Card className="border-0 shadow-sm ring-1 ring-gray-200 dark:ring-gray-800">
                              <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-lg">
                                   <Activity className="w-5 h-5 text-primary" />
                                   Performance Metrics
                                </CardTitle>
                              </CardHeader>
                              <CardContent>
                                <PerformanceCharts
                                  foodDepletionHistory={simulationResults.food_depletion_history ?? []}
                                  currentMetrics={currentMetrics}
                                  pheromoneData={latestDetailedData.pheromone}
                                  efficiencyData={latestDetailedData.efficiency}
                                />
                              </CardContent>
                           </Card>
                           
                           <div className="space-y-8">
                              <div className="bg-card rounded-xl shadow-sm ring-1 ring-gray-200 dark:ring-gray-800 p-6">
                                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                                  <Database className="w-5 h-5 text-primary" />
                                  Historical Data
                                </h3>
                                <HistoricalPerformance />
                              </div>
                              
                              {simulationResults.blockchain_transactions && (
                                 <div className="bg-card rounded-xl shadow-sm ring-1 ring-gray-200 dark:ring-gray-800 p-6">
                                   <div className="flex justify-between items-center mb-4">
                                      <h3 className="text-lg font-semibold flex items-center gap-2">
                                        <Link2 className="w-5 h-5 text-primary" />
                                        Ledger
                                      </h3>
                                      <Button variant="outline" size="sm" onClick={() => navigate('/comparison')}>
                                        Compare Runs
                                      </Button>
                                   </div>
                                   <BlockchainMetrics transactions={simulationResults.blockchain_transactions} />
                                 </div>
                              )}
                           </div>
                        </div>
                        
                        <div className="border-t border-border pt-8">
                           <h3 className="text-xl font-semibold mb-6">Comparative Analysis</h3>
                           <ComparisonPanel config={config} apiBaseUrl={API_BASE_URL} />
                        </div>
                        
                        {/* Tech Specs Footer */}
                        <div className="bg-muted/30 rounded-xl p-6 border border-border/50 text-sm text-muted-foreground">
                           <div className="flex items-center gap-2 font-semibold text-foreground mb-4">
                              <Info className="w-4 h-4" />
                              Technical Specifications
                           </div>
                           <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                              <div>
                                 <div className="text-xs uppercase tracking-wider mb-1 opacity-70">Configuration</div>
                                 <div>{config.grid_width}x{config.grid_height} Grid</div>
                                 <div>{config.n_ants} Agents</div>
                              </div>
                              <div>
                                 <div className="text-xs uppercase tracking-wider mb-1 opacity-70">Model</div>
                                 <div className="truncate" title={config.selected_model}>{config.selected_model}</div>
                                 <div>{config.prompt_style} Prompting</div>
                              </div>
                              <div>
                                 <div className="text-xs uppercase tracking-wider mb-1 opacity-70">System</div>
                                 <div>{config.use_queen ? "Hierarchical Control" : "Decentralized"}</div>
                                 <div>{config.blockchain_enabled ? "On-Chain Logging" : "Off-Chain"}</div>
                              </div>
                               <div>
                                 <div className="text-xs uppercase tracking-wider mb-1 opacity-70">Runtime</div>
                                 <div>{metrics.apiCalls} API Calls</div>
                                 <div>{(metrics.currentStep / metrics.totalSteps * 100).toFixed(0)}% Complete</div>
                              </div>
                           </div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-20 text-muted-foreground">
                        <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-20" />
                        <p>Run a simulation to view analysis data.</p>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
