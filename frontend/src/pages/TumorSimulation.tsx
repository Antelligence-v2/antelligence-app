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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

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
    agent_type: "LLM-Powered",
    selected_model: "meta-llama/Llama-3.3-70B-Instruct",
    use_queen: true,
    use_llm_queen: true,
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
     
     return simulationResults.final_substrate_data || null;
   };

   const currentSubstrateData = getCurrentSubstrateData();
   
   // Debug logging
   console.log('Simulation Results:', simulationResults);
   console.log('Current Step Data:', currentStepData);
   console.log('Current Substrate Data:', currentSubstrateData);

  const metrics = {
    currentStep: currentStepData?.step ?? 0,
    totalSteps: simulationResults?.total_steps_run ?? 0,
    time: currentStepData?.time ?? 0,
    cellsKilled: simulationResults?.tumor_statistics?.cells_killed ?? 0,
    deliveries: currentStepData?.metrics?.total_deliveries ?? 0,
    drugDelivered: currentStepData?.metrics?.total_drug_delivered ?? 0,
    hypoxicCells: currentStepData?.metrics?.hypoxic_cells ?? 0,
    viableCells: currentStepData?.metrics?.viable_cells ?? 0,
    // New biological metrics
    cellTypeDistribution: simulationResults?.tumor_statistics?.cell_type_distribution ?? {},
    immuneCellDistribution: simulationResults?.tumor_statistics?.immune_cell_distribution ?? {},
    totalImmuneCells: simulationResults?.tumor_statistics?.n_immune_cells ?? 0,
    totalVessels: simulationResults?.tumor_statistics?.n_vessels ?? 0,
    survivalRate: simulationResults?.tumor_statistics?.survival_rate ?? 0,
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 text-foreground">
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
        {/* Header with gradient background */}
        <div className="p-4 border-b bg-gradient-to-r from-white via-blue-50 to-indigo-50 dark:from-slate-800 dark:via-slate-700 dark:to-slate-600 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                onClick={() => navigate('/')}
                variant="ghost"
                size="sm"
                className="text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-300 dark:hover:text-slate-100 dark:hover:bg-slate-700 transition-all duration-200"
              >
                <Home className="w-4 h-4 mr-2" />
                Back to Home
              </Button>
              <div className="h-6 w-px bg-slate-300 dark:bg-slate-600" />
              <div className="flex items-center gap-3">
                <div>
                  <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                    Tumor Nanobot Simulation
                  </h1>
                  <p className="text-sm text-slate-600 dark:text-slate-400">
                    Glioblastoma Treatment Analysis
                  </p>
                </div>
              </div>
            </div>
            
            {simulationResults && (
              <div className="flex items-center gap-4 text-sm">
                <div className="px-3 py-1 bg-blue-100 dark:bg-blue-900 rounded-full">
                  <span className="font-semibold text-blue-800 dark:text-blue-200">
                    Step {currentStep + 1}/{simulationResults.history.length}
                  </span>
                </div>
                <div className="px-3 py-1 bg-green-100 dark:bg-green-900 rounded-full">
                  <span className="font-semibold text-green-800 dark:text-green-200">
                    {metrics.time.toFixed(2)}m
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {simulationResults && (
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
        )}

         <div className="flex-1 overflow-auto bg-gradient-to-b from-slate-50/50 to-blue-50/30 dark:from-slate-900/50 dark:to-slate-800/30">
           <div className="p-6 space-y-6">
             <Card className="border-0 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
               <CardHeader className="pb-4">
                 <div className="flex items-center justify-between">
                   <div className="flex items-center gap-3">
                     <div>
                       <CardTitle className="text-2xl font-bold bg-gradient-to-r from-pink-600 to-purple-600 bg-clip-text text-transparent">
                         Glioblastoma Tumor Microenvironment
                       </CardTitle>
                       <CardDescription className="text-base mt-1">
                         {simulationResults 
                           ? `Step ${currentStep + 1} of ${simulationResults.history.length} • Time: ${metrics.time.toFixed(3)} min`
                           : "Configure nanobot parameters and start simulation"
                         }
                       </CardDescription>
                     </div>
                   </div>
                   
                   {simulationResults && (
                     <div className="flex gap-2">
                       <Button
                         size="sm"
                         variant={!detailedMode ? "default" : "outline"}
                         onClick={() => setDetailedMode(false)}
                         className={`transition-all duration-200 ${
                           !detailedMode 
                             ? "bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-lg" 
                             : "hover:bg-blue-50 dark:hover:bg-blue-900/20"
                         }`}
                       >
                         👤 Simple Mode
                       </Button>
                       <Button
                         size="sm"
                         variant={detailedMode ? "default" : "outline"}
                         onClick={() => setDetailedMode(true)}
                         className={`transition-all duration-200 ${
                           detailedMode 
                             ? "bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 shadow-lg" 
                             : "hover:bg-purple-50 dark:hover:bg-purple-900/20"
                         }`}
                       >
                         🔬 Detailed Mode
                       </Button>
                     </div>
                   )}
                 </div>
               </CardHeader>
               <CardContent>
                 {simulationResults ? (
                   <Tabs value={selectedSubstrate} onValueChange={setSelectedSubstrate} className="w-full">
                     <TabsList className="grid w-full grid-cols-6 bg-slate-100 dark:bg-slate-700 p-1 rounded-lg">
                       <TabsTrigger 
                         value="oxygen" 
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-blue-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-blue-400 transition-all duration-200"
                       >
                         🫁 Oxygen
                       </TabsTrigger>
                       <TabsTrigger 
                         value="drug"
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-green-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-green-400 transition-all duration-200"
                       >
                         💊 Drug
                       </TabsTrigger>
                       <TabsTrigger 
                         value="ifn_gamma"
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-purple-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-purple-400 transition-all duration-200"
                       >
                         🦠 IFN-γ
                       </TabsTrigger>
                       <TabsTrigger 
                         value="tnf_alpha"
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-orange-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-orange-400 transition-all duration-200"
                       >
                         🔥 TNF-α
                       </TabsTrigger>
                       <TabsTrigger 
                         value="perforin"
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-red-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-red-400 transition-all duration-200"
                       >
                         ⚡ Perforin
                       </TabsTrigger>
                       <TabsTrigger 
                         value="chemokine_signal"
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-cyan-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-cyan-400 transition-all duration-200"
                       >
                         🧪 Chemokine
                       </TabsTrigger>
                     </TabsList>
                     <TabsContent value={selectedSubstrate} className="mt-6">
                       <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-4 bg-slate-50/50 dark:bg-slate-800/50">
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
                       </div>
                     </TabsContent>
                   </Tabs>
                 ) : (
                   <div className="text-center py-16 text-muted-foreground">
                     <div className="relative">
                       <div className="absolute inset-0 flex items-center justify-center">
                         <div className="w-32 h-32 bg-gradient-to-r from-pink-500/20 to-purple-500/20 rounded-full animate-pulse"></div>
                       </div>
                       <Brain className="w-20 h-20 mx-auto mb-6 text-pink-400 relative z-10" />
                     </div>
                     <h3 className="text-2xl font-bold mb-2 bg-gradient-to-r from-pink-600 to-purple-600 bg-clip-text text-transparent">
                       Ready to Simulate
                     </h3>
                     <p className="text-lg mb-6">Configure your nanobot swarm and click "Run Simulation"</p>
                     <div className="max-w-lg mx-auto p-6 bg-gradient-to-r from-pink-50 to-purple-50 dark:from-pink-950/50 dark:to-purple-950/50 rounded-2xl border border-pink-200 dark:border-pink-800">
                       <div className="flex items-start gap-3">
                         <div className="text-2xl">💡</div>
                         <div className="text-left">
                           <p className="font-semibold text-pink-800 dark:text-pink-200 mb-2">
                             How it works:
                           </p>
                           <p className="text-sm text-pink-700 dark:text-pink-300">
                             Nanobots navigate toward hypoxic tumor regions using chemotaxis and pheromone trails, 
                             delivering targeted drug payloads to maximize treatment effectiveness.
                           </p>
                         </div>
                       </div>
                     </div>
                   </div>
                 )}
               </CardContent>
            </Card>

            {/* All simulation-related sections - only show after simulation starts */}
            {simulationResults && (
              <>
                {/* Legend */}
                <Card className="border-0 shadow-lg bg-white/60 dark:bg-slate-800/60 backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <div className="p-1 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-500">
                        <span className="text-white text-sm">🎨</span>
                      </div>
                      Visualization Legend
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="flex items-center gap-3 p-2 rounded-lg bg-blue-50 dark:bg-blue-950/30">
                        <div className="w-4 h-4 bg-blue-500 rounded-full shadow-sm"></div>
                        <span className="font-medium text-sm">Nanobots</span>
                      </div>
                      <div className="flex items-center gap-3 p-2 rounded-lg bg-red-50 dark:bg-red-950/30">
                        <div className="w-4 h-4 bg-red-500 rounded-full shadow-sm"></div>
                        <span className="font-medium text-sm">Tumor Cells</span>
                      </div>
                      <div className="flex items-center gap-3 p-2 rounded-lg bg-green-50 dark:bg-green-950/30">
                        <div className="w-4 h-4 bg-green-500 rounded-full shadow-sm"></div>
                        <span className="font-medium text-sm">Blood Vessels</span>
                      </div>
                      <div className="flex items-center gap-3 p-2 rounded-lg bg-purple-50 dark:bg-purple-950/30">
                        <div className="w-4 h-4 bg-purple-500 rounded-full shadow-sm"></div>
                        <span className="font-medium text-sm">Hypoxic Regions</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Performance Charts */}
                <Card className="border-0 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
                  <CardHeader>
                    <CardTitle className="text-xl flex items-center gap-2">
                      <div className="p-1 rounded-lg bg-gradient-to-r from-green-500 to-blue-500">
                        <span className="text-white text-sm">📈</span>
                      </div>
                      Performance Analytics
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <TumorPerformanceCharts
                      simulationResults={simulationResults}
                      currentStep={currentStep}
                    />
                  </CardContent>
                </Card>

                {/* Tumor Statistics */}
                <Card className="border-0 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 shadow-lg">
                        <Activity className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">📊 Treatment Outcomes</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                          Real-time metrics from nanobot therapy
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="text-center p-4 bg-gradient-to-br from-red-50 to-red-100 dark:from-red-950/50 dark:to-red-900/30 rounded-xl border border-red-200 dark:border-red-800">
                        <div className="text-3xl font-bold text-red-600 dark:text-red-400 mb-1">
                          {simulationResults.tumor_statistics?.cells_killed || 0}
                        </div>
                        <div className="text-sm font-medium text-red-700 dark:text-red-300">Cells Killed</div>
                      </div>
                      <div className="text-center p-4 bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-950/50 dark:to-blue-900/30 rounded-xl border border-blue-200 dark:border-blue-800">
                        <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-1">
                          {metrics.deliveries}
                        </div>
                        <div className="text-sm font-medium text-blue-700 dark:text-blue-300">Drug Deliveries</div>
                      </div>
                      <div className="text-center p-4 bg-gradient-to-br from-green-50 to-green-100 dark:from-green-950/50 dark:to-green-900/30 rounded-xl border border-green-200 dark:border-green-800">
                        <div className="text-3xl font-bold text-green-600 dark:text-green-400 mb-1">
                          {((simulationResults.tumor_statistics?.kill_rate || 0) * 100).toFixed(1)}%
                        </div>
                        <div className="text-sm font-medium text-green-700 dark:text-green-300">Kill Rate</div>
                      </div>
                      <div className="text-center p-4 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-950/50 dark:to-purple-900/30 rounded-xl border border-purple-200 dark:border-purple-800">
                        <div className="text-3xl font-bold text-purple-600 dark:text-purple-400 mb-1">
                          {metrics.hypoxicCells}
                        </div>
                        <div className="text-sm font-medium text-purple-700 dark:text-purple-300">Hypoxic Cells</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Technical Details */}
                <Card className="border-0 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-gradient-to-r from-yellow-500 to-orange-500 shadow-lg">
                        <Zap className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">🔬 Technical Parameters</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                          Detailed simulation configuration and metrics
                        </p>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                          Simulation Setup
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Domain:</span>
                            <span className="font-medium">{config.domain_size} µm</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Voxel Size:</span>
                            <span className="font-medium">{config.voxel_size} µm</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Tumor Radius:</span>
                            <span className="font-medium">{config.tumor_radius} µm</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Nanobots:</span>
                            <span className="font-medium">{config.n_nanobots}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Agent Type:</span>
                            <span className="font-medium">{config.agent_type}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                          Tumor State
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Viable:</span>
                            <span className="font-medium text-green-600">{metrics.viableCells}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Hypoxic:</span>
                            <span className="font-medium text-purple-600">{metrics.hypoxicCells}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Necrotic:</span>
                            <span className="font-medium text-gray-600">{currentStepData?.metrics?.necrotic_cells ?? 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Apoptotic:</span>
                            <span className="font-medium text-orange-600">{currentStepData?.metrics?.apoptotic_cells ?? 0}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          Treatment Progress
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Time:</span>
                            <span className="font-medium">{metrics.time.toFixed(3)} min</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Drug Delivered:</span>
                            <span className="font-medium">{metrics.drugDelivered.toFixed(1)} units</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Efficiency:</span>
                            <span className="font-medium">{(metrics.cellsKilled / Math.max(metrics.deliveries, 1)).toFixed(2)} cells/delivery</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">API Calls:</span>
                            <span className="font-medium">{currentStepData?.metrics?.total_api_calls ?? 0}</span>
                          </div>
                        </div>
                      </div>
                      
                      {/* New Biological Metrics Section */}
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                          Cell Type Distribution
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Stem Cells:</span>
                            <span className="font-medium text-purple-600">{metrics.cellTypeDistribution.stem_cell || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Differentiated:</span>
                            <span className="font-medium text-blue-600">{metrics.cellTypeDistribution.differentiated || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Resistant:</span>
                            <span className="font-medium text-orange-600">{metrics.cellTypeDistribution.resistant || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Invasive:</span>
                            <span className="font-medium text-red-600">{metrics.cellTypeDistribution.invasive || 0}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-cyan-500 rounded-full"></div>
                          Immune System
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Total Immune Cells:</span>
                            <span className="font-medium text-cyan-600">{metrics.totalImmuneCells}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">T Cells:</span>
                            <span className="font-medium text-blue-500">{metrics.immuneCellDistribution.t_cell || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Macrophages:</span>
                            <span className="font-medium text-green-500">{metrics.immuneCellDistribution.macrophage || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">NK Cells:</span>
                            <span className="font-medium text-purple-500">{metrics.immuneCellDistribution.nk_cell || 0}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Dendritic:</span>
                            <span className="font-medium text-yellow-500">{metrics.immuneCellDistribution.dendritic || 0}</span>
                          </div>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <h4 className="font-semibold text-lg flex items-center gap-2">
                          <div className="w-2 h-2 bg-indigo-500 rounded-full"></div>
                          System Status
                        </h4>
                        <div className="space-y-2 text-sm">
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Blood Vessels:</span>
                            <span className="font-medium text-indigo-600">{metrics.totalVessels}</span>
                          </div>
                          <div className="flex justify-between p-2 bg-slate-50 dark:bg-slate-700 rounded-lg">
                            <span className="text-muted-foreground">Survival Rate:</span>
                            <span className="font-medium text-green-600">{(metrics.survivalRate * 100).toFixed(1)}%</span>
                          </div>
                        </div>
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

