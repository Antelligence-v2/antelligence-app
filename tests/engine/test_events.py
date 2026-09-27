import json

import pytest

from antelligence.kernel.events import GENESIS, EventLog, EventLogError


def build():
    log = EventLog()
    log.append("run_started", 0, {"seed": 1})
    log.append("outcome", 1, {"accepted": True}, agent_id="a0")
    log.append("run_finished", 1, {"metrics": {"x": 1}})
    return log


def test_hash_chain_is_deterministic_and_order_sensitive():
    assert build().trace_hash == build().trace_hash
    assert EventLog().trace_hash == GENESIS
    other = EventLog()
    other.append("outcome", 1, {"accepted": True}, agent_id="a0")
    other.append("run_started", 0, {"seed": 1})
    other.append("run_finished", 1, {"metrics": {"x": 1}})
    assert other.trace_hash != build().trace_hash


def test_data_is_detached():
    log = EventLog()
    data = {"v": [1]}
    log.append("x", 0, data)
    data["v"].append(2)
    assert list(log)[0].data == {"v": [1]}


def test_sink_receives_events():
    seen = []
    log = EventLog(sink=seen.append)
    log.append("x", 0, {})
    assert [e.type for e in seen] == ["x"]


def test_jsonl_roundtrip_verifies(tmp_path):
    path = tmp_path / "events.jsonl"
    log = build()
    log.write_jsonl(path)
    loaded = EventLog.read_jsonl(path)
    assert loaded.trace_hash == log.trace_hash and len(loaded) == 3


@pytest.mark.parametrize("mutation", ["edit", "drop", "swap"])
def test_jsonl_tampering_is_detected(tmp_path, mutation):
    path = tmp_path / "events.jsonl"
    build().write_jsonl(path)
    lines = path.read_text().splitlines()
    if mutation == "edit":
        row = json.loads(lines[1])
        row["data"]["accepted"] = False
        lines[1] = json.dumps(row)
    elif mutation == "drop":
        del lines[1]
    else:
        lines[0], lines[1] = lines[1], lines[0]
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(EventLogError):
        EventLog.read_jsonl(path)
