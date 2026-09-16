"""Deterministic fixture-only chain ingestion buffer.

This module intentionally does not read RPC, clocks, or process-local state. It
only canonicalizes already-collected chain events so replay/provenance code can
hash the exact same block-height-indexed view across process runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

DETERMINISM_RISK_NOTE = (
    "Sepolia RPC must be checked for identical-height query determinism before live use; "
    "if logs, receipts, or timestamps vary for the same height range, use a local archive node "
    "or snapshot fixture instead of treating a live RPC read as replayable."
)


@dataclass(frozen=True)
class ChainBufferEvent:
    """One deterministic event in the canonical chain-reader buffer."""

    chain_id: int
    source: str
    block_height: int
    tx_index: int
    log_index: int
    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ChainBufferEvent":
        return cls(
            chain_id=int(value["chain_id"]),
            source=str(value["source"]),
            block_height=int(value["block_height"]),
            tx_index=int(value["tx_index"]),
            log_index=int(value["log_index"]),
            payload=dict(value.get("payload") or {}),
        )

    def sort_key(self) -> tuple[int, str, int, int, int, str]:
        payload_key = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        return (self.chain_id, self.source, self.block_height, self.tx_index, self.log_index, payload_key)

    def to_canonical_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeterministicChainBuffer:
    """Block-height-indexed deterministic chain event buffer.

    Ordering is derived only from deterministic chain identifiers:
    ``chain_id``, ``source``, ``block_height``, ``tx_index``, and ``log_index``.
    Arrival order, wall-clock time, and local process state are not represented
    in the canonical bytes or digest.
    """

    def __init__(self, events: Iterable[ChainBufferEvent] = ()):  # noqa: B006 - immutable tuple default equivalent
        # Only immutable snapshot fixtures are admitted to the replayable buffer.
        self._events = tuple(sorted(
            [e for e in events if e.source == "snapshot"],
            key=lambda event: event.sort_key()
        ))

    @classmethod
    def from_events(cls, events: Iterable[dict[str, Any] | ChainBufferEvent]) -> "DeterministicChainBuffer":
        normalized = [event if isinstance(event, ChainBufferEvent) else ChainBufferEvent.from_mapping(event) for event in events]
        return cls(normalized)

    @property
    def events(self) -> tuple[ChainBufferEvent, ...]:
        return self._events

    def canonical_dict(self) -> dict[str, Any]:
        return {"events": [event.to_canonical_dict() for event in self._events]}

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def trust_tier_label(*, event_block_height: int | None, observer_height: int | None, finality_height: int | None) -> str:
    """Return inert trust-tier copy; stale/missing observation degrades to T1."""

    if event_block_height is not None and finality_height is not None and finality_height >= event_block_height:
        return "T3 finality"
    if event_block_height is not None and observer_height is not None and observer_height >= event_block_height:
        return f"T2 observer@{observer_height}"
    return "T1 local"


def pheromone_provenance_checksum(sim_seed_or_run_id: str | int, chain_buffer_digest: str, provenance_id: str) -> str:
    """SHA-256 label binding sim identity, chain buffer digest, and provenance id."""

    payload = {
        "chain_buffer_digest": str(chain_buffer_digest),
        "provenance_id": str(provenance_id),
        "sim_seed_or_run_id": str(sim_seed_or_run_id),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
