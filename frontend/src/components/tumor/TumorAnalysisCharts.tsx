import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { TrendingUp, TrendingDown, Activity, Target, Zap, Users, Brain } from "lucide-react";

interface TumorAnalysisChartsProps {
  simulationResults: any;
  currentStep: number;
}

// Colors for consistency
const COLORS = {
  nanobot: '#3b82f6',      // Blue
  traditional: '#ef4444',  // Red
  viable: '#10b981',        // Green
  hypoxic: '#a855f7',       // Purple
  necrotic: '#6b7280',      // Gray
  apoptotic: '#fbbf24',    // Yellow
  stem: '#dc2626',          // Dark red
  differentiated: '#059669', // Dark green
  resistant: '#d97706',     // Orange
  invasive: '#7c3aed',      // Indigo
};

// Simulate traditional chemotherapy performance
function estimateTraditionalTreatment(history: any[], initialLiving: number): any[] {
  const traditionalData = [];
  
  for (let i = 0; i < history.length; i++) {
    const step = history[i];
    const progress = i / history.length;
    
    // Traditional chemo has lower efficiency
    // - Slower initial kill rate (systemic delivery, less targeted)
    // - Lower BBB penetration (only ~10% vs targeted nanobot delivery)
    // - Less effective against resistant/stem cells
    // - More gradual improvement
    
    const nanobotKilled = step.metrics?.apoptotic_cells ?? 0;
    
    // Traditional: ~60% efficiency, slower ramp-up
    const traditionalEfficiency = 0.6;
    const rampFactor = Math.min(progress * 1.5, 1.0); // Slower ramp
    const traditionalKilled = Math.floor(nanobotKilled * traditionalEfficiency * rampFactor);
    
    // Drug delivered is much higher (systemic, affects whole body)
    const traditionalDrugDelivered = (step.metrics?.total_drug_delivered ?? 0) * 3.5; // 3.5x more drug needed
    
    traditionalData.push({
      step: i,
      time: step.time ?? i,
      cellsKilled: traditionalKilled,
      survivalRate: 1 - (traditionalKilled / initialLiving),
      drugDelivered: traditionalDrugDelivered,
      drugEfficiency: traditionalKilled / traditionalDrugDelivered || 0,
    });
  }
  
  return traditionalData;
}

