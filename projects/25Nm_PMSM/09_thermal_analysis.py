#!/usr/bin/env python3
"""
Step 9: Transient thermal analysis with loss coupling.

修复: 经 bridge 调用 add_thermal_setup / analyze_setup / get_temperature_data / export_data。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)

THERMAL_STOP_TIME_S = 100.0   # 100s thermal transient
THERMAL_TIME_STEP_S = 0.5     # 0.5s step


def setup_thermal():
    """Setup transient thermal simulation with loss coupling."""
    bridge.add_thermal_setup(
        setup_name="ThermalTransient",
        stop_time=THERMAL_STOP_TIME_S,
        time_step=THERMAL_TIME_STEP_S,
        loss_source="RatedLoad",
    )

    print(f"Thermal setup: stop={THERMAL_STOP_TIME_S}s, step={THERMAL_TIME_STEP_S}s")


def run_thermal():
    """Run thermal simulation and extract temperature."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="ThermalTransient")
    temp_data = bridge.get_temperature_data(setup_name="ThermalTransient")

    bridge.export_data(
        file_path=f"{EXPORT_DIR}thermal_transient.csv",
        expressions=[
            "Temperature",
            "Temperature(Winding)",
            "Temperature(Magnet)",
            "Time",
        ],
        setup_name="ThermalTransient",
    )

    bridge.create_report(
        report_name="Thermal_Rise",
        report_type="Transient",
        x_quantity="Time",
        y_quantities=[
            "Temperature(Winding)",
            "Temperature(Magnet)",
        ],
        display_type="Rectangular Plot",
    )

    print(f"Thermal results exported to {EXPORT_DIR}")
    return temp_data


if __name__ == "__main__":
    setup_thermal()
    run_thermal()
    bridge.save_project()