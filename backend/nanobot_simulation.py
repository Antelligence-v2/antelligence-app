"""
Nanobot swarm simulation for targeted drug delivery.

This module adapts the Antelligence ant colony logic to nanobots navigating
the tumor microenvironment using pheromone-based communication and chemotaxis.

Key adaptations:
- Food → Tumor cells (hypoxic regions)
- Food collection → Drug delivery
- Home/Nest → Blood vessels (drug reload points)
- Pheromone trails → Successful delivery paths
- Alarm pheromones → Toxicity or navigation failures
"""

import numpy as np
import random
from typing import Dict, List, Tuple, Optional
from enum import Enum
import openai
import os
from dotenv import load_dotenv

from biofvm import Microenvironment
from tumor_environment import TumorGeometry, TumorCell, VesselPoint, CellPhase

load_dotenv()
IO_API_KEY = os.getenv("IO_SECRET_KEY")


class NanobotState(Enum):
    """States a nanobot can be in."""
    SEARCHING = "searching"      # Looking for hypoxic tumor regions
    TARGETING = "targeting"       # Moving toward locked target
    DELIVERING = "delivering"     # Releasing drug payload
    RETURNING = "returning"       # Going back to vessel to reload
    RELOADING = "reloading"      # At vessel, refilling drug


class NanobotAgent:
    """
    A single nanobot agent that navigates the tumor microenvironment.
    
    Adapted from SimpleAntAgent in simulation.py, but now operates in
    continuous space with chemotaxis toward substrate gradients.
    """
    
    def __init__(
        self,
        nanobot_id: int,
        model: 'TumorNanobotModel',
        is_llm_controlled: bool = True
    ):
        self.nanobot_id = nanobot_id
        self.model = model
        self.is_llm_controlled = is_llm_controlled
        
        # Start near a random vessel
        if model.geometry.vessels:
            start_vessel = random.choice(model.geometry.vessels)
            # Add small random offset
            offset = np.random.randn(2) * 20.0  # 20 µm std dev
            self.position = np.array([
                start_vessel.position[0] + offset[0],
                start_vessel.position[1] + offset[1],
                0.0  # 2D for now
            ])
        else:
            # Random position if no vessels
            self.position = np.array([
                np.random.uniform(model.microenv.x_range[0], model.microenv.x_range[1]),
                np.random.uniform(model.microenv.y_range[0], model.microenv.y_range[1]),
                0.0
            ])
        
        # Nanobot properties
        self.state = NanobotState.SEARCHING
        self.drug_payload = 100.0  # Start full
        self.max_payload = 100.0
        self.speed = 10.0  # µm per step
        
        # Chemotaxis weights (how much each gradient influences movement)
        self.chemotaxis_weights = {
            'oxygen': -1.0,      # Move TOWARD low oxygen (hypoxic tumor)
            'trail': 0.8,        # Follow successful delivery trails
            'alarm': -0.5,       # Avoid alarm pheromones
            'recruitment': 0.6,  # Respond to recruitment signals
        }
        
        # Target tracking
        self.target_cell: Optional[TumorCell] = None
        self.target_vessel: Optional[VesselPoint] = None
        
        # Performance metrics
        self.deliveries_made = 0
        self.total_drug_delivered = 0.0
        self.api_calls = 0
        self.move_history: List[Tuple[float, float]] = []
        
    def step(self, guidance: Optional[Dict] = None):
        """
        Execute one timestep of nanobot behavior.
        
        Args:
            guidance: Optional guidance from Queen nanobot
        """
        # Record position history
        self.move_history.append(tuple(self.position[:2]))
        
        # State machine
        if self.state == NanobotState.RELOADING:
            self._reload_drug()
        elif self.state == NanobotState.DELIVERING:
            self._deliver_drug()
        elif self.state == NanobotState.RETURNING:
            self._return_to_vessel()
        elif self.state == NanobotState.TARGETING:
            self._move_toward_target()
        else:  # SEARCHING
            self._search_for_target(guidance)
    
    def _search_for_target(self, guidance: Optional[Dict] = None):
        """
        Search for hypoxic tumor cells to target.
        Uses chemotaxis and pheromone guidance.
        """
        # Check if we have guidance from Queen
        if guidance and self.nanobot_id in guidance:
            guided_direction = guidance[self.nanobot_id]
            self.position += guided_direction * self.speed
            self._clamp_position()
            return
        
        # LLM-based decision making
        if self.is_llm_controlled and self.model.io_client and self.model.api_enabled:
            try:
                action = self._ask_llm_for_decision()
                self.api_calls += 1
                
                if action == "target":
                    # Try to lock onto nearby hypoxic cell
                    target_cell = self._find_nearest_hypoxic_cell()
                    if target_cell:
                        self.target_cell = target_cell
                        self.state = NanobotState.TARGETING
                        return
                elif action == "follow_trail":
                    # Follow pheromone trail
                    direction = self._compute_pheromone_direction()
                    if np.linalg.norm(direction) > 0:
                        direction = direction / np.linalg.norm(direction)
                        self.position += direction * self.speed
                        self._clamp_position()
                        return
                # "explore" or other → use chemotaxis
            except Exception as e:
                self.model.log_error(f"Nanobot {self.nanobot_id} LLM call failed: {str(e)}")
                # Deposit alarm pheromone on error
                voxel = self.model.microenv.position_to_voxel(tuple(self.position))
                alarm = self.model.microenv.get_substrate('alarm')
                if alarm:
                    alarm.add_source(voxel, 5.0)
        
        # Default behavior: chemotaxis-based movement
        direction = self._compute_chemotaxis_direction()
        if np.linalg.norm(direction) > 0:
            direction = direction / np.linalg.norm(direction)
            self.position[:2] += direction * self.speed
        else:
            # Random walk if no gradient, but stay within tumor
            if self._is_within_tumor_boundary():
                angle = np.random.uniform(0, 2 * np.pi)
                self.position[0] += self.speed * np.cos(angle)
                self.position[1] += self.speed * np.sin(angle)
            else:
                # Move toward tumor center if outside
                tumor_center = np.array(self.model.geometry.center[:2])
                direction_to_center = tumor_center - self.position[:2]
                direction_to_center = direction_to_center / np.linalg.norm(direction_to_center)
                self.position[:2] += direction_to_center * self.speed
        
        self._clamp_position()
        
        # Check if we're now near a hypoxic cell
        nearby_cell = self._find_nearest_hypoxic_cell(max_distance=30.0)
        if nearby_cell and self.drug_payload > 10.0:
            self.target_cell = nearby_cell
            self.state = NanobotState.TARGETING
    
    def _compute_chemotaxis_direction(self) -> np.ndarray:
        """
        Compute movement direction based on multiple substrate gradients.
        
        Returns:
            Direction vector (not normalized)
        """
        total_direction = np.zeros(2)
        
        for substrate_name, weight in self.chemotaxis_weights.items():
            substrate = self.model.microenv.get_substrate(substrate_name)
            if substrate:
                gradient = self.model.microenv.get_gradient_at(substrate_name, tuple(self.position))
                total_direction += weight * gradient[:2]
        
        return total_direction
    
    def _compute_pheromone_direction(self) -> np.ndarray:
        """Compute direction based only on pheromone trails."""
        direction = np.zeros(2)
        
        trail = self.model.microenv.get_substrate('trail')
        if trail:
            gradient = self.model.microenv.get_gradient_at('trail', tuple(self.position))
            direction = gradient[:2]
        
        return direction
    
    def _find_nearest_hypoxic_cell(self, max_distance: float = 100.0) -> Optional[TumorCell]:
        """
        Find nearest hypoxic tumor cell within range and within tumor boundary.
        
        Args:
            max_distance: Maximum search radius (µm)
            
        Returns:
            Nearest hypoxic TumorCell or None
        """
        hypoxic_cells = [
            cell for cell in self.model.geometry.get_living_cells()
            if cell.phase == CellPhase.HYPOXIC
        ]
        
        if not hypoxic_cells:
            return None
        
        # Filter cells to only those within tumor boundary
        tumor_center = np.array(self.model.geometry.center[:2])
        tumor_radius = self.model.geometry.tumor_radius
        
        valid_cells = []
        for cell in hypoxic_cells:
            cell_pos = np.array(cell.position[:2])
            distance_from_center = np.linalg.norm(cell_pos - tumor_center)
            if distance_from_center <= tumor_radius:
                valid_cells.append(cell)
        
        if not valid_cells:
            return None
        
        # Calculate distances to valid cells only
        distances = [
            np.linalg.norm(np.array(cell.position[:2]) - self.position[:2])
            for cell in valid_cells
        ]
        
        min_dist = min(distances)
        if min_dist <= max_distance:
            return valid_cells[distances.index(min_dist)]
        
        return None
    
    def _move_toward_target(self):
        """Move toward locked target cell."""
        if not self.target_cell or not self.target_cell.is_alive:
            # Target lost, go back to searching
            self.target_cell = None
            self.state = NanobotState.SEARCHING
            return
        
        target_pos = np.array(self.target_cell.position[:2])
        direction = target_pos - self.position[:2]
        distance = np.linalg.norm(direction)
        
        if distance < 5.0:  # Close enough to deliver
            self.state = NanobotState.DELIVERING
        else:
            direction = direction / distance
            self.position[:2] += direction * self.speed
            self._clamp_position()
    
    def _deliver_drug(self):
        """Deliver drug payload to target cell."""
        if not self.target_cell or not self.target_cell.is_alive:
            self.target_cell = None
            self.state = NanobotState.SEARCHING
            return
        
        # Release drug into microenvironment at this location
        voxel = self.model.microenv.position_to_voxel(tuple(self.position))
        drug = self.model.microenv.get_substrate('drug')
        
        if drug and self.drug_payload > 0:
            delivery_amount = min(self.drug_payload, 20.0)  # 20 units per step
            drug.add_source(voxel, delivery_amount)
            self.drug_payload -= delivery_amount
            self.total_drug_delivered += delivery_amount
            
            # Deposit trail pheromone (mark successful delivery path)
            trail = self.model.microenv.get_substrate('trail')
            if trail:
                trail.add_source(voxel, 3.0)
        
        # If payload depleted, return to vessel
        if self.drug_payload < 10.0:
            self.deliveries_made += 1
            self.target_cell = None
            self.target_vessel = self.model.geometry.find_nearest_vessel(tuple(self.position))
            self.state = NanobotState.RETURNING
        else:
            # Continue delivering
            pass
    
    def _return_to_vessel(self):
        """Navigate back to nearest vessel to reload."""
        if not self.target_vessel:
            self.target_vessel = self.model.geometry.find_nearest_vessel(tuple(self.position))
        
        if not self.target_vessel:
            # No vessels available, just search
            self.state = NanobotState.SEARCHING
            return
        
        vessel_pos = np.array(self.target_vessel.position[:2])
        direction = vessel_pos - self.position[:2]
        distance = np.linalg.norm(direction)
        
        if distance < 10.0:  # At vessel
            self.state = NanobotState.RELOADING
        else:
            direction = direction / distance
            self.position[:2] += direction * self.speed
            self._clamp_position()
    
    def _reload_drug(self):
        """Reload drug payload at vessel."""
        reload_rate = 20.0  # Units per step
        self.drug_payload = min(self.drug_payload + reload_rate, self.max_payload)
        
        if self.drug_payload >= self.max_payload * 0.9:  # 90% full
            self.target_vessel = None
            self.state = NanobotState.SEARCHING
    
    def _clamp_position(self):
        """Keep nanobot within simulation boundaries and tumor constraints."""
        # First, clamp to simulation domain
        self.position[0] = np.clip(
            self.position[0],
            self.model.microenv.x_range[0],
            self.model.microenv.x_range[1]
        )
        self.position[1] = np.clip(
            self.position[1],
            self.model.microenv.y_range[0],
            self.model.microenv.y_range[1]
        )
        
        # CRITICAL: Enforce tumor boundary constraints
        self._enforce_tumor_boundary()
    
    def _enforce_tumor_boundary(self):
        """
        Enforce nanobot boundary constraints:
        - Must stay within tumor boundary (red area) when treating
        - Can only leave tumor to go to blood vessels (green areas) for reloading
        """
        pos_2d = self.position[:2]
        tumor_center = np.array(self.model.geometry.center[:2])
        distance_from_center = np.linalg.norm(pos_2d - tumor_center)
        
        # Check if we're in a valid state to be outside tumor
        can_be_outside = (
            self.state == NanobotState.RETURNING or 
            self.state == NanobotState.RELOADING or
            self.drug_payload < 20.0  # Low on drugs, need to reload
        )
        
        # If we're outside tumor boundary and shouldn't be, move back in
        if distance_from_center > self.model.geometry.tumor_radius:
            if not can_be_outside:
                # Force nanobot back into tumor boundary
                direction_to_center = tumor_center - pos_2d
                direction_to_center = direction_to_center / np.linalg.norm(direction_to_center)
                
                # Move to edge of tumor boundary
                edge_position = tumor_center + direction_to_center * (self.model.geometry.tumor_radius - 5.0)
                self.position[0] = edge_position[0]
                self.position[1] = edge_position[1]
                
                # If we were targeting something outside, cancel it
                if self.target_cell:
                    self.target_cell = None
                    self.state = NanobotState.SEARCHING
            else:
                # We're allowed to be outside (returning to vessel), but check if we're near a vessel
                if self.state == NanobotState.RETURNING:
                    # Make sure we're actually heading toward a vessel
                    nearest_vessel = self.model.geometry.find_nearest_vessel(tuple(self.position))
                    if nearest_vessel:
                        vessel_pos = np.array(nearest_vessel.position[:2])
                        vessel_distance = np.linalg.norm(pos_2d - vessel_pos)
                        
                        # If we're far from any vessel, redirect toward nearest one
                        if vessel_distance > 100.0:  # 100 µm threshold
                            direction_to_vessel = vessel_pos - pos_2d
                            direction_to_vessel = direction_to_vessel / np.linalg.norm(direction_to_vessel)
                            self.position[:2] += direction_to_vessel * self.speed * 0.5
    
    def _is_within_tumor_boundary(self) -> bool:
        """Check if nanobot is within the tumor boundary (red area)."""
        pos_2d = self.position[:2]
        tumor_center = np.array(self.model.geometry.center[:2])
        distance_from_center = np.linalg.norm(pos_2d - tumor_center)
        return distance_from_center <= self.model.geometry.tumor_radius
    
    def _ask_llm_for_decision(self) -> str:
        """
        Query LLM for high-level strategy decision.
        
        Returns:
            Action string: 'target', 'follow_trail', 'explore', 'return'
        """
        # Get local environmental information
        oxygen = self.model.microenv.get_concentration_at('oxygen', tuple(self.position))
        drug = self.model.microenv.get_concentration_at('drug', tuple(self.position))
        trail = self.model.microenv.get_concentration_at('trail', tuple(self.position))
        alarm = self.model.microenv.get_concentration_at('alarm', tuple(self.position))
        
        # Find nearby hypoxic cells
        nearby_hypoxic = len([
            c for c in self.model.geometry.get_cells_in_phase(CellPhase.HYPOXIC)
            if np.linalg.norm(np.array(c.position[:2]) - self.position[:2]) < 50.0
        ])
        
        prompt = f"""You are a nanobot carrying anti-cancer drugs through a tumor.
        
Current status:
- Position: ({self.position[0]:.1f}, {self.position[1]:.1f}) µm
- Drug payload: {self.drug_payload:.1f}/{self.max_payload} units
- Deliveries made: {self.deliveries_made}

Local environment:
- Oxygen: {oxygen:.2f} mmHg (low oxygen = tumor hypoxia, good target)
- Drug concentration: {drug:.2f} (already treated area?)
- Trail pheromone: {trail:.2f} (successful delivery paths)
- Alarm pheromone: {alarm:.2f} (problems reported here)
- Nearby hypoxic cells: {nearby_hypoxic}

Actions:
- 'target': Lock onto nearby hypoxic tumor cell
- 'follow_trail': Follow pheromone trail to known good areas  
- 'explore': Use chemotaxis to explore new regions
- 'return': Return to blood vessel to reload

What should you do? Respond with ONE word only."""

        try:
            response = self.model.io_client.chat.completions.create(
                model=self.model.selected_model,
                messages=[
                    {"role": "system", "content": "You are an intelligent nanobot. Respond with one word: target, follow_trail, explore, or return."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_completion_tokens=10,
                timeout=10
            )
            action = response.choices[0].message.content.strip().lower()
            return action if action in ['target', 'follow_trail', 'explore', 'return'] else 'explore'
        except Exception as e:
            return 'explore'
    
    def to_dict(self) -> Dict:
        """Convert nanobot to dictionary for serialization."""
        return {
            'id': self.nanobot_id,
            'position': tuple(self.position[:2]),
            'state': self.state.value,
            'drug_payload': self.drug_payload,
            'deliveries_made': self.deliveries_made,
            'total_drug_delivered': self.total_drug_delivered,
            'is_llm': self.is_llm_controlled,
            'has_target': self.target_cell is not None
        }


class QueenNanobot:
    """
    Queen overseer that provides high-level swarm strategy.
    
    Adapted from QueenAnt in simulation.py. Operates at episodic level
    (every K steps) to adjust swarm parameters.
    """
    
    def __init__(self, model: 'TumorNanobotModel', use_llm: bool = False):
        self.model = model
        self.use_llm = use_llm
        
    def guide(self) -> Dict[int, np.ndarray]:
        """
        Provide strategic guidance to nanobots.
        
        Returns:
            Dictionary mapping nanobot_id to direction vector
        """
        if self.use_llm and self.model.io_client and self.model.api_enabled:
            return self._guide_with_llm()
        else:
            return self._guide_with_heuristic()
    
    def _guide_with_heuristic(self) -> Dict[int, np.ndarray]:
        """Simple heuristic guidance based on tumor statistics."""
        guidance = {}
        
        # Find regions with high hypoxic cell density
        hypoxic_cells = self.model.geometry.get_cells_in_phase(CellPhase.HYPOXIC)
        
        if not hypoxic_cells:
            return guidance
        
        # Direct nanobots toward hypoxic regions
        for nanobot in self.model.nanobots:
            if nanobot.state == NanobotState.SEARCHING and nanobot.drug_payload > 20.0:
                # Find nearest hypoxic cell
                distances = [
                    np.linalg.norm(np.array(cell.position[:2]) - nanobot.position[:2])
                    for cell in hypoxic_cells
                ]
                
                if distances:
                    nearest_cell = hypoxic_cells[np.argmin(distances)]
                    direction = np.array(nearest_cell.position[:2]) - nanobot.position[:2]
                    distance = np.linalg.norm(direction)
                    
                    if distance > 0:
                        guidance[nanobot.nanobot_id] = direction / distance
        
        return guidance
    
    def _guide_with_llm(self) -> Dict[int, np.ndarray]:
        """LLM-based strategic guidance."""
        # TODO: Implement LLM queen guidance similar to QueenAnt
        # For now, fall back to heuristic
        return self._guide_with_heuristic()


class TumorNanobotModel:
    """
    Main simulation model integrating nanobots, tumor, and microenvironment.
    
    Adapted from SimpleForagingModel but operates in continuous space
    with substrate diffusion.
    """
    
    def __init__(
        self,
        domain_size: float = 600.0,  # µm
        voxel_size: float = 10.0,    # µm
        n_nanobots: int = 10,
        tumor_radius: float = 200.0,
        agent_type: str = "LLM-Powered",
        with_queen: bool = False,
        use_llm_queen: bool = False,
        selected_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    ):
        self.domain_size = domain_size
        self.voxel_size = voxel_size
        self.selected_model = selected_model
        self.with_queen = with_queen
        self.use_llm_queen = use_llm_queen
        
        print(f"\n[TUMOR MODEL] Initializing tumor nanobot simulation...")
        print(f"  Domain: {domain_size} x {domain_size} µm")
        print(f"  Voxel size: {voxel_size} µm")
        print(f"  Nanobots: {n_nanobots}")
        
        # Initialize microenvironment
        self.microenv = Microenvironment(
            x_range=(0, domain_size),
            y_range=(0, domain_size),
            z_range=(0, domain_size),
            dx=voxel_size,
            dy=voxel_size,
            dz=voxel_size,
            dimensionality=2
        )
        
        # Add substrates
        from biofvm import create_oxygen_substrate, create_drug_substrate, create_pheromone_substrate
        
        create_oxygen_substrate(self.microenv, boundary_value=38.0)
        create_drug_substrate(self.microenv, diffusion_coeff=1e-7)
        create_pheromone_substrate(self.microenv, 'trail', decay_rate=0.1)
        create_pheromone_substrate(self.microenv, 'alarm', decay_rate=0.15)
        create_pheromone_substrate(self.microenv, 'recruitment', decay_rate=0.12)
        
        # Generate tumor geometry
        from tumor_environment import create_simple_tumor_environment
        
        self.geometry = create_simple_tumor_environment(
            domain_size=domain_size,
            tumor_radius=tumor_radius,
            cell_density=0.001,
            dimensionality=2
        )
        
        # Initialize nanobots
        self.nanobots: List[NanobotAgent] = []
        is_llm = agent_type == "LLM-Powered"
        
        for i in range(n_nanobots):
            if agent_type == "Hybrid":
                is_llm = i < n_nanobots // 2
            
            nanobot = NanobotAgent(i, self, is_llm_controlled=is_llm)
            self.nanobots.append(nanobot)
        
        # Initialize errors list first (needed for log_error calls)
        self.errors: List[str] = []
        
        # Initialize Queen
        self.queen = QueenNanobot(self, use_llm=use_llm_queen) if with_queen else None
        
        # Initialize IO client
        self.api_enabled = False
        if IO_API_KEY:
            try:
                self.io_client = openai.OpenAI(
                    api_key=IO_API_KEY,
                    base_url="https://api.intelligence.io.solutions/api/v1/"
                )
                self.api_enabled = True
                print("[TUMOR MODEL] LLM API initialized successfully")
            except Exception as e:
                self.io_client = None
                self.log_error(f"Failed to initialize LLM API: {str(e)}")
        else:
            self.io_client = None
            self.log_error("IO_SECRET_KEY not found. LLM features disabled.")
        
        # Metrics tracking
        self.step_count = 0
        self.metrics = {
            'total_deliveries': 0,
            'total_drug_delivered': 0.0,
            'cells_killed': 0,
            'hypoxic_cells': len(self.geometry.get_cells_in_phase(CellPhase.HYPOXIC)),
            'viable_cells': len(self.geometry.get_cells_in_phase(CellPhase.VIABLE)),
            'necrotic_cells': len(self.geometry.get_cells_in_phase(CellPhase.NECROTIC)),
            'apoptotic_cells': len(self.geometry.get_cells_in_phase(CellPhase.APOPTOTIC)),
            'total_api_calls': 0
        }
        self.queen_report = "Queen initialized" if self.queen else "No queen active"
        
        print(f"[TUMOR MODEL] Initialization complete!")
        print(f"  Tumor cells: {len(self.geometry.tumor_cells)}")
        print(f"  Blood vessels: {len(self.geometry.vessels)}")
        print(f"  Nanobots: {len(self.nanobots)}")
    
    def step(self):
        """Execute one simulation timestep."""
        self.step_count += 1
        
        # Reset substrate sources/sinks
        self.microenv.reset_all_sources_sinks()
        
        # Update tumor cells (oxygen consumption, drug absorption)
        self._update_tumor_cells()
        
        # Apply vessel sources
        self._apply_vessel_sources()
        
        # Get Queen guidance
        guidance = {}
        if self.queen and self.step_count % 10 == 0:  # Queen acts every 10 steps
            try:
                guidance = self.queen.guide()
            except Exception as e:
                self.log_error(f"Queen guidance failed: {str(e)}")
        
        # Update nanobots
        for nanobot in self.nanobots:
            nanobot.step(guidance)
            if nanobot.is_llm_controlled:
                self.metrics['total_api_calls'] += nanobot.api_calls
                nanobot.api_calls = 0
        
        # Simulate microenvironment diffusion
        self.microenv.step()
        
        # Update metrics
        self._update_metrics()
    
    def _update_tumor_cells(self):
        """Update all tumor cells based on local microenvironment."""
        for cell in self.geometry.tumor_cells:
            if not cell.is_alive:
                continue
            
            # Get local oxygen and drug concentrations
            oxygen = self.microenv.get_concentration_at('oxygen', cell.position)
            drug = self.microenv.get_concentration_at('drug', cell.position)
            
            # Update cell state
            cell.update_oxygen_status(oxygen, self.microenv.dt)
            cell.absorb_drug(drug, self.microenv.dt)
            
            # Add oxygen consumption as sink
            voxel = self.microenv.position_to_voxel(cell.position)
            oxygen_substrate = self.microenv.get_substrate('oxygen')
            if oxygen_substrate:
                oxygen_substrate.add_sink(voxel, cell.get_oxygen_consumption() * self.microenv.dt)
    
    def _apply_vessel_sources(self):
        """Apply oxygen and drug sources from blood vessels."""
        oxygen_substrate = self.microenv.get_substrate('oxygen')
        
        for vessel in self.geometry.vessels:
            voxel = self.microenv.position_to_voxel(vessel.position)
            
            # Vessels supply oxygen
            if oxygen_substrate:
                oxygen_substrate.add_source(voxel, vessel.oxygen_supply * 0.5)
    
    def _update_metrics(self):
        """Update simulation metrics."""
        # Count cells by phase
        self.metrics['hypoxic_cells'] = len(self.geometry.get_cells_in_phase(CellPhase.HYPOXIC))
        self.metrics['viable_cells'] = len(self.geometry.get_cells_in_phase(CellPhase.VIABLE))
        self.metrics['necrotic_cells'] = len(self.geometry.get_cells_in_phase(CellPhase.NECROTIC))
        self.metrics['apoptotic_cells'] = len(self.geometry.get_cells_in_phase(CellPhase.APOPTOTIC))
        
        # Count killed cells (apoptotic only, not natural necrosis)
        self.metrics['cells_killed'] = self.metrics['apoptotic_cells']
        
        # Nanobot metrics
        self.metrics['total_deliveries'] = sum(n.deliveries_made for n in self.nanobots)
        self.metrics['total_drug_delivered'] = sum(n.total_drug_delivered for n in self.nanobots)
    
    def log_error(self, message: str):
        """Log an error message."""
        self.errors.append(message)
        print(f"[TUMOR MODEL] {message}")