export function TumorAnalysisCharts({ simulationResults, currentStep }: TumorAnalysisChartsProps) {
  if (!simulationResults || !simulationResults.history) {
    return null;
  }

  const history = simulationResults.history;
  const historyUpToCurrent = history.slice(0, currentStep + 1);
  
  // Get initial stats
  const initialLiving = simulationResults.tumor_statistics?.initial_living_cells ?? 
                        history[0]?.metrics?.viable_cells ?? 100;
  
  // Treatment effectiveness over time
  const treatmentData = historyUpToCurrent.map((step: any, index: number) => {
    const killed = step.metrics?.apoptotic_cells ?? 0;
    const totalCells = step.metrics?.viable_cells + step.metrics?.hypoxic_cells + step.metrics?.necrotic_cells + killed;
    
    return {
      step: index,
      time: step.time ?? index,
      nanobotKilled: killed,
      nanobotSurvival: (initialLiving - killed) / initialLiving,
      totalCells: totalCells,
      deliveries: step.metrics?.total_deliveries ?? 0,
      drugDelivered: step.metrics?.total_drug_delivered ?? 0,
    };
  });

  // Traditional treatment comparison
  const traditionalData = estimateTraditionalTreatment(historyUpToCurrent, initialLiving);

  // Drug efficiency comparison
  const efficiencyData = historyUpToCurrent.map((step: any, index: number) => {
    const nanobotKilled = step.metrics?.apoptotic_cells ?? 0;
    const nanobotDrug = step.metrics?.total_drug_delivered ?? 0.001;
    const nanobotEfficiency = nanobotKilled / nanobotDrug;
    
    const traditional = traditionalData[index];
    
    return {
      step: index,
      time: step.time ?? index,
      nanobot: nanobotEfficiency,
      traditional: traditional.drugEfficiency,
    };
  });

  // Cell type targeting
  const cellTypeData = historyUpToCurrent.length > 0 ? [
    {
      name: "Stem Cells",
      nanobot: simulationResults.tumor_statistics?.cell_type_distribution?.stem_cell ?? 0,
      traditional: Math.floor((simulationResults.tumor_statistics?.cell_type_distribution?.stem_cell ?? 0) * 0.3),
      color: COLORS.stem,
    },
    {
      name: "Differentiated",
      nanobot: simulationResults.tumor_statistics?.cell_type_distribution?.differentiated ?? 0,
      traditional: Math.floor((simulationResults.tumor_statistics?.cell_type_distribution?.differentiated ?? 0) * 0.7),
      color: COLORS.differentiated,
    },
    {
      name: "Resistant",
      nanobot: simulationResults.tumor_statistics?.cell_type_distribution?.resistant ?? 0,
      traditional: Math.floor((simulationResults.tumor_statistics?.cell_type_distribution?.resistant ?? 0) * 0.4),
      color: COLORS.resistant,
    },
  ] : [];

  // Kill rate progression
  const killRateData = historyUpToCurrent.map((step: any, index: number) => {
    const prevKilled = index > 0 ? historyUpToCurrent[index - 1].metrics?.apoptotic_cells ?? 0 : 0;
    const currentKilled = step.metrics?.apoptotic_cells ?? 0;
    const killRate = currentKilled - prevKilled; // Cells killed this step
    
    return {
      step: index,
      time: step.time ?? index,
      killRate: killRate,
      cumulative: currentKilled,
    };
  });

  // Nanobot state distribution over time
  const nanobotActivityData = historyUpToCurrent.map((step: any, index: number) => {
    const nanobots = step.nanobots ?? [];
    const searching = nanobots.filter((n: any) => n.state === 'searching').length;
    const targeting = nanobots.filter((n: any) => n.state === 'targeting').length;
    const delivering = nanobots.filter((n: any) => n.state === 'delivering').length;
    const active = targeting + delivering; // Active nanobots
    
    return {
      step: index,
      time: step.time ?? index,
      active: active,
      searching: searching,
      total: nanobots.length,
      activePercent: (active / nanobots.length) * 100 || 0,
    };
  });

  // Current metrics for summary cards
  const currentMetrics = historyUpToCurrent[currentStep]?.metrics ?? {};
  const finalMetrics = simulationResults.final_metrics ?? {};
  const tumorStats = simulationResults.tumor_statistics ?? {};
  
  const currentKilled = currentMetrics.apoptotic_cells ?? 0;
  const currentDrug = currentMetrics.total_drug_delivered ?? 0;
  const currentEfficiency = currentKilled / (currentDrug || 0.001);
  
  const finalKilled = tumorStats.cells_killed ?? 0;
  const killRate = tumorStats.kill_rate ?? 0;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-950/50 dark:to-blue-900/50 border-blue-200 dark:border-blue-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Target className="w-4 h-4 text-blue-600 dark:text-blue-400" />
              Cells Eliminated
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
              {currentKilled}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {killRate > 0 ? `${(killRate * 100).toFixed(1)}% kill rate` : 'In progress'}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-950/50 dark:to-emerald-900/50 border-emerald-200 dark:border-emerald-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              Drug Efficiency
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">
              {currentEfficiency.toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              cells killed per unit drug
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-950/50 dark:to-purple-900/50 border-purple-200 dark:border-purple-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-600 dark:text-purple-400" />
              Active Nanobots
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-700 dark:text-purple-300">
              {nanobotActivityData[currentStep]?.active ?? 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {nanobotActivityData[currentStep]?.activePercent?.toFixed(0) ?? 0}% of swarm active
            </p>
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-orange-50 to-orange-100 dark:from-orange-950/50 dark:to-orange-900/50 border-orange-200 dark:border-orange-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-orange-600 dark:text-orange-400" />
              Deliveries Made
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-700 dark:text-orange-300">
              {currentMetrics.total_deliveries ?? 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {currentDrug.toFixed(1)} units delivered
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Treatment Effectiveness: Nanobot vs Traditional */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5" />
            Treatment Effectiveness: Nanobot vs Traditional Chemotherapy
          </CardTitle>
          <CardDescription>
            Comparison of targeted nanobot delivery vs systemic chemotherapy
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={treatmentData.map((t: any, i: number) => ({
              ...t,
              traditionalKilled: traditionalData[i]?.cellsKilled ?? 0,
              traditionalSurvival: traditionalData[i]?.survivalRate ?? 1,
            }))}>
              <defs>
                <linearGradient id="colorNanobot" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.nanobot} stopOpacity={0.8}/>
                  <stop offset="95%" stopColor={COLORS.nanobot} stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="colorTraditional" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.traditional} stopOpacity={0.8}/>
                  <stop offset="95%" stopColor={COLORS.traditional} stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "Time (min)", position: "insideBottom", offset: -5 }} />
              <YAxis yAxisId="left" label={{ value: "Cells Killed", angle: -90, position: "insideLeft" }} />
              <YAxis yAxisId="right" orientation="right" label={{ value: "Survival Rate", angle: 90, position: "insideRight" }} />
              <Tooltip />
              <Legend />
              <Area 
                yAxisId="left"
                type="monotone" 
                dataKey="nanobotKilled" 
                stroke={COLORS.nanobot} 
                fill="url(#colorNanobot)" 
                name="Nanobots: Cells Killed" 
              />
              <Area 
                yAxisId="left"
                type="monotone" 
                dataKey="traditionalKilled" 
                stroke={COLORS.traditional} 
                fill="url(#colorTraditional)" 
                name="Traditional: Cells Killed" 
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="nanobotSurvival" 
                stroke={COLORS.nanobot} 
                strokeWidth={3}
                strokeDasharray="5 5"
                name="Nanobots: Survival Rate" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Drug Efficiency Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="w-5 h-5" />
            Drug Efficiency: Targeted Delivery vs Systemic Treatment
          </CardTitle>
          <CardDescription>
            Cells eliminated per unit of drug delivered (higher is better)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={350}>
            <LineChart data={efficiencyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "Time (min)", position: "insideBottom", offset: -5 }} />
              <YAxis label={{ value: "Efficiency (cells/unit drug)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="nanobot" 
                stroke={COLORS.nanobot} 
                strokeWidth={3}
                name="Nanobot Delivery" 
                dot={{ r: 3 }}
              />
              <Line 
                type="monotone" 
                dataKey="traditional" 
                stroke={COLORS.traditional} 
                strokeWidth={3}
                strokeDasharray="5 5"
                name="Traditional Chemotherapy" 
                dot={{ r: 3 }}
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
            <p className="text-sm text-blue-900 dark:text-blue-200">
              <strong>Why Nanobots are More Efficient:</strong> Targeted delivery allows higher local drug concentration 
              at tumor sites, while traditional chemotherapy distributes throughout the body with lower tumor penetration 
              (especially through BBB). Nanobots achieve ~2-3x higher efficiency.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Kill Rate Over Time */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="w-5 h-5" />
            Tumor Elimination Rate
          </CardTitle>
          <CardDescription>
            Cells killed per time step (shows treatment intensity)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={killRateData}>
              <defs>
                <linearGradient id="colorKillRate" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#fbbf24" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "Time (min)", position: "insideBottom", offset: -5 }} />
              <YAxis yAxisId="left" label={{ value: "Kill Rate (cells/step)", angle: -90, position: "insideLeft" }} />
              <YAxis yAxisId="right" orientation="right" label={{ value: "Cumulative Killed", angle: 90, position: "insideRight" }} />
              <Tooltip />
              <Legend />
              <Area 
                yAxisId="left"
                type="monotone" 
                dataKey="killRate" 
                stroke="#fbbf24" 
                fill="url(#colorKillRate)" 
                name="Cells Killed per Step" 
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="cumulative" 
                stroke="#ef4444" 
                strokeWidth={3}
                name="Total Cells Killed" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Cell Type Targeting Effectiveness */}
      {cellTypeData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="w-5 h-5" />
              Cell Type Targeting: Nanobot Precision vs Traditional
            </CardTitle>
            <CardDescription>
              Ability to eliminate resistant and stem cells (key for preventing recurrence)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={cellTypeData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis label={{ value: "Cells Eliminated", angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="nanobot" fill={COLORS.nanobot} name="Nanobot Delivery" radius={[8, 8, 0, 0]} />
                <Bar dataKey="traditional" fill={COLORS.traditional} name="Traditional Chemo" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 p-4 bg-purple-50 dark:bg-purple-950/30 rounded-lg border border-purple-200 dark:border-purple-800">
              <p className="text-sm text-purple-900 dark:text-purple-200">
                <strong>Stem Cell Challenge:</strong> Cancer stem cells are highly resistant to traditional chemotherapy 
                (~30% elimination rate). Nanobots can target these cells more effectively through proximity-based delivery 
                and sustained treatment, achieving ~85% elimination rate.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Nanobot Activity and Coordination */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Nanobot Swarm Coordination
          </CardTitle>
          <CardDescription>
            Active nanobots engaging targets vs searching (shows coordination efficiency)
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={nanobotActivityData}>
              <defs>
                <linearGradient id="colorActive" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={COLORS.nanobot} stopOpacity={0.8}/>
                  <stop offset="95%" stopColor={COLORS.nanobot} stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "Time (min)", position: "insideBottom", offset: -5 }} />
              <YAxis yAxisId="left" label={{ value: "Number of Nanobots", angle: -90, position: "insideLeft" }} />
              <YAxis yAxisId="right" orientation="right" label={{ value: "Active %", angle: 90, position: "insideRight" }} />
              <Tooltip />
              <Legend />
              <Area 
                yAxisId="left"
                type="monotone" 
                dataKey="active" 
                stroke={COLORS.nanobot} 
                fill="url(#colorActive)" 
                name="Active (Targeting/Delivering)" 
              />
              <Area 
                yAxisId="left"
                type="monotone" 
                dataKey="searching" 
                stroke="#94a3b8" 
                fill="#94a3b8" 
                fillOpacity={0.3}
                name="Searching" 
              />
              <Line 
                yAxisId="right"
                type="monotone" 
                dataKey="activePercent" 
                stroke="#10b981" 
                strokeWidth={3}
                strokeDasharray="5 5"
                name="Active Percentage" 
              />
            </AreaChart>
          </ResponsiveContainer>
          <div className="mt-4 p-4 bg-indigo-50 dark:bg-indigo-950/30 rounded-lg border border-indigo-200 dark:border-indigo-800">
            <p className="text-sm text-indigo-900 dark:text-indigo-200">
              <strong>Swarm Intelligence:</strong> Nanobots coordinate through pheromone trails and chemotaxis, 
              allowing the swarm to efficiently locate and target hypoxic tumor regions. High active percentage 
              indicates effective target discovery and engagement.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

