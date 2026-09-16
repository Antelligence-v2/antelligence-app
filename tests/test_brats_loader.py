"""
Tests for brats_loader.py - covers BraTS 2024 NIfTI, TCGA TIFF, and label detection.
"""
import pytest
import numpy as np
from pathlib import Path

# Paths to real data
DATA_DIR = Path(__file__).parent.parent / 'data' / 'brats'
GLI_DIR = DATA_DIR / 'BraTS2024-GLI'
TCGA_DIR = DATA_DIR / 'brain_tumor_custom'

HAS_BRATS2024 = GLI_DIR.exists() and any(GLI_DIR.iterdir())
HAS_TCGA = (TCGA_DIR / 'Tumor').exists() and any((TCGA_DIR / 'Tumor').glob('*.tif'))


# ---------------------------------------------------------------------------
# Original tests - updated so they work with real data (no synthetic required)
# ---------------------------------------------------------------------------

def test_load_patient_returns_volume():
    """load_brats_patient() must return a non-None volume object."""
    from backend.brats_loader import load_brats_patient
    vol = load_brats_patient()
    assert vol is not None


def test_tumor_statistics():
    """get_statistics() must include standard keys and a positive tumor volume."""
    from backend.brats_loader import load_brats_patient
    vol = load_brats_patient()
    stats = vol.get_statistics()
    assert stats is not None
    assert len(stats) > 0
    # Key present in both BraTSVolume and TCGASliceVolume
    assert 'patient_id' in stats
    # BraTSVolume-specific keys (real NIfTI data should be available)
    from backend.brats_loader import BraTSVolume
    if isinstance(vol, BraTSVolume):
        assert 'ncr_cm3' in stats
        assert 'et_cm3' in stats
        assert 'ed_cm3' in stats
        assert stats['tumor_total_cm3'] > 0


def test_brats_to_geometry():
    """brats_volume_to_tumor_geometry() must produce cells within domain bounds."""
    from backend.brats_loader import load_brats_patient, brats_volume_to_tumor_geometry
    vol = load_brats_patient()
    geom = brats_volume_to_tumor_geometry(vol, domain_size=600.0, max_cells=100)
    assert geom is not None
    assert len(geom.tumor_cells) > 0
    assert len(geom.vessels) > 0
    for cell in geom.tumor_cells:
        assert 0 <= cell.position[0] <= 600.0
        assert 0 <= cell.position[1] <= 600.0


def test_cell_type_mapping():
    """Geometry from real data must include multiple cell types."""
    from backend.brats_loader import load_brats_patient, brats_volume_to_tumor_geometry
    from backend.tumor_environment import CellType, CellPhase
    vol = load_brats_patient()
    geom = brats_volume_to_tumor_geometry(vol, domain_size=600.0, max_cells=200)
    cell_types = {c.cell_type for c in geom.tumor_cells}
    assert len(cell_types) > 1


def test_create_brats_tumor_geometry_fallback():
    """create_brats_tumor_geometry() helper must not raise NotImplementedError."""
    from backend.tumor_environment import create_brats_tumor_geometry
    geom = create_brats_tumor_geometry(domain_size=600.0, max_cells=50)
    assert geom is not None
    assert len(geom.tumor_cells) > 0


# ---------------------------------------------------------------------------
# New test: BraTS 2024 NIfTI real data
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_BRATS2024, reason="BraTS2024-GLI data not present")
def test_real_brats2024_nifti():
    """Loads from BraTS2024-GLI, verifies it is NOT synthetic data."""
    from backend.brats_loader import load_brats_patient, brats_volume_to_tumor_geometry, BraTSVolume
    from collections import Counter

    vol = load_brats_patient()
    assert vol is not None, "Expected a BraTSVolume from BraTS2024-GLI"
    assert isinstance(vol, BraTSVolume), f"Expected BraTSVolume, got {type(vol)}"

    # Confirm it is a real BraTS2024-GLI patient (not synthetic)
    assert 'synthetic' not in vol.patient_id.lower(), \
        f"Expected real data, got synthetic patient: {vol.patient_id}"
    assert 'BraTS' in vol.patient_id or 'GLI' in vol.patient_id, \
        f"Expected BraTS-GLI patient ID, got: {vol.patient_id}"

    # Confirm statistics look reasonable for a real GBM scan
    stats = vol.get_statistics()
    assert stats['tumor_total_cm3'] > 0.0, "Expected non-zero tumor volume"
    assert stats['format'] == 'NIfTI-3D'
    assert stats['source'] == 'BraTS-NIfTI'

    # Confirm geometry creation works end-to-end
    geom = brats_volume_to_tumor_geometry(vol, domain_size=600.0, max_cells=300)
    assert geom is not None
    assert len(geom.tumor_cells) > 0, "Expected tumor cells in geometry"

    types = Counter(c.cell_type.value for c in geom.tumor_cells)
    phases = Counter(c.phase.value for c in geom.tumor_cells)
    print(f"\n[test] Patient: {vol.patient_id}")
    print(f"[test] Tumor: {stats['tumor_total_cm3']:.2f} cm3")
    print(f"[test] Cells: {len(geom.tumor_cells)}, types: {dict(types)}, phases: {dict(phases)}")


