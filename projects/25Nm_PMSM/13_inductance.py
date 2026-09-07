#!/usr/bin/env python3
"""
Step 13: Inductance calculation (Ld, Lq) — frozen permeability method.
Essential for control design.
Run after: 04_rated_load.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def setup_inductance():
    """Configure frozen permeability for Ld/Lq calculation."""

    # Step 1: Freeze permeability at rated operating point
    bridge.run_script(script="""
    oDesign.SetDesignSettings(
        ["NAME:DesignSettings",
         "FrozenPermeability:=", True]
    )
    """)

    # Step 2: D-axis excitation (Id only)
    i_dc = RATED_CURRENT_PEAK_A * 0.5  # half-rated DC for inductance measurement

    bridge.run_script(script=f"""
    oModule = oDesign.GetModule("BoundarySetup")
    # Remove AC, apply DC on d-axis
    oModule.EditCurrent(
        "PhaseA_Plus",
        ["NAME:PhaseA_Plus",
         "Objects:=", ["Slot_1", "Slot_7"],
         "Current:=", "{i_dc}A"]
    )
    oModule.EditCurrent(
        "PhaseA_Minus",
        ["NAME:PhaseA_Minus",
         "Objects:=", ["Slot_4", "Slot_10"],
         "Current:=", "-{i_dc}A"]
    )
    oModule.EditCurrent(
        "PhaseB_Plus",
        ["NAME:PhaseB_Plus",
         "Objects:=", ["Slot_3", "Slot_9"],
         "Current:=", "{-i_dc / 2:.4f}A"]
    )
    oModule.EditCurrent(
        "PhaseB_Minus",
        ["NAME:PhaseB_Minus",
         "Objects:=", ["Slot_6", "Slot_12"],
         "Current:=", "{i_dc / 2:.4f}A"]
    )
    oModule.EditCurrent(
        "PhaseC_Plus",
        ["NAME:PhaseC_Plus",
         "Objects:=", ["Slot_5", "Slot_11"],
         "Current:=", "{-i_dc / 2:.4f}A"]
    )
    oModule.EditCurrent(
        "PhaseC_Minus",
        ["NAME:PhaseC_Minus",
         "Objects:=", ["Slot_2", "Slot_8"],
         "Current:=", "{i_dc / 2:.4f}A"]
    )
    """)

    # Step 3: Magnetostatic setup for inductance
    bridge.add_magnetostatic_setup(
        setup_name="Ld_Calc",
        max_passes=15,
    )

    print("Ld setup: frozen permeability, d-axis DC excitation")


def run_inductance():
    """Run inductance calculation."""
    bridge.analyze_setup(design_name=DESIGN_NAME, setup_name="Ld_Calc")
    print("Inductance calculation complete")


def extract_inductance_results():
    """Extract Ld and Lq values."""

    # Extract flux linkage
    bridge.export_data(
        file_path=f"{EXPORT_DIR}inductance_ld.csv",
        expressions=["FluxLinkage(PhaseA)", "FluxLinkage(PhaseB)", "FluxLinkage(PhaseC)"],
        setup_name="Ld_Calc",
    )

    # Lq calculation (similar, with q-axis excitation)
    # For now, note that SPMSM Ld ≈ Lq
    print("Ld calculation complete. For Lq, repeat with q-axis excitation.")
    print("SPMSM expected: Ld ≈ Lq (within 10%)")


if __name__ == "__main__":
    setup_inductance()
    run_inductance()
    extract_inductance_results()
    bridge.save_project()
