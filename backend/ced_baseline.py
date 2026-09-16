"""
CED Baseline Model — Convection-Enhanced Delivery Pharmacokinetics

Implements the standard surgical drug delivery method for GBM comparison.
This is the current clinical standard we are benchmarking against.

Reference physics:
  Morrison PF et al. (1994) High-level CNS concentrations of chemotherapeutic
  agents achieved using convection-enhanced delivery. Cancer Chemotherapy
  and Pharmacology, 35(1), 88-95.
  
  Linninger AA et al. (2008) Prediction of convection-enhanced drug delivery
  to the human brain. Journal of Theoretical Biology, 250(1), 125-138.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import time


@dataclass
class CEDParams:
    """Clinically-validated CED parameters for GBM chemotherapy."""
    # Diffusion
    D_eff_cm2_per_s: float = 5e-8        # effective diffusion in brain (cm²/s)
    # Convection  
    convection_velocity_um_per_min: float = 0.2  # interstitial fluid velocity (µm/min)
    # Degradation
    degradation_rate_per_min: float = 0.01  # drug half-life ~70 min
    # Infusion
    infusion_rate_ul_per_min: float = 5.0   # µL/min (typical clinical)
    infusion_duration_min: float = 360.0    # 6 hours (typical clinical)
    catheter_drug_conc: float = 1.0         # normalized drug concentration at tip
    # Tissue
    porosity: float = 0.2                   # brain tissue void fraction
    tortuosity: float = 1.6                 # diffusion path tortuosity
    # BBB (blood-brain barrier)
    bbb_clearance_rate: float = 0.005       # drug cleared into vasculature (/min)
    # Drug effect on cells
    drug_kill_threshold: float = 0.5        # normalized concentration for cell kill
    kill_probability_per_min: float = 0.02  # prob of killing cell above threshold/min
    # Cell type sensitivity multipliers
    stem_cell_sensitivity: float = 0.3      # stem cells highly resistant
    differentiated_sensitivity: float = 1.0 
    resistant_sensitivity: float = 0.5
    invasive_sensitivity: float = 1.2       # more sensitive but harder to reach


class CEDSimulation:
    """
    Finite-difference simulation of CED drug delivery in a GBM tumor.
    
    Grid: same resolution as nanobot simulation (voxel_size µm)
    Time: minutes (matching clinical timescales)
    Drug: normalized concentration (0=none, 1=max at catheter)
    
    Comparison metric: cells killed per unit drug administered
    vs nanobot simulation's cells killed per unit drug delivered
    """
    
    def __init__(
        self,
        domain_size: float = 600.0,        # µm
        voxel_size: float = 20.0,          # µm
        tumor_cells=None,                  # list of TumorCell from tumor_environment
        params: Optional[CEDParams] = None,
        catheter_position: Optional[Tuple[float,float]] = None,  # µm, default=tumor center
        n_catheters: int = 1,              # CED typically uses 1-4 catheters
        rng_seed: int = 42,
    ):
        self.domain_size = domain_size
        self.voxel_size = voxel_size
        self.params = params or CEDParams()
        self.rng = np.random.default_rng(rng_seed)
        self.step_count = 0
        self.time_min = 0.0
        self.errors = []
        
        # Grid dimensions
        self.nx = int(domain_size / voxel_size)
        self.ny = int(domain_size / voxel_size)
        
        # Drug concentration grid
        self.drug = np.zeros((self.nx, self.ny), dtype=np.float64)
        
        # Tumor cells (copy to avoid modifying originals)
        self.tumor_cells = list(tumor_cells) if tumor_cells else []
        
        # CFL-stable timestep for diffusion
        D_um2_per_min = self.params.D_eff_cm2_per_s * 6e9 / (self.params.tortuosity**2)
        self.D_effective = D_um2_per_min
        dx = voxel_size
        self.dt = 0.25 * dx**2 / (2 * D_um2_per_min + 1e-10)  # CFL criterion
        self.dt = min(self.dt, 0.5)  # cap at 0.5 min
        
        # Catheter positions
        center = domain_size / 2.0
        if catheter_position:
            base_pos = catheter_position
        else:
            base_pos = (center, center)
        
        # Multiple catheters: spread around center
        self.catheter_positions = []
        offsets = [(0,0), (30,0), (-30,0), (0,30)] if n_catheters > 1 else [(0,0)]
        for i in range(n_catheters):
            ox, oy = offsets[i % len(offsets)]
            self.catheter_positions.append((
                base_pos[0] + ox,
                base_pos[1] + oy
            ))
        
        # Metrics
        self.metrics = {
            "cells_killed": 0,
            "total_drug_administered": 0.0,
            "drug_efficiency": 0.0,
            "cells_killed_by_type": {"stem": 0, "differentiated": 0, "resistant": 0, "invasive": 0},
            "viable_cells": len([c for c in self.tumor_cells if c.is_alive]),
            "initial_cells": len([c for c in self.tumor_cells if c.is_alive]),
            "infusion_active": True,
            "distribution_volume_um3": 0.0,
        }
        
        self.history = []
    
    def _pos_to_voxel(self, x, y) -> Tuple[int, int]:
        i = int(np.clip(x / self.voxel_size, 0, self.nx - 1))
        j = int(np.clip(y / self.voxel_size, 0, self.ny - 1))
        return i, j
    
    def _apply_catheter_source(self):
        """Apply drug source at catheter tips during infusion period."""
        if self.time_min > self.params.infusion_duration_min:
            self.metrics["infusion_active"] = False
            return
        
        source_per_dt = (self.params.catheter_drug_conc * 
                         self.params.infusion_rate_ul_per_min * 
                         self.dt / 60.0)  # normalized
        
        for cx, cy in self.catheter_positions:
            i, j = self._pos_to_voxel(cx, cy)
            # Apply to 3x3 voxel region around catheter tip
            for di in range(-1, 2):
                for dj in range(-1, 2):
                    ni, nj = int(np.clip(i+di, 0, self.nx-1)), int(np.clip(j+dj, 0, self.ny-1))
                    self.drug[ni, nj] = min(1.0, self.drug[ni, nj] + source_per_dt)
        
        self.metrics["total_drug_administered"] += source_per_dt * len(self.catheter_positions)
    
    def _diffuse_and_convect(self):
        """Explicit finite difference: diffusion + convection + degradation."""
        C = self.drug
        D = self.D_effective
        v = self.params.convection_velocity_um_per_min
        lam = self.params.degradation_rate_per_min
        bbb = self.params.bbb_clearance_rate
        dx = self.voxel_size
        dt = self.dt
        
        # Laplacian (2D)
        lap = (np.roll(C, 1, 0) + np.roll(C, -1, 0) +
               np.roll(C, 1, 1) + np.roll(C, -1, 1) - 4*C) / (dx**2)
        
        # Upwind convection (radially outward from catheter center)
        # Simple: uniform flow in +x direction as approximation
        dCdx = (np.roll(C, -1, 0) - np.roll(C, 1, 0)) / (2 * dx)
        dCdy = (np.roll(C, -1, 1) - np.roll(C, 1, 1)) / (2 * dx)
        
        # Update
        self.drug = C + dt * (D * lap - v * (dCdx + dCdy) - (lam + bbb) * C)
        self.drug = np.clip(self.drug, 0, 1.0)
        
        # Dirichlet BC: zero at boundaries
        self.drug[0, :] = 0
        self.drug[-1, :] = 0
        self.drug[:, 0] = 0
        self.drug[:, -1] = 0
    
    def _update_tumor_cells(self):
        """Apply drug effect to tumor cells based on local concentration."""
        sensitivity_map = {
            "stem_cell": self.params.stem_cell_sensitivity,
            "differentiated": self.params.differentiated_sensitivity,
            "resistant": self.params.resistant_sensitivity,
            "invasive": self.params.invasive_sensitivity,
        }
        
        for cell in self.tumor_cells:
            if not cell.is_alive:
                continue
            
            # Get local drug concentration
            i, j = self._pos_to_voxel(cell.position[0], cell.position[1])
            local_drug = float(self.drug[i, j])
            
            if local_drug < self.params.drug_kill_threshold:
                continue
            
            # Kill probability based on concentration and cell type sensitivity
            cell_type_str = cell.cell_type.value if hasattr(cell.cell_type, 'value') else str(cell.cell_type)
            sensitivity = sensitivity_map.get(cell_type_str, 1.0)
            
            # Also account for cell's own resistance level
            effective_sensitivity = sensitivity * (1.0 - cell.resistance_level * 0.5)
            
            kill_prob = (self.params.kill_probability_per_min * 
                        local_drug * effective_sensitivity * self.dt)
            
            if self.rng.random() < kill_prob:
                cell.is_alive = False
                self.metrics["cells_killed"] += 1
                type_key = cell_type_str.replace('_cell', '')
                if type_key in self.metrics["cells_killed_by_type"]:
                    self.metrics["cells_killed_by_type"][type_key] += 1
    
    def _update_metrics(self):
        viable = sum(1 for c in self.tumor_cells if c.is_alive)
        self.metrics["viable_cells"] = viable
        drug_given = self.metrics["total_drug_administered"]
        killed = self.metrics["cells_killed"]
        self.metrics["drug_efficiency"] = round(killed / max(1.0, drug_given), 4)
        # Distribution volume: voxels with drug > 0.1 threshold
        dv = int((self.drug > 0.1).sum()) * (self.voxel_size ** 2)  # µm²
        self.metrics["distribution_volume_um3"] = dv
    
    def step(self, n_substeps: int = 10):
        """Advance simulation by one macro-step (n_substeps of dt each)."""
        self.step_count += 1
        for _ in range(n_substeps):
            self._apply_catheter_source()
            self._diffuse_and_convect()
            self.time_min += self.dt
        self._update_tumor_cells()
        self._update_metrics()
    
    def run(self, total_steps: int = 100, record_interval: int = 10) -> List[Dict]:
        """Run full simulation and return history."""
        history = []
        for step in range(total_steps):
            self.step()
            if step % record_interval == 0 or step == total_steps - 1:
                history.append({
                    "step": self.step_count,
                    "time_min": round(self.time_min, 2),
                    "metrics": self.metrics.copy(),
                    "drug_max": round(float(self.drug.max()), 4),
                    "drug_mean": round(float(self.drug.mean()), 6),
                })
        return history
    
    def get_kill_rate(self) -> float:
        initial = self.metrics["initial_cells"]
        killed = self.metrics["cells_killed"]
        return round(killed / max(1, initial), 4)
    
    def get_drug_efficiency(self) -> float:
        """Kills per unit drug — key comparison metric vs nanobots."""
        return self.metrics["drug_efficiency"]
    
    def get_comparison_report(self) -> Dict:
        """Generate structured comparison report."""
        return {
            "method": "CED (Convection-Enhanced Delivery)",
            "time_elapsed_min": round(self.time_min, 1),
            "total_drug_administered": round(self.metrics["total_drug_administered"], 4),
            "cells_killed": self.metrics["cells_killed"],
            "initial_cells": self.metrics["initial_cells"],
            "kill_rate": self.get_kill_rate(),
            "drug_efficiency_kills_per_unit": self.get_drug_efficiency(),
            "cells_killed_by_type": self.metrics["cells_killed_by_type"],
            "distribution_volume_um2": self.metrics["distribution_volume_um3"],
            "limitations": [
                "No cell-type targeting — kills stem cells and differentiated cells equally poorly",
                "Drug distribution follows pressure gradient, not tumor biology",
                "No real-time feedback or adaptation",
                "Requires open skull surgery for catheter placement",
                "Cannot reach infiltrating cells at tumor margin",
                "BBB restricts drug to local infusion site",
            ]
        }
