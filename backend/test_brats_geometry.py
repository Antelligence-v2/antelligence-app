#!/usr/bin/env python3
"""
Test creating tumor geometry from BraTS segmentation.
"""

import os
import sys
import numpy as np

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from brats_loader import load_brats_segmentation, find_brats_segmentation_file
from tumor_environment import create_brats_tumor_geometry, TumorGeometry

def test_brats_geometry():
    """Test creating geometry from BraTS patient."""
    print("\n" + "="*70)
    print("Testing BraTS Tumor Geometry Creation")
    print("="*70)
    
    # Find a test patient
    from brats_loader import BRATS_ADDITIONAL_TRAINING_PATH, list_brats_patients
    
    patients = list_brats_patients(BRATS_ADDITIONAL_TRAINING_PATH)
    if not patients:
        print("✗ No patients found")
        return False
    
    patient_id = patients[0]
    patient_dir = os.path.join(BRATS_ADDITIONAL_TRAINING_PATH, patient_id)
    seg_file = find_brats_segmentation_file(patient_dir)
    
    if not seg_file:
        print(f"✗ No segmentation file for {patient_id}")
        return False
    
    print(f"\nTesting with patient: {patient_id}")
    print(f"Segmentation: {seg_file}")
    
    try:
        # Load segmentation
        seg_array, voxel_spacing = load_brats_segmentation(seg_file)
        print(f"✓ Loaded: shape={seg_array.shape}, spacing={voxel_spacing} mm")
        
        # Create geometry with resampling
        geometry = create_brats_tumor_geometry(
            segmentation_array=seg_array,
            voxel_spacing=voxel_spacing,
            cell_density=0.001,
            slice_idx=None,  # Use best slice
            target_domain_size=2000.0,  # Resample to 2000 µm domain for more cells
            voxel_size=20.0  # 20 µm voxels
        )
        
        # Check results
        print(f"\n✓ Geometry created successfully!")
        print(f"  Tumor center: {geometry.center}")
        print(f"  Tumor radius: {geometry.tumor_radius:.1f} µm")
        print(f"  Total cells: {len(geometry.tumor_cells)}")
        print(f"  Vessels: {len(geometry.vessels)}")
        
        # Get statistics
        stats = geometry.get_tumor_statistics()
        print(f"\n  Tumor statistics:")
        print(f"    Living cells: {stats['living_cells']}")
        print(f"    Viable: {stats['phase_distribution']['viable']}")
        print(f"    Hypoxic: {stats['phase_distribution']['hypoxic']}")
        print(f"    Necrotic: {stats['phase_distribution']['necrotic']}")
        print(f"    Apoptotic: {stats['phase_distribution']['apoptotic']}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_brats_geometry()
    sys.exit(0 if success else 1)

