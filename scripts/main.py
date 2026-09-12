#!/usr/bin/env python3
"""
ANSYS Maxwell 电机自动化建模 - 主入口
支持多槽型/多永磁拓扑切换的一键建模
支持自定义参数输入

使用方法：
    python main.py --preset 8p36s_tutorial
    python main.py --params "slots=36 poles=8 stator_od=210"
    python main.py --json '{"slots":36,"poles":8,"stator_od":210}'
    python main.py --csv params.csv
"""

import sys
import os
import argparse
import json
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_config import MotorConfig, SlotType, PMTopology, MotorType, create_motor_from_input
from pmsm_winding_builder import WindingBuilder, LayerType


class MotorModelBuilder:
    """电机模型自动化建模器"""

    def __init__(self, config: MotorConfig):
        self.config = config
        self.scripts = {}

    def validate(self):
        c = self.config
        issues = c.validate()

        errors = [i for i in issues if i.startswith("ERROR")]
        warnings = [i for i in issues if i.startswith("WARNING")]

        if errors:
            for e in errors:
                print(e)
            return False

        for w in warnings:
            print(w)

        print("[OK] 参数校验通过")
        return True

    def generate_all_scripts(self):
        """生成全部Maxwell脚本"""
        c = self.config
        pole_pitch = 360.0 / c.slots
        pm_pitch = 360.0 / c.poles
        freq = c.pole_pairs * c.rated_speed_rpm / 60.0

        self.scripts["setup"] = self._gen_setup()
        self.scripts["materials"] = self._gen_materials()
        self.scripts["geometry"] = self._gen_geometry()
        self.scripts["winding"] = self._gen_winding()
        self.scripts["boundary"] = self._gen_boundary(freq)
        self.scripts["mesh"] = self._gen_mesh()
        self.scripts["solver"] = self._gen_solver(freq)

        return self.scripts

    def _gen_setup(self):
        c = self.config
        return f'''#!/usr/bin/env python3
"""Step 1: 项目设置 — 修复 NewProject 弹"是否保存"对话框的问题"""
import ScriptEnv
import time

ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()

# ── 修复:避免 AEDT 启动后弹"最近文件/Home"对话框卡死脚本 ──
#  1. 等 AEDT 启动稳定 (load screen/许可/启动画面)
time.sleep(3)

#  2. 主动关掉任何已打开的项目,避免后续 NewProject 触发"是否保存"弹窗
try:
    active = oDesktop.GetActiveProject()
    if active is not None:
        try:
            # ClearSavedFlag 让 AEDT 认为当前项目已保存,丢弃未保存修改
            active.ClearSavedFlag()
        except Exception:
            pass
        try:
            oDesktop.CloseProject(active.GetName())
        except Exception:
            pass
except Exception:
    # 无激活项目/启动尚未就绪 — 忽略,直接 NewProject
    pass

#  3. 关闭 Home / Recent Files 弹窗 (AEDT 2021+ 启动时常弹)
try:
    # 顺序点掉主窗口的 child dialog:典型 Home Screen 的标题是 "Home"
    for w in list(oDesktop.GetWindowNames()):
        title = (oDesktop.GetWindowTitle(w) or "").lower()
        if "home" in title or "recent" in title or "welcome" in title:
            try:
                oDesktop.CloseWindow(w)
            except Exception:
                pass
except Exception:
    pass

#  4. 现在安全新建项目 (overwrite=True 兜底,避免再有"覆盖?"弹窗)
oProject = oDesktop.NewProject()
oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
oDesign = oProject.SetActiveDesign("Motor_Design")
oDesign.SetDesignSettings(
    ["NAME:DesignSettingsData",
     "PreserveTransientSolution:=", False,
     "ComputeTransientInductance:=", True])
print("Setup done: {c.slots} slots, {c.poles} poles, {c.slot_type.value}, {c.pm_topology.value}")
'''

    def _gen_materials(self):
        c = self.config
        freq = c.pole_pairs * c.rated_speed_rpm / 60.0
        return f'''#!/usr/bin/env python3
"""Step 2: 自定义材料定义（N/S极磁钢）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDefinitionManager = oProject.GetDefinitionManager()

# N极磁钢（磁化方向径向向外）
oDefinitionManager.EditMaterial("{c.pm_material_n}",
    [
        "NAME:{c.pm_material_n}",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "{c.pm_conductivity}",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-{c.pm_hc_kam * 1000}A_per_meter",
            "DirComp1:=", "1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "{c.pm_mass_density}",
        "youngs_modulus:=", "147000000000",
    ])

# S极磁钢（磁化方向径向向内）
oDefinitionManager.EditMaterial("{c.pm_material_s}",
    [
        "NAME:{c.pm_material_s}",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "{c.pm_conductivity}",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-{c.pm_hc_kam * 1000}A_per_meter",
            "DirComp1:=", "-1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "{c.pm_mass_density}",
        "youngs_modulus:=", "147000000000",
    ])

print("Materials defined: {c.pm_material_n}, {c.pm_material_s}")
'''

    def _gen_geometry(self):
        """生成几何建模脚本"""
        c = self.config
        pole_pitch = 360.0 / c.slots
        pm_pitch = 360.0 / c.poles

        slot_names_str = ', '.join([f"Slot_{i}" for i in range(1, c.slots + 1)])

        s = f'''#!/usr/bin/env python3
"""Step 3: 几何建模"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.SetModelUnits(["NAME:UnitsSettings", "Length:=", "mm"])

# Region（外部边界）
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_od/2+20}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",
     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_od/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator inner
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_id/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorInner", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Slot creation (pear type)
x0 = {c.stator_id/2}
bs0 = {c.slot_Bs0}
bs1 = {c.slot_Bs1}
bs2 = {c.slot_Bs2}
hs0 = {c.slot_Hs0}
hs1 = {c.slot_Hs1}
hs2 = {c.slot_Hs2}
rs = {c.slot_Rs}

x1 = x0 + hs0
x2 = x0 + hs0 + hs1
x3 = x0 + hs0 + hs1 + rs

oEditor.CreatePolyline(
    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True],
    ["NAME:PolylinePoints",
     ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-bs0/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(-bs1/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(-bs2/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x3) + "mm", "Y:=", "0mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(bs2/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(bs1/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(bs0/2) + "mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-bs0/2) + "mm", "Z:=", "0mm"]],
    ["NAME:PolylineSegments",
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Arc", "StartIndex:=", 3, "NoOfPoints:=", 3],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 7, "NoOfPoints:=", 2]],
    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Duplicate slots
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "{pole_pitch}deg", "Numclones:=", "{c.slots}"])

# Subtract slots from stator
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", "{slot_names_str}"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Rotor outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.rotor_od/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Shaft
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.rotor_id/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# PMs (N/S alternating)
pm_pitch = {pm_pitch}
pa = {c.pm_pole_arc}
pm_r = {c.rotor_od/2}
pm_w = {c.pm_thickness}
pm_h = pm_r * 2 * math.sin(math.radians(pa * pm_pitch / 2))

for i in range({c.poles}):
    angle = i * pm_pitch
    if i % 2 == 0:
        mat = "{c.pm_material_n}"
        color = "(255 0 0)"
    else:
        mat = "{c.pm_material_s}"
        color = "(0 0 255)"
    pname = "PM_" + str(i + 1)

    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(pm_r) + "mm",
         "YStart:=", str(-pm_h/2) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(pm_w) + "mm",
         "Height:=", str(pm_h) + "mm",
         "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", pname, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"' + mat + '"', "SolveInside:=", True])

    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", pname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])

# Band（气隙中心）
band_r = ({c.rotor_od} + {c.stator_id}) / 4.0
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

print("Geometry done: {c.slots} slots, {c.poles} PMs, Band")
'''
        return s

    def _gen_winding(self):
        """生成绕组脚本 — v4 修复: 与 canonical 真值表对齐
        + standard 极性约定 (A+→Positive, A-→Negative)

        演化史:
          v1 硬编码 A_1..A_12 / B_1..B_12 / C_1..C_12, 与 builder 算法脱节
          v2 模板用 builder.coil_groups 输出, 但 builder 算法对 8p12s 集中绕组有 bug
          v3 头部加"winding guide" + 槽位图 ASCII 示意
          v4 builder 改为 lookup-first, 数据源 = references/winding_layouts.md
             极性约定统一为 standard (A+→Positive, A-→Negative)
        """
        c = self.config
        from pmsm_winding_builder import WindingBuilder
        builder = WindingBuilder(
            slots=c.slots, poles=c.poles, phases=3,
            polarity_convention="standard",   # ★ 新约定: A+→Positive, A-→Negative
        )
        config = builder.compute_winding()

        # ── 按 builder 实际输出的 coil_groups 渲染 AssignCoilGroup ──
        # 每个 CoilGroup: phase, polarity ('+'|'-'), coil_indices, coil_names
        coil_group_blocks = []
        coil_name_blocks  = []
        # 在主进程算好每相 +/- 线圈组数(供 print 报告用)
        n_pos_neg = {p: {"+": 0, "-": 0} for p in ["A", "B", "C"]}
        for group in config.coil_groups:
            if not group.coil_indices:
                continue
            pol_str = builder.polarity_type(group.polarity)   # 走 builder 的标准约定
            coil_name = f"{group.phase}{group.polarity}"  # 例: "A+", "B-"
            coil_objs = ", ".join(f'"{n}"' for n in group.coil_names)
            coil_group_blocks.append(
                f'oModule.AssignCoilGroup(\n'
                f'    ["NAME:{coil_name}",\n'
                f'     "Objects:=", [{coil_objs}],\n'
                f'     "Conductor number:=", "{c.conductors_per_slot}",\n'
                f'     "PolarityType:=", "{pol_str}"])\n'
            )
            coil_name_blocks.append(f'    "{coil_name}"')
            n_pos_neg[group.phase][group.polarity] += 1
        coil_groups_py = "\n".join(coil_group_blocks)
        n_A_pos, n_A_neg = n_pos_neg["A"]["+"], n_pos_neg["A"]["-"]
        n_B_pos, n_B_neg = n_pos_neg["B"]["+"], n_pos_neg["B"]["-"]
        n_C_pos, n_C_neg = n_pos_neg["C"]["+"], n_pos_neg["C"]["-"]

        # ── AddWindingCoils: 把每相的 + / - 组连到 WindingX ──
        add_winding_lines = []
        for phase in ["A", "B", "C"]:
            phase_groups = [g for g in config.coil_groups
                            if g.phase == phase and g.coil_indices]
            names = ", ".join(f'"{g.phase}{g.polarity}"' for g in phase_groups)
            add_winding_lines.append(
                f'oModule.AddWindingCoils("Winding{phase}", [{names}])'
            )
        add_winding_py = "\n".join(add_winding_lines)

        # ── 相位带表(供人类/AI 阅读校对) ──
        # 输出多行 print, 每槽一行, 一目了然
        phase_belt_prints = []
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append(f'print("  绕组位置分配表 (Phase-Belt Allocation)")')
        phase_belt_prints.append(f'print("  slots={c.slots}  poles={c.poles}  q={c.slots/(c.poles/2)/3:.2f}  layers={builder.layer}")')
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append('print("  槽号  相+/极性  拓扑示意  备注")')
        # 极性星号: A+/B+/C+ → ★ (N 极下), A-/B-/C- → · (S 极下)
        for slot in range(c.slots):
            ph, pl = config.slot_map[slot]
            star = "★" if pl == '+' else "·"
            line_marker = f"[{ph}{pl}]"
            note = "上 N 极下" if pl == '+' else "下 S 极下"
            phase_belt_prints.append(
                f'print(f"  Slot_{slot+1:>2}   {ph}{pl}    {line_marker} {star}   {note}")'
            )
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append('print("  说明: ★ = 电流方向 + (N 极下); · = 电流方向 - (S 极下)")')
        phase_belt_prints.append('print("  同相/同极性的所有槽属于同一 AssignCoilGroup")')
        phase_belt_prints.append('print("  按 A+/A-/B+/B-/C+/C- 的顺序连到 WindingA/B/C")')
        phase_belt_py = "\n".join(phase_belt_prints)

        return f'''#!/usr/bin/env python3
"""Step 4: 线圈组与绕组定义 — 修复 v2: 真正用 builder.compute_winding() 的输出"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# ── 相位带分配表(从 builder 算出, AI 友好: print 出每槽位置 + 拓扑示意) ──
# slots={c.slots}, poles={c.poles}, q={c.slots/(c.poles/2)/3:.2f}, layers={builder.layer}
# 绕组系数 kw = {config.winding_factor:.4f}
#
# 算法 (整数槽分布式 Pyrhonen 公式):
#   相 = (slot_idx * pole_pairs) // (slots // 3)  mod 3
#   极性 = '+' if (slot_idx // q) % 2 == 0 else '-'
# 集中绕组 (q=0.5): 槽电角 120°/槽 → A+B-C+A-B+C- 循环
{phase_belt_py}

# ── Step 1: 定义三相绕组 ──
for phase in ["A", "B", "C"]:
    oModule.AssignWindingGroup(
        ["NAME:Winding" + phase,
         "Type:=", "Current",
         "IsSolid:=", False,
         "Current:=", "0A",
         "Resistance:=", "0.1ohm",
         "Inductance:=", "0.001H",
         "Voltage:=", "0V",
         "ParallelBranchesNum:=", "1"])

# ── Step 2: 线圈组赋值(按 builder.coil_groups 逐组) ──
{coil_groups_py}

# ── Step 3: 把线圈组连到对应相绕组 ──
{add_winding_py}

print("Winding assignment complete: {c.slots} slots, {c.poles} poles, 3 phases")
print(f"  Winding factor kw = {config.winding_factor:.4f}")
print(f"  Coil groups: A+={n_A_pos} A-={n_A_neg} B+={n_B_pos} B-={n_B_neg} C+={n_C_pos} C-={n_C_neg}")
print(f"  Layout source = {config.source}  ({'真值表 references/winding_layouts.md' if config.source=='canonical' else '⚠ fallback 算法, 请人工核对'})")
print(f"  Polarity convention = {builder.polarity_convention}  (A+→Positive, A-→Negative)")
'''

    def _gen_boundary(self, freq):
        c = self.config
        return f'''#!/usr/bin/env python3
"""Step 5: 边界条件与运动设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# 零矢势边界（定子外边界）
oModule.AssignVectorPotential(
    ["NAME:VectorPotential1",
     "Edges:=", [], "Objects:=", ["Region"],
     "Value:=", "0",
     "CoordinateSystem:=", ""])

print("Boundary: VectorPotential=0 on Region")

# 运动设置
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData",
     "Move Type:=", "Rotate",
     "Coordinate System:=", "Global",
     "Axis:=", "Z",
     "Is Positive:=", True,
     "InitPos:=", "0deg",
     "HasRotateLimit:=", False,
     "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "{c.rated_speed_rpm}rpm",
     "Objects:=", ["Band"]])

print("Motion band set: {c.rated_speed_rpm}rpm")
'''

    def _gen_mesh(self):
        c = self.config
        pm_list = ', '.join([f'"PM_{i}"' for i in range(1, c.poles + 1)])
        return f'''#!/usr/bin/env python3
"""Step 6: 网格设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("MeshSetup")

# 气隙网格
oModule.AssignSurfApproxOp(
    ["NAME:SurfApprox_Airgap",
     "Objects:=", ["Band"],
     "CurvedSurfaceApproxChoice:=", "ManualSettings",
     "SurfDevChoice:=", 2,
     "SurfDev:=", "{c.mesh_airgap}mm",
     "NormalDevChoice:=", 2,
     "NormalDev:=", "15deg"])

# 定转子网格
oModule.AssignLengthOp(
    ["NAME:Mesh_Stator",
     "Objects:=", ["StatorOuter"],
     "MaxLength:=", "{c.mesh_teeth}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_Rotor",
     "Objects:=", ["RotorOuter"],
     "MaxLength:=", "{c.mesh_yoke}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_PM",
     "Objects:=", [{pm_list}],
     "MaxLength:=", "{c.mesh_pm}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

print("Mesh configured")
'''

    def _gen_solver(self, freq):
        c = self.config
        stop_time = max(2.0 / freq, 0.02) if freq > 0 else 0.02
        time_step = max(1.0 / (freq * 200), 5e-5) if freq > 0 else 5e-5

        stop_str = f"{stop_time:.4f}"
        step_str = f"{time_step:.6f}"

        return f'''#!/usr/bin/env python3
"""Step 7: 求解器设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "{stop_str}s",
     "TimeStep:=", "{step_str}s",
     "SaveFieldsType:=", "Every N Steps",
     "N:=", "1",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, {stop_str}s / {step_str}s")
'''

    def export_scripts(self, output_dir):
        """导出脚本到文件"""
        os.makedirs(output_dir, exist_ok=True)
        order = ["setup", "materials", "geometry", "winding", "boundary", "mesh", "solver"]
        for name in order:
            if name in self.scripts and self.scripts[name]:
                filepath = os.path.join(output_dir, f"{name}.py")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(self.scripts[name])
                print(f"  Exported: {filepath}")

    def export_winding_report(self, output_dir):
        """导出绕组配置报告"""
        c = self.config
        from pmsm_winding_builder import WindingBuilder
        builder = WindingBuilder(slots=c.slots, poles=c.poles, phases=3)
        config = builder.compute_winding()

        report_path = os.path.join(output_dir, "winding_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("PMSM Winding Configuration Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"  Slots: {config.slots}\n")
            f.write(f"  Poles: {config.poles}\n")
            f.write(f"  q: {config.q:.2f}\n")
            f.write(f"  Winding factor: {config.winding_factor:.4f}\n")
            f.write(f"  Coil span: {config.coil_span}\n")
            f.write("\n  Coil Groups:\n")
            for group in config.coil_groups:
                if group.coil_indices:
                    f.write(f"    {group.phase}{group.polarity}: {len(group.coil_indices)} coils\n")
            f.write("=" * 60 + "\n")
        print(f"  Exported: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="ANSYS Maxwell Motor Auto-Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --preset 8p36s_tutorial
  python main.py --preset 8p12s_servo
  python main.py --params "slots=36 poles=8 stator_od=210 stator_id=136"
  python main.py --json '{"slots":36,"poles":8,"stator_od":210,"stator_id":136}'
  python main.py --csv "slots,36\\npoles,8\\nstator_od,210"
  python main.py --interactive
""")
    parser.add_argument("--preset", type=str,
                        choices=["8p12s_servo", "36slot_industrial", "8p12s_ipm_ev", "8p36s_tutorial"],
                        help="使用预设配置")
    parser.add_argument("--params", type=str, help="关键词参数: slots=36 poles=8")
    parser.add_argument("--json", type=str, help="JSON参数: '{\"slots\":36}'")
    parser.add_argument("--csv", type=str, help="CSV参数: slots,36")
    parser.add_argument("--input", type=str, help="从文件读取参数")
    parser.add_argument("--interactive", action="store_true", help="交互式输入模式")
    parser.add_argument("--output_dir", type=str, default="./output_scripts",
                        help="脚本输出目录 (default: ./output_scripts)")
    parser.add_argument("--validate_only", action="store_true",
                        help="仅验证参数，不生成脚本")
    parser.add_argument("--report", action="store_true",
                        help="是否生成绕组报告")

    args = parser.parse_args()

    # 确定配置来源
    config = None

    if args.preset:
        if args.preset == "8p12s_servo":
            from motor_config import create_8p12s_spm_servo
            config = create_8p12s_spm_servo()
        elif args.preset == "36slot_industrial":
            from motor_config import create_36slot_industrial
            config = create_36slot_industrial()
        elif args.preset == "8p12s_ipm_ev":
            from motor_config import create_8p12s_ipm_ev
            config = create_8p12s_ipm_ev()
        elif args.preset == "8p36s_tutorial":
            from motor_config import create_8p36s_tutorial
            config = create_8p36s_tutorial()
            # 8p36s使用教程模式的绕组参数
            config.conductors_per_slot = 45

    elif args.params:
        config = create_motor_from_input(args.params, input_type="keyword")

    elif args.json:
        config = create_motor_from_input(args.json, input_type="json")

    elif args.csv:
        config = create_motor_from_input(args.csv, input_type="csv")

    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            content = f.read()
        config = create_motor_from_input(content, input_type="auto")

    elif args.interactive:
        config = interactive_input()

    else:
        print("请指定参数来源（--preset, --params, --json, --csv, --interactive）")
        print("使用 --help 查看帮助")
        sys.exit(1)

    if config is None:
        print("[ERROR] 无法创建配置")
        sys.exit(1)

    print("=" * 60)
    print("ANSYS Maxwell 电机自动化建模")
    print("=" * 60)
    print(f"  槽型: {config.slot_type.value}")
    print(f"  永磁拓扑: {config.pm_topology.value}")
    print(f"  槽数/极数: {config.slots}/{config.poles}")
    print(f"  定子: {config.stator_od}mm / {config.stator_id}mm")
    print(f"  转子: {config.rotor_od}mm / {config.rotor_id}mm")
    print(f"  磁钢材料(N/S): {config.pm_material_n} / {config.pm_material_s}")
    print()

    builder = MotorModelBuilder(config)
    if not builder.validate():
        sys.exit(1)

    if args.validate_only:
        return

    builder.generate_all_scripts()
    print(f"\n导出到: {args.output_dir}")
    builder.export_scripts(args.output_dir)

    if args.report:
        builder.export_winding_report(args.output_dir)

    print("\n[DONE] 脚本生成成功！")
    print(f"\n可以在ANSYS Electronics Desktop中依次运行:")
    print(f"  1. {args.output_dir}/setup.py     - 项目设置")
    print(f"  2. {args.output_dir}/materials.py  - 材料定义")
    print(f"  3. {args.output_dir}/geometry.py   - 几何建模")
    print(f"  4. {args.output_dir}/winding.py    - 绕组定义")
    print(f"  5. {args.output_dir}/boundary.py   - 边界与运动")
    print(f"  6. {args.output_dir}/mesh.py       - 网格设置")
    print(f"  7. {args.output_dir}/solver.py     - 求解器设置")


def interactive_input():
    """交互式输入模式"""
    print("\n=== 交互式电机参数输入 ===")
    print("（直接回车使用默认值）\n")

    data = {}

    def prompt(msg, default, cast_func=None):
        val = input(f"  {msg} [{default}]: ").strip()
        if not val:
            val = default
        if cast_func:
            val = cast_func(val)
        return val

    data["motor_type"] = "PMSM"
    data["rated_power_kw"] = float(prompt("额定功率 (kW)", "2.2"))
    data["rated_speed_rpm"] = float(prompt("额定转速 (rpm)", "2000"))
    data["dc_bus_voltage_v"] = float(prompt("母线电压 (V)", "310"))
    data["slots"] = int(prompt("槽数", "36"))
    data["poles"] = int(prompt("极数", "8"))
    data["stator_od"] = float(prompt("定子外径 (mm)", "210.0"))
    data["stator_id"] = float(prompt("定子内径 (mm)", "136.0"))
    data["rotor_od"] = float(prompt("转子外径 (mm)", "135.2"))
    data["rotor_id"] = float(prompt("转子内径 (mm)", "48.0"))
    data["airgap"] = float(prompt("气隙 (mm)", "0.4"))
    data["stack_length"] = float(prompt("叠片长度 (mm)", "100"))
    data["pm_thickness"] = float(prompt("磁钢厚度 (mm)", "3.0"))
    data["pm_pole_arc"] = float(prompt("极弧系数", "0.85"))
    data["conductors_per_slot"] = int(prompt("每槽导体数", "45"))
    data["slot_fill_factor"] = float(prompt("槽满率", "0.45"))

    return MotorConfig.from_dict(data)


if __name__ == "__main__":
    main()
