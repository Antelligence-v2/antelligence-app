"""L1 subtree gate with cross-process static sub-budget slice escrow, kill file, atomic status, and usability gate."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import time
from typing import Any, Callable

from .l0 import GENESIS, externalize_payload, line_bytes, seal_event, validate

T0 = 1_792_600_000_000_000
MIN_USABLE_RATE = 0.85


class InvalidRunError(Exception):
    pass


def _is_int(x: Any) -> bool:
    return type(x) is int and 0 <= x <= 9_007_199_254_740_991


def atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_live_state(run_dir: str) -> dict[str, Any]:
    """Swarm Control #4: read runtime truth strictly from structured JSON artifacts, never prose docs."""
    state: dict[str, Any] = {}
    for name in ("run_status.json", "env_state.json", "manifest.lock.json"):
        p = os.path.join(run_dir, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                state[name] = json.load(f)
    return state


def export_bundle(run_dir: str, dest_dir: str, min_usable_rate: float = MIN_USABLE_RATE) -> str:
    """Export a run bundle only if usability >= min_usable_rate (blocks STATUS=INVALID_RUN)."""
    status_path = os.path.join(run_dir, "run_status.json")
    if os.path.isfile(status_path):
        with open(status_path, encoding="utf-8") as f:
            st = json.load(f)
        if st.get("status") == "INVALID_RUN" or float(st.get("usable_rate", 1.0)) < min_usable_rate:
            raise InvalidRunError(f"STATUS=INVALID_RUN: usable_rate={st.get('usable_rate')} < {min_usable_rate}")
    shutil.copytree(run_dir, dest_dir, dirs_exist_ok=True)
    return dest_dir


class L1Gate:
    """L1 safe-floor gate with subtree escrow accounting, concurrency caps, kill files, and atomic status."""

    def __init__(
        self,
        path: str,
        run: str,
        task: str,
        allow: list[str],
        caps: dict[str, int],
        parent: dict[str, Any] | None = None,
        kill_paths: tuple[str, ...] = (),
        clock: Callable[[], int] | None = None,
        max_concurrent_workers: int | None = None,
        min_usable_rate: float = MIN_USABLE_RATE,
        status_path: str | None = None,
        install_sigterm: bool = False,
        blobs_dir: str | None = None,
    ) -> None:
        for k in ("spend_microusd", "max_steps", "max_depth"):
            if not _is_int(caps.get(k)):
                raise ValueError(f"caps.{k} must be a non-negative integer <= 2^53-1")
        self.path, self.run, self.allow = path, run, list(allow)
        self.caps = dict(caps)
        self.depth = 0 if parent is None else parent["depth"] + 1
        self.parent = parent
        self.kill_paths = tuple(dict.fromkeys([f"{path}.kill", *kill_paths]))
        self._clock = clock
        self.max_concurrent_workers = max_concurrent_workers
        self.min_usable_rate = min_usable_rate
        self.blobs_dir = blobs_dir
        self.status_path = status_path or (os.path.join(os.path.dirname(os.path.abspath(path)), "run_status.json") if parent is None else None)
        self.seq, self.prev, self.t = 0, GENESIS, T0 - 1
        self.spent = 0
        self.calls = 0
        self.total_results = 0
        self.usable_results = 0
        self.in_flight: list[int] = []
        self.children: dict[str, dict[str, Any]] = {}
        self.ended = False
        self.end_status: str | None = None
        self.last_hash: str | None = None
        self.refusals: list[str] = []
        self._prev_sigterm: Any = None
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.f = open(path, "wb")
        self._emit(
            "run_start",
            {
                "task": task,
                "permissions": {"default": "deny", "allow": self.allow, "caps": self.caps},
                "parent_run": None if parent is None else parent["run"],
                "parent_seq": None if parent is None else parent["seq"],
                "depth": self.depth,
            },
            actor="l1_gate",
        )
        self._write_status("running")
        if install_sigterm:
            self._install_sigterm()

    def _install_sigterm(self) -> None:
        def _handler(_signum: int, _frame: Any) -> None:
            if not self.ended:
                self._abort("sigterm")
            raise SystemExit(143)

        self._prev_sigterm = signal.signal(signal.SIGTERM, _handler)

    @property
    def usable_rate(self) -> float:
        return self.usable_results / self.total_results if self.total_results > 0 else 1.0

    def _write_status(self, status: str) -> None:
        if not self.status_path:
            return
        effective = "INVALID_RUN" if (self.ended and self.total_results > 0 and self.usable_rate < self.min_usable_rate) else status
        atomic_write_json(
            self.status_path,
            {
                "run_id": self.run,
                "status": effective,
                "usable_rate": round(self.usable_rate, 6),
                "total_results": self.total_results,
                "usable_results": self.usable_results,
                "spent_microusd": self.subtree_spent(),
                "steps_used": self.subtree_calls(),
                "active_children": sum(1 for c in self.children.values() if c["state"] == "live"),
                "forfeited_microusd": sum(c["escrow_spend"] for c in self.children.values() if c["state"] == "forfeited"),
                "last_hash": self.last_hash,
                "pid": os.getpid(),
                "updated_at_us": int(time.time() * 1_000_000),
            },
        )

    def _emit(self, kind: str, data: dict[str, Any], actor: str = "l1_gate") -> dict[str, Any]:
        t = self._clock() if self._clock else self.t + 1
        t = max(t, self.t)
        payload = externalize_payload(self.blobs_dir, data) if self.blobs_dir else data
        ev = seal_event(self.run, self.seq, t, kind, actor, payload, self.prev)
        self.f.write(line_bytes(ev))
        self.f.flush()
        self.seq, self.prev, self.t, self.last_hash = self.seq + 1, ev["hash"], t, ev["hash"]
        return ev

    def _refuse(self, why: str) -> None:
        self.refusals.append(why)

    def _alive(self) -> bool:
        if self.ended:
            self._refuse("after_end")
            return False
        for k in self.kill_paths:
            if os.path.exists(k):
                self._abort("kill file present: " + os.path.basename(k))
                return False
        return True

    def _abort(self, reason: str) -> None:
        self._emit("note", {"text": "abort: " + reason})
        self.end("aborted", detail=reason)

    def close_file(self) -> None:
        if self._prev_sigterm is not None:
            signal.signal(signal.SIGTERM, self._prev_sigterm)
            self._prev_sigterm = None
        if not self.f.closed:
            self.f.close()

    def subtree_spent(self) -> int:
        child_total = sum(
            c["settled_spend"] if c["state"] == "done" else c["escrow_spend"]
            for c in self.children.values()
        )
        return self.spent + child_total

    def subtree_calls(self) -> int:
        child_total = sum(
            c["settled_steps"] if c["state"] == "done" else c["escrow_steps"]
            for c in self.children.values()
        )
        return self.calls + child_total

    def remaining(self) -> tuple[int, int]:
        spend = self.caps["spend_microusd"] - self.subtree_spent() - sum(self.in_flight)
        steps = self.caps["max_steps"] - self.subtree_calls()
        return spend, steps

    def tool(self, name: str, args: Any = None) -> bool:
        if not self._alive():
            return False
        if name not in self.allow:
            self._emit("permission", {"action": name, "decision": "deny", "rule": "not_in_allow_list"})
            self._refuse("tool_denied")
            return False
        self._emit("permission", {"action": name, "decision": "allow", "rule": "allow_list"})
        self._emit("tool_call", {"tool": name, "args": args}, actor="agent")
        return True

    def tool_result(self, ok: bool, result: str, nbytes: int | None = None) -> bool:
        if not self._alive():
            return False
        self._emit("tool_result", {"ok": bool(ok), "result": result, "bytes": len(result.encode()) if nbytes is None else nbytes}, actor="tool")
        return True

    def note(self, text: str) -> bool:
        if not self._alive():
            return False
        self._emit("note", {"text": text})
        return True

    def model_call(self, model: str, input_text: str, worst_case_microusd: int) -> bool:
        if not self._alive():
            return False
        if not _is_int(worst_case_microusd):
            raise ValueError("worst_case_microusd must be a non-negative integer")
        spend_left, steps_left = self.remaining()
        if steps_left < 1:
            self._emit("note", {"text": "refused model_call: step cap"})
            self._refuse("step_cap")
            return False
        if worst_case_microusd > spend_left:
            self._emit("note", {"text": "refused model_call: spend cap"})
            self._refuse("spend_cap")
            return False
        self.calls += 1
        self.in_flight.append(worst_case_microusd)
        self._emit("model_call", {"model": model, "input_sha256": hashlib.sha256(input_text.encode()).hexdigest(), "worst_case_microusd": worst_case_microusd}, actor="agent")
        return True

    def model_result(self, tokens_in: int, tokens_out: int, cost_microusd: int, output_text: str, format_ok: bool = True) -> bool:
        if self.ended:
            self._refuse("after_end")
            return False
        if not self.in_flight:
            self._emit("note", {"text": "refused model_result: no call in flight"})
            self._refuse("result_without_call")
            return False
        reserve = self.in_flight.pop(0)
        self.spent += cost_microusd
        self.total_results += 1
        if format_ok:
            self.usable_results += 1
        self._emit("model_result", {"tokens_in": tokens_in, "tokens_out": tokens_out, "cost_microusd": cost_microusd, "output_sha256": hashlib.sha256(output_text.encode()).hexdigest(), "format_ok": bool(format_ok)}, actor="model")
        if cost_microusd > reserve:
            self._emit("note", {"text": f"actual cost {cost_microusd} exceeded reserve {reserve}"})
            self.end("error", detail="actual cost exceeded worst-case reserve")
        return True

    def spawn_child(self, run: str, task: str, allow: list[str], caps: dict[str, int], external: bool = False) -> "L1Gate | None":
        if not self._alive():
            return None
        why = self._child_violation(run, allow, caps)
        if why:
            self._emit("permission", {"action": "child_start", "decision": "deny", "rule": why.split()[0]})
            self.note(f"child {run} refused: {why}")
            self._refuse("child_" + why.split()[0])
            return None
        ev = self._emit("child_start", {"child_run": run})
        child_path = os.path.join(os.path.dirname(self.path), run + ".jsonl")
        child = None if external else L1Gate(
            child_path, run, task, allow, caps,
            parent={"run": self.run, "seq": ev["seq"], "depth": self.depth},
            kill_paths=self.kill_paths, clock=self._clock, blobs_dir=self.blobs_dir,
        )
        self.children[run] = {
            "gate": child,
            "path": child_path,
            "escrow_spend": caps["spend_microusd"],
            "escrow_steps": caps["max_steps"],
            "state": "live",
            "settled_spend": caps["spend_microusd"],
            "settled_steps": caps["max_steps"],
        }
        return child

    def _child_violation(self, run: str, allow: list[str], caps: dict[str, int]) -> str | None:
        if run in self.children or run == self.run:
            return "duplicate or self run id"
        if self.max_concurrent_workers is not None:
            active = sum(1 for c in self.children.values() if c["state"] == "live")
            if active >= self.max_concurrent_workers:
                return f"max_concurrent_workers {active} >= {self.max_concurrent_workers}"
        for k in ("spend_microusd", "max_steps", "max_depth"):
            if not _is_int(caps.get(k)):
                return f"{k} invalid"
        spend_left, steps_left = self.remaining()
        if caps["spend_microusd"] > spend_left:
            return f"spend {caps['spend_microusd']} > parent remaining {spend_left}"
        if caps["max_steps"] > steps_left:
            return f"steps {caps['max_steps']} > parent remaining {steps_left}"
        if caps["max_depth"] > self.caps["max_depth"]:
            return "max_depth exceeds parent max_depth"
        cd = self.depth + 1
        if cd > self.caps["max_depth"]:
            return "depth exceeds parent max_depth"
        if caps["max_depth"] < cd:
            return "child max_depth below its own depth"
        if not set(allow) <= set(self.allow):
            return "allow list not a subset of parent allow list"
        return None

    def forfeit_child(self, run: str, reason: str = "crashed_or_orphaned") -> None:
        c = self.children[run]
        if c["state"] != "live":
            return
        c["state"] = "forfeited"
        c["settled_spend"] = c["escrow_spend"]
        c["settled_steps"] = c["escrow_steps"]
        self._emit("note", {"text": f"escrow forfeited for {run}: {reason}"})

    def finish_child(self, run: str, status: str = "pass", detail: str = "") -> None:
        c = self.children[run]
        if c["state"] != "live":
            return
        g: L1Gate | None = c["gate"]
        if g is not None:
            if not g.ended:
                g.end(status, detail=detail)
            sub_spent, sub_steps = g.subtree_spent(), g.subtree_calls()
            c_status, c_hash = g.end_status, g.last_hash
            g.close_file()
        else:
            if not os.path.isfile(c["path"]):
                self.forfeit_child(run, "missing child log")
                return
            with open(c["path"], "rb") as f:
                raw = f.read()
            res = validate(raw)
            if not res["valid"] or res["status"] != "complete":
                self.forfeit_child(run, f"unverified child log ({res['code'] or res['status']})")
                return
            evs = [json.loads(ln) for ln in raw.decode("utf-8").splitlines() if ln]
            c_status = evs[-1]["data"]["status"]
            c_hash = evs[-1]["hash"]
            sub_spent = sum(e["data"]["cost_microusd"] for e in evs if e["kind"] == "model_result")
            sub_steps = sum(1 for e in evs if e["kind"] == "model_call")
        c["state"] = "done"
        c["settled_spend"] = min(c["escrow_spend"], sub_spent)
        c["settled_steps"] = min(c["escrow_steps"], sub_steps)
        self._emit(
            "child_end",
            {"child_run": run, "status": c_status, "digest": c_hash, "spent_microusd": c["settled_spend"], "steps_used": c["settled_steps"]},
        )

    def end(self, status: str, grader: str = "l1_gate", grader_kind: str = "automatic", detail: str = "") -> None:
        if self.ended:
            return
        for run, c in list(self.children.items()):
            if c["state"] == "live":
                if c["gate"] is not None:
                    c["gate"].end("aborted", detail="parent ended")
                    self.finish_child(run, "aborted")
                else:
                    self.forfeit_child(run, "orphaned at parent end")
        self._emit("run_end", {"status": status, "grader": grader, "grader_kind": grader_kind, "detail": detail})
        self.ended, self.end_status = True, status
        self._write_status(status)
        self.close_file()


Gate = L1Gate
