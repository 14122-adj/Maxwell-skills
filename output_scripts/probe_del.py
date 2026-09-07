# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
bs = oDesign.GetModule("BoundarySetup")
methods = [m for m in dir(bs) if "elet" in m or "xcit" in m or "Coil" in m]
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_del_out.txt", "w", encoding="utf-8")
f.write(str(methods))
f.close()
