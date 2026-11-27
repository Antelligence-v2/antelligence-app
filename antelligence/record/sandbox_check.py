"""On-disk worker sandbox verification before admitting step 1."""
from __future__ import annotations

import os
from typing import Iterable

_FORBIDDEN_INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules")


class SandboxViolation(Exception):
    pass


def check_worker_sandbox(
    config_dir: str,
    allowed_tools: Iterable[str],
    global_instruction_paths: Iterable[str] = (),
) -> tuple[bool, list[str]]:
    """Verify isolated config_dir, explicit tool allow-list, and zero inherited global instructions."""
    reasons: list[str] = []
    real_cfg = os.path.realpath(config_dir)
    if not os.path.isdir(real_cfg):
        reasons.append(f"config_dir missing or not a directory: {config_dir}")
    home = os.path.realpath(os.path.expanduser("~"))
    forbidden_roots = {home, os.path.realpath(os.sep), os.path.join(home, ".gemini"), os.path.join(home, ".codex"), os.path.join(home, ".claude")}
    if real_cfg in forbidden_roots:
        reasons.append(f"config_dir is not isolated: {real_cfg}")

    tools = list(allowed_tools)
    if not tools or any(not isinstance(t, str) or not t or t == "*" for t in tools):
        reasons.append("allowed_tools must be a non-empty list without wildcard '*'")

    if os.path.isdir(real_cfg):
        for name in _FORBIDDEN_INSTRUCTION_FILES:
            candidate = os.path.join(config_dir, name)
            if os.path.lexists(candidate):
                reasons.append(f"inherited global instruction present in config_dir: {name}")
        global_reals = {os.path.realpath(p) for p in global_instruction_paths}
        for root, _, files in os.walk(config_dir):
            for fname in files:
                fpath = os.path.join(root, fname)
                if os.path.realpath(fpath) in global_reals or fname in _FORBIDDEN_INSTRUCTION_FILES:
                    reasons.append(f"inherited global instruction detected: {fpath}")
    return (len(reasons) == 0), reasons


def verify_worker_sandbox(
    config_dir: str,
    allowed_tools: Iterable[str],
    global_instruction_paths: Iterable[str] = (),
) -> dict[str, object]:
    ok, reasons = check_worker_sandbox(config_dir, allowed_tools, global_instruction_paths)
    if not ok:
        raise SandboxViolation("; ".join(reasons))
    return {"ok": True, "config_dir": os.path.realpath(config_dir), "allowed_tools": list(allowed_tools)}
