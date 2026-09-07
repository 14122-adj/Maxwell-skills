#!/usr/bin/env python3
"""
Step 11: NVH scan — force harmonics & acoustic noise over speed range.

修复: 经 bridge 调用 setup_nvh_scan / analyze_setup / export_data / create_report。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)

SPEED_RPM_MIN = 500
SPEED_RPM_MAX = 6000
SPEED_STEP_RPM = 500


def setup_nvh_sweep():
    """Setup parametric speed sweep for NVH analysis."""
    bridge.setup_nvh_scan(
        setup_name="NVH_Sweep",
        speed_var="$Speed",
        speed_rpm_min=SPEED_RPM_MIN,
        speed_rpm_max=SPEED_RPM_MAX,
        speed_step_rpm=SPEED_STEP_RPM,
        stop_time=2.0 / RATED_FREQUENCY_HZ,
        time_step=SIM_TIME_STEP_S,
    )
    print(f"NVH sweep: {SPEED_RPM_MIN}-{SPEED_RPM_MAX} rpm, step={SPEED_STEP_RPM}")


def run_nvh():
    """Run NVH scan and extract force harmonics."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="NVH_Sweep")

    # Force harmonics vs speed
    bridge.create_report(
        report_name="Force_Harmonics_vs_Speed",
        report_type="Data Table",
        x_quantity="$Speed",
        y_quantities=[
            "Force_Radial_Harmonic_Order_2",
            "Force_Radial_Harmonic_Order_4",
            "Force_Radial_Harmonic_Order_6",
        ],
        display_type="Rectangular Plot",
    )

    # Sound power level
    bridge.create_report(
        report_name="SPL_vs_Speed",
        report_type="Data Table",
        x_quantity="$Speed",
        y_quantities=[
            "SPL_dBA_Total",
            "SPL_dBA_1kHz",
            "SPL_dBA_2kHz",
        ],
        display_type="Rectangular Plot",
    )

    bridge.export_data(
        file_path=f"{EXPORT_DIR}nvh_scan.csv",
        expressions=[
            "$Speed",
            "Force_Radial_Harmonic_Order_2",
            "Force_Radial_Harmonic_Order_4",
            "Force_Radial_Harmonic_Order_6",
            "SPL_dBA_Total",
        ],
        setup_name="NVH_Sweep",
    )

    print(f"NVH scan results exported to {EXPORT_DIR}")


if __name__ == "__main__":
    setup_nvh_sweep()
    run_nvh()
    bridge.save_project()