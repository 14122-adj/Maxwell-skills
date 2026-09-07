#!/usr/bin/env python3
"""
Step 6: Overload capacity and demagnetization analysis.

修复: 经 bridge 调用 add_transient_setup / analyze_setup / export_data / get_torque / get_field_data。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)

OVERLOAD_FACTORS = [1.5, 2.0, 3.0]


def setup_overload(factor):
    """Setup overload simulation at given current multiplier."""
    i_peak = RATED_CURRENT_PEAK_A * factor
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

    script_lines = ["oModule = oDesign.GetModule(\"BoundarySetup\")"]
    for name, val in currents.items():
        script_lines.append(
            f'oModule.EditCurrent("{name}", ["NAME:{name}", "Current:=", "{val}"])'
        )
    bridge.run_script(script="\n".join(script_lines))

    setup_name = f"Overload_{factor}x"
    bridge.add_transient_setup(
        setup_name=setup_name,
        stop_time=SIM_STOP_TIME_S,
        time_step=SIM_TIME_STEP_S,
    )
    return setup_name


def run_overload():
    """Run all overload cases and extract torque/demag results."""
    results = {}
    for factor in OVERLOAD_FACTORS:
        sname = setup_overload(factor)
        bridge.analyze_setup(design_name=DESIGN_NAME, setup_name=sname)
        torque = bridge.get_torque(setup_name=sname)
        bridge.export_data(
            file_path=f"{EXPORT_DIR}overload_{factor}x.csv",
            expressions=["Moving1.Torque", "SolidLoss", "CoreLoss", "Time"],
            setup_name=sname,
        )
        results[f"{factor}x"] = torque
        print(f"Overload {factor}x: torque = {torque}")

    # 退磁检查——磁钢最小磁密
    demag_data = bridge.get_field_data(
        quantity="Mag_B",
        objects=["NdFe35_N", "NdFe35_S"],
        setup_name="Overload_2x",
    )
    bridge.export_data(
        file_path=f"{EXPORT_DIR}demag_check.csv",
        expressions=["Mag_B"],
        setup_name="Overload_2x",
    )
    print(f"Demagnetization check data exported to {EXPORT_DIR}")
    return results


if __name__ == "__main__":
    run_overload()
    bridge.save_project()