#!/usr/bin/env python3
"""
Step 10: Structural integrity — stress & deformation under peak load.

修复: 经 bridge 调用 setup_structural_analysis / analyze_setup /
export_data / create_report。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_structural():
    """Setup structural FEA analysis."""
    bridge.setup_structural_analysis(
        setup_name="Structural_Peak",
        load_source="Overload_3x",
        mesher="Mechanical",
    )
    print("Structural analysis setup complete (from Overload_3x)")


def run_structural():
    """Run structural simulation and extract results."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="Structural_Peak")

    bridge.export_data(
        file_path=f"{EXPORT_DIR}structural_peak.csv",
        expressions=[
            "Stress(vonMises)",
            "TotalDeformation",
            "SafetyFactor",
        ],
        setup_name="Structural_Peak",
    )

    bridge.create_report(
        report_name="Structural_Stress",
        display_type="Rectangular Plot",
        report_type="Data Table",
        x_quantity="Distance",
        y_quantities=["Stress(vonMises)"],
    )

    print(f"Structural results exported to {EXPORT_DIR}")


if __name__ == "__main__":
    setup_structural()
    run_structural()
    bridge.save_project()