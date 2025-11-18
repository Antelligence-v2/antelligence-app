import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Brain, Network, Activity, ChevronDown } from 'lucide-react';
import { SwarmBackground } from './SwarmBackground';

interface IntroPageProps {
  onEnter: () => void;
}

export const IntroPage: React.FC<IntroPageProps> = ({ onEnter }) => {
  const [isVisible, setIsVisible] = useState(true);
  const navigate = useNavigate();

  const handleEnter = () => {
    setIsVisible(false);
    setTimeout(() => {
      onEnter();
    }, 500);
  };

  const handleTumorSimulation = () => {
    navigate('/tumor');
  };

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'Enter') {
        handleEnter();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  if (!isVisible) {
    return (
      <div className="fixed inset-0 bg-background z-50 flex items-center justify-center transition-opacity duration-500 opacity-0">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto"></div>
          <div className="text-sm font-medium tracking-widest uppercase text-muted-foreground">Initializing Environment</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen text-foreground selection:bg-primary selection:text-primary-foreground relative">
      
      {/* Hero Section */}
      <div className="relative min-h-screen flex flex-col items-center justify-center p-6 overflow-hidden z-0">
        
        {/* Swarm Background - Positioned Absolutely */}
        <div className="absolute inset-0 -z-10">
            <SwarmBackground />
        </div>
        
        {/* Content Container */}
        <div className="max-w-4xl mx-auto text-center space-y-12 z-10 pointer-events-none">
          <div className="space-y-6 animate-fade-in pointer-events-auto">
            <h1 className="text-6xl md:text-8xl font-black tracking-tighter leading-tight drop-shadow-[0_0_15px_rgba(0,242,255,0.3)] text-white">
              Antelligence
            </h1>
            <p className="text-xl md:text-2xl text-gray-300 max-w-2xl mx-auto font-light leading-relaxed drop-shadow-md">
              Emergent swarm intelligence powered by Large Language Models.
              <br className="hidden md:block" />
              Simulating complex adaptive systems in real-time.
            </p>
          </div>

          <div className="flex flex-col md:flex-row gap-6 justify-center items-center w-full max-w-md mx-auto animate-fade-in delay-200 pointer-events-auto">
            <Button 
              onClick={handleEnter}
              size="lg"
              className="w-full h-14 text-base font-medium rounded-full transition-transform hover:scale-105 active:scale-95 shadow-[0_0_20px_rgba(0,242,255,0.2)] bg-cyan-500 hover:bg-cyan-400 text-black border-none"
            >
              Enter Colony Simulation
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
            <Button 
              onClick={handleTumorSimulation}
              size="lg"
              variant="outline"
              className="w-full h-14 text-base font-medium rounded-full hover:bg-white/10 border-white/20 text-white backdrop-blur-sm"
            >
              Medical Nanobots
            </Button>
          </div>
        </div>

        <div className="absolute bottom-12 left-1/2 -translate-x-1/2 animate-bounce text-cyan-400/70">
          <ChevronDown className="w-6 h-6" />
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-background/95 backdrop-blur-lg py-24 border-t border-white/10 relative z-10">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-3 gap-12">
            <div className="space-y-4">
              <div className="w-12 h-12 bg-cyan-500/10 rounded-2xl flex items-center justify-center text-cyan-400 mb-6">
                <Network className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold tracking-tight">Decentralized Control</h3>
              <p className="text-muted-foreground leading-relaxed">
                No central coordinator. Agents operate autonomously based on local information and LLM-driven decision making logic.
              </p>
            </div>
            
            <div className="space-y-4">
              <div className="w-12 h-12 bg-cyan-500/10 rounded-2xl flex items-center justify-center text-cyan-400 mb-6">
                <Brain className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold tracking-tight">Cognitive Agents</h3>
              <p className="text-muted-foreground leading-relaxed">
                Each agent is powered by advanced language models, allowing for complex reasoning beyond simple heuristic rule sets.
              </p>
            </div>

            <div className="space-y-4">
              <div className="w-12 h-12 bg-cyan-500/10 rounded-2xl flex items-center justify-center text-cyan-400 mb-6">
                <Activity className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold tracking-tight">Emergent Behavior</h3>
              <p className="text-muted-foreground leading-relaxed">
                Observe how complex patterns and efficient solutions naturally emerge from the interactions of simple individual agents.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Deep Dive Grid */}
      <div className="bg-background py-24 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
            <div className="grid md:grid-cols-2 gap-8">
            <Card className="group cursor-pointer border border-white/10 shadow-sm hover:shadow-cyan-500/10 transition-all duration-300 bg-card/50 overflow-hidden">
                <div className="h-1 bg-gradient-to-r from-cyan-500 to-blue-500 w-full origin-left transform transition-transform duration-500 scale-x-0 group-hover:scale-x-100"></div>
                <CardHeader>
                <CardTitle className="text-2xl mb-2">Colony Simulation</CardTitle>
                <p className="text-muted-foreground">Foraging optimization & resource management</p>
                </CardHeader>
                <CardContent className="space-y-4 text-sm text-muted-foreground">
                <p>
                    Watch digital ants use pheromone trails and AI decision-making to efficiently collect food. 
                    Features blockchain logging for immutable history of agent actions.
                </p>
                <ul className="space-y-2 mt-4 pt-4 border-t border-white/5">
                    <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-500"></span>
                    LLM-powered decision making
                    </li>
                    <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-500"></span>
                    Pheromone communication grids
                    </li>
                </ul>
                </CardContent>
            </Card>

            <Card className="group cursor-pointer border border-white/10 shadow-sm hover:shadow-rose-500/10 transition-all duration-300 bg-card/50 overflow-hidden">
                <div className="h-1 bg-gradient-to-r from-rose-500 to-purple-500 w-full origin-left transform transition-transform duration-500 scale-x-0 group-hover:scale-x-100"></div>
                <CardHeader>
                <CardTitle className="text-2xl mb-2">Tumor Nanobots</CardTitle>
                <p className="text-muted-foreground">Medical targeting & drug delivery</p>
                </CardHeader>
                <CardContent className="space-y-4 text-sm text-muted-foreground">
                <p>
                    Explore how nanobots navigate tumor microenvironments. Applies swarm principles to 
                    targeted drug therapy and hypoxia detection.
                </p>
                <ul className="space-y-2 mt-4 pt-4 border-t border-white/5">
                    <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                    Gradient descent navigation
                    </li>
                    <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
                    Biological signal processing
                    </li>
                </ul>
                </CardContent>
            </Card>
            </div>
        </div>
      </div>
    </div>
  );
};
