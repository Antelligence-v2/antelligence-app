"""Engine fingerprint: a hash of every source file that can change a result.

Cached experiments are keyed by (request, fingerprint), so any change to the
engine, a world, or the legacy physics/paper modules the worlds run on gives a
new cache key automatically; nobody has to remember to bump a version.
"""

from __future__ import annotations

import functools
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DEPENDENCIES = (
    "backend/biofvm.py",
    "backend/tumor_environment.py",
    "backend/swarm_core.py",
    "backend/source_calculation.py",
    "backend/research_hive_tasks.py",
    "backend/research_hive_verifier.py",
    "backend/research_hive_contracts.py",
)


@functools.lru_cache(maxsize=1)
def engine_fingerprint() -> str:
    digest = hashlib.sha256()
    files = sorted((ROOT / "antelligence").rglob("*.py")) + [ROOT / p for p in BACKEND_DEPENDENCIES]
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()[:16]
