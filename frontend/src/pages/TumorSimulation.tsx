import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { TumorSimulationLoading } from "@/components/TumorSimulationLoading";
import { TumorSimulationGrid } from "@/components/TumorSimulationGrid";
import { TumorSimulation3D } from "@/components/tumor/TumorSimulation3D";
import { TumorSimulationControls } from "@/components/TumorSimulationControls";
import { TumorSimulationSidebar } from "@/components/TumorSimulationSidebar";
import { TumorAnalysisCharts } from "@/components/tumor/TumorAnalysisCharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Brain, Activity, Zap, Home, Microscope, Sparkles, BarChart3 } from "lucide-react";
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
  use_brats?: boolean;
  brats_patient?: string;
  brats_dataset?: string;
}

const TumorSimulation = () => {
  const navigate = useNavigate();
  const [config, setConfig] = useState<TumorSimulationConfig>({
    domain_size: 600.0,
    voxel_size: 20.0,
    n_nanobots: 10,
    tumor_radius: 200.0,
    agent_type: "LLM-Powered",
    selected_model: "mistralai/Mistral-Large-Instruct-2411",
    use_queen: true,
    use_llm_queen: true,
    max_steps: 200,
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
  const [viewMode, setViewMode] = useState<'2D' | '3D'>('2D'); // 2D vs 3D view toggle

  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    setLoadingProgress(0);
    setIsPlaying(false);
    setSimulationResults(null);
    
    const isBratsMode = config.use_brats && config.brats_patient;
    toast.info(isBratsMode ? "Starting BraTS patient simulation..." : "Starting tumor nanobot simulation...");

    try {
      const progressInterval = setInterval(() => {
        setLoadingProgress(prev => Math.min(prev + 1, 90));
      }, 200);

      // Choose endpoint based on BraTS mode
      const endpoint = isBratsMode 
        ? `${API_BASE_URL}/simulation/tumor/from-brats`
        : `${API_BASE_URL}/simulation/tumor/run`;
      
      // Prepare request config
      const requestConfig = isBratsMode
        ? {
            patient_id: config.brats_patient,
            dataset: config.brats_dataset || "additional_training",
            domain_size: config.domain_size,
            voxel_size: config.voxel_size,
            n_nanobots: config.n_nanobots,
            agent_type: config.agent_type,
            selected_model: config.selected_model,
            use_queen: config.use_queen,
            use_llm_queen: config.use_llm_queen,
            max_steps: config.max_steps,
            cell_density: config.cell_density,
            vessel_density: config.vessel_density,
          }
        : config;

      const response = await axios.post(endpoint, requestConfig);
      
      clearInterval(progressInterval);
      setLoadingProgress(100);

      setSimulationResults(response.data);
      setCurrentStep(0);
      
      // Save simulation data to session storage for visualization tab
      sessionStorage.setItem('tumorSimulationResults', JSON.stringify(response.data));
      sessionStorage.setItem('tumorSimulationConfig', JSON.stringify(config));
      sessionStorage.setItem('tumorSimulationStep', '0');
      
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
      <TumorSimulationLoading 
        isVisible={isLoading}
        progress={loadingProgress}
        currentStep={Math.floor((loadingProgress / 100) * config.max_steps)}
        totalSteps={config.max_steps}
        config={config}
      />
      
      <TumorSimulationSidebar
        settings={config}
        onSettingsChange={setConfig}
        onRunSimulation={runSimulation}
        isLoading={isLoading}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Modern Header with gradient background */}
        <div className="p-5 border-b bg-gradient-to-r from-white via-blue-50/80 to-indigo-50/80 dark:from-slate-900 dark:via-slate-800 dark:to-slate-700 shadow-md backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-5">
              <Button
                onClick={() => navigate('/')}
                variant="ghost"
                size="sm"
                className="text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 dark:text-slate-300 dark:hover:text-slate-100 dark:hover:bg-slate-700/80 transition-all duration-200 rounded-lg"
              >
                <Home className="w-4 h-4 mr-2" />
                Back to Home
              </Button>
              <Separator orientation="vertical" className="h-8" />
              <div className="flex items-center gap-4">
                <div className="p-2 rounded-xl bg-gradient-to-br from-pink-500/10 to-purple-500/10 dark:from-pink-500/20 dark:to-purple-500/20">
                  <Microscope className="w-5 h-5 text-pink-600 dark:text-pink-400" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                    Tumor Nanobot Simulation
                  </h1>
                  <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                    Glioblastoma Treatment Analysis Platform
                  </p>
                </div>
              </div>
            </div>
            
            {simulationResults && (
              <div className="flex items-center gap-3">
                <Badge variant="secondary" className="px-4 py-1.5 bg-blue-500/10 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800 hover:bg-blue-500/20 transition-colors">
                  <Activity className="w-3.5 h-3.5 mr-1.5" />
                  Step {currentStep + 1}/{simulationResults.history.length}
                </Badge>
                <Badge variant="secondary" className="px-4 py-1.5 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800 hover:bg-emerald-500/20 transition-colors">
                  <Sparkles className="w-3.5 h-3.5 mr-1.5" />
                  {metrics.time.toFixed(2)} min
                </Badge>
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

         <div className="flex-1 overflow-auto bg-gradient-to-b from-slate-50/70 via-blue-50/40 to-indigo-50/30 dark:from-slate-900/70 dark:via-slate-800/40 dark:to-slate-900/30">
           <div className="p-6 space-y-6">
             <Card className="border border-slate-200/80 dark:border-slate-700/80 shadow-2xl bg-white/90 dark:bg-slate-800/90 backdrop-blur-md hover:shadow-3xl transition-shadow duration-300">
               <CardHeader className="pb-5">
                 <div className="flex items-start justify-between">
                   <div className="flex items-start gap-4">
                     <div className="p-2.5 rounded-xl bg-gradient-to-br from-pink-500/10 to-purple-500/10 dark:from-pink-500/20 dark:to-purple-500/20 mt-0.5">
                       <Microscope className="w-6 h-6 text-pink-600 dark:text-pink-400" />
                     </div>
                     <div>
                       <CardTitle className="text-3xl font-bold bg-gradient-to-r from-pink-600 via-purple-600 to-indigo-600 bg-clip-text text-transparent tracking-tight">
                         Glioblastoma Tumor Microenvironment
                       </CardTitle>
                       <CardDescription className="text-base mt-2 text-slate-600 dark:text-slate-400">
                         {simulationResults 
                           ? (
                             <div className="flex items-center gap-3 flex-wrap">
                               <Badge variant="outline" className="text-xs">
                                 Step {currentStep + 1} of {simulationResults.history.length}
                               </Badge>
                               <span className="text-slate-400">•</span>
                               <Badge variant="outline" className="text-xs">
                                 Time: {metrics.time.toFixed(3)} min
                               </Badge>
                             </div>
                           )
                           : "Configure nanobot parameters and start simulation"
                         }
                       </CardDescription>
                     </div>
                   </div>
                   
                   {simulationResults && (
                     <div className="flex gap-2 flex-wrap">
                       <Button
                         size="sm"
                         variant={viewMode === '2D' ? "default" : "outline"}
                         onClick={() => setViewMode('2D')}
                         className={`transition-all duration-200 rounded-lg ${
                           viewMode === '2D' 
                             ? "bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 shadow-md text-white border-0" 
                             : "hover:bg-emerald-50 dark:hover:bg-emerald-900/20 border-slate-200 dark:border-slate-700"
                         }`}
                       >
                         📊 2D View
                       </Button>
                       <Button
                         size="sm"
                         variant={viewMode === '3D' ? "default" : "outline"}
                         onClick={() => setViewMode('3D')}
                         className={`transition-all duration-200 rounded-lg ${
                           viewMode === '3D' 
                             ? "bg-gradient-to-r from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700 shadow-md text-white border-0" 
                             : "hover:bg-purple-50 dark:hover:bg-purple-900/20 border-slate-200 dark:border-slate-700"
                         }`}
                       >
                         🎮 3D View
                       </Button>
                       <Separator orientation="vertical" className="h-6 mx-1" />
                       <Button
                         size="sm"
                         variant={!detailedMode ? "default" : "outline"}
                         onClick={() => setDetailedMode(false)}
                         className={`transition-all duration-200 rounded-lg ${
                           !detailedMode 
                             ? "bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 shadow-md text-white border-0" 
                             : "hover:bg-blue-50 dark:hover:bg-blue-900/20 border-slate-200 dark:border-slate-700"
                         }`}
                       >
                         👤 Simple
                       </Button>
                       <Button
                         size="sm"
                         variant={detailedMode ? "default" : "outline"}
                         onClick={() => setDetailedMode(true)}
                         className={`transition-all duration-200 rounded-lg ${
                           detailedMode 
                             ? "bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 shadow-md text-white border-0" 
                             : "hover:bg-indigo-50 dark:hover:bg-indigo-900/20 border-slate-200 dark:border-slate-700"
                         }`}
                       >
                         🔬 Detailed
                       </Button>
                     </div>
                   )}
                 </div>
               </CardHeader>
               <CardContent>
                 {simulationResults ? (
                   <Tabs defaultValue="visualization" className="w-full">
                     <TabsList className="grid w-full grid-cols-2 bg-slate-100 dark:bg-slate-700 p-1 rounded-lg mb-6">
                       <TabsTrigger 
                         value="visualization" 
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-blue-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-blue-400 transition-all duration-200"
                       >
                         <Microscope className="w-4 h-4 mr-2" />
                         Visualization
                       </TabsTrigger>
                       <TabsTrigger 
                         value="analysis" 
                         className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-purple-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-purple-400 transition-all duration-200"
                       >
                         <BarChart3 className="w-4 h-4 mr-2" />
                         Performance Analysis
                       </TabsTrigger>
                     </TabsList>
                     
                     <TabsContent value="visualization" className="mt-0">
                       <Tabs value={selectedSubstrate} onValueChange={setSelectedSubstrate} className="w-full">
                         <TabsList className="grid w-full grid-cols-9 bg-slate-100 dark:bg-slate-700 p-1 rounded-lg">
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
                           <TabsTrigger 
                             value="trail" 
                             className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-emerald-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-emerald-400 transition-all duration-200"
                           >
                             🛤️ Trail
                           </TabsTrigger>
                           <TabsTrigger 
                             value="alarm" 
                             className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-red-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-red-400 transition-all duration-200"
                           >
                             🚨 Alarm
                           </TabsTrigger>
                           <TabsTrigger 
                             value="recruitment" 
                             className="data-[state=active]:bg-white data-[state=active]:shadow-sm data-[state=active]:text-blue-600 dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-blue-400 transition-all duration-200"
                           >
                             📢 Recruitment
                           </TabsTrigger>
                         </TabsList>
                         <TabsContent value={selectedSubstrate} className="mt-6">
                           <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 p-4 bg-slate-50/50 dark:bg-slate-800/50">
                             {viewMode === '2D' ? (
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
                               <TumorSimulation3D
                                 domainSize={config.domain_size}
                                 nanobots={currentStepData?.nanobots ?? []}
                                 tumorCells={currentStepData?.tumor_cells ?? []}
                                 vessels={simulationResults.history[0]?.vessels ?? []}
                                 substrateData={currentSubstrateData}
                                 selectedSubstrate={selectedSubstrate}
                                 tumorRadius={config.tumor_radius}
                                 detailedMode={detailedMode}
                               />
                             )}
                           </div>
                         </TabsContent>
                       </Tabs>
                     </TabsContent>
                     
                     <TabsContent value="analysis" className="mt-0">
                       <TumorAnalysisCharts 
                         simulationResults={simulationResults}
                         currentStep={currentStep}
                       />
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

            {/* Modern Legend - only show after simulation starts */}
            {simulationResults && (
              <Card className="border border-slate-200/80 dark:border-slate-700/80 shadow-xl bg-white/80 dark:bg-slate-800/80 backdrop-blur-md hover:shadow-2xl transition-shadow duration-300">
                <CardHeader className="pb-4">
                  <CardTitle className="text-xl flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 dark:from-indigo-500/30 dark:to-purple-500/30">
                      <Sparkles className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <span className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                      Visualization Legend
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-br from-blue-50 to-blue-100/50 dark:from-blue-950/40 dark:to-blue-900/20 border border-blue-200/50 dark:border-blue-800/50 hover:shadow-md transition-all duration-200">
                      <div className="w-5 h-5 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full shadow-sm ring-2 ring-blue-200 dark:ring-blue-800"></div>
                      <span className="font-semibold text-sm text-blue-900 dark:text-blue-200">Nanobots</span>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-br from-red-50 to-red-100/50 dark:from-red-950/40 dark:to-red-900/20 border border-red-200/50 dark:border-red-800/50 hover:shadow-md transition-all duration-200">
                      <div className="w-5 h-5 bg-gradient-to-br from-red-500 to-red-600 rounded-full shadow-sm ring-2 ring-red-200 dark:ring-red-800"></div>
                      <span className="font-semibold text-sm text-red-900 dark:text-red-200">Tumor Cells</span>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-br from-emerald-50 to-emerald-100/50 dark:from-emerald-950/40 dark:to-emerald-900/20 border border-emerald-200/50 dark:border-emerald-800/50 hover:shadow-md transition-all duration-200">
                      <div className="w-5 h-5 bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-full shadow-sm ring-2 ring-emerald-200 dark:ring-emerald-800"></div>
                      <span className="font-semibold text-sm text-emerald-900 dark:text-emerald-200">Blood Vessels</span>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-br from-purple-50 to-purple-100/50 dark:from-purple-950/40 dark:to-purple-900/20 border border-purple-200/50 dark:border-purple-800/50 hover:shadow-md transition-all duration-200">
                      <div className="w-5 h-5 bg-gradient-to-br from-purple-500 to-purple-600 rounded-full shadow-sm ring-2 ring-purple-200 dark:ring-purple-800"></div>
                      <span className="font-semibold text-sm text-purple-900 dark:text-purple-200">Hypoxic Regions</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default TumorSimulation;

