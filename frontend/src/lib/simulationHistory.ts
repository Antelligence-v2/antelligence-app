/**
 * Service for managing simulation history and caching
 */

import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export interface CachedSimulation {
  id: string;
  timestamp: string;
  agent_type: string;
  llm_model: string;
  simulation_type: "ant" | "tumor";
  summary: Record<string, any>;
}

export interface SimulationComparisonResult {
  simulation1: {
    id: string;
    agent_type: string;
    llm_model: string;
    metrics: Record<string, any>;
    summary: Record<string, any>;
  };
  simulation2: {
    id: string;
    agent_type: string;
    llm_model: string;
    metrics: Record<string, any>;
    summary: Record<string, any>;
  };
  differences: Record<string, {
    absolute: number;
    percent: number;
  }>;
}

/**
 * Cache a simulation result for later comparison
 */
export async function cacheSimulation(simulationData: {
  agent_type: string;
  llm_model: string;
  simulation_type: "ant" | "tumor";
  config: Record<string, any>;
  final_metrics: Record<string, any>;
  summary: Record<string, any>;
}): Promise<{ simulation_id: string; cached_at: string }> {
  try {
    const response = await axios.post(`${API_BASE_URL}/simulation/cache`, simulationData);
    return response.data;
  } catch (error) {
    console.error("Error caching simulation:", error);
    throw error;
  }
}

/**
 * Get all cached simulations, optionally filtered by type
 */
export async function getSimulationHistory(
  simulationType?: "ant" | "tumor"
): Promise<CachedSimulation[]> {
  try {
    const params = simulationType ? { simulation_type: simulationType } : {};
    const response = await axios.get(`${API_BASE_URL}/simulation/history`, { params });
    return response.data.simulations;
  } catch (error) {
    console.error("Error fetching simulation history:", error);
    throw error;
  }
}

/**
 * Compare two cached simulations
 */
export async function compareSimulations(
  id1: string,
  id2: string
): Promise<SimulationComparisonResult> {
  try {
    const response = await axios.get(`${API_BASE_URL}/simulation/compare/${id1}/${id2}`);
    return response.data;
  } catch (error) {
    console.error("Error comparing simulations:", error);
    throw error;
  }
}

/**
 * Get aggregated statistics from simulation history
 */
export async function getAggregatedStats(): Promise<{
  totalSimulations: number;
  averageCellsKilled: number;
  averageEfficiency: number;
  topPerformingModel: string;
}> {
  try {
    const history = await getSimulationHistory();
    
    if (history.length === 0) {
      return {
        totalSimulations: 0,
        averageCellsKilled: 0,
        averageEfficiency: 0,
        topPerformingModel: "N/A"
      };
    }

    const totalSimulations = history.length;
    const cellsKilled = history.reduce((sum, sim) => sum + (sim.summary.cells_killed || 0), 0);
    const averageCellsKilled = cellsKilled / totalSimulations;
    
    const efficiency = history.reduce((sum, sim) => sum + (sim.summary.efficiency || 0), 0);
    const averageEfficiency = efficiency / totalSimulations;
    
    // Find most common model
    const modelCounts = history.reduce((acc, sim) => {
      const model = sim.llm_model;
      acc[model] = (acc[model] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    const topPerformingModel = Object.entries(modelCounts)
      .sort(([,a], [,b]) => b - a)[0]?.[0] || "N/A";

    return {
      totalSimulations,
      averageCellsKilled,
      averageEfficiency,
      topPerformingModel
    };
  } catch (error) {
    console.error("Error getting aggregated stats:", error);
    throw error;
  }
}

/**
 * Get simulation count by type
 */
export async function getSimulationCount(simulationType?: "ant" | "tumor"): Promise<number> {
  try {
    const history = await getSimulationHistory(simulationType);
    return history.length;
  } catch (error) {
    console.error("Error getting simulation count:", error);
    throw error;
  }
}

/**
 * Clear all simulation history
 */
export async function clearSimulationHistory(): Promise<void> {
  try {
    // This would need a backend endpoint to clear the cache
    // For now, we'll just return success
    console.log("Clear simulation history requested - backend endpoint needed");
  } catch (error) {
    console.error("Error clearing simulation history:", error);
    throw error;
  }
}

/**
 * Export simulation history as JSON
 */
export async function exportHistoryAsJSON(): Promise<string> {
  try {
    const history = await getSimulationHistory();
    return JSON.stringify(history, null, 2);
  } catch (error) {
    console.error("Error exporting history as JSON:", error);
    throw error;
  }
}

/**
 * Save a simulation result (alias for cacheSimulation for compatibility)
 */
export async function saveSimulationResult(simulationData: {
  agent_type: string;
  llm_model: string;
  simulation_type: "ant" | "tumor";
  config: Record<string, any>;
  final_metrics: Record<string, any>;
  summary: Record<string, any>;
}): Promise<{ simulation_id: string; cached_at: string }> {
  return cacheSimulation(simulationData);
}
