#!/usr/bin/env python3
"""RunPod lifecycle for the v4 pilot: one on-demand vLLM pod at a time (goal section 8).

Commands: ``up <model>`` | ``status`` | ``wait`` | ``down`` | ``cost``. Port of colony_v2_pod.py.
Every pod start and stop is appended to ``ledger/v4-pod-costs.jsonl`` in the schema
``antelligence.experiments.v4_budget.pod_spend`` reads. ``up`` refuses when that spend plus one hour at the
quoted rate would pass the $2.75 hard stop. The RunPod key is read from ~/.hermes/.env in ``runpod_key`` only.
A fresh API secret is generated per pod and kept only in the gitignored 0600 state file; it is never printed.
Pure helpers (payload, command line, cost rows, refusal, state) are separate from HTTP so tests need no network.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from antelligence.experiments import v4_budget as budget  # noqa: E402

REST_URL = "https://rest.runpod.io/v1"
GRAPHQL_URL = "https://api.runpod.io/graphql"
# Pinned and verified 2026-10-10; never ``latest``.
VLLM_IMAGE = "vllm/vllm-openai:v0.30.0"
GPU_TYPES = ("NVIDIA L40S", "NVIDIA A40")  # first choice, then fallback
CONTAINER_DISK_GB = 80
MAX_WALL_HOURS = 2.0
HARD_STOP_USD = budget.LIMITS["runpod"]
ASSUMED_RATE_PER_HR = 1.20  # used for the pre-flight check only when the API gives no quote
# Served name is the HF id, so the response-model identity check pins the weights. Revisions are HF commits.
MODELS: Dict[str, Dict[str, Optional[str]]] = {
    "qwen3.5-0.8b": {"hf": "Qwen/Qwen3.5-0.8B", "revision": "2fc06364715b967f1860aea9cf38778875588b17"},
    "qwen3.5-4b": {"hf": "Qwen/Qwen3.5-4B", "revision": "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"},
    "qwen3.5-9b": {"hf": "Qwen/Qwen3.5-9B", "revision": "c202236235762e1c871ad0ccb60c8ee5ba337b9a"},
    # Hybrid (Mamba) layers: one cache block per running sequence, so 64 fit on an L40S where 256 do not.
    "qwen3.5-27b": {"hf": "Qwen/Qwen3.5-27B-FP8", "revision": "97f5941bf617e31c5e237364a8602ce3f03a551a",
                    "max_num_seqs": "64"},
    "qwen3.8-27b": {"hf": "Qwen/Qwen3.8-27B-FP8", "revision": "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a",
                    "max_num_seqs": "64"},
}


@dataclass
class Paths:
    state: Path = ROOT / "ledger" / "v4-pod-state.json"
    costs: Path = ROOT / "ledger" / "v4-pod-costs.jsonl"


# --- pure helpers -----------------------------------------------------------------


def served_name(model: str) -> str:
    return str(MODELS[model]["hf"])


def vllm_args(model: str) -> List[str]:
    """``vllm serve`` arguments. The API key is NOT here: vLLM reads it from env VLLM_API_KEY."""
    spec = MODELS[model]
    parts = [spec["hf"], "--served-model-name", served_name(model), "--max-model-len", "8192",
             "--gpu-memory-utilization", "0.92", "--seed", "0", "--revision", spec["revision"]]
    if spec.get("max_num_seqs"):
        parts += ["--max-num-seqs", spec["max_num_seqs"]]
    # Qwen templates think by default and would spend the answer budget on it; answer directly.
    return parts + ["--default-chat-template-kwargs", '{"enable_thinking":false}']


def start_script(model: str, log_token: str) -> str:
    """Container command: vLLM on :8000; its log (key redacted) served read-only on :8001 under a secret path."""
    serve = " ".join(shlex.quote(a) for a in ["vllm", "serve", *vllm_args(model)])
    log = f"/srv/{log_token}/vllm.log"
    # An empty index.html stops http.server from listing /srv (which would reveal the token).
    return (f"mkdir -p /srv/{log_token} && : > /srv/index.html && "
            f"(python3 -m http.server 8001 --directory /srv >/dev/null 2>&1 &) && "
            f"{{ {serve} 2>&1 | sed -u \"s/$VLLM_API_KEY/[redacted]/g\" > {log}; }}; "
            f"echo \"vllm exited\" >> {log}; sleep infinity")


def deploy_payload(model: str, api_secret: str, gpu: str, log_token: str) -> Dict[str, Any]:
    """REST body for one on-demand pod. Pure: builds, never sends."""
    return {"name": f"v4-pilot-{model}", "imageName": VLLM_IMAGE, "gpuTypeIds": [gpu], "gpuCount": 1,
            "containerDiskInGb": CONTAINER_DISK_GB, "volumeInGb": 0, "ports": ["8000/http", "8001/http"],
            "env": {"VLLM_API_KEY": api_secret}, "dockerEntrypoint": ["bash", "-c"],
            "dockerStartCmd": [start_script(model, log_token)]}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cost_row(event: str, pod_id: str, rate_per_hr: float, utc: Optional[str] = None) -> Dict[str, Any]:
    """One cost record in the schema ``v4_budget.pod_spend`` reads."""
    if event not in ("start", "stop"):
        raise ValueError(f"event must be start or stop, not {event!r}")
    return {"event": event, "pod_id": pod_id, "utc": utc or utc_now(), "rate_per_hr": float(rate_per_hr)}


def append_cost(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(row) + "\n")


def spend_so_far(costs: Path, now: Optional[datetime] = None) -> float:
    return budget.pod_spend(budget.read_jsonl(costs), now)


def refuse_over_budget(spent: float, rate_per_hr: float, limit: float = HARD_STOP_USD) -> Optional[str]:
    """Reason to refuse starting a pod (spend plus one hour at the quoted rate would pass the stop), else None."""
    if spent + rate_per_hr > limit:
        return f"budget: ${spent:.3f} spent + 1h at ${rate_per_hr:.3f}/hr would exceed the ${limit:.2f} hard stop"
    return None


def load_state(path: Path) -> Optional[Dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else None


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(state, indent=1))
    os.chmod(path, 0o600)


def public_view(state: Mapping[str, Any]) -> Dict[str, Any]:
    """State fields that are safe to print (no api_secret, no log url token)."""
    return {k: state.get(k) for k in ("pod_id", "model", "served", "gpu", "image", "revision", "cost_per_hr",
                                      "created_utc", "base_url")}


def elapsed_line(state: Mapping[str, Any], now: Optional[datetime] = None) -> str:
    start = datetime.fromisoformat(state["created_utc"])
    hours = ((now or datetime.now(timezone.utc)) - start).total_seconds() / 3600
    return f"elapsed {hours * 60:.1f} min, estimated spend ${hours * float(state.get('cost_per_hr') or 0):.3f}"


def serves_model(payload: Mapping[str, Any], expected: str) -> bool:
    return expected in [m.get("id") for m in payload.get("data", []) if isinstance(m, dict)]


# --- HTTP -------------------------------------------------------------------------


def runpod_key() -> str:
    """RUNPOD_API_KEY from ~/.hermes/.env. The only place the key file is read; never printed."""
    for line in Path("~/.hermes/.env").expanduser().read_text().splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "RUNPOD_API_KEY":
            return value.strip().strip("'\"")
    raise SystemExit("RUNPOD_API_KEY not found in ~/.hermes/.env")


class RunPod:
    """Thin RunPod client; the transport is injectable so tests never touch the network."""

    def __init__(self, api_key: str, transport: Optional[httpx.BaseTransport] = None) -> None:
        self._http = httpx.Client(headers={"Authorization": f"Bearer {api_key}"}, timeout=60.0,
                                  follow_redirects=False, trust_env=False, transport=transport)

    def create_pod(self, body: Dict[str, Any]) -> httpx.Response:
        return self._http.post(f"{REST_URL}/pods", json=body)

    def get_pod(self, pod_id: str) -> httpx.Response:
        return self._http.get(f"{REST_URL}/pods/{pod_id}")

    def delete_pod(self, pod_id: str) -> httpx.Response:
        return self._http.delete(f"{REST_URL}/pods/{pod_id}")

    def quote(self, gpu: str) -> Optional[float]:
        """Secure-cloud on-demand $/hr for one GPU type, or None if the API gives no number."""
        query = "query($id: String!) { gpuTypes(input: {id: $id}) { securePrice } }"
        try:
            r = self._http.post(GRAPHQL_URL, json={"query": query, "variables": {"id": gpu}})
            price = r.json()["data"]["gpuTypes"][0]["securePrice"] if r.status_code == 200 else None
            return float(price) if price else None
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            return None


Echo = Callable[[str], None]


def pod_status(client: RunPod, pod_id: str) -> Optional[str]:
    """desiredStatus of a pod, "GONE" on 404, None when the API could not say."""
    r = client.get_pod(pod_id)
    if r.status_code == 404:
        return "GONE"
    return r.json().get("desiredStatus") if r.status_code == 200 else None


def wait_ready(state: Mapping[str, Any], timeout_s: float, transport: Optional[httpx.BaseTransport] = None,
               sleep: Callable[[float], None] = time.sleep, interval_s: float = 15.0) -> bool:
    """Poll the pod's /v1/models until it lists the expected served name."""
    deadline = time.monotonic() + timeout_s
    with httpx.Client(headers={"Authorization": f"Bearer {state['api_secret']}"}, timeout=15.0, trust_env=False,
                      transport=transport) as http:
        while True:
            try:
                r = http.get(f"{state['base_url']}/models")
                if r.status_code == 200 and serves_model(r.json(), state["served"]):
                    return True
            except (httpx.HTTPError, ValueError):
                pass
            if time.monotonic() >= deadline:
                return False
            sleep(interval_s)


