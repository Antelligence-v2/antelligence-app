"""W2 harness flags must default to the preregistered behaviour exactly."""
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_benchmark_defaults_are_preregistered():
    b = _load("w2_benchmark")
    assert b.QA_MAX_TOKENS == 512
    assert b.OUT == b.ROOT / "docs/research/slm-vs-frontier-20261008"
    assert b.resolve_out(None) == b.OUT
    assert b.resolve_out("x/y") == b.ROOT / "x/y"
    assert b.variant_name(512) == "prereg"
    assert b.variant_name(2048) == "sens-maxtok2048"
    assert b.RUN["variant"] == "prereg"
    import inspect
    assert inspect.signature(b.run_cell).parameters["max_tokens"].default == 512
    argv = sys.argv
    try:
        sys.argv = ["w2_benchmark.py", "--model", "qwen38-27b-q3k", "--world", "research_qa"]
        captured = {}
        b.asyncio.run = lambda coro: (captured.setdefault("args", coro.cr_frame.f_locals["args"]), coro.close())
        b.main()
    finally:
        sys.argv = argv
    assert captured["args"].max_tokens == 512
    assert captured["args"].out_dir is None


def test_analyze_and_report_default_out_unchanged():
    for name in ("w2_analyze", "w2_report"):
        m = _load(name)
        assert m.OUT == m.DEFAULT_OUT == m.ROOT / "docs/research/slm-vs-frontier-20261008"
