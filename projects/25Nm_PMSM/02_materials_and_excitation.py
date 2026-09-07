#!/usr/bin/env python3
"""
Step 2: Assign materials, excitation, and motion band.

修复:经 maxwell_bridge 单一抽象层调用 set_magnet_orientation /
create_winding_setup / assign_band / create_region 等真缺口工具,
脚本本身只与 bridge 对话。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def assign_materials():
    """Assign materials to all components."""

    # Stator / Rotor core
    bridge.assign_material("Stator_Outer", STEEL_MATERIAL)
    bridge.assign_material("Rotor_Outer", STEEL_MATERIAL)
    bridge.assign_material("Shaft", SHAFT_MATERIAL)
    bridge.assign_material("Airgap_Outer", AIRGAP_MATERIAL)
    bridge.assign_material("Region", AIRGAP_MATERIAL)

    # PMs - 各自朝向其角位置径向向外(沿 cosθ, sinθ)
    for i in range(POLES):
        angle_deg = i * 360.0 / POLES
        angle_rad = math.radians(angle_deg)
        dx, dy = math.cos(angle_rad), math.sin(angle_rad)
        # bridge 统一处理 - 第 i 块 N/S 极交替
        direction = "radial" if i % 2 == 0 else "inward"
        bridge.set_magnet_orientation(f"PM_{i + 1}", direction=direction)

    # 给 N35/NdFeB 材料加载到 PM 几何
    pm_names = [f"PM_{i}" for i in range(1, POLES + 1)]
    for nm in pm_names:
        bridge.assign_material(nm, PM_MATERIAL)

    print("Materials assigned: M270-35A, N35 NdFeB, copper, vacuum")


def create_windings():
    """Create 3-phase winding setup and assign current excitations."""

    # 三相绕组配置(电流型,后续步骤通过 EditCurrent 切换数值)
    bridge.create_winding_setup("WindingA", winding_type="Current")
    bridge.create_winding_setup("WindingB", winding_type="Current")
    bridge.create_winding_setup("WindingC", winding_type="Current")

    # 教程模式:每相 2 槽集中绕组(8p12s)
    phases = {
        "A+": (["Slot_1", "Slot_7"], "A"),
        "A-": (["Slot_4", "Slot_10"], "A"),
        "B+": (["Slot_3", "Slot_9"], "B"),
        "B-": (["Slot_6", "Slot_12"], "B"),
        "C+": (["Slot_5", "Slot_11"], "C"),
        "C-": (["Slot_2", "Slot_8"], "C"),
    }

    i_peak = RATED_CURRENT_PEAK_A
    freq = RATED_FREQUENCY_HZ
    omega = 2.0 * math.pi * freq

    currents = {
        "A+": f"{i_peak}*sin({omega:.4f}*time)",
        "A-": f"-{i_peak}*sin({omega:.4f}*time)",
        "B+": f"{i_peak}*sin({omega:.4f}*time-2.0944)",
        "B-": f"-{i_peak}*sin({omega:.4f}*time-2.0944)",
        "C+": f"{i_peak}*sin({omega:.4f}*time+2.0944)",
        "C-": f"-{i_peak}*sin({omega:.4f}*time+2.0944)",
    }

    for group, (slots, phase) in phases.items():
        polarity = "Positive" if group.endswith("+") else "Negative"
        bridge.assign_coil_group(
            name=group,
            objects=slots,
            conductor_number=CONDUCTORS_PER_SLOT,
            polarity=polarity,
        )
        bridge.assign_current_excitation(slots, current=currents[group])
        bridge.add_winding_coils(f"Winding{phase}", [group])

    print(f"Windings: 3-phase, I_peak={i_peak}A, f={freq}Hz")


def assign_motion_band():
    """Assign rotating motion to the band."""
    bridge.assign_band(name="Band", angular_velocity=f"{RATED_SPEED_RPM}rpm",
                      axis="Z", is_positive=True)
    print(f"Motion band: {RATED_SPEED_RPM} RPM")


def assign_mesh():
    """Assign mesh refinement to critical regions."""
    bridge.assign_mesh_operation(["Airgap_Outer"], max_length=f"{MESH_AIRGAP_LENGTH_MM}mm")
    bridge.assign_mesh_operation(["Stator_Outer"], max_length=f"{MESH_TOOTH_LENGTH_MM}mm")
    pm_names = [f"PM_{i}" for i in range(1, POLES + 1)]
    bridge.assign_mesh_operation(pm_names, max_length=f"{MESH_PM_LENGTH_MM}mm")
    bridge.assign_mesh_operation(["Rotor_Outer"], max_length=f"{MESH_YOKE_LENGTH_MM}mm")
    print("Mesh: airgap=0.1mm, teeth=1.5mm, PM=0.5mm, yoke=3mm")


if __name__ == "__main__":
    assign_materials()
    create_windings()
    assign_motion_band()
    assign_mesh()
    bridge.save_project()
