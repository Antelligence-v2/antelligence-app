"""
BraTS NIfTI + TCGA TIFF Loader for Antelligence

Converts BraTS MRI segmentation volumes into TumorGeometry objects
that the nanobot simulation can use.

Supported formats:
  1. BraTS 2024 GLI - NIfTI .nii.gz, labels: 1=NCR, 2=ED, 3=ET (BraTS2024) or 4=ET (BraTS2021)
  2. BraTS 2021 synthetic NIfTI - labels: 1=NCR, 2=ED, 4=ET
  3. TCGA BraTS 2019 - 2D TIFF slices with binary masks

BraTS segmentation labels (auto-detected):
  0 = background
  1 = necrotic tumor core (NCR) -> maps to NECROTIC phase cells
  2 = peritumoral edema (ED) -> maps to HYPOXIC phase cells
  3 = GD-enhancing tumor ET (BraTS 2024) -> maps to VIABLE phase cells
  4 = GD-enhancing tumor ET (BraTS 2021) -> maps to VIABLE phase cells

Coordinate system:
  BraTS: voxel indices (i, j, k) with 1mm isotropic spacing
  Simulation: micrometers (um), centered at (domain_size/2, domain_size/2)
  Conversion: sim_pos = (voxel_idx - tumor_center_voxel) * voxel_spacing_mm * 1000 + domain_center
  But we scale to fit in domain_size, so:
  scale = domain_size / (max_tumor_extent_mm * 1000)
"""
import numpy as np
import json
import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Union

DATA_DIR = Path(__file__).parent.parent / 'data' / 'brats'


