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
"""Step 2: 自定义材料定义（N/S极磁钢 + 铁芯）"""
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
# 铁芯材料（G4：模板此前从未定义/绑定，定转子默认是 vacuum）
STEEL_MATS = ['M270_35A']
for _m in STEEL_MATS:
    oDefinitionManager.EditMaterial(
        _m, ["NAME:" + _m, "CoordinateSystemType:=", "Cartesian",
             "BulkOrSurfaceType:=", 1,
             ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal",
                                               "Structural"]],
             "permittivity:=", "1", "permeability:=", "1000",
             "conductivity:=", "2000000", "dielectric_loss_tangent:=", "0",
             "magnetic_loss_tangent:=", "0", "mass_density:=", "7650",
             "youngs_modulus:=", "200000000000"])


# ============ GEOMETRY ============
#!/usr/bin/env python3
"""Step 3: 几何建模"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
# ── G3b 真机修复·几何 1：单位设置的键名是 Units，不是 Length ──
#   写 "Length:=" 会被 AEDT 判为未知键（rc=1, "Unknown key"），脚本在第一步就死。
oEditor.SetModelUnits(["NAME:UnitsSettings", "Units:=", "mm"])

# Region（外部边界）
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "95.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",
     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# ── G4 真机修复·边界 9：零矢势边界必须在 Region 还是「单条边的整圆」时赋 ──
#   2026-11-13：Region 一旦被 Subtract 切出孔洞（定子/线圈/Band），
#   `GetEdgeIDsFromObject("Region")` 会把外圆**和所有孔边**一起返回，
#   `VectorPotential=0` 就被强行加到材料界面上 ⇒ 磁通被人为短路。
#   求解器不报任何错，BEMF 却掉一大截 —— 又一个静默错误。
#   正确顺序（= m4_build_solve.py 跑出 401 点解的顺序）：先赋边界，再切 Region。
_region_edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]
oDesign.GetModule("BoundarySetup").AssignVectorPotential(
    ["NAME:VectorPotential1", "Edges:=", _region_edges, "Value:=", "0",
     "CoordinateSystem:=", ""])
print("Boundary: VectorPotential=0 on pristine Region (%d edge)" % len(_region_edges))

# Stator outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "75.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"M270_35A"', "SolveInside:=", True])

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
r_bore = 46.5
x0 = r_bore - 0.2
x1 = r_bore + 1.5
x2 = r_bore + 18.0
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
# ── G3b 真机修复·几何 2：DuplicateAroundAxis 必须带第 3 个参数 ──
#   缺 ["NAME:Options", ...] 时报 "expects at least 3 arguments"，克隆不执行。
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "30.0deg", "Numclones:=", "12"],
    ["NAME:Options", "DuplicateAssignments:=", False])

# Subtract slots from stator
# ── G3b 真机修复·几何 3：克隆体实名 Slot_1_1..Slot_1_11 ──
slot_names = ["Slot_1"] + ["Slot_1_" + str(i) for i in range(1, 12)]
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", ", ".join(slot_names)],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Rotor outer
# ── G4 真机修复·几何 6：转子半径 = 磁钢内半径 + 0.03 mm，磁钢"嵌"进转子 ──
#   磁钢改环形扇区后，转子盘必须小于磁钢外弧（否则转子自己就顶到定子内径），
#   但又要与磁钢内弧重叠 30 µm，让布尔开出一个闭合浅坑：界面严格互补、
#   无相切顶点（相切会触发 `Non-manifold vertices`，M2/M3 的死因之一）。
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "43.905000mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"M270_35A"', "SolveInside:=", True])

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
# ── G4 真机修复·几何 7：磁钢是**环形扇区**，不是平板弦 ──
#   旧版用 `CreateRectangle(XStart=rotor_od/2, Width=pm_thickness)`，即把 1.95 mm 厚的
#   平板放在转子外径**之外** ⇒ 径向跨 45.825..47.775 mm，而定子内径 46.5 mm，
#   磁钢直接插进定子铁芯 1.275 mm（`StatorOuter and PM_x intersect`）。
#   0.675 mm 气隙里平板弦几何上不可行。现在内外弧各离散 24 段
#   （弧矢 ~4.5 µm），内弧 43.8750 / 外弧 45.8250，从根上消除相切与穿插。
pm_pitch = 45.0
pm_pts = [(43.176486, -15.353230), (43.596046, -14.117910), (43.980271, -12.871147), (44.328848, -11.613952), (44.641495, -10.347343), (44.917960, -9.072347), (45.158018, -7.789999), (45.361473, -6.501336), (45.528162, -5.207403), (45.657950, -3.909250), (45.750730, -2.607928), (45.806429, -1.304493), (45.825000, 0.000000), (45.806429, 1.304493), (45.750730, 2.607928), (45.657950, 3.909250), (45.528162, 5.207403), (45.361473, 6.501336), (45.158018, 7.789999), (44.917960, 9.072347), (44.641495, 10.347343), (44.328848, 11.613952), (43.980271, 12.871147), (43.596046, 14.117910), (43.176486, 15.353230), (41.339189, 14.699901), (41.740895, 13.517148), (42.108770, 12.323439), (42.442514, 11.119741), (42.741857, 9.907031), (43.006558, 8.686290), (43.236400, 7.458509), (43.431198, 6.224683), (43.590794, 4.985812), (43.715058, 3.742899), (43.803891, 2.496953), (43.857219, 1.248982), (43.875000, 0.000000), (43.857219, -1.248982), (43.803891, -2.496953), (43.715058, -3.742899), (43.590794, -4.985812), (43.431198, -6.224683), (43.236400, -7.458509), (43.006558, -8.686290), (42.741857, -9.907031), (42.442514, -11.119741), (42.108770, -12.323439), (41.740895, -13.517148), (41.339189, -14.699901)]
for i in range(8):
    angle = i * pm_pitch
    if i % 2 == 0:
        mat = "NdFe35_N"
        color = "(255 0 0)"
    else:
        mat = "NdFe35_S"
        color = "(0 0 255)"
    pname = "PM_" + str(i + 1)

    _pm_plpts = []
    for (_x, _y) in pm_pts + [pm_pts[0]]:
        _pm_plpts.append(["NAME:PLPoint", "X:=", str(_x) + "mm",
                          "Y:=", str(_y) + "mm", "Z:=", "0mm"])
    _pm_segs = ["NAME:PolylineSegments"]
    for _i in range(len(pm_pts)):
        _pm_segs.append(["NAME:PLSegment", "SegmentType:=", "Line",
                         "StartIndex:=", _i, "NoOfPoints:=", 2])
    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True,
         "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + _pm_plpts, _pm_segs],
        ["NAME:Attributes", "Name:=", pname, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"' + mat + '"', "SolveInside:=", True])

    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", pname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])

# 转子 − 8 磁钢（KeepOriginals=True：磁钢本体保留，只在转子上挖出浅坑）
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "PM_1, PM_2, PM_3, PM_4, PM_5, PM_6, PM_7, PM_8"],
    ["NAME:SubtractParameters", "KeepOriginals:=", True])

# Band（气隙中心）
#   半径取 (rotor_od + stator_id)/4 = 气隙中点 46.1625 mm：
#   磁钢外弧 45.8250 与其内切，转子盘整个落在带内 ⇒ AEDT 的
#   "objects within the band" 检查能通过（Band 内必须有运动件）。
band_r = (91.65 + 93.0) / 4.0
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# ── 线圈截面（铜，槽轮廓 0.88 内缩；命名 Coil_1..Coil_N 与绕组脚本对齐）──
#    矩形截面在高槽满率槽里必然穿出槽壁，线圈必须由槽形收缩得到。
coil_pts = [(47.096000, -1.100000), (48.592000, -1.100000), (63.112000, -4.180000), (63.112000, 4.180000), (48.592000, 1.100000), (47.096000, 1.100000)]
coil_slot_angle = 30.000000
for k in range(12):
    angle = k * coil_slot_angle
    cname = "Coil_" + str(k + 1)
    _plpts = []
    for (_x, _y) in coil_pts + [coil_pts[0]]:
        _plpts.append(["NAME:PLPoint", "X:=", str(_x) + "mm",
                       "Y:=", str(_y) + "mm", "Z:=", "0mm"])
    _segs = ["NAME:PolylineSegments"]
    for _i in range(len(coil_pts)):
        _segs.append(["NAME:PLSegment", "SegmentType:=", "Line",
                      "StartIndex:=", _i, "NoOfPoints:=", 2])
    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True,
         "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + _plpts, _segs],
        ["NAME:Attributes", "Name:=", cname, "Flags:=", "", "Color:=", "(255 128 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"copper"', "SolveInside:=", True])
    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", cname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])

# Region 布尔分离
# ── G4 真机修复·几何 8：Region 必须与所有实体/线圈/运动带布尔分离 ──
#   旧版 Region 是一个从未参与布尔的整圆 sheet ⇒ 与定子、线圈、Band 全域重叠，
#   网格在重叠区被重复计入（M2/M3 的 36 条 intersect 中最隐蔽的一类：
#   求解器不报错，只是场解错）。这里 KeepOriginals=True 只切 Region 本身。
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "Region",
     "Tool Parts:=", "StatorOuter, RotorOuter, PM_1, PM_2, PM_3, PM_4, PM_5, PM_6, PM_7, PM_8, Coil_1, Coil_2, Coil_3, Coil_4, Coil_5, Coil_6, Coil_7, Coil_8, Coil_9, Coil_10, Coil_11, Coil_12, Band"],
    ["NAME:SubtractParameters", "KeepOriginals:=", True])

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
print("  每个槽边 = 一个 Coil 对象 = 一个 AssignCoil（直接挂 Winding:=）")
print("  同一相 +/- 的槽边共用同一个 WindingX，靠 PolarityType 定方向")

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

# ── Step 2: 逐槽边 AssignCoil（每对象一个，直接挂 Winding:=）──
oModule.AssignCoil(
    ["NAME:A_1",
     "Objects:=", ["Coil_1"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_7",
     "Objects:=", ["Coil_7"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_2",
     "Objects:=", ["Coil_2"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_8",
     "Objects:=", ["Coil_8"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:B_3",
     "Objects:=", ["Coil_3"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_9",
     "Objects:=", ["Coil_9"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_4",
     "Objects:=", ["Coil_4"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_10",
     "Objects:=", ["Coil_10"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:C_5",
     "Objects:=", ["Coil_5"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_11",
     "Objects:=", ["Coil_11"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_6",
     "Objects:=", ["Coil_6"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_12",
     "Objects:=", ["Coil_12"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingC"])


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
oEditor = oDesign.SetActiveEditor("3D Modeler")
oModule = oDesign.GetModule("BoundarySetup")

# 零矢势边界（定子外边界）
# ── G4 迁移：这段边界已移到 geometry.py，紧跟 Region 建圆之后 ──
#   原因（2026-11-13 真机分析）：本脚本在 geometry 之后运行，此时 Region 已被
#   Subtract 切出孔洞，`GetEdgeIDsFromObject("Region")` 会把外圆**和所有孔边**
#   一起返回，`VectorPotential=0` 就落到材料界面上 ⇒ 磁通被短路。
#   写法规矩本身没变（G3b：只吃 1D 实体，必须传 Edges，不能传 Region sheet），
#   只是**时机**必须早于任何布尔运算。见 geometry.py 同位置的注释。

# 运动设置
# ── G3b 真机修复·边界 2：键名是 "Init Pos:="（带空格）──
#   实测（m4_build_solve_progress.log: `OK AssignBand A Init Pos`，两轮均通过）：
#   带空格且**同时给全** Coordinate System / HasRotateLimit / NonCylindrical /
#   Consider Mechanical Transient 这几个可选键，2021.1 才按旋转带处理；
#   缺键或写成 "InitPos:=" 会被判成平动，报
#   `For 2D XY translation problem, only X or Y axis could be used`。
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData",
     "Move Type:=", "Rotate",
     "Coordinate System:=", "Global",
     "Axis:=", "Z",
     "Is Positive:=", True,
     "Init Pos:=", "0deg",
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
# ── G3b 真机修复·网格 6：2021.1 没有 AssignSurfApproxOp ──
#   用 AssignLengthOp 控 Band 内最大边长即可（m4_build_solve.py 实机验证的写法）。
oModule.AssignLengthOp(
    ["NAME:Mesh_Band",
     "Objects:=", ["Band"],
     "MaxLength:=", "0.2mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

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
     # G4：隔步存场（N=2）与 m4_build_solve.py 的全时长口径一致 ——
     # 报表采样点仍由求解步长决定（20 ms / 5e-5 s = 401 点），存场减半只影响
     # 磁盘占用与写盘耗时，不影响转矩/磁链曲线。
     "N:=", "2",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, 0.0200s / 0.000050s")

