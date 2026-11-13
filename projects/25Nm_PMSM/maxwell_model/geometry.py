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
