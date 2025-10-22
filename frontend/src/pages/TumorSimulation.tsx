import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { SimulationLoading } from "@/components/SimulationLoading";
import { TumorSimulationGrid } from "@/components/TumorSimulationGrid";
import { TumorSimulationControls } from "@/components/TumorSimulationControls";
import { TumorSimulationSidebar } from "@/components/TumorSimulationSidebar";
import { TumorPerformanceCharts } from "@/components/TumorPerformanceCharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, Activity, Zap, Home } from "lucide-react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

interface TumorSimulationConfig {
  domain_size: number;
  voxel_size: number;
  n_nanobots: number;
  tumor_radius: number;
  agent_type: string;
  selected_model: string;
  use_queen: boolean;
  use_llm_queen: boolean;
  max_steps: number;
  cell_density: number;
  vessel_density: number;
}

const TumorSimulation = () => {
  const navigate = useNavigate();
  const [config, setConfig] = useState<TumorSimulationConfig>({
    domain_size: 600.0,
    voxel_size: 20.0,
    n_nanobots: 10,
    tumor_radius: 200.0,
    agent_type: "Rule-Based",
    selected_model: "meta-llama/Llama-3.3-70B-Instruct",
    use_queen: false,
    use_llm_queen: false,
    max_steps: 100,
    cell_density: 0.001,
    vessel_density: 0.01,
  });

  const [simulationResults, setSimulationResults] = useState<any>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(500);
  const [selectedSubstrate, setSelectedSubstrate] = useState<string>("oxygen");
  const [detailedMode, setDetailedMode] = useState(false); // Simple vs Detailed mode toggle

  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    setLoadingProgress(0);
    setIsPlaying(false);
    setSimulationResults(null);
    toast.info("Starting tumor nanobot simulation...");

    try {
      const progressInterval = setInterval(() => {
        setLoadingProgress(prev => Math.min(prev + 1, 90));
      }, 200);

      const response = await axios.post(`${API_BASE_URL}/simulation/tumor/run`, config);
      
      clearInterval(progressInterval);
      setLoadingProgress(100);

      setSimulationResults(response.data);
      setCurrentStep(0);
      
      setTimeout(() => {
        setIsLoading(false);
        setLoadingProgress(0);
        toast.success("Simulation complete! Results loaded for playback.");
      }, 800);
      
    } catch (error: any) {
      console.error("Tumor simulation API error:", error);
      setIsLoading(false);
      setLoadingProgress(0);
      toast.error(`Failed to run simulation: ${error.response?.data?.detail || error.message}`);
    }
  }, [config]);

  const handleReset = () => {
    setIsPlaying(false);
    setSimulationResults(null);
    setCurrentStep(0);
    toast("Simulation has been reset.");
  };

  const handleStepForward = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(prev => Math.min(prev + 1, simulationResults.history.length - 1));
  }, [simulationResults]);

  const handleStepBackward = useCallback(() => {
    if (!simulationResults) return;
    setCurrentStep(prev => Math.max(prev - 1, 0));
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

  // Playback effect
  useEffect(() => {
    if (!isPlaying || !simulationResults) return;

    const interval = setInterval(() => {
      setCurrentStep(prevStep => {
        if (prevStep >= simulationResults.history.length - 1) {
          setIsPlaying(false);
          return prevStep;
        }
        return prevStep + 1;
      });
    }, playbackSpeed);

    return () => clearInterval(interval);
  }, [isPlaying, simulationResults, playbackSpeed]);

  const currentStepData = simulationResults?.history?.[currentStep];
  
  // Get the most recent substrate data
  const getCurrentSubstrateData = () => {
    if (!simulationResults?.history) return null;
    
    for (let i = currentStep; i >= 0; i--) {
      const stepData = simulationResults.history[i];
      if (stepData.substrate_data) {
        return stepData.substrate_data;
      }
    }
    
    return simulationResults.final_substrate_data;
  };

  const currentSubstrateData = getCurrentSubstrateData();

  const metrics = {
    currentStep: currentStepData?.step ?? 0,
    totalSteps: simulationResults?.total_steps_run ?? 0,
    time: currentStepData?.time ?? 0,
    cellsKilled: simulationResults?.tumor_statistics?.cells_killed ?? 0,
    deliveries: currentStepData?.metrics?.total_deliveries ?? 0,
    drugDelivered: currentStepData?.metrics?.total_drug_delivered ?? 0,
    hypoxicCells: currentStepData?.metrics?.hypoxic_cells ?? 0,
    viableCells: currentStepData?.metrics?.viable_cells ?? 0,
  };

  return (
    <div className="flex h-screen bg-background text-foreground">
      <SimulationLoading 
        isVisible={isLoading}
        progress={loadingProgress}
        currentStep={Math.floor((loadingProgress / 100) * config.max_steps)}
        totalSteps={config.max_steps}
      />
      
      <TumorSimulationSidebar
        settings={config}
        onSettingsChange={setConfig}
        onRunSimulation={runSimulation}
        isLoading={isLoading}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Back to Home Button */}
        <div className="p-2 border-b bg-white">
          <Button
            onClick={() => navigate('/')}
            variant="ghost"
            size="sm"
            className="text-gray-600 hover:text-gray-900"
          >
            <Home className="w-4 h-4 mr-2" />
            Back to Home
          </Button>
        </div>

        <TumorSimulationControls
          isRunning={isPlaying}
          onStart={() => simulationResults && setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onStep={handleStepForward}
          onStepBackward={handleStepBackward}
          onReset={handleReset}
          onGoToStart={handleGoToStart}
          onGoToEnd={handleGoToEnd}
          metrics={metrics}
          isSimulationLoaded={!!simulationResults}
          playbackSpeed={playbackSpeed}
          onSpeedChange={setPlaybackSpeed}
          currentStep={currentStep}
          totalSteps={simulationResults?.history?.length ?? 0}
        />

        <div className="flex-1 overflow-auto">
          <div className="p-4 space-y-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Brain className="w-6 h-6 text-pink-500" />
                  <CardTitle>🧠 Glioblastoma Tumor Microenvironment</CardTitle>
                </div>
                <CardDescription>
                  {simulationResults 
                    ? `Step ${currentStep + 1} of ${simulationResults.history.length} • Time: ${metrics.time.toFixed(3)} min`
                    : "Configure nanobot parameters and start simulation"
                  }
                </CardDescription>
                {simulationResults && (
                  <div className="flex gap-2 mt-3">
                    <Button
                      size="sm"
                      variant={!detailedMode ? "default" : "outline"}
                      onClick={() => setDetailedMode(false)}
                      className={!detailedMode ? "bg-blue-500 hover:bg-blue-600" : ""}
                    >
                      👤 Simple Mode
                    </Button>
                    <Button
                      size="sm"
                      variant={detailedMode ? "default" : "outline"}
                      onClick={() => setDetailedMode(true)}
                      className={detailedMode ? "bg-purple-500 hover:bg-purple-600" : ""}
                    >
                      🔬 Detailed Mode (Geek)
                    </Button>
                  </div>
                )}
              </CardHeader>
              <CardContent>
                <Tabs value={selectedSubstrate} onValueChange={setSelectedSubstrate} className="w-full">
                  <TabsList className="grid w-full grid-cols-5">
                    <TabsTrigger value="oxygen">Oxygen</TabsTrigger>
                    <TabsTrigger value="drug">Drug</TabsTrigger>
                    <TabsTrigger value="trail">Trail</TabsTrigger>
                    <TabsTrigger value="alarm">Alarm</TabsTrigger>
                    <TabsTrigger value="recruitment">Recruitment</TabsTrigger>
                  </TabsList>
                  <TabsContent value={selectedSubstrate} className="mt-4">
                    {simulationResults ? (
                      <TumorSimulationGrid
                        domainSize={config.domain_size}
                        nanobots={currentStepData?.nanobots ?? []}
                        tumorCells={currentStepData?.tumor_cells ?? []}
                        vessels={simulationResults.history[0]?.vessels ?? []}
                        substrateData={currentSubstrateData}
                        selectedSubstrate={selectedSubstrate}
                        tumorRadius={config.tumor_radius}
                        detailedMode={detailedMode}
                      />
                    ) : (
                      <div className="text-center py-12 text-muted-foreground">
                        <Brain className="w-16 h-16 mx-auto mb-4 text-pink-300" />
                        <h3 className="text-lg font-semibold">Ready to Simulate</h3>
                        <p>Configure your nanobot swarm and click "Run Simulation"</p>
                        <div className="mt-4 p-4 bg-pink-50 dark:bg-pink-950 rounded-lg max-w-md mx-auto">
                          <p className="text-sm">
                            💡 <strong>Tip:</strong> Nanobots navigate toward hypoxic tumor regions using 
                            chemotaxis and pheromone trails, delivering targeted drug payloads.
                          </p>
                        </div>
                      </div>
                    )}
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Legend */}
            {simulationResults && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">🎨 Visualization Legend</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                      <span>Nanobots</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                      <span>Tumor Cells</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                      <span>Blood Vessels</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                      <span>Hypoxic Regions</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Performance Charts */}
            {simulationResults && (
              <>
                <Separator />
                <TumorPerformanceCharts
                  simulationResults={simulationResults}
                  currentStep={currentStep}
                />
              </>
            )}

            {/* Tumor Statistics */}
            {simulationResults && (
              <>
                <Separator />
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Activity className="w-5 h-5 text-green-500" />
                      <CardTitle>📊 Treatment Outcomes</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="text-center p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                        <div className="text-2xl font-bold text-red-600">
                          {simulationResults.tumor_statistics.cells_killed}
                        </div>
                        <div className="text-xs text-muted-foreground">Cells Killed</div>
                      </div>
                      <div className="text-center p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">
                          {metrics.deliveries}
                        </div>
                        <div className="text-xs text-muted-foreground">Drug Deliveries</div>
                      </div>
                      <div className="text-center p-3 bg-green-50 dark:bg-green-950 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">
                          {(simulationResults.tumor_statistics.kill_rate * 100).toFixed(1)}%
                        </div>
                        <div className="text-xs text-muted-foreground">Kill Rate</div>
                      </div>
                      <div className="text-center p-3 bg-purple-50 dark:bg-purple-950 rounded-lg">
                        <div className="text-2xl font-bold text-purple-600">
                          {metrics.hypoxicCells}
                        </div>
                        <div className="text-xs text-muted-foreground">Hypoxic Cells</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}

            {/* Technical Details */}
            {simulationResults && (
              <>
                <Separator />
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Zap className="w-5 h-5 text-yellow-500" />
                      <CardTitle>🔬 Technical Parameters</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <h4 className="font-semibold mb-2">Simulation Setup:</h4>
                        <ul className="space-y-1 text-muted-foreground">
                          <li>Domain: {config.domain_size} µm</li>
                          <li>Voxel Size: {config.voxel_size} µm</li>
                          <li>Tumor Radius: {config.tumor_radius} µm</li>
                          <li>Nanobots: {config.n_nanobots}</li>
                          <li>Agent Type: {config.agent_type}</li>
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-semibold mb-2">Tumor State:</h4>
                        <ul className="space-y-1 text-muted-foreground">
                          <li>Viable: {metrics.viableCells}</li>
                          <li>Hypoxic: {metrics.hypoxicCells}</li>
                          <li>Necrotic: {currentStepData?.metrics?.necrotic_cells ?? 0}</li>
                          <li>Apoptotic: {currentStepData?.metrics?.apoptotic_cells ?? 0}</li>
                        </ul>
                      </div>
                      <div>
                        <h4 className="font-semibold mb-2">Treatment Progress:</h4>
                        <ul className="space-y-1 text-muted-foreground">
                          <li>Time: {metrics.time.toFixed(3)} min</li>
                          <li>Drug Delivered: {metrics.drugDelivered.toFixed(1)} units</li>
                          <li>Delivery Efficiency: {(metrics.cellsKilled / Math.max(metrics.deliveries, 1)).toFixed(2)} cells/delivery</li>
                          <li>API Calls: {currentStepData?.metrics?.total_api_calls ?? 0}</li>
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default TumorSimulation;

