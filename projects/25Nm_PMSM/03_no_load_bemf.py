#!/usr/bin/env python3
"""
Step 3: No-load back-EMF & cogging torque simulation.

修复: 经 maxwell_bridge 调用 add_transient_setup / analyze_setup /
get_induced_voltage / get_torque / create_report / export_data 等真缺口工具。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_no_load():
    """Configure no-load simulation (current = 0)."""

    # 将各相激励电流置零 —— 经 bridge.run_script 注入 IronPython
    bridge.run_script(script="""
oModule = oDesign.GetModule("BoundarySetup")
oModule.EditCurrent(
    "PhaseA_Plus",
    ["NAME:PhaseA_Plus", "Objects:=", ["Slot_1", "Slot_7"], "Current:=", "0A"]
)
oModule.EditCurrent(
    "PhaseA_Minus",
    ["NAME:PhaseA_Minus", "Objects:=", ["Slot_4", "Slot_10"], "Current:=", "0A"]
)
oModule.EditCurrent(
    "PhaseB_Plus",
    ["NAME:PhaseB_Plus", "Objects:=", ["Slot_3", "Slot_9"], "Current:=", "0A"]
)
oModule.EditCurrent(
    "PhaseB_Minus",
    ["NAME:PhaseB_Minus", "Objects:=", ["Slot_6", "Slot_12"], "Current:=", "0A"]
)
oModule.EditCurrent(
    "PhaseC_Plus",
    ["NAME:PhaseC_Plus", "Objects:=", ["Slot_5", "Slot_11"], "Current:=", "0A"]
)
oModule.EditCurrent(
    "PhaseC_Minus",
    ["NAME:PhaseC_Minus", "Objects:=", ["Slot_2", "Slot_8"], "Current:=", "0A"]
)
""")

    # Transient setup: 2 electrical cycles, fine time step
    bridge.add_transient_setup(
        setup_name="NoLoad",
        stop_time=SIM_STOP_TIME_S,
        time_step=SIM_TIME_STEP_S,
    )

    print("No-load setup: 0A current, stop=0.02s, step=5e-5s")


def run_no_load():
    """Run no-load simulation."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="NoLoad")
    print("No-load simulation complete")


def extract_no_load_results():
    """Extract back-EMF and cogging torque results."""

    # Back-EMF waveforms
    bridge.create_report(
        report_name="BackEMF_NoLoad",
        report_type="Transient",
        x_quantity="Time",
        y_quantities=[
            "InducedVoltage(PhaseA)",
            "InducedVoltage(PhaseB)",
            "InducedVoltage(PhaseC)",
        ],
        display_type="Rectangular Plot",
    )

    # Cogging torque
    bridge.create_report(
        report_name="Cogging_Torque",
        report_type="Transient",
        x_quantity="Time",
        y_quantities=["Moving1.Torque"],
        display_type="Rectangular Plot",
    )

    # Extract numerical data
    bemf_data = bridge.get_induced_voltage(
        setup_name="NoLoad",
        winding_name="ThreePhase_Winding",
    )

    torque_data = bridge.get_torque(setup_name="NoLoad")

    # Export to CSV
    bridge.export_data(
        file_path=f"{EXPORT_DIR}no_load_bemf.csv",
        expressions=[
            "InducedVoltage(PhaseA)",
            "InducedVoltage(PhaseB)",
            "InducedVoltage(PhaseC)",
            "Moving1.Torque",
            "Time",
        ],
        setup_name="NoLoad",
    )

    print(f"Results: back-EMF and cogging torque exported to {EXPORT_DIR}")

    return bemf_data, torque_data


if __name__ == "__main__":
    setup_no_load()
    run_no_load()
    extract_no_load_results()
    bridge.save_project()