# -*- coding: utf-8 -*-
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
# PM 角点最大半径
for i in range(1, 5):
    nm = "PM_%d" % i
    verts = oEditor.GetVertexIDsFromObject(nm)
    maxr = 0
    for v in list(verts):
        p = oEditor.GetVertexPosition(v)
        r = math.hypot(float(p[0]), float(p[1]))
        maxr = max(maxr, r)
    out.append("%s max corner r=%.2f" % (nm, maxr))
# 线圈角点最大半径
for nm in ["A_1", "A_2", "C_12"]:
    verts = oEditor.GetVertexIDsFromObject(nm)
    maxr = 0
    for v in list(verts):
        p = oEditor.GetVertexPosition(v)
        r = math.hypot(float(p[0]), float(p[1]))
        maxr = max(maxr, r)
    out.append("%s max corner r=%.2f" % (nm, maxr))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_geom_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
