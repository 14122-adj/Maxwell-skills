# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
# 测试格式1: 嵌套数组作为 PolylineParameters 的子元素（无 key）
try:
    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,
         ["NAME:PolylinePoints",
          ["NAME:PLPoint", "X:=", "70mm", "Y:=", "-2mm", "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "75mm", "Y:=", "0mm", "Z:=", "0mm"],
          ["NAME:PLPoint", "X:=", "70mm", "Y:=", "2mm", "Z:=", "0mm"]],
         ["NAME:PolylineSegments",
          ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
          ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2]]],
        ["NAME:Attributes", "Name:=", "Probe_Slot", "Flags:=", "", "Color:=", "(0 200 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
    print("FORMAT1_OK")
except Exception as e:
    print("FORMAT1_FAIL:", str(e)[:200])
