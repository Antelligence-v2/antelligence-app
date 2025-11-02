#!/usr/bin/env python3
"""
Test the BraTS API endpoints.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_list_patients():
    """Test listing BraTS patients."""
    print("\n" + "="*70)
    print("Testing GET /brats/patients")
    print("="*70)
    
    response = requests.get(f"{BASE_URL}/brats/patients")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✓ Found {data['total_patients']} total patients:")
        for dataset, patients in data['datasets'].items():
            print(f"  {dataset}: {len(patients)} patients")
            if patients:
                print(f"    Example: {patients[0]}")
        return True
    else:
        print(f"✗ Error: {response.text}")
        return False


def test_brats_simulation():
    """Test BraTS-based simulation."""
    print("\n" + "="*70)
    print("Testing POST /simulation/tumor/from-brats")
    print("="*70)
    
    config = {
        "patient_id": "BraTS-GLI-02405-100",
        "dataset": "additional_training",
        "slice_idx": None,
        "domain_size": 2000.0,
        "voxel_size": 20.0,
        "n_nanobots": 10,
        "agent_type": "Rule-Based",
        "max_steps": 20,
        "cell_density": 0.001,
        "vessel_density": 0.01
    }
    
    print(f"\nConfiguration:")
    print(json.dumps(config, indent=2))
    
    response = requests.post(
        f"{BASE_URL}/simulation/tumor/from-brats",
        json=config
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ Simulation completed!")
        print(f"  Total steps: {result['total_steps_run']}")
        print(f"  Living cells: {result['tumor_statistics']['living_cells']}")
        print(f"  Viable: {result['tumor_statistics']['phase_distribution']['viable']}")
        print(f"  Hypoxic: {result['tumor_statistics']['phase_distribution']['hypoxic']}")
        print(f"  Necrotic: {result['tumor_statistics']['phase_distribution']['necrotic']}")
        return True
    else:
        print(f"✗ Error: {response.text}")
        return False


if __name__ == "__main__":
    import sys
    
    print("\n" + "="*70)
    print("BraTS API Test Suite")
    print("="*70)
    print("\nMake sure backend server is running: uvicorn main:app --reload")
    input("\nPress Enter to continue...")
    
    # Test 1: List patients
    list_ok = test_list_patients()
    
    # Test 2: Run simulation
    if list_ok:
        sim_ok = test_brats_simulation()
        sys.exit(0 if sim_ok else 1)
    
    sys.exit(0 if list_ok else 1)

