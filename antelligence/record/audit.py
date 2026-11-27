"""Offline bundle and directory tree auditor (v0.4 subtree escrow + v0.2/v0.3 validation)."""
from __future__ import annotations

import json
import os
from typing import Any

from .l0 import bundle as validate_bundle
from .l1_gate import MIN_USABLE_RATE


def _subtree_usage(
    rid: str,
    runs: dict[str, list[dict[str, Any]]],
    memo: dict[str, tuple[int, int]],
) -> tuple[int, int]:
    if rid in memo:
        return memo[rid]
    evs = runs[rid]
    direct_spend = sum(e["data"]["cost_microusd"] for e in evs if e["kind"] == "model_result")
    direct_steps = sum(1 for e in evs if e["kind"] == "model_call")
    child_spend = child_steps = 0
    for e in evs:
        if e["kind"] != "child_start":
            continue
        cid = e["data"]["child_run"]
        end = next((x for x in evs if x["kind"] == "child_end" and x["data"]["child_run"] == cid), None)
        cc = runs[cid][0]["data"]["permissions"]["caps"] if cid in runs else {"spend_microusd": 0, "max_steps": 0}
        if end is None:
            child_spend += cc["spend_microusd"]
            child_steps += cc["max_steps"]
        else:
            cs, cn = _subtree_usage(cid, runs, memo) if cid in runs else (0, 0)
            child_spend += max(end["data"].get("spent_microusd", 0), cs)
            child_steps += max(end["data"].get("steps_used", 0), cn)
    memo[rid] = (direct_spend + child_spend, direct_steps + child_steps)
    return memo[rid]


def check_bundle(files: dict[str, bytes | str]) -> list[str]:
    """Check subtree budget, depth, and allow-list invariants across a bundle."""
    runs: dict[str, list[dict[str, Any]]] = {}
    for _, b in files.items():
        text = b.decode("utf-8") if isinstance(b, bytes) else b
        evs = [json.loads(ln) for ln in text.splitlines() if ln]
        runs[evs[0]["run"]] = evs
    out: list[str] = []
    memo: dict[str, tuple[int, int]] = {}
    for rid, evs in runs.items():
        perms = evs[0]["data"]["permissions"]
        cap_s, cap_n, cap_d = perms["caps"]["spend_microusd"], perms["caps"]["max_steps"], perms["caps"]["max_depth"]
        for ev in evs:
            if ev["kind"] != "child_start":
                continue
            s, cid = ev["seq"], ev["data"]["child_run"]
            if cid not in runs:
                out.append(f"{rid}: child {cid} not supplied")
                continue
            child = runs[cid][0]["data"]
            cc = child["permissions"]["caps"]
            cost = sum(e["data"]["cost_microusd"] for e in evs[:s] if e["kind"] == "model_result")
            calls = sum(1 for e in evs[:s] if e["kind"] == "model_call")
            esc_s = esc_n = 0
            for prior in evs[:s]:
                if prior["kind"] != "child_start":
                    continue
                pid = prior["data"]["child_run"]
                end = next((e for e in evs[:s] if e["kind"] == "child_end" and e["data"]["child_run"] == pid), None)
                pc = runs[pid][0]["data"]["permissions"]["caps"] if pid in runs else {"spend_microusd": 0, "max_steps": 0}
                if end is not None and "spent_microusd" in end["data"]:
                    ps, pn = _subtree_usage(pid, runs, memo) if pid in runs else (0, 0)
                    esc_s += max(end["data"]["spent_microusd"], ps)
                    esc_n += max(end["data"].get("steps_used", 0), pn)
                else:
                    esc_s += pc["spend_microusd"]
                    esc_n += pc["max_steps"]
            if cc["spend_microusd"] > cap_s - cost - esc_s:
                out.append(f"{rid}->{cid}: child spend cap {cc['spend_microusd']} > parent remaining {cap_s - cost - esc_s}")
            if cc["max_steps"] > cap_n - calls - esc_n:
                out.append(f"{rid}->{cid}: child max_steps {cc['max_steps']} > parent remaining {cap_n - calls - esc_n}")
            if cc["max_depth"] > cap_d:
                out.append(f"{rid}->{cid}: child max_depth {cc['max_depth']} > parent max_depth {cap_d}")
            if child["depth"] != evs[0]["data"]["depth"] + 1 or child["depth"] > cap_d:
                out.append(f"{rid}->{cid}: child depth {child['depth']} not parent depth+1 within parent max_depth")
            if not set(child["permissions"]["allow"]) <= set(perms["allow"]):
                out.append(f"{rid}->{cid}: child allow list not a subset of parent allow list")
    return out


def audit_tree(bundle_or_dir: dict[str, bytes | str] | str) -> dict[str, Any]:
    """Audit a bundle mapping or a run directory on disk."""
    usable_ok = True
    if isinstance(bundle_or_dir, str):
        files: dict[str, bytes | str] = {}
        for name in sorted(os.listdir(bundle_or_dir)):
            if name.endswith(".jsonl"):
                with open(os.path.join(bundle_or_dir, name), "rb") as f:
                    files[name] = f.read()
        status_path = os.path.join(bundle_or_dir, "run_status.json")
        if os.path.isfile(status_path):
            with open(status_path, encoding="utf-8") as f:
                st = json.load(f)
            if st.get("status") == "INVALID_RUN" or float(st.get("usable_rate", 1.0)) < MIN_USABLE_RATE:
                usable_ok = False
    else:
        files = bundle_or_dir
    v = validate_bundle(files)
    violations = check_bundle(files) if v["valid"] else []
    if not usable_ok:
        violations.append("STATUS=INVALID_RUN: usable_rate below threshold")
    return {
        "valid": bool(v["valid"]) and len(violations) == 0,
        "status": v["status"],
        "code": v["code"],
        "violations": violations,
        "runs": sorted(files.keys()),
    }
