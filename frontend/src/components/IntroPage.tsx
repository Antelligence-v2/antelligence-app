import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useNavigate } from 'react-router-dom';
import { Brain } from 'lucide-react';
import antFrontpageImage from '/ant-frontpage.jpg';

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

  // Handle keyboard enter
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
      <div className="fixed inset-0 bg-amber-900/60 backdrop-blur-sm z-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl animate-spin mb-4">🐜</div>
          <div className="text-lg text-amber-800 dark:text-amber-200">Loading simulation...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cover bg-center bg-no-repeat bg-fixed"
         style={{ backgroundImage: `url(${antFrontpageImage})` }}>
      {/* Hero Section */}
      <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
        <div className="text-center -mt-48">
          <h1 className="text-8xl font-black text-black mb-12 tracking-tight drop-shadow-2xl" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
          Antelligence
          </h1>
          <div className="flex flex-col gap-4 items-center">
            <Button 
              onClick={handleEnter}
              size="lg"
              className="w-80 h-14 text-lg font-semibold"
            >
              Ant Colony Simulation
            </Button>
            <Button 
              onClick={handleTumorSimulation}
              size="lg"
              variant="outline"
              className="w-80 h-14 text-lg font-semibold border-2 border-slate-300 hover:border-slate-400 bg-slate-100 text-slate-800 hover:bg-slate-200 hover:text-slate-800"
            >
              Tumor Nanobot Simulation
            </Button>
          </div>
          <p className="text-gray-800 mt-4 text-lg drop-shadow-md font-medium">
            Choose your simulation experience
          </p>
        </div>
      </div>

      {/* Scroll Indicator */}
      <div className="absolute bottom-8 left-1/2 transform -translate-x-1/2 z-20 text-center">
        <div className="flex flex-col items-center space-y-2">
          <p className="text-white font-semibold drop-shadow-lg">
            Scroll down for more information
          </p>
          <div className="animate-bounce">
            <svg 
              className="w-6 h-6 text-white drop-shadow-lg" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M19 14l-7 7m0 0l-7-7m7 7V3" 
              />
            </svg>
          </div>
        </div>
      </div>

      {/* Information Section */}
      <div className="relative z-10 bg-background">
        <div className="max-w-4xl mx-auto px-6 py-16">
          <Card className="shadow-lg">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl font-bold">Swarm Intelligence</CardTitle>
              <CardDescription className="text-lg mt-4">
                The power of collective behavior emerges from simple individual actions
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-8">
              
              {/* Core Concept */}
              <div className="text-center space-y-4">
                <p className="text-muted-foreground text-lg leading-relaxed">
                  Swarm intelligence demonstrates how complex, intelligent behavior can emerge from simple rules 
                  followed by many individual agents. No single ant knows the entire path to food, yet together 
                  they create efficient foraging networks through local interactions.
                </p>
              </div>

              {/* Two Projects */}
              <div className="grid md:grid-cols-2 gap-8">
                
                {/* Ant Colony Simulation */}
                <Card className="border-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      🐜 Ant Colony Simulation
                    </CardTitle>
                    <CardDescription>
                      AI-powered ants foraging for food
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      Watch digital ants use pheromone trails and AI decision-making to efficiently collect food. 
                      Each ant follows simple rules, but together they demonstrate emergent intelligence.
                    </p>
                    <ul className="text-sm space-y-1">
                      <li>• LLM-powered decision making</li>
                      <li>• Pheromone communication</li>
                      <li>• Blockchain transaction logging</li>
                    </ul>
                  </CardContent>
                </Card>

                {/* Tumor Nanobot Simulation */}
                <Card className="border-2">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      🧠 Tumor Nanobot Simulation
                    </CardTitle>
                    <CardDescription>
                      Medical nanobots targeting cancer cells
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      Explore how nanobots navigate tumor microenvironments to deliver targeted drug therapy. 
                      Similar swarm principles applied to medical treatment scenarios.
                    </p>
                    <ul className="text-sm space-y-1">
                      <li>• Hypoxic zone targeting</li>
                      <li>• Drug delivery optimization</li>
                      <li>• Biological signal processing</li>
                    </ul>
                  </CardContent>
                </Card>
              </div>

              {/* Common Principles */}
              <div className="text-center space-y-4">
                <h3 className="text-xl font-semibold">Common Principles</h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div className="p-4 bg-muted rounded-lg">
                    <div className="font-semibold mb-2">Decentralized Control</div>
                    <p className="text-muted-foreground">No central coordinator needed</p>
                  </div>
                  <div className="p-4 bg-muted rounded-lg">
                    <div className="font-semibold mb-2">Local Interactions</div>
                    <p className="text-muted-foreground">Agents respond to immediate environment</p>
                  </div>
                  <div className="p-4 bg-muted rounded-lg">
                    <div className="font-semibold mb-2">Emergent Behavior</div>
                    <p className="text-muted-foreground">Complex patterns from simple rules</p>
                  </div>
                </div>
              </div>

            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}; 