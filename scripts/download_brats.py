#!/usr/bin/env python3
"""
BraTS Dataset Setup Script for Antelligence

Dataset: BraTS 2021 Task 1 (Glioblastoma Segmentation)
Source: https://www.synapse.org/#!Synapse:syn25829067
Alternative: https://www.kaggle.com/datasets/dschettler8845/brats-2021-task1

Usage:
    python scripts/download_brats.py --check    # check if data exists
    python scripts/download_brats.py --sample   # download a small sample
    python scripts/download_brats.py --kaggle   # download via kaggle API
"""
import os
import sys
import argparse
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data' / 'brats'
SAMPLE_DIR = DATA_DIR / 'samples'

def check_data():
    # Check if BraTS data exists, return stats
    if not DATA_DIR.exists():
        return {"exists": False, "patients": 0, "path": str(DATA_DIR)}
    
    # Look for patient directories (BraTS_2021_XXXXX pattern)
    patients = [d for d in DATA_DIR.iterdir() if d.is_dir() and 'BraTS' in d.name]
    seg_files = list(DATA_DIR.rglob('*seg.nii.gz'))
    
    return {
        "exists": len(patients) > 0 or len(seg_files) > 0,
        "patients": len(patients),
        "seg_files": len(seg_files),
        "path": str(DATA_DIR),
        "size_mb": sum(f.stat().st_size for f in DATA_DIR.rglob('*') if f.is_file()) // (1024*1024)
    }

def create_synthetic_brats_sample():
    """
    Create a synthetic BraTS-format NIfTI file for testing.
    Generates a realistic GBM tumor geometry without requiring the real dataset.
    This is used for development and testing before the real dataset is downloaded.
    """
    try:
        import nibabel as nib
        import numpy as np
    except ImportError:
        print("ERROR: nibabel not installed. Run: pip install nibabel")
        return False
    
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    patient_dir = SAMPLE_DIR / 'BraTS2021_synthetic_001'
    patient_dir.mkdir(exist_ok=True)
    
    # Create 240x240x155 volume (standard BraTS resolution)
    shape = (240, 240, 155)
    voxel_spacing = (1.0, 1.0, 1.0)  # 1mm isotropic
    
    seg = np.zeros(shape, dtype=np.uint8)
    
    # GBM anatomy: center of brain
    cx, cy, cz = 120, 120, 77
    
    # Layer 1: Necrotic core (label=1), ~15mm radius
    for x in range(shape[0]):
        for y in range(shape[1]):
            for z in range(shape[2]):
                r = ((x-cx)**2 + (y-cy)**2 + (z-cz)**2)**0.5
                if r < 15:
                    seg[x,y,z] = 1  # necrotic core
                elif r < 25:
                    seg[x,y,z] = 4  # enhancing tumor
                elif r < 40:
                    seg[x,y,z] = 2  # edema
    
    # Add some irregularity (tumor fingers)
    rng = np.random.default_rng(42)
    for _ in range(5):
        fx = cx + rng.integers(-20, 20)
        fy = cy + rng.integers(-20, 20)
        fz = cz + rng.integers(-10, 10)
        r_finger = rng.integers(5, 12)
        for x in range(max(0,fx-r_finger), min(shape[0],fx+r_finger)):
            for y in range(max(0,fy-r_finger), min(shape[1],fy+r_finger)):
                for z in range(max(0,fz-r_finger), min(shape[2],fz+r_finger)):
                    r = ((x-fx)**2 + (y-fy)**2 + (z-fz)**2)**0.5
                    if r < r_finger and seg[x,y,z] == 0:
                        seg[x,y,z] = 4  # enhancing tumor finger
    
    # Save as NIfTI
    affine = np.diag([1.0, 1.0, 1.0, 1.0])  # 1mm isotropic
    nib.save(nib.Nifti1Image(seg, affine), str(patient_dir / 'seg.nii.gz'))
    
    # Create a simple T1ce volume (just intensity map from seg)
    t1ce = np.zeros(shape, dtype=np.float32)
    t1ce[seg == 4] = 1.0   # bright enhancement
    t1ce[seg == 1] = 0.2   # dark necrosis
    t1ce[seg == 2] = 0.6   # intermediate edema
    t1ce += rng.normal(0, 0.05, shape).astype(np.float32)  # noise
    nib.save(nib.Nifti1Image(t1ce, affine), str(patient_dir / 't1ce.nii.gz'))
    
    metadata = {
        "patient_id": "BraTS2021_synthetic_001",
        "type": "synthetic",
        "shape": list(shape),
        "voxel_spacing_mm": list(voxel_spacing),
        "tumor_center_voxel": [cx, cy, cz],
        "labels": {"0": "background", "1": "necrotic_core", "2": "edema", "4": "enhancing_tumor"}
    }
    with open(patient_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Synthetic BraTS sample created at: {patient_dir}")
    print(f"Segmentation shape: {shape}, Labels: NCR=1, ED=2, ET=4")
    print(f"Tumor center: ({cx}, {cy}, {cz}) voxels")
    return True

def kaggle_download():
    print("To download BraTS 2021 via Kaggle:")
    print("1. Install kaggle CLI: pip install kaggle")
    print("2. Get API token from: https://www.kaggle.com/settings -> API -> Create New Token")
    print("3. Place ~/.kaggle/kaggle.json")
    print("4. Run: kaggle datasets download -d dschettler8845/brats-2021-task1 -p data/brats/ --unzip")
    print("")
    print("OR download manually from Synapse:")
    print("https://www.synapse.org/#!Synapse:syn25829067")
    print("Registration required (free academic access)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BraTS dataset setup for Antelligence')
    parser.add_argument('--check', action='store_true', help='Check if data exists')
    parser.add_argument('--sample', action='store_true', help='Create synthetic sample for testing')
    parser.add_argument('--kaggle', action='store_true', help='Show Kaggle download instructions')
    args = parser.parse_args()
    
    if args.check:
        info = check_data()
        print(json.dumps(info, indent=2))
    elif args.sample:
        create_synthetic_brats_sample()
    elif args.kaggle:
        kaggle_download()
    else:
        info = check_data()
        if not info['exists']:
            print("No BraTS data found. Creating synthetic sample for development...")
            create_synthetic_brats_sample()
        else:
            print(json.dumps(info, indent=2))
