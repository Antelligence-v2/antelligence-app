"""Canonical JSON and content hashing shared by every kernel record."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


class CanonicalError(ValueError):
    """A value cannot be represented as canonical JSON."""


def _check(value: Any, path: str) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalError(f"{path}: non-finite float")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalError(f"{path}: object keys must be strings")
            _check(item, f"{path}.{key}")
        return
    raise CanonicalError(f"{path}: unsupported type {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, finite numbers only."""
    _check(value, "$")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def content_hash(value: Any) -> str:
    """sha256 hex digest of the canonical form of ``value``."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def plain(value: Any) -> Any:
    """Return a detached, JSON-plain deep copy (tuples become lists)."""
    return json.loads(canonical_json(value))
