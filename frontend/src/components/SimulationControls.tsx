// src/components/simulation/SimulationControls.tsx

import { Pause, SkipForward, SkipBack, RotateCcw, HelpCircle, Repeat, ChevronsLeft, ChevronsRight, Repeat1, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import antLogo from "/ant-logo.jpeg";

interface SimulationControlsProps {
  isRunning: boolean;
  onStart: () => void;
  onPause: () => void;
  onStep: () => void;
  onStepBackward: () => void;
  onReset: () => void;
  onReplay: () => void;
  onGoToStart: () => void;
  onGoToEnd: () => void;
  onBackToIntro: () => void;
  metrics: any;
  isSimulationLoaded: boolean;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
  speedOptions: { label: string; value: number }[];
  isLooping: boolean;
  onLoopChange: (loop: boolean) => void;
  currentStep: number;
  totalSteps: number;
}

export const SimulationControls = ({
  isRunning,
  onStart,
  onPause,
  onStep,
  onStepBackward,
  onReset,
  onReplay,
  onGoToStart,
  onGoToEnd,
  onBackToIntro,
  metrics,
  isSimulationLoaded,
  playbackSpeed,
  onSpeedChange,
  speedOptions,
  isLooping,
  onLoopChange,
  currentStep,
  totalSteps,
}: SimulationControlsProps) => {

  return (
    <div className="w-full bg-background border-b border-border shadow-sm z-10">
      <div className="p-3 max-w-7xl mx-auto">
        {/* Header Row */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
             <div className="relative group">
                <img 
                  src={antLogo} 
                  alt="Antelligence Logo" 
                  className="w-9 h-9 object-contain rounded-md shadow-sm border border-border transition-all duration-300 group-hover:scale-105"
                />
              </div>
              <div className="flex flex-col">
                <h1 className="text-lg font-bold tracking-tight text-foreground">
                  Antelligence
                </h1>
                <p className="text-xs text-muted-foreground">Swarm Intelligence Lab</p>
              </div>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-6 w-6 rounded-full">
                    <HelpCircle className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="max-w-xs">
                  <div className="space-y-1 text-xs">
                    <div className="font-semibold">Keyboard Shortcuts:</div>
                    <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
                      <span className="font-mono bg-muted px-1 rounded">Space</span> <span>Play/Pause</span>
                      <span className="font-mono bg-muted px-1 rounded">←/→</span> <span>Step</span>
                      <span className="font-mono bg-muted px-1 rounded">Home/End</span> <span>Start/End</span>
                      <span className="font-mono bg-muted px-1 rounded">R</span> <span>Replay</span>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          
          {/* Controls */}
          <div className="flex items-center gap-1 bg-muted/30 p-1 rounded-lg border border-border/50">
            {!isRunning ? (
              <Button 
                onClick={onStart} 
                disabled={!isSimulationLoaded || isRunning} 
                size="sm"
                className="h-8 px-3 font-medium"
              >
                <Play className="h-3.5 w-3.5 mr-1.5 fill-current" />
                Run
              </Button>
            ) : (
              <Button onClick={onPause} disabled={!isRunning} variant="secondary" size="sm" className="h-8 px-3 font-medium">
                <Pause className="h-3.5 w-3.5 mr-1.5 fill-current" /> Pause
              </Button>
            )}
            
            <div className="w-px h-4 bg-border mx-1" />
            
             <div className="flex gap-0.5">
                <Button onClick={onStepBackward} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
                  <SkipBack className="h-4 w-4" />
                </Button>
                <Button onClick={onStep} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
                  <SkipForward className="h-4 w-4" />
                </Button>
             </div>

             <div className="w-px h-4 bg-border mx-1" />

             <div className="flex gap-0.5">
                <Button onClick={onGoToStart} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
                  <ChevronsLeft className="h-4 w-4" />
                </Button>
                <Button onClick={onGoToEnd} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
                  <ChevronsRight className="h-4 w-4" />
                </Button>
             </div>
             
            <div className="w-px h-4 bg-border mx-1" />

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button onClick={onReplay} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
                    <Repeat className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Replay</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button onClick={onReset} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Reset</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <div className="flex items-center gap-3 text-sm">
             <div className="flex items-center space-x-2">
              <Switch
                id="loop"
                checked={isLooping}
                onCheckedChange={onLoopChange}
                className="scale-75"
              />
              <Label htmlFor="loop" className="text-xs font-medium text-muted-foreground cursor-pointer">Loop</Label>
            </div>
            <Separator className="h-4" orientation="vertical" />
            <Select 
              value={playbackSpeed.toString()} 
              onValueChange={(value) => onSpeedChange(Number(value))}
            >
              <SelectTrigger className="w-[70px] h-8 text-xs bg-muted/30 border-border/50">
                <SelectValue placeholder="Speed" />
              </SelectTrigger>
              <SelectContent>
                {speedOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value.toString()} className="text-xs">
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={onBackToIntro} variant="outline" size="sm" className="h-8 text-xs ml-2">
               Back
            </Button>
          </div>
        </div>

        {/* Progress & Metrics Bar */}
        {isSimulationLoaded && totalSteps > 0 && (
          <div className="space-y-3">
             <div className="flex items-center gap-3">
                <div className="text-xs font-medium text-muted-foreground w-16 shrink-0">Progress</div>
                <div className="flex-1 relative">
                  <Progress value={(currentStep / (totalSteps - 1)) * 100} className="h-2" />
                </div>
                <div className="text-xs font-mono text-muted-foreground w-16 text-right shrink-0">
                  {currentStep + 1}/{totalSteps}
                </div>
             </div>

            <div className="grid grid-cols-6 gap-2">
               <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Food</span>
                 <span className="text-sm font-bold font-mono">{metrics.foodCollected}</span>
               </div>
               <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Agents</span>
                 <span className="text-sm font-bold font-mono">{metrics.activeAnts}</span>
               </div>
               <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Calls</span>
                 <span className="text-sm font-bold font-mono">{metrics.apiCalls}</span>
               </div>
               <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Queen</span>
                 <span className={`text-sm font-bold ${metrics.queenActive ? 'text-primary' : 'text-muted-foreground'}`}>
                    {metrics.queenActive ? "ON" : "OFF"}
                 </span>
               </div>
                <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Ledger</span>
                 <span className={`text-sm font-bold ${metrics.blockchainActive ? 'text-primary' : 'text-muted-foreground'}`}>
                    {metrics.blockchainActive ? "ON" : "OFF"}
                 </span>
               </div>
               <div className="bg-muted/30 rounded border border-border/50 px-3 py-1.5 flex flex-col items-center justify-center">
                 <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">Efficiency</span>
                 <span className="text-sm font-bold font-mono">
                    {metrics.efficiency ? `${(metrics.efficiency * 100).toFixed(1)}%` : "--"}
                 </span>
               </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
