"""
BraTS 2024 Data Loader

This module handles loading and preprocessing BraTS 2024 glioblastoma segmentation data
from NIfTI files for use in the PhysiCell-based tumor nanobot simulation.

BraTS Label Encoding:
- 0: Background (healthy brain tissue)
- 1: Necrotic core (NCR) - dead/dying tumor cells
- 2: Peritumoral edema (ED) - fluid accumulation around tumor
- 4: Enhancing tumor (ET) - actively growing tumor cells
"""

import os
import numpy as np
import nibabel as nib
from typing import Tuple, Optional, List, Dict
from pathlib import Path
import json
from dotenv import load_dotenv

load_dotenv()

# BraTS data paths from environment
BRATS_TRAINING_PATH = os.getenv("BRATS_TRAINING_PATH", "")
BRATS_VALIDATION_PATH = os.getenv("BRATS_VALIDATION_PATH", "")
BRATS_ADDITIONAL_TRAINING_PATH = os.getenv("BRATS_ADDITIONAL_TRAINING_PATH", "")
BRATS_CACHE_DIR = os.getenv("BRATS_DATA_CACHE_DIR", "backend/data/processed")

# BraTS label constants
LABEL_BACKGROUND = 0
LABEL_NCR = 1  # Necrotic core
LABEL_ED = 2   # Peritumoral edema
LABEL_ET = 4   # Enhancing tumor


def find_brats_segmentation_file(patient_dir: str) -> Optional[str]:
    """
    Find the segmentation file in a BraTS patient directory.
    
    BraTS 2024 format: [PatientID]-seg.nii.gz
    
    Args:
        patient_dir: Path to patient directory
        
    Returns:
        Path to segmentation file or None if not found
    """
    patient_dir = Path(patient_dir)
    if not patient_dir.exists():
        return None
    
    # Look for segmentation file
    seg_files = list(patient_dir.glob("*seg.nii.gz"))
    if seg_files:
        return str(seg_files[0])
    
    return None


def load_brats_segmentation(seg_path: str) -> Tuple[np.ndarray, Tuple[float, float, float]]:
    """
    Load BraTS segmentation NIfTI file.
    
    Args:
        seg_path: Path to segmentation .nii.gz file
        
    Returns:
        Tuple of (segmentation_array, voxel_spacing_mm)
        - segmentation_array: 3D numpy array with tumor labels (0, 1, 2, 4)
        - voxel_spacing_mm: (dx, dy, dz) in millimeters
    """
    if not os.path.exists(seg_path):
        raise FileNotFoundError(f"Segmentation file not found: {seg_path}")
    
    # Load NIfTI file
    nii_img = nib.load(seg_path)
    seg_array = nii_img.get_fdata().astype(np.uint8)
    
    # Get voxel spacing from header (in mm)
    header = nii_img.header
    voxel_spacing = tuple(header.get_zooms()[:3])  # (dx, dy, dz) in mm
    
    return seg_array, voxel_spacing


