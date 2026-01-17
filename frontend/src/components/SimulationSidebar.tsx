// src/components/simulation/SimulationSidebar.tsx

import React, { useState } from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight, SlidersHorizontal, Zap, Brain, Bug, Link2, Clock, Settings2 } from "lucide-react";

interface SimulationSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  settings: any;
  onSettingsChange: (settings: any) => void;
  onRunSimulation: () => void;
  isLoading: boolean;
}

export const SimulationSidebar: React.FC<SimulationSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  settings,
  onSettingsChange,
  onRunSimulation,
  isLoading
}) => {
  const [isHabitatOpen, setIsHabitatOpen] = useState(false);
  const [isAgentOpen, setIsAgentOpen] = useState(false);
  const [isQueenOpen, setIsQueenOpen] = useState(false);
  const [isPredatorOpen, setIsPredatorOpen] = useState(false);
  const [isBlockchainOpen, setIsBlockchainOpen] = useState(false);

  const handleChange = (key: string, value: any) => {
    onSettingsChange({ ...settings, [key]: value });
  };

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
    <div className="w-80 border-r border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex flex-col h-full">
      {/* Header */}
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

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">

        {/* Habitat Parameters */}
        <Collapsible open={isHabitatOpen} onOpenChange={setIsHabitatOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Bug className="h-4 w-4 text-primary" />
                Environment & Colony
              </span>
              {isHabitatOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-5 pt-2 px-1">
            <div className="space-y-3">
              <div className="flex justify-between">
                <Label className="text-xs font-medium text-muted-foreground">Width</Label>
                <span className="text-xs font-mono">{settings.grid_width}</span>
              </div>
              <Slider
                min={10}
                max={50}
                step={1}
                value={[settings.grid_width]}
                onValueChange={([v]) => handleChange("grid_width", v)}
                className="[&_.absolute]:bg-primary"
              />
            </div>

            <div className="space-y-3">
              <div className="flex justify-between">
                <Label className="text-xs font-medium text-muted-foreground">Height</Label>
                <span className="text-xs font-mono">{settings.grid_height}</span>
              </div>
              <Slider
                min={10}
                max={50}
                step={1}
                value={[settings.grid_height]}
                onValueChange={([v]) => handleChange("grid_height", v)}
              />
            </div>

            <div className="space-y-3">
              <div className="flex justify-between">
                <Label className="text-xs font-medium text-muted-foreground">Food Sources</Label>
                <span className="text-xs font-mono">{settings.n_food}</span>
              </div>
              <Slider
                min={5}
                max={100}
                step={5}
                value={[settings.n_food]}
                onValueChange={([v]) => handleChange("n_food", v)}
              />
            </div>

            <div className="space-y-3">
              <div className="flex justify-between">
                <Label className="text-xs font-medium text-muted-foreground">Agent Count</Label>
                <span className="text-xs font-mono">{settings.n_ants}</span>
              </div>
              <Slider
                min={1}
                max={20}
                step={1}
                value={[settings.n_ants]}
                onValueChange={([v]) => handleChange("n_ants", v)}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Agent Configuration */}
        <Collapsible open={isAgentOpen} onOpenChange={setIsAgentOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Brain className="h-4 w-4 text-primary" />
                Intelligence
              </span>
              {isAgentOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Agent Type</Label>
              <Select
                value={settings.agent_type}
                onValueChange={(value) => handleChange("agent_type", value)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="LLM-Powered">LLM-Powered</SelectItem>
                  <SelectItem value="Rule-Based">Rule-Based</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Model</Label>
              <Select
                value={settings.selected_model}
                onValueChange={(value) => handleChange("selected_model", value)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                  <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>
                  <SelectItem value="meta-llama/Llama-3.3-70B-Instruct">Llama 3.3 70B</SelectItem>
                  <SelectItem value="gemini-2.0-flash-exp">Gemini 2.0 Flash</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-xs font-medium text-muted-foreground">Prompt Style</Label>
              <Select
                value={settings.prompt_style}
                onValueChange={(value) => handleChange("prompt_style", value)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Adaptive">Adaptive</SelectItem>
                  <SelectItem value="Structured">Structured</SelectItem>
                  <SelectItem value="Autonomous">Autonomous</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Advanced Settings (Queen, Predators, Blockchain) */}
        <Collapsible open={isQueenOpen} onOpenChange={setIsQueenOpen} className="space-y-2">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto hover:bg-transparent">
              <span className="text-sm font-semibold flex items-center gap-2">
                <Zap className="h-4 w-4 text-primary" />
                Advanced Logic
              </span>
              {isQueenOpen ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
            </Button>
          </CollapsibleTrigger>
          
          <CollapsibleContent className="space-y-4 pt-2 px-1">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-medium text-muted-foreground">Queen Agent</Label>
              <Switch
                checked={settings.use_queen}
                onCheckedChange={(checked) => handleChange("use_queen", checked)}
              />
            </div>
              <div className="flex items-center justify-between">
              <Label className="text-xs font-medium text-muted-foreground">Predators</Label>
              <Switch
                checked={settings.enable_predators}
                onCheckedChange={(checked) => handleChange("enable_predators", checked)}
              />
            </div>
             <div className="flex items-center justify-between">
              <Label className="text-xs font-medium text-muted-foreground">Blockchain Logs</Label>
              <Switch
                checked={settings.blockchain_enabled}
                onCheckedChange={(checked) => handleChange("blockchain_enabled", checked)} // Assuming this field exists or needs to be added to state
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Simulation Length */}
        <div className="space-y-3 pt-4 border-t border-border">
          <div className="flex justify-between">
            <Label className="text-xs font-medium text-muted-foreground flex items-center gap-2">
              <Clock className="h-3 w-3" />
              Max Steps
          </Label>
            <span className="text-xs font-mono">{settings.max_steps}</span>
          </div>
          <Slider
            min={10}
            max={1000}
            step={10}
            value={[settings.max_steps]}
            onValueChange={([v]) => handleChange("max_steps", v)}
          />
        </div>
      </div>

      {/* Run Button */}
      <div className="p-4 border-t border-border bg-muted/20">
        <Button
          onClick={onRunSimulation}
          disabled={isLoading}
          className="w-full shadow-sm transition-all active:scale-95"
          size="lg"
        >
          {isLoading ? "Initializing..." : "Start Simulation"}
        </Button>
      </div>
    </div>
  );
};
