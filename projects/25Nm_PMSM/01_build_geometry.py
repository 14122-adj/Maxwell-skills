#!/usr/bin/env python3
"""
Step 1: Build complete 2D motor geometry in ANSYS Maxwell.
Creates stator core, rotor core, PMs, shaft, band, airgap region.

修复:所有 Maxwell 接口调用经 `maxwell_bridge.MaxwellBridge` 单一抽象层,
脚本永不直接接触 MCP 工具名/COM API 名,消除原 `set_model_units` /
`subtract` / `duplicate_around_axis` / `draw_region_pad` 的 NameError。
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401  电机参数常量
from maxwell_bridge import MaxwellBridge  # ★ 唯一抽象层入口


# ── 单例 bridge,dry_run 由环境变量切换以便CI无 Maxwell 也能跑 ──
_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def build_geometry():
    """Build full motor cross-section (units/lithograph via bridge)."""

    # --- 单位 ---
    bridge.set_model_units("mm")

    # --- Stator core (annulus) ---
    bridge.draw_circle("Stator_Outer", x=0, y=0, radius=STATOR_OD_MM / 2)
    bridge.draw_circle("Stator_Inner", x=0, y=0, radius=STATOR_ID_MM / 2)
    bridge.subtract(blank_parts="Stator_Outer", tool_parts="Stator_Inner", keep_originals=False)

    # --- Rotor core (annulus) ---
    bridge.draw_circle("Rotor_Outer", x=0, y=0, radius=ROTOR_OD_MM / 2)
    bridge.draw_circle("Rotor_Inner", x=0, y=0, radius=ROTOR_ID_MM / 2)
    bridge.subtract(blank_parts="Rotor_Outer", tool_parts="Rotor_Inner", keep_originals=False)

    # --- Shaft ---
    bridge.draw_circle("Shaft", x=0, y=0, radius=ROTOR_ID_MM / 2)

    # --- 单槽模板 → 阵列 ---
    slot_angle_step = 360.0 / SLOTS
    slot_depth = (STATOR_OD_MM - STATOR_ID_MM) / 2.0 - YOKE_THICKNESS_MM - 1.0
    half_slot_width = (TAU_SLOT_MM - TOOTH_WIDTH_MM) / 2.0

    bridge.draw_rectangle(
        "Slot_1",
        x=STATOR_ID_MM / 2, y=-half_slot_width,
        width=slot_depth, height=half_slot_width * 2,
    )
    bridge.duplicate_around_axis("Slot_1", angle_deg=slot_angle_step, num_clones=SLOTS)

    # --- 单磁钢模板 → 阵列 ---
    pm_arc_angle = PM_POLE_ARC * (360.0 / POLES)
    pm_length = math.sin(pm_arc_angle / 2.0 * math.pi / 180.0) * ROTOR_OD_MM / 2.0
    pm_pole_pitch = 360.0 / POLES

    bridge.draw_rectangle(
        "PM_1",
        x=ROTOR_OD_MM / 2, y=-pm_length / 2,
        width=PM_THICKNESS_MM, height=pm_length,
    )
    bridge.duplicate_around_axis("PM_1", angle_deg=pm_pole_pitch, num_clones=POLES)

    # --- Airgap region ---
    bridge.draw_circle("Airgap_Inner", x=0, y=0, radius=ROTOR_OD_MM / 2)
    bridge.draw_circle("Airgap_Outer", x=0, y=0, radius=STATOR_ID_MM / 2)
    bridge.subtract(blank_parts="Airgap_Outer", tool_parts="Airgap_Inner", keep_originals=False)

    # --- Motion Band ---
    bridge.draw_circle("Band", x=0, y=0, radius=BAND_RADIUS_MM)

    # --- Subtract slots from stator ---
    slot_names = ",".join(f"Slot_{i}" for i in range(1, SLOTS + 1))
    bridge.subtract(blank_parts="Stator_Outer", tool_parts=slot_names, keep_originals=False)

    # --- Subtract PMs from rotor (or keepPMs on rotor surface for SPM) ---
    pm_names = ",".join(f"PM_{i}" for i in range(1, POLES + 1))
    bridge.subtract(blank_parts="Rotor_Outer", tool_parts=pm_names, keep_originals=False)

    # --- Region (external air) ---
    bridge.create_region(padding=STATOR_OD_MM / 2 * 0.3)

    # --- 线圈截面（8p12s 槽内居中, Coil_1..Coil_12）---
    # 修复: 原几何不建线圈, 导致后续 AssignCoilGroup 引用对象不存在、无法加激励。
    # 槽位: 矩形槽从 0° 起, 每 360/SLOTS 一个; 线圈居中于槽中心线。
    coil_script = f"""# 线圈截面创建（槽内居中, Coil_1..Coil_12）
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
_oEd = oDesign.SetActiveEditor("3D Modeler")
_slot_angle = 360.0 / {SLOTS}
_r_in = {STATOR_ID_MM} / 2.0
_r_mid = ({STATOR_ID_MM} / 2.0 + {STATOR_ID_MM} / 2.0 + {slot_depth:.2f}) / 2.0
_r_thick = {slot_depth:.2f} * 0.50   # 径向厚(Width)
_t_wide = {half_slot_width * 1.5:.2f}   # 周向宽(Height), 小于槽内宽
for _k in range({SLOTS}):
    _angle = _k * _slot_angle
    _nm = "Coil_%d" % (_k + 1)
    _oEd.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(_r_mid - _r_thick / 2.0) + "mm",
         "YStart:=", str(-_t_wide / 2.0) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(_r_thick) + "mm",
         "Height:=", str(_t_wide) + "mm",
         "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", _nm, "Flags:=", "", "Color:=", "(255 128 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"copper"', "SolveInside:=", True])
    if _angle > 0:
        _oEd.Rotate(
            ["NAME:Selections", "Selections:=", _nm],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(_angle) + "deg",
             "DuplicateObjects:=", False])
"""
    bridge.run_script(coil_script)

    print(f"Geometry built: {SLOTS} slots, {POLES} PMs, airgap={AIRGAP_MM}mm, {SLOTS} coils")
    return True


if __name__ == "__main__":
    build_geometry()
    bridge.save_project()
