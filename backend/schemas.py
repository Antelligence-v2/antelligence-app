# schemas.py
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Literal, Optional
import numpy as np

class SimulationConfig(BaseModel):
    """Configuration for starting a simulation."""
    grid_width: int = Field(20, gt=0, description="Width of the simulation grid.")
    grid_height: int = Field(20, gt=0, description="Height of the simulation grid.")
    n_ants: int = Field(10, gt=0, description="Number of ants in the colony.")
    n_food: int = Field(15, gt=0, description="Number of food piles.")
    agent_type: Literal["LLM-Powered", "Rule-Based", "Hybrid"] = "LLM-Powered"
    selected_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    prompt_style: Literal["Adaptive", "Structured", "Autonomous"] = "Adaptive"
    use_queen: bool = True
    use_llm_queen: bool = True
    max_steps: int = Field(200, gt=0, le=1000)
    
    # Pheromone configuration parameters
    pheromone_decay_rate: float = Field(0.05, ge=0.01, le=0.2, description="Pheromone decay rate per step")
    trail_deposit: float = Field(1.0, ge=0.1, le=5.0, description="Trail pheromone deposit amount")
    alarm_deposit: float = Field(2.0, ge=0.1, le=5.0, description="Alarm pheromone deposit amount")
    recruitment_deposit: float = Field(1.5, ge=0.1, le=5.0, description="Recruitment pheromone deposit amount")
    max_pheromone_value: float = Field(10.0, ge=5.0, le=20.0, description="Maximum pheromone value")
    
    # Predator configuration parameters
    enable_predators: bool = Field(False, description="Whether to enable predators in the simulation")
    n_predators: int = Field(0, ge=0, le=10, description="Number of predators in the ecosystem")
    predator_type: Literal["LLM-Powered", "Rule-Based", "Hybrid"] = "LLM-Powered"
    fear_deposit: float = Field(3.0, ge=1.0, le=10.0, description="Fear pheromone deposit amount")

class AntState(BaseModel):
    """Represents the state of a single ant at a point in time."""
    id: int | str # Queen ID will be a string
    pos: Tuple[int, int]
    carrying_food: bool
    is_llm: bool
    is_queen: bool = False # Flag to identify queen ant
    steps_since_food: Optional[int] = None # For tracking recruitment behavior

class PredatorState(BaseModel):
    """Represents the state of a single predator at a point in time."""
    id: int | str
    pos: Tuple[int, int]
    energy: int
    is_llm: bool
    ants_caught: int
    hunt_cooldown: int

class FoodDepletionPoint(BaseModel):
    """Represents a point in the food depletion history."""
    step: int
    food_piles_remaining: int

class PheromoneMapData(BaseModel):
    """Represents pheromone map data for visualization."""
    trail: List[List[float]]
    alarm: List[List[float]]
    recruitment: List[List[float]]
    fear: List[List[float]] = []  # Add fear pheromone with default empty list
    max_values: Dict[str, float]

class ForagingEfficiencyData(BaseModel):
    """Represents foraging efficiency grid data."""
    efficiency_grid: List[List[float]]
    max_efficiency: float
    hotspot_locations: List[Tuple[int, int]]

class StepState(BaseModel):
    """Represents the complete state of the simulation at a single step."""
    step: int
    ants: List[AntState]
    predators: List[PredatorState] = []  # Add predators with default empty list
    food_positions: List[Tuple[int, int]]
    metrics: Dict
    queen_report: str
    errors: List[str]
    pheromone_data: Optional[PheromoneMapData] = None
    efficiency_data: Optional[ForagingEfficiencyData] = None
    nest_position: Tuple[int, int] = (10, 10)  # Default nest position

class BlockchainTransaction(BaseModel):
    """Represents a single blockchain transaction with latency data."""
    tx_hash: str
    step: int
    position: List[int]
    ant_type: str
    submit_time: float
    confirm_time: float
    latency_ms: int
    success: bool
    gas_used: int = 0  # Gas used in the transaction

class SimulationResult(BaseModel):
    """The final result of a full simulation run."""
    config: SimulationConfig
    total_steps_run: int
    final_metrics: Dict
    history: List[StepState]
    food_depletion_history: List[FoodDepletionPoint]
    initial_food_count: int
    final_pheromone_data: Optional[PheromoneMapData] = None
    final_efficiency_data: Optional[ForagingEfficiencyData] = None
    blockchain_logs: List[str] = []  # Add blockchain transaction logs
    blockchain_transactions: List[BlockchainTransaction] = []  # Structured transaction data

class ComparisonConfig(SimulationConfig):
    """Configuration for the comparison endpoint."""
    comparison_steps: int = Field(100, gt=0, le=500, description="Number of steps for each comparison run.")

class ComparisonResult(BaseModel):
    """Result of the Queen vs. No-Queen comparison."""
    food_collected_with_queen: int
    food_collected_no_queen: int
    config: ComparisonConfig

class PerformanceData(BaseModel):
    """Performance metrics for charts and analysis."""
    food_collected_by_llm: int
    food_collected_by_rule: int
    total_api_calls: int
    efficiency_by_agent_type: Dict[str, float]
    pheromone_summary: Optional[Dict[str, float]] = None
    foraging_hotspots: Optional[List[Tuple[int, int]]] = None

class ChartDataRequest(BaseModel):
    """Request for chart data from a simulation result."""
    simulation_id: str = None  # For future use if we store results
    step_range: Tuple[int, int] = None  # Optional range filter