# ---------------------------------------------------------------------------
# New test: TCGA 2019 TIFF slices
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_TCGA, reason="TCGA TIFF data not present")
def test_tcga_tiff_loader():
    """Loads a TCGA TIFF slice, checks statistics, and creates a geometry."""
    from backend.brats_loader import TCGASliceVolume, brats_volume_to_tumor_geometry
    from collections import Counter

    tumor_files = sorted((TCGA_DIR / 'Tumor').glob('*.tif'))
    mask_files = sorted((TCGA_DIR / 'Mask').glob('*_mask.tif'))
    assert tumor_files, "Expected TIFF tumor files"
    assert mask_files, "Expected TIFF mask files"

    # Find a matching pair
    tfile = tumor_files[0]
    mfile = TCGA_DIR / 'Mask' / (tfile.stem + '_mask.tif')
    assert mfile.exists(), f"Expected mask file {mfile}"

    vol = TCGASliceVolume(tfile, mfile)
    assert vol.tumor_img is not None, "Expected tumor image"
    assert vol.mask_img is not None, "Expected mask image"
    assert vol.tumor_img.shape == (256, 256), \
        f"Expected (256,256) grayscale, got {vol.tumor_img.shape}"
    assert vol.mask_img.shape == (256, 256)
    assert vol.mask_img.max() == 1, "Expected binary mask with values 0/1"

    stats = vol.get_statistics()
    assert stats['source'] == 'TCGA-BraTS2019'
    assert stats['format'] == 'TIFF-2D'
    assert stats['tumor_pixels'] > 0, "Expected non-zero tumor pixels"
    assert stats['tumor_center_px'] is not None
    assert stats['tumor_bbox'] is not None
    assert 'TCGA' in stats['patient_id']

    # Geometry creation
    geom = brats_volume_to_tumor_geometry(vol, domain_size=600.0, max_cells=200)
    assert geom is not None
    assert len(geom.tumor_cells) > 0, "Expected tumor cells from TCGA TIFF"
    assert len(geom.vessels) > 0

    types = Counter(c.cell_type.value for c in geom.tumor_cells)
    phases = Counter(c.phase.value for c in geom.tumor_cells)
    print(f"\n[test] TCGA patient: {vol.patient_id}")
    print(f"[test] Tumor pixels: {stats['tumor_pixels']} ({stats['tumor_pct']}%)")
    print(f"[test] Cells: {len(geom.tumor_cells)}, types: {dict(types)}, phases: {dict(phases)}")

    # Verify brats_metadata is populated
    assert hasattr(geom, 'brats_metadata')
    assert geom.brats_metadata['source'] == 'TCGA-BraTS2019'

    # Cells must be within domain
    for cell in geom.tumor_cells:
        assert 0 <= cell.position[0] <= 600.0
        assert 0 <= cell.position[1] <= 600.0


# ---------------------------------------------------------------------------
# New test: BraTS 2024 label 3 detection
# ---------------------------------------------------------------------------

