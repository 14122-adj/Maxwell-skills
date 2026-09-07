# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
methods = [m for m in dir(oEditor) if "Arc" in m or "Circle" in m or "Regular" in m or "Spline" in m or "Polyline" in m]
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_arc_out.txt", "w", encoding="utf-8")
f.write(str(methods))
f.close()
