"""Test helper: fake a TumorIntel record that proves an artifact's exact public values.

Since the W1 hardening, ``verify_artifact`` only reports ``verified_onchain`` when the chain's
record is verified *and* its ``publicValuesHash`` is keccak256 of the artifact's own encoded
public values. A bare ``{"verified": True}`` mock no longer suffices, by design.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from chain.onchain_record import public_values_hash_from_encoded  # noqa: E402
from chain.proof_spec import build_public_values_payload, encode_public_values_payload  # noqa: E402


def proven_onchain(artifact: dict, nanobot_count: int = 0, tumor_radius: int = 0, steps: int = 0):
    """Return a ``check_onchain_verification`` stand-in whose record proves ``artifact``.

    Artifacts without encoded public values get them, derived from the artifact's own
    ``config_hash`` and ``metrics.kill_rate`` (percentage points, scaled to basis points).
    """
    onchain = artifact.setdefault("onchain", {})
    if not onchain.get("public_values"):
        kill_rate_bps = int(float(artifact["metrics"]["kill_rate"]) * 100)
        payload = build_public_values_payload(artifact["config_hash"], kill_rate_bps, nanobot_count, tumor_radius,
                                              steps)
        onchain["public_values"] = encode_public_values_payload(payload)
    pv_hash = public_values_hash_from_encoded(onchain["public_values"])
    return lambda config_hash: {"ok": True, "verified": True, "raw": True,
                                "record": {"verified": True, "public_values_hash": pv_hash}}
