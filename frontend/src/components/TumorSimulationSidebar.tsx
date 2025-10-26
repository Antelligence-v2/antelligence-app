import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";

interface TumorSimulationSidebarProps {
  settings: any;
  onSettingsChange: (settings: any) => void;
  onRunSimulation: () => void;
  isLoading: boolean;
}

export function TumorSimulationSidebar({
  settings,
  onSettingsChange,
  onRunSimulation,
  isLoading,
}: TumorSimulationSidebarProps) {
  const updateSetting = (key: string, value: any) => {
    onSettingsChange({ ...settings, [key]: value });
  };

  const [domainOpen, setDomainOpen] = useState(false);
  const [nanobotOpen, setNanobotOpen] = useState(false);
  const [queenOpen, setQueenOpen] = useState(false);
  const [simOpen, setSimOpen] = useState(false);

  return (
    <aside className="w-80 border-r bg-muted/10 overflow-y-auto">
      <div className="p-4 space-y-4">
        {/* Header */}
        <Card className="bg-gradient-to-r from-pink-50 to-purple-50 dark:from-pink-950 dark:to-purple-950">
          <CardHeader>
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">Tumor Nanobot Config</CardTitle>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              PhysiCell-inspired simulation
            </p>
          </CardHeader>
        </Card>

        {/* Domain Settings - Collapsible */}
        <Collapsible open={domainOpen} onOpenChange={setDomainOpen}>
          <Card>
          <CardHeader className="py-3">
            <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70">
              <CardTitle className="text-sm">🌍 Domain Setup</CardTitle>
              {domainOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </CollapsibleTrigger>
          </CardHeader>
          <CollapsibleContent>
          <CardContent className="space-y-3 pt-0">
            <div>
              <Label htmlFor="domain_size">Domain Size (µm)</Label>
              <Input
                id="domain_size"
                type="number"
                value={settings.domain_size}
                onChange={(e) => updateSetting("domain_size", parseFloat(e.target.value))}
                min={300}
                max={1000}
                step={50}
              />
            </div>
            <div>
              <Label htmlFor="voxel_size">Voxel Size (µm)</Label>
              <Input
                id="voxel_size"
                type="number"
                value={settings.voxel_size}
                onChange={(e) => updateSetting("voxel_size", parseFloat(e.target.value))}
                min={10}
                max={50}
                step={5}
              />
            </div>
            <div>
              <Label htmlFor="tumor_radius">Tumor Radius (µm)</Label>
              <Input
                id="tumor_radius"
                type="number"
                value={settings.tumor_radius}
                onChange={(e) => updateSetting("tumor_radius", parseFloat(e.target.value))}
                min={50}
                max={400}
                step={10}
              />
            </div>
          </CardContent>
          </CollapsibleContent>
        </Card>
        </Collapsible>

        {/* Nanobot Settings - Collapsible */}
        <Collapsible open={nanobotOpen} onOpenChange={setNanobotOpen}>
        <Card>
          <CardHeader className="py-3">
            <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70">
              <CardTitle className="text-sm">🤖 Nanobot Configuration</CardTitle>
              {nanobotOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </CollapsibleTrigger>
          </CardHeader>
          <CollapsibleContent>
          <CardContent className="space-y-3 pt-0">
            <div>
              <Label htmlFor="n_nanobots">Number of Nanobots</Label>
              <Input
                id="n_nanobots"
                type="number"
                value={settings.n_nanobots}
                onChange={(e) => updateSetting("n_nanobots", parseInt(e.target.value))}
                min={3}
                max={50}
              />
            </div>
            <div>
              <Label htmlFor="agent_type">Agent Type</Label>
              <Select
                value={settings.agent_type}
                onValueChange={(value) => updateSetting("agent_type", value)}
              >
                <SelectTrigger>
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
              <div>
                <Label htmlFor="selected_model">LLM Model</Label>
                <Select
                  value={settings.selected_model}
                  onValueChange={(value) => updateSetting("selected_model", value)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="meta-llama/Llama-3.3-70B-Instruct">Llama 3.3 70B</SelectItem>
                    <SelectItem value="meta-llama/Llama-3.2-3B-Instruct">Llama 3.2 3B</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </CardContent>
          </CollapsibleContent>
        </Card>
        </Collapsible>

        {/* Queen Settings - Collapsible */}
        <Collapsible open={queenOpen} onOpenChange={setQueenOpen}>
        <Card>
          <CardHeader className="py-3">
            <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70">
              <CardTitle className="text-sm">👑 Queen Coordination</CardTitle>
              {queenOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </CollapsibleTrigger>
          </CardHeader>
          <CollapsibleContent>
          <CardContent className="space-y-3 pt-0">
            <div className="flex items-center justify-between">
              <Label htmlFor="use_queen">Enable Queen</Label>
              <Switch
                id="use_queen"
                checked={settings.use_queen}
                onCheckedChange={(checked) => updateSetting("use_queen", checked)}
              />
            </div>
            {settings.use_queen && (
              <div className="flex items-center justify-between">
                <Label htmlFor="use_llm_queen">LLM Queen</Label>
                <Switch
                  id="use_llm_queen"
                  checked={settings.use_llm_queen}
                  onCheckedChange={(checked) => updateSetting("use_llm_queen", checked)}
                />
              </div>
            )}
          </CardContent>
          </CollapsibleContent>
        </Card>
        </Collapsible>

        {/* Simulation Settings - Collapsible */}
        <Collapsible open={simOpen} onOpenChange={setSimOpen}>
        <Card>
          <CardHeader className="py-3">
            <CollapsibleTrigger className="flex items-center justify-between w-full hover:opacity-70">
              <CardTitle className="text-sm">⚙️ Advanced Settings</CardTitle>
              {simOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </CollapsibleTrigger>
          </CardHeader>
          <CollapsibleContent>
          <CardContent className="space-y-3 pt-0">
            <div>
              <Label htmlFor="max_steps">Max Steps</Label>
              <Input
                id="max_steps"
                type="number"
                value={settings.max_steps}
                onChange={(e) => updateSetting("max_steps", parseInt(e.target.value))}
                min={20}
                max={500}
                step={10}
              />
            </div>
            <div>
              <Label htmlFor="cell_density">Cell Density (cells/µm²)</Label>
              <Input
                id="cell_density"
                type="number"
                value={settings.cell_density}
                onChange={(e) => updateSetting("cell_density", parseFloat(e.target.value))}
                min={0.0001}
                max={0.01}
                step={0.0001}
              />
            </div>
            <div>
              <Label htmlFor="vessel_density">Vessel Density (vessels/100µm²)</Label>
              <Input
                id="vessel_density"
                type="number"
                value={settings.vessel_density}
                onChange={(e) => updateSetting("vessel_density", parseFloat(e.target.value))}
                min={0.001}
                max={0.1}
                step={0.001}
              />
            </div>
          </CardContent>
          </CollapsibleContent>
        </Card>
        </Collapsible>

        <Separator />

        {/* Run Button */}
        <Button
          onClick={onRunSimulation}
          disabled={isLoading}
          className="w-full bg-gradient-to-r from-pink-500 to-purple-500 hover:from-pink-600 hover:to-purple-600"
          size="lg"
        >
          {isLoading ? "🧠 Simulating..." : "🚀 Run Simulation"}
        </Button>

        <p className="text-xs text-center text-muted-foreground">
          PhysiCell-inspired glioblastoma treatment simulation
        </p>
      </div>
    </aside>
  );
}

