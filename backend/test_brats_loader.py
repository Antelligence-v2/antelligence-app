#!/usr/bin/env python3
"""
Quick test script for BraTS data loader.
Tests that data paths are accessible and files can be loaded.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from brats_loader import (
    find_brats_segmentation_file,
    list_brats_patients,
    get_patient_metadata,
    build_dataset_index
)

def test_data_paths():
    """Test that all BraTS data paths exist."""
    print("\n" + "="*70)
    print("Testing BraTS Data Paths")
    print("="*70)
    
    from brats_loader import (
        BRATS_TRAINING_PATH,
        BRATS_VALIDATION_PATH,
        BRATS_ADDITIONAL_TRAINING_PATH
    )
    
    paths = {
        "Training (Kaggle)": BRATS_TRAINING_PATH,
        "Validation (Synapse)": BRATS_VALIDATION_PATH,
        "Additional Training (Synapse)": BRATS_ADDITIONAL_TRAINING_PATH
    }
    
    for name, path in paths.items():
        if path and os.path.exists(path):
            print(f"✓ {name}: {path}")
        else:
            print(f"✗ {name}: {'Not set' if not path else 'Path does not exist: ' + path}")
    
    return all(path and os.path.exists(path) for path in paths.values())


def test_list_patients():
    """Test listing patients from datasets."""
    print("\n" + "="*70)
    print("Testing Patient Listing")
    print("="*70)
    
    from brats_loader import (
        BRATS_TRAINING_PATH,
        BRATS_VALIDATION_PATH,
        BRATS_ADDITIONAL_TRAINING_PATH
    )
    
    all_patients = []
    
    # Test training
    if BRATS_TRAINING_PATH and os.path.exists(BRATS_TRAINING_PATH):
        patients = list_brats_patients(BRATS_TRAINING_PATH)
        print(f"\nTraining (Kaggle): {len(patients)} patients found")
        if patients:
            print(f"  Example: {patients[0]}")
            all_patients.extend([(p, 'training') for p in patients[:3]])  # First 3
    
    # Test validation
    if BRATS_VALIDATION_PATH and os.path.exists(BRATS_VALIDATION_PATH):
        patients = list_brats_patients(BRATS_VALIDATION_PATH)
        print(f"Validation (Synapse): {len(patients)} patients found")
        if patients:
            print(f"  Example: {patients[0]}")
            all_patients.extend([(p, 'validation') for p in patients[:3]])  # First 3
    
    # Test additional training
    if BRATS_ADDITIONAL_TRAINING_PATH and os.path.exists(BRATS_ADDITIONAL_TRAINING_PATH):
        patients = list_brats_patients(BRATS_ADDITIONAL_TRAINING_PATH)
        print(f"Additional Training (Synapse): {len(patients)} patients found")
        if patients:
            print(f"  Example: {patients[0]}")
            all_patients.extend([(p, 'additional_training') for p in patients[:3]])  # First 3
    
    return all_patients


def test_load_segmentation(patient_id: str, dataset: str):
    """Test loading a segmentation file."""
    print("\n" + "="*70)
    print(f"Testing Segmentation Loading: {patient_id} ({dataset})")
    print("="*70)
    
    from brats_loader import (
        BRATS_TRAINING_PATH,
        BRATS_VALIDATION_PATH,
        BRATS_ADDITIONAL_TRAINING_PATH,
        load_brats_segmentation,
        extract_tumor_regions,
        find_best_slice
    )
    
    # Find patient directory
    if dataset == 'training':
        base_path = BRATS_TRAINING_PATH
    elif dataset == 'validation':
        base_path = BRATS_VALIDATION_PATH
    elif dataset == 'additional_training':
        base_path = BRATS_ADDITIONAL_TRAINING_PATH
    else:
        print(f"✗ Unknown dataset: {dataset}")
        return False
    
    patient_dir = os.path.join(base_path, patient_id)
    seg_file = find_brats_segmentation_file(patient_dir)
    
    if not seg_file:
        print(f"✗ Segmentation file not found for {patient_id}")
        return False
    
    print(f"✓ Found segmentation: {seg_file}")
    
    try:
        # Load segmentation
        seg_array, voxel_spacing = load_brats_segmentation(seg_file)
        print(f"✓ Loaded segmentation: shape={seg_array.shape}, spacing={voxel_spacing} mm")
        
        # Extract regions
        regions = extract_tumor_regions(seg_array)
        print(f"✓ Extracted tumor regions:")
        print(f"  NCR (necrotic): {np.sum(regions['ncr'])} voxels")
        print(f"  ED (edema): {np.sum(regions['ed'])} voxels")
        print(f"  ET (enhancing): {np.sum(regions['et'])} voxels")
        print(f"  Whole tumor: {np.sum(regions['whole_tumor'])} voxels")
        
        # Find best slice
        best_slice = find_best_slice(seg_array)
        print(f"✓ Best slice (axial): {best_slice} with {np.sum(regions['whole_tumor'][:, :, best_slice])} tumor voxels")
        
        return True
        
    except Exception as e:
        print(f"✗ Error loading segmentation: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("BraTS Data Loader Test Suite")
    print("="*70)
    
    # Test 1: Data paths
    paths_ok = test_data_paths()
    if not paths_ok:
        print("\n⚠️  Some data paths are not accessible. Please check your .env file.")
        print("   Continuing with available datasets...")
    
    # Test 2: List patients
    patients = test_list_patients()
    
    if not patients:
        print("\n⚠️  No patients found in any dataset.")
        print("   Please verify:")
        print("   1. Data paths are correct in .env")
        print("   2. Data has been unzipped")
        print("   3. Directory structure matches BraTS 2024 format")
        return 1
    
    # Test 3: Load one segmentation
    if patients:
        patient_id, dataset = patients[0]
        load_ok = test_load_segmentation(patient_id, dataset)
        
        if load_ok:
            print("\n" + "="*70)
            print("✅ All tests passed! BraTS loader is working.")
            print("="*70)
            print("\nNext steps:")
            print("  1. Integrate with create_brats_tumor_geometry()")
            print("  2. Add API endpoint for BraTS simulations")
            print("  3. Update frontend to select patients")
            return 0
        else:
            print("\n✗ Segmentation loading failed.")
            return 1
    
    return 0


if __name__ == "__main__":
    import numpy as np
    exit_code = main()
    sys.exit(exit_code)

