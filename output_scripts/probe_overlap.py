# -*- coding: utf-8 -*-
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
# StatorOuter 顶点数
v = oEditor.GetVertexIDsFromObject("StatorOuter")
out.append("StatorOuter vertices: %d" % len(list(v)))
# Band 半径
v = oEditor.GetVertexIDsFromObject("Band")
maxr = 0
for vid in list(v):
    p = oEditor.GetVertexPosition(vid)
    maxr = max(maxr, math.hypot(float(p[0]), float(p[1])))
out.append("Band max r: %.2f" % maxr)
# 线圈与定子槽的空间检查: 线圈外角 73.81 vs 槽底 74.45
for nm in ["A_1", "B_7"]:
    v = oEditor.GetVertexIDsFromObject(nm)
    maxr = 0
    for vid in list(v):
        p = oEditor.GetVertexPosition(vid)
        maxr = max(maxr, math.hypot(float(p[0]), float(p[1])))
    out.append("%s max r: %.2f" % (nm, maxr))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_overlap_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
