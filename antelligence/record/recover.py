"""L0.5 crash diagnosis and deterministic non-destructive recovery."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

from .l0 import FILE_LIMIT, LINE_LIMIT, line_bytes, seal_event, validate

Oracle = Callable[[bytes], dict[str, Any]]


class RecoveryError(Exception):
    pass


def split_tail(data: bytes) -> tuple[bytes, bytes]:
    i = data.rfind(b"\n")
    return data[: i + 1], data[i + 1 :]


def over_limit(data: bytes) -> bool:
    return len(data) > FILE_LIMIT or any(len(ln) > LINE_LIMIT for ln in data.split(b"\n"))


def _event_hashes(prefix: bytes) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln in prefix.split(b"\n"):
        if ln:
            try:
                out.append(json.loads(ln.decode("utf-8")))
            except Exception:
                break
    return out


def _fork_suspected(data: bytes, whole: dict[str, Any]) -> bool:
    if whole["code"] not in ("E_SEQ", "E_PREV"):
        return False
    evs: list[dict[str, Any]] = []
    for ln in data.split(b"\n"):
        if not ln:
            continue
        try:
            evs.append(json.loads(ln.decode("utf-8")))
        except Exception:
            return False
    hashes = [e.get("hash") for e in evs]
    for i, e in enumerate(evs):
        if i >= 2 and e.get("prev") in hashes[: i - 1]:
            return True
    return False


def diagnose(data: bytes, oracle: Oracle = validate) -> dict[str, Any]:
    if len(data) == 0:
        return {"cls": "empty", "good_bytes": 0, "good_events": 0, "fragment_bytes": 0, "code": "E_SCHEMA", "fork_suspected": False, "over_limit": False}
    prefix, frag = split_tail(data)
    whole = oracle(data)
    base: dict[str, Any] = {"good_bytes": 0, "good_events": 0, "fragment_bytes": len(frag), "code": whole["code"], "fork_suspected": False}
    if whole["valid"]:
        n = sum(1 for ln in data.split(b"\n") if ln)
        out = {**base, "cls": "clean", "good_bytes": len(data), "good_events": n}
    elif frag and not prefix:
        out = {**base, "cls": "torn_first_line"}
    elif frag and prefix:
        vp = oracle(prefix)
        if vp["valid"] and vp["status"] == "open":
            n = sum(1 for ln in prefix.split(b"\n") if ln)
            out = {**base, "cls": "torn_tail", "good_bytes": len(prefix), "good_events": n}
        elif vp["valid"] and vp["status"] == "complete":
            out = {**base, "cls": "corrupt_tail_after_end"}
        else:
            out = {**base, "cls": "corrupt", "fork_suspected": _fork_suspected(data, whole)}
    else:
        out = {**base, "cls": "corrupt", "fork_suspected": _fork_suspected(data, whole)}
    out["over_limit"] = over_limit(data)
    return out


def recover(path: str, oracle: Oracle = validate) -> dict[str, Any]:
    """Never modifies `path`. Writes `.torn-<sha12>` and `.recovered` atomically."""
    with open(path, "rb") as f:
        data = f.read()
    d = diagnose(data, oracle)
    if d["cls"] not in ("clean", "torn_tail", "torn_first_line"):
        raise RecoveryError(f"not recoverable: {d['cls']} {d['code']}")
    prefix, frag = split_tail(data)
    res: dict[str, Any] = {"cls": d["cls"], "torn_path": None, "recovered_path": None}
    if d["cls"] == "clean":
        return res
    torn = f"{path}.torn-{hashlib.sha256(frag).hexdigest()[:12]}"
    if os.path.exists(torn):
        with open(torn, "rb") as f:
            if f.read() != frag:
                raise RecoveryError("existing .torn file differs")
    else:
        with open(torn, "wb") as f:
            f.write(frag)
    res["torn_path"] = torn
    if d["cls"] == "torn_first_line":
        return res
    last = _event_hashes(prefix)[-1]
    text = (
        f"recovered; dropped_bytes={len(frag)}; dropped_sha256={hashlib.sha256(frag).hexdigest()}; "
        f"source_sha256={hashlib.sha256(data).hexdigest()}"
    )
    note = seal_event(last["run"], last["seq"] + 1, last["t"], "note", "recovery", {"text": text}, last["hash"])
    out = path + ".recovered"
    tmp = out + ".tmp"
    with open(tmp, "wb") as f:
        f.write(prefix + line_bytes(note))
    os.replace(tmp, out)
    res["recovered_path"] = out
    return res
