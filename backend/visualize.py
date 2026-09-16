"""Visualization utilities — pheromone heatmaps and kill-rate charts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Use non-interactive Matplotlib backend so this module is safe to import
# in headless environments (CI, servers, tests).
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def render_pheromone_heatmap(
    biofvm: Any,
    output_path: str | Path,
    substrate_name: str = "trail",
    title: Optional[str] = None,
) -> Path:
    """Save a PNG heatmap of a pheromone field at the current timestep.

    Parameters
    ----------
    biofvm:
        A ``Microenvironment`` instance (from ``backend.biofvm``).
    output_path:
        Destination file path (e.g. ``"heatmap.png"``).
    substrate_name:
        Name of the substrate to visualise (default: ``"trail_pheromone"``).
    title:
        Optional plot title.  Defaults to the substrate name.

    Returns
    -------
    Path
        Resolved path to the saved PNG.
    """
    substrate = biofvm.get_substrate(substrate_name)
    if substrate is None:
        raise ValueError(f"Substrate '{substrate_name}' not found in microenvironment.")

    concentrations = np.array(substrate.concentration)

    # Handle 2-D or 3-D fields (take the first z-slice for 3-D).
    if concentrations.ndim == 3:
        concentrations = concentrations[:, :, 0]
    elif concentrations.ndim != 2:
        raise ValueError(f"Unsupported concentration array shape: {concentrations.shape}")

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(
        concentrations.T,
        origin="lower",
        aspect="equal",
        cmap="hot",
        interpolation="nearest",
    )
    fig.colorbar(im, ax=ax, label="Concentration")
    ax.set_xlabel("x (voxels)")
    ax.set_ylabel("y (voxels)")
    ax.set_title(title or substrate_name.replace("_", " ").title())

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out.resolve()


def render_kill_rate_chart(
    results_list: List[Dict[str, Any]],
    output_path: str | Path,
    title: str = "Kill Rate by Run",
    label_key: str = "run_id",
    value_key: str = "kill_rate",
) -> Path:
    """Save a bar chart of kill rates across multiple simulation runs.

    Parameters
    ----------
    results_list:
        List of result dicts, each containing at least ``run_id`` (or
        ``label_key``) and ``kill_rate`` (or ``value_key``) fields.
    output_path:
        Destination file path.
    title:
        Chart title.
    label_key:
        Key used as the x-axis label.
    value_key:
        Key containing the numeric kill-rate value.

    Returns
    -------
    Path
        Resolved path to the saved PNG.
    """
    if not results_list:
        raise ValueError("results_list must not be empty.")

    labels = [str(r.get(label_key, i)) for i, r in enumerate(results_list)]
    values = [float(r[value_key]) for r in results_list]

    fig, ax = plt.subplots(figsize=(max(4, len(labels)), 4))
    bars = ax.bar(labels, values, color="steelblue", edgecolor="white")
    ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 1.0)
    ax.set_xlabel(label_key.replace("_", " ").title())
    ax.set_ylabel(value_key.replace("_", " ").title())
    ax.set_title(title)
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return out.resolve()
