#!/usr/bin/env python3
"""RunPod lifecycle for the colony-v2 experiment: one on-demand vLLM pod at a time.

Commands: ``up --model KEY`` | ``status`` | ``down`` | ``balance``.
The RunPod key is read from env RUNPOD_API_KEY (never logged). No Hugging Face token is
passed: every model is ungated. A fresh API secret is generated per pod and stored with the
pod id in ~/.config/antelligence/colony-v2-pod.json (chmod 600, outside the repo).
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

GRAPHQL_URL = "https://api.runpod.io/graphql"
REST_URL = "https://rest.runpod.io/v1"
STATE_PATH = Path("~/.config/antelligence/colony-v2-pod.json").expanduser()
# Verified 2026-10-10: the tag exists and its model registry has every architecture below. Never use ``latest``.
VLLM_IMAGE = "vllm/vllm-openai:v0.30.0"  # 2026-09-22; registry has Qwen3_5/Gemma4/Phi3 architectures
GPU_TYPES = ("NVIDIA L40S", "NVIDIA A40")  # first choice, then fallback
CONTAINER_DISK_GB = 80
MAX_WALL_HOURS = 2.0
# key -> HF repo (also the served name, so the response-model identity check pins the weights).
# revision: HF commit hashes pinned 2026-10-10 (recorded in every cell).
POD_MODELS: Dict[str, Dict[str, Optional[str]]] = {
    "qwen": {"hf": "Qwen/Qwen3.8-27B-FP8", "served": "Qwen/Qwen3.8-27B-FP8",
             "revision": "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"},
    "phi": {"hf": "microsoft/Phi-4-mini-instruct", "served": "microsoft/Phi-4-mini-instruct",
             "revision": "cfbefacb99257ffa30c83adab238a50856ac3083"},
    "gemma": {"hf": "google/gemma-4-E4B-it", "served": "google/gemma-4-E4B-it",
             "revision": "ee0ef6023621cff504d758262d4e04895a5af4a2"},
}
# Not a pod model: Claude Haiku 5.5 via the Nous inference API.
HAIKU_NOUS_ID = "anthropic/claude-haiku-5.5"


def vllm_args(model: str) -> List[str]:
    """``vllm serve`` arguments. The API key is NOT here: vLLM reads it from env VLLM_API_KEY."""
    spec = POD_MODELS[model]
    parts = [spec["hf"], "--served-model-name", spec["served"], "--max-model-len", "8192",
             "--gpu-memory-utilization", "0.92", "--seed", "0"]
    if spec["revision"]:
        parts += ["--revision", spec["revision"]]
    # Qwen3.8's template thinks by default and would spend the answer budget on it; answer directly.
    # Gemma 4's template already defaults to no thinking; Phi-4-mini has none. Same setting for every seat.
    return parts + ["--default-chat-template-kwargs", '{"enable_thinking":false}']


def start_script(model: str) -> str:
    """Container command: vLLM on :8000; its log, with the key redacted, served read-only on :8001.

    RunPod has no log API, so a crash-looping server is otherwise invisible. Only /logs is served.
    After vLLM exits the container stays up so the log can be read; ``down`` terminates it.
    """
    serve = " ".join(shlex.quote(a) for a in ["vllm", "serve", *vllm_args(model)])
    return ("mkdir -p /logs && (python3 -m http.server 8001 --directory /logs >/dev/null 2>&1 &) && "
            f"{{ {serve} 2>&1 | sed -u \"s/$VLLM_API_KEY/[redacted]/g\" > /logs/vllm.log; }}; "
            "echo \"vllm exited\" >> /logs/vllm.log; sleep infinity")


def deploy_payload(model: str, api_secret: str, gpu: str) -> Dict[str, Any]:
    """REST body for one on-demand pod. Pure: builds, never sends."""
    return {"name": f"colony-v2-{model}", "imageName": VLLM_IMAGE, "gpuTypeIds": [gpu], "gpuCount": 1,
            "containerDiskInGb": CONTAINER_DISK_GB, "volumeInGb": 0, "ports": ["8000/http", "8001/http"],
            "env": {"VLLM_API_KEY": api_secret}, "dockerEntrypoint": ["bash", "-c"],
            "dockerStartCmd": [start_script(model)]}


def rest(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> httpx.Response:
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        sys.exit("RUNPOD_API_KEY is not set (load it from ~/.hermes/.env)")
    return httpx.request(method, REST_URL + path, json=body, headers={"Authorization": f"Bearer {key}"},
                         timeout=60.0, follow_redirects=False, trust_env=False)


def gql(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        sys.exit("RUNPOD_API_KEY is not set (load it from ~/.hermes/.env)")
    r = httpx.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}},
                   headers={"Authorization": f"Bearer {key}"}, timeout=60.0, follow_redirects=False, trust_env=False)
    if r.status_code != 200:
        sys.exit(f"RunPod HTTP {r.status_code}")
    return r.json()


def load_state() -> Optional[Dict[str, Any]]:
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else None


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(STATE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(json.dumps(state, indent=1))
    os.chmod(STATE_PATH, 0o600)


def pod_info(pod_id: str) -> Optional[Dict[str, Any]]:
    r = rest("GET", f"/pods/{pod_id}")
    return r.json() if r.status_code == 200 else None


def spend_line(state: Dict[str, Any]) -> str:
    start = datetime.fromisoformat(state["created_utc"])
    hours = (datetime.now(timezone.utc) - start).total_seconds() / 3600
    return f"elapsed {hours * 60:.1f} min, estimated spend ${hours * float(state.get('cost_per_hr') or 0):.3f}"


def wait_ready(state: Dict[str, Any], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{state['base_url']}/models", headers={"Authorization": f"Bearer {state['api_secret']}"},
                          timeout=15.0, trust_env=False)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(15)
    return False


def cmd_up(args: argparse.Namespace) -> int:
    if args.model not in POD_MODELS:
        sys.exit(f"{args.model!r} is not a pod model (choose from {sorted(POD_MODELS)}; haiku runs via Nous)")
    state = load_state()
    if state:
        info = pod_info(state["pod_id"])
        if info and info.get("desiredStatus") == "RUNNING":
            sys.exit(f"pod {state['pod_id']} ({state['model']}) is still running; run `down` first (one pod at a time)")
        print("stale state file (pod gone); replacing it")
    api_secret = secrets.token_urlsafe(32)
    for gpu in GPU_TYPES:
        r = rest("POST", "/pods", deploy_payload(args.model, api_secret, gpu))
        pod = r.json() if r.status_code in (200, 201) else None
        if pod and pod.get("id"):
            break
        print(f"{gpu} unavailable: HTTP {r.status_code} {r.text[:160]}")
    else:
        sys.exit("no GPU available")
    spec = POD_MODELS[args.model]
    state = {"pod_id": pod["id"], "api_secret": api_secret, "model": args.model, "served": spec["served"],
             "hf": spec["hf"], "revision": spec["revision"], "image": VLLM_IMAGE, "gpu": gpu,
             "cost_per_hr": pod.get("costPerHr"), "created_utc": datetime.now(timezone.utc).isoformat(),
             "base_url": f"https://{pod['id']}-8000.proxy.runpod.net/v1",
             "log_url": f"https://{pod['id']}-8001.proxy.runpod.net/vllm.log"}
    save_state(state)
    print(f"pod {pod['id']} on {gpu} at ${pod.get('costPerHr')}/hr; base_url {state['base_url']}")
    if args.wait:
        ok = wait_ready(state, MAX_WALL_HOURS * 3600)
        print("ready" if ok else "NOT READY within the wall-clock cap; run `down`", "|", spend_line(state))
        return 0 if ok else 1
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("no pod recorded")
        return 0
    info = pod_info(state["pod_id"])
    print(json.dumps({"pod_id": state["pod_id"], "model": state["model"], "gpu": state["gpu"],
                      "desiredStatus": (info or {}).get("desiredStatus", "GONE"), "base_url": state["base_url"],
                      "log_url": state.get("log_url")}))
    print(spend_line(state))
    return 0


def cmd_down(_: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("no pod recorded")
        return 0
    r = rest("DELETE", f"/pods/{state['pod_id']}")
    if r.status_code not in (200, 204) and pod_info(state["pod_id"]):
        sys.exit(f"terminate failed: HTTP {r.status_code} {r.text[:200]}; pod may still be billing")
    print(f"terminated {state['pod_id']} |", spend_line(state))
    STATE_PATH.unlink()
    return 0


def cmd_balance(_: argparse.Namespace) -> int:
    me = (gql("query { myself { clientBalance currentSpendPerHr } }").get("data") or {}).get("myself") or {}
    print(json.dumps(me))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    up = sub.add_parser("up")
    up.add_argument("--model", required=True)
    up.add_argument("--no-wait", dest="wait", action="store_false")
    for name in ("status", "down", "balance"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    return {"up": cmd_up, "status": cmd_status, "down": cmd_down, "balance": cmd_balance}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
