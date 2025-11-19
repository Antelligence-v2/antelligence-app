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

// Auto-detect API base URL based on current host
const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  
  if (typeof window !== 'undefined') {
    const host = window.location.host;
    const protocol = window.location.protocol;
    
    if (host.includes('antelligence.co')) {
      return `${protocol}//${host}`;
    }
    
    if (host.includes('44.220.130.72')) {
      return `http://${host.split(':')[0]}:8001`;
    }
    
    return "http://127.0.0.1:8000";
  }
  
  return "http://127.0.0.1:8000";
};

const API_BASE_URL = getApiBaseUrl();
console.log('🌐 API Base URL:', API_BASE_URL);

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
  const [detailedMode, setDetailedMode] = useState(false);
  const [viewMode, setViewMode] = useState<'2D' | '3D'>('2D');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const runSimulation = useCallback(async () => {
    setIsLoading(true);
    setLoadingProgress(0);
    setIsPlaying(false);
    setSimulationResults(null);
    
    const isBratsMode = config.use_brats && config.brats_patient;
    toast.info(isBratsMode ? "Starting BraTS patient simulation..." : "Starting tumor nanobot simulation...");

    let progressInterval: NodeJS.Timeout | null = null;
    try {
      progressInterval = setInterval(() => {
        setLoadingProgress(prev => Math.min(prev + 1, 90));
      }, 200);

      const endpoint = isBratsMode 
        ? `${API_BASE_URL}/simulation/tumor/from-brats`
        : `${API_BASE_URL}/simulation/tumor/run`;
      
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

      console.log('📡 Calling API endpoint:', endpoint);
      console.log('📦 Request config:', requestConfig);
      
      const response = await axios.post(endpoint, requestConfig);
      
      if (progressInterval) clearInterval(progressInterval);
      setLoadingProgress(100);

      setSimulationResults(response.data);
      setCurrentStep(0);
      
      sessionStorage.setItem('tumorSimulationResults', JSON.stringify(response.data));
      sessionStorage.setItem('tumorSimulationConfig', JSON.stringify(config));
      sessionStorage.setItem('tumorSimulationStep', '0');
      
      setTimeout(() => {
        setIsLoading(false);
        setLoadingProgress(0);
        toast.success("Simulation complete! Results loaded for playback.");
      }, 800);
      
    } catch (error: any) {
      if (progressInterval) clearInterval(progressInterval);
      console.error("❌ Tumor simulation API error:", error);
      setIsLoading(false);
      setLoadingProgress(0);
      
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Unknown error';
      toast.error(`Failed to run simulation: ${errorMessage}`);
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
  
   const getCurrentSubstrateData = () => {
     if (!simulationResults?.history) return null;
     
     // Search backwards from current step
     for (let i = currentStep; i >= 0; i--) {
       const stepData = simulationResults.history[i];
       if (stepData.substrate_data) {
         return stepData.substrate_data;
       }
     }
     
     // If not found backwards, try forwards (e.g. if we are at step 0 and data is at step 1)
     for (let i = currentStep + 1; i < simulationResults.history.length; i++) {
        const stepData = simulationResults.history[i];
        if (stepData.substrate_data) {
          return stepData.substrate_data;
        }
     }

     return simulationResults.final_substrate_data || null;
   };

   const getCurrentTumorCells = () => {
     if (!simulationResults?.history) return [];
     
     // Search backwards from current step
     for (let i = currentStep; i >= 0; i--) {
       const stepData = simulationResults.history[i];
       if (stepData.tumor_cells && stepData.tumor_cells.length > 0) {
         return stepData.tumor_cells;
       }
     }

     // If not found backwards, try forwards
     for (let i = currentStep + 1; i < simulationResults.history.length; i++) {
        const stepData = simulationResults.history[i];
        if (stepData.tumor_cells && stepData.tumor_cells.length > 0) {
          return stepData.tumor_cells;
        }
     }
     
     return [];
   };

   const currentSubstrateData = getCurrentSubstrateData();
   const currentTumorCells = getCurrentTumorCells();

  const metrics = {
    currentStep: currentStepData?.step ?? 0,
    totalSteps: simulationResults?.total_steps_run ?? 0,
    time: currentStepData?.time ?? 0,
    cellsKilled: simulationResults?.tumor_statistics?.cells_killed ?? 0,
    deliveries: currentStepData?.metrics?.total_deliveries ?? 0,
    drugDelivered: currentStepData?.metrics?.total_drug_delivered ?? 0,
    hypoxicCells: currentStepData?.metrics?.hypoxic_cells ?? 0,
    viableCells: currentStepData?.metrics?.viable_cells ?? 0,
    cellTypeDistribution: simulationResults?.tumor_statistics?.cell_type_distribution ?? {},
    immuneCellDistribution: simulationResults?.tumor_statistics?.immune_cell_distribution ?? {},
    totalImmuneCells: simulationResults?.tumor_statistics?.n_immune_cells ?? 0,
    totalVessels: simulationResults?.tumor_statistics?.n_vessels ?? 0,
    survivalRate: simulationResults?.tumor_statistics?.survival_rate ?? 0,
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans">
      <TumorSimulationLoading 
        isVisible={isLoading}
        progress={loadingProgress}
        currentStep={Math.floor((loadingProgress / 100) * config.max_steps)}
        totalSteps={config.max_steps}
        config={config}
      />
      
      <TumorSimulationSidebar
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        settings={config}
        onSettingsChange={setConfig}
        onRunSimulation={runSimulation}
        isLoading={isLoading}
      />

      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="flex-none z-10 bg-background/80 backdrop-blur-sm border-b border-border">
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                onClick={() => navigate('/')}
                variant="ghost"
                size="sm"
                className="gap-2 text-muted-foreground hover:text-foreground"
              >
                <Home className="w-4 h-4" />
                Back
              </Button>
              <Separator orientation="vertical" className="h-6" />
              <div className="flex items-center gap-3">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <Microscope className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <h1 className="text-lg font-semibold tracking-tight">
                    Tumor Nanobot Simulation
                  </h1>
                  <p className="text-xs text-muted-foreground hidden md:block">
                    Glioblastoma Treatment Analysis Platform
                  </p>
                </div>
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
          </div>
        </div>

         <div className="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth">
           <div className="max-w-7xl mx-auto space-y-8">
             <Card className="border-0 shadow-sm ring-1 ring-border bg-card">
               <CardHeader className="pb-4 border-b border-border/50">
                 <div className="flex items-center justify-between">
                   <div className="flex items-center gap-3">
                     <CardTitle className="text-lg font-semibold flex items-center gap-2">
                       <Activity className="w-5 h-5 text-primary" />
                       Microenvironment
                     </CardTitle>
                     {simulationResults && (
                       <Badge variant="secondary" className="font-mono text-xs">
                         Step {currentStep + 1} / {simulationResults.history.length}
                       </Badge>
                     )}
                   </div>
                   
                   {simulationResults && (
                     <div className="flex gap-2">
                       <div className="flex bg-muted rounded-lg p-1">
                         <Button
                           size="sm"
                           variant={viewMode === '2D' ? "default" : "ghost"}
                           onClick={() => setViewMode('2D')}
                           className="h-7 text-xs px-3"
                         >
                           2D View
                         </Button>
                         <Button
                           size="sm"
                           variant={viewMode === '3D' ? "default" : "ghost"}
                           onClick={() => setViewMode('3D')}
                           className="h-7 text-xs px-3"
                         >
                           3D View
                         </Button>
                       </div>
                       <Separator orientation="vertical" className="h-8" />
                       <Button
                         size="sm"
                         variant={detailedMode ? "secondary" : "outline"}
                         onClick={() => setDetailedMode(!detailedMode)}
                         className="h-8 text-xs"
                       >
                         {detailedMode ? "Hide Details" : "Show Details"}
                       </Button>
                     </div>
                   )}
                 </div>
               </CardHeader>
               <CardContent className="p-6">
                 {simulationResults ? (
                   <Tabs defaultValue="visualization" className="w-full">
                     <TabsList className="grid w-full grid-cols-2 mb-6">
                       <TabsTrigger value="visualization" className="gap-2">
                         <Microscope className="w-4 h-4" />
                         Visualization
                       </TabsTrigger>
                       <TabsTrigger value="analysis" className="gap-2">
                         <BarChart3 className="w-4 h-4" />
                         Analysis
                       </TabsTrigger>
                     </TabsList>
                     
                     <TabsContent value="visualization" className="mt-0 space-y-6">
                       <Tabs value={selectedSubstrate} onValueChange={setSelectedSubstrate} className="w-full">
                         <div className="overflow-x-auto pb-2">
                           <TabsList className="inline-flex w-auto min-w-full justify-start">
                             <TabsTrigger value="oxygen">Oxygen</TabsTrigger>
                             <TabsTrigger value="drug">Drug</TabsTrigger>
                             <TabsTrigger value="ifn_gamma">IFN-γ</TabsTrigger>
                             <TabsTrigger value="tnf_alpha">TNF-α</TabsTrigger>
                             <TabsTrigger value="perforin">Perforin</TabsTrigger>
                             <TabsTrigger value="chemokine_signal">Chemokine</TabsTrigger>
                             <TabsTrigger value="trail">Trail</TabsTrigger>
                             <TabsTrigger value="alarm">Alarm</TabsTrigger>
                             <TabsTrigger value="recruitment">Recruitment</TabsTrigger>
                           </TabsList>
                         </div>
                         <TabsContent value={selectedSubstrate} className="mt-4">
                           <div className="rounded-xl border border-border bg-muted/10 p-4 flex justify-center">
                             {viewMode === '2D' ? (
                              <TumorSimulationGrid
                                domainSize={config.domain_size}
                                nanobots={currentStepData?.nanobots ?? []}
                                tumorCells={currentTumorCells}
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
                                tumorCells={currentTumorCells}
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
                   <div className="text-center py-20">
                     <div className="w-20 h-20 bg-primary/5 rounded-full flex items-center justify-center mx-auto mb-6 animate-pulse">
                       <Brain className="w-10 h-10 text-primary" />
                     </div>
                     <h3 className="text-2xl font-semibold mb-3">Ready to Simulate</h3>
                     <p className="text-muted-foreground max-w-md mx-auto mb-8">
                       Configure your nanobot swarm parameters in the sidebar and initialize the simulation environment.
                     </p>
                     <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto text-left text-sm">
                       <div className="p-4 rounded-lg border bg-card">
                         <div className="font-semibold mb-1 flex items-center gap-2">
                           <Zap className="w-4 h-4 text-yellow-500" />
                           Targeting
                         </div>
                         <p className="text-muted-foreground text-xs">Nanobots navigate toward hypoxic tumor regions using chemotaxis.</p>
                       </div>
                       <div className="p-4 rounded-lg border bg-card">
                         <div className="font-semibold mb-1 flex items-center gap-2">
                           <Activity className="w-4 h-4 text-green-500" />
                           Delivery
                         </div>
                         <p className="text-muted-foreground text-xs">Precise drug payload release maximizing therapeutic index.</p>
                       </div>
                       <div className="p-4 rounded-lg border bg-card">
                         <div className="font-semibold mb-1 flex items-center gap-2">
                           <Sparkles className="w-4 h-4 text-purple-500" />
                           Intelligence
                         </div>
                         <p className="text-muted-foreground text-xs">Swarm coordination via LLM-driven decision making.</p>
                       </div>
                     </div>
                   </div>
                 )}
               </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default TumorSimulation;
