#!/usr/bin/env python3
"""
Compare synthetic tumor geometries with BraTS patient data.

This script helps identify differences between synthetic and real tumor geometries
to improve the simulation parameters.
"""

import numpy as np
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from tumor_environment import TumorGeometry, create_brats_tumor_geometry
from brats_loader import load_brats_segmentation, find_brats_segmentation_file

def analyze_geometry(geometry: TumorGeometry, name: str):
    """Analyze and print geometry statistics."""
    stats = geometry.get_tumor_statistics()
    
    print(f"\n{'='*70}")
    print(f"{name} Geometry Statistics")
    print(f"{'='*70}")
    
    print(f"\nSpatial Properties:")
    print(f"  Tumor center: ({geometry.center[0]:.1f}, {geometry.center[1]:.1f}) µm")
    print(f"  Tumor radius: {geometry.tumor_radius:.1f} µm")
    print(f"  Necrotic core radius: {geometry.necrotic_core_radius:.1f} µm")
    print(f"  Core/tumor ratio: {geometry.necrotic_core_radius / geometry.tumor_radius:.2%}")
    
    print(f"\nCell Distribution:")
    print(f"  Total cells: {stats['living_cells']}")
    print(f"  Viable: {stats['phase_distribution']['viable']} ({stats['phase_distribution']['viable']/stats['living_cells']*100:.1f}%)")
    print(f"  Hypoxic: {stats['phase_distribution']['hypoxic']} ({stats['phase_distribution']['hypoxic']/stats['living_cells']*100:.1f}%)")
    print(f"  Necrotic: {stats['phase_distribution']['necrotic']} ({stats['phase_distribution']['necrotic']/stats['living_cells']*100:.1f}%)")
    print(f"  Apoptotic: {stats['phase_distribution']['apoptotic']} ({stats['phase_distribution']['apoptotic']/stats['living_cells']*100:.1f}%)")
    
    if 'cell_type_distribution' in stats:
        print(f"\nCell Type Distribution:")
        for cell_type, count in stats['cell_type_distribution'].items():
            percentage = count / stats['living_cells'] * 100
            print(f"  {cell_type}: {count} ({percentage:.1f}%)")
    
    print(f"\nInfrastructure:")
    print(f"  Blood vessels: {len(geometry.vessels)}")
    print(f"  Immune cells: {len(geometry.immune_cells)}")
    
    # Calculate cell density
    area = np.pi * (geometry.tumor_radius ** 2)
    cell_density = stats['living_cells'] / area
    print(f"\nCell Density: {cell_density:.6f} cells/µm²")
    
    return stats

