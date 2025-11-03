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
import threading
from biofvm import Microenvironment
from tumor_environment import TumorGeometry, TumorCell, VesselPoint, CellPhase, CellType

load_dotenv()
IO_API_KEY = os.getenv("IO_SECRET_KEY")

# Blockchain integration
try:
    # Add parent directory to path to find blockchain module
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    
    from blockchain.client import w3, acct, tumor_intel_contract, TUMOR_INTEL_CONTRACT_ADDRESS
    BLOCKCHAIN_ENABLED = tumor_intel_contract is not None
    if BLOCKCHAIN_ENABLED:
        print("[NANOBOT] ✅ Blockchain intelligence sharing enabled")
    else:
        print("[NANOBOT] ⚠️ Blockchain client loaded but TumorIntel contract not available")
except Exception as e:
    BLOCKCHAIN_ENABLED = False
    print(f"[NANOBOT] ⚠️ Blockchain disabled: {e}")


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
        
        # Nanobot properties (medically realistic values)
        self.state = NanobotState.SEARCHING
        self.drug_payload = 20.0  # Start with 20 μg payload (effective for direct delivery)
        self.max_payload = 20.0   # 20 μg total capacity (effective for simulation)
        self.speed = 30.0  # µm per step (movement speed)
        
        # Chemotaxis weights (how much each gradient influences movement)
        self.chemotaxis_weights = {
            'oxygen': -1.0,           # Move TOWARD low oxygen (hypoxic tumor)
            'trail': 0.8,             # Follow successful delivery trails
            'alarm': -0.5,            # Avoid alarm pheromones
            'recruitment': 0.6,       # Respond to recruitment signals
            'chemokine_signal': 1.2,  # Strong attraction to "come here" signals
            'toxicity_signal': -1.5,  # Strong repulsion from "stay away" signals
        }
        
        # Target tracking
        self.target_cell: Optional[TumorCell] = None
        self.target_vessel: Optional[VesselPoint] = None
        
        # Performance metrics
        self.deliveries_made = 0
        self.total_drug_delivered = 0.0
        self.api_calls = 0
        self.move_history: List[Tuple[float, float]] = []
        
        # Movement inertia for smoother navigation
        self.previous_direction = np.zeros(2)
        
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
        Search for tumor cells to target.
        Prioritizes nearest living cell for drug delivery.
        """
        # FIRST PRIORITY: Check for nearby targets immediately
        nearby_cell = self._find_nearest_living_cell(max_distance=100.0)  # Updated to find any living cell
        if nearby_cell and self.drug_payload > 2.0:
            self.target_cell = nearby_cell
            self.state = NanobotState.TARGETING
            
            # New Blockchain Event: Report new target acquired
            self._report_intel_to_blockchain(
                pin_type=5,  # TARGET_ACQUIRED
                x=self.target_cell.position[0],
                y=self.target_cell.position[1],
                priority=5
            )
            return
        
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
                    target_cell = self._find_nearest_hypoxic_cell(max_distance=120.0)  # Increased for LLM
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
        
        # Default behavior: chemotaxis-based movement with inertia and stochasticity
        direction = self._compute_chemotaxis_direction()
        if np.linalg.norm(direction) > 0:
            direction = direction / np.linalg.norm(direction)
            
            # Add inertia: blend new direction with previous direction (70% new, 30% old)
            inertial_direction = 0.7 * direction + 0.3 * self.previous_direction
            
            # Add stochasticity: small random noise to break oscillation loops
            random_vector = np.random.randn(2) * 0.1
            final_direction = inertial_direction + random_vector
            
            # Normalize and apply movement
            if np.linalg.norm(final_direction) > 0:
                final_direction = final_direction / np.linalg.norm(final_direction)
            
            self.position[:2] += final_direction * self.speed
            self.previous_direction = final_direction
        else:
            # Random walk if no gradient, but stay within tumor
            if self._is_within_tumor_boundary():
                angle = np.random.uniform(0, 2 * np.pi)
                random_direction = np.array([np.cos(angle), np.sin(angle)])
                self.position[0] += self.speed * random_direction[0]
                self.position[1] += self.speed * random_direction[1]
                self.previous_direction = random_direction
            else:
                # Move toward tumor center if outside
                tumor_center = np.array(self.model.geometry.center[:2])
                direction_to_center = tumor_center - self.position[:2]
                direction_to_center = direction_to_center / np.linalg.norm(direction_to_center)
                self.position[:2] += direction_to_center * self.speed
                self.previous_direction = direction_to_center
        
        self._clamp_position()
    
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
    
    def _find_nearest_hypoxic_cell(self, max_distance: float = 150.0) -> Optional[TumorCell]:
        """
        Find nearest hypoxic tumor cell within range and within tumor boundary.
        
        Args:
            max_distance: Maximum search radius (µm) - increased for better targeting
            
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
        
        min_dist = min(distances) if distances else float('inf')
        if min_dist <= max_distance:
            target_cell = valid_cells[distances.index(min_dist)]
            
            # Report hypoxic cluster discovery to blockchain
            pin_type = 0  # HYPOXIC_CLUSTER
            priority = 8 if target_cell.cell_type == CellType.STEM_CELL else 6
            self._report_intel_to_blockchain(pin_type, target_cell.position[0], target_cell.position[1], priority)
            
            return target_cell
        
        return None
    
    def _find_nearest_living_cell(self, max_distance: float = 150.0) -> Optional[TumorCell]:
        """
        Find nearest living tumor cell within range (prioritizes closest, not hypoxic status).
        
        Args:
            max_distance: Maximum search radius (µm)
            
        Returns:
            Nearest living TumorCell or None
        """
        living_cells = self.model.geometry.get_living_cells()
        
        if not living_cells:
            return None
        
        # Filter cells to only those within tumor boundary
        tumor_center = np.array(self.model.geometry.center[:2])
        tumor_radius = self.model.geometry.tumor_radius
        
        valid_cells = []
        for cell in living_cells:
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
        
        min_dist = min(distances) if distances else float('inf')
        if min_dist <= max_distance:
            target_cell = valid_cells[distances.index(min_dist)]
            return target_cell
        
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
        
        if distance < 30.0:  # Close enough to deliver (increased from 15µm to 30µm for better reach)
            self.state = NanobotState.DELIVERING
        else:
            direction = direction / distance
            self.position[:2] += direction * self.speed
            self._clamp_position()
    
    def _report_intel_to_blockchain(self, pin_type: int, x: float, y: float, priority: int):
        """
        Report intelligence to the blockchain for swarm coordination.
        
        Args:
            pin_type: Type of intel (0=HYPOXIC_CLUSTER, 1=STEM_CELL_DETECTED, etc.)
            x, y: Coordinates in micrometers
            priority: Priority level (1-10)
        """
        if not BLOCKCHAIN_ENABLED:
            print(f"[NANOBOT {self.nanobot_id}] ⚠️ Blockchain not enabled globally")
            return
            
        if not self.model.blockchain_enabled:
            print(f"[NANOBOT {self.nanobot_id}] ⚠️ Blockchain not enabled in model")
            return
        
        pin_type_names = {
            0: "HYPOXIC_CLUSTER",
            1: "STEM_CELL_DETECTED",
            2: "HIGH_RESISTANCE",
            3: "IMMUNE_ACTIVE",
            4: "SUCCESSFUL_KILL",
            5: "TARGET_ACQUIRED",
            6: "DRUG_DELIVERY"
        }
        pin_name = pin_type_names.get(pin_type, f"UNKNOWN_{pin_type}")
        
        print(f"[NANOBOT {self.nanobot_id}] 🔄 Attempting blockchain report: {pin_name} at ({int(x)}, {int(y)}) priority={priority}")
        
        try:
            # Pre-transaction validation checks
            if not tumor_intel_contract:
                raise Exception("tumor_intel_contract is None - contract not initialized")
            if not TUMOR_INTEL_CONTRACT_ADDRESS:
                raise Exception("TUMOR_INTEL_CONTRACT_ADDRESS is None - check .env file")
            if not w3.is_connected():
                raise Exception("Web3 not connected to RPC")
            
            # Check account balance before attempting transaction
            balance_wei = w3.eth.get_balance(acct.address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            print(f"[NANOBOT {self.nanobot_id}]   Account balance: {balance_eth:.6f} ETH ({acct.address})")
            
            if balance_eth == 0:
                raise Exception(f"Account has 0 ETH. Transactions will fail. Please fund the account: {acct.address}")
            
            # Use centralized nonce manager to prevent conflicts
            with self.model.nonce_lock:
                nonce = self.model.current_nonce
                self.model.current_nonce += 1
            
            # Get current gas price and add buffer to avoid underpricing
            base_gas_price = w3.eth.gas_price
            gas_price = int(base_gas_price * 1.1)
            
            # Get current chain ID
            chain_id = w3.eth.chain_id
            print(f"[NANOBOT {self.nanobot_id}]   Building transaction: nonce={nonce}, gas_price={gas_price} (base: {base_gas_price}), chainId={chain_id}")
            
            txn = tumor_intel_contract.functions.reportIntel(
                int(x), int(y), pin_type, priority
            ).build_transaction({
                'from': acct.address,
                'nonce': nonce,
                'gas': 200000,
                'gasPrice': gas_price,
                'chainId': chain_id,  # Add chainId to match network
            })
            
            # Sign and send
            print(f"[NANOBOT {self.nanobot_id}]   Signing transaction...")
            signed = acct.sign_transaction(txn)
            
            # Use raw_transaction (snake_case) for newer web3.py versions, with fallback
            raw_tx = signed.raw_transaction if hasattr(signed, 'raw_transaction') else signed.rawTransaction
            print(f"[NANOBOT {self.nanobot_id}]   Sending raw transaction to network...")
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            
            print(f"[NANOBOT {self.nanobot_id}]   Transaction hash: {tx_hash.hex()}")
            print(f"[NANOBOT {self.nanobot_id}]   Transaction URL: https://sepolia.basescan.org/tx/{tx_hash.hex()}")
            
            # Wait for transaction receipt to confirm it was mined
            print(f"[NANOBOT {self.nanobot_id}]   Waiting for transaction confirmation...")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                print(f"[NANOBOT {self.nanobot_id}] ✅ Intel reported to blockchain! (Gas used: {receipt['gasUsed']})")
            else:
                raise Exception(f"Transaction failed with status: {receipt['status']}")
            
            # Add to model's blockchain logs
            if hasattr(self.model, 'blockchain_logs'):
                self.model.blockchain_logs.append(f"Nanobot {self.nanobot_id}: {pin_name} at ({int(x)}, {int(y)}) - tx: {tx_hash.hex()[:10]}...")
                
        except Exception as e:
            print(f"[NANOBOT {self.nanobot_id}] ❌ Failed to report intel: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
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
            delivery_amount = min(self.drug_payload, 3.0)  # 3 μg per delivery (increased for more effective killing)
            drug.add_source(voxel, delivery_amount)
            self.drug_payload -= delivery_amount
            self.total_drug_delivered += delivery_amount
            
            # Count delivery immediately when drug is released
            self.deliveries_made += 1
            
            # New Blockchain Event: Report every drug delivery
            self._report_intel_to_blockchain(
                pin_type=6,  # DRUG_DELIVERY
                x=self.position[0],
                y=self.position[1],
                priority=4
            )
            
            # Directly accumulate drug to target cell (bypassing diffusion for immediate effect)
            cell_killed = self.target_cell.accumulate_drug(delivery_amount)
            
            # Report successful kill to blockchain if cell was eliminated
            if cell_killed:
                pin_type = 4  # SUCCESSFUL_KILL
                priority = 7 if self.target_cell.cell_type == CellType.STEM_CELL else 5
                self._report_intel_to_blockchain(pin_type, self.position[0], self.position[1], priority)
            
            # Deposit trail pheromone (mark successful delivery path)
            trail = self.model.microenv.get_substrate('trail')
            if trail:
                trail.add_source(voxel, 3.0)
            
            # Emit chemokine signal to attract other nanobots to this successful delivery site
            chemokine = self.model.microenv.get_substrate('chemokine_signal')
            if chemokine:
                chemokine.add_source(voxel, 4.0)  # Strong "come here" signal
        
        # If payload depleted, return to vessel
        if self.drug_payload < 2.0:  # Return when < 2 μg remaining
            self.target_cell = None
            self.target_vessel = self.model.geometry.find_nearest_vessel(tuple(self.position))
            self.state = NanobotState.RETURNING
        else:
            # Continue delivering to same target
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
        """Reload drug payload at vessel (effective reload rate)."""
        reload_rate = 5.0  # 5 μg per step (effective reload rate)
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
        - Allow entry into tumor when targeting
        - Can leave tumor to go to blood vessels for reloading
        - Prevent wandering outside tumor when not on a mission
        """
        pos_2d = self.position[:2]
        tumor_center = np.array(self.model.geometry.center[:2])
        distance_from_center = np.linalg.norm(pos_2d - tumor_center)
        
        # Check if we're in a valid state to be outside tumor
        can_be_outside = (
            self.state == NanobotState.RETURNING or 
            self.state == NanobotState.RELOADING or
            self.drug_payload < 10.0  # Low on drugs, need to reload
        )
        
        # Allow entry when actively targeting (TARGETING or DELIVERING state)
        is_actively_targeting = (
            self.state == NanobotState.TARGETING or 
            self.state == NanobotState.DELIVERING
        )
        
        # If we're outside tumor boundary, decide what to do
        if distance_from_center > self.model.geometry.tumor_radius:
            # Allow entry if actively targeting a cell inside tumor
            if is_actively_targeting and self.target_cell:
                # Check if target is inside tumor - if so, allow crossing boundary
                target_pos = np.array(self.target_cell.position[:2])
                target_distance_from_center = np.linalg.norm(target_pos - tumor_center)
                if target_distance_from_center <= self.model.geometry.tumor_radius:
                    # Target is inside tumor, allow nanobot to enter
                    return  # Don't constrain movement
            
            # Not actively targeting or target is outside tumor
            if not can_be_outside and not is_actively_targeting:
                # Force nanobot back toward tumor center only if not on a mission
                direction_to_center = tumor_center - pos_2d
                if np.linalg.norm(direction_to_center) > 0:
                    direction_to_center = direction_to_center / np.linalg.norm(direction_to_center)
                    # Move toward tumor boundary edge
                    edge_position = tumor_center + direction_to_center * (self.model.geometry.tumor_radius - 5.0)
                    self.position[0] = edge_position[0]
                    self.position[1] = edge_position[1]
                    
                    # Cancel targeting if forced back
                    if self.target_cell:
                        self.target_cell = None
                        self.state = NanobotState.SEARCHING
            elif self.state == NanobotState.RETURNING:
                # We're allowed to be outside (returning to vessel)
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
        Query LLM for high-level strategy decision with advanced biological context.
        
        Returns:
            Action string: 'target', 'follow_trail', 'explore', 'return'
        """
        # Get local environmental information
        oxygen = self.model.microenv.get_concentration_at('oxygen', tuple(self.position))
        drug = self.model.microenv.get_concentration_at('drug', tuple(self.position))
        trail = self.model.microenv.get_concentration_at('trail', tuple(self.position))
        alarm = self.model.microenv.get_concentration_at('alarm', tuple(self.position))
        
        # Get immune system signals
        ifn_gamma = self.model.microenv.get_concentration_at('ifn_gamma', tuple(self.position))
        tnf_alpha = self.model.microenv.get_concentration_at('tnf_alpha', tuple(self.position))
        perforin = self.model.microenv.get_concentration_at('perforin', tuple(self.position))
        
        # Get multi-drug concentrations
        drug_a = self.model.microenv.get_concentration_at('drug_a', tuple(self.position))
        drug_b = self.model.microenv.get_concentration_at('drug_b', tuple(self.position))
        
        # Analyze nearby tumor cells by type
        nearby_cells = [
            c for c in self.model.geometry.get_living_cells()
            if np.linalg.norm(np.array(c.position[:2]) - self.position[:2]) < 50.0
        ]
        
        cell_type_counts = {}
        avg_resistance = 0.0
        stem_cells_nearby = 0
        
        if nearby_cells:
            for cell_type in CellType:
                cell_type_counts[cell_type.value] = len([
                    c for c in nearby_cells if c.cell_type == cell_type
                ])
            avg_resistance = np.mean([c.resistance_level for c in nearby_cells])
            stem_cells_nearby = cell_type_counts.get('stem_cell', 0)
        
        # Analyze nearby immune cells
        nearby_immune = [
            c for c in self.model.geometry.immune_cells
            if c.is_active and np.linalg.norm(np.array(c.position[:2]) - self.position[:2]) < 50.0
        ]
        
        immune_activity = np.mean([c.activation_level for c in nearby_immune]) if nearby_immune else 0.0
        
        # Check BBB permeability of nearest vessel
        nearest_vessel = self.model.geometry.find_nearest_vessel(tuple(self.position))
        bbb_permeability = nearest_vessel.bbb_permeability if nearest_vessel else 0.1
        
        prompt = f"""You are an intelligent nanobot carrying anti-cancer drugs through a complex tumor microenvironment.

CURRENT STATUS:
- Position: ({self.position[0]:.1f}, {self.position[1]:.1f}) µm
- Drug payload: {self.drug_payload:.1f}/{self.max_payload} units
- Deliveries made: {self.deliveries_made}

LOCAL MICROENVIRONMENT:
- Oxygen: {oxygen:.2f} mmHg (low = hypoxic tumor region, good target)
- Drug concentration: {drug:.2f} (already treated area?)
- Trail pheromone: {trail:.2f} (successful delivery paths)
- Alarm pheromone: {alarm:.2f} (problems/toxicity reported)

IMMUNE SYSTEM SIGNALS:
- IFN-gamma: {ifn_gamma:.2f} (T-cell activity, enhances immune response)
- TNF-alpha: {tnf_alpha:.2f} (macrophage activity, pro-inflammatory)
- Perforin: {perforin:.2f} (NK cell activity, cytotoxic)

MULTI-DRUG THERAPY:
- Drug A: {drug_a:.2f} (primary therapeutic agent)
- Drug B: {drug_b:.2f} (secondary/synergistic agent)

TUMOR CELL ANALYSIS (within 50µm):
- Total cells: {len(nearby_cells)}
- Stem cells: {stem_cells_nearby} (highly resistant, need more drug)
- Differentiated: {cell_type_counts.get('differentiated', 0)} (normal sensitivity)
- Resistant: {cell_type_counts.get('resistant', 0)} (developed resistance)
- Invasive: {cell_type_counts.get('invasive', 0)} (more sensitive)
- Average resistance level: {avg_resistance:.2f} (0=no resistance, 1=fully resistant)

IMMUNE CELL ACTIVITY:
- Active immune cells nearby: {len(nearby_immune)}
- Average activation: {immune_activity:.2f} (0=inactive, 1=fully active)

BLOOD-BRAIN BARRIER:
- Nearest vessel BBB permeability: {bbb_permeability:.2f} (0.05=very restrictive, 0.3=leaky tumor vessels)

STRATEGIC CONSIDERATIONS:
- Stem cells require 3x more drug than regular cells
- Immune cells make tumor cells more vulnerable to drugs
- High resistance areas need sustained drug delivery
- BBB restricts drug transport (only {bbb_permeability*100:.0f}% passes through)
- Multi-drug combinations can overcome resistance

ACTIONS:
- 'target': Lock onto specific tumor cell (prioritize stem cells if payload sufficient)
- 'follow_trail': Follow pheromone trail to known effective areas
- 'explore': Use chemotaxis to find new targets (avoid high resistance areas)
- 'return': Return to vessel to reload (especially if near BBB vessels)

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
        """LLM-based strategic guidance with advanced biological context."""
        guidance = {}
        
        # Get comprehensive tumor statistics
        stats = self.model.geometry.get_tumor_statistics()
        
        # Analyze cell type distribution
        cell_type_dist = stats.get('cell_type_distribution', {})
        immune_dist = stats.get('immune_cell_distribution', {})
        
        # Calculate priority regions
        stem_cell_regions = []
        high_resistance_regions = []
        immune_active_regions = []
        
        for cell in self.model.geometry.get_living_cells():
            if cell.cell_type == CellType.STEM_CELL:
                stem_cell_regions.append(cell.position[:2])
            if cell.resistance_level > 0.5:
                high_resistance_regions.append(cell.position[:2])
        
        for immune_cell in self.model.geometry.immune_cells:
            if immune_cell.is_active and immune_cell.activation_level > 0.7:
                immune_active_regions.append(immune_cell.position[:2])
        
        # Create strategic prompt for Queen
        prompt = f"""You are the Queen nanobot coordinating a swarm of {len(self.model.nanobots)} nanobots in a complex tumor microenvironment.

TUMOR STATUS:
- Total cells: {stats['total_cells']}
- Living cells: {stats['living_cells']}
- Survival rate: {stats['survival_rate']:.2%}

CELL TYPE DISTRIBUTION:
- Stem cells: {cell_type_dist.get('stem_cell', 0)} (highly resistant, priority targets)
- Differentiated: {cell_type_dist.get('differentiated', 0)} (normal sensitivity)
- Resistant: {cell_type_dist.get('resistant', 0)} (developed resistance)
- Invasive: {cell_type_dist.get('invasive', 0)} (more sensitive)

IMMUNE SYSTEM STATUS:
- T cells: {immune_dist.get('t_cell', 0)} (adaptive immunity)
- Macrophages: {immune_dist.get('macrophage', 0)} (phagocytosis)
- NK cells: {immune_dist.get('nk_cell', 0)} (innate cytotoxicity)
- Dendritic: {immune_dist.get('dendritic', 0)} (antigen presentation)

STRATEGIC PRIORITIES:
- Stem cell regions: {len(stem_cell_regions)} (require sustained drug delivery)
- High resistance areas: {len(high_resistance_regions)} (need multi-drug approach)
- Immune active zones: {len(immune_active_regions)} (synergistic opportunities)

NANOBOT STATUS:
- Total deliveries: {self.model.metrics['total_deliveries']}
- Total drug delivered: {self.model.metrics['total_drug_delivered']:.1f}
- Cells killed: {self.model.metrics['cells_killed']}

COORDINATION STRATEGY:
1. Direct nanobots to stem cell regions (highest priority)
2. Avoid over-concentrating in already treated areas
3. Leverage immune-active regions for synergistic effects
4. Consider BBB permeability when planning reload routes

Provide guidance for nanobot positioning and targeting priorities."""

        try:
            response = self.model.io_client.chat.completions.create(
                model=self.model.selected_model,
                messages=[
                    {"role": "system", "content": "You are a strategic Queen nanobot. Provide high-level coordination guidance."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_completion_tokens=200,
                timeout=15
            )
            
            # Parse response and convert to guidance vectors
            # For now, use enhanced heuristic based on the analysis
            print(f"[TUMOR MODEL] ✅ Queen LLM guidance successful")
            return self._guide_with_enhanced_heuristic(stem_cell_regions, high_resistance_regions, immune_active_regions)
            
        except Exception as e:
            print(f"[TUMOR MODEL] Queen LLM guidance failed: {e}")
            self.model.log_error(f"Queen LLM guidance failed: {str(e)}")
            return self._guide_with_heuristic()
    
    def _guide_with_enhanced_heuristic(self, stem_regions, resistance_regions, immune_regions) -> Dict[int, np.ndarray]:
        """Enhanced heuristic guidance using advanced biological analysis."""
        guidance = {}
        
        for nanobot in self.model.nanobots:
            if nanobot.state == NanobotState.SEARCHING and nanobot.drug_payload > 20.0:
                best_direction = None
                best_priority = 0
                
                # Priority 1: Stem cell regions (highest priority)
                for stem_pos in stem_regions:
                    direction = np.array(stem_pos) - nanobot.position[:2]
                    distance = np.linalg.norm(direction)
                    if distance > 0:
                        priority = 3.0 / (distance + 1)  # Higher priority for closer stem cells
                        if priority > best_priority:
                            best_direction = direction / distance
                            best_priority = priority
                
                # Priority 2: Immune-active regions (synergistic opportunities)
                for immune_pos in immune_regions:
                    direction = np.array(immune_pos) - nanobot.position[:2]
                    distance = np.linalg.norm(direction)
                    if distance > 0:
                        priority = 2.0 / (distance + 1)
                        if priority > best_priority:
                            best_direction = direction / distance
                            best_priority = priority
                
                # Priority 3: High resistance regions (need sustained treatment)
                for res_pos in resistance_regions:
                    direction = np.array(res_pos) - nanobot.position[:2]
                    distance = np.linalg.norm(direction)
                    if distance > 0:
                        priority = 1.5 / (distance + 1)
                        if priority > best_priority:
                            best_direction = direction / distance
                            best_priority = priority
                
                if best_direction is not None:
                    guidance[nanobot.nanobot_id] = best_direction
        
        return guidance


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
        
        # List of known supported chat models
        SUPPORTED_CHAT_MODELS = [
            'meta-llama/Llama-3.3-70B-Instruct',
            'mistralai/Mistral-Large-Instruct-2411',
            'openai/gpt-4-turbo',
            'openai/gpt-4',
            'openai/gpt-3.5-turbo'
        ]
        
        # Validate LLM model selection
        if self.use_llm_queen and self.selected_model not in SUPPORTED_CHAT_MODELS:
            print(f"⚠️ [TUMOR MODEL] Warning: Unsupported model '{self.selected_model}' for Queen LLM.")
            print(f"   Supported models: {SUPPORTED_CHAT_MODELS}")
            self.selected_model = 'mistralai/Mistral-Large-Instruct-2411'  # Fallback to safe default
            print(f"   Fell back to default: '{self.selected_model}'")
        
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
        
        # Add new chemokine and toxicity signal substrates
        create_pheromone_substrate(self.microenv, 'chemokine_signal', decay_rate=0.08)  # Attractant - slower decay
        create_pheromone_substrate(self.microenv, 'toxicity_signal', decay_rate=0.2)     # Repellent - faster decay
        
        # Add immune system substrates
        create_pheromone_substrate(self.microenv, 'ifn_gamma', decay_rate=0.05)    # IFN-gamma from T cells
        create_pheromone_substrate(self.microenv, 'tnf_alpha', decay_rate=0.08)    # TNF-alpha from macrophages
        create_pheromone_substrate(self.microenv, 'perforin', decay_rate=0.12)    # Perforin from NK cells
        
        # Add multi-drug substrates
        self.microenv.add_substrate('drug_a', diffusion_coefficient=1e-6, decay_rate=0.05)  # Primary drug
        self.microenv.add_substrate('drug_b', diffusion_coefficient=1e-7, decay_rate=0.05)  # Secondary drug
        
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
        
        # Blockchain integration for decentralized swarm intelligence
        self.blockchain_enabled = BLOCKCHAIN_ENABLED
        self.nonce_lock = threading.Lock()
        if self.blockchain_enabled:
            try:
                # Test blockchain connection before using it
                self.current_nonce = w3.eth.get_transaction_count(acct.address)
                print("[TUMOR MODEL] ✅ Blockchain connection verified")
            except Exception as e:
                print(f"[TUMOR MODEL] ⚠️ Blockchain connection failed: {e}")
                print("[TUMOR MODEL] ⚠️ Continuing without blockchain integration")
                self.blockchain_enabled = False
                self.current_nonce = 0
        else:
            self.current_nonce = 0

        self.nonce = 0
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
            'total_api_calls': 0,
            # Add LLM vs rule-based metrics for frontend compatibility
            'food_collected_by_llm': 0,
            'food_collected_by_rule': 0,
            'deliveries_by_llm': 0,
            'deliveries_by_rule': 0
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
        
        # Update immune cells and their interactions
        self._update_immune_cells()
        
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
        toxicity_substrate = self.microenv.get_substrate('toxicity_signal')
        new_cells = []  # Track cells ready to divide
        next_cell_id = len(self.geometry.tumor_cells)
        
        for cell in self.geometry.tumor_cells:
            if not cell.is_alive:
                continue
            
            # Get local oxygen and drug concentrations
            oxygen = self.microenv.get_concentration_at('oxygen', cell.position)
            drug = self.microenv.get_concentration_at('drug', cell.position)
            
            # Update cell state
            cell.update_oxygen_status(oxygen, self.microenv.dt)
            cell.absorb_drug(drug, self.microenv.dt)
            
            # Update cell growth and check for division
            if cell.update_growth(self.microenv.dt, oxygen):
                daughter_cell = cell.divide(next_cell_id)
                if daughter_cell:
                    new_cells.append(daughter_cell)
                    next_cell_id += 1
            
            # Add oxygen consumption as sink
            voxel = self.microenv.position_to_voxel(cell.position)
            oxygen_substrate = self.microenv.get_substrate('oxygen')
            if oxygen_substrate:
                oxygen_substrate.add_sink(voxel, cell.get_oxygen_consumption() * self.microenv.dt)
            
            # Generate toxicity signal from hypoxic/necrotic cells and drug overdose
            if toxicity_substrate:
                toxicity_amount = 0.0
                
                # Hypoxic cells emit moderate toxicity
                if cell.phase == CellPhase.HYPOXIC:
                    toxicity_amount += 2.0
                
                # Necrotic cells emit high toxicity
                if cell.phase == CellPhase.NECROTIC:
                    toxicity_amount += 5.0
                
                # Drug overdose areas emit toxicity (high drug concentration)
                if drug > 50.0:  # Threshold for drug overdose
                    toxicity_amount += 3.0
                
                # Add toxicity signal if any toxicity is generated
                if toxicity_amount > 0.0:
                    toxicity_substrate.add_source(voxel, toxicity_amount)
        
        # Add newly divided cells to the tumor geometry
        self.geometry.tumor_cells.extend(new_cells)
        
        # Apply cell mechanics (repulsion) to prevent overlap
        if new_cells:
            self._apply_cell_mechanics()
    
    def _apply_cell_mechanics(self):
        """
        Apply simple repulsion forces between nearby cells to prevent overlap.
        This is a simplified version of cell mechanics - not full PhysiCell.
        """
        cells = self.geometry.tumor_cells
        repulsion_radius = 25.0  # µm - cells repel if closer than this
        repulsion_force = 2.0    # µm displacement per step
        
        for i, cell1 in enumerate(cells):
            if not cell1.is_alive:
                continue
                
            for j in range(i + 1, len(cells)):
                cell2 = cells[j]
                if not cell2.is_alive:
                    continue
                
                # Calculate distance between cells
                dx = cell2.position[0] - cell1.position[0]
                dy = cell2.position[1] - cell1.position[1]
                distance = np.sqrt(dx**2 + dy**2)
                
                # If cells are overlapping, push them apart
                if distance < repulsion_radius and distance > 0.1:
                    # Normalize direction
                    nx = dx / distance
                    ny = dy / distance
                    
                    # Calculate repulsion (inversely proportional to distance)
                    repulsion_magnitude = repulsion_force * (repulsion_radius - distance) / repulsion_radius
                    
                    # Apply repulsion to both cells (equal and opposite)
                    cell1.position = (
                        cell1.position[0] - nx * repulsion_magnitude * 0.5,
                        cell1.position[1] - ny * repulsion_magnitude * 0.5,
                        cell1.position[2]
                    )
                    cell2.position = (
                        cell2.position[0] + nx * repulsion_magnitude * 0.5,
                        cell2.position[1] + ny * repulsion_magnitude * 0.5,
                        cell2.position[2]
                    )
    
    def _update_immune_cells(self):
        """Update immune cells and their interactions with tumor cells."""
        for immune_cell in self.geometry.immune_cells:
            if immune_cell.is_active:
                # Update immune cell state and interactions
                immune_cell.update(self.microenv.dt, self.geometry.tumor_cells)
                
                # Secrete cytokines into microenvironment
                immune_cell.secrete_cytokines(self.microenv)
    
    def _apply_vessel_sources(self):
        """Apply oxygen and drug sources from blood vessels."""
        oxygen_substrate = self.microenv.get_substrate('oxygen')
        drug_substrate = self.microenv.get_substrate('drug')
        
        for vessel in self.geometry.vessels:
            voxel = self.microenv.position_to_voxel(vessel.position)
            
            # Vessels supply oxygen
            if oxygen_substrate:
                oxygen_substrate.add_source(voxel, vessel.oxygen_supply * 0.5)
            
            # Vessels supply drugs with BBB permeability consideration
            if drug_substrate and vessel.drug_supply > 0:
                # Apply BBB permeability factor
                effective_drug_supply = vessel.drug_supply * vessel.bbb_permeability
                drug_substrate.add_source(voxel, effective_drug_supply)
    
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
        
        # Track deliveries by LLM vs rule-based nanobots (for frontend compatibility)
        self.metrics['deliveries_by_llm'] = sum(n.deliveries_made for n in self.nanobots if n.is_llm_controlled)
        self.metrics['deliveries_by_rule'] = sum(n.deliveries_made for n in self.nanobots if not n.is_llm_controlled)
        
        # Map deliveries to food collection for frontend compatibility
        self.metrics['food_collected_by_llm'] = self.metrics['deliveries_by_llm']
        self.metrics['food_collected_by_rule'] = self.metrics['deliveries_by_rule']
    
    def log_error(self, message: str):
        """Log an error message."""
        self.errors.append(message)
        print(f"[TUMOR MODEL] {message}")

