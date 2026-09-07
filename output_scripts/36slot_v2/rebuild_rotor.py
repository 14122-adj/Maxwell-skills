# -*- coding: utf-8 -*-
"""重建转子+PM+Band+线圈（修正 PM 半径与线圈旋转中心）"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

# ========== 1. 转子铁心（外径 r=64.8，轴孔 r=24） ==========
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "64.8mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "24.0mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# ========== 2. 永磁体（r=64.8 -> 67.8，N/S 交替） ==========
pm_r_in = 64.8          # PM 内径（贴转子表面）
pm_thick = 3.0          # PM 厚度
pm_pitch = 90.0         # 4极 -> 90 度/极
pa = 0.85               # 极弧系数
pm_h = pm_r_in * 2 * math.sin(math.radians(pa * pm_pitch / 2))  # 弧长
for i in range(4):
    angle = i * pm_pitch
    if i % 2 == 0:
        mat = "NdFe35_N"; color = "(255 0 0)"
    else:
        mat = "NdFe35_S"; color = "(0 0 255)"
    pname = "PM_%d" % (i + 1)
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(pm_r_in) + "mm",
         "YStart:=", str(-pm_h/2) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(pm_thick) + "mm",
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

# ========== 3. Band（气隙中心 r=67.9） ==========
band_r = 67.9
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

print("Rotor+PM+Band rebuilt")
