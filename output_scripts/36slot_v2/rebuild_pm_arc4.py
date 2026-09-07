# -*- coding: utf-8 -*-
"""扇区 PM v4: 6 点 4 段（外弧/径线/内弧/闭合）"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")

r_in = 64.8
r_out = 67.8
half_arc = 38.25

def make_pm(name, mat, color):
    a0 = math.radians(-half_arc); a1 = math.radians(0.0); a2 = math.radians(half_arc)
    p0 = (r_out*math.cos(a0), r_out*math.sin(a0))
    p1 = (r_out*math.cos(a1), r_out*math.sin(a1))
    p2 = (r_out*math.cos(a2), r_out*math.sin(a2))
    p3 = (r_in*math.cos(a2), r_in*math.sin(a2))
    p4 = (r_in*math.cos(a1), r_in*math.sin(a1))
    p5 = (r_in*math.cos(a0), r_in*math.sin(a0))

    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,
         ["NAME:PolylinePoints",
          ["NAME:PLPoint", "X:=", "%.4fmm" % p0[0], "Y:=", "%.4fmm" % p0[1], "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "%.4fmm" % p1[0], "Y:=", "%.4fmm" % p1[1], "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "%.4fmm" % p2[0], "Y:=", "%.4fmm" % p2[1], "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "%.4fmm" % p3[0], "Y:=", "%.4fmm" % p3[1], "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "%.4fmm" % p4[0], "Y:=", "%.4fmm" % p4[1], "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "%.4fmm" % p5[0], "Y:=", "%.4fmm" % p5[1], "Z:=", "0mm"]],
         ["NAME:PolylineSegments",
          ["NAME:PLSegment", "SegmentType:=", "Arc", "StartIndex:=", 0, "NoOfPoints:=", 3],
          ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],
          ["NAME:PLSegment", "SegmentType:=", "Arc", "StartIndex:=", 3, "NoOfPoints:=", 3],
          ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2]]],
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
print("PM arc v4 done")
