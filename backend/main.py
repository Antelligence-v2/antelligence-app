# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
import os
import sys
import numpy as np
import random
import traceback
import openai
from dotenv import load_dotenv

# Add the current directory to Python path for local development
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.simulation import SimpleForagingModel
    from backend.nanobot_simulation import TumorNanobotModel
    from backend.tumor_environment import CellPhase
    from backend.schemas import (
        SimulationConfig, SimulationResult, StepState, AntState, 
        PheromoneMapData, ForagingEfficiencyData, FoodDepletionPoint,
        ComparisonConfig, ComparisonResult, PerformanceData,
        PheromoneConfigUpdate, PredatorState,
        # Tumor simulation schemas
        TumorSimulationConfig, TumorSimulationResult, TumorStepState,
        NanobotState, TumorCellState, VesselState, SubstrateMapData,
        TumorComparisonConfig, TumorComparisonResult, TumorPerformanceData,
        BraTSSimulationConfig
    )
except ImportError:
    # Fallback for local development
    from simulation import SimpleForagingModel
    from nanobot_simulation import TumorNanobotModel
    from tumor_environment import CellPhase
    from schemas import (
        SimulationConfig, SimulationResult, StepState, AntState, 
        PheromoneMapData, ForagingEfficiencyData, FoodDepletionPoint,
        ComparisonConfig, ComparisonResult, PerformanceData,
        PheromoneConfigUpdate, PredatorState,
        # Tumor simulation schemas
        TumorSimulationConfig, TumorSimulationResult, TumorStepState,
        NanobotState, TumorCellState, VesselState, SubstrateMapData,
        TumorComparisonConfig, TumorComparisonResult, TumorPerformanceData,
        BraTSSimulationConfig
    )

# Load environment variables
load_dotenv()

# Get API key from environment
IO_API_KEY = os.getenv("IO_SECRET_KEY")

# --- Blockchain Integration ---
BLOCKCHAIN_ENABLED = False
try:
    from blockchain.client import w3, acct, MEMORY_CONTRACT_ADDRESS
    BLOCKCHAIN_ENABLED = True
    print("✅ Blockchain client loaded successfully!")
except ImportError as e:
    print(f"⚠️ Blockchain client import failed: {e}. Blockchain features will use simulated transactions.")
    BLOCKCHAIN_ENABLED = False
except Exception as e:
    print(f"⚠️ Blockchain client could not be loaded: {e}. Blockchain features will use simulated transactions.")
    BLOCKCHAIN_ENABLED = False

app = FastAPI(
    title="Antelligence API",
    description="AI-Powered Ant Colony Simulation with Blockchain Integration",
    version="1.0.0"
)

# Mount static files (frontend build)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# Serve index.html for root path
@app.get("/")
async def read_root():
    try:
        return FileResponse("static/index.html")
    except Exception as e:
        return {"message": "Frontend not built. Please build the frontend first.", "error": str(e)}

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "antelligence-api"}

# Define the list of allowed origins for CORS
# Production-ready CORS configuration
origins = [
    "http://localhost",
    "http://localhost:3000",  # Default React port
    "http://localhost:5173",  # Default Vite port
    "http://localhost:8080",  # Your current frontend port
    "http://127.0.0.1:5173",  # Vite sometimes uses 127.0.0.1 instead of localhost
    "http://127.0.0.1:8080",  # Your current frontend port (127.0.0.1 variant)
    "https://yourdomain.com",  # Replace with your production domain
    "https://antelligence.yourdomain.com",  # Replace with your production subdomain
]

# Add the CORS middleware to the application
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers to prevent CORS preflight issues
)

def convert_pheromone_maps(model) -> PheromoneMapData:
    """Convert numpy pheromone maps to JSON-serializable format."""
    return PheromoneMapData(
        trail=model.pheromone_map['trail'].T.tolist(),  # Transpose for correct orientation
        alarm=model.pheromone_map['alarm'].T.tolist(),
        recruitment=model.pheromone_map['recruitment'].T.tolist(),
        fear=model.pheromone_map.get('fear', np.zeros_like(model.pheromone_map['trail'])).T.tolist(),
        max_values={
            'trail': float(np.max(model.pheromone_map['trail'])),
            'alarm': float(np.max(model.pheromone_map['alarm'])),
            'recruitment': float(np.max(model.pheromone_map['recruitment'])),
            'fear': float(np.max(model.pheromone_map.get('fear', np.zeros_like(model.pheromone_map['trail']))))
        }
    )

