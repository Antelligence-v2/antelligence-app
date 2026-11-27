"""L0 canonical SHA-256 hash-chained JSONL record, blobs, lock, and 12 MiB rollover."""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from typing import Any

GENESIS = "0" * 64
MAX_INT = 9_007_199_254_740_991
FILE_LIMIT = 16_777_216
LINE_LIMIT = 1_048_576
ROLLOVER_BYTES = 12 * 1024 * 1024
BLOB_THRESHOLD = 4096

TOP_KEYS = {"v", "run", "seq", "t", "kind", "actor", "data", "prev", "hash"}
SPECS: dict[str, dict[str, Any]] = {
    "run_start": {"task": str, "permissions": dict, "parent_run": (str, type(None)), "parent_seq": (int, type(None)), "depth": int},
    "model_call": {"model": str, "input_sha256": str},
    "model_result": {"tokens_in": int, "tokens_out": int, "cost_microusd": int, "output_sha256": str},
    "permission": {"action": str, "decision": str, "rule": str},
    "tool_call": {"tool": str, "args": object},
    "tool_result": {"ok": bool, "result": str, "bytes": int},
    "child_start": {"child_run": str},
    "child_end": {"child_run": str, "status": str, "digest": str},
    "note": {"text": str},
    "run_end": {"status": str, "grader": str, "grader_kind": str, "detail": str},
}
_HEX64 = re.compile(r"[0-9a-f]{64}")
_KEY_RE = re.compile(r"[a-z0-9_]+")
_INT_RE = re.compile(r"0|[1-9][0-9]*")


class Reject(Exception):
    pass


class LockHeld(Exception):
    pass


class NeedsRecovery(Exception):
    pass


class _Integer(str):
    pass


class _FloatToken(str):
    pass


def _result(code: str | None = None, status: str | None = None) -> dict[str, Any]:
    return {"valid": code is None, "status": status if code is None else None, "code": code}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def seal_event(run: str, seq: int, t: int, kind: str, actor: str, data: dict[str, Any], prev: str, v: str = "0.2") -> dict[str, Any]:
    ev = {"v": v, "run": run, "seq": seq, "t": t, "kind": kind, "actor": actor, "data": data, "prev": prev}
    ev["hash"] = hashlib.sha256(canonical(ev).encode("utf-8")).hexdigest()
    return ev


def line_bytes(ev: dict[str, Any]) -> bytes:
    return canonical(ev).encode("utf-8") + b"\n"


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in items:
        if k in d:
            raise Reject("E_SCHEMA")
        d[k] = v
    return d


def _syntax_tree(x: Any, depth: int = 0) -> None:
    if depth > 128:
        raise Reject("E_SCHEMA")
    if isinstance(x, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in x):
        raise Reject("E_SCHEMA")
    if isinstance(x, dict):
        for k, v in x.items():
            if any(0xD800 <= ord(c) <= 0xDFFF for c in k):
                raise Reject("E_SCHEMA")
            _syntax_tree(v, depth + 1)
    elif isinstance(x, list):
        for v in x:
            _syntax_tree(v, depth + 1)


def _has_float(x: Any) -> bool:
    if isinstance(x, _FloatToken):
        return True
    if isinstance(x, dict):
        return any(_has_float(v) for v in x.values())
    if isinstance(x, list):
        return any(_has_float(v) for v in x)
    return False


