#!/usr/bin/env python3
"""
Driver — 调用 skill 的 scripts/main.py (MotorModelBuilder) 为 25N·m SPMSM 生成
可运行的 ANSYS Maxwell 2D IronPython 建模脚本（即"绘制电机"）。

参数取自 projects/25Nm_PMSM/pmsm_config.py，与现有设计 B 完全一致：
  8 极 12 槽 表贴式永磁同步电机 (SPMSM)
  定子外径 150mm / 内径 93mm / 叠长 160mm / 气隙 0.675mm
  磁钢 N35, Br=1.17T, 极弧系数 0.87
  绕组 Kw=0.933, 每相 81 匝, 每槽 40 导体, AWG15

⚠ 重跑前必读（2026-11-11 G3）
--------------------------------------------------------------------------
`maxwell_model/geometry.py` / `build_25Nm_SPMSM.py` 里有 **4 处只在真机上验证过、
但尚未回灌到 scripts/main.py 模板**的手工修复：
  1. `SetModelUnits` 用 `"Units:="` 而不是 `"Length:="`
  2. `DuplicateAroundAxis` 必须带第 3 个参数 `["NAME:Options", ...]`
  3. 克隆体实名是 `Slot_1_1..Slot_1_11`，不是 `Slot_2..Slot_12`
  4. `CreatePolyline` 的点/段必须各自嵌进独立字典
空白重跑本脚本会把这 4 处改回旧写法，模型立刻变不可解。
`tests/test_prepare_batch.py::TestModelerApiRegressions` 与
`tests/test_model_depth.py::TestCombinedScriptApiFixes` 是护栏；
真要重跑，跑完必须逐条核对这两个测试类。
"""
import os
import sys
import math

# ---- 让本脚本能 import skill 的 scripts 模块 ----
SKILL_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SKILL_SCRIPTS))

from motor_config import MotorConfig, SlotType, PMTopology, MotorType
from main import MotorModelBuilder

# ---- 25Nm SPMSM 配置（与 pmsm_config.py 一致）----
cfg = MotorConfig(
    motor_type=MotorType.PMSM,
    rated_power_kw=3.93,
    rated_speed_rpm=1500.0,
    dc_bus_voltage_v=537.0,
    phases=3,

    slot_type=SlotType.RECTANGULAR,        # 25Nm 设计为平行壁矩形槽
    pm_topology=PMTopology.SPM,
    pole_pairs=4,
    slots=12,

    # 几何 (mm)
    stator_od=150.0,
    stator_id=93.0,
    rotor_od=91.65,
    rotor_id=30.0,
    airgap=0.675,
    stack_length=160.0,

    # 槽参数 (mm) — 映射自 pmsm_config 的平行壁矩形槽
    slot_Hs0=1.5,        # 槽口高度（楔部）
    slot_Bs0=2.5,        # 槽口宽度 bs0
    slot_Hs2=18.0,       # 槽深 hs3
    slot_Bs2=9.5,        # 槽身宽度 bs2

    # 永磁体 (mm)
    pm_thickness=1.95,
    pm_pole_arc=0.87,

    # 绕组
    turns_per_phase=81,
    conductors_per_slot=40,
    wire_diameter_mm=1.45,
    slot_fill_factor=0.40,

    # 电气
    rated_current_rms=9.89,
    frequency_hz=100.0,
    phase_resistance=0.48,
    phase_inductance=0.0038,

    # 材料
    stator_material="M270_35A",
    rotor_material="M270_35A",
    pm_material="N35",
    pm_br_20c=1.17,
    pm_hc_kam=890.0,
    pm_mur=1.05,
    conductor_material="copper",
    shaft_material="steel_stainless",
)

builder = MotorModelBuilder(cfg)
print("=" * 60)
print("25N·m SPMSM — Maxwell 2D 建模脚本生成")
print("=" * 60)
ok = builder.validate()
print(f"校验结果: {'通过' if ok else '存在错误'}")

scripts = builder.generate_all_scripts()

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maxwell_model")
os.makedirs(OUT_DIR, exist_ok=True)

# 写出 7 个分脚本
# 合并顺序必须 materials → geometry：Maxwell 里对象的 MaterialValue 引用必须已存在，
# 反序会让 build_25Nm_SPMSM.py 在 "SetMaterial" 处直接报 Unknown material。
# （2026-11-11 G3：旧顺序是 setup→geometry→materials，与 tests/test_prepare_batch.py
#  的 test_materials_before_geometry 冲突，本次一并纠正。）
order = ["setup", "materials", "geometry", "winding", "boundary", "mesh", "solver"]
written = []
for key in order:
    fname = f"{key}.py"
    fpath = os.path.join(OUT_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(scripts[key])
    written.append(fpath)
    print(f"  ✔ {fname}  ({len(scripts[key])} chars)")

# 合并为单一可直接在 Maxwell IronPython 控制台运行的脚本
combined = "# -*- coding: utf-8 -*-\n"
combined += f'"""\nANSYS Maxwell 2D 自动建模 — 25N·m SPMSM (8p12s)\n'
combined += f'定子外径 150mm / 内径 93mm / 叠长 160mm / 气隙 0.675mm\n'
combined += f'磁钢 N35 / 极弧系数 0.87 / 绕组 Kw=0.933\n'
combined += f'将本文件内容粘贴进 Maxwell 的 IronPython 控制台即可建模。\n"""\n\n'
for key in order:
    combined += f"\n# ============ {key.upper()} ============\n"
    combined += scripts[key] + "\n"

combined_path = os.path.join(OUT_DIR, "build_25Nm_SPMSM.py")
with open(combined_path, "w", encoding="utf-8") as f:
    f.write(combined)
written.append(combined_path)
print(f"  ✔ build_25Nm_SPMSM.py  (合并, {len(combined)} chars)")

print("=" * 60)
print(f"输出目录: {OUT_DIR}")
for w in written:
    print(f"  - {os.path.basename(w)}")
print("=" * 60)
