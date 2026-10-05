"""Background experiments report progress and end with the same report as the sync endpoint."""

import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from antelligence.api.app import create_app
from antelligence.experiments import run_experiment

BODY = {"world": "foraging", "arms": ["baseline", "hive_memory"], "cases": [101, 102, 103], "params": {"max_steps": 40}}


def wait(client, job_id, timeout=60.0):
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        job = client.get(f"/engine/experiments/jobs/{job_id}").json()
        seen.append(job["done"])
        if job["status"] != "running":
            return job, seen
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_runs_to_completion_with_progress():
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    started = client.post("/engine/experiments/jobs", json=BODY)
    assert started.status_code == 202
    assert started.json()["total"] == 6
    job, seen = wait(client, started.json()["job_id"])
    assert job["status"] == "done" and job["done"] == 6
    assert seen == sorted(seen)  # progress never goes backwards
    report = client.get(f"/engine/experiments/{job['experiment_id']}").json()
    assert set(report["runs"]) == {"baseline", "hive_memory"}


def test_job_report_matches_the_synchronous_endpoint():
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    job, _ = wait(client, client.post("/engine/experiments/jobs", json=BODY).json()["job_id"])
    background = client.get(f"/engine/experiments/{job['experiment_id']}").json()
    direct = run_experiment({**BODY, "baseline": None})
    assert background["comparisons_vs_baseline"] == direct["comparisons_vs_baseline"]


def test_progress_callback_counts_every_run():
    calls = []
    run_experiment({**BODY, "baseline": None}, on_progress=lambda d, t: calls.append((d, t)))
    assert calls == [(i, 6) for i in range(1, 7)]


def test_bad_requests_fail_fast_and_unknown_jobs_404():
    client = TestClient(create_app(Path(tempfile.mkdtemp())))
    assert client.post("/engine/experiments/jobs", json={**BODY, "arms": ["nope"]}).status_code == 422
    assert client.get("/engine/experiments/jobs/missing").status_code == 404
