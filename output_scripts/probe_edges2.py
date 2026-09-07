# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
methods = [m for m in dir(oEditor) if "Edge" in m or "Face" in m or "Vertex" in m]
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_edges_out.txt", "w", encoding="utf-8")
f.write("editor edge/face methods: " + str(methods))
f.close()
