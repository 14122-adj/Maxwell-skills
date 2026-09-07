# -*- coding: utf-8 -*-
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
for i in range(1, 5):
    nm = "PM_%d_2" % i
    verts = oEditor.GetVertexIDsFromObject(nm)
    pts = []
    maxr = 0
    for v in list(verts):
        p = oEditor.GetVertexPosition(v)
        r = math.hypot(float(p[0]), float(p[1]))
        maxr = max(maxr, r)
        pts.append((round(float(p[0]),2), round(float(p[1]),2)))
    out.append("%s: maxr=%.2f pts=%s" % (nm, maxr, pts))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_pm4_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
