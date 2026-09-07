#!/usr/bin/env python3
"""
Master Orchestrator — Run all 13 simulations in correct order.
Execute this script after connecting to Maxwell MCP Server.

Usage:
  python run_all_simulations.py              # Run all simulations
  python run_all_simulations.py --step 1     # Run only step 1 (geometry)
  python run_all_simulations.py --from 3     # Run from step 3 onwards
  python run_all_simulations.py --status     # Check project status
"""

import sys
import os
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *

# ============================================================
# Simulation Steps
# ============================================================
STEPS = [
    {"id": 1,  "name": "Build Geometry",          "script": "01_build_geometry.py",          "depends": []},
    {"id": 2,  "name": "Materials & Excitation",  "script": "02_materials_and_excitation.py", "depends": [1]},
    {"id": 3,  "name": "No-Load Back-EMF",        "script": "03_no_load_bemf.py",            "depends": [2]},
    {"id": 4,  "name": "Rated Load",              "script": "04_rated_load.py",              "depends": [2]},
    {"id": 5,  "name": "Airgap Flux Density",     "script": "05_airgap_flux_density.py",     "depends": [4]},
    {"id": 6,  "name": "Overload Capacity + Demag","script": "06_overload_capacity.py",      "depends": [4]},
    {"id": 7,  "name": "Core Loss Separation",     "script": "07_loss_separation.py",         "depends": [4]},
    {"id": 8,  "name": "MTPA Sweep",              "script": "08_mtpa_sweep.py",              "depends": [4]},
    {"id": 9,  "name": "Transient Thermal",        "script": "09_thermal_analysis.py",       "depends": [4]},
    {"id": 10, "name": "Structural Integrity",     "script": "10_structural_analysis.py",    "depends": [4]},
    {"id": 11, "name": "NVH Quick Scan",          "script": "11_nvh_scan.py",                "depends": [4]},
    {"id": 12, "name": "PM Eddy Loss",            "script": "12_pm_eddy_loss.py",            "depends": [4]},
    {"id": 13, "name": "Inductance (Ld/Lq)",      "script": "13_inductance.py",              "depends": [4]},
]


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def run_step(step):
    """Execute a single simulation step."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), step["script"])
    log(f"Step {step['id']}: {step['name']} — executing {step['script']}")

    try:
        # 用 __name__="__main__" 执行，触发脚本内 if __name__=="__main__" 主流程
        g = {"__name__": "__main__", "__file__": script_path}
        exec(open(script_path, encoding='utf-8').read(), g)
        log(f"Step {step['id']}: {step['name']} — COMPLETE")
        return True
    except Exception as e:
        log(f"Step {step['id']}: {step['name']} — FAILED: {e}")
        return False


def run_all(from_step=1, only_step=None):
    """Run simulation steps in order."""

    log("=" * 60)
    log("ANSYS Maxwell Motor Simulation — 25N·m SPMSM")
    log(f"Design: {DESIGN_NAME}, {POLES}p{SLOTS}s")
    log(f"OD={STATOR_OD_MM}mm, L={STACK_LENGTH_MM}mm, Airgap={AIRGAP_MM}mm")
    log("=" * 60)

    start_time = time.time()
    results = {}

    for step in STEPS:
        # Skip steps before from_step
        if step["id"] < from_step:
            continue

        # Skip if only running specific step
        if only_step is not None and step["id"] != only_step:
            continue

        # Check dependencies
        deps_met = all(results.get(d, False) for d in step["depends"])
        if not deps_met:
            log(f"Step {step['id']}: SKIPPED — dependencies not met")
            continue

        # Run step
        success = run_step(step)
        results[step["id"]] = success

        if not success and step["id"] <= 4:
            # Critical steps: stop on failure
            log(f"Critical step {step['id']} failed. Stopping.")
            break

        # Save after each major step
        try:
            save_project()
        except Exception:
            pass

    elapsed = time.time() - start_time
    log("=" * 60)
    log(f"Simulation complete in {elapsed:.1f}s")
    log("Results:")
    for step_id, success in sorted(results.items()):
        status = "PASS" if success else "FAIL"
        log(f"  Step {step_id}: {STEPS[step_id - 1]['name']} — {status}")
    log(f"Output: {EXPORT_DIR}")
    log("=" * 60)


def check_status():
    """Check current project status."""
    log(f"Project: {PROJECT_NAME}")
    log(f"Design: {DESIGN_NAME}")
    log(f"Output: {EXPORT_DIR}")

    # Check which result files exist
    result_files = [
        "no_load_bemf.csv",
        "rated_load.csv",
        "airgap_flux_density.csv",
        "mtpa_sweep.csv",
        "thermal_transient.csv",
        "structural_peak.csv",
        "nvh_scan.csv",
        "pm_eddy_loss.csv",
        "inductance_ld.csv",
    ]

    for f in result_files:
        path = os.path.join(EXPORT_DIR, f)
        exists = os.path.exists(path)
        status = "EXISTS" if exists else "MISSING"
        log(f"  {f}: {status}")


def main():
    parser = argparse.ArgumentParser(description="Maxwell Motor Simulation Orchestrator")
    parser.add_argument("--from", dest="from_step", type=int, default=1, help="Start from step N")
    parser.add_argument("--step", dest="only_step", type=int, default=None, help="Run only step N")
    parser.add_argument("--status", action="store_true", help="Check project status")
    args = parser.parse_args()

    if args.status:
        check_status()
    else:
        run_all(from_step=args.from_step, only_step=args.only_step)


if __name__ == "__main__":
    main()
