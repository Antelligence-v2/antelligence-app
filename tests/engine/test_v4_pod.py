"""scripts/v4_pod.py: payloads, budget refusal, cost rows vs v4_budget, one-pod rule, secrecy. No network."""
import json
import stat
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from antelligence.experiments import v4_budget as budget
from scripts import v4_pod as pod

KEY = "rp-test-key-NOT-REAL"


class FakeRunPod:
    """MockTransport handler holding a tiny RunPod: quote, create, get, delete."""

    def __init__(self, rate=0.86, create_ok=("NVIDIA L40S", "NVIDIA A40"), alive=True):
        self.rate, self.create_ok, self.alive = rate, create_ok, alive
        self.calls = []
        self.created = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        assert request.headers["authorization"] == f"Bearer {KEY}"
        if request.url.host == "api.runpod.io":
            return httpx.Response(200, json={"data": {"gpuTypes": [{"securePrice": self.rate}]}})
        if request.method == "POST":
            body = json.loads(request.content)
            self.created.append(body)
            if body["gpuTypeIds"][0] not in self.create_ok:
                return httpx.Response(500, json={"error": "no capacity"})
            return httpx.Response(201, json={"id": "pod123", "costPerHr": self.rate})
        if request.method == "GET":
            return httpx.Response(200, json={"desiredStatus": "RUNNING"}) if self.alive else httpx.Response(404)
        self.alive = False
        return httpx.Response(204)


@pytest.fixture
def paths(tmp_path):
    return pod.Paths(state=tmp_path / "state.json", costs=tmp_path / "costs.jsonl")


def run(argv, paths, fake, out):
    return pod.main(argv, paths=paths, transport=httpx.MockTransport(fake), api_key=KEY, sleep=lambda s: None,
                    echo=out.append)


def test_models_pinned():
    assert set(pod.MODELS) == {"qwen3.5-0.8b", "qwen3.5-4b", "qwen3.5-9b", "qwen3.5-27b", "qwen3.8-27b"}
    assert pod.VLLM_IMAGE == "vllm/vllm-openai:v0.30.0" and pod.GPU_TYPES == ("NVIDIA L40S", "NVIDIA A40")
    for key, spec in pod.MODELS.items():
        args = pod.vllm_args(key)
        assert args[0] == spec["hf"] == args[args.index("--served-model-name") + 1]
        assert args[args.index("--revision") + 1] == spec["revision"] and len(spec["revision"]) == 40
        assert args[args.index("--gpu-memory-utilization") + 1] == "0.92"
        assert args[args.index("--seed") + 1] == "0"
        assert ("--max-num-seqs" in args) == key.endswith("27b")
        if key.endswith("27b"):
            assert args[args.index("--max-num-seqs") + 1] == "64"


def test_payload_pins_image_and_revision_per_model():
    for key, spec in pod.MODELS.items():
        body = pod.deploy_payload(key, "s3cret", "NVIDIA L40S", "tok")
        assert body["imageName"] == "vllm/vllm-openai:v0.30.0" and body["gpuTypeIds"] == ["NVIDIA L40S"]
        assert body["env"] == {"VLLM_API_KEY": "s3cret"} and body["gpuCount"] == 1
        cmd = body["dockerStartCmd"][0]
        assert f"--revision {spec['revision']}" in cmd and spec["hf"] in cmd
        assert ("--max-num-seqs 64" in cmd) == key.endswith("27b")
        assert "s3cret" not in cmd  # the secret reaches vLLM only via env


def test_budget_refusal_pure():
    assert pod.refuse_over_budget(0.0, 0.86) is None
    assert pod.refuse_over_budget(1.89, 0.86) is None  # exactly at the stop is allowed
    assert pod.refuse_over_budget(1.90, 0.86) is not None


def test_up_refuses_over_budget_without_creating(paths):
    now = datetime.now(timezone.utc)
    for ev, t in (("start", now - timedelta(hours=4)), ("stop", now)):
        pod.append_cost(paths.costs, pod.cost_row(ev, "old", 0.6, t.isoformat()))  # $2.40 spent
    fake, out = FakeRunPod(rate=0.86), []
    assert run(["up", "qwen3.5-9b"], paths, fake, out) == 1
    assert any("budget" in line for line in out)
    assert fake.created == [] and not paths.state.exists()


