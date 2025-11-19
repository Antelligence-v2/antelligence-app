import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, ChevronDown, ChevronRight, Settings2, Microscope, Activity, Users, Database } from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

interface TumorSimulationSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  settings: any;
  onSettingsChange: (settings: any) => void;
  onRunSimulation: () => void;
  isLoading: boolean;
}

export function TumorSimulationSidebar({
  isCollapsed,
  onToggleCollapse,
  settings,
  onSettingsChange,
  onRunSimulation,
  isLoading,
}: TumorSimulationSidebarProps) {
  const updateSetting = (key: string, value: any) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  const [domainOpen, setDomainOpen] = useState(true);
  const [nanobotOpen, setNanobotOpen] = useState(true);
  const [queenOpen, setQueenOpen] = useState(false);
  const [simOpen, setSimOpen] = useState(false);
  const [bratsOpen, setBratsOpen] = useState(false);
  
  // BraTS data state
  const [useBrats, setUseBrats] = useState(false);
  const [bratsPatients, setBratsPatients] = useState<string[]>([]);
  const [selectedPatient, setSelectedPatient] = useState<string>("");
  const [selectedDataset, setSelectedDataset] = useState<"training" | "validation" | "additional_training">("additional_training");
  
  useEffect(() => {
    const loadBratsPatients = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/brats/patients`);
        const allPatients = Object.values(response.data.datasets)
          .flat() as string[];
        setBratsPatients(allPatients);
        if (allPatients.length > 0 && !selectedPatient) {
          setSelectedPatient(allPatients[0]);
        }
      } catch (error) {
        console.error("Failed to load BraTS patients:", error);
      }
    };
    loadBratsPatients();
  }, []);

  if (isCollapsed) {
    return (
      <div className="w-16 border-r border-border bg-background flex flex-col items-center py-4">
        <Button
          onClick={onToggleCollapse}
          variant="ghost"
          size="icon"
          className="mb-4"
        >
          <Settings2 className="h-5 w-5 text-muted-foreground" />
        </Button>
      </div>
    );
  }

  return (
    <aside className="w-80 border-r border-border bg-background/95 backdrop-blur flex flex-col h-full">
      <div className="p-4 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground flex items-center gap-2">
          <Settings2 className="h-4 w-4" />
          Configuration
        </h2>
        <Button
          onClick={onToggleCollapse}
          variant="ghost"
          size="icon"
          className="h-8 w-8"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        
        {/* BraTS Data Settings */}
        <Collapsible open={bratsOpen} onOpenChange={setBratsOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" />
                Patient Data (BraTS)
              </span>
              {bratsOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium text-muted-foreground">Use Real Data</Label>
              <Switch
                checked={useBrats}
                onCheckedChange={setUseBrats}
              />
            </div>
            {useBrats && (
              <>
                <div className="space-y-2">
                  <Label className="text-xs font-medium text-muted-foreground">Dataset</Label>
                  <Select
                    value={selectedDataset}
                    onValueChange={(value: any) => setSelectedDataset(value)}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="training">Training</SelectItem>
                      <SelectItem value="validation">Validation</SelectItem>
                      <SelectItem value="additional_training">Additional</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs font-medium text-muted-foreground">Patient ID</Label>
                  <Select
                    value={selectedPatient}
                    onValueChange={setSelectedPatient}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="max-h-[200px]">
                      {bratsPatients.slice(0, 50).map((patient) => (
                        <SelectItem key={patient} value={patient}>
                          {patient}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Domain Settings */}
        <Collapsible open={domainOpen} onOpenChange={setDomainOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Microscope className="h-4 w-4 text-primary" />
                Environment
              </span>
              {domainOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Domain Size (µm)</Label>
              <Input
                type="number"
                value={settings.domain_size}
                onChange={(e) => updateSetting("domain_size", parseFloat(e.target.value))}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Voxel Size (µm)</Label>
              <Input
                type="number"
                value={settings.voxel_size}
                onChange={(e) => updateSetting("voxel_size", parseFloat(e.target.value))}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Tumor Radius (µm)</Label>
              <Input
                type="number"
                value={settings.tumor_radius}
                onChange={(e) => updateSetting("tumor_radius", parseFloat(e.target.value))}
                className="h-8 text-xs"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Nanobot Settings */}
        <Collapsible open={nanobotOpen} onOpenChange={setNanobotOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Brain className="h-4 w-4 text-primary" />
                Swarm Intelligence
              </span>
              {nanobotOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Nanobot Count</Label>
              <Input
                type="number"
                value={settings.n_nanobots}
                onChange={(e) => updateSetting("n_nanobots", parseInt(e.target.value))}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Agent Type</Label>
              <Select
                value={settings.agent_type}
                onValueChange={(value) => updateSetting("agent_type", value)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Rule-Based">Rule-Based</SelectItem>
                  <SelectItem value="LLM-Powered">LLM-Powered</SelectItem>
                  <SelectItem value="Hybrid">Hybrid</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {settings.agent_type !== "Rule-Based" && (
              <div className="space-y-2">
                <Label className="text-xs font-medium text-muted-foreground">LLM Model</Label>
                <Select
                  value={settings.selected_model}
                  onValueChange={(value) => updateSetting("selected_model", value)}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="meta-llama/Llama-3.3-70B-Instruct">Llama 3.3 70B</SelectItem>
                    <SelectItem value="meta-llama/Llama-3.2-3B-Instruct">Llama 3.2 3B</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Queen Settings */}
        <Collapsible open={queenOpen} onOpenChange={setQueenOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                Coordination
              </span>
              {queenOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium text-muted-foreground">Enable Queen</Label>
              <Switch
                checked={settings.use_queen}
                onCheckedChange={(checked) => updateSetting("use_queen", checked)}
              />
            </div>
            {settings.use_queen && (
              <div className="flex items-center justify-between">
                <Label className="text-xs font-medium text-muted-foreground">LLM Queen</Label>
                <Switch
                  checked={settings.use_llm_queen}
                  onCheckedChange={(checked) => updateSetting("use_llm_queen", checked)}
                />
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Simulation Settings */}
        <Collapsible open={simOpen} onOpenChange={setSimOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                Advanced
              </span>
              {simOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Max Steps</Label>
              <Input
                type="number"
                value={settings.max_steps}
                onChange={(e) => updateSetting("max_steps", parseInt(e.target.value))}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Cell Density</Label>
              <Input
                type="number"
                value={settings.cell_density}
                onChange={(e) => updateSetting("cell_density", parseFloat(e.target.value))}
                className="h-8 text-xs"
                step={0.0001}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Vessel Density</Label>
              <Input
                type="number"
                value={settings.vessel_density}
                onChange={(e) => updateSetting("vessel_density", parseFloat(e.target.value))}
                className="h-8 text-xs"
                step={0.001}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      {/* Run Button */}
      <div className="p-4 border-t border-border bg-muted/20">
        <Button
          onClick={onRunSimulation}
          disabled={isLoading}
          className="w-full shadow-sm transition-all active:scale-95"
          size="lg"
        >
          {isLoading ? "Processing..." : "Initialize Simulation"}
        </Button>
      </div>
    </aside>
  );
}
