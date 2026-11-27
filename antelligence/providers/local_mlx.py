"""Thin lifecycle manager for one local ``mlx_lm.server`` (macOS), plus a memory-pressure guard.

``mlx_lm.server`` serves one model and cannot unload it, so switching models means stopping the process this
manager started (and only that one), waiting for memory to come back, then starting the next. Process spawning,
HTTP probing and memory probing are injectable so tests never start a real server.
"""

from __future__ import annotations

import re
import subprocess
import time
import urllib.error
import urllib.request
from typing import Callable, List, Optional, Sequence


class LocalModelError(RuntimeError):
    pass


def free_memory_fraction(run: Callable[..., str] | None = None) -> Optional[float]:
    """Fraction of memory the OS reports free, from ``memory_pressure`` or ``vm_stat``; ``None`` if unavailable."""
    def sh(*cmd: str) -> str:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True).stdout

    run = run or sh
    try:
        m = re.search(r"free percentage:\s*(\d+)%", run("memory_pressure"))
        if m:
            return int(m.group(1)) / 100
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        out = run("vm_stat")
        size = int(re.search(r"page size of (\d+) bytes", out).group(1))
        pages = {k: int(v) for k, v in re.findall(r"Pages ([a-z ]+):\s+(\d+)\.", out)}
        total = sum(pages.values())
        return (pages.get("free", 0) + pages.get("inactive", 0)) / total if total and size else None
    except (OSError, subprocess.SubprocessError, AttributeError):
        return None


class LocalModelManager:
    def __init__(self, *, port: int = 11435, server_cmd: Sequence[str] = ("mlx_lm.server",),
                 min_free_fraction: float = 0.15, start_timeout_s: float = 1800.0,
                 popen: Callable[..., "subprocess.Popen"] = subprocess.Popen,
                 probe: Optional[Callable[[str], bool]] = None,
                 memory: Callable[[], Optional[float]] = free_memory_fraction,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> None:
        self.port, self.server_cmd, self.min_free = port, list(server_cmd), min_free_fraction
        self.start_timeout_s = start_timeout_s
        self._popen, self._probe, self._memory, self._sleep, self._clock = popen, probe or self._http_probe, memory, sleep, clock
        self.proc: Optional["subprocess.Popen"] = None
        self.model: Optional[str] = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    @staticmethod
    def _http_probe(base_url: str) -> bool:
        try:
            with urllib.request.urlopen(f"{base_url}/models", timeout=5) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def _check_memory(self) -> None:
        free = self._memory()
        if free is not None and free < self.min_free:
            raise LocalModelError(f"memory pressure: {free:.0%} free < required {self.min_free:.0%}")

    def stop(self) -> None:
        """Stop only the server this manager started."""
        if self.proc is None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.proc, self.model = None, None

    def ensure(self, model: str) -> str:
        """Make ``model`` the served model and return the base URL."""
        if self.model == model and self.proc is not None and self.proc.poll() is None:
            return self.base_url
        self.stop()
        self._check_memory()
        cmd: List[str] = [*self.server_cmd, "--model", model, "--port", str(self.port), "--host", "127.0.0.1"]
        self.proc = self._popen(cmd)
        self.model = model
        deadline = self._clock() + self.start_timeout_s
        while not self._probe(self.base_url):
            if self.proc.poll() is not None:
                self.proc, self.model = None, None
                raise LocalModelError(f"server for {model} exited before answering")
            if self._clock() > deadline:
                self.stop()
                raise LocalModelError(f"server for {model} did not answer within {self.start_timeout_s:.0f}s")
            self._sleep(2.0)
        return self.base_url

    def __enter__(self) -> "LocalModelManager":
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
