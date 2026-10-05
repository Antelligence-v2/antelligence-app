"""Per-tick spatial frames for visualization.

Frames are a *view* of a run, not evidence: they are recorded beside the
hash-chained event log and never enter it, so recording them cannot change a
trace hash. A world opts in by implementing ``scene()`` (static layout) and
``snapshot()`` (dynamic state); both must be read-only (no RNG draws, no
mutation) so replay stays exact.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, Iterable, List

import numpy as np

from antelligence.kernel.signal import Signal


def encode_field(values: np.ndarray, stride: int = 1) -> Dict[str, Any]:
    """Quantize a 2D scalar field to uint8 (0..255 of its own max) as base64.

    Keeps frames small (a 31x31 field is ~1.3 kB); ``max`` restores scale.
    """
    grid = np.asarray(values, dtype=np.float64)
    if grid.ndim == 3:
        grid = grid[:, :, 0]
    grid = grid[::stride, ::stride]
    top = float(np.nanmax(grid)) if grid.size else 0.0
    if not np.isfinite(top) or top <= 0.0:
        quantized = np.zeros(grid.shape, dtype=np.uint8)
        top = 0.0
    else:
        quantized = np.clip(np.rint(np.nan_to_num(grid) / top * 255.0), 0, 255).astype(np.uint8)
    # Row-major over (x, y): index = x * ny + y.
    return {"max": round(top, 6), "b64": base64.b64encode(quantized.tobytes()).decode("ascii")}


def signal_marks(signals: Iterable[Signal], tick: int) -> List[List[Any]]:
    """Spatial signals as compact rows: [x, y, kind, sender, ticks_left]."""
    marks = []
    for s in signals:
        if s.pos is None or len(s.pos) < 2:
            continue
        marks.append([round(float(s.pos[0]), 2), round(float(s.pos[1]), 2), s.kind, s.sender, s.expires_at - tick])
    return marks
