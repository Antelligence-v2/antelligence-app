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
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

GRAPHQL_URL = "https://api.runpod.io/graphql"
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


def docker_args(model: str, api_secret: str) -> str:
    spec = POD_MODELS[model]
    parts = ["--model", spec["hf"], "--served-model-name", spec["served"], "--api-key", api_secret,
             "--max-model-len", "8192", "--gpu-memory-utilization", "0.92", "--seed", "0"]
    if spec["revision"]:
        parts += ["--revision", spec["revision"]]
    # Qwen3.8's template thinks by default and would spend the 512-token answer budget on it; answer directly.
    # Gemma 4's template already defaults to no thinking; Phi-4-mini has none. Same setting for every seat.
    parts += ["--default-chat-template-kwargs", "'{\"enable_thinking\":false}'"]
    return " ".join(str(p) for p in parts)


def deploy_payload(model: str, api_secret: str, gpu: str) -> Dict[str, Any]:
    """GraphQL request body for one on-demand pod. Pure: builds, never sends."""
    query = ("mutation Deploy($input: PodFindAndDeployOnDemandInput!) { podFindAndDeployOnDemand(input: $input) "
             "{ id costPerHr machine { gpuDisplayName } } }")
    variables = {"input": {"name": f"colony-v2-{model}", "cloudType": "ALL", "gpuCount": 1, "gpuTypeId": gpu,
                           "imageName": VLLM_IMAGE, "containerDiskInGb": CONTAINER_DISK_GB, "volumeInGb": 0,
                           "ports": "8000/http", "dockerArgs": docker_args(model, api_secret)}}
    return {"query": query, "variables": variables}


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
    out = gql("query($i: PodFilter) { pod(input: $i) { id desiredStatus costPerHr runtime { uptimeInSeconds } } }",
              {"i": {"podId": pod_id}})
    return (out.get("data") or {}).get("pod")


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
        out = gql(**deploy_payload(args.model, api_secret, gpu))
        pod = (out.get("data") or {}).get("podFindAndDeployOnDemand")
        if pod:
            break
        print(f"{gpu} unavailable: {str((out.get('errors') or [{}])[0].get('message'))[:120]}")
    else:
        sys.exit("no GPU available")
    spec = POD_MODELS[args.model]
    state = {"pod_id": pod["id"], "api_secret": api_secret, "model": args.model, "served": spec["served"],
             "hf": spec["hf"], "revision": spec["revision"], "image": VLLM_IMAGE, "gpu": gpu,
             "cost_per_hr": pod.get("costPerHr"), "created_utc": datetime.now(timezone.utc).isoformat(),
             "base_url": f"https://{pod['id']}-8000.proxy.runpod.net/v1"}
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
                      "desiredStatus": (info or {}).get("desiredStatus", "GONE"), "base_url": state["base_url"]}))
    print(spend_line(state))
    return 0


def cmd_down(_: argparse.Namespace) -> int:
    state = load_state()
    if not state:
        print("no pod recorded")
        return 0
    out = gql("mutation($i: PodTerminateInput!) { podTerminate(input: $i) }", {"i": {"podId": state["pod_id"]}})
    if out.get("errors") and pod_info(state["pod_id"]):
        sys.exit(f"terminate failed: {str(out['errors'][0].get('message'))[:200]}; pod may still be billing")
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
