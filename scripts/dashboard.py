"""Streamlit dashboard for antelligence simulation leaderboard.

Displays live leaderboard from on-chain data or local artifacts,
experiment sweep results, and system health.

Usage:
    streamlit run scripts/dashboard.py
"""

import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from chain.leaderboard import build_leaderboard, load_local_artifacts
from chain.ipfs import create_simulation_artifact

st.set_page_config(page_title="Antelligence Dashboard", layout="wide")

st.title("Antelligence — Simulation Leaderboard")
st.markdown("Privacy-preserving tumor simulation attestation on Base L2")

# Sidebar
st.sidebar.header("Configuration")
artifacts_dir = st.sidebar.text_input("Artifacts directory", value="./results")
contract = "0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b"
st.sidebar.code(f"TumorIntel: {contract}", language="text")
st.sidebar.markdown(f"[View on BaseScan](https://sepolia.basescan.org/address/{contract})")

# Load data
tab1, tab2, tab3 = st.tabs(["Leaderboard", "Sweep Results", "System Info"])

with tab1:
    st.header("Simulation Leaderboard")

    # Try loading local artifacts
    artifacts_path = Path(artifacts_dir)
    if artifacts_path.exists():
        artifacts = load_local_artifacts(str(artifacts_path))
        if artifacts:
            result = build_leaderboard(artifacts)
            if result["leaderboard"]:
                st.dataframe(
                    [
                        {
                            "Rank": e["rank"],
                            "Kill Rate": f"{e['kill_rate']}%",
                            "Deliveries": e["deliveries"],
                            "Nanobots": e["nanobot_count"],
                            "Steps": e["steps"],
                            "Verified": "Yes" if e.get("verified_onchain") else "No",
                            "Run ID": e["run_id"][:16],
                        }
                        for e in result["leaderboard"][:20]
                    ],
                    use_container_width=True,
                )
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Entries", result["summary"]["total_entries"])
                col2.metric("Best Kill Rate", f"{result['summary']['best_kill_rate']}%")
                col3.metric("Avg Kill Rate", f"{result['summary']['avg_kill_rate']}%")
            else:
                st.info("No artifacts found. Run a sweep to populate.")
        else:
            st.info(f"No artifacts in {artifacts_dir}. Run batch_runner.py first.")
    else:
        st.info(f"Directory {artifacts_dir} does not exist.")

with tab2:
    st.header("Recent Sweep Results")

    # Load most recent sweep result
    sweep_file = st.file_uploader("Upload sweep results (JSON)", type=["json"])
    if sweep_file:
        text = sweep_file.read().decode()
        start = text.find("{")
        if start >= 0:
            data = json.loads(text[start:])
            summary = data.get("summary", {})

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Runs", summary.get("total_runs", 0))
            col2.metric("Avg Kill Rate", f"{summary.get('avg_kill_rate', 0)}%")
            col3.metric("Best", f"{summary.get('best_kill_rate', 0)}%")
            col4.metric("Worst", f"{summary.get('worst_kill_rate', 0)}%")

            results = data.get("results", [])
            if results:
                st.dataframe(
                    [
                        {
                            "Patient": r.get("patient", "?"),
                            "Seed": r.get("seed", "?"),
                            "Kill Rate": f"{r.get('kill_rate_pct', 0)}%",
                            "Deliveries": r.get("deliveries", 0),
                            "Drug (ug)": r.get("total_drug_ug", 0),
                            "Runtime": f"{r.get('runtime_s', 0)}s",
                        }
                        for r in results
                    ],
                    use_container_width=True,
                )

with tab3:
    st.header("System Information")

    st.subheader("Contract")
    st.code(f"TumorIntel: {contract}\nChain: Base Sepolia (84532)\nVerifier: SP1 Gateway", language="text")

    st.subheader("Sprint Progress")
    phases = {
        "Phase 0 — Blockchain Foundation": True,
        "Phase 1 — Python Simulation Core": True,
        "Phase 2 — Pheromone System": True,
        "Phase 3 — Blockchain Integration": True,
        "Phase 4 — LLM Queen/Worker": "4/5",
        "Phase 5 — Experiment Ops": "4/5",
    }
    for phase, status in phases.items():
        if status is True:
            st.markdown(f"- [x] {phase}")
        else:
            st.markdown(f"- [ ] {phase} ({status})")

    st.subheader("Test Suite")
    st.metric("Python Tests", 100)
    st.metric("Hardhat Tests", 30)
    st.metric("Total", 130)
