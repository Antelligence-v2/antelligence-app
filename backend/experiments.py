"""Durable, bounded Experiment Lab orchestration over the tumor runner."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

try:  # Reuse the schema module selected by the frontend API entry point.
    from schemas import TumorSimulationConfig
    from backend.tumor_runs import canonical_config_hash
except ImportError:  # pragma: no cover - direct package imports.
    from .schemas import TumorSimulationConfig
    from .tumor_runs import canonical_config_hash


ARM_ORDER = ("no_bots", "fixed", "pheromone")
LIMITATIONS = [
    "Synthetic 2D geometry, not patient data.",
    "Short simulated exposure; inspect each case's simulated duration.",
    "Toxicity is not modeled.",
    "Descriptive small sample; no clinical efficacy or statistical superiority claim.",
    "Local deterministic replay is not cryptographic verification.",
]


class ExperimentRequest(BaseModel):
    """The intentionally narrow public request for an experiment batch."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    seeds: list[StrictInt] = Field(min_length=1, max_length=5)
    config: TumorSimulationConfig

    @model_validator(mode="after")
    def validate_bounded_local_policy(self) -> "ExperimentRequest":
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")
        if any(seed < 0 or seed > 4294967295 for seed in self.seeds):
            raise ValueError("seeds must be unsigned 32-bit integers")

        config = self.config
        if config.agent_type != "Rule-Based":
            raise ValueError("experiments require explicit Rule-Based workers")
        if not config.offline:
            raise ValueError("experiments require offline=true")
        if config.use_queen or config.use_llm_queen:
            raise ValueError("experiments do not support a Queen")
        if config.use_brats_geometry or config.brats_patient_id is not None:
            raise ValueError("experiments require synthetic geometry")
        if config.n_nanobots < 1 or config.n_nanobots > 25:
            raise ValueError("experiment nanobot count must be between 1 and 25")
        if config.max_steps > 200:
            raise ValueError("experiment steps must be <= 200")
        if config.domain_size > 1000:
            raise ValueError("experiment domain_size must be <= 1000")

        grid_intervals = config.domain_size / config.voxel_size
        if grid_intervals > 30:
            raise ValueError("experiment grid intervals must be <= 30")

        # The runtime creates an annular 2D tumor (the central quarter is
        # necrotic), so this is the allocation estimate used by the guard.
        expected_cells = _expected_cells(config)
        if expected_cells > 100:
            raise ValueError("experiment expected cells must be <= 100")
        aggregate_work = expected_cells * config.max_steps * len(self.seeds) * 3
        if aggregate_work > 100000:
            raise ValueError("experiment workload exceeds the bounded local budget")
        return self


def _expected_cells(config: TumorSimulationConfig) -> int:
    annulus_area = math.pi * (config.tumor_radius**2 - (config.tumor_radius * 0.25) ** 2)
    return max(0, math.ceil(annulus_area * config.cell_density))


