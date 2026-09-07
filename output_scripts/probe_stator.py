# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
# 查看当前对象
print("ALL:", [a for a in dir(oEditor) if not a.startswith("_")][:20])
try:
    oEditor.CreateCircle(
        ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
         "ZCenter:=", "0mm", "Radius:=", "68.0mm", "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", "StatorInnerProbe", "Flags:=", "", "Color:=", "(132 132 193)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
    print("CREATE_OK")
except Exception as e:
    print("CREATE_FAIL:", str(e)[:300])
