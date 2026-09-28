"""Engine HTTP API (local-only by default).

Run with ``uvicorn antelligence.api.app:app --host 127.0.0.1 --port 8002`` or
mount :func:`make_router` into another FastAPI app. Data lives under
``ANTELLIGENCE_ENGINE_DATA`` (read once, when the default app is created).

Every endpoint is bounded: registered rule-policy worlds only, capped arms,
cases and steps. Nothing here calls a model, a chain, or the network.
"""

from __future__ import annotations

import ipaddress
import os
import threading
import uuid
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from antelligence.experiments import registry
from antelligence.experiments.runner import execute_run, experiment_request, run_experiment
from antelligence.experiments.store import EngineStore
from antelligence.kernel.events import EventLogError
from antelligence.provenance.bundle import replay
from antelligence.provenance.outbox import LocalFilePublisher, ProvenanceOutbox

MAX_ARMS = 6
MAX_CASES = 20


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world: str
    arm: str
    case: int = Field(ge=0, le=2**31 - 1)
    params: Dict[str, int] = Field(default_factory=dict)


class ExperimentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world: str
    arms: Optional[List[str]] = Field(default=None, min_length=1, max_length=MAX_ARMS)  # omitted: every arm
    cases: Optional[List[Annotated[int, Field(ge=0, le=2**31 - 1)]]] = Field(default=None, min_length=1,
                                                                             max_length=MAX_CASES)
    baseline: Optional[str] = None
    params: Dict[str, int] = Field(default_factory=dict)
    force: bool = False  # re-run even if a report for this request and engine version exists


def _local_only(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host == "testclient"
    if not loopback:
        raise HTTPException(403, "Engine API is local-only")
    origin = request.headers.get("origin")
    if origin and urlparse(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise HTTPException(403, "Engine API rejects non-local origins")


class EngineService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.store = EngineStore(self.data_dir)
        self.outbox = ProvenanceOutbox(str(self.data_dir / "outbox.sqlite3"))
        self.publisher = LocalFilePublisher(self.data_dir / "bundles")
        self._lock = threading.Lock()  # one CPU-bound run at a time; keeps the host responsive and ordered
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._jobs_lock = threading.Lock()

    def verify(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        # Replays use the same global-state-sensitive worlds as runs, so they share the lock.
        with self._lock:
            return replay(bundle)

    def run(self, body: RunRequest) -> Dict[str, Any]:
        spec = registry.RunSpec(body.world, body.arm, body.case, body.params)
        with self._lock:
            return execute_run(spec, store=self.store, outbox=self.outbox)

    def _request(self, body: ExperimentBody) -> Dict[str, Any]:
        ws = registry.world(body.world)
        return {"world": body.world, "arms": body.arms, "cases": body.cases or list(ws.default_cases)[:MAX_CASES],
                "baseline": body.baseline, "params": body.params}

    def experiment(self, body: ExperimentBody) -> Dict[str, Any]:
        request = self._request(body)
        with self._lock:
            return run_experiment(request, store=self.store, outbox=self.outbox, force=body.force)

    # Background experiments with progress (in-memory job table; local, single process).
    MAX_JOBS = 50

    def start_experiment(self, body: ExperimentBody) -> Dict[str, Any]:
        request = self._request(body)
        # Validate up front so bad requests fail with 422 instead of inside the thread.
        normalized = experiment_request(request["world"], request["arms"], request["cases"],
                                        params=request["params"], baseline=request["baseline"])
        job = {"job_id": uuid.uuid4().hex[:12], "status": "running", "done": 0,
               "total": len(normalized["arms"]) * len(normalized["cases"]), "experiment_id": None, "error": None}
        with self._jobs_lock:
            self._jobs[job["job_id"]] = job
            for old in list(self._jobs)[:-self.MAX_JOBS]:
                del self._jobs[old]

        def progress(done: int, total: int) -> None:
            job["done"], job["total"] = done, total

        def work() -> None:
            try:
                with self._lock:
                    report = run_experiment(request, store=self.store, outbox=self.outbox, force=body.force,
                                            on_progress=progress)
                job.update(status="done", done=job["total"], experiment_id=report["experiment_id"])
            except Exception as exc:  # surfaced to the client via the job
                job.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:500])

        threading.Thread(target=work, name=f"experiment-{job['job_id']}", daemon=True).start()
        return dict(job)

    def job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None


def make_router(service: EngineService) -> APIRouter:
    router = APIRouter(prefix="/engine", dependencies=[Depends(_local_only)])

    @router.get("/health")
    def health() -> Dict[str, Any]:
        return {"ok": True, "worlds": sorted(registry.WORLDS)}

    @router.get("/worlds")
    def worlds() -> List[Dict[str, Any]]:
        return registry.catalog()

    @router.post("/runs", status_code=201)
    async def create_run(body: RunRequest) -> Dict[str, Any]:
        try:
            return await run_in_threadpool(service.run, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        try:
            run = service.store.get_run(run_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if run is None:
            raise HTTPException(404, "run not found")
        return {**run, "outbox": service.outbox.status(run["bundle_hash"])}

    @router.get("/runs/{run_id}/events")
    def get_events(run_id: str, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)) -> Dict[str, Any]:
        try:
            events = service.store.events(run_id, offset, limit)
        except EventLogError as exc:
            raise HTTPException(409, f"stored event log failed its integrity check: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if events is None:
            raise HTTPException(404, "run not found")
        return events

    @router.get("/runs/{run_id}/frames")
    def get_frames(run_id: str) -> Dict[str, Any]:
        try:
            frames = service.store.frames(run_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if frames is None:
            if service.store.get_run(run_id) is None:
                raise HTTPException(404, "run not found")
            raise HTTPException(404, "no frames recorded for this run (non-spatial world, or recorded before frames existed)")
        return frames

    @router.post("/runs/{run_id}/verify")
    async def verify_run(run_id: str) -> Dict[str, Any]:
        run = service.store.get_run(run_id)
        if run is None:
            raise HTTPException(404, "run not found")
        result = await run_in_threadpool(service.verify, run["bundle"])
        if result["reason"] == "spec_unresolvable":
            raise HTTPException(422, f"stored run can no longer be rebuilt: {result.get('detail', '')}")
        return result

    @router.post("/experiments", status_code=201)
    async def create_experiment(body: ExperimentBody) -> Dict[str, Any]:
        try:
            return await run_in_threadpool(service.experiment, body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/experiments/jobs", status_code=202)
    def start_experiment(body: ExperimentBody) -> Dict[str, Any]:
        try:
            return service.start_experiment(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/experiments/jobs/{job_id}")
    def get_job(job_id: str) -> Dict[str, Any]:
        job = service.job(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    @router.get("/experiments")
    def list_experiments(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
        return service.store.list_experiments(limit)

    @router.get("/experiments/{experiment_id}")
    def get_experiment(experiment_id: str) -> Dict[str, Any]:
        report = service.store.get_experiment(experiment_id)
        if report is None:
            raise HTTPException(404, "experiment not found")
        return report

    @router.post("/outbox/drain")
    async def drain_outbox(limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
        return await service.outbox.drain(service.publisher, limit=limit)

    return router


def create_app(data_dir: Optional[Path] = None) -> FastAPI:
    directory = Path(data_dir or os.environ.get("ANTELLIGENCE_ENGINE_DATA", "data/engine"))
    app = FastAPI(title="Antelligence Engine", version="0.1.0")
    app.include_router(make_router(EngineService(directory)))
    return app


def __getattr__(name: str):  # lazy default app so importing this module has no filesystem side effects
    if name == "app":
        return create_app()
    raise AttributeError(name)
