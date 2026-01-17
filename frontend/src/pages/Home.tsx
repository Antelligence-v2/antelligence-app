import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Microscope, Bug, ArrowRight } from "lucide-react";

const HomePage = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="max-w-4xl w-full space-y-8">
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold tracking-tight">Antelligence Simulation Platform</h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Advanced bio-inspired swarm intelligence simulations powered by Large Language Models.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 mt-8">
          <Card className="hover:border-primary/50 transition-all cursor-pointer" onClick={() => navigate('/ant-colony')}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bug className="w-6 h-6 text-primary" />
                Ant Colony Simulation
              </CardTitle>
              <CardDescription>
                Simulate foraging behavior with LLM-powered ants, pheromone trails, and predators.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-40 bg-muted/20 rounded-lg mb-4 flex items-center justify-center">
                <Bug className="w-16 h-16 text-muted-foreground/20" />
              </div>
              <Button className="w-full group">
                Launch Simulation 
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
            </CardContent>
          </Card>

          <Card className="hover:border-primary/50 transition-all cursor-pointer" onClick={() => navigate('/tumor')}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Microscope className="w-6 h-6 text-primary" />
                Tumor Nanobot Simulation
              </CardTitle>
              <CardDescription>
                Advanced medical nanobot swarm for targeted drug delivery in glioblastoma tumors.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="h-40 bg-muted/20 rounded-lg mb-4 flex items-center justify-center">
                <Microscope className="w-16 h-16 text-muted-foreground/20" />
              </div>
              <Button className="w-full group">
                Launch Simulation
                <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default HomePage;

