#!/usr/bin/env python3
"""Generate Markdown report from batch sweep results.

Reads JSON output from batch_runner.py and generates a formatted
report with tables, summary stats, and links to IPFS/Sepolia.

Usage:
    python3 scripts/batch_runner.py config.yaml --json > results.json
    python3 scripts/generate_report.py results.json > report.md
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def generate_markdown(data: dict) -> str:
    """Generate Markdown report from sweep results."""
    config = data.get("config", {})
    summary = data.get("summary", {})
    results = data.get("results", [])
    attestation = data.get("attestation", {})

    lines = []
    lines.append(f"# Experiment Report: {summary.get('name', 'unnamed')}")
    lines.append(f"")
    lines.append(f"Generated: {summary.get('timestamp', datetime.now().isoformat())}")
    lines.append(f"")

    # Config summary
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Seeds | {config.get('seeds', '?')} |")
    lines.append(f"| Steps | {config.get('steps', '?')} |")
    lines.append(f"| Nanobots | {config.get('n_bots', '?')} |")
    lines.append(f"| Queen | {'Yes' if config.get('with_queen') else 'No'} |")
    lines.append(f"| Episode length | {config.get('episode_length', '?')} |")
    lines.append(f"| Patients | {len(config.get('patients', []))} |")
    lines.append("")

    # Summary stats
    lines.append("## Results Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Total runs | {summary.get('total_runs', 0)} |")
    lines.append(f"| Avg kill rate | {summary.get('avg_kill_rate', 0)}% |")
    lines.append(f"| Std deviation | ±{summary.get('std_kill_rate', 0)}% |")
    lines.append(f"| Best | {summary.get('best_kill_rate', 0)}% |")
    lines.append(f"| Worst | {summary.get('worst_kill_rate', 0)}% |")
    lines.append(f"| Avg deliveries | {summary.get('avg_deliveries', 0)} |")
    lines.append(f"| Avg runtime | {summary.get('avg_runtime_s', 0)}s |")
    lines.append("")

    # Per-run table
    if results:
        lines.append("## Individual Runs")
        lines.append("")
        lines.append("| Patient | Seed | Kill Rate | Kills | Deliveries | Drug (ug) | Runtime |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in results:
            lines.append(
                f"| {r.get('patient', '?')} "
                f"| {r.get('seed', '?')} "
                f"| {r.get('kill_rate_pct', 0)}% "
                f"| {r.get('kills', 0)}/{r.get('total_cells', 0)} "
                f"| {r.get('deliveries', 0)} "
                f"| {r.get('total_drug_ug', 0)} "
                f"| {r.get('runtime_s', 0)}s |"
            )
        lines.append("")

    # Per-patient summary
    patients = set(r.get("patient") for r in results)
    if len(patients) > 1:
        lines.append("## Per-Patient Summary")
        lines.append("")
        lines.append("| Patient | Avg Kill Rate | Best | Worst | Runs |")
        lines.append("|---|---|---|---|---|")
        for patient in sorted(patients):
            runs = [r for r in results if r.get("patient") == patient]
            rates = [r["kill_rate_pct"] for r in runs]
            avg = sum(rates) / len(rates) if rates else 0
            lines.append(
                f"| {patient} "
                f"| {avg:.1f}% "
                f"| {max(rates):.1f}% "
                f"| {min(rates):.1f}% "
                f"| {len(runs)} |"
            )
        lines.append("")

    # Attestation
    if attestation:
        lines.append("## On-Chain Attestation")
        lines.append("")
        if attestation.get("cid"):
            lines.append(f"- IPFS CID: `{attestation['cid']}`")
            lines.append(f"- Gateway: {attestation.get('gateway_url', '')}")
        lines.append(f"- Artifact hash: `{attestation.get('artifact_hash', 'N/A')}`")
        lines.append(f"- Config hash: `{attestation.get('config_hash', 'N/A')}`")
        lines.append(f"- Contract: `0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b` (Base Sepolia)")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate experiment report")
    parser.add_argument("input", help="JSON results file from batch_runner.py")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    args = parser.parse_args()

    if args.input == "-" or args.input == "/dev/stdin":
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text()
    # Extract JSON from potentially mixed output (simulation prints to stdout)
    start = text.find("{")
    if start < 0:
        print("Error: No JSON found in input", file=sys.stderr)
        sys.exit(1)
    data = json.loads(text[start:])
    report = generate_markdown(data)

    if args.output:
        Path(args.output).write_text(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
