# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
for obj in ["RotorOuter", "PM_1", "PM_2"]:
    verts = oEditor.GetVertexIDsFromObject(obj)
    pts = []
    for v in list(verts)[:4]:
        p = oEditor.GetVertexPosition(v)
        pts.append((round(float(p[0]),2), round(float(p[1]),2)))
    out.append("%s: %s" % (obj, pts))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_pos2_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
