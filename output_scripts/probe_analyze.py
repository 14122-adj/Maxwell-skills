# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
as_ = oDesign.GetModule("AnalysisSetup")
methods = [m for m in dir(as_)]
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_analyze_out.txt", "w", encoding="utf-8")
f.write("AnalysisSetup: " + str(methods) + "\n\n")
dmethods = [m for m in dir(oDesign) if "naly" in m or "olve" in m or "Validate" in m]
f.write("Design: " + str(dmethods))
f.close()