def convert_efficiency_data(model) -> ForagingEfficiencyData:
    """Convert foraging efficiency grid to JSON-serializable format."""
    max_eff = float(np.max(model.foraging_efficiency_grid))
    
    # Find hotspot locations (top 10% of efficiency values)
    threshold = max_eff * 0.1
    hotspots = []
    if threshold > 0:
        hotspot_coords = np.argwhere(model.foraging_efficiency_grid >= threshold)
        hotspots = [(int(x), int(y)) for x, y in hotspot_coords[:20]]  # Limit to 20 hotspots
    
    return ForagingEfficiencyData(
        efficiency_grid=model.foraging_efficiency_grid.T.tolist(),  # Transpose for correct orientation
        max_efficiency=max_eff,
        hotspot_locations=hotspots
    )

@app.get("/test")
def test_endpoint():
    """Simple test endpoint to verify the API is working."""
    return {"status": "API is working!", "message": "Backend is ready for simulation requests."}

@app.post("/simulation/test")
async def test_simulation():
    """Run a quick rule-based simulation to test the system."""
    try:
        print("[TEST] Starting test simulation...")
        
        # Simple rule-based test
        model = SimpleForagingModel(
            width=10, height=10, N_ants=3, N_food=5,
            agent_type="Rule-Based", with_queen=False, use_llm_queen=False
        )
        
        steps_run = 0
        for i in range(10):  # Run only 10 steps
            if not model.foods:
                break
            model.step()
            steps_run += 1
            print(f"[TEST] Step {i+1}: {len(model.foods)} food remaining")
        
        print(f"[TEST] Completed {steps_run} steps")
        
        return {
            "status": "success",
            "steps_run": steps_run,
            "food_collected": model.metrics["food_collected"],
            "food_remaining": len(model.foods),
            "pheromone_totals": {
                "trail": float(np.sum(model.pheromone_map['trail'])),
                "alarm": float(np.sum(model.pheromone_map['alarm'])),
                "recruitment": float(np.sum(model.pheromone_map['recruitment']))
            },
            "errors": model.errors
        }
    except Exception as e:
        print(f"[TEST] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")

