# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
bs = oDesign.GetModule("BoundarySetup")
methods = [m for m in dir(bs)]
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_bs_out.txt", "w", encoding="utf-8")
f.write("BOUNDARY ALL: " + str(methods))
f.close()
