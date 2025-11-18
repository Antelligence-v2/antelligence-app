import React from 'react';

interface SimulationLoadingProps {
  isVisible: boolean;
  progress?: number;
  message?: string;
  currentStep?: number;
  totalSteps?: number;
}

export const SimulationLoading: React.FC<SimulationLoadingProps> = ({
  isVisible,
  progress = 0,
  currentStep = 0,
  totalSteps = 0
}) => {
  if (!isVisible) return null;

  const stepPercentage = totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0;
  
  const getStepMessage = () => {
    if (stepPercentage < 20) return "Booting Agent Environment...";
    if (stepPercentage < 40) return "Initializing Neural Networks...";
    if (stepPercentage < 60) return "Generating Resource Grid...";
    if (stepPercentage < 80) return "Establishing Blockchain Ledger...";
    if (stepPercentage < 95) return "Executing Simulation Steps...";
    return "Finalizing Analysis...";
  };

  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-md z-50 flex items-center justify-center animate-in fade-in duration-200">
      <div className="w-full max-w-md p-6 bg-card rounded-xl shadow-2xl border border-border">
        <div className="space-y-8 text-center">
          
          {/* Modern Minimalist Loader */}
          <div className="relative w-16 h-16 mx-auto">
             <div className="absolute inset-0 border-4 border-muted rounded-full"></div>
             <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
             <div className="absolute inset-0 flex items-center justify-center text-xl animate-pulse">
               🐜
             </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-lg font-semibold tracking-tight text-foreground">
              {getStepMessage()}
            </h3>
            <p className="text-xs font-mono text-muted-foreground">
              {totalSteps > 0 ? `Step ${currentStep} / ${totalSteps}` : `${progress.toFixed(0)}%`}
            </p>
          </div>

          <div className="space-y-2">
             <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
               <div 
                  className="h-full bg-primary transition-all duration-300 ease-out rounded-full"
                  style={{ width: `${Math.max(5, progress)}%` }}
               />
             </div>
             <div className="flex justify-between text-[10px] text-muted-foreground uppercase tracking-widest">
                <span>System Init</span>
                <span>Simulation</span>
                <span>Analysis</span>
             </div>
          </div>

        </div>
      </div>
    </div>
  );
};
