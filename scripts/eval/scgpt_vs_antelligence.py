#!/usr/bin/env python3
"""scgpt_vs_antelligence — illustrative head-to-head comparison stub.

BRIEF-327, Step 2. Single combinatorial-perturbation comparison between
zero-shot scGPT and a simplified antelligence simulation, designed to
*surface the metric mismatch* — not declare a winner. The comparison is
honest by construction: scGPT reports DEG-F1 on transcriptome delta, the
simulation reports a mechanistic readout (kill-rate / growth-rate delta)
on a downstream phenotype the perturbation should affect.

Default benchmark: Norman 2019 (single + double gene perturbations).
Other supported: Replogle 2022, Adamson 2016 — all standard in scGPT
papers.

This stub is runnable end-to-end. If the scGPT checkpoint or the dataset
are not staged locally, it falls back to a clear "not staged" message
listing exactly what is missing and where it expects each artefact —
keeping the file from rotting.

Heavy weights live on /Volumes/WD_BLACK to keep the project repo light:
- /Volumes/WD_BLACK/scgpt/checkpoints/<release>/  — HF snapshot
- /Volumes/WD_BLACK/scgpt/datasets/norman2019.h5ad — perturbation atlas

Usage:
    python3 scripts/eval/scgpt_vs_antelligence.py --dataset norman2019
    python3 scripts/eval/scgpt_vs_antelligence.py --dry-run
"""
import argparse
import json
import os
import sys
from pathlib import Path

WD_BLACK = Path("/Volumes/WD_BLACK")
SCGPT_CHECKPOINT_DIR = WD_BLACK / "scgpt" / "checkpoints"
SCGPT_DATASETS_DIR = WD_BLACK / "scgpt" / "datasets"

DATASETS = {
    "norman2019":   {"file": "norman2019.h5ad",   "expected_perturbations": "single + double gene KO"},
    "replogle2022": {"file": "replogle2022.h5ad", "expected_perturbations": "perturb-seq, K562"},
    "adamson2016":  {"file": "adamson2016.h5ad",  "expected_perturbations": "UPR perturbations"},
}


def check_staging(dataset_key: str) -> dict:
    info = DATASETS[dataset_key]
    dataset_path = SCGPT_DATASETS_DIR / info["file"]
    checkpoint_path = SCGPT_CHECKPOINT_DIR
    return {
        "dataset_key": dataset_key,
        "dataset_path": str(dataset_path),
        "dataset_present": dataset_path.exists(),
        "checkpoint_dir": str(checkpoint_path),
        "checkpoint_present": checkpoint_path.exists() and any(checkpoint_path.iterdir()) if checkpoint_path.exists() else False,
        "expected_perturbations": info["expected_perturbations"],
    }


def run_scgpt_zeroshot(dataset_path: Path) -> dict:
    """Zero-shot perturbation inference via the scGPT HF checkpoint.

    Pseudocode — fill in once the HF release is pinned and on WD_BLACK.
    Returns a dict with deg_f1, mse, num_perturbations.
    """
    raise NotImplementedError(
        "scGPT zero-shot inference not wired yet — pin the HF checkpoint "
        "release on WD_BLACK first, then implement load + perturb_predict."
    )


def run_antelligence_mechanistic(dataset_path: Path) -> dict:
    """Run a simplified antelligence simulation that produces a downstream
    phenotype (kill-rate or growth-rate delta) for the same perturbations.

    The mapping perturbation→agent-parameter is dataset-specific; for
    Norman 2019 the default is to map gene-KO to a proliferation-rate
    multiplier and re-run the nanobot-tumour scenario with that parameter
    set, then report the mean kill-rate delta vs unperturbed control.
    """
    raise NotImplementedError(
        "Antelligence mechanistic readout not wired yet — Norman 2019 "
        "perturbation→agent-parameter mapping needs to be defined first; "
        "see docs/positioning/2026-04-virtual-cell-foundation-models.md."
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS), default="norman2019")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print staging status only; never load weights or simulate.",
    )
    args = parser.parse_args(argv)

    staging = check_staging(args.dataset)
    print(json.dumps({"staging": staging}, indent=2))

    if args.dry_run:
        return 0

    if not staging["dataset_present"] or not staging["checkpoint_present"]:
        print(
            "[scgpt_vs_antelligence] Required artefacts missing. "
            "Stage them under WD_BLACK and re-run, or pass --dry-run.",
            file=sys.stderr,
        )
        return 2

    scgpt_result = run_scgpt_zeroshot(Path(staging["dataset_path"]))
    antelligence_result = run_antelligence_mechanistic(Path(staging["dataset_path"]))

    out = {
        "dataset": args.dataset,
        "scgpt": scgpt_result,
        "antelligence": antelligence_result,
        "comment": (
            "These are different metrics for different problems. The point "
            "is to surface the metric mismatch — see "
            "docs/positioning/2026-04-virtual-cell-foundation-models.md."
        ),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
