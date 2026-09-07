# -*- coding: utf-8 -*-
"""重建 36 个线圈：先画在 0 度槽中心线上，再旋转到各槽角度"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

# 槽参数：槽口 r=68（定子内径），槽底 r=68+0.8+1.5+11.5+4.15=85.95？
# 实际槽深: hs0=0.8, hs1=1.5, hs2=11.5, rs=4.15 -> 槽底 x3 = 68+0.8+1.5+4.15 = 74.45
# 槽底半径 = sqrt(74.45^2 - (bs2/2)^2) ≈ 74.4，槽口 68
# 线圈放槽中部: 径向 r 68.8 ~ 73.8（5mm 厚），切向宽 2.5mm（< 槽口 3.5mm）
r_coil_in = 68.8
r_coil_out = 73.8
coil_w = 2.5          # 切向宽度
coil_h = r_coil_out - r_coil_in  # 径向厚度 5.0

# 36 个线圈命名（与绕组脚本一致）
names = []
for prefix, grp in [("A", range(1, 7)), ("A", range(7, 13)),
                    ("B", range(1, 7)), ("B", range(7, 13)),
                    ("C", range(1, 7)), ("C", range(7, 13))]:
    for i in grp:
        names.append("%s_%d" % (prefix, i))
assert len(names) == 36

# 槽中心半径（0度槽的槽中心线在 X 轴上，槽深方向沿 X）
r_mid = (r_coil_in + r_coil_out) / 2.0

for k in range(36):
    angle = k * 10.0   # 槽 k 的中心角
    nm = names[k]
    # 先在 0 度位置画矩形：中心在 (r_mid, 0)，宽=coil_w(切向/Y)，高=coil_h(径向/X)
    # CreateRectangle 的 XStart/YStart 是左下角
    # 径向沿 X: X 从 r_coil_in 到 r_coil_out; 切向沿 Y: Y 从 -coil_w/2 到 +coil_w/2
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(r_coil_in) + "mm",
         "YStart:=", str(-coil_w/2) + "mm",
         "ZStart:=", "0mm",
         "Width:=", str(coil_h) + "mm",
         "Height:=", str(coil_w) + "mm",
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

print("Coils rebuilt: %d" % len(names))
