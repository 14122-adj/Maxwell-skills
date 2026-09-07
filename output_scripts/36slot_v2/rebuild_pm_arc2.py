# -*- coding: utf-8 -*-
"""扇区 PM v2: 顶点序列首尾闭合（外弧->内弧->回到起点）"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

r_in = 64.8
r_out = 67.8
half_arc = 38.25   # 0.85*90/2 deg
step = 3.0

def make_pm(name, mat, color):
    # 外弧点 + 内弧点(反向) + 回到外弧起点(闭合)
    pts = []
    a = -half_arc
    while a <= half_arc + 1e-9:
        pts.append((r_out*math.cos(math.radians(a)), r_out*math.sin(math.radians(a))))
        a += step
    a = half_arc
    while a >= -half_arc - 1e-9:
        pts.append((r_in*math.cos(math.radians(a)), r_in*math.sin(math.radians(a))))
        a -= step
    # 不重复闭合点; IsPolylineClosed=True 自动闭合

    point_arr = ["NAME:PolylinePoints"]
    for (x, y) in pts:
        point_arr.append(["NAME:PLPoint", "X:=", "%.4fmm" % x, "Y:=", "%.4fmm" % y, "Z:=", "0mm"])
    seg_arr = ["NAME:PolylineSegments"]
    for i in range(len(pts) - 1):
        seg_arr.append(["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", i, "NoOfPoints:=", 2])

    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,
         point_arr, seg_arr],
        ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"' + mat + '"', "SolveInside:=", True])

for i in range(4):
    angle = i * 90.0
    if i % 2 == 0:
        mat = "NdFe35_N"; color = "(255 0 0)"
    else:
        mat = "NdFe35_S"; color = "(0 0 255)"
    pname = "PM_%d" % (i + 1)
    make_pm(pname, mat, color)
    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", pname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])
print("PM arcs done")