class BraTSVolume:
    """Loaded and parsed BraTS patient volume (NIfTI format)."""

    def __init__(self, patient_dir: Path):
        self.patient_dir = patient_dir
        self.patient_id = patient_dir.name
        self.seg = None          # uint8 (H,W,D)
        self.t1ce = None         # float32 (H,W,D) optional
        self.affine = None       # 4x4 affine matrix
        self.voxel_spacing = (1.0, 1.0, 1.0)  # mm
        self.shape = None
        self.tumor_center = None  # voxel coords
        self.tumor_bbox = None    # (min_i, max_i, min_j, max_j, min_k, max_k)
        self._load()

    def _load(self):
        try:
            import nibabel as nib
        except ImportError:
            raise ImportError("nibabel required: pip install nibabel")

        seg_path = self.patient_dir / 'seg.nii.gz'
        if not seg_path.exists():
            # Try other naming conventions (e.g. BraTS2024 style)
            segs = list(self.patient_dir.glob('*seg*.nii.gz'))
            if not segs:
                raise FileNotFoundError(f"No seg.nii.gz in {self.patient_dir}")
            seg_path = segs[0]

        img = nib.load(str(seg_path))
        self.seg = np.array(img.get_fdata(), dtype=np.uint8)
        self.affine = img.affine
        self.shape = self.seg.shape

        # Extract voxel spacing from affine
        self.voxel_spacing = tuple(abs(self.affine[i, i]) for i in range(3))

        # Load T1ce / T1c if available (for intensity context)
        # BraTS 2024 uses *-t1c.nii.gz; BraTS 2021 uses t1ce.nii.gz
        t1ce_path = self.patient_dir / 't1ce.nii.gz'
        if t1ce_path.exists():
            t1ce_img = nib.load(str(t1ce_path))
            self.t1ce = np.array(t1ce_img.get_fdata(), dtype=np.float32)
        else:
            t1c_files = list(self.patient_dir.glob('*t1c*.nii.gz'))
            if t1c_files:
                t1ce_img = nib.load(str(t1c_files[0]))
                self.t1ce = np.array(t1ce_img.get_fdata(), dtype=np.float32)

        # Compute tumor bounding box and center
        tumor_mask = self.seg > 0
        if tumor_mask.any():
            coords = np.where(tumor_mask)
            self.tumor_bbox = (
                int(coords[0].min()), int(coords[0].max()),
                int(coords[1].min()), int(coords[1].max()),
                int(coords[2].min()), int(coords[2].max())
            )
            self.tumor_center = (
                int((coords[0].min() + coords[0].max()) / 2),
                int((coords[1].min() + coords[1].max()) / 2),
                int((coords[2].min() + coords[2].max()) / 2)
            )

    def get_tumor_slice(self, axis: int = 2, offset: int = 0) -> np.ndarray:
        """Get 2D cross-section through tumor center."""
        if self.tumor_center is None:
            return np.zeros((self.shape[0], self.shape[1]), dtype=np.uint8)
        z = self.tumor_center[axis] + offset
        z = np.clip(z, 0, self.shape[axis] - 1)
        if axis == 0: return self.seg[z, :, :]
        if axis == 1: return self.seg[:, z, :]
        return self.seg[:, :, z]

    def get_statistics(self) -> Dict:
        if self.seg is None:
            return {}
        # Auto-detect ET label (BraTS 2024 uses 3, BraTS 2021 uses 4)
        unique_labels = set(np.unique(self.seg).tolist()) - {0}
        if 4 in unique_labels:
            et_label = 4
        elif 3 in unique_labels:
            et_label = 3
        else:
            et_label = max(unique_labels) if unique_labels else 1

        ncr = int((self.seg == 1).sum())
        ed = int((self.seg == 2).sum())
        et = int((self.seg == et_label).sum())
        tumor_total = ncr + ed + et
        vox_vol = self.voxel_spacing[0] * self.voxel_spacing[1] * self.voxel_spacing[2]
        return {
            "patient_id": self.patient_id,
            "source": "BraTS-NIfTI",
            "format": "NIfTI-3D",
            "shape": list(self.shape),
            "voxel_spacing_mm": list(self.voxel_spacing),
            "tumor_center_voxel": list(self.tumor_center) if self.tumor_center else None,
            "tumor_bbox": list(self.tumor_bbox) if self.tumor_bbox else None,
            "et_label_used": et_label,
            "ncr_voxels": ncr, "ed_voxels": ed, "et_voxels": et,
            "ncr_cm3": round(ncr * vox_vol / 1000, 2),
            "ed_cm3": round(ed * vox_vol / 1000, 2),
            "et_cm3": round(et * vox_vol / 1000, 2),
            "tumor_total_cm3": round(tumor_total * vox_vol / 1000, 2),
            "necrotic_fraction": round(ncr / max(1, tumor_total), 3),
            "edema_fraction": round(ed / max(1, tumor_total), 3),
            "enhancing_fraction": round(et / max(1, tumor_total), 3),
        }


class TCGASliceVolume:
    """Loads a 2D TIFF MRI slice + binary mask from TCGA BraTS 2019 format."""

    def __init__(self, tumor_path: Path, mask_path: Path):
        self.patient_id = tumor_path.stem  # e.g. TCGA_CS_4941_19960909_11
        self.tumor_path = tumor_path
        self.mask_path = mask_path
        self.tumor_img = None   # numpy (256,256) float32 MRI
        self.mask_img = None    # numpy (256,256) uint8 binary
        self.tumor_center = None
        self.tumor_bbox = None
        self._load()

    def _load(self):
        from PIL import Image
        tumor_pil = Image.open(self.tumor_path)
        # Convert to grayscale if RGB/RGBA (MRI intensity channel)
        if tumor_pil.mode != 'L':
            tumor_pil = tumor_pil.convert('L')
        tumor_arr = np.array(tumor_pil, dtype=np.float32)
        # Normalize to 0-1
        if tumor_arr.max() > 0:
            tumor_arr = tumor_arr / tumor_arr.max()
        self.tumor_img = tumor_arr

        mask_arr = np.array(Image.open(self.mask_path), dtype=np.uint8)
        # Binary: 255 -> 1
        self.mask_img = (mask_arr > 127).astype(np.uint8)

        # Compute tumor bbox and center
        if self.mask_img.any():
            rows, cols = np.where(self.mask_img > 0)
            self.tumor_bbox = (rows.min(), rows.max(), cols.min(), cols.max())
            self.tumor_center = (
                int((rows.min() + rows.max()) / 2),
                int((cols.min() + cols.max()) / 2)
            )

    def get_statistics(self) -> dict:
        if self.mask_img is None:
            return {}
        tumor_pixels = int(self.mask_img.sum())
        total = self.mask_img.size
        # Assume 1mm/pixel for TCGA slices -> tumor area in mm2
        return {
            'patient_id': self.patient_id,
            'source': 'TCGA-BraTS2019',
            'format': 'TIFF-2D',
            'shape': list(self.mask_img.shape),
            'tumor_pixels': tumor_pixels,
            'tumor_pct': round(tumor_pixels / total * 100, 2),
            'tumor_center_px': list(self.tumor_center) if self.tumor_center else None,
            'tumor_bbox': list(self.tumor_bbox) if self.tumor_bbox else None,
        }

    def get_tumor_slice(self, axis=None, offset=0):
        """Returns the 2D mask (TCGA only has one slice per file)."""
        return self.mask_img