def test_brats2024_label_detection():
    """
    Verifies that the auto-detect logic identifies label 3 as ET when
    label 4 is absent (BraTS 2024 convention), and label 4 when present
    (BraTS 2021 convention).
    """
    from backend.brats_loader import brats_volume_to_tumor_geometry, BraTSVolume
    from backend.tumor_environment import CellPhase, CellType
    from collections import Counter
    import types as pytypes

    # --- Build a minimal mock BraTSVolume with ONLY label 3 (BraTS2024 style) ---
    mock_vol = pytypes.SimpleNamespace()
    mock_vol.patient_id = 'mock-brats2024-label3'

    # Create a small 3D segmentation: 20x20x20, with a block of label 3
    seg = np.zeros((20, 20, 20), dtype=np.uint8)
    seg[8:12, 8:12, 8:12] = 3    # ET label (BraTS2024)
    seg[5:8,  5:8,  5:8]  = 2    # ED label
    mock_vol.seg = seg
    mock_vol.t1ce = None
    mock_vol.affine = np.eye(4)
    mock_vol.voxel_spacing = (1.0, 1.0, 1.0)
    mock_vol.shape = seg.shape

    tumor_mask = seg > 0
    coords = np.where(tumor_mask)
    mock_vol.tumor_bbox = (
        int(coords[0].min()), int(coords[0].max()),
        int(coords[1].min()), int(coords[1].max()),
        int(coords[2].min()), int(coords[2].max()),
    )
    mock_vol.tumor_center = (
        int((coords[0].min() + coords[0].max()) / 2),
        int((coords[1].min() + coords[1].max()) / 2),
        int((coords[2].min() + coords[2].max()) / 2),
    )

    # Patch get_tumor_slice and get_statistics onto mock
    def _get_tumor_slice(axis=2, offset=0):
        z = mock_vol.tumor_center[axis] + offset
        z = max(0, min(z, mock_vol.shape[axis] - 1))
        if axis == 0: return mock_vol.seg[z, :, :]
        if axis == 1: return mock_vol.seg[:, z, :]
        return mock_vol.seg[:, :, z]

    mock_vol.get_tumor_slice = _get_tumor_slice
    mock_vol.get_statistics = lambda: {'patient_id': mock_vol.patient_id}

    # Convert to geometry - should detect ET_LABEL = 3
    geom = brats_volume_to_tumor_geometry(mock_vol, domain_size=200.0, max_cells=50)
    assert geom is not None
    assert len(geom.tumor_cells) > 0

    # ET (label 3) -> VIABLE phase
    phases = Counter(c.phase.value for c in geom.tumor_cells)
    assert 'viable' in phases, \
        f"Expected VIABLE cells from label-3 ET region, got phases: {dict(phases)}"

    # Verify metadata records ET_LABEL = 3
    assert hasattr(geom, 'brats_metadata')
    assert geom.brats_metadata['et_label'] == 3, \
        f"Expected et_label=3, got {geom.brats_metadata['et_label']}"

    # --- Also verify label 4 is still preferred when both 3 and 4 exist ---
    # Place all labels at the SAME z-range so the center axial slice sees all of them
    seg2 = np.zeros((20, 20, 20), dtype=np.uint8)
    seg2[8:12, 8:12, 8:16] = 4   # ET label (BraTS2021), z=8..15
    seg2[4:8,  4:8,  8:16] = 3   # Another region, same z range
    seg2[1:4,  1:4,  8:16] = 2   # ED, same z range
    mock_vol.seg = seg2

    tumor_mask2 = seg2 > 0
    coords2 = np.where(tumor_mask2)
    mock_vol.tumor_bbox = (
        int(coords2[0].min()), int(coords2[0].max()),
        int(coords2[1].min()), int(coords2[1].max()),
        int(coords2[2].min()), int(coords2[2].max()),
    )
    mock_vol.tumor_center = (
        int((coords2[0].min() + coords2[0].max()) / 2),
        int((coords2[1].min() + coords2[1].max()) / 2),
        int((coords2[2].min() + coords2[2].max()) / 2),
    )
    mock_vol.shape = seg2.shape

    geom2 = brats_volume_to_tumor_geometry(mock_vol, domain_size=200.0, max_cells=50)
    assert hasattr(geom2, 'brats_metadata'), \
        "Expected brats_metadata on geometry (not synthetic fallback)"
    assert geom2.brats_metadata['et_label'] == 4, \
        f"Expected et_label=4 when label 4 is present, got {geom2.brats_metadata['et_label']}"

    print("\n[test] BraTS2024 label detection: PASSED")
    print(f"[test] Label 3 only -> et_label=3, viable cells={phases.get('viable', 0)}")
    print(f"[test] Labels 3+4   -> et_label=4 (BraTS2021 wins)")
