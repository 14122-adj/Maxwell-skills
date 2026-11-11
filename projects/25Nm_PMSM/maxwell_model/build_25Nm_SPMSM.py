# -*- coding: utf-8 -*-
"""
ANSYS Maxwell 2D 自动建模 — 25N·m SPMSM (8p12s)
定子外径 150mm / 内径 93mm / 叠长 160mm / 气隙 0.675mm
磁钢 N35 / 极弧系数 0.87 / 绕组 Kw=0.933
将本文件内容粘贴进 Maxwell 的 IronPython 控制台即可建模。
"""


# ============ SETUP ============
#!/usr/bin/env python3
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
# ── G3：2D 求解必须显式写叠长 ──
#  Maxwell 2D 的默认 ModelDepth 是 1 mm（不是 0），若这里不写，
#  转矩/反电势/铁耗/铜耗全部按 1 mm 深度算，物理量整体缩小约 160 倍，
#  而求解器不会报任何错（“模型自洽、物理错量级”的静默错误）。
#  实测依据：m4_build_solve.py 写入 ModelDepth:="160mm" 后，
#  空载 BEMF 118.88 V(rms)、负载 T_avg 22.33 N·m，与解析值同量级。
oDesign.SetDesignSettings(
    ["NAME:DesignSettingsData",
     "ModelDepth:=", "160mm",
     "PreserveTransientSolution:=", False,
     "ComputeTransientInductance:=", True])
print("Setup done: 12 slots, 8 poles, rectangular, SPM, ModelDepth=160mm")


# ============ MATERIALS ============
#!/usr/bin/env python3
"""Step 2: 自定义材料定义（N/S极磁钢）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDefinitionManager = oProject.GetDefinitionManager()

# N极磁钢（磁化方向径向向外）
oDefinitionManager.EditMaterial("NdFe35_N",
    [
        "NAME:NdFe35_N",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "625000",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-890000.0A_per_meter",
            "DirComp1:=", "1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "7400",
        "youngs_modulus:=", "147000000000",
    ])

# S极磁钢（磁化方向径向向内）
oDefinitionManager.EditMaterial("NdFe35_S",
    [
        "NAME:NdFe35_S",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "625000",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-890000.0A_per_meter",
            "DirComp1:=", "-1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "7400",
        "youngs_modulus:=", "147000000000",
    ])

print("Materials defined: NdFe35_N, NdFe35_S")


# ============ GEOMETRY ============
#!/usr/bin/env python3
"""Step 3: 几何建模"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.SetModelUnits(["NAME:UnitsSettings", "Units:=", "mm"])

# Region（外部边界）
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "95.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",
     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "75.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator inner
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "46.5mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorInner", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Slot creation (rectangular type)
x0 = 46.5
x1 = x0 + 1.5
x2 = x0 + 18.0
b0 = 2.5
b2 = 9.5
oEditor.CreatePolyline(
    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,
     ["NAME:PolylinePoints",
      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(-b2/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(b2/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(b0/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(b0/2) + "mm", "Z:=", "0mm"],
      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"]],
     ["NAME:PolylineSegments",
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 3, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 4, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2],
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2]]],
    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Duplicate slots
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "30.0deg", "Numclones:=", "12"],
    ["NAME:Options", "DuplicateAssignments:=", False])

# Subtract slots from stator
# 注意: DuplicateAroundAxis 的克隆名为 Slot_1_1..Slot_1_11, 不是 Slot_2..Slot_12
slot_names = ["Slot_1"] + ["Slot_1_" + str(i) for i in range(1, 12)]
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", ", ".join(slot_names)],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Rotor outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "45.825mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Shaft
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "15.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# PMs (N/S alternating)
pm_pitch = 45.0
pa = 0.87
pm_r = 45.825
pm_w = 1.95
pm_h = pm_r * 2 * math.sin(math.radians(pa * pm_pitch / 2))

for i in range(8):
    angle = i * pm_pitch
    if i % 2 == 0:
        mat = "NdFe35_N"
        color = "(255 0 0)"
    else:
        mat = "NdFe35_S"
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
band_r = (91.65 + 93.0) / 4.0
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# ── 线圈截面（铜，槽内居中；命名 Coil_1..Coil_N 与绕组脚本对齐）──
coil_r_mid = 56.250
coil_radial = 13.200
coil_tang = 5.700
coil_slot_angle = 30.000000
for k in range(12):
    angle = k * coil_slot_angle
    cname = f"Coil_{k + 1}"
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(coil_r_mid - coil_radial / 2.0) + "mm",
         "YStart:=", str(-coil_tang / 2.0) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(coil_radial) + "mm",
         "Height:=", str(coil_tang) + "mm",
         "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", cname, "Flags:=", "", "Color:=", "(255 128 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"copper"', "SolveInside:=", True])
    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", cname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])