def load_brats_patient(
    patient_id: Optional[str] = None
) -> Optional[Union[BraTSVolume, TCGASliceVolume]]:
    """
    Load a BraTS patient volume. Checks data sources in priority order:
      1. BraTS2024-GLI NIfTI (most detailed, multi-label)
      2. BraTS2021 synthetic NIfTI samples (fallback)
      3. TCGA 2019 TIFF slices (2D binary mask)

    If patient_id is None, loads the first available patient.
    Falls back to synthetic sample if no real NIfTI data exists.
    Returns BraTSVolume or TCGASliceVolume depending on what is found.
    """
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # --- Priority 1: BraTS2024-GLI NIfTI ---
    gli_dir = DATA_DIR / 'BraTS2024-GLI'
    gli_patients = []
    if gli_dir.exists():
        gli_patients = sorted([
            d for d in gli_dir.iterdir()
            if d.is_dir() and any(d.glob('*seg*.nii.gz'))
        ])

    # --- Priority 2: BraTS2021 / generic NIfTI (samples/ or elsewhere) ---
    # Handles both exact 'seg.nii.gz' and prefixed '*_seg.nii.gz' (BraTS2021 style)
    nifti_patients = sorted([
        d for d in DATA_DIR.rglob('*')
        if d.is_dir()
        and any(d.glob('*seg*.nii.gz'))
        and d not in gli_patients
    ])
    sample_patients = sorted([
        d for d in (DATA_DIR / 'samples').rglob('*')
        if d.is_dir() and any(d.glob('*seg*.nii.gz'))
    ]) if (DATA_DIR / 'samples').exists() else []

    all_nifti = gli_patients + nifti_patients + sample_patients

    # --- Try NIfTI first ---
    if all_nifti:
        if patient_id:
            match = [p for p in all_nifti if patient_id in p.name]
            patient_dir = match[0] if match else all_nifti[0]
        else:
            patient_dir = all_nifti[0]

        try:
            print(f"[BraTS] Loading NIfTI patient: {patient_dir.name}")
            vol = BraTSVolume(patient_dir)
            stats = vol.get_statistics()
            print(f"[BraTS] Tumor volume: {stats.get('tumor_total_cm3', '?')} cm3")
            print(f"[BraTS] NCR: {stats.get('ncr_cm3','?')} cm3, "
                  f"ET(label {stats.get('et_label_used','?')}): {stats.get('et_cm3','?')} cm3, "
                  f"ED: {stats.get('ed_cm3','?')} cm3")
            return vol
        except Exception as e:
            print(f"[BraTS] Error loading NIfTI {patient_dir}: {e}")

    # --- Priority 2 fallback: create synthetic NIfTI sample ---
    print("[BraTS] No NIfTI patient data found. Trying synthetic sample...")
    try:
        import subprocess, sys
        script = Path(__file__).parent.parent / 'scripts' / 'download_brats.py'
        subprocess.run([sys.executable, str(script), '--sample'], check=True)
        retry_patients = sorted([
            d for d in DATA_DIR.rglob('*')
            if d.is_dir() and (d / 'seg.nii.gz').exists()
        ])
        if retry_patients:
            patient_dir = retry_patients[0]
            vol = BraTSVolume(patient_dir)
            print(f"[BraTS] Loaded synthetic patient: {vol.patient_id}")
            return vol
    except Exception as e:
        print(f"[BraTS] Synthetic NIfTI creation failed: {e}")

    # --- Priority 3: TCGA TIFF slices ---
    tcga_dir = DATA_DIR / 'brain_tumor_custom'
    tumor_dir = tcga_dir / 'Tumor'
    mask_dir = tcga_dir / 'Mask'
    if tumor_dir.exists() and mask_dir.exists():
        tumor_files = sorted(tumor_dir.glob('*.tif'))
        mask_files = sorted(mask_dir.glob('*_mask.tif'))

        # Match tumor files to mask files by patient stem
        def find_mask(tfile: Path) -> Optional[Path]:
            expected = mask_dir / (tfile.stem + '_mask.tif')
            if expected.exists():
                return expected
            # Fallback: partial match
            for mf in mask_files:
                if tfile.stem in mf.stem:
                    return mf
            return None

        if patient_id:
            tumor_files = [f for f in tumor_files if patient_id in f.stem] or tumor_files

        for tfile in tumor_files:
            mfile = find_mask(tfile)
            if mfile is None:
                continue
            try:
                print(f"[BraTS] Loading TCGA TIFF: {tfile.name}")
                vol = TCGASliceVolume(tfile, mfile)
                stats = vol.get_statistics()
                print(f"[BraTS] TCGA tumor pixels: {stats.get('tumor_pixels','?')} "
                      f"({stats.get('tumor_pct','?')}% of slice)")
                return vol
            except Exception as e:
                print(f"[BraTS] Error loading TCGA TIFF {tfile}: {e}")

    print("[BraTS] No data available from any source.")
    return None


