import { Button } from "@/components/ui/button";
import { Play, Pause, SkipForward, SkipBack, RotateCcw, ChevronsLeft, ChevronsRight } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface TumorSimulationControlsProps {
  isRunning: boolean;
  onStart: () => void;
  onPause: () => void;
  onStep: () => void;
  onStepBackward: () => void;
  onReset: () => void;
  onGoToStart: () => void;
  onGoToEnd: () => void;
  metrics: {
    currentStep: number;
    totalSteps: number;
    time: number;
    cellsKilled: number;
    deliveries: number;
    drugDelivered: number;
  };
  isSimulationLoaded: boolean;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
  currentStep: number;
  totalSteps: number;
}

export function TumorSimulationControls({
  isRunning,
  onStart,
  onPause,
  onStep,
  onStepBackward,
  onReset,
  onGoToStart,
  onGoToEnd,
  metrics,
  isSimulationLoaded,
  playbackSpeed,
  onSpeedChange,
  currentStep,
  totalSteps,
}: TumorSimulationControlsProps) {
  const speedOptions = [
    { label: "0.5x", value: 1000 },
    { label: "1x", value: 500 },
    { label: "2x", value: 250 },
    { label: "4x", value: 125 },
  ];

  return (
    <div className="flex items-center justify-between gap-4">
      {/* Playback Controls */}
      <div className="flex items-center gap-1 bg-muted/30 p-1 rounded-lg border border-border/50">
        <div className="flex gap-0.5">
          <Button onClick={onGoToStart} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button onClick={onStepBackward} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
            <SkipBack className="h-4 w-4" />
          </Button>
        </div>

        <div className="w-px h-4 bg-border mx-1" />

        <Button
          onClick={isRunning ? onPause : onStart}
          disabled={!isSimulationLoaded}
          size="sm"
          className="h-8 px-3 font-medium min-w-[80px]"
        >
          {isRunning ? (
            <>
              <Pause className="w-3.5 h-3.5 mr-1.5 fill-current" /> Pause
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5 mr-1.5 fill-current" /> Play
            </>
          )}
        </Button>

        <div className="w-px h-4 bg-border mx-1" />

        <div className="flex gap-0.5">
          <Button onClick={onStep} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
            <SkipForward className="h-4 w-4" />
          </Button>
          <Button onClick={onGoToEnd} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8">
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="w-px h-4 bg-border mx-1" />

        <Button onClick={onReset} variant="ghost" disabled={!isSimulationLoaded} size="icon" className="h-8 w-8 text-destructive hover:text-destructive">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      <div className="flex items-center gap-4">
        {/* Metrics Display */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <div className="flex flex-col items-center">
            <span className="text-[10px] uppercase tracking-wider opacity-70">Killed</span>
            <span className="font-mono font-medium text-foreground">{metrics.cellsKilled}</span>
          </div>
          <Separator orientation="vertical" className="h-8" />
          <div className="flex flex-col items-center">
            <span className="text-[10px] uppercase tracking-wider opacity-70">Deliveries</span>
            <span className="font-mono font-medium text-foreground">{metrics.deliveries}</span>
          </div>
          <Separator orientation="vertical" className="h-8" />
          <div className="flex flex-col items-center">
            <span className="text-[10px] uppercase tracking-wider opacity-70">Drug Units</span>
            <span className="font-mono font-medium text-foreground">{metrics.drugDelivered.toFixed(0)}</span>
          </div>
        </div>

        <Separator orientation="vertical" className="h-8" />

        {/* Speed Control */}
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
      </div>
    </div>
  );
}
