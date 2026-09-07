# -*- coding: utf-8 -*-
"""运行 Setup1 瞬态仿真（oDesign.Analyze）"""
import ScriptEnv, time
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
start = time.time()
oDesign.Analyze("Setup1")
elapsed = time.time() - start
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\analysis_done.txt", "w", encoding="utf-8")
f.write("Analyze Setup1 completed in %.1f s" % elapsed)
f.close()