@app.post("/simulation/run", response_model=SimulationResult)
async def run_simulation(config: SimulationConfig):
    """
    Runs a full ant foraging simulation based on the provided configuration.
    Returns the history of every step and the final results.
    """
    try:
        print(f"[SIMULATION] Starting simulation with config: {config.dict()}")
        print(f"[BLOCKCHAIN] Backend blockchain enabled: {BLOCKCHAIN_ENABLED}")
        np.random.seed(42)
        random.seed(42)

        model = SimpleForagingModel(
            width=config.grid_width,
            height=config.grid_height,
            N_ants=config.n_ants,
            N_food=config.n_food,
            agent_type=config.agent_type,
            with_queen=config.use_queen,
            use_llm_queen=config.use_llm_queen,
            selected_model_param=config.selected_model,
            prompt_style_param=config.prompt_style,
            N_predators=config.n_predators if config.enable_predators else 0,
            predator_type=config.predator_type
        )
        
        # Apply pheromone configuration
        model.set_pheromone_params(
            config.pheromone_decay_rate,
            config.trail_deposit,
            config.alarm_deposit, 
            config.recruitment_deposit,
            config.max_pheromone_value,
            config.fear_deposit
        )
        
        print(f"[SIMULATION] Model initialized. API enabled: {model.api_enabled}")
        
        history = []
        # Determine how often to capture detailed state (every N steps for performance)
        detail_interval = max(1, config.max_steps // 50)  # Capture ~50 detailed snapshots
        
        for step_num in range(config.max_steps):
            if not model.foods:
                print(f"[SIMULATION] All food collected at step {step_num}")
                break
            
            print(f"[SIMULATION] Running step {step_num + 1}/{config.max_steps}")
            model.step()

            # --- Create the list of agents for the current step ---
            ants_list = [
                AntState(
                    id=ant.unique_id, 
                    pos=ant.pos, 
                    carrying_food=ant.carrying_food, 
                    is_llm=ant.is_llm_controlled,
                    steps_since_food=ant.steps_since_food
                ) 
                for ant in model.ants
            ]

            # If the queen exists, add her to the list with a special flag
            if model.queen:
                center_pos = (model.width // 2, model.height // 2)
                queen_state = AntState(
                    id='queen', 
                    pos=center_pos, 
                    carrying_food=False, 
                    is_llm=model.use_llm_queen, 
                    is_queen=True
                )
                ants_list.append(queen_state)
            
            # --- Create the list of predators for the current step ---
            predators_list = [
                PredatorState(
                    id=predator.unique_id,
                    pos=predator.pos,
                    energy=predator.energy,
                    is_llm=predator.is_llm_controlled,
                    ants_caught=predator.ants_caught,
                    hunt_cooldown=predator.hunt_cooldown
                )
                for predator in model.predators
            ]
            
            # Capture detailed state periodically or for final step
            capture_detail = (step_num % detail_interval == 0) or (step_num == config.max_steps - 1)
            pheromone_data = None
            efficiency_data = None
            
            if capture_detail:
                pheromone_data = convert_pheromone_maps(model)
                efficiency_data = convert_efficiency_data(model)
            
            # --- Capture the full state for this step ---
            current_state = StepState(
                step=model.step_count,
                ants=ants_list,
                predators=predators_list,
                food_positions=model.get_food_positions(),
                metrics=model.metrics.copy(),
                queen_report=model.queen_llm_anomaly_rep,
                errors=model.errors.copy(),
                pheromone_data=pheromone_data,
                efficiency_data=efficiency_data,
                nest_position=(model.width // 2, model.height // 2)
            )
            history.append(current_state)
            model.errors.clear()

        print(f"[SIMULATION] Completed {model.step_count} steps")

        # Convert food depletion history to proper format
        food_depletion_data = [
            FoodDepletionPoint(step=point["step"], food_piles_remaining=point["food_piles_remaining"])
            for point in model.food_depletion_history
        ]

        # Final state data
        final_pheromone_data = convert_pheromone_maps(model)
        final_efficiency_data = convert_efficiency_data(model)

        # Collect blockchain logs and transactions (always enabled)
        blockchain_logs = []
        blockchain_transactions = []
        if hasattr(model, 'blockchain_logs'):
            blockchain_logs = model.blockchain_logs
            print(f"[BLOCKCHAIN] Collected {len(blockchain_logs)} blockchain logs")
        else:
            print(f"[BLOCKCHAIN] No blockchain logs attribute found on model")
        
        if hasattr(model, 'blockchain_transactions'):
            blockchain_transactions = model.blockchain_transactions
            print(f"[BLOCKCHAIN] Collected {len(blockchain_transactions)} blockchain transactions")
        else:
            print(f"[BLOCKCHAIN] No blockchain transactions attribute found on model")

        return SimulationResult(
            config=config,
            total_steps_run=model.step_count,
            final_metrics=model.metrics,
            history=history,
            food_depletion_history=food_depletion_data,
            initial_food_count=model.initial_food_count,
            final_pheromone_data=final_pheromone_data,
            final_efficiency_data=final_efficiency_data,
            blockchain_logs=blockchain_logs,
            blockchain_transactions=blockchain_transactions
        )

    except Exception as e:
        print("--- ERROR CAUGHT IN /simulation/run ---")
        traceback.print_exc()
        print("------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))

def _run_comparison_leg(params: dict, steps: int) -> int:
    """Helper to run one leg of the comparison."""
    try:
        print(f"[QUEEN COMPARISON] Starting leg with params: {params}")
        np.random.seed(42)
        random.seed(42)
        
        # Force rule-based agents for comparison to avoid API timeouts
        comparison_params = params.copy()
        comparison_params['agent_type'] = 'Rule-Based'  # Use rule-based for reliable comparison
        
        model = SimpleForagingModel(
            width=comparison_params['grid_width'], 
            height=comparison_params['grid_height'], 
            N_ants=comparison_params['n_ants'],
            N_food=comparison_params['n_food'], 
            agent_type=comparison_params['agent_type'], 
            with_queen=comparison_params['with_queen'],
            use_llm_queen=comparison_params['use_llm_queen'], 
            selected_model_param=comparison_params['selected_model'],
            prompt_style_param=comparison_params['prompt_style'],
            N_predators=comparison_params.get('n_predators', 0),
            predator_type=comparison_params.get('predator_type', 'Rule-Based')
        )
        
        # Apply pheromone parameters if provided
        if 'pheromone_decay_rate' in comparison_params:
            model.set_pheromone_params(
                comparison_params['pheromone_decay_rate'],
                comparison_params['trail_deposit'],
                comparison_params['alarm_deposit'],
                comparison_params['recruitment_deposit'],
                comparison_params['max_pheromone_value'],
                comparison_params.get('fear_deposit', 3.0)
            )
        
        print(f"[QUEEN COMPARISON] Running {steps} steps with rule-based agents...")
        for step in range(steps):
            if not model.foods: 
                print(f"[QUEEN COMPARISON] No food remaining at step {step}")
                break
            model.step()
            if step % 10 == 0:  # Log every 10 steps
                print(f"[QUEEN COMPARISON] Step {step}/{steps}, food remaining: {len(model.foods)}")
        
        result = model.metrics["food_collected"]
        print(f"[QUEEN COMPARISON] Completed with {result} food collected")
        return result
        
    except Exception as e:
        print(f"[QUEEN COMPARISON] Error in comparison leg: {str(e)}")
        raise e

@app.post("/simulation/compare", response_model=ComparisonResult)
async def compare_queen_performance(config: ComparisonConfig):
    """
    Runs two simulations in parallel to compare the effectiveness of the Queen Ant.
    """
    try:
        print(f"[QUEEN COMPARISON] Starting comparison with {config.comparison_steps} steps")
        base_params = config.dict()
        
        # Use asyncio timeout instead of signal (cross-platform compatible)
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        import time
        
        async def run_comparison_with_timeout():
            """Run comparison with timeout using asyncio"""
            executor = ThreadPoolExecutor(max_workers=2)
            loop = asyncio.get_event_loop()
            
            try:
                # Run simulations with timeout
                print(f"[QUEEN COMPARISON] Running simulation WITH queen...")
                queen_params = {**base_params, 'with_queen': True}
                food_with_queen_future = loop.run_in_executor(
                    executor, _run_comparison_leg, queen_params, config.comparison_steps
                )
                
                print(f"[QUEEN COMPARISON] Running simulation WITHOUT queen...")
                no_queen_params = {**base_params, 'with_queen': False, 'use_llm_queen': False}
                food_no_queen_future = loop.run_in_executor(
                    executor, _run_comparison_leg, no_queen_params, config.comparison_steps
                )
                
                # Wait for both with 60 second timeout
                food_with_queen, food_no_queen = await asyncio.wait_for(
                    asyncio.gather(food_with_queen_future, food_no_queen_future),
                    timeout=60.0
                )
                
                print(f"[QUEEN COMPARISON] Results - With Queen: {food_with_queen}, Without Queen: {food_no_queen}")
                
                return ComparisonResult(
                    food_collected_with_queen=food_with_queen,
                    food_collected_no_queen=food_no_queen,
                    config=config
                )
            except asyncio.TimeoutError:
                executor.shutdown(wait=False)
                raise HTTPException(status_code=408, detail="Queen comparison timed out after 60 seconds")
            finally:
                executor.shutdown(wait=True)
        
        return await run_comparison_with_timeout()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[QUEEN COMPARISON] Error in comparison: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulation/performance", response_model=PerformanceData)
async def get_performance_analysis(config: SimulationConfig):
    """
    Runs a simulation and returns focused performance data for analysis.
    """
    try:
        np.random.seed(42)
        random.seed(42)

        model = SimpleForagingModel(
            width=config.grid_width,
            height=config.grid_height,
            N_ants=config.n_ants,
            N_food=config.n_food,
            agent_type=config.agent_type,
            with_queen=config.use_queen,
            use_llm_queen=config.use_llm_queen,
            selected_model_param=config.selected_model,
            prompt_style_param=config.prompt_style,
            N_predators=config.n_predators if config.enable_predators else 0,
            predator_type=config.predator_type
        )
        
        # Apply pheromone configuration
        model.set_pheromone_params(
            config.pheromone_decay_rate,
            config.trail_deposit,
            config.alarm_deposit,
            config.recruitment_deposit,
            config.max_pheromone_value,
            config.fear_deposit
        )
        
        for _ in range(config.max_steps):
            if not model.foods:
                break
            model.step()

        # Calculate efficiency by agent type
        total_llm_ants = sum(1 for ant in model.ants if ant.is_llm_controlled)
        total_rule_ants = len(model.ants) - total_llm_ants
        
        efficiency_by_type = {}
        if total_llm_ants > 0:
            efficiency_by_type["LLM"] = model.metrics["food_collected_by_llm"] / total_llm_ants
        if total_rule_ants > 0:
            efficiency_by_type["Rule-Based"] = model.metrics["food_collected_by_rule"] / total_rule_ants

        # Pheromone summary
        pheromone_summary = {
            "total_trail": float(np.sum(model.pheromone_map['trail'])),
            "total_alarm": float(np.sum(model.pheromone_map['alarm'])),
            "total_recruitment": float(np.sum(model.pheromone_map['recruitment'])),
            "max_trail": float(np.max(model.pheromone_map['trail'])),
            "max_alarm": float(np.max(model.pheromone_map['alarm'])),
            "max_recruitment": float(np.max(model.pheromone_map['recruitment']))
        }

        # Foraging hotspots
        efficiency_data = convert_efficiency_data(model)
        foraging_hotspots = efficiency_data.hotspot_locations

        return PerformanceData(
            food_collected_by_llm=model.metrics["food_collected_by_llm"],
            food_collected_by_rule=model.metrics["food_collected_by_rule"],
            total_api_calls=model.metrics["total_api_calls"],
            efficiency_by_agent_type=efficiency_by_type,
            pheromone_summary=pheromone_summary,
            foraging_hotspots=foraging_hotspots
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tumor Nanobot Simulation Endpoints
# ============================================================================

def convert_substrate_maps(model: TumorNanobotModel) -> SubstrateMapData:
    """Convert substrate concentration grids to JSON-serializable format."""
    substrate_data = {}
    max_values = {}
    mean_values = {}
    
    for name in ['oxygen', 'drug', 'trail', 'alarm', 'recruitment']:
        substrate = model.microenv.get_substrate(name)
        if substrate:
            # Get 2D slice (z=0) and transpose for correct orientation
            conc = substrate.concentration[:, :, 0].T.tolist()
            substrate_data[name] = conc
            max_values[name] = float(np.max(substrate.concentration))
            mean_values[name] = float(np.mean(substrate.concentration))
        else:
            substrate_data[name] = []
            max_values[name] = 0.0
            mean_values[name] = 0.0
    
    return SubstrateMapData(
        oxygen=substrate_data['oxygen'],
        drug=substrate_data['drug'],
        trail=substrate_data['trail'],
        alarm=substrate_data['alarm'],
        recruitment=substrate_data['recruitment'],
        max_values=max_values,
        mean_values=mean_values
    )


@app.post("/simulation/tumor/run", response_model=TumorSimulationResult)
async def run_tumor_simulation(config: TumorSimulationConfig):
    """
    Run a tumor nanobot simulation with PhysiCell-inspired dynamics.
    
    This endpoint runs the core PhysiCell-based glioblastoma nanobot simulation
    with pheromone-guided drug delivery.
    """
    try:
        print(f"[TUMOR SIM] Starting tumor simulation with config: {config.dict()}")
        
        # Set random seeds for reproducibility
        np.random.seed(42)
        random.seed(42)
        
        # Initialize the tumor nanobot model
        model = TumorNanobotModel(
            domain_size=config.domain_size,
            voxel_size=config.voxel_size,
            n_nanobots=config.n_nanobots,
            tumor_radius=config.tumor_radius,
            agent_type=config.agent_type,
            with_queen=config.use_queen,
            use_llm_queen=config.use_llm_queen,
            selected_model=config.selected_model
        )
        
        print(f"[TUMOR SIM] Model initialized. Starting {config.max_steps} steps...")
        
        # Track initial tumor stats
        initial_stats = model.geometry.get_tumor_statistics()
        
        history = []
        detail_interval = max(1, config.max_steps // 20)  # Capture ~20 snapshots
        
        # Store initial vessel positions (static, only need once)
        vessels_state = [
            VesselState(
                position=v.position,
                oxygen_supply=v.oxygen_supply,
                drug_supply=v.drug_supply,
                supply_radius=v.supply_radius
            )
            for v in model.geometry.vessels
        ]
        
        for step_num in range(config.max_steps):
            print(f"[TUMOR SIM] Step {step_num + 1}/{config.max_steps}")
            model.step()
            
            # Create nanobot states
            nanobots_state = [nanobot.to_dict() for nanobot in model.nanobots]
            nanobots_state = [
                NanobotState(**nb) for nb in nanobots_state
            ]
            
            # Capture detailed state periodically
            capture_detail = (step_num % detail_interval == 0) or (step_num == config.max_steps - 1)
            substrate_data = None
            tumor_cells_state = []
            
            if capture_detail:
                substrate_data = convert_substrate_maps(model)
                
                # Include tumor cell states (sample for performance)
                sample_cells = random.sample(
                    model.geometry.tumor_cells,
                    min(100, len(model.geometry.tumor_cells))
                )
                tumor_cells_state = [
                    TumorCellState(**cell.to_dict())
                    for cell in sample_cells
                ]
            
            # Create step state
            current_state = TumorStepState(
                step=model.step_count,
                time=model.microenv.time,
                nanobots=nanobots_state,
                tumor_cells=tumor_cells_state,
                vessels=vessels_state if step_num == 0 else [],  # Only include vessels in first step
                metrics=model.metrics.copy(),
                queen_report=model.queen_report,
                errors=model.errors.copy(),
                substrate_data=substrate_data
            )
            
            history.append(current_state)
            model.errors.clear()
        
        print(f"[TUMOR SIM] Simulation completed after {model.step_count} steps")
        
        # Get final tumor statistics
        final_stats = model.geometry.get_tumor_statistics()
        
        # Calculate treatment effectiveness
        initial_living = initial_stats['living_cells']
        final_living = final_stats['living_cells']
        cells_killed = initial_living - final_living
        
        tumor_statistics = {
            'initial_living_cells': initial_living,
            'final_living_cells': final_living,
            'cells_killed': cells_killed,
            'kill_rate': cells_killed / initial_living if initial_living > 0 else 0,
            'initial_hypoxic': len([c for c in model.geometry.tumor_cells if c.phase.value == 'hypoxic']),
            'final_hypoxic': final_stats['phase_distribution'].get('hypoxic', 0),
            'apoptotic_cells': final_stats['phase_distribution'].get('apoptotic', 0),
            'necrotic_cells': final_stats['phase_distribution'].get('necrotic', 0)
        }
        
        # Get final substrate data
        final_substrate_data = convert_substrate_maps(model)
        
        # Blockchain logs (placeholder for now)
        blockchain_logs = [
            f"Simulation initialized: {model.step_count} steps, {len(model.nanobots)} nanobots",
            f"Treatment outcome: {cells_killed} cells killed, {model.metrics['total_deliveries']} drug deliveries"
        ]
        
        return TumorSimulationResult(
            config=config,
            total_steps_run=model.step_count,
            total_time=model.microenv.time,
            final_metrics=model.metrics,
            history=history,
            tumor_statistics=tumor_statistics,
            final_substrate_data=final_substrate_data,
            blockchain_logs=blockchain_logs
        )
        
    except Exception as e:
        print("--- ERROR IN /simulation/tumor/run ---")
        traceback.print_exc()
        print("--------------------------------------")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulation/tumor/performance", response_model=TumorPerformanceData)
async def get_tumor_performance(config: TumorSimulationConfig):
    """
    Run tumor simulation and return focused performance metrics.
    """
    try:
        print(f"[TUMOR PERF] Running performance analysis...")
        
        np.random.seed(42)
        random.seed(42)
        
        model = TumorNanobotModel(
            domain_size=config.domain_size,
            voxel_size=config.voxel_size,
            n_nanobots=config.n_nanobots,
            tumor_radius=config.tumor_radius,
            agent_type=config.agent_type,
            with_queen=config.use_queen,
            use_llm_queen=config.use_llm_queen,
            selected_model=config.selected_model
        )
        
        initial_hypoxic = len(model.geometry.get_cells_in_phase(CellPhase.HYPOXIC))
        initial_living = len(model.geometry.get_living_cells())
        
        # Run simulation
        for _ in range(config.max_steps):
            model.step()
        
        final_hypoxic = len(model.geometry.get_cells_in_phase(CellPhase.HYPOXIC))
        final_living = len(model.geometry.get_living_cells())
        
        cells_killed = initial_living - final_living
        drug_efficiency = cells_killed / model.metrics['total_drug_delivered'] if model.metrics['total_drug_delivered'] > 0 else 0
        hypoxic_reduction = ((initial_hypoxic - final_hypoxic) / initial_hypoxic * 100) if initial_hypoxic > 0 else 0
        
        # Get substrate summary
        substrate_summary = model.microenv.get_substrate_summary()
        
        return TumorPerformanceData(
            cells_killed=cells_killed,
            total_drug_delivered=model.metrics['total_drug_delivered'],
            total_deliveries=model.metrics['total_deliveries'],
            drug_efficiency=drug_efficiency,
            hypoxic_cell_reduction=hypoxic_reduction,
            total_api_calls=model.metrics['total_api_calls'],
            substrate_summary=substrate_summary
        )
        
    except Exception as e:
        print(f"[TUMOR PERF] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulation/tumor/compare", response_model=TumorComparisonResult)
async def compare_tumor_strategies(config: TumorComparisonConfig):
    """
    Compare pheromone-guided vs. non-pheromone nanobot strategies.
    """
    try:
        print(f"[TUMOR COMPARE] Starting strategy comparison...")
        
        # Helper function to run one simulation
        def run_one(use_pheromones: bool, steps: int):
            np.random.seed(42)
            random.seed(42)
            
            model = TumorNanobotModel(
                domain_size=config.domain_size,
                voxel_size=config.voxel_size,
                n_nanobots=config.n_nanobots,
                tumor_radius=config.tumor_radius,
                agent_type="Rule-Based",  # Use rule-based for fair comparison
                with_queen=False,
                use_llm_queen=False,
                selected_model=config.selected_model
            )
            
            initial_living = len(model.geometry.get_living_cells())
            
            # If not using pheromones, disable chemotaxis to pheromones
            if not use_pheromones:
                for nanobot in model.nanobots:
                    nanobot.chemotaxis_weights['trail'] = 0.0
                    nanobot.chemotaxis_weights['alarm'] = 0.0
                    nanobot.chemotaxis_weights['recruitment'] = 0.0
            
            for _ in range(steps):
                model.step()
            
            final_living = len(model.geometry.get_living_cells())
            cells_killed = initial_living - final_living
            drug_efficiency = cells_killed / model.metrics['total_drug_delivered'] if model.metrics['total_drug_delivered'] > 0 else 0
            
            return cells_killed, drug_efficiency
        
        # Run both strategies
        print("[TUMOR COMPARE] Running WITH pheromones...")
        cells_killed_with, efficiency_with = run_one(True, config.comparison_steps)
        
        print("[TUMOR COMPARE] Running WITHOUT pheromones...")
        cells_killed_without, efficiency_without = run_one(False, config.comparison_steps)
        
        print(f"[TUMOR COMPARE] Results - With: {cells_killed_with} killed, Without: {cells_killed_without} killed")
        
        return TumorComparisonResult(
            cells_killed_with_pheromones=cells_killed_with,
            cells_killed_no_pheromones=cells_killed_without,
            drug_efficiency_with_pheromones=efficiency_with,
            drug_efficiency_no_pheromones=efficiency_without,
            config=config
        )
        
    except Exception as e:
        print(f"[TUMOR COMPARE] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulation/tumor/test")
async def test_tumor_simulation():
    """Quick test of tumor simulation system."""
    try:
        print("[TUMOR TEST] Starting quick test...")
        
        model = TumorNanobotModel(
            domain_size=400.0,
            voxel_size=20.0,
            n_nanobots=5,
            tumor_radius=100.0,
            agent_type="Rule-Based",
            with_queen=False
        )
        
        initial_living = len(model.geometry.get_living_cells())
        
        # Run 10 steps
        for i in range(10):
            model.step()
            print(f"[TUMOR TEST] Step {i+1}: {len(model.geometry.get_living_cells())} living cells")
        
        final_living = len(model.geometry.get_living_cells())
        
        return {
            "status": "success",
            "steps_run": model.step_count,
            "initial_living_cells": initial_living,
            "final_living_cells": final_living,
            "cells_killed": initial_living - final_living,
            "drug_deliveries": model.metrics['total_deliveries'],
            "substrate_summary": model.microenv.get_substrate_summary(),
            "errors": model.errors
        }
        
    except Exception as e:
        print(f"[TUMOR TEST] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/simulation/tumor/from-brats", response_model=TumorSimulationResult)
async def run_brats_simulation(config: BraTSSimulationConfig):
    """
    Run a tumor nanobot simulation using real BraTS 2024 patient data.
    
    This endpoint loads BraTS segmentation data and creates a realistic
    tumor geometry for simulation.
    """
    try:
        print(f"[BRATS SIM] Starting BraTS simulation for patient: {config.patient_id}")
        
        # Import BraTS loader
        from brats_loader import (
            load_brats_segmentation,
            find_brats_segmentation_file,
            get_patient_metadata
        )
        from tumor_environment import create_brats_tumor_geometry
        from brats_loader import BRATS_TRAINING_PATH, BRATS_VALIDATION_PATH, BRATS_ADDITIONAL_TRAINING_PATH
        
        # Find patient directory based on dataset
        if config.dataset == 'training':
            base_path = BRATS_TRAINING_PATH
        elif config.dataset == 'validation':
            base_path = BRATS_VALIDATION_PATH
        elif config.dataset == 'additional_training':
            base_path = BRATS_ADDITIONAL_TRAINING_PATH
        else:
            raise HTTPException(status_code=400, detail=f"Unknown dataset: {config.dataset}")
        
        if not base_path or not os.path.exists(base_path):
            raise HTTPException(status_code=400, detail=f"Dataset path not found: {config.dataset}")
        
        patient_dir = os.path.join(base_path, config.patient_id)
        seg_file = find_brats_segmentation_file(patient_dir)
        
        if not seg_file:
            raise HTTPException(status_code=404, detail=f"Patient not found: {config.patient_id}")
        
        print(f"  Loading segmentation: {seg_file}")
        
        # Load segmentation
        seg_array, voxel_spacing = load_brats_segmentation(seg_file)
        print(f"  Loaded: shape={seg_array.shape}, spacing={voxel_spacing} mm")
        
        # Create geometry from BraTS
        brats_geometry = create_brats_tumor_geometry(
            segmentation_array=seg_array,
            voxel_spacing=voxel_spacing,
            cell_density=config.cell_density,
            slice_idx=config.slice_idx,
            target_domain_size=config.domain_size,
            voxel_size=config.voxel_size
        )
        
        print(f"[BRATS SIM] Geometry created: {len(brats_geometry.tumor_cells)} cells")
        
        # Initialize simulation model with BraTS geometry
        model = TumorNanobotModel(
            domain_size=config.domain_size,
            voxel_size=config.voxel_size,
            n_nanobots=config.n_nanobots,
            tumor_radius=brats_geometry.tumor_radius,  # Use actual tumor radius from BraTS
            agent_type=config.agent_type,
            with_queen=config.use_queen,
            use_llm_queen=config.use_llm_queen,
            selected_model=config.selected_model
        )
        
        # Replace geometry with BraTS geometry
        model.geometry = brats_geometry
        
        print(f"[BRATS SIM] Model initialized. Starting {config.max_steps} steps...")
        
        # Track initial tumor stats
        initial_stats = model.geometry.get_tumor_statistics()
        
        history = []
        detail_interval = max(1, config.max_steps // 20)
        
        # Store vessel positions
        vessels_state = [
            VesselState(
                position=v.position,
                oxygen_supply=v.oxygen_supply,
                drug_supply=v.drug_supply,
                supply_radius=v.supply_radius
            )
            for v in model.geometry.vessels
        ]
        
        for step_num in range(config.max_steps):
            if step_num % 10 == 0:
                print(f"[BRATS SIM] Step {step_num + 1}/{config.max_steps}")
            model.step()
            
            # Create nanobot states
            nanobots_state = [nanobot.to_dict() for nanobot in model.nanobots]
            nanobots_state = [NanobotState(**nb) for nb in nanobots_state]
            
            # Capture detailed state periodically
            capture_detail = (step_num % detail_interval == 0) or (step_num == config.max_steps - 1)
            substrate_data = None
            tumor_cells_state = []
            
            if capture_detail:
                substrate_data = convert_substrate_maps(model)
                
                sample_cells = random.sample(
                    model.geometry.tumor_cells,
                    min(100, len(model.geometry.tumor_cells))
                )
                tumor_cells_state = [TumorCellState(**cell.to_dict()) for cell in sample_cells]
            
            current_state = TumorStepState(
                step=model.step_count,
                time=model.microenv.time,
                nanobots=nanobots_state,
                tumor_cells=tumor_cells_state,
                vessels=vessels_state if step_num == 0 else [],
                metrics=model.metrics.copy(),
                queen_report=model.queen_report,
                errors=model.errors.copy(),
                substrate_data=substrate_data
            )
            
            history.append(current_state)
            model.errors.clear()
        
        print(f"[BRATS SIM] Simulation completed after {model.step_count} steps")
        
        # Get final statistics
        final_stats = model.geometry.get_tumor_statistics()
        final_substrate_data = convert_substrate_maps(model)
        blockchain_logs = []
        
        result = TumorSimulationResult(
            config=TumorSimulationConfig(**config.dict()),
            total_steps_run=model.step_count,
            total_time=model.microenv.time,
            final_metrics=model.metrics,
            history=history,
            tumor_statistics=final_stats,
            final_substrate_data=final_substrate_data,
            blockchain_logs=blockchain_logs
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BRATS SIM] Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/brats/patients")
async def list_brats_patients():
    """
    List all available BraTS patients across all datasets.
    """
    try:
        from brats_loader import list_brats_patients, BRATS_TRAINING_PATH, BRATS_VALIDATION_PATH, BRATS_ADDITIONAL_TRAINING_PATH
        
        datasets = {}
        
        # Get patients from each dataset
        for dataset_name, path in [
            ("training", BRATS_TRAINING_PATH),
            ("validation", BRATS_VALIDATION_PATH),
            ("additional_training", BRATS_ADDITIONAL_TRAINING_PATH)
        ]:
            if path and os.path.exists(path):
                patients = list_brats_patients(path)
                datasets[dataset_name] = patients
            else:
                datasets[dataset_name] = []
        
        total = sum(len(p) for p in datasets.values())
        print(f"[BRATS] Listed {total} patients across {len(datasets)} datasets")
        
        return {
            "datasets": datasets,
            "total_patients": total
        }
        
    except Exception as e:
        print(f"[BRATS] Error listing patients: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))