def _dump(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return json.loads(json.dumps(value))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value.dict()


def canonical_trace_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return only actual deterministic run material used by replay."""
    return {
        "config": result["config"],
        "history": result["history"],
        "final_metrics": result["final_metrics"],
        "tumor_statistics": result["tumor_statistics"],
        "total_time": result["total_time"],
    }


def trace_hash(result: Dict[str, Any]) -> str:
    canonical = json.dumps(
        canonical_trace_payload(result),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ExperimentStore:
    """SQLite document store for the experiment library and replay checks."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, document: Dict[str, Any]) -> None:
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"))
        request_json = json.dumps(document["request"], sort_keys=True, separators=(",", ":"))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO experiments
                    (experiment_id, name, created_at, status, request_json, response_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    name=excluded.name,
                    created_at=excluded.created_at,
                    status=excluded.status,
                    request_json=excluded.request_json,
                    response_json=excluded.response_json
                """,
                (
                    document["experiment_id"],
                    document["name"],
                    document["created_at"],
                    document["status"],
                    request_json,
                    encoded,
                ),
            )
            conn.commit()

    def get(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT response_json FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, *, limit: int = 50, offset: int = 0) -> tuple[list[Dict[str, Any]], bool]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT experiment_id, name, created_at, status, response_json
                FROM experiments
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (limit + 1, offset),
            ).fetchall()
        has_more = len(rows) > limit
        summaries = []
        for experiment_id, name, created_at, status, encoded in rows[:limit]:
            document = json.loads(encoded)
            summaries.append(
                {
                    "experiment_id": experiment_id,
                    "name": name,
                    "created_at": created_at,
                    "status": status,
                    "case_count": len(document.get("cases", [])),
                    "seed_count": len(document.get("request", {}).get("seeds", [])),
                }
            )
        return summaries, has_more


class ExperimentNotFound(LookupError):
    pass


class ExperimentCaseNotFound(LookupError):
    pass


class ExperimentFailure(RuntimeError):
    def __init__(self, status_code: int, detail: Dict[str, Any], experiment_id: str):
        super().__init__(detail.get("message", "experiment failed"))
        self.status_code = status_code
        self.detail = detail
        self.experiment_id = experiment_id


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_document(request: ExperimentRequest) -> Dict[str, Any]:
    document = {
        "experiment_id": str(uuid.uuid4()),
        "name": request.name,
        "created_at": _now(),
        "status": "partial",
        "request": _dump(request),
        "case_count": 0,
        "seed_count": len(request.seeds),
        "matched_initial_geometry": None,
        "cases": [],
        "summary": [],
        "replay_checks": [],
        "limitations": LIMITATIONS,
    }
    return document


def _arm_config(request: ExperimentRequest, arm: str, seed: int) -> TumorSimulationConfig:
    if arm not in ARM_ORDER:
        raise ValueError(f"unknown experiment arm: {arm}")
    return request.config.model_copy(
        update={
            "seed": seed,
            "n_nanobots": 0 if arm == "no_bots" else request.config.n_nanobots,
            "pheromones_enabled": arm == "pheromone",
        }
    )


def _case_from_result(
    *, request: ExperimentRequest, arm: str, seed: int, result: Any, runtime_seconds: float
) -> Dict[str, Any]:
    data = _dump(result)
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError("tumor runner returned no executed config")
    expected = _dump(_arm_config(request, arm, seed))
    if config != expected:
        raise ValueError("tumor runner did not return the requested arm configuration")
    if data.get("config_hash") != canonical_config_hash(config):
        raise ValueError("tumor runner returned an invalid config hash")
    if not data.get("initial_geometry_hash"):
        raise ValueError("tumor runner returned no initial geometry hash")
    if data.get("proof_ok") is not False:
        raise ValueError("experiment runs must retain proof_ok=false")
    stats = data["tumor_statistics"]
    metrics = data["final_metrics"]
    initial = int(stats["initial_living_cells"])
    final = int(stats["final_living_cells"])
    if initial <= 0:
        raise ValueError("Initial living-cell population is empty; reduction is unmeasured.")
    reduction = 100.0 * (initial - final) / initial
    return {
        "case_id": f"{arm}:{seed}",
        "arm": arm,
        "seed": seed,
        "run_id": data["run_id"],
        "config_hash": data["config_hash"],
        "initial_geometry_hash": data.get("initial_geometry_hash", ""),
        "trace_hash": trace_hash(data),
        "config": config,
        "initial_living_cells": initial,
        "final_living_cells": final,
        "net_cell_reduction_pct": reduction,
        "deliveries": int(metrics["total_deliveries"]),
        "drug_delivered": float(metrics["total_drug_delivered"]),
        "simulation_minutes": float(data["total_time"]),
        "runtime_seconds": float(runtime_seconds),
    }


def _mean(values: Iterable[float]) -> Optional[float]:
    values = list(values)
    return statistics.fmean(values) if values else None


def _paired_delta(cases: list[Dict[str, Any]], baseline: Dict[int, Dict[str, Any]]) -> Optional[float]:
    deltas = []
    for case in cases:
        other = baseline.get(case["seed"])
        if other is None or case["net_cell_reduction_pct"] is None or other["net_cell_reduction_pct"] is None:
            continue
        deltas.append(case["net_cell_reduction_pct"] - other["net_cell_reduction_pct"])
    return _mean(deltas)


def build_summary(cases: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    by_arm = {arm: [case for case in cases if case["arm"] == arm] for arm in ARM_ORDER}
    by_seed = {
        arm: {case["seed"]: case for case in arm_cases}
        for arm, arm_cases in by_arm.items()
    }
    summary = []
    for arm in ARM_ORDER:
        arm_cases = by_arm[arm]
        reductions = [case["net_cell_reduction_pct"] for case in arm_cases if case["net_cell_reduction_pct"] is not None]
        deliveries = [case["deliveries"] for case in arm_cases]
        drug = [case["drug_delivered"] for case in arm_cases]
        summary.append(
            {
                "arm": arm,
                "seed_count": len(arm_cases),
                "net_cell_reduction_pct_mean": _mean(reductions),
                "net_cell_reduction_pct_std": statistics.stdev(reductions) if len(reductions) >= 2 else None,
                "deliveries_mean": _mean(deliveries),
                "drug_delivered_mean": _mean(drug),
                "vs_no_bots_pp": _paired_delta(arm_cases, by_seed["no_bots"]),
                "vs_fixed_pp": _paired_delta(arm_cases, by_seed["fixed"]),
            }
        )
    return summary


def _refresh_document(document: Dict[str, Any]) -> None:
    cases = document.get("cases", [])
    document["case_count"] = len(cases)
    document["summary"] = build_summary(cases)
    grouped = {}
    for case in cases:
        grouped.setdefault(case["seed"], []).append(case.get("initial_geometry_hash", ""))
    required_seeds = document["request"]["seeds"]
    complete = len(cases) == len(required_seeds) * len(ARM_ORDER) and set(grouped) == set(required_seeds)
    document["matched_initial_geometry"] = (
        all(len(values) == len(ARM_ORDER) and bool(values[0]) and len(set(values)) == 1 for values in grouped.values())
        if complete else None
    )


Runner = Callable[[TumorSimulationConfig], Awaitable[Any]]


async def execute_experiment(
    request: ExperimentRequest, *, runner: Runner, store: ExperimentStore
) -> Dict[str, Any]:
    document = _new_document(request)
    store.save(document)
    try:
        for seed in request.seeds:
            for arm in ARM_ORDER:
                started = time.perf_counter()
                result = await runner(_arm_config(request, arm, seed))
                document["cases"].append(
                    _case_from_result(
                        request=request,
                        arm=arm,
                        seed=seed,
                        result=result,
                        runtime_seconds=time.perf_counter() - started,
                    )
                )
                _refresh_document(document)
                store.save(document)
        _refresh_document(document)
        if document["matched_initial_geometry"] is not True:
            raise ValueError("Initial geometries do not match across arms.")
        document["status"] = "completed"
        store.save(document)
        return document
    except Exception as exc:
        document["status"] = "failed"
        document["error"] = str(getattr(exc, "detail", exc))
        _refresh_document(document)
        store.save(document)
        status_code = int(getattr(exc, "status_code", 500))
        raw_detail = getattr(exc, "detail", None)
        if isinstance(raw_detail, dict):
            detail = dict(raw_detail)
        else:
            detail = {"type": "experiment_failed", "message": str(exc)}
        detail.setdefault("type", "experiment_failed")
        detail.setdefault("message", str(exc))
        detail["experiment_id"] = document["experiment_id"]
        raise ExperimentFailure(status_code, detail, document["experiment_id"]) from exc


def _replay_check(
    *, experiment_id: str, case_id: str, status: str, expected: str, actual: str,
    replay_run_id: str, message: str
) -> Dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "case_id": case_id,
        "status": status,
        "expected_trace_hash": expected,
        "actual_trace_hash": actual,
        "replay_run_id": replay_run_id,
        "checked_at": _now(),
        "message": message,
    }


async def replay_experiment_case(
    experiment_id: str,
    case_id: str,
    *,
    runner: Runner,
    store: ExperimentStore,
    tumor_store: Any,
) -> Dict[str, Any]:
    document = store.get(experiment_id)
    if document is None:
        raise ExperimentNotFound(experiment_id)
    case = next((candidate for candidate in document.get("cases", []) if candidate.get("case_id") == case_id), None)
    if case is None:
        raise ExperimentCaseNotFound(case_id)

    expected = str(case.get("trace_hash", ""))
    actual = ""
    replay_run_id = ""
    stored = tumor_store.get(str(case.get("run_id", "")))
    original = stored.get("result") if stored else None
    try:
        if not isinstance(original, dict):
            raise ValueError("stored tumor run snapshot is missing")
        original_config = original.get("config")
        if (
            not isinstance(original_config, dict)
            or original_config != case.get("config")
            or canonical_config_hash(original_config) != case.get("config_hash")
            or original.get("config_hash") != case.get("config_hash")
            or original.get("initial_geometry_hash") != case.get("initial_geometry_hash")
        ):
            raise ValueError("stored experiment case binding is corrupted")
        stored_trace = trace_hash(original)
        actual = stored_trace
        if stored_trace != expected:
            raise ValueError("stored experiment trace binding is corrupted")
    except Exception as exc:
        check = _replay_check(
            experiment_id=experiment_id,
            case_id=case_id,
            status="error",
            expected=expected,
            actual=actual,
            replay_run_id="",
            message=str(exc),
        )
        document.setdefault("replay_checks", []).append(check)
        store.save(document)
        return check

    try:
        result = await runner(TumorSimulationConfig(**case["config"]))
        data = _dump(result)
        actual = trace_hash(data)
        replay_run_id = str(data.get("run_id", ""))
        if data.get("proof_ok") is not False:
            raise ValueError("replay run did not retain proof_ok=false")
        status = "matched" if actual == expected else "mismatch"
        message = "Replay matched the recorded deterministic trace." if status == "matched" else "Replay trace differs from the recorded trace."
    except Exception as exc:
        status = "error"
        message = str(exc)

    check = _replay_check(
        experiment_id=experiment_id,
        case_id=case_id,
        status=status,
        expected=expected,
        actual=actual,
        replay_run_id=replay_run_id,
        message=message,
    )
    document.setdefault("replay_checks", []).append(check)
    store.save(document)
    return check
