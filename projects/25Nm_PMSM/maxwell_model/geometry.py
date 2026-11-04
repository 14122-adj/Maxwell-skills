#!/usr/bin/env python3
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
    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True],
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
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2]],
    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Duplicate slots
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "30.0deg", "Numclones:=", "12"])

# Subtract slots from stator
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", "Slot_1, Slot_2, Slot_3, Slot_4, Slot_5, Slot_6, Slot_7, Slot_8, Slot_9, Slot_10, Slot_11, Slot_12"],
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
