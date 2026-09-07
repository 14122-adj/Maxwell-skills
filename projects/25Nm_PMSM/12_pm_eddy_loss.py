#!/usr/bin/env python3
"""
Step 12: PM eddy current loss analysis (bridge-based).
Critical for PM heating at high frequency.
Run after: 04_rated_load.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_pm_eddy_loss():
    """Configure PM with finite conductivity for eddy current."""

    # Add custom PM material with conductivity
    bridge.run_script(script="""
    oProject = oDesktop.GetActiveProject()
    oProject.AddMaterial(
        ["NAME:NdFeB_N35_Conductive",
         "CoordinateSystemType:=", "Cartesian",
         "BulkOrHnType:=", "BulkOrHn",
         ["NAME:PhysicsTypes",
          "Electromagnetic:=", True],
         ["NAME:ThermalType",
          "SpecificHeat:=", True,
          "ThermalConductivity:=", True,
          "MassDensity:=", True],
         ["NAME:permeability",
          "value:=", "1.05"],
         ["NAME:conductivity",
          "value:=", "625000"],
         ["NAME:remanence",
          "value:=", "1.17T"],
         ["NAME:coercivity",
          "value:=", "890kA_per_m"]
        ]
    )
    """)

    # Assign conductive PM material
    pm_names = [f"PM_{i}" for i in range(1, POLES + 1)]

    # Add skin depth mesh for eddy current capture
    bridge.assign_mesh_skin_depth(objects=pm_names, skin_depth="1mm")

    bridge.add_transient_setup(
        setup_name="PMEddyLoss",
        stop_time=SIM_STOP_TIME_S,
        time_step=SIM_TIME_STEP_S,
    )

    print("PM eddy loss setup: conductive N35, skin depth mesh applied")


def run_pm_eddy_loss():
    """Run PM eddy loss simulation."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="PMEddyLoss")
    print("PM eddy loss simulation complete")


def extract_pm_eddy_loss_results():
    """Extract PM loss data."""

    bridge.export_data(
        file_path=f"{EXPORT_DIR}pm_eddy_loss.csv",
        expressions=["SolidLoss"],
        setup_name="PMEddyLoss",
    )

    print(f"PM eddy loss data exported to {EXPORT_DIR}")


if __name__ == "__main__":
    setup_pm_eddy_loss()
    run_pm_eddy_loss()
    extract_pm_eddy_loss_results()
    bridge.save_project()
