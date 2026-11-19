# -*- coding: utf-8 -*-
"""在36个槽内创建线圈截面（copper），命名 A_1..A_12, B_1..B_12, C_1..C_12。
与 winding.py 引用的对象名对齐；先运行本脚本再运行 winding.py，绕组激励才能加成功。"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

# 线圈尺寸（槽内矩形，居中于槽中心线；几何来自 geometry.py: stator_id=136, 梨形槽
# x0=68, hs0=0.8, hs1=1.5, hs2=11.5, rs=4.15, bs2=8.3）
r_mid = 71.0          # 线圈中心半径（槽深中段，x1+x3 中点 ≈ 71.2）
coil_w = 3.2          # 线圈径向厚度（Width，mm）
coil_h = 4.0          # 线圈周向宽度（Height，mm）

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
    # 起点用矩形中心折算的左下角，使线圈绕槽中心线对称（避免偏心伸出槽外）
    x_start = cx - coil_w / 2.0
    y_start = cy - coil_h / 2.0
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(x_start) + "mm",
         "YStart:=", str(y_start) + "mm",
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