def test_up_down_rows_round_trip_with_v4_budget(paths):
    fake, out = FakeRunPod(), []
    assert run(["up", "qwen3.5-9b"], paths, fake, out) == 0
    rows = budget.read_jsonl(paths.costs)
    assert len(rows) == 1 and set(rows[0]) == {"event", "pod_id", "utc", "rate_per_hr"}
    assert rows[0]["event"] == "start" and rows[0]["pod_id"] == "pod123" and rows[0]["rate_per_hr"] == 0.86
    # unstopped pod bills to now: 2 hours later it is $1.72
    later = datetime.fromisoformat(rows[0]["utc"]) + timedelta(hours=2)
    assert budget.pod_spend(rows, later) == pytest.approx(1.72)
    assert run(["down"], paths, fake, out) == 0
    rows = budget.read_jsonl(paths.costs)
    assert [r["event"] for r in rows] == ["start", "stop"] and not paths.state.exists()
    assert pod.spend_so_far(paths.costs) == pytest.approx(budget.pod_spend(rows), abs=1e-6)
    # a known interval prices exactly through the budget module
    one_hour = [pod.cost_row("start", "p", 0.9, "2026-10-12T00:00:00+00:00"),
                pod.cost_row("stop", "p", 0.9, "2026-10-12T01:00:00+00:00")]
    assert budget.pod_spend(one_hour) == pytest.approx(0.9)


def test_one_pod_at_a_time(paths):
    fake, out = FakeRunPod(), []
    assert run(["up", "qwen3.5-4b"], paths, fake, out) == 0
    n_created = len(fake.created)
    assert run(["up", "qwen3.5-9b"], paths, fake, out) == 1
    assert len(fake.created) == n_created and "one pod at a time" in out[-1]


def test_stale_state_is_closed_and_replaced(paths):
    fake, out = FakeRunPod(), []
    run(["up", "qwen3.5-4b"], paths, fake, out)
    fake.alive = False  # pod vanished
    assert run(["up", "qwen3.5-9b"], paths, fake, out) == 0
    events = [r["event"] for r in budget.read_jsonl(paths.costs)]
    assert events == ["start", "stop", "start"]
    assert pod.load_state(paths.state)["model"] == "qwen3.5-9b"


def test_gpu_fallback(paths):
    fake, out = FakeRunPod(create_ok=("NVIDIA A40",)), []
    assert run(["up", "qwen3.5-0.8b"], paths, fake, out) == 0
    assert [b["gpuTypeIds"] for b in fake.created] == [["NVIDIA L40S"], ["NVIDIA A40"]]
    assert pod.load_state(paths.state)["gpu"] == "NVIDIA A40"


def test_secret_never_printed_or_in_cost_rows(paths, capsys):
    fake, out = FakeRunPod(), []
    run(["up", "qwen3.5-9b"], paths, fake, out)
    run(["status"], paths, fake, out)
    run(["cost"], paths, fake, out)
    run(["down"], paths, fake, out)
    state_secret = fake.created[0]["env"]["VLLM_API_KEY"]
    log_token = fake.created[0]["dockerStartCmd"][0].split("mkdir -p /srv/")[1].split("/")[0]
    shown = "\n".join(out) + capsys.readouterr().out + paths.costs.read_text()
    assert state_secret not in shown and log_token not in shown and KEY not in shown


def test_state_file_is_private_and_holds_secret(paths):
    run(["up", "qwen3.5-9b"], paths, FakeRunPod(), [])
    assert stat.S_IMODE(paths.state.stat().st_mode) == 0o600
    state = pod.load_state(paths.state)
    assert len(state["api_secret"]) >= 32 and "api_secret" not in pod.public_view(state)


def test_wait_until_expected_name_served(paths):
    run(["up", "qwen3.5-9b"], paths, FakeRunPod(), [])
    state = pod.load_state(paths.state)
    seen = []

    def handler(request):
        assert request.headers["authorization"] == f"Bearer {state['api_secret']}"
        seen.append(1)
        if len(seen) == 1:
            raise httpx.ConnectError("booting")
        if len(seen) == 2:
            return httpx.Response(200, json={"data": [{"id": "other/model"}]})
        return httpx.Response(200, json={"data": [{"id": "Qwen/Qwen3.5-9B"}]})

    out = []
    assert pod.cmd_wait(paths, out.append, httpx.MockTransport(handler), lambda s: None) == 0
    assert len(seen) == 3 and out[0] == "ready: serving Qwen/Qwen3.5-9B"


def test_wait_times_out(paths):
    run(["up", "qwen3.5-9b"], paths, FakeRunPod(), [])
    handler = httpx.MockTransport(lambda r: httpx.Response(503))
    assert pod.cmd_wait(paths, lambda s: None, handler, lambda s: None, timeout_s=0) == 1


def test_down_failure_keeps_state_and_no_stop_row(paths):
    class Stuck(FakeRunPod):
        def __call__(self, request):
            if request.method == "DELETE":
                return httpx.Response(500)
            return super().__call__(request)

    out = []
    run(["up", "qwen3.5-9b"], paths, Stuck(), out)
    assert run(["down"], paths, Stuck(), out) == 1
    assert paths.state.exists() and [r["event"] for r in budget.read_jsonl(paths.costs)] == ["start"]


def test_cost_line(paths):
    out = []
    run(["cost"], paths, FakeRunPod(), out)
    assert out == ["runpod spend $0.000 of $2.75 hard stop ($2.750 left)"]


def test_no_live_call_without_key_file_in_tests():
    with pytest.raises(SystemExit):
        pod.main(["up", "not-a-model"], api_key=KEY)  # argparse rejects before any client exists