def _domain(x: Any) -> Any:
    if isinstance(x, _Integer):
        if not _INT_RE.fullmatch(x) or len(x) > 16 or int(x) > MAX_INT:
            raise Reject("E_SCHEMA")
        return int(x)
    if isinstance(x, dict):
        if any(not _KEY_RE.fullmatch(k) for k in x):
            raise Reject("E_SCHEMA")
        return {k: _domain(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_domain(v) for v in x]
    return x


def _decode(text: str | bytes) -> tuple[list[str], list[Any]]:
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8")
        except UnicodeError as exc:
            raise Reject("E_SCHEMA") from exc
    if not isinstance(text, str) or not text or len(text.encode("utf-8")) > FILE_LIMIT:
        raise Reject("E_SCHEMA")
    body = text[:-1] if text.endswith("\n") else text
    lines = body.split("\n")
    if any(not ln or "\r" in ln or len(ln.encode("utf-8")) > LINE_LIMIT for ln in lines):
        raise Reject("E_SCHEMA")
    events: list[Any] = []
    for line in lines:
        try:
            x = json.loads(
                line,
                parse_int=_Integer,
                parse_float=_FloatToken,
                object_pairs_hook=_pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(Reject("E_SCHEMA")),
            )
            _syntax_tree(x)
            events.append(x)
        except (ValueError, RecursionError) as exc:
            raise Reject("E_SCHEMA") from exc
    if any(_has_float(ev) for ev in events):
        raise Reject("E_FLOAT")
    return lines, events


def _digest(x: Any) -> bool:
    return type(x) is str and _HEX64.fullmatch(x) is not None


def _typeok(x: Any, t: Any) -> bool:
    return t is object or type(x) in (t if isinstance(t, tuple) else (t,))


def _schema(e: Any, i: int, run: str | None, legacy: bool) -> None:
    if type(e) is not dict or set(e) != TOP_KEYS:
        raise Reject("E_SCHEMA")
    if e["v"] != ("0.1" if legacy else "0.2") or type(e["run"]) is not str or e["run"] != run:
        raise Reject("E_SCHEMA")
    if type(e["kind"]) is not str or e["kind"] not in SPECS or type(e["actor"]) is not str or type(e["data"]) is not dict:
        raise Reject("E_SCHEMA")
    if type(e["seq"]) is not int or type(e["t"]) is not int or not _digest(e["prev"]) or not _digest(e["hash"]):
        raise Reject("E_SCHEMA")
    d, k = e["data"], e["kind"]
    if any(key not in d or not _typeok(d[key], t) for key, t in SPECS[k].items()):
        raise Reject("E_SCHEMA")
    if (i == 0) != (k == "run_start"):
        raise Reject("E_SCHEMA")
    if k == "run_start":
        p = d["permissions"]
        c = p.get("caps")
        if p.get("default") != "deny" or type(p.get("allow")) is not list or any(type(t) is not str for t in p["allow"]):
            raise Reject("E_SCHEMA")
        if type(c) is not dict or any(type(c.get(key)) is not int for key in ("spend_microusd", "max_steps", "max_depth")):
            raise Reject("E_SCHEMA")
        root = d["parent_run"] is None and d["parent_seq"] is None and d["depth"] == 0
        child = type(d["parent_run"]) is str and type(d["parent_seq"]) is int and d["depth"] > 0
        if not (root or child):
            raise Reject("E_SCHEMA")
    if k == "permission" and d["decision"] not in ("allow", "deny"):
        raise Reject("E_SCHEMA")
    if k == "run_end" and (d["status"] not in ("pass", "fail", "error", "aborted") or d["grader_kind"] not in ("automatic", "human", "model", "none")):
        raise Reject("E_SCHEMA")
    for key in ("input_sha256", "output_sha256", "digest"):
        if key in SPECS[k] and not _digest(d[key]):
            raise Reject("E_SCHEMA")


def checked(text: str | bytes, legacy: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lines, raw = _decode(text)
    events: list[dict[str, Any]] = []
    spent = steps = 0
    ended = False
    prev = GENESIS
    last_t = 0
    run: str | None = None
    permissions: dict[str, Any] = {}
    caps: dict[str, int] = {}
    for i, x in enumerate(raw):
        e = _domain(x)
        if i == 0 and isinstance(e, dict):
            run = e.get("run")
        _schema(e, i, run, legacy)
        if canonical(e) != lines[i]:
            raise Reject("E_SCHEMA")
        if e["seq"] != i:
            raise Reject("E_SEQ")
        if ended:
            raise Reject("E_AFTER_END")
        if e["prev"] != prev:
            raise Reject("E_PREV")
        h = hashlib.sha256(canonical({k: v for k, v in e.items() if k != "hash"}).encode("utf-8")).hexdigest()
        if e["hash"] != h:
            raise Reject("E_HASH")
        if e["t"] < last_t:
            raise Reject("E_TIME")
        k, d = e["kind"], e["data"]
        if i == 0:
            permissions = d["permissions"]
            caps = permissions["caps"]
        if k == "tool_call":
            p = events[-1]
            if p["kind"] != "permission" or p["data"]["decision"] != "allow" or p["data"]["action"] != d["tool"] or d["tool"] not in permissions["allow"]:
                raise Reject("E_NO_PERMISSION")
        if k == "run_start" and d["depth"] > caps["max_depth"]:
            raise Reject("E_CAP")
        if k == "model_call":
            if spent > caps["spend_microusd"] or steps >= caps["max_steps"]:
                raise Reject("E_CAP")
            steps += 1
        if k == "model_result":
            spent += d["cost_microusd"]
        if k == "run_end":
            ended = True
        events.append(e)
        prev = h
        last_t = e["t"]
    return events, _result(status="complete" if ended else "open")


def validate(text: str | bytes, legacy: bool = False) -> dict[str, Any]:
    try:
        return checked(text, legacy)[1]
    except (Reject, UnicodeError) as exc:
        return _result(str(exc) if isinstance(exc, Reject) else "E_SCHEMA")


def bundle(files: dict[str, str | bytes]) -> dict[str, Any]:
    try:
        if type(files) is not dict or not files or any(type(k) is not str or type(v) not in (str, bytes) for k, v in files.items()):
            raise Reject("E_SCHEMA")
        if any(any(0xD800 <= ord(c) <= 0xDFFF for c in name) for name in files):
            raise Reject("E_SCHEMA")
        runs: dict[str, list[dict[str, Any]]] = {}
        all_events: list[list[dict[str, Any]]] = []
        complete = True
        for _, text in sorted(files.items()):
            events, r = checked(text)
            rid = events[0]["run"]
            all_events.append(events)
            complete &= r["status"] == "complete"
            if rid not in runs:
                runs[rid] = events
        if len(runs) != len(files):
            raise Reject("E_CHILD_STRUCTURE")
        starts: dict[str, tuple[str, int]] = {}
        ends: dict[str, dict[str, Any]] = {}
        for events in all_events:
            rid = events[0]["run"]
            local: dict[str, bool] = {}
            for e in events:
                k, d = e["kind"], e["data"]
                if k == "child_start":
                    cid = d["child_run"]
                    if cid == rid or cid in starts:
                        raise Reject("E_CHILD_STRUCTURE")
                    starts[cid] = (rid, e["seq"])
                    local[cid] = False
                elif k == "child_end":
                    cid = d["child_run"]
                    if cid not in local or local[cid] or cid in ends:
                        raise Reject("E_CHILD_STRUCTURE")
                    local[cid] = True
                    ends[cid] = d
            if events[-1]["kind"] == "run_end" and not all(local.values()):
                raise Reject("E_CHILD_STRUCTURE")
        if any(cid not in runs for cid in starts) or any(ev[0]["data"]["parent_run"] is not None and ev[0]["data"]["parent_run"] not in runs for ev in all_events):
            raise Reject("E_CHILD_MISSING")
        for rid, ev in runs.items():
            d = ev[0]["data"]
            if rid in starts:
                if (d["parent_run"], d["parent_seq"]) != starts[rid]:
                    raise Reject("E_CHILD_LINK")
            elif d["parent_run"] is not None:
                raise Reject("E_CHILD_LINK")
        for cid, (pid, _) in starts.items():
            if runs[cid][0]["data"]["depth"] != runs[pid][0]["data"]["depth"] + 1:
                raise Reject("E_CHILD_DEPTH")
        if any(d["digest"] != runs[cid][-1]["hash"] for cid, d in ends.items()):
            raise Reject("E_CHILD_DIGEST")
        for cid, d in ends.items():
            end = runs[cid][-1]
            if d["status"] != (end["data"]["status"] if end["kind"] == "run_end" else "open"):
                raise Reject("E_CHILD_STATUS")
        return _result(status="complete" if complete else "open")
    except (Reject, UnicodeError) as exc:
        return _result(str(exc) if isinstance(exc, Reject) else "E_SCHEMA")


def write_blob(blobs_dir: str, payload: bytes | str) -> str:
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    digest = hashlib.sha256(raw).hexdigest()
    os.makedirs(blobs_dir, exist_ok=True)
    target = os.path.join(blobs_dir, digest)
    if not os.path.exists(target):
        tmp = f"{target}.tmp-{os.getpid()}"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, target)
    return digest


def read_blob(blobs_dir: str, sha256_hex: str) -> bytes:
    if not _digest(sha256_hex):
        raise ValueError("invalid blob digest")
    with open(os.path.join(blobs_dir, sha256_hex), "rb") as f:
        return f.read()


def externalize_payload(blobs_dir: str, data: dict[str, Any], threshold: int = BLOB_THRESHOLD) -> dict[str, Any]:
    out = dict(data)
    for key in ("result", "text", "detail"):
        val = out.get(key)
        if isinstance(val, str):
            raw = val.encode("utf-8")
            if len(raw) > threshold:
                digest = write_blob(blobs_dir, raw)
                out[key] = f"blob:{digest}"
                out["blob_sha256"] = digest
                out["blob_bytes"] = len(raw)
    return out


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_events(path: str) -> list[dict[str, Any]]:
    with open(path, "rb") as f:
        events, _ = checked(f.read())
    return events


def read_segments(paths: list[str]) -> list[dict[str, Any]]:
    all_events: list[dict[str, Any]] = []
    prev_seg_sha: str | None = None
    expected_run: str | None = None
    for idx, path in enumerate(paths):
        with open(path, "rb") as f:
            raw = f.read()
        events, _ = checked(raw)
        if idx > 0:
            rs = events[0]["data"]
            if expected_run is not None and events[0]["run"] != expected_run:
                raise Reject("E_CHILD_LINK")
            if rs.get("prev_segment_sha256") != prev_seg_sha:
                raise Reject("E_PREV")
        prev_seg_sha = hashlib.sha256(raw).hexdigest()
        expected_run = events[-1]["data"].get("continuation_run_id") if events[-1]["kind"] == "run_end" else None
        all_events.extend(events)
    return all_events


class Writer:
    """Append-only L0 writer with O_CREAT|O_EXCL lock, >4 KiB blob externalization, and 12 MiB rollover."""

    def __init__(
        self,
        path: str,
        run: str = "r-0",
        task: str = "run",
        allow: list[str] | None = None,
        caps: dict[str, int] | None = None,
        use_lock: bool = True,
        max_bytes: int = ROLLOVER_BYTES,
        blobs_dir: str | None = None,
        blob_threshold: int = BLOB_THRESHOLD,
    ) -> None:
        self.path = path
        self.run = run
        self.task = task
        self.allow = list(allow or [])
        self.caps = dict(caps or {"spend_microusd": 0, "max_steps": 0, "max_depth": 0})
        self.use_lock = use_lock
        self.max_bytes = max_bytes
        self.blobs_dir = blobs_dir if blobs_dir is not None else os.path.join(os.path.dirname(os.path.abspath(path)), "blobs")
        self.blob_threshold = blob_threshold
        self.lock_path = path + ".lock"
        self.locked = False
        self.fd: int | None = None
        self.segments: list[tuple[str, str]] = []
        self._seg_index = 0
        self._base_stem = path[:-6] if path.endswith(".jsonl") else path
        if use_lock:
            self._acquire()
        try:
            self._open_state()
        except Exception:
            self.close()
            raise

    def __enter__(self) -> "Writer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _acquire(self) -> None:
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            try:
                pid = int(open(self.lock_path, encoding="utf-8").read().split()[0])
            except Exception:
                pid = -1
            if pid > 0 and _pid_alive(pid):
                raise LockHeld(f"lock held by live pid {pid}") from exc
            raise NeedsRecovery("stale lock: run recover() then remove the lock deliberately") from exc
        os.write(fd, f"{os.getpid()} {random.random()}\n".encode("utf-8"))
        os.close(fd)
        self.locked = True

    def _open_state(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        exists = os.path.exists(self.path) and os.path.getsize(self.path) > 0
        if exists:
            data = open(self.path, "rb").read()
            res = validate(data)
            if not res["valid"]:
                raise NeedsRecovery(f"file is invalid ({res['code']}); recover() first")
            evs, _ = checked(data)
            last = evs[-1]
            if last["kind"] == "run_end":
                raise NeedsRecovery("run already ended")
            self.seq, self.t, self.prev, self.run = last["seq"] + 1, last["t"] + 1, last["hash"], last["run"]
            self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            self._bytes = len(data)
            if not data.endswith(b"\n"):
                os.write(self.fd, b"\n")
                self._bytes += 1
        else:
            self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            self.seq, self.t, self.prev, self._bytes = 0, 1_792_600_000_000_000, GENESIS, 0
            start = {"task": self.task, "permissions": {"default": "deny", "allow": self.allow, "caps": self.caps}, "parent_run": None, "parent_seq": None, "depth": 0}
            self.append("run_start", start, actor="harness")
        self.segments.append((self.run, self.path))

    def _rollover(self) -> None:
        self._seg_index += 1
        next_run = f"{self.run.split('-seg')[0]}-seg{self._seg_index}"
        next_path = f"{self._base_stem}.seg{self._seg_index:04d}.jsonl"
        end_ev = seal_event(
            self.run, self.seq, self.t, "run_end", "harness",
            {"status": "pass", "grader": "l0_rollover", "grader_kind": "automatic", "detail": "segment_rollover", "continuation_run_id": next_run},
            self.prev,
        )
        os.write(self.fd, line_bytes(end_ev))
        os.close(self.fd)
        with open(self.path, "rb") as f:
            seg_sha = hashlib.sha256(f.read()).hexdigest()
        self.path, self.run, self.seq, self.prev = next_path, next_run, 0, GENESIS
        self.t += 1
        self._bytes = 0
        self.fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        start = {
            "task": self.task,
            "permissions": {"default": "deny", "allow": self.allow, "caps": self.caps},
            "parent_run": None,
            "parent_seq": None,
            "depth": 0,
            "continuation_run_id": next_run,
            "prev_segment_sha256": seg_sha,
        }
        ev = seal_event(self.run, self.seq, self.t, "run_start", "harness", start, self.prev)
        b = line_bytes(ev)
        os.write(self.fd, b)
        self.seq, self.prev, self.t = 1, ev["hash"], self.t + 1
        self._bytes += len(b)
        self.segments.append((self.run, self.path))

    def append(self, kind: str, data: dict[str, Any], actor: str = "harness") -> dict[str, Any]:
        payload = externalize_payload(self.blobs_dir, data, self.blob_threshold) if self.blobs_dir else data
        ev = seal_event(self.run, self.seq, self.t, kind, actor, payload, self.prev)
        b = line_bytes(ev)
        if kind != "run_end" and self.max_bytes > 0 and self._bytes + len(b) > self.max_bytes - 512:
            self._rollover()
            ev = seal_event(self.run, self.seq, self.t, kind, actor, payload, self.prev)
            b = line_bytes(ev)
        os.write(self.fd, b)
        self._bytes += len(b)
        self.seq, self.prev, self.t = self.seq + 1, ev["hash"], self.t + 1
        return ev

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        if self.locked:
            try:
                os.unlink(self.lock_path)
            except FileNotFoundError:
                pass
            self.locked = False
