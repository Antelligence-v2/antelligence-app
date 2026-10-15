// src/components/simulation/SimulationSidebar.tsx

import React, { useState } from "react";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";

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
      <div className="w-16 bg-gradient-to-b from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-r border-amber-200 dark:border-amber-700 flex flex-col items-center py-4 shadow-lg">
        <Button
          onClick={onToggleCollapse}
          variant="ghost"
          size="icon"
          className="mb-4 hover:bg-amber-200 dark:hover:bg-amber-800 transition-all duration-200 hover:scale-110"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-80 bg-gradient-to-b from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 border-r border-amber-200 dark:border-amber-700 flex flex-col h-full shadow-xl">
      {/* Header */}
      <div className="p-4 border-b border-amber-200 dark:border-amber-700 bg-gradient-to-r from-amber-100/50 to-orange-100/50 dark:from-amber-800/20 dark:to-orange-800/20">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-amber-800 dark:text-amber-200 flex items-center gap-2">
            <span className="animate-pulse">🐜</span>
            Colony Settings
          </h2>
          <Button
            onClick={onToggleCollapse}
            variant="ghost"
            size="icon"
            className="hover:bg-amber-200 dark:hover:bg-amber-800 transition-all duration-200 hover:scale-110"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="mt-3">
          <Button
            onClick={onRunSimulation}
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white shadow-lg transition-all duration-300 hover:shadow-xl hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <>
                <span className="animate-spin mr-2">🐜</span>
                Running...
              </>
            ) : (
              <>
                <span className="animate-bounce mr-2">🚀</span>
                Run Simulation
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* Habitat Parameters */}
        <Collapsible open={isHabitatOpen} onOpenChange={setIsHabitatOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-800">
              <span className="text-base font-semibold">🌄 Habitat Parameters</span>
              {isHabitatOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            <div>
              <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                <span>🌾 Territory Width</span>
                <span className="text-amber-600 dark:text-amber-400">{settings.grid_width}</span>
              </Label>
              <Slider
                min={10}
                max={50}
                step={1}
                value={[settings.grid_width]}
                onValueChange={([v]) => handleChange("grid_width", v)}
                className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-600"
              />
            </div>

            <div>
              <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                <span>🌾 Territory Height</span>
                <span className="text-amber-600 dark:text-amber-400">{settings.grid_height}</span>
              </Label>
              <Slider
                min={10}
                max={50}
                step={1}
                value={[settings.grid_height]}
                onValueChange={([v]) => handleChange("grid_height", v)}
                className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-600"
              />
            </div>

            <div>
              <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                <span>🍯 Food Resources</span>
                <span className="text-amber-600 dark:text-amber-400">{settings.n_food}</span>
              </Label>
              <Slider
                min={5}
                max={100}
                step={5}
                value={[settings.n_food]}
                onValueChange={([v]) => handleChange("n_food", v)}
                className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-600"
              />
            </div>

            <div>
              <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                <span>🐜 Colony Size</span>
                <span className="text-amber-600 dark:text-amber-400">{settings.n_ants}</span>
              </Label>
              <Slider
                min={1}
                max={20}
                step={1}
                value={[settings.n_ants]}
                onValueChange={([v]) => handleChange("n_ants", v)}
                className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-600"
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Agent Configuration */}
        <Collapsible open={isAgentOpen} onOpenChange={setIsAgentOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-800">
              <span className="text-base font-semibold">🧠 Agent Configuration</span>
              {isAgentOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            <div>
              <Label className="text-sm text-amber-800 dark:text-amber-200">Agent Type</Label>
              <Select
                value={settings.agent_type}
                onValueChange={(value) => handleChange("agent_type", value)}
              >
                <SelectTrigger className="bg-amber-50 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-amber-50 dark:bg-amber-900 border-amber-300 dark:border-amber-700">
                  <SelectItem value="LLM-Powered" className="text-amber-800 dark:text-amber-200">🧠 LLM-Powered</SelectItem>
                  <SelectItem value="Rule-Based" className="text-amber-800 dark:text-amber-200">⚡ Rule-Based</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-sm text-amber-800 dark:text-amber-200">AI Model</Label>
              <Select
                value={settings.selected_model}
                onValueChange={(value) => handleChange("selected_model", value)}
              >
                <SelectTrigger className="bg-amber-50 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-amber-50 dark:bg-amber-900 border-amber-300 dark:border-amber-700 max-h-[400px]">
                  <SelectItem value="gpt-4o" className="text-amber-800 dark:text-amber-200">GPT-4o (OpenAI)</SelectItem>
                  <SelectItem value="gpt-4o-mini" className="text-amber-800 dark:text-amber-200">GPT-4o Mini (OpenAI)</SelectItem>
                  <SelectItem value="meta-llama/Llama-3.3-70B-Instruct" className="text-amber-800 dark:text-amber-200">Llama 3.3 70B (IO.NET)</SelectItem>
                  <SelectItem value="meta-llama/Llama-3.1-405B-Instruct" className="text-amber-800 dark:text-amber-200">Llama 3.1 405B (IO.NET)</SelectItem>
                  <SelectItem value="meta-llama/Llama-3.1-70B-Instruct" className="text-amber-800 dark:text-amber-200">Llama 3.1 70B (IO.NET)</SelectItem>
                  <SelectItem value="gemini-2.0-flash-exp" className="text-amber-800 dark:text-amber-200">Gemini 2.0 Flash (Google)</SelectItem>
                  <SelectItem value="gemini-exp-1206" className="text-amber-800 dark:text-amber-200">Gemini 2.0 Pro (Google)</SelectItem>
                  <SelectItem value="mistral-small-latest" className="text-amber-800 dark:text-amber-200">Mistral Small (Mistral AI)</SelectItem>
                  <SelectItem value="mistral-large-latest" className="text-amber-800 dark:text-amber-200">Mistral Large (Mistral AI)</SelectItem>
                  <SelectItem value="deepseek-chat" className="text-amber-800 dark:text-amber-200">DeepSeek Chat (IO.NET)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-sm text-amber-800 dark:text-amber-200">Prompt Style</Label>
              <Select
                value={settings.prompt_style}
                onValueChange={(value) => handleChange("prompt_style", value)}
              >
                <SelectTrigger className="bg-amber-50 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-amber-50 dark:bg-amber-900 border-amber-300 dark:border-amber-700">
                  <SelectItem value="Adaptive" className="text-amber-800 dark:text-amber-200">🔄 Adaptive</SelectItem>
                  <SelectItem value="Structured" className="text-amber-800 dark:text-amber-200">📋 Structured</SelectItem>
                  <SelectItem value="Autonomous" className="text-amber-800 dark:text-amber-200">🤖 Autonomous</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Queen Configuration */}
        <Collapsible open={isQueenOpen} onOpenChange={setIsQueenOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-800">
              <span className="text-base font-semibold">👸 Queen Configuration</span>
              {isQueenOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm text-amber-800 dark:text-amber-200">Enable Queen</Label>
              <Switch
                checked={settings.use_queen}
                onCheckedChange={(checked) => handleChange("use_queen", checked)}
                className="data-[state=checked]:bg-amber-600"
              />
            </div>

            {settings.use_queen && (
              <div className="flex items-center justify-between">
                <Label className="text-sm text-amber-800 dark:text-amber-200">LLM Queen</Label>
                <Switch
                  checked={settings.use_llm_queen}
                  onCheckedChange={(checked) => handleChange("use_llm_queen", checked)}
                  className="data-[state=checked]:bg-amber-600"
                />
              </div>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Predator Settings */}
        <Collapsible open={isPredatorOpen} onOpenChange={setIsPredatorOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-800">
              <span className="text-base font-semibold">🦅 Predator Settings</span>
              {isPredatorOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            <div className="flex items-center justify-between">
              <Label className="text-sm text-amber-800 dark:text-amber-200">Enable Predators</Label>
              <Switch
                checked={settings.enable_predators}
                onCheckedChange={(checked) => handleChange("enable_predators", checked)}
                className="data-[state=checked]:bg-amber-600"
              />
            </div>

            {settings.enable_predators && (
              <>
                <div>
                  <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                    <span>🦅 Number of Predators</span>
                    <span className="text-amber-600 dark:text-amber-400">{settings.n_predators}</span>
                  </Label>
                  <Slider
                    min={1}
                    max={10}
                    step={1}
                    value={[settings.n_predators]}
                    onValueChange={([v]) => handleChange("n_predators", v)}
                    className="bg-gradient-to-r from-red-500 via-red-400 to-red-600"
                  />
                </div>

                <div>
                  <Label className="text-sm text-amber-800 dark:text-amber-200">Predator Agent Type</Label>
                  <Select
                    value={settings.predator_type}
                    onValueChange={(value) => handleChange("predator_type", value)}
                  >
                    <SelectTrigger className="bg-amber-50 dark:bg-amber-900/30 border-amber-300 dark:border-amber-700">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-amber-50 dark:bg-amber-900 border-amber-300 dark:border-amber-700">
                      <SelectItem value="LLM-Powered" className="text-amber-800 dark:text-amber-200">🧠 LLM-Powered</SelectItem>
                      <SelectItem value="Rule-Based" className="text-amber-800 dark:text-amber-200">⚡ Rule-Based</SelectItem>
                      <SelectItem value="Hybrid" className="text-amber-800 dark:text-amber-200">🔄 Hybrid</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
                    <span>😰 Fear Pheromone Intensity</span>
                    <span className="text-amber-600 dark:text-amber-400">{settings.fear_deposit}</span>
                  </Label>
                  <Slider
                    min={1.0}
                    max={10.0}
                    step={0.5}
                    value={[settings.fear_deposit]}
                    onValueChange={([v]) => handleChange("fear_deposit", v)}
                    className="bg-gradient-to-r from-orange-500 via-orange-400 to-red-500"
                  />
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">How much fear pheromone predators leave behind</p>
                </div>

                <div className="p-3 bg-amber-100 dark:bg-amber-800/30 rounded-md border border-amber-300 dark:border-amber-700">
                  <p className="text-sm text-amber-800 dark:text-amber-200">
                    🦅 <strong>Predator Behavior:</strong><br/>
                    • Hunt nearby ants<br/>
                    • Leave fear pheromone trails<br/>
                    • Smart LLM decision making<br/>
                    • Force ants to prioritize survival
                  </p>
                </div>
              </>
            )}
          </CollapsibleContent>
        </Collapsible>

        {/* Blockchain Settings */}
        <Collapsible open={isBlockchainOpen} onOpenChange={setIsBlockchainOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" className="w-full justify-between p-0 h-auto text-amber-800 dark:text-amber-200 hover:bg-amber-100 dark:hover:bg-amber-800">
              <span className="text-base font-semibold">🔗 Blockchain Integration</span>
              {isBlockchainOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 mt-4">
            <div className="p-3 bg-amber-100 dark:bg-amber-800/30 rounded-md border border-amber-300 dark:border-amber-700">
              <p className="text-sm text-amber-800 dark:text-amber-200">
                🔗 <strong>Blockchain Features:</strong><br/>
                • Log food collection events<br/>
                • Record ant movements<br/>
                • Immutable transaction history<br/>
                • Smart contract integration
              </p>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Max Steps */}
        <div>
          <Label className="flex justify-between text-sm text-amber-800 dark:text-amber-200">
            <span>🕒 Max Steps</span>
            <span className="text-amber-600 dark:text-amber-400">{settings.max_steps}</span>
          </Label>
          <Slider
            min={10}
            max={1000}
            step={10}
            value={[settings.max_steps]}
            onValueChange={([v]) => handleChange("max_steps", v)}
            className="bg-gradient-to-r from-amber-500 via-orange-400 to-amber-600"
          />
        </div>
      </div>

    </div>
  );
};