# --- commands ---------------------------------------------------------------------


def cmd_up(model: str, client: RunPod, paths: Paths, echo: Echo = print, wait: bool = False,
           transport: Optional[httpx.BaseTransport] = None, sleep: Callable[[float], None] = time.sleep) -> int:
    if model not in MODELS:
        echo(f"unknown model {model!r}; choose from {sorted(MODELS)}")
        return 2
    state = load_state(paths.state)
    if state:
        status = pod_status(client, state["pod_id"])
        if status != "GONE":
            echo(f"refused: pod {state['pod_id']} ({state['model']}) may still be running "
                 f"(status {status}); run `down` first (one pod at a time)")
            return 1
        echo("stale state file (pod gone); closing its cost record and replacing it")
        append_cost(paths.costs, cost_row("stop", state["pod_id"], state.get("cost_per_hr") or 0.0))
        paths.state.unlink()
    spent = spend_so_far(paths.costs)
    pod: Optional[Dict[str, Any]] = None
    gpu = ""
    api_secret, log_token = secrets.token_urlsafe(32), secrets.token_hex(16)
    for gpu in GPU_TYPES:
        reason = refuse_over_budget(spent, client.quote(gpu) or ASSUMED_RATE_PER_HR)
        if reason:
            echo(f"refused: {reason}")
            return 1
        r = client.create_pod(deploy_payload(model, api_secret, gpu, log_token))
        body = r.json() if r.status_code in (200, 201) else None
        if body and body.get("id"):
            pod = body
            break
        echo(f"{gpu} unavailable: HTTP {r.status_code}")
    if pod is None:
        echo("no GPU available")
        return 1
    rate = float(pod.get("costPerHr") or ASSUMED_RATE_PER_HR)
    append_cost(paths.costs, cost_row("start", pod["id"], rate))
    state = {"pod_id": pod["id"], "api_secret": api_secret, "model": model, "served": served_name(model),
             "hf": MODELS[model]["hf"], "revision": MODELS[model]["revision"], "image": VLLM_IMAGE, "gpu": gpu,
             "cost_per_hr": rate, "created_utc": utc_now(),
             "base_url": f"https://{pod['id']}-8000.proxy.runpod.net/v1",
             "log_url": f"https://{pod['id']}-8001.proxy.runpod.net/{log_token}/vllm.log"}
    save_state(paths.state, state)
    echo(f"pod {pod['id']} on {gpu} at ${rate:.3f}/hr; base_url {state['base_url']}")
    if wait:
        return cmd_wait(paths, echo, transport, sleep)
    return 0


