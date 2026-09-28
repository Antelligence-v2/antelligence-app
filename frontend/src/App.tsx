import { lazy } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "./design/theme";
import { AppShell } from "./shell/AppShell";

// Every page is its own chunk, so the shell paints before page code loads.
const Home = lazy(() => import("./pages/Home"));
const ResearchWorkbench = lazy(() => import("./pages/ResearchWorkbench"));
const NotFound = lazy(() => import("./pages/NotFound"));
// Legacy pages keep their original URLs; they link to each other by path.
const AntColony = lazy(() => import("./pages/Index"));
const SimulationComparison = lazy(() => import("./pages/SimulationComparison"));
const TumorSimulation = lazy(() => import("./pages/TumorSimulation"));
const TumorHunt = lazy(() => import("./pages/TumorHunt"));
const ExperimentLab = lazy(() => import("./pages/ExperimentLab"));
const DesignSystem = import.meta.env.DEV ? lazy(() => import("./pages/DesignSystem")) : null;

const queryClient = new QueryClient();

const App = () => (
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/" element={<Home />} />
              <Route path="/research" element={<ResearchWorkbench />} />
              <Route path="/research/:id" element={<ResearchWorkbench />} />
              <Route path="/ants" element={<AntColony />} />
              <Route path="/comparison" element={<SimulationComparison />} />
              <Route path="/tumor" element={<TumorSimulation />} />
              <Route path="/tumor-hunt" element={<TumorHunt />} />
              <Route path="/experiments" element={<ExperimentLab />} />
              <Route path="/experiments/:id" element={<ExperimentLab />} />
              {DesignSystem && <Route path="/design" element={<DesignSystem />} />}
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