def brats_volume_to_tumor_geometry(
    vol: Union[BraTSVolume, TCGASliceVolume],
    domain_size: float = 600.0,
    target_slice_axis: int = 2,
    max_cells: int = 500,
    cell_density_scale: float = 1.0,
    include_3d: bool = False
):
    """
    Convert a BraTSVolume or TCGASliceVolume to TumorGeometry.

    For BraTSVolume (NIfTI):
      Label 1 (NCR, necrotic) -> NECROTIC phase, STEM_CELL type
      Label 3 or 4 (ET, enhancing) -> VIABLE phase, DIFFERENTIATED/RESISTANT
      Label 2 (ED, edema) -> HYPOXIC phase, INVASIVE type

    For TCGASliceVolume (TIFF, binary mask):
      Uses MRI intensity to infer sub-regions (biologically sound in T1c):
        Dark (intensity < 0.2)   -> NECROTIC phase, STEM_CELL   (necrotic core)
        Bright (intensity > 0.6) -> VIABLE phase, mix DIFFERENTIATED/RESISTANT (enhancing)
        Mid (0.2 - 0.6)          -> HYPOXIC phase, INVASIVE     (infiltrating edge)

    Args:
        vol: loaded BraTSVolume or TCGASliceVolume
        domain_size: simulation domain in um
        target_slice_axis: 0=sagittal, 1=coronal, 2=axial (ignored for TCGA)
        max_cells: maximum cells to place (performance limit)
        cell_density_scale: multiplier on cell sampling density
        include_3d: if True, use 3D cell placement (NIfTI only)
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from tumor_environment import (
        TumorCell, TumorGeometry, VesselPoint, ImmuneCell,
        CellPhase, CellType, ImmuneCellType,
        create_simple_tumor_environment
    )

    # -------------------------------------------------------------------------
    # Handle TCGA TIFF (2D binary mask with intensity inference)
    # -------------------------------------------------------------------------
    if isinstance(vol, TCGASliceVolume):
        if vol.mask_img is None or not vol.mask_img.any():
            print("[BraTS] TCGA: no tumor in mask, falling back to synthetic geometry")
            return create_simple_tumor_environment(domain_size=domain_size)

        mask = vol.mask_img       # (H, W) uint8, 0 or 1
        mri = vol.tumor_img       # (H, W) float32, 0-1 normalized

        rows, cols = np.where(mask > 0)
        r_min, r_max = int(rows.min()), int(rows.max())
        c_min, c_max = int(cols.min()), int(cols.max())
        r_extent = r_max - r_min
        c_extent = c_max - c_min
        max_extent = max(r_extent, c_extent, 1)

        usable_domain = domain_size * 0.7
        vox_to_um = (usable_domain / max_extent) * cell_density_scale
        domain_center = domain_size / 2.0
        r_center = (r_min + r_max) / 2.0
        c_center = (c_min + c_max) / 2.0

        def voxel_to_sim_2d(r, c):
            x = (c - c_center) * vox_to_um + domain_center
            y = (r - r_center) * vox_to_um + domain_center
            return float(x), float(y)

        # Classify tumor pixels by MRI intensity
        tumor_coords = list(zip(rows.tolist(), cols.tolist()))
        dark_voxels = [(r, c) for r, c in tumor_coords if mri[r, c] < 0.2]
        bright_voxels = [(r, c) for r, c in tumor_coords if mri[r, c] > 0.6]
        mid_voxels = [(r, c) for r, c in tumor_coords
                      if 0.2 <= mri[r, c] <= 0.6]

        total_tv = len(tumor_coords)
        n_dark = max(1, int(max_cells * len(dark_voxels) / max(1, total_tv)))
        n_bright = max(1, int(max_cells * len(bright_voxels) / max(1, total_tv)))
        n_mid = max(1, int(max_cells * len(mid_voxels) / max(1, total_tv)))

        rng = np.random.default_rng(42)

        def sample_voxels(vl, n):
            if len(vl) <= n:
                return vl
            idx = rng.choice(len(vl), n, replace=False)
            return [vl[i] for i in idx]

        sampled_dark = sample_voxels(dark_voxels, n_dark)
        sampled_bright = sample_voxels(bright_voxels, n_bright)
        sampled_mid = sample_voxels(mid_voxels, n_mid)

        tumor_radius = (max_extent / 2) * vox_to_um
        geometry = TumorGeometry(
            center=(domain_center, domain_center, 0.0),
            tumor_radius=tumor_radius,
            necrotic_core_radius=tumor_radius * (len(dark_voxels) / max(1, total_tv)) * 1.5
        )

        cell_id = 0
        # Dark -> necrotic core / stem cells
        for r, c in sampled_dark:
            x, y = voxel_to_sim_2d(r, c)
            cell = TumorCell(
                cell_id=cell_id,
                position=(x, y, 0.0),
                radius=10.0,
                initial_phase=CellPhase.NECROTIC,
                cell_type=CellType.STEM_CELL
            )
            cell.is_alive = True
            geometry.tumor_cells.append(cell)
            cell_id += 1

        # Bright -> enhancing / viable (DIFFERENTIATED + RESISTANT mix)
        for r, c in sampled_bright:
            x, y = voxel_to_sim_2d(r, c)
            ctype = CellType.RESISTANT if rng.random() < 0.3 else CellType.DIFFERENTIATED
            cell = TumorCell(
                cell_id=cell_id,
                position=(x, y, 0.0),
                radius=10.0,
                initial_phase=CellPhase.VIABLE,
                cell_type=ctype
            )
            geometry.tumor_cells.append(cell)
            cell_id += 1

        # Mid -> infiltrating edge / hypoxic invasive
        for r, c in sampled_mid:
            x, y = voxel_to_sim_2d(r, c)
            cell = TumorCell(
                cell_id=cell_id,
                position=(x, y, 0.0),
                radius=10.0,
                initial_phase=CellPhase.HYPOXIC,
                cell_type=CellType.INVASIVE
            )
            geometry.tumor_cells.append(cell)
            cell_id += 1

        geometry._generate_peripheral_vasculature(dimensionality=2)
        geometry._generate_immune_cells(dimensionality=2)

        geometry.brats_metadata = {
            "patient_id": vol.patient_id,
            "source": "TCGA-BraTS2019",
            "format": "TIFF-2D",
            "tumor_stats": vol.get_statistics(),
            "vox_to_um": vox_to_um,
            "cells_dark_necrotic": len(sampled_dark),
            "cells_bright_enhancing": len(sampled_bright),
            "cells_mid_invasive": len(sampled_mid),
        }

        print(f"[BraTS] TCGA geometry: {len(geometry.tumor_cells)} cells, "
              f"{len(geometry.vessels)} vessels")
        print(f"[BraTS] Dark(NCR)={len(sampled_dark)}, "
              f"Bright(ET)={len(sampled_bright)}, "
              f"Mid(ED)={len(sampled_mid)}")
        return geometry

    # -------------------------------------------------------------------------
    # Handle BraTSVolume (NIfTI) - original logic + BraTS2024 label fix
    # -------------------------------------------------------------------------
    if vol.tumor_bbox is None:
        print("[BraTS] No tumor found in segmentation, falling back to synthetic geometry")
        return create_simple_tumor_environment(domain_size=domain_size)

    # Auto-detect ET label: BraTS 2024 uses 3, BraTS 2021 uses 4
    unique_labels = set(np.unique(vol.seg).tolist()) - {0}
    if 4 in unique_labels:
        ET_LABEL = 4   # BraTS 2021 convention
    elif 3 in unique_labels:
        ET_LABEL = 3   # BraTS 2024 convention
    else:
        ET_LABEL = max(unique_labels) if unique_labels else 1

    print(f"[BraTS] Auto-detected ET label: {ET_LABEL} (labels present: {unique_labels})")

    # Get 2D cross-section at tumor center (axial slice is most informative for GBM)
    seg_slice = vol.get_tumor_slice(axis=target_slice_axis)

    # Crop to tumor bounding box on this slice
    tumor_mask = seg_slice > 0
    if not tumor_mask.any():
        # Try adjacent slices
        for offset in range(1, 20):
            for sign in [1, -1]:
                seg_slice = vol.get_tumor_slice(axis=target_slice_axis, offset=sign * offset)
                if (seg_slice > 0).any():
                    break
            if (seg_slice > 0).any():
                break

    tumor_mask = seg_slice > 0
    if not tumor_mask.any():
        print("[BraTS] Tumor not visible in any axial slice, using synthetic")
        return create_simple_tumor_environment(domain_size=domain_size)

    # Bounding box of tumor on this slice
    rows, cols = np.where(tumor_mask)
    r_min, r_max = rows.min(), rows.max()
    c_min, c_max = cols.min(), cols.max()

    r_extent = r_max - r_min
    c_extent = c_max - c_min
    max_extent = max(r_extent, c_extent)

    # Scale: fit tumor into 70% of domain (leave margin for vessels)
    usable_domain = domain_size * 0.7
    vox_to_um = (usable_domain / max(1, max_extent)) * cell_density_scale

    domain_center = domain_size / 2.0
    r_center = (r_min + r_max) / 2.0
    c_center = (c_min + c_max) / 2.0

    def voxel_to_sim(r, c):
        """Convert voxel (row, col) to simulation (x, y) in um."""
        x = (c - c_center) * vox_to_um + domain_center
        y = (r - r_center) * vox_to_um + domain_center
        return float(x), float(y)

    # Sample cells from segmentation proportionally by label
    ncr_voxels = list(zip(*np.where(seg_slice == 1))) if (seg_slice == 1).any() else []
    et_voxels = list(zip(*np.where(seg_slice == ET_LABEL))) if (seg_slice == ET_LABEL).any() else []
    ed_voxels = list(zip(*np.where(seg_slice == 2))) if (seg_slice == 2).any() else []

    total_tumor_voxels = len(ncr_voxels) + len(et_voxels) + len(ed_voxels)
    if total_tumor_voxels == 0:
        return create_simple_tumor_environment(domain_size=domain_size)

    # Proportional sampling
    n_ncr = max(1, int(max_cells * len(ncr_voxels) / total_tumor_voxels))
    n_et = max(1, int(max_cells * len(et_voxels) / total_tumor_voxels))
    n_ed = max(1, int(max_cells * len(ed_voxels) / total_tumor_voxels))

    rng = np.random.default_rng(42)

    def sample_voxels(voxel_list, n):
        if len(voxel_list) <= n:
            return voxel_list
        idx = rng.choice(len(voxel_list), n, replace=False)
        return [voxel_list[i] for i in idx]

    sampled_ncr = sample_voxels(ncr_voxels, n_ncr)
    sampled_et = sample_voxels(et_voxels, n_et)
    sampled_ed = sample_voxels(ed_voxels, n_ed)

    # Build TumorGeometry
    tumor_radius = (max_extent / 2) * vox_to_um
    tumor_center_3d = (domain_center, domain_center, 0.0)

    geometry = TumorGeometry(
        center=tumor_center_3d,
        tumor_radius=tumor_radius,
        necrotic_core_radius=tumor_radius * (len(ncr_voxels) / max(1, total_tumor_voxels)) * 1.5
    )

    cell_id = 0

    # NCR (necrotic core) -> NECROTIC phase, STEM_CELL type
    for r, c in sampled_ncr:
        x, y = voxel_to_sim(r, c)
        cell = TumorCell(
            cell_id=cell_id,
            position=(x, y, 0.0),
            radius=10.0,
            initial_phase=CellPhase.NECROTIC,
            cell_type=CellType.STEM_CELL
        )
        cell.is_alive = True
        geometry.tumor_cells.append(cell)
        cell_id += 1

    # ET (enhancing tumor) -> VIABLE, mixed DIFFERENTIATED and RESISTANT
    for r, c in sampled_et:
        x, y = voxel_to_sim(r, c)
        # 30% resistant in enhancing region (survived initial treatment)
        cell_type = CellType.RESISTANT if rng.random() < 0.3 else CellType.DIFFERENTIATED
        cell = TumorCell(
            cell_id=cell_id,
            position=(x, y, 0.0),
            radius=10.0,
            initial_phase=CellPhase.VIABLE,
            cell_type=cell_type
        )
        geometry.tumor_cells.append(cell)
        cell_id += 1

    # ED (edema) -> HYPOXIC, INVASIVE type (infiltrating cells at margin)
    for r, c in sampled_ed:
        x, y = voxel_to_sim(r, c)
        cell = TumorCell(
            cell_id=cell_id,
            position=(x, y, 0.0),
            radius=10.0,
            initial_phase=CellPhase.HYPOXIC,
            cell_type=CellType.INVASIVE
        )
        geometry.tumor_cells.append(cell)
        cell_id += 1

    # Generate vasculature and immune cells
    geometry._generate_peripheral_vasculature(dimensionality=2)
    geometry._generate_immune_cells(dimensionality=2)

    # Store BraTS metadata on geometry object
    geometry.brats_metadata = {
        "patient_id": vol.patient_id,
        "source": "brats",
        "et_label": ET_LABEL,
        "slice_axis": target_slice_axis,
        "tumor_stats": vol.get_statistics(),
        "vox_to_um": vox_to_um,
        "cells_from_ncr": len(sampled_ncr),
        "cells_from_et": len(sampled_et),
        "cells_from_ed": len(sampled_ed),
    }

    print(f"[BraTS] Geometry created: {len(geometry.tumor_cells)} cells, "
          f"{len(geometry.vessels)} vessels")
    print(f"[BraTS] NCR={len(sampled_ncr)}, ET(label {ET_LABEL})={len(sampled_et)}, "
          f"ED={len(sampled_ed)}")
    print(f"[BraTS] Tumor radius: {tumor_radius:.1f}um, voxel scale: {vox_to_um:.2f}um/voxel")

    return geometry