def main():
    print("\n" + "="*70)
    print("Synthetic vs BraTS Tumor Geometry Comparison")
    print("="*70)
    
    # 1. Create synthetic geometry (baseline)
    print("\n📊 Generating synthetic tumor...")
    synthetic_geometry = TumorGeometry(
        center=(300.0, 300.0, 0.0),
        tumor_radius=200.0,
        necrotic_core_radius=50.0,
        vessel_density=0.01
    )
    synthetic_geometry.generate_circular_tumor(cell_density=0.001, dimensionality=2)
    synthetic_stats = analyze_geometry(synthetic_geometry, "Synthetic")
    
    # 2. Load a BraTS patient
    print("\n📊 Loading BraTS patient data...")
    BRATS_ADDITIONAL_TRAINING = os.getenv("BRATS_ADDITIONAL_TRAINING_PATH", "")
    
    if not BRATS_ADDITIONAL_TRAINING:
        print("❌ BRATS_ADDITIONAL_TRAINING_PATH not set in .env")
        return
    
    # Find first patient
    patient_folders = [d for d in os.listdir(BRATS_ADDITIONAL_TRAINING) 
                      if os.path.isdir(os.path.join(BRATS_ADDITIONAL_TRAINING, d))]
    
    if not patient_folders:
        print(f"❌ No patients found in {BRATS_ADDITIONAL_TRAINING}")
        return
    
    patient_id = patient_folders[0]
    patient_dir = os.path.join(BRATS_ADDITIONAL_TRAINING, patient_id)
    seg_file = find_brats_segmentation_file(patient_dir)
    
    if not seg_file:
        print(f"❌ No segmentation file for {patient_id}")
        return
    
    print(f"  Patient: {patient_id}")
    print(f"  File: {seg_file}")
    
    # Load segmentation
    seg_array, voxel_spacing = load_brats_segmentation(seg_file)
    print(f"  Shape: {seg_array.shape}, Spacing: {voxel_spacing} mm")
    
    # Create BraTS geometry
    brats_geometry = create_brats_tumor_geometry(
        segmentation_array=seg_array,
        voxel_spacing=voxel_spacing,
        cell_density=0.001,
        slice_idx=None,  # Use best slice
        target_domain_size=600.0,
        voxel_size=20.0
    )
    brats_stats = analyze_geometry(brats_geometry, f"BraTS ({patient_id})")
    
    # 3. Compare
    print(f"\n{'='*70}")
    print("Comparison Summary")
    print(f"{'='*70}")
    
    print(f"\n📏 Size Differences:")
    print(f"  Radius ratio (BraTS/Synthetic): {brats_geometry.tumor_radius / synthetic_geometry.tumor_radius:.2f}")
    print(f"  Core ratio (BraTS/Synthetic): {brats_geometry.necrotic_core_radius / synthetic_geometry.necrotic_core_radius:.2f}")
    
    print(f"\n🎯 Cell Phase Distribution:")
    for phase in ['viable', 'hypoxic', 'necrotic', 'apoptotic']:
        synth_pct = (synthetic_stats['phase_distribution'][phase] / synthetic_stats['living_cells']) * 100
        brats_pct = (brats_stats['phase_distribution'][phase] / brats_stats['living_cells']) * 100
        diff = brats_pct - synth_pct
        print(f"  {phase.capitalize()}: Synthetic={synth_pct:.1f}%, BraTS={brats_pct:.1f}% (Δ={diff:+.1f}%)")
    
    print(f"\n🏗️ Infrastructure:")
    print(f"  Vessels: Synthetic={len(synthetic_geometry.vessels)}, BraTS={len(brats_geometry.vessels)}")
    print(f"  Immune cells: Synthetic={len(synthetic_geometry.immune_cells)}, BraTS={len(brats_geometry.immune_cells)}")
    
    # 4. Recommendations
    print(f"\n{'='*70}")
    print("📋 Recommendations for Finetuning")
    print(f"{'='*70}")
    
    recommendations = []
    
    # Check hypoxic percentage
    brats_hypoxic_pct = (brats_stats['phase_distribution']['hypoxic'] / brats_stats['living_cells']) * 100
    synth_hypoxic_pct = (synthetic_stats['phase_distribution']['hypoxic'] / synthetic_stats['living_cells']) * 100
    if brats_hypoxic_pct > synth_hypoxic_pct + 10:
        recommendations.append(f"BraTS has {brats_hypoxic_pct:.1f}% hypoxic cells vs {synth_hypoxic_pct:.1f}% synthetic. Consider increasing hypoxic thresholds or initial hypoxic fraction.")
    
    # Check necrotic core
    brats_core_ratio = brats_geometry.necrotic_core_radius / brats_geometry.tumor_radius
    synth_core_ratio = synthetic_geometry.necrotic_core_radius / synthetic_geometry.tumor_radius
    if brats_core_ratio > synth_core_ratio + 0.1:
        recommendations.append(f"BraTS core is {brats_core_ratio:.2%} vs {synth_core_ratio:.2%} synthetic. Increase necrotic_core_radius/tumor_radius ratio.")
    
    # Check tumor size
    if brats_geometry.tumor_radius > synthetic_geometry.tumor_radius * 1.5:
        recommendations.append(f"BraTS tumors are larger ({brats_geometry.tumor_radius:.0f}µm vs {synthetic_geometry.tumor_radius:.0f}µm). Consider increasing default tumor_radius.")
    
    # Check cell density
    synth_area = np.pi * (synthetic_geometry.tumor_radius ** 2)
    synth_density = synthetic_stats['living_cells'] / synth_area
    brats_area = np.pi * (brats_geometry.tumor_radius ** 2)
    brats_density = brats_stats['living_cells'] / brats_area
    if abs(brats_density - synth_density) > synth_density * 0.2:
        recommendations.append(f"Cell density differs: BraTS={brats_density:.6f}, Synthetic={synth_density:.6f}. Adjust cell_density parameter.")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec}")
    else:
        print("\n✓ Synthetic geometry closely matches BraTS data!")
    
    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()