def extract_tumor_regions(seg_array: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Extract individual tumor regions from BraTS segmentation.
    
    Args:
        seg_array: 3D segmentation array with labels (0, 1, 2, 4)
        
    Returns:
        Dictionary with binary masks for each tumor region:
        {
            'ncr': binary mask for necrotic core (label 1),
            'ed': binary mask for edema (label 2),
            'et': binary mask for enhancing tumor (label 4),
            'whole_tumor': combined mask (1, 2, 4),
            'tumor_core': combined mask (1, 4) - NCR + ET
        }
    """
    ncr_mask = (seg_array == LABEL_NCR).astype(np.uint8)
    ed_mask = (seg_array == LABEL_ED).astype(np.uint8)
    et_mask = (seg_array == LABEL_ET).astype(np.uint8)
    
    whole_tumor = ((seg_array == LABEL_NCR) | 
                   (seg_array == LABEL_ED) | 
                   (seg_array == LABEL_ET)).astype(np.uint8)
    
    tumor_core = ((seg_array == LABEL_NCR) | 
                  (seg_array == LABEL_ET)).astype(np.uint8)
    
    return {
        'ncr': ncr_mask,
        'ed': ed_mask,
        'et': et_mask,
        'whole_tumor': whole_tumor,
        'tumor_core': tumor_core
    }


def get_2d_slice(volume: np.ndarray, slice_idx: int, axis: int = 2) -> np.ndarray:
    """
    Extract a 2D slice from a 3D volume.
    
    Args:
        volume: 3D numpy array
        slice_idx: Index of slice to extract
        axis: Axis along which to slice (0=x, 1=y, 2=z, default=2 for axial)
        
    Returns:
        2D numpy array
    """
    if axis == 0:
        return volume[slice_idx, :, :]
    elif axis == 1:
        return volume[:, slice_idx, :]
    elif axis == 2:
        return volume[:, :, slice_idx]
    else:
        raise ValueError(f"Invalid axis: {axis}. Must be 0, 1, or 2")


def resample_2d_slice(
    slice_2d: np.ndarray, 
    target_size: Tuple[int, int], 
    method: str = 'downscale'
) -> np.ndarray:
    """
    Resample a 2D slice to target size.
    
    Args:
        slice_2d: 2D numpy array
        target_size: (width, height) target dimensions
        method: 'downscale' (simple downsampling) or 'interpolate' (bicubic)
        
    Returns:
        Resampled 2D array
    """
    from scipy import ndimage
    
    if method == 'downscale':
        # Simple downsampling by skipping pixels
        h, w = slice_2d.shape
        target_h, target_w = target_size
        
        step_h = h / target_h
        step_w = w / target_w
        
        indices_h = np.round(np.arange(0, h, step_h)).astype(int)
        indices_w = np.round(np.arange(0, w, step_w)).astype(int)
        
        # Clip to valid range
        indices_h = indices_h[indices_h < h]
        indices_w = indices_w[indices_w < w]
        
        resampled = slice_2d[np.ix_(indices_h, indices_w)]
        
        # Pad or crop to exact target size
        if resampled.shape[0] < target_h or resampled.shape[1] < target_w:
            # Pad
            result = np.zeros(target_size, dtype=slice_2d.dtype)
            result[:resampled.shape[0], :resampled.shape[1]] = resampled
            return result
        else:
            # Crop
            return resampled[:target_h, :target_w]
    
    elif method == 'interpolate':
        # Use scipy for better quality interpolation
        zoom_h = target_size[0] / slice_2d.shape[0]
        zoom_w = target_size[1] / slice_2d.shape[1]
        
        resampled = ndimage.zoom(slice_2d, (zoom_h, zoom_w), order=1, mode='nearest')
        return resampled
    
    else:
        raise ValueError(f"Unknown method: {method}. Use 'downscale' or 'interpolate'")


def find_best_slice(seg_array: np.ndarray, axis: int = 2) -> int:
    """
    Find the slice with maximum tumor area (for 2D simulation).
    
    Args:
        seg_array: 3D segmentation array
        axis: Axis to search along (default=2 for axial slices)
        
    Returns:
        Index of slice with maximum tumor area
    """
    whole_tumor_mask = ((seg_array == LABEL_NCR) | 
                        (seg_array == LABEL_ED) | 
                        (seg_array == LABEL_ET))
    
    if axis == 2:
        tumor_areas = np.sum(whole_tumor_mask, axis=(0, 1))
    elif axis == 1:
        tumor_areas = np.sum(whole_tumor_mask, axis=(0, 2))
    elif axis == 0:
        tumor_areas = np.sum(whole_tumor_mask, axis=(1, 2))
    else:
        raise ValueError(f"Invalid axis: {axis}")
    
    best_slice = int(np.argmax(tumor_areas))
    return best_slice


def list_brats_patients(data_path: str) -> List[str]:
    """
    List all BraTS patient directories in a data path.
    
    Args:
        data_path: Path to BraTS dataset root
        
    Returns:
        List of patient directory names
    """
    if not os.path.exists(data_path):
        return []
    
    data_path = Path(data_path)
    patients = []
    
    # BraTS 2024 structure: [PatientID]/[PatientID]-seg.nii.gz
    for item in data_path.iterdir():
        if item.is_dir():
            # Check if it has a segmentation file
            seg_file = find_brats_segmentation_file(str(item))
            if seg_file:
                patients.append(item.name)
    
    return sorted(patients)


def get_patient_metadata(patient_dir: str) -> Dict:
    """
    Extract metadata for a BraTS patient.
    
    Args:
        patient_dir: Path to patient directory
        
    Returns:
        Dictionary with patient metadata
    """
    patient_dir = Path(patient_dir)
    seg_file = find_brats_segmentation_file(str(patient_dir))
    
    if not seg_file:
        return {}
    
    try:
        seg_array, voxel_spacing = load_brats_segmentation(seg_file)
        regions = extract_tumor_regions(seg_array)
        
        # Calculate tumor statistics
        ncr_volume = np.sum(regions['ncr'])
        ed_volume = np.sum(regions['ed'])
        et_volume = np.sum(regions['et'])
        whole_tumor_volume = np.sum(regions['whole_tumor'])
        
        # Find best slice
        best_slice = find_best_slice(seg_array)
        
        return {
            'patient_id': patient_dir.name,
            'seg_file': seg_file,
            'shape': seg_array.shape,
            'voxel_spacing_mm': voxel_spacing,
            'ncr_volume_voxels': int(ncr_volume),
            'ed_volume_voxels': int(ed_volume),
            'et_volume_voxels': int(et_volume),
            'whole_tumor_volume_voxels': int(whole_tumor_volume),
            'best_slice': best_slice,
            'best_slice_tumor_area': int(np.sum(regions['whole_tumor'][:, :, best_slice]))
        }
    except Exception as e:
        print(f"Error loading metadata for {patient_dir}: {e}")
        return {}


def build_dataset_index() -> Dict:
    """
    Build an index of all available BraTS patients across all datasets.
    
    Returns:
        Dictionary mapping dataset names to lists of patient metadata
    """
    datasets = {}
    
    # Training data (Kaggle)
    if BRATS_TRAINING_PATH and os.path.exists(BRATS_TRAINING_PATH):
        patients = list_brats_patients(BRATS_TRAINING_PATH)
        datasets['training'] = []
        for patient_id in patients:
            patient_dir = os.path.join(BRATS_TRAINING_PATH, patient_id)
            metadata = get_patient_metadata(patient_dir)
            if metadata:
                datasets['training'].append(metadata)
    
    # Validation data (Synapse)
    if BRATS_VALIDATION_PATH and os.path.exists(BRATS_VALIDATION_PATH):
        patients = list_brats_patients(BRATS_VALIDATION_PATH)
        datasets['validation'] = []
        for patient_id in patients:
            patient_dir = os.path.join(BRATS_VALIDATION_PATH, patient_id)
            metadata = get_patient_metadata(patient_dir)
            if metadata:
                datasets['validation'].append(metadata)
    
    # Additional training data (Synapse)
    if BRATS_ADDITIONAL_TRAINING_PATH and os.path.exists(BRATS_ADDITIONAL_TRAINING_PATH):
        patients = list_brats_patients(BRATS_ADDITIONAL_TRAINING_PATH)
        datasets['additional_training'] = []
        for patient_id in patients:
            patient_dir = os.path.join(BRATS_ADDITIONAL_TRAINING_PATH, patient_id)
            metadata = get_patient_metadata(patient_dir)
            if metadata:
                datasets['additional_training'].append(metadata)
    
    return datasets

