# -*- coding: utf-8 -*-
"""在36个槽内创建线圈截面（copper），命名 A_1..A_12, B_1..B_12, C_1..C_12"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

# 线圈尺寸（槽内矩形，位于槽中部）
r_mid = 71.0          # 线圈中心半径
coil_w = 3.2          # 线圈宽度（周向，mm）
coil_h = 4.0          # 线圈厚度（径向，mm）

# 36个线圈命名，按 winding.py 的分组
names = []
for prefix, grp in [("A", range(1, 7)), ("A", range(7, 13)),
                    ("B", range(1, 7)), ("B", range(7, 13)),
                    ("C", range(1, 7)), ("C", range(7, 13))]:
    for i in grp:
        names.append("%s_%d" % (prefix, i))
assert len(names) == 36, len(names)

for k in range(36):
    angle = k * 10.0  # 槽中心角（deg）
    theta = math.radians(angle)
    cx = r_mid * math.cos(theta)
    cy = r_mid * math.sin(theta)
    nm = names[k]
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(cx) + "mm",
         "YStart:=", str(cy) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(coil_w) + "mm",
         "Height:=", str(coil_h) + "mm",
         "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", nm, "Flags:=", "", "Color:=", "(255 128 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"copper"', "SolveInside:=", True])
    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", nm],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])
print("Coils created: %d" % len(names))