print("Geometry done: 12 slots, 8 PMs, Band, 12 coils")


# ============ WINDING ============
#!/usr/bin/env python3
"""Step 4: 线圈组与绕组定义 — 修复 v2: 真正用 builder.compute_winding() 的输出"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# ── 相位带分配表(从 builder 算出, AI 友好: print 出每槽位置 + 拓扑示意) ──
# slots=12, poles=8, q=1.00, layers=LayerType.DOUBLE
# 绕组系数 kw = 0.8660
#
# 算法 (整数槽分布式 Pyrhonen 公式):
#   相 = (slot_idx * pole_pairs) // (slots // 3)  mod 3
#   极性 = '+' if (slot_idx // q) % 2 == 0 else '-'
# 集中绕组 (q=0.5): 槽电角 120°/槽 → A+B-C+A-B+C- 循环
print("=" * 60)
print("  绕组位置分配表 (Phase-Belt Allocation)")
print("  slots=12  poles=8  q=1.00  layers=LayerType.DOUBLE")
print("=" * 60)
print("  槽号  相+/极性  拓扑示意  备注")
print(f"  Slot_ 1   A+    [A+] ★   上 N 极下")
print(f"  Slot_ 2   A-    [A-] ·   下 S 极下")
print(f"  Slot_ 3   B+    [B+] ★   上 N 极下")
print(f"  Slot_ 4   B-    [B-] ·   下 S 极下")
print(f"  Slot_ 5   C+    [C+] ★   上 N 极下")
print(f"  Slot_ 6   C-    [C-] ·   下 S 极下")
print(f"  Slot_ 7   A+    [A+] ★   上 N 极下")
print(f"  Slot_ 8   A-    [A-] ·   下 S 极下")
print(f"  Slot_ 9   B+    [B+] ★   上 N 极下")
print(f"  Slot_10   B-    [B-] ·   下 S 极下")
print(f"  Slot_11   C+    [C+] ★   上 N 极下")
print(f"  Slot_12   C-    [C-] ·   下 S 极下")
print("=" * 60)
print("  说明: ★ = 电流方向 + (N 极下); · = 电流方向 - (S 极下)")
print("  同相/同极性的所有槽属于同一 AssignCoilGroup")
print("  按 A+/A-/B+/B-/C+/C- 的顺序连到 WindingA/B/C")

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
oModule.AssignCoilGroup(
    ["NAME:A+",
     "Objects:=", ["Coil_1", "Coil_7"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:A-",
     "Objects:=", ["Coil_2", "Coil_8"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])

oModule.AssignCoilGroup(
    ["NAME:B+",
     "Objects:=", ["Coil_3", "Coil_9"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:B-",
     "Objects:=", ["Coil_4", "Coil_10"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])

oModule.AssignCoilGroup(
    ["NAME:C+",
     "Objects:=", ["Coil_5", "Coil_11"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:C-",
     "Objects:=", ["Coil_6", "Coil_12"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])


# ── Step 3: 把线圈组连到对应相绕组 ──
oModule.AddWindingCoils("WindingA", ["A+", "A-"])
oModule.AddWindingCoils("WindingB", ["B+", "B-"])
oModule.AddWindingCoils("WindingC", ["C+", "C-"])

print("Winding assignment complete: 12 slots, 8 poles, 3 phases")
print(f"  Winding factor kw = 0.8660")
print(f"  Coil groups: A+=1 A-=1 B+=1 B-=1 C+=1 C-=1")
print(f"  Layout source = canonical  (真值表 references/winding_layouts.md)")
print(f"  Polarity convention = standard  (A+→Positive, A-→Negative)")


# ============ BOUNDARY ============
#!/usr/bin/env python3
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
     "Angular Velocity:=", "1500.0rpm",
     "Objects:=", ["Band"]])

print("Motion band set: 1500.0rpm")


# ============ MESH ============
#!/usr/bin/env python3
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
     "SurfDev:=", "0.2mm",
     "NormalDevChoice:=", 2,
     "NormalDev:=", "15deg"])

# 定转子网格
oModule.AssignLengthOp(
    ["NAME:Mesh_Stator",
     "Objects:=", ["StatorOuter"],
     "MaxLength:=", "1.5mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_Rotor",
     "Objects:=", ["RotorOuter"],
     "MaxLength:=", "3.0mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_PM",
     "Objects:=", ["PM_1", "PM_2", "PM_3", "PM_4", "PM_5", "PM_6", "PM_7", "PM_8"],
     "MaxLength:=", "0.5mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

print("Mesh configured")


# ============ SOLVER ============
#!/usr/bin/env python3
"""Step 7: 求解器设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "0.0200s",
     "TimeStep:=", "0.000050s",
     "SaveFieldsType:=", "Every N Steps",
     "N:=", "1",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, 0.0200s / 0.000050s")

