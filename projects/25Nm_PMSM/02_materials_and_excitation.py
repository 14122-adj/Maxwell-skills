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
    """Create 3-phase winding setup, coil groups (canonical 8p12s) and current excitations.

    修复:
      1. 原 phases 字典映射错误 (A- 组用了 B-/C+ 槽), 与 canonical 真值表
         (references/winding_layouts.md) 不符 → 改为 WindingBuilder(12,8) 查表输出。
      2. 原用 Slot_N (已经从定子 subtract 掉的槽腔) 作线圈对象 → 改为真实线圈
         Coil_1..Coil_12 (01 步已创建), AssignCoilGroup 才能加到激励。
    """

    from pmsm_winding_builder import WindingBuilder
    builder = WindingBuilder(slots=SLOTS, poles=POLES, phases=3,
                             polarity_convention="standard")
    wcfg = builder.compute_winding()

    # 三相绕组配置(电流型,后续步骤通过 EditCurrent 切换数值)
    for phase in ["A", "B", "C"]:
        bridge.create_winding_setup(f"Winding{phase}", winding_type="Current")

    i_peak = RATED_CURRENT_PEAK_A
    freq = RATED_FREQUENCY_HZ
    omega = 2.0 * math.pi * freq
    phase_offset = {"A": 0.0, "B": -2.0944, "C": +2.0944}

    for group in wcfg.coil_groups:
        if not group.coil_indices:
            continue
        gname = f"{group.phase}{group.polarity}"
        polarity = "Positive" if group.polarity == "+" else "Negative"
        sign = 1.0 if group.polarity == "+" else -1.0
        current = (f"{sign * i_peak:.4f}*sin({omega:.4f}*time"
                   f"{phase_offset[group.phase]:+.4f})")
        bridge.assign_coil_group(name=gname, objects=group.coil_names,
                                 conductor_number=CONDUCTORS_PER_SLOT,
                                 polarity=polarity)
        bridge.assign_current_excitation(group.coil_names, current=current)
        bridge.add_winding_coils(f"Winding{group.phase}", [gname])

    if wcfg.source != "canonical":
        print(f"  [WARN] 8p12s 落在 fallback, 请人工核对槽位图")
    print(f"Windings: 3-phase, I_peak={i_peak}A, f={freq}Hz, "
          f"layout source={wcfg.source}")


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
