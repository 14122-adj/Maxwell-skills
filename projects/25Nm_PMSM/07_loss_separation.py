#!/usr/bin/env python3
"""
Step 7: Core loss separation under rated conditions.

修复: 经 bridge 调用 add_transient_setup / analyze_setup / get_loss_data / export_data / create_report。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_loss_separation():
    """Setup fine-step simulation for loss separation."""

    stop_time = 2.0 / RATED_FREQUENCY_HZ
    time_step = 5e-6  # 5us for high-fidelity loss computation

    bridge.add_transient_setup(
        setup_name="LossSeparation",
        stop_time=stop_time,
        time_step=time_step,
    )

    print("Loss separation setup: step=5us, 2 electrical cycles")


def run_loss_separation():
    """Run and extract loss components."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="LossSeparation")

    loss_data = bridge.get_loss_data(setup_name="LossSeparation")

    bridge.create_report(
        report_name="Core_Loss_Breakdown",
        report_type="Transient",
        x_quantity="Time",
        y_quantities=["SolidLoss", "CoreLoss", "StrandedLoss_RMS"],
        display_type="Rectangular Plot",
    )

    bridge.export_data(
        file_path=f"{EXPORT_DIR}loss_separation.csv",
        expressions=[
            "SolidLoss",
            "CoreLoss",
            "StrandedLoss_RMS",
            "Moving1.Torque",
            "Time",
        ],
        setup_name="LossSeparation",
    )

    print(f"Loss separation results exported to {EXPORT_DIR}")
    return loss_data


if __name__ == "__main__":
    setup_loss_separation()
    run_loss_separation()
    bridge.save_project()