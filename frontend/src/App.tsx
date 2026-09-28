import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import SimulationComparison from "./pages/SimulationComparison";
import TumorSimulation from "./pages/TumorSimulation";
import TumorHunt from "./pages/TumorHunt";
import ExperimentLab from "./pages/ExperimentLab";
import ResearchWorkbench from "./pages/ResearchWorkbench";
import NotFound from "./pages/NotFound";
import { PreviewModeBanner } from "./components/PreviewModeBanner";
import { ThemeProvider } from "./design/theme";
import { lazy, Suspense } from "react";

const DesignSystem = import.meta.env.DEV ? lazy(() => import("./pages/DesignSystem")) : null;

const queryClient = new QueryClient();

const App = () => (
  <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <PreviewModeBanner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/comparison" element={<SimulationComparison />} />
            <Route path="/tumor" element={<TumorSimulation />} />
            <Route path="/tumor-hunt" element={<TumorHunt />} />
            <Route path="/experiments" element={<ExperimentLab />} />
            <Route path="/experiments/:id" element={<ExperimentLab />} />
            <Route path="/research" element={<ResearchWorkbench />} />
            <Route path="/research/:id" element={<ResearchWorkbench />} />
            {DesignSystem && <Route path="/design" element={<Suspense fallback={null}><DesignSystem /></Suspense>} />}
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
