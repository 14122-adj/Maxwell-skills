#!/usr/bin/env python3
"""
Step 8: MTPA trajectory sweep (current angle scan).

修复: 经 bridge 调用 setup_mtpa_sweep / analyze_setup / get_torque / export_data。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)

ANGLE_START = 0
ANGLE_STOP = 90
ANGLE_STEP = 5


def setup_mtpa_current(angle_deg):
    """Setup 3-phase currents with given current angle."""
    i_peak = RATED_CURRENT_PEAK_A
    freq = RATED_FREQUENCY_HZ
    omega = 2.0 * math.pi * freq
    gamma = math.radians(angle_deg)

    currents = {
        "PhaseA_Plus": f"{i_peak}*sin({omega:.4f}*time+{gamma:.4f})",
        "PhaseA_Minus": f"-{i_peak}*sin({omega:.4f}*time+{gamma:.4f})",
        "PhaseB_Plus": f"{i_peak}*sin({omega:.4f}*time+{gamma:.4f}-2.0944)",
        "PhaseB_Minus": f"-{i_peak}*sin({omega:.4f}*time+{gamma:.4f}-2.0944)",
        "PhaseC_Plus": f"{i_peak}*sin({omega:.4f}*time+{gamma:.4f}+2.0944)",
        "PhaseC_Minus": f"-{i_peak}*sin({omega:.4f}*time+{gamma:.4f}+2.0944)",
    }

    script_lines = ["oModule = oDesign.GetModule(\"BoundarySetup\")"]
    for name, val in currents.items():
        script_lines.append(
            f'oModule.EditCurrent("{name}", ["NAME:{name}", "Current:=", "{val}"])'
        )
    bridge.run_script(script="\n".join(script_lines))


def run_mtpa_sweep():
    """Sweep current angle, output torque vs gamma."""

    # 使用 bridge 参数化扫描（ParametricSetup）
    bridge.setup_mtpa_sweep(
        setup_name="MTPA_Sweep",
        variable="$CurrentAngle",
        start=ANGLE_START,
        stop=ANGLE_STOP,
        step=ANGLE_STEP,
        stop_time=SIM_STOP_TIME_S,
        time_step=SIM_TIME_STEP_S,
    )

    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="MTPA_Sweep")
    torque_data = bridge.get_torque(setup_name="MTPA_Sweep")

    bridge.export_data(
        file_path=f"{EXPORT_DIR}mtpa_sweep.csv",
        expressions=["Moving1.Torque", "$CurrentAngle", "Time"],
        setup_name="MTPA_Sweep",
    )

    print(f"MTPA sweep results exported to {EXPORT_DIR}")
    return torque_data


if __name__ == "__main__":
    run_mtpa_sweep()
    bridge.save_project()