# Antelligence Data Directory

Medical imaging data is NOT committed to git (too large, patient data).
Download using the provided scripts.

## Available Datasets

### BraTS 2024 GLI (Glioblastoma) — RECOMMENDED
Real NIfTI patient volumes with 3-label segmentation (NCR/ET/ED).
6 patients pre-downloaded. 1000 total available.

Download more:
```bash
python scripts/download_brats.py --brats2024 --n_patients 20
```

Or manually via HuggingFace (CC BY-NC-SA 4.0):
https://huggingface.co/datasets/Spirit-26/BraTS-2024-Complete

Place in: data/brats/BraTS2024-GLI/<patient_id>/

### TCGA BraTS 2019 (TCGA-GBM)
51 real 2D MRI slices with binary tumor masks (TIFF format).
From The Cancer Genome Atlas — clinical GBM cases.

Download via Kaggle:
```bash
cd antelligence-app
.venv/bin/kaggle datasets download -d aryanfelix/brats-2019-traintestvalid -p data/brats/ --unzip
```

Place in: data/brats/brain_tumor_custom/

### Synthetic Sample (no download needed)
Auto-generated for testing when no real data is present.
Created by: python scripts/download_brats.py --sample

## Data Priority

The loader checks in this order:
1. BraTS2024-GLI NIfTI (richest — 3 sub-region labels)
2. TCGA 2019 TIFF slices (binary masks, uses MRI intensity for sub-regions)
3. Synthetic sample (fallback for testing)

## Formats Supported

| Format | Extension | Labels | Source |
|--------|-----------|--------|--------|
| NIfTI  | .nii.gz   | 0=bg, 1=NCR, 2=ED, 3/4=ET | BraTS 2024/2021 |
| TIFF   | .tif      | 0=bg, 255=tumor | TCGA BraTS 2019 |

## Citation

If using BraTS 2024 data, cite:
> Data used in this publication were obtained from the BraTS 2024 Challenge.
> See CITATIONS.bib in the dataset directory.

If using TCGA data, cite:
> The Cancer Genome Atlas Research Network. (2008). Comprehensive genomic
> characterization defines human glioblastoma genes and core pathways.
> Nature, 455(7216), 1061-1068.