class PheromoneConfigUpdate(BaseModel):
    """Update pheromone parameters during simulation."""
    decay_rate: float = Field(ge=0.01, le=0.2)
    trail_deposit: float = Field(ge=0.1, le=5.0)
    alarm_deposit: float = Field(ge=0.1, le=5.0)
    recruitment_deposit: float = Field(ge=0.1, le=5.0)
    max_value: float = Field(ge=5.0, le=20.0)


# ============================================================================
# Tumor Nanobot Simulation Schemas
# ============================================================================

class TumorSimulationConfig(BaseModel):
    """Configuration for tumor nanobot simulation."""
    domain_size: float = Field(600.0, gt=0, description="Simulation domain size in micrometers")
    voxel_size: float = Field(10.0, gt=0, description="Voxel spacing in micrometers")
    n_nanobots: int = Field(10, gt=0, le=100, description="Number of nanobots")
    tumor_radius: float = Field(200.0, gt=0, description="Tumor radius in micrometers")
    agent_type: Literal["LLM-Powered", "Rule-Based", "Hybrid"] = "LLM-Powered"
    selected_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    use_queen: bool = False
    use_llm_queen: bool = False
    max_steps: int = Field(100, gt=0, le=500, description="Maximum simulation steps")
    
    # Cell parameters
    cell_density: float = Field(0.001, gt=0, description="Tumor cells per µm²")
    vessel_density: float = Field(0.01, gt=0, description="Blood vessels per 100 µm²")
    
    # Advanced biological parameters
    enable_bbb: bool = Field(True, description="Enable blood-brain barrier modeling")
    bbb_permeability: float = Field(0.1, ge=0.0, le=1.0, description="BBB permeability factor")
    enable_immune_system: bool = Field(True, description="Enable immune system interactions")
    immune_cell_density: float = Field(0.05, gt=0, description="Immune cells per tumor cell")
    enable_tumor_heterogeneity: bool = Field(True, description="Enable tumor cell heterogeneity")
    stem_cell_fraction: float = Field(0.1, ge=0.0, le=1.0, description="Fraction of stem cells")
    resistant_cell_fraction: float = Field(0.15, ge=0.0, le=1.0, description="Fraction of resistant cells")
    enable_multi_drug: bool = Field(False, description="Enable multi-drug combination therapy")
    drug_combination_ratio: float = Field(1.0, gt=0, description="Ratio of drug A to drug B")


class NanobotState(BaseModel):
    """State of a single nanobot at a point in time."""
    id: int
    position: Tuple[float, float]
    state: str  # 'searching', 'targeting', 'delivering', 'returning', 'reloading'
    drug_payload: float
    deliveries_made: int
    total_drug_delivered: float
    is_llm: bool
    has_target: bool


class TumorCellState(BaseModel):
    """State of a tumor cell at a point in time."""
    id: int
    position: Tuple[float, float, float]
    radius: float
    phase: str  # 'viable', 'hypoxic', 'necrotic', 'apoptotic'
    is_alive: bool
    oxygen_uptake: float
    accumulated_drug: float
    hypoxic_duration: float


class VesselState(BaseModel):
    """State of a blood vessel."""
    position: Tuple[float, float, float]
    oxygen_supply: float
    drug_supply: float
    supply_radius: float


class SubstrateMapData(BaseModel):
    """Substrate concentration maps for visualization."""
    oxygen: List[List[float]]
    drug: List[List[float]]
    trail: List[List[float]]
    alarm: List[List[float]]
    recruitment: List[List[float]]
    max_values: Dict[str, float]
    mean_values: Dict[str, float]


class TumorStepState(BaseModel):
    """Complete state of tumor simulation at a single step."""
    step: int
    time: float  # Simulation time in minutes
    nanobots: List[NanobotState]
    tumor_cells: List[TumorCellState] = []  # Optional, can be sparse for performance
    vessels: List[VesselState] = []  # Optional, static so only need once
    metrics: Dict
    queen_report: str
    errors: List[str]
    substrate_data: Optional[SubstrateMapData] = None


class TumorSimulationResult(BaseModel):
    """Final result of a tumor nanobot simulation run."""
    config: TumorSimulationConfig
    total_steps_run: int
    total_time: float  # Simulation time in minutes
    final_metrics: Dict
    history: List[TumorStepState]
    tumor_statistics: Dict  # Summary stats about tumor kill rate, etc.
    final_substrate_data: Optional[SubstrateMapData] = None
    blockchain_logs: List[str] = []


class TumorComparisonConfig(TumorSimulationConfig):
    """Configuration for comparing tumor nanobot strategies."""
    comparison_steps: int = Field(50, gt=0, le=200, description="Steps for each comparison run")


class TumorComparisonResult(BaseModel):
    """Result of comparing different nanobot strategies."""
    cells_killed_with_pheromones: int
    cells_killed_no_pheromones: int
    drug_efficiency_with_pheromones: float
    drug_efficiency_no_pheromones: float
    config: TumorComparisonConfig


class TumorPerformanceData(BaseModel):
    """Performance metrics for tumor simulation analysis."""
    cells_killed: int
    total_drug_delivered: float
    total_deliveries: int
    drug_efficiency: float  # Cells killed per unit drug
    hypoxic_cell_reduction: float  # Percentage reduction in hypoxic cells
    total_api_calls: int
    substrate_summary: Optional[Dict[str, Dict[str, float]]] = None