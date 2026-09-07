#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 3: 几何建模"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.SetModelUnits(["NAME:Units Parameter", "Units:=", "mm", "Rescale:=", False])

# Region（外部边界）
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "125.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",
     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "105.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Stator inner
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "68.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorInner", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Slot creation (pear type)
x0 = 68.0
bs0 = 3.5
bs1 = 6.2
bs2 = 8.3
hs0 = 0.8
hs1 = 1.5
hs2 = 11.5
rs = 4.15

x1 = x0 + hs0
x2 = x0 + hs0 + hs1
x3 = x0 + hs0 + hs1 + rs

oEditor.CreatePolyline(
    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,
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
      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 7, "NoOfPoints:=", 2]]],
    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Slot creation (pear type)
x0 = 68.0
bs0 = 3.5
bs1 = 6.2
bs2 = 8.3
hs0 = 0.8
hs1 = 1.5
hs2 = 11.5
rs = 4.15

x1 = x0 + hs0
x2 = x0 + hs0 + hs1
x3 = x0 + hs0 + hs1 + rs


# Duplicate slots
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "10.0deg", "Numclones:=", "36"])

# Subtract slots from stator
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", "Slot_1, Slot_2, Slot_3, Slot_4, Slot_5, Slot_6, Slot_7, Slot_8, Slot_9, Slot_10, Slot_11, Slot_12, Slot_13, Slot_14, Slot_15, Slot_16, Slot_17, Slot_18, Slot_19, Slot_20, Slot_21, Slot_22, Slot_23, Slot_24, Slot_25, Slot_26, Slot_27, Slot_28, Slot_29, Slot_30, Slot_31, Slot_32, Slot_33, Slot_34, Slot_35, Slot_36"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Rotor outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "67.8mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# Shaft
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "24.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# PMs (N/S alternating)
pm_pitch = 90.0
pa = 0.85
pm_r = 67.8
pm_w = 3.0
pm_h = pm_r * 2 * math.sin(math.radians(pa * pm_pitch / 2))

for i in range(4):
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
band_r = (135.6 + 136) / 4.0
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

print("Geometry done: 36 slots, 4 PMs, Band")
