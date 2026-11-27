"""CLI for Antelligence Harness vNext (`antelligence-harness`).

Subcommands:
* ``snapshot``: write ``studies/<date>-<slug>/manifest.lock.json`` capturing git state, environment, and dataset hashes.
* ``score``: summarize an :class:`~antelligence.harness.scorecard.OutcomeLog` JSONL file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from antelligence.harness.scorecard import OutcomeLog, pareto, summary


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_info(cwd: Path) -> Dict[str, Any]:
    def _run(args: Sequence[str]) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", *args],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return res.stdout.strip() if res.returncode == 0 else None
        except OSError:
            return None

    commit = _run(["rev-parse", "HEAD"])
    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    status = _run(["status", "--porcelain"])
    return {
        "commit": commit,
        "branch": branch,
        "dirty": bool(status) if status is not None else None,
    }


def _pkg_versions(names: Iterable[str]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for name in names:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            out[name] = None
    return out


def build_manifest(
    slug: str,
    *,
    study_date: Optional[str] = None,
    inputs: Sequence[Path] = (),
    cutoff_at: Optional[str] = None,
    notes: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Construct a reproducible ``manifest.lock.json`` payload for a study."""
    date_str = study_date or dt.date.today().isoformat()
    root = repo_root or Path.cwd()
    file_hashes = {}
    for p in inputs:
        path = Path(p)
        file_hashes[str(path)] = _sha256_file(path) if path.is_file() else None
    return {
        "schema_version": "1.0",
        "study": {"date": date_str, "slug": slug, "cutoff_at": cutoff_at, "notes": notes},
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "git": _git_info(root),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": _pkg_versions(("antelligence", "numpy", "pydantic", "httpx")),
        },
        "inputs": file_hashes,
        "extra": dict(extra or {}),
    }


def write_manifest(
    slug: str,
    *,
    studies_dir: Path = Path("studies"),
    study_date: Optional[str] = None,
    inputs: Sequence[Path] = (),
    cutoff_at: Optional[str] = None,
    notes: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
    repo_root: Optional[Path] = None,
) -> Path:
    """Write ``studies/<date>-<slug>/manifest.lock.json`` and return its path."""
    manifest = build_manifest(
        slug,
        study_date=study_date,
        inputs=inputs,
        cutoff_at=cutoff_at,
        notes=notes,
        extra=extra,
        repo_root=repo_root,
    )
    date_str = manifest["study"]["date"]
    out_path = Path(studies_dir) / f"{date_str}-{slug}" / "manifest.lock.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def cmd_snapshot(args: argparse.Namespace) -> int:
    out_path = write_manifest(
        args.slug,
        studies_dir=Path(args.studies_dir),
        study_date=args.date,
        inputs=[Path(p) for p in args.inputs],
        cutoff_at=args.cutoff_at,
        notes=args.notes,
    )
    print(json.dumps({"manifest": str(out_path)}))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    outcomes = OutcomeLog(Path(args.log)).read()
    table = summary(outcomes, baseline=args.baseline)
    print(json.dumps({"summary": table, "pareto": pareto(table)}, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antelligence-harness", description="Antelligence Harness vNext CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_snap = sub.add_parser("snapshot", help="Write studies/<date>-<slug>/manifest.lock.json")
    p_snap.add_argument("slug", help="Short study slug (e.g. 'triage-v1')")
    p_snap.add_argument("--date", default=None, help="ISO date YYYY-MM-DD (default: today)")
    p_snap.add_argument("--studies-dir", default="studies", help="Base studies directory (default: studies)")
    p_snap.add_argument("--input", dest="inputs", action="append", default=[], help="Input file to SHA-256 hash")
    p_snap.add_argument("--cutoff-at", default=None, help="Dataset cutoff ISO timestamp")
    p_snap.add_argument("--notes", default=None, help="Optional study notes")
    p_snap.set_defaults(func=cmd_snapshot)

    p_score = sub.add_parser("score", help="Summarize an outcome JSONL log")
    p_score.add_argument("log", help="Path to outcome JSONL file")
    p_score.add_argument("--baseline", default="baseline", help="Baseline variant name (default: baseline)")
    p_score.set_defaults(func=cmd_score)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
