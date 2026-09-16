"""api_server.py — lightweight FastAPI simulation API.

Endpoints
---------
POST /simulate      Run a simulation; returns run_id + metrics immediately.
GET  /runs/{run_id} Retrieve stored results for a previous run.
GET  /health        Liveness check.

Usage
-----
    uvicorn backend.api_server:app --reload
    # or via pyproject.toml script: antelligence-api
"""

from __future__ import annotations

import hashlib
import json
import sys
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError

# Ensure backend package is importable when running from repo root.
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.config import PheromoneParams, SimulationConfig  # noqa: E402
from backend.run_store import SQLiteRunStore  # noqa: E402
from backend.runtime_factory import run_simulation  # noqa: E402
from chain.proof_adapter import create_proof_bundle  # noqa: E402

# Import simulation model at module level so tests can patch backend.api_server.TumorNanobotModel
try:
    from nanobot_simulation import TumorNanobotModel
except ImportError:
    try:
        from backend.nanobot_simulation import TumorNanobotModel  # type: ignore[no-redef]
    except ImportError:
        TumorNanobotModel = None  # type: ignore[assignment,misc]

app = FastAPI(
    title="Antelligence Simulation API",
    description="REST interface for the nanobot tumor-simulation engine.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Run storage
# ---------------------------------------------------------------------------
_RUNS: Dict[str, Dict[str, Any]] = {}
_DEFAULT_DB_PATH = Path(os.environ.get("ANTELLIGENCE_RUN_DB", Path(_backend_dir).parent / "data" / "api_runs.sqlite3"))
RUN_STORE = SQLiteRunStore(_DEFAULT_DB_PATH)
CONFIG_TRACE_SCHEMA_VERSION = "config-trace-v1"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_bots: int = 10
    grid_size: int = 60
    steps: int = 100
    queen_enabled: bool = False
    seed: Optional[int] = None
    pheromone_params: Optional[PheromoneParams] = None

class SimulateResponse(BaseModel):
    run_id: str
    status: str
    metrics: Dict[str, Any]
    provenance: Dict[str, Any]


class RunResponse(BaseModel):
    run_id: str
    status: str
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    provenance: Optional[Dict[str, Any]] = None


class ConfigTraceResponse(BaseModel):
    run_id: str
    config_trace: Dict[str, Any]
    source_validation: Dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    version: str


def _config_validation_detail(exc: ValidationError) -> list[dict[str, Any]]:
    """Return FastAPI-style validation errors for SimulationConfig failures."""
    detail: list[dict[str, Any]] = []
    for error in exc.errors():
        item = dict(error)
        item["loc"] = ["body", *item.get("loc", ())]
        if "ctx" in item:
            item["ctx"] = {key: str(value) for key, value in item["ctx"].items()}
        detail.append(item)
    return detail


def _provenance_config(cfg: SimulationConfig) -> Dict[str, Any]:
    """Return simulation config normalized for proof/public-value metadata."""
    model_kwargs = cfg.to_model_kwargs()
    config = cfg.model_dump()
    config.update(
        {
            "nanobot_count": cfg.num_bots,
            "tumor_radius": int(model_kwargs["tumor_radius"]),
        }
    )
    return config


def _request_config_hash(config: Dict[str, Any]) -> str:
    """Return a stable hash of the API request config stored for replay."""
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_run_provenance(run_id: str, cfg: SimulationConfig, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Build machine-readable proof/provenance metadata for an API run."""
    config = cfg.model_dump()
    proof_input_config = _provenance_config(cfg)
    proof_metrics = dict(metrics)
    # runtime_factory exposes kill_rate as a [0, 1] fraction; the proof
    # adapter's public contract accepts percentage points before converting
    # them to basis points.
    proof_metrics["kill_rate"] = float(metrics.get("kill_rate", 0.0)) * 100.0
    bundle = create_proof_bundle(proof_input_config, proof_metrics, run_id=run_id)
    config_hash = bundle["onchain"]["simulation_commitments"]["config_hash"]
    request_config_hash = _request_config_hash(config)
    proof_input_config_hash = _request_config_hash(proof_input_config)
    proof_config_hash = bundle["proof_bundle"]["config_hash"]
    onchain_config_hash = bundle["onchain"]["simulation_commitments"]["config_hash"]
    return {
        "run_id": run_id,
        "config": config,
        "request_config_hash": request_config_hash,
        "config_trace": {
            "schema_version": CONFIG_TRACE_SCHEMA_VERSION,
            "stored_run_id": run_id,
            "proof_bundle_run_id": bundle["proof_bundle"]["run_id"],
            "request_config_hash": request_config_hash,
            "stored_config_hash": request_config_hash,
            "proof_input_config_hash": proof_input_config_hash,
            "proof_config_hash": proof_config_hash,
            "onchain_config_hash": onchain_config_hash,
            "config_sources": {
                "request": {
                    "kind": "api_request_config",
                    "path": "provenance.config",
                    "hash": request_config_hash,
                },
                "stored_run": {
                    "kind": "persisted_run_record",
                    "path": f"runs/{run_id}.config",
                    "run_id": run_id,
                    "hash": request_config_hash,
                },
                "proof_input": {
                    "kind": "proof_bundle_input",
                    "path": "provenance.proof_bundle.config_hash",
                    "run_id": bundle["proof_bundle"]["run_id"],
                    "hash": proof_input_config_hash,
                },
                "onchain_commitment": {
                    "kind": "onchain_commitment",
                    "path": "provenance.onchain.simulation_commitments.config_hash",
                    "hash": onchain_config_hash,
                },
            },
            "trace_edges": [
                {
                    "from": "request",
                    "to": "stored_run",
                    "relationship": "persisted_as",
                    "match": True,
                    "from_hash": request_config_hash,
                    "to_hash": request_config_hash,
                },
                {
                    "from": "stored_run",
                    "to": "proof_input",
                    "relationship": "normalized_for_proof",
                    "match": request_config_hash == proof_input_config_hash,
                    "from_hash": request_config_hash,
                    "to_hash": proof_input_config_hash,
                },
                {
                    "from": "proof_input",
                    "to": "onchain_commitment",
                    "relationship": "committed_as",
                    "match": proof_config_hash == onchain_config_hash,
                    "from_hash": proof_config_hash,
                    "to_hash": onchain_config_hash,
                },
            ],
            "request_matches_stored": True,
            "stored_matches_proof_input": request_config_hash == proof_input_config_hash,
            "proof_matches_onchain": proof_config_hash == onchain_config_hash,
        },
        "config_hash": config_hash,
        "trust_tier": bundle["trust_tier"],
        "verification_status": bundle["verification_status"],
        "proof_lifecycle": bundle["proof_lifecycle"],
        "onchain": bundle["onchain"],
        "proof_bundle": bundle["proof_bundle"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    """Return service liveness status."""
    return HealthResponse(status="ok", version=app.version)


@app.post("/simulate", response_model=SimulateResponse, tags=["simulation"])
def simulate(request: SimulateRequest) -> SimulateResponse:
    """Run a simulation synchronously and store the results.

    Returns a ``run_id`` that can later be used with ``GET /runs/{run_id}``.
    """
    # Build a validated config (raises HTTP 422 on bad input automatically).
    pheromone_kwargs = request.pheromone_params or {}
    try:
        cfg = SimulationConfig(
            num_bots=request.num_bots,
            grid_size=request.grid_size,
            steps=request.steps,
            queen_enabled=request.queen_enabled,
            seed=request.seed,
            pheromone_params=pheromone_kwargs,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_config_validation_detail(exc)) from exc

    try:
        _, metrics = run_simulation(cfg, model_factory=TumorNanobotModel)

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={
                "type": "simulation_runtime_error",
                "message": f"Simulation error: {exc}",
            },
        ) from exc

    run_id = str(uuid.uuid4())
    provenance = _build_run_provenance(run_id, cfg, metrics)
    entry = {
        "status": "completed",
        "config": cfg.model_dump(),
        "metrics": metrics,
        "provenance": provenance,
    }
    _RUNS[run_id] = entry
    RUN_STORE.save_run(run_id, entry["status"], entry["config"], entry["metrics"], entry["provenance"])

    return SimulateResponse(run_id=run_id, status="completed", metrics=metrics, provenance=provenance)


@app.get("/runs/{run_id}", response_model=RunResponse, tags=["simulation"])
def get_run(run_id: str) -> RunResponse:
    """Retrieve stored results for a previous simulation run."""
    entry = _RUNS.get(run_id)
    if entry is None:
        persisted = RUN_STORE.get_run(run_id)
        if persisted is not None:
            entry = {
                "status": persisted["status"],
                "config": persisted["config"],
                "metrics": persisted["metrics"],
                "provenance": persisted.get("provenance"),
            }
            _RUNS[run_id] = entry
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "run_not_found",
                "run_id": run_id,
                "message": f"Run '{run_id}' not found.",
            },
        )
    provenance = entry.get("provenance")
    if provenance is None:
        # Rows created before the provenance column existed remain readable,
        # but expose no trust or config-trace claims.
        return RunResponse(
            run_id=run_id,
            status=entry["status"],
            config=entry["config"],
            metrics=entry["metrics"],
            provenance=None,
        )
    required_provenance_fields = {
        "run_id",
        "config",
        "config_hash",
        "trust_tier",
        "verification_status",
        "proof_lifecycle",
        "onchain",
        "proof_bundle",
    }
    missing_fields = sorted(required_provenance_fields - provenance.keys())
    if missing_fields:
        raise HTTPException(
            status_code=500,
            detail={
                "type": "invalid_run_provenance",
                "run_id": run_id,
                "missing_fields": missing_fields,
                "message": "Persisted run provenance is incomplete.",
            },
        )
    return RunResponse(
        run_id=run_id,
        status=entry["status"],
        config=entry["config"],
        metrics=entry["metrics"],
        provenance=provenance,
    )


@app.get("/runs/{run_id}/config-trace", response_model=ConfigTraceResponse, tags=["simulation"])
def get_run_config_trace(run_id: str) -> ConfigTraceResponse:
    """Return the machine-readable request-to-commitment trace for a run."""
    run = get_run(run_id)
    config_trace = (run.provenance or {}).get("config_trace")
    if config_trace is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "config_trace_not_found",
                "run_id": run_id,
                "message": f"Config trace for run '{run_id}' not found.",
            },
        )
    request_source = config_trace.get("config_sources", {}).get("request", {})
    stored_source = config_trace.get("config_sources", {}).get("stored_run", {})
    proof_input_source = config_trace.get("config_sources", {}).get("proof_input", {})
    onchain_source = config_trace.get("config_sources", {}).get("onchain_commitment", {})
    proof_bundle = (run.provenance or {}).get("proof_bundle", {})
    provenance_config = (run.provenance or {}).get("config")
    onchain_config_hash = (
        (run.provenance or {}).get("onchain", {}).get("simulation_commitments", {}).get("config_hash")
    )
    expected_request_path = "provenance.config"
    expected_path = f"runs/{run_id}.config"
    expected_proof_input_path = "provenance.proof_bundle.config_hash"
    expected_onchain_path = "provenance.onchain.simulation_commitments.config_hash"
    request_config_hash = _request_config_hash(run.config)
    trace_edges = config_trace.get("trace_edges")
    expected_trace_edges = [
        {
            "from": "request",
            "to": "stored_run",
            "relationship": "persisted_as",
            "match": True,
            "from_hash": request_config_hash,
            "to_hash": request_config_hash,
        },
        {
            "from": "stored_run",
            "to": "proof_input",
            "relationship": "normalized_for_proof",
            "match": request_config_hash == proof_bundle.get("config_hash"),
            "from_hash": request_config_hash,
            "to_hash": proof_bundle.get("config_hash"),
        },
        {
            "from": "proof_input",
            "to": "onchain_commitment",
            "relationship": "committed_as",
            "match": proof_bundle.get("config_hash") == onchain_config_hash,
            "from_hash": proof_bundle.get("config_hash"),
            "to_hash": onchain_config_hash,
        },
    ]
    source_validation = {
        "request": {
            "kind": request_source.get("kind"),
            "kind_matches_source": request_source.get("kind") == "api_request_config",
            "path": request_source.get("path"),
            "path_matches_config": request_source.get("path") == expected_request_path,
            "config_matches_stored_run": provenance_config == run.config,
            "hash_matches_config": request_source.get("hash") == request_config_hash,
            "hash": request_config_hash,
        },
        "stored_run": {
            "kind": stored_source.get("kind"),
            "kind_matches_source": stored_source.get("kind") == "persisted_run_record",
            "path": stored_source.get("path"),
            "path_matches_run": stored_source.get("path") == expected_path,
            "hash_matches_stored_config": stored_source.get("hash") == _request_config_hash(run.config),
        },
        "proof_input": {
            "kind": proof_input_source.get("kind"),
            "kind_matches_source": proof_input_source.get("kind") == "proof_bundle_input",
            "path": proof_input_source.get("path"),
            "path_matches_proof_bundle": proof_input_source.get("path") == expected_proof_input_path,
            "run_id": proof_input_source.get("run_id"),
            "run_id_matches_run": proof_input_source.get("run_id") == run_id,
            "hash_matches_proof_bundle": proof_input_source.get("hash") == proof_bundle.get("config_hash"),
        },
        "onchain_commitment": {
            "kind": onchain_source.get("kind"),
            "kind_matches_source": onchain_source.get("kind") == "onchain_commitment",
            "path": onchain_source.get("path"),
            "path_matches_commitment": onchain_source.get("path") == expected_onchain_path,
            "hash": onchain_config_hash,
            "hash_matches_proof_bundle": (
                onchain_source.get("hash") == onchain_config_hash == proof_bundle.get("config_hash")
            ),
        },
        "trace_summary": {
            "schema_version": config_trace.get("schema_version"),
            "schema_version_supported": config_trace.get("schema_version") == CONFIG_TRACE_SCHEMA_VERSION,
            "stored_run_id": config_trace.get("stored_run_id"),
            "stored_run_id_matches_run": config_trace.get("stored_run_id") == run_id,
            "proof_bundle_run_id": config_trace.get("proof_bundle_run_id"),
            "proof_bundle_run_id_matches_bundle": (
                config_trace.get("proof_bundle_run_id") == proof_bundle.get("run_id") == run_id
            ),
            "request_config_hash_matches_config": (
                config_trace.get("request_config_hash") == request_config_hash
            ),
            "stored_config_hash_matches_config": (
                config_trace.get("stored_config_hash") == request_config_hash
            ),
            "proof_input_config_hash_matches_bundle": (
                config_trace.get("proof_input_config_hash") == proof_bundle.get("config_hash")
            ),
            "proof_config_hash_matches_bundle": (
                config_trace.get("proof_config_hash") == proof_bundle.get("config_hash")
            ),
            "onchain_config_hash_matches_commitment": (
                config_trace.get("onchain_config_hash") == onchain_config_hash
            ),
        },
        "trace_edges": {
            "edge_count": len(trace_edges) if isinstance(trace_edges, list) else 0,
            "expected_edge_count": len(expected_trace_edges),
            "edges_match_expected": trace_edges == expected_trace_edges,
        },
    }
    validation_checks = {
        "request": (
            source_validation["request"]["kind_matches_source"],
            source_validation["request"]["path_matches_config"],
            source_validation["request"]["config_matches_stored_run"],
            source_validation["request"]["hash_matches_config"],
        ),
        "stored_run": (
            source_validation["stored_run"]["kind_matches_source"],
            source_validation["stored_run"]["path_matches_run"],
            source_validation["stored_run"]["hash_matches_stored_config"],
        ),
        "proof_input": (
            source_validation["proof_input"]["kind_matches_source"],
            source_validation["proof_input"]["path_matches_proof_bundle"],
            source_validation["proof_input"]["run_id_matches_run"],
            source_validation["proof_input"]["hash_matches_proof_bundle"],
        ),
        "onchain_commitment": (
            source_validation["onchain_commitment"]["kind_matches_source"],
            source_validation["onchain_commitment"]["path_matches_commitment"],
            source_validation["onchain_commitment"]["hash_matches_proof_bundle"],
        ),
        "trace_summary": (
            source_validation["trace_summary"]["schema_version_supported"],
            source_validation["trace_summary"]["stored_run_id_matches_run"],
            source_validation["trace_summary"]["proof_bundle_run_id_matches_bundle"],
            source_validation["trace_summary"]["request_config_hash_matches_config"],
            source_validation["trace_summary"]["stored_config_hash_matches_config"],
            source_validation["trace_summary"]["proof_input_config_hash_matches_bundle"],
            source_validation["trace_summary"]["proof_config_hash_matches_bundle"],
            source_validation["trace_summary"]["onchain_config_hash_matches_commitment"],
        ),
        "trace_edges": (source_validation["trace_edges"]["edges_match_expected"],),
    }
    source_validation["invalid_sources"] = [
        source_name for source_name, checks in validation_checks.items() if not all(checks)
    ]
    source_validation["all_sources_valid"] = not source_validation["invalid_sources"]
    return ConfigTraceResponse(
        run_id=run_id,
        config_trace=config_trace,
        source_validation=source_validation,
    )


# ---------------------------------------------------------------------------
# Entry-point for pyproject.toml script
# ---------------------------------------------------------------------------


def main() -> None:
    import uvicorn

    uvicorn.run("backend.api_server:app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
    main()
