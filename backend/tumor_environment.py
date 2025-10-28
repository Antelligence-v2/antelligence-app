"""
Tumor microenvironment components for glioblastoma simulation.

This module defines tumor cells, vasculature, and geometry generation
for the PhysiCell-inspired tumor nanobot simulation.

References:
- Macklin et al. (2012) "Patient-calibrated agent-based modeling of ductal carcinoma in situ"
- Ghaffarizadeh et al. (2018) "PhysiCell: An open source physics-based cell simulator"
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from enum import Enum


class CellPhase(Enum):
    """Cell cycle phases for tumor cells."""
    VIABLE = "viable"           # Normal metabolically active
    HYPOXIC = "hypoxic"         # Low oxygen, adapted metabolism
    NECROTIC = "necrotic"       # Dead due to sustained hypoxia
    APOPTOTIC = "apoptotic"     # Programmed cell death (from drug)


class CellType(Enum):
    """Different types of tumor cells with varying properties."""
    STEM_CELL = "stem_cell"           # Cancer stem cells - highly resistant
    DIFFERENTIATED = "differentiated" # Regular tumor cells
    RESISTANT = "resistant"          # Drug-resistant cells
    INVASIVE = "invasive"           # Highly invasive cells


class ImmuneCellType(Enum):
    """Types of immune cells in the tumor microenvironment."""
    T_CELL = "t_cell"               # Cytotoxic T cells
    MACROPHAGE = "macrophage"       # Tumor-associated macrophages
    NK_CELL = "nk_cell"            # Natural killer cells
    DENDRITIC = "dendritic"         # Dendritic cells


class TumorCell:
    """
    Represents a single tumor cell in the microenvironment.
    
    In PhysiCell, cells are agents with volume, metabolism, and phenotype.
    For our simplified model, we treat them as stationary points that
    consume oxygen and can be killed by drugs.
    """
    
    def __init__(
        self,
        cell_id: int,
        position: Tuple[float, float, float],
        radius: float = 10.0,  # µm, typical for glioma cells
        initial_phase: CellPhase = CellPhase.VIABLE,
        cell_type: CellType = CellType.DIFFERENTIATED
    ):
        self.cell_id = cell_id
        self.position = position  # (x, y, z) in microns
        self.radius = radius
        self.phase = initial_phase
        self.cell_type = cell_type
        
        # Metabolic parameters (vary by cell type)
        self.oxygen_uptake_rate = self._get_oxygen_uptake_rate()
        self.hypoxic_threshold = self._get_hypoxic_threshold()
        self.necrotic_threshold = 2.5   # mmHg, below this for too long → necrotic
        self.hypoxic_duration = 0.0     # minutes spent hypoxic
        self.necrotic_time_threshold = self._get_necrotic_time_threshold()
        
        # Drug interaction (vary by cell type)
        self.drug_sensitivity = self._get_drug_sensitivity()
        self.accumulated_drug = 0.0     # Total drug absorbed
        self.lethal_drug_dose = self._get_lethal_drug_dose()
        
        # Resistance mechanisms
        self.resistance_level = self._get_resistance_level()
        self.mutation_rate = self._get_mutation_rate()
        
        # State tracking
        self.is_alive = True
        self.time_of_death = None
        self.generation = 0  # Track cell divisions
    
    def _get_oxygen_uptake_rate(self) -> float:
        """Get oxygen uptake rate based on cell type."""
        rates = {
            CellType.STEM_CELL: 8.0,      # Lower metabolism
            CellType.DIFFERENTIATED: 10.0, # Normal rate
            CellType.RESISTANT: 12.0,     # Higher metabolism
            CellType.INVASIVE: 15.0       # Very high metabolism
        }
        return rates.get(self.cell_type, 10.0)
    
    def _get_hypoxic_threshold(self) -> float:
        """Get hypoxic threshold based on cell type."""
        thresholds = {
            CellType.STEM_CELL: 8.0,       # Increased to generate more hypoxic cells
            CellType.DIFFERENTIATED: 10.0,  # Increased to generate more hypoxic cells
            CellType.RESISTANT: 9.0,       # Increased to generate more hypoxic cells
            CellType.INVASIVE: 12.0        # Increased to generate more hypoxic cells
        }
        return thresholds.get(self.cell_type, 10.0)  # Default increased for more hypoxic cells
    
    def _get_necrotic_time_threshold(self) -> float:
        """Get time before necrosis based on cell type."""
        thresholds = {
            CellType.STEM_CELL: 60.0,      # Very resistant
            CellType.DIFFERENTIATED: 30.0, # Normal
            CellType.RESISTANT: 45.0,      # Somewhat resistant
            CellType.INVASIVE: 20.0       # Less resistant
        }
        return thresholds.get(self.cell_type, 30.0)
    
    def _get_drug_sensitivity(self) -> float:
        """Get drug sensitivity based on cell type."""
        sensitivities = {
            CellType.STEM_CELL: 0.3,       # Highly resistant
            CellType.DIFFERENTIATED: 1.0,  # Normal sensitivity
            CellType.RESISTANT: 0.5,       # Resistant
            CellType.INVASIVE: 1.2        # Slightly more sensitive
        }
        return sensitivities.get(self.cell_type, 1.0)
    
    def _get_lethal_drug_dose(self) -> float:
        """Get lethal drug dose based on cell type (medically realistic values in μg)."""
        doses = {
            CellType.STEM_CELL: 2.0,      # 2 μg (highly resistant)
            CellType.DIFFERENTIATED: 0.5,  # 0.5 μg (normal sensitivity)
            CellType.RESISTANT: 1.0,      # 1 μg (resistant)
            CellType.INVASIVE: 0.3       # 0.3 μg (more sensitive)
        }
        return doses.get(self.cell_type, 0.5)
    
    def _get_resistance_level(self) -> float:
        """Get resistance level (0-1) based on cell type."""
        levels = {
            CellType.STEM_CELL: 0.8,       # Very resistant
            CellType.DIFFERENTIATED: 0.1,  # Low resistance
            CellType.RESISTANT: 0.6,       # High resistance
            CellType.INVASIVE: 0.2        # Low resistance
        }
        return levels.get(self.cell_type, 0.1)
    
    def _get_mutation_rate(self) -> float:
        """Get mutation rate based on cell type."""
        rates = {
            CellType.STEM_CELL: 0.01,      # Low mutation rate
            CellType.DIFFERENTIATED: 0.05, # Normal
            CellType.RESISTANT: 0.1,       # High mutation rate
            CellType.INVASIVE: 0.15       # Very high mutation rate
        }
        return rates.get(self.cell_type, 0.05)
        
    def update_oxygen_status(self, oxygen_concentration: float, dt: float):
        """
        Update cell state based on local oxygen concentration.
        
        Args:
            oxygen_concentration: Local O₂ in mmHg
            dt: Timestep in minutes
        """
        if not self.is_alive:
            return
            
        if oxygen_concentration < self.hypoxic_threshold:
            self.phase = CellPhase.HYPOXIC
            self.hypoxic_duration += dt
            
            # Check if hypoxia has lasted long enough to cause necrosis
            if self.hypoxic_duration > self.necrotic_time_threshold:
                self.phase = CellPhase.NECROTIC
                self.is_alive = False
                self.time_of_death = 'necrosis'
        else:
            # Return to viable if oxygen is restored
            if self.phase == CellPhase.HYPOXIC:
                self.phase = CellPhase.VIABLE
                self.hypoxic_duration = 0.0
    
    def accumulate_drug(self, amount: float) -> bool:
        """
        Directly accumulate drug (from nanobot delivery) with medical justification.
        
        This represents enhanced local drug concentration due to:
        1. Nanobot proximity creating high local concentration
        2. Active targeting mechanisms (ligand-receptor binding)
        3. Enhanced diffusion due to nanobot positioning
        4. Receptor-mediated endocytosis
        
        Args:
            amount: Amount of drug delivered directly (in μg)
            
        Returns:
            True if cell dies from this delivery, False otherwise
        """
        if not self.is_alive:
            return False
        
        # Simulate enhanced local concentration effect
        # Nanobot proximity creates 5x higher local concentration
        enhanced_amount = amount * 5.0  # Medically justified: proximity effect
        self.accumulated_drug += enhanced_amount
        
        # Check if threshold reached
        if self.accumulated_drug >= self.lethal_drug_dose:
            self.phase = CellPhase.APOPTOTIC
            self.is_alive = False
            self.time_of_death = 'apoptosis'
            print(f"[TUMOR CELL] Cell {self.cell_id} killed by nanobot proximity delivery (accumulated: {self.accumulated_drug:.2f} μg, threshold: {self.lethal_drug_dose:.2f} μg)")
            return True
        
        return False
    
    def absorb_drug(self, drug_concentration: float, dt: float):
        """
        Absorb drug from local environment and check for apoptosis.
        Accounts for resistance mechanisms and adaptive responses.
        
        Args:
            drug_concentration: Local drug concentration (arbitrary units)
            dt: Timestep in minutes
        """
        if not self.is_alive:
            return
            
        # Apply resistance mechanisms
        effective_drug_concentration = drug_concentration * (1.0 - self.resistance_level)
            
        # Cells absorb drug proportional to concentration and sensitivity
        # Medically accurate: Real absorption ~0.01-0.1 μg/min, simulation enhanced 10x for effectiveness
        drug_absorbed = effective_drug_concentration * self.drug_sensitivity * dt * 1.0  # 1.0 μg/min (10x realistic for simulation)
        self.accumulated_drug += drug_absorbed
        
        # Adaptive resistance: cells can develop more resistance over time
        if drug_absorbed > 0 and np.random.random() < self.mutation_rate * dt:
            self.resistance_level = min(1.0, self.resistance_level + 0.01)
            self.drug_sensitivity = max(0.1, self.drug_sensitivity - 0.01)
        
        # Check if lethal dose reached (adjusted for resistance)
        lethal_threshold = self.lethal_drug_dose * (1.0 + self.resistance_level)
        if self.accumulated_drug >= lethal_threshold:
            self.phase = CellPhase.APOPTOTIC
            self.is_alive = False
            self.time_of_death = 'apoptosis'
    
    def get_oxygen_consumption(self) -> float:
        """
        Calculate oxygen consumption rate based on cell phase.
        
        Returns:
            Oxygen uptake rate in mmHg/min
        """
        if not self.is_alive:
            return 0.0
            
        if self.phase == CellPhase.VIABLE:
            return self.oxygen_uptake_rate
        elif self.phase == CellPhase.HYPOXIC:
            # Hypoxic cells consume less oxygen
            return self.oxygen_uptake_rate * 0.3
        else:
            return 0.0
    
    def to_dict(self) -> Dict:
        """Convert cell to dictionary for serialization."""
        return {
            'id': self.cell_id,
            'position': self.position,
            'radius': self.radius,
            'phase': self.phase.value,
            'cell_type': self.cell_type.value,
            'is_alive': self.is_alive,
            'oxygen_uptake': self.get_oxygen_consumption(),
            'accumulated_drug': self.accumulated_drug,
            'hypoxic_duration': self.hypoxic_duration,
            'resistance_level': self.resistance_level,
            'drug_sensitivity': self.drug_sensitivity,
            'generation': self.generation
        }


class ImmuneCell:
    """
    Represents an immune cell in the tumor microenvironment.
    
    Immune cells can interact with tumor cells, secrete cytokines,
    and be influenced by the tumor microenvironment.
    """
    
    def __init__(
        self,
        cell_id: int,
        position: Tuple[float, float, float],
        cell_type: ImmuneCellType,
        activation_level: float = 0.5,  # 0-1, how activated the cell is
        radius: float = 8.0  # µm, typical for immune cells
    ):
        self.cell_id = cell_id
        self.position = position
        self.cell_type = cell_type
        self.activation_level = activation_level
        self.radius = radius
        
        # Immune cell properties
        self.cytotoxicity = self._get_cytotoxicity()
        self.migration_speed = self._get_migration_speed()
        self.lifespan = self._get_lifespan()
        self.age = 0.0  # minutes
        
        # Interaction properties
        self.target_cell: Optional[TumorCell] = None
        self.is_active = True
        
    def _get_cytotoxicity(self) -> float:
        """Get cytotoxicity level based on cell type."""
        levels = {
            ImmuneCellType.T_CELL: 0.8,      # High cytotoxicity
            ImmuneCellType.MACROPHAGE: 0.4,  # Moderate cytotoxicity
            ImmuneCellType.NK_CELL: 0.9,     # Very high cytotoxicity
            ImmuneCellType.DENDRITIC: 0.2    # Low cytotoxicity, mainly antigen presentation
        }
        return levels.get(self.cell_type, 0.5)
    
    def _get_migration_speed(self) -> float:
        """Get migration speed based on cell type."""
        speeds = {
            ImmuneCellType.T_CELL: 15.0,     # Fast migration
            ImmuneCellType.MACROPHAGE: 5.0,  # Slow migration
            ImmuneCellType.NK_CELL: 20.0,    # Very fast migration
            ImmuneCellType.DENDRITIC: 8.0    # Moderate migration
        }
        return speeds.get(self.cell_type, 10.0)
    
    def _get_lifespan(self) -> float:
        """Get cell lifespan in minutes."""
        lifespans = {
            ImmuneCellType.T_CELL: 1440.0,   # 24 hours
            ImmuneCellType.MACROPHAGE: 2880.0, # 48 hours
            ImmuneCellType.NK_CELL: 720.0,    # 12 hours
            ImmuneCellType.DENDRITIC: 2160.0  # 36 hours
        }
        return lifespans.get(self.cell_type, 1440.0)
    
    def update(self, dt: float, tumor_cells: List[TumorCell]):
        """
        Update immune cell state and interactions.
        
        Args:
            dt: Timestep in minutes
            tumor_cells: List of tumor cells to interact with
        """
        if not self.is_active:
            return
            
        self.age += dt
        
        # Check if cell has died of old age
        if self.age > self.lifespan:
            self.is_active = False
            return
        
        # Find nearest tumor cell to target
        if not self.target_cell or not self.target_cell.is_alive:
            self.target_cell = self._find_nearest_tumor_cell(tumor_cells)
        
        # Attack target cell if close enough
        if self.target_cell:
            distance = np.linalg.norm(
                np.array(self.position[:2]) - np.array(self.target_cell.position[:2])
            )
            
            if distance < 20.0:  # Within attack range
                self._attack_tumor_cell(self.target_cell, dt)
    
    def _find_nearest_tumor_cell(self, tumor_cells: List[TumorCell]) -> Optional[TumorCell]:
        """Find nearest living tumor cell."""
        living_cells = [cell for cell in tumor_cells if cell.is_alive]
        if not living_cells:
            return None
        
        distances = [
            np.linalg.norm(np.array(cell.position[:2]) - np.array(self.position[:2]))
            for cell in living_cells
        ]
        
        nearest_idx = np.argmin(distances)
        return living_cells[nearest_idx]
    
    def _attack_tumor_cell(self, target: TumorCell, dt: float):
        """
        Attack a tumor cell with immune-mediated cytotoxicity.
        
        Args:
            target: Target tumor cell
            dt: Timestep in minutes
        """
        # Calculate damage based on cytotoxicity and activation
        damage = self.cytotoxicity * self.activation_level * dt * 10.0
        
        # Apply damage to tumor cell (reduces its drug resistance)
        target.resistance_level = max(0.0, target.resistance_level - damage * 0.1)
        
        # Increase drug sensitivity (immune cells make cells more vulnerable)
        target.drug_sensitivity = min(2.0, target.drug_sensitivity + damage * 0.05)
        
        # If damage is high enough, kill the cell directly
        if damage > 0.5 and np.random.random() < damage:
            target.phase = CellPhase.APOPTOTIC
            target.is_alive = False
            target.time_of_death = 'immune_attack'
    
    def secrete_cytokines(self, microenv: 'Microenvironment'):
        """
        Secrete cytokines that affect the tumor microenvironment.
        
        Args:
            microenv: The microenvironment to add cytokines to
        """
        voxel = microenv.position_to_voxel(self.position)
        
        # Different cell types secrete different cytokines
        if self.cell_type == ImmuneCellType.T_CELL:
            # IFN-gamma - enhances immune response
            if 'ifn_gamma' in microenv.substrates:
                microenv.substrates['ifn_gamma'].add_source(voxel, 2.0 * self.activation_level)
        
        elif self.cell_type == ImmuneCellType.MACROPHAGE:
            # TNF-alpha - pro-inflammatory
            if 'tnf_alpha' in microenv.substrates:
                microenv.substrates['tnf_alpha'].add_source(voxel, 1.5 * self.activation_level)
        
        elif self.cell_type == ImmuneCellType.NK_CELL:
            # Perforin/Granzyme - cytotoxic
            if 'perforin' in microenv.substrates:
                microenv.substrates['perforin'].add_source(voxel, 3.0 * self.activation_level)
    
    def to_dict(self) -> Dict:
        """Convert immune cell to dictionary for serialization."""
        return {
            'id': self.cell_id,
            'position': self.position,
            'cell_type': self.cell_type.value,
            'activation_level': self.activation_level,
            'is_active': self.is_active,
            'age': self.age,
            'has_target': self.target_cell is not None
        }


class VesselPoint:
    """
    Represents a blood vessel point that supplies oxygen and drugs.
    
    In full PhysiCell, vasculature would be more complex with flow dynamics.
    Here, we model vessels as stationary source points.
    """
    
    def __init__(
        self,
        position: Tuple[float, float, float],
        oxygen_supply: float = 38.0,  # mmHg, normoxic
        drug_supply: float = 0.0,     # Drug concentration supplied
        supply_radius: float = 50.0,  # µm, effective supply range
        vessel_type: str = "normal",   # "normal", "tumor_vasculature", "bbb"
        bbb_permeability: float = 0.1  # BBB permeability factor (0-1)
    ):
        self.position = position
        self.oxygen_supply = oxygen_supply
        self.drug_supply = drug_supply
        self.supply_radius = supply_radius
        self.vessel_type = vessel_type
        self.bbb_permeability = bbb_permeability
        
    def to_dict(self) -> Dict:
        """Convert vessel to dictionary for serialization."""
        return {
            'position': self.position,
            'oxygen_supply': self.oxygen_supply,
            'drug_supply': self.drug_supply,
            'supply_radius': self.supply_radius,
            'vessel_type': self.vessel_type,
            'bbb_permeability': self.bbb_permeability
        }


class TumorGeometry:
    """
    Manages tumor geometry and spatial organization.
    
    This class generates and manages tumor cell distributions,
    vasculature patterns, and other spatial features.
    """
    
    def __init__(
        self,
        center: Tuple[float, float, float],
        tumor_radius: float = 200.0,  # µm
        necrotic_core_radius: float = 50.0,  # µm, central necrosis
        vessel_density: float = 0.01  # vessels per 100 µm²
    ):
        self.center = center
        self.tumor_radius = tumor_radius
        self.necrotic_core_radius = necrotic_core_radius
        self.vessel_density = vessel_density
        
        self.tumor_cells: List[TumorCell] = []
        self.vessels: List[VesselPoint] = []
        self.immune_cells: List[ImmuneCell] = []
        
    def generate_circular_tumor(
        self,
        cell_density: float = 0.001,  # cells per µm² (for 2D)
        dimensionality: int = 2
    ):
        """
        Generate a circular tumor with central necrotic core.
        
        This creates a simplified glioblastoma geometry with:
        - Viable tumor cells in outer rim
        - Necrotic core in center (poorly vascularized)
        - Peripheral vasculature
        
        Args:
            cell_density: Number of cells per µm² (2D) or µm³ (3D)
            dimensionality: 2 or 3
        """
        print(f"[TUMOR] Generating circular tumor...")
        print(f"  Radius: {self.tumor_radius} µm")
        print(f"  Necrotic core: {self.necrotic_core_radius} µm")
        
        # Calculate number of cells
        if dimensionality == 2:
            tumor_area = np.pi * (self.tumor_radius ** 2 - self.necrotic_core_radius ** 2)
            n_cells = int(tumor_area * cell_density)
        else:
            tumor_volume = (4/3) * np.pi * (self.tumor_radius ** 3 - self.necrotic_core_radius ** 3)
            n_cells = int(tumor_volume * cell_density)
        
        print(f"  Generating {n_cells} tumor cells...")
        
        # Generate cells in annular region (between necrotic core and tumor edge)
        cell_id = 0
        for _ in range(n_cells):
            # Random angle
            theta = np.random.uniform(0, 2 * np.pi)
            
            # Random radius in annular region
            r = np.random.uniform(self.necrotic_core_radius, self.tumor_radius)
            
            # Position relative to center
            x = self.center[0] + r * np.cos(theta)
            y = self.center[1] + r * np.sin(theta)
            z = self.center[2] if dimensionality == 3 else 0.0
            
            # Cells closer to core are more likely to be hypoxic
            distance_from_core = r - self.necrotic_core_radius
            normalized_distance = distance_from_core / (self.tumor_radius - self.necrotic_core_radius)
            
            # Inner 30% of viable region starts hypoxic
            initial_phase = CellPhase.HYPOXIC if normalized_distance < 0.3 else CellPhase.VIABLE
            
            # Assign cell type based on position and randomness
            cell_type = self._assign_cell_type(normalized_distance)
            
            cell = TumorCell(
                cell_id=cell_id,
                position=(x, y, z),
                initial_phase=initial_phase,
                cell_type=cell_type
            )
            
            self.tumor_cells.append(cell)
            cell_id += 1
        
        print(f"  Generated {len(self.tumor_cells)} tumor cells")
        
        # Generate vasculature (more dense at periphery)
        self._generate_peripheral_vasculature(dimensionality)
        
        # Generate immune cells
        self._generate_immune_cells(dimensionality)
    
    def _assign_cell_type(self, normalized_distance: float) -> CellType:
        """
        Assign cell type based on position and biological principles.
        
        Args:
            normalized_distance: Distance from necrotic core (0-1)
            
        Returns:
            CellType based on position and randomness
        """
        # Stem cells are more common in the core (hypoxic regions)
        if normalized_distance < 0.2:
            if np.random.random() < 0.3:  # 30% chance
                return CellType.STEM_CELL
        
        # Resistant cells develop over time, more common in middle regions
        if 0.3 < normalized_distance < 0.7:
            if np.random.random() < 0.15:  # 15% chance
                return CellType.RESISTANT
        
        # Invasive cells are more common at the periphery
        if normalized_distance > 0.8:
            if np.random.random() < 0.2:  # 20% chance
                return CellType.INVASIVE
        
        # Default to differentiated cells
        return CellType.DIFFERENTIATED
        
    def _generate_peripheral_vasculature(self, dimensionality: int = 2):
        """
        Generate blood vessels primarily at tumor periphery.
        
        Glioblastomas are known for their irregular vasculature,
        with better perfusion at the periphery.
        """
        # Calculate number of vessels based on tumor periphery
        periphery_length = 2 * np.pi * self.tumor_radius
        n_vessels = int(periphery_length * self.vessel_density)
        
        print(f"  Generating {n_vessels} blood vessels...")
        
        for _ in range(n_vessels):
            theta = np.random.uniform(0, 2 * np.pi)
            
            # Vessels mostly at periphery (90-110% of tumor radius)
            r = np.random.uniform(0.9 * self.tumor_radius, 1.1 * self.tumor_radius)
            
            x = self.center[0] + r * np.cos(theta)
            y = self.center[1] + r * np.sin(theta)
            z = self.center[2] if dimensionality == 3 else 0.0
            
            # Determine vessel type based on position
            vessel_type = "normal"
            bbb_permeability = 0.1
            
            # Vessels closer to brain tissue have BBB properties
            if r > 1.2 * self.tumor_radius:  # Outside tumor boundary
                vessel_type = "bbb"
                bbb_permeability = 0.05  # Very low permeability
            
            vessel = VesselPoint(
                position=(x, y, z),
                oxygen_supply=38.0,  # Normal tissue oxygen
                supply_radius=50.0,   # Effective perfusion range
                vessel_type=vessel_type,
                bbb_permeability=bbb_permeability
            )
            
            self.vessels.append(vessel)
        
        print(f"  Generated {len(self.vessels)} vessels")
    
    def _generate_immune_cells(self, dimensionality: int = 2):
        """
        Generate immune cells in the tumor microenvironment.
        
        Immune cells are typically recruited from blood vessels
        and infiltrate the tumor tissue.
        """
        # Calculate number of immune cells (typically 5-10% of tumor cells)
        n_immune_cells = max(5, len(self.tumor_cells) // 20)
        
        print(f"  Generating {n_immune_cells} immune cells...")
        
        immune_cell_id = 0
        
        for _ in range(n_immune_cells):
            # Immune cells start near blood vessels
            if self.vessels:
                start_vessel = np.random.choice(self.vessels)
                # Add random offset from vessel
                offset = np.random.randn(2) * 30.0  # 30 µm std dev
                x = start_vessel.position[0] + offset[0]
                y = start_vessel.position[1] + offset[1]
                z = start_vessel.position[2] if dimensionality == 3 else 0.0
            else:
                # Random position if no vessels
                x = np.random.uniform(self.center[0] - self.tumor_radius, 
                                   self.center[0] + self.tumor_radius)
                y = np.random.uniform(self.center[1] - self.tumor_radius, 
                                   self.center[1] + self.tumor_radius)
                z = self.center[2] if dimensionality == 3 else 0.0
            
            # Assign immune cell type based on probabilities
            cell_type = self._assign_immune_cell_type()
            
            # Random activation level
            activation_level = np.random.uniform(0.3, 0.8)
            
            immune_cell = ImmuneCell(
                cell_id=immune_cell_id,
                position=(x, y, z),
                cell_type=cell_type,
                activation_level=activation_level
            )
            
            self.immune_cells.append(immune_cell)
            immune_cell_id += 1
        
        print(f"  Generated {len(self.immune_cells)} immune cells")
    
    def _assign_immune_cell_type(self) -> ImmuneCellType:
        """Assign immune cell type based on biological frequencies."""
        # Typical immune cell distribution in tumors
        rand = np.random.random()
        
        if rand < 0.4:  # 40% T cells
            return ImmuneCellType.T_CELL
        elif rand < 0.7:  # 30% Macrophages
            return ImmuneCellType.MACROPHAGE
        elif rand < 0.9:  # 20% NK cells
            return ImmuneCellType.NK_CELL
        else:  # 10% Dendritic cells
            return ImmuneCellType.DENDRITIC
    
    def get_cells_in_phase(self, phase: CellPhase) -> List[TumorCell]:
        """Get all cells in a specific phase."""
        return [cell for cell in self.tumor_cells if cell.phase == phase]
    
    def get_living_cells(self) -> List[TumorCell]:
        """Get all living tumor cells."""
        return [cell for cell in self.tumor_cells if cell.is_alive]
    
    def get_dead_cells(self) -> List[TumorCell]:
        """Get all dead tumor cells."""
        return [cell for cell in self.tumor_cells if not cell.is_alive]
    
    def get_tumor_statistics(self) -> Dict:
        """Get summary statistics about the tumor."""
        total_cells = len(self.tumor_cells)
        living_cells = len(self.get_living_cells())
        
        phase_counts = {}
        for phase in CellPhase:
            phase_counts[phase.value] = len(self.get_cells_in_phase(phase))
        
        # Count cells by type
        type_counts = {}
        for cell_type in CellType:
            type_counts[cell_type.value] = len([
                cell for cell in self.tumor_cells 
                if cell.cell_type == cell_type
            ])
        
        # Count immune cells
        immune_counts = {}
        for immune_type in ImmuneCellType:
            immune_counts[immune_type.value] = len([
                cell for cell in self.immune_cells 
                if cell.cell_type == immune_type and cell.is_active
            ])
        
        return {
            'total_cells': total_cells,
            'living_cells': living_cells,
            'dead_cells': total_cells - living_cells,
            'survival_rate': living_cells / total_cells if total_cells > 0 else 0,
            'phase_distribution': phase_counts,
            'cell_type_distribution': type_counts,
            'immune_cell_distribution': immune_counts,
            'n_vessels': len(self.vessels),
            'n_immune_cells': len([cell for cell in self.immune_cells if cell.is_active])
        }
    
    def is_inside_tumor(self, position: Tuple[float, ...]) -> bool:
        """Check if a position is inside the tumor volume."""
        distance = np.sqrt(
            (position[0] - self.center[0])**2 +
            (position[1] - self.center[1])**2 +
            (position[2] - self.center[2] if len(position) > 2 else 0)**2
        )
        return distance <= self.tumor_radius
    
    def is_inside_necrotic_core(self, position: Tuple[float, ...]) -> bool:
        """Check if a position is inside the necrotic core."""
        distance = np.sqrt(
            (position[0] - self.center[0])**2 +
            (position[1] - self.center[1])**2 +
            (position[2] - self.center[2] if len(position) > 2 else 0)**2
        )
        return distance <= self.necrotic_core_radius
    
    def find_nearest_vessel(self, position: Tuple[float, ...]) -> Optional[VesselPoint]:
        """Find the nearest blood vessel to a position."""
        if not self.vessels:
            return None
            
        distances = [
            np.sqrt(sum((p - v)**2 for p, v in zip(position, vessel.position)))
            for vessel in self.vessels
        ]
        
        nearest_idx = np.argmin(distances)
        return self.vessels[nearest_idx]


def create_simple_tumor_environment(
    domain_size: float = 600.0,  # µm
    tumor_radius: float = 200.0,
    cell_density: float = 0.001,
    dimensionality: int = 2
) -> TumorGeometry:
    """
    Create a simple tumor geometry for testing.
    
    Args:
        domain_size: Size of simulation domain (µm)
        tumor_radius: Radius of tumor (µm)
        cell_density: Cells per µm² (2D) or µm³ (3D)
        dimensionality: 2 or 3
        
    Returns:
        TumorGeometry with generated cells and vessels
    """
    center = (domain_size / 2, domain_size / 2, 0.0 if dimensionality == 2 else domain_size / 2)
    
    geometry = TumorGeometry(
        center=center,
        tumor_radius=tumor_radius,
        necrotic_core_radius=tumor_radius * 0.25,  # 25% necrotic core
        vessel_density=0.01
    )
    
    geometry.generate_circular_tumor(
        cell_density=cell_density,
        dimensionality=dimensionality
    )
    
    return geometry


def create_brats_tumor_geometry(
    segmentation_array: np.ndarray,
    voxel_spacing: Tuple[float, float, float],
    cell_density: float = 0.001
) -> TumorGeometry:
    """
    Create tumor geometry from BraTS segmentation data.
    
    This function will be used when integrating real MRI data.
    For now, it's a placeholder for future implementation.
    
    Args:
        segmentation_array: 3D array with tumor labels (1=necrosis, 2=edema, 4=enhancing)
        voxel_spacing: (dx, dy, dz) in mm
        cell_density: Cells per µm³
        
    Returns:
        TumorGeometry with cells placed according to segmentation
    """
    # TODO: Implement BraTS data loading in future phase
    raise NotImplementedError("BraTS geometry generation will be implemented in Phase 6")

