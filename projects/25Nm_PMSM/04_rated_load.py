#!/usr/bin/env python3
"""
Step 4: Rated load simulation with 3-phase current excitation.

修复: 经 bridge 调用 add_transient_setup / analyze_setup / export_data。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_rated_load():
    """Configure rated load simulation with 3-phase currents."""

    i_peak = RATED_CURRENT_PEAK_A
    freq = RATED_FREQUENCY_HZ
    omega = 2.0 * math.pi * freq

    currents = {
        "PhaseA_Plus": f"{i_peak}*sin({omega:.4f}*time)",
        "PhaseA_Minus": f"-{i_peak}*sin({omega:.4f}*time)",
        "PhaseB_Plus": f"{i_peak}*sin({omega:.4f}*time-2.0944)",
        "PhaseB_Minus": f"-{i_peak}*sin({omega:.4f}*time-2.0944)",
        "PhaseC_Plus": f"{i_peak}*sin({omega:.4f}*time+2.0944)",
        "PhaseC_Minus": f"-{i_peak}*sin({omega:.4f}*time+2.0944)",
    }

    # 通过 bridge.run_script 批量编辑各相电流
    script_lines = ["oModule = oDesign.GetModule(\"BoundarySetup\")"]
    for name, current in currents.items():
        script_lines.append(f'oModule.EditCurrent("{name}", ["NAME:{name}", "Current:=", "{current}"])')
    bridge.run_script(script="\n".join(script_lines))

    # Transient setup
    bridge.add_transient_setup(
        setup_name="RatedLoad",
        stop_time=SIM_STOP_TIME_S,
        time_step=SIM_TIME_STEP_S,
    )

    print("Rated load setup: 3-phase currents, stop=0.02s, step=5e-5s")


def run_rated_load():
    """Run rated load simulation."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="RatedLoad")
    print("Rated load simulation complete")


def extract_rated_load_results():
    """Extract torque, efficiency, and loss results."""

    # Torque
    torque_data = bridge.get_torque(setup_name="RatedLoad")

    # Loss breakdown
    loss_data = bridge.get_loss_data(setup_name="RatedLoad")

    # Export
    bridge.export_data(
        file_path=f"{EXPORT_DIR}rated_load.csv",
        expressions=[
            "Moving1.Torque",
            "SolidLoss",
            "CoreLoss",
            "Moving1.Speed",
            "Time",
        ],
        setup_name="RatedLoad",
    )

    print(f"Rated load results exported to {EXPORT_DIR}")
    return torque_data, loss_data


if __name__ == "__main__":
    setup_rated_load()
    run_rated_load()
    extract_rated_load_results()
    bridge.save_project()