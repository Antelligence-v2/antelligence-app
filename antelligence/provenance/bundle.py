"""Run bundles: the portable provenance record of one engine run.

A bundle binds *what was asked* (the RunSpec and config hash) to *what
happened* (the event-log trace hash and final metrics). Anyone holding the
bundle and this code can rebuild the run from the spec and check that the
event log reproduces the same trace hash (:func:`replay`).

Trust labels are deliberately modest and match the project's tiers:
``trust_tier = "local_replay"``, ``proof_ok = False``, ``onchain_ok = False``.
A bundle is replayable provenance, not a cryptographic proof; nothing here
claims ``verified_onchain``. For tumor runs the five public values used by
TumorIntel are included so an operator can stage a proof/submission with the
existing ``backend.chain`` tooling.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from antelligence.kernel.canonical import content_hash, plain
from antelligence.kernel.scheduler import RunResult

SCHEMA = "antelligence.run-bundle/v1"
TRUST_TIER = "local_replay"


def _tumor_public_values(result: RunResult, params: Mapping[str, Any], world: Mapping[str, Any]) -> Dict[str, Any]:
    kill_rate = float(result.metrics.get("kill_rate", 0.0))
    return {
        "config_hash": result.config_hash,
        "kill_rate_bps": int(round(kill_rate * 10_000)),
        "nanobot_count": int(world.get("n_nanobots", params.get("n_nanobots", 0))),
        "tumor_radius": int(round(float(world.get("tumor_radius", 0)))),
        "steps": int(result.ticks),
    }


def build_bundle(result: RunResult, spec: Mapping[str, Any], *, world_description: Optional[Mapping[str, Any]] = None,
                 extra: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "schema": SCHEMA,
        "spec": plain(dict(spec)),
        "run_id": result.run_id,
        "arm": result.arm,
        "scope": result.scope,
        "config_hash": result.config_hash,
        "trace_hash": result.trace_hash,
        "event_count": result.event_count,
        "ticks": result.ticks,
        "stopped_reason": result.stopped_reason,
        "metrics": plain(result.metrics),
        "counters": {
            "policy_failures": result.policy_failures,
            "signals_deposited": result.signals_deposited,
            "signals_rejected": result.signals_rejected,
            **plain(result.extra),
        },
        "trust": {"trust_tier": TRUST_TIER, "proof_ok": False, "onchain_ok": False,
                  "note": "Hash-chained event log + deterministic replay. Not a cryptographic proof."},
    }
    if spec.get("world") == "tumor":
        body["public_values"] = _tumor_public_values(result, spec.get("params", {}), world_description or {})
    if extra:
        body["extra"] = plain(dict(extra))
    return {**body, "bundle_hash": content_hash(body)}


def verify_bundle_integrity(bundle: Mapping[str, Any]) -> bool:
    body = {k: v for k, v in bundle.items() if k != "bundle_hash"}
    return content_hash(body) == bundle.get("bundle_hash")


# Every recorded field a replay must reproduce, beyond the trace/config hashes.
RESULT_FIELDS = ("run_id", "arm", "scope", "event_count", "ticks", "stopped_reason", "metrics", "counters",
                 "public_values")


def replay(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild the run from its spec and require it to reproduce the whole bundle.

    Checks the trace and config hashes *and* every recorded result field
    (metrics, counters, ticks, event count, public values, verdict), so a bundle
    whose results were edited and re-hashed is rejected.
    """
    from antelligence.experiments.registry import RunSpec, world
    from antelligence.kernel.verifier import classify_episode

    if not verify_bundle_integrity(bundle):
        return {"replay_ok": False, "reason": "bundle_hash_mismatch"}
    try:
        spec = RunSpec(**bundle["spec"])
        spec_world = world(spec.world)
        scheduler = spec_world.build(spec, run_id=bundle["run_id"])
    except (KeyError, TypeError, ValueError) as exc:
        return {"replay_ok": False, "reason": "spec_unresolvable", "detail": str(exc)[:200]}
    result = scheduler.run()
    rebuilt = build_bundle(result, spec.to_dict(), world_description=scheduler.world.describe())
    base = {"replayed_trace_hash": result.trace_hash, "expected_trace_hash": bundle.get("trace_hash"),
            "event_count": result.event_count}
    if result.trace_hash != bundle.get("trace_hash") or result.config_hash != bundle.get("config_hash"):
        return {"replay_ok": False, "reason": "trace_mismatch", **base}
    mismatched = [field for field in RESULT_FIELDS if bundle.get(field) != rebuilt.get(field)]
    recorded_verdict = (bundle.get("extra") or {}).get("verdict")
    if recorded_verdict is not None:
        goal = bool(result.metrics.get(spec_world.success_metric))
        if classify_episode(scheduler.log, goal_reached=goal).to_dict() != recorded_verdict:
            mismatched.append("verdict")
    if mismatched:
        return {"replay_ok": False, "reason": "result_mismatch", "mismatched_fields": mismatched, **base}
    return {"replay_ok": True, "reason": None, **base}