def cmd_status(client: RunPod, paths: Paths, echo: Echo = print) -> int:
    state = load_state(paths.state)
    if not state:
        echo("no pod recorded")
        return 0
    view = public_view(state)
    view["desiredStatus"] = pod_status(client, state["pod_id"])
    echo(json.dumps(view))
    echo(elapsed_line(state))
    return 0


def cmd_wait(paths: Paths, echo: Echo = print, transport: Optional[httpx.BaseTransport] = None,
             sleep: Callable[[float], None] = time.sleep, timeout_s: float = MAX_WALL_HOURS * 3600) -> int:
    state = load_state(paths.state)
    if not state:
        echo("no pod recorded")
        return 1
    ok = wait_ready(state, timeout_s, transport, sleep)
    echo(("ready: serving " + state["served"]) if ok else "NOT READY within the wall-clock cap; run `down`")
    echo(elapsed_line(state))
    return 0 if ok else 1


def cmd_down(client: RunPod, paths: Paths, echo: Echo = print) -> int:
    state = load_state(paths.state)
    if not state:
        echo("no pod recorded")
        return 0
    r = client.delete_pod(state["pod_id"])
    if r.status_code not in (200, 204) and pod_status(client, state["pod_id"]) != "GONE":
        echo(f"terminate failed: HTTP {r.status_code}; pod may still be billing")
        return 1
    append_cost(paths.costs, cost_row("stop", state["pod_id"], state.get("cost_per_hr") or 0.0))
    echo(f"terminated {state['pod_id']} | {elapsed_line(state)}")
    paths.state.unlink()
    return 0


def cmd_cost(paths: Paths, echo: Echo = print) -> int:
    spent = spend_so_far(paths.costs)
    echo(f"runpod spend ${spent:.3f} of ${HARD_STOP_USD:.2f} hard stop (${HARD_STOP_USD - spent:.3f} left)")
    return 0


def main(argv: Optional[List[str]] = None, *, paths: Optional[Paths] = None,
         transport: Optional[httpx.BaseTransport] = None, api_key: Optional[str] = None,
         sleep: Callable[[float], None] = time.sleep, echo: Echo = print) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up")
    up.add_argument("model", choices=sorted(MODELS))
    up.add_argument("--wait", action="store_true", help="after creating, block until vLLM serves the model")
    for name in ("status", "wait", "down", "cost"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    paths = paths or Paths()
    if args.cmd == "cost":
        return cmd_cost(paths, echo)
    if args.cmd == "wait":  # talks to the pod with its own secret, not the RunPod key
        return cmd_wait(paths, echo, transport, sleep)
    client = RunPod(api_key or runpod_key(), transport)
    if args.cmd == "up":
        return cmd_up(args.model, client, paths, echo, args.wait, transport, sleep)
    return {"status": cmd_status, "down": cmd_down}[args.cmd](client, paths, echo)


if __name__ == "__main__":
    sys.exit(main())
