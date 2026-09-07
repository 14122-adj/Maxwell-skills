# -*- coding: utf-8 -*-
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
for i in range(1, 5):
    nm = "Mag%d" % i
    verts = oEditor.GetVertexIDsFromObject(nm)
    pts = []
    maxr = 0
    for v in list(verts):
        p = oEditor.GetVertexPosition(v)
        r = math.hypot(float(p[0]), float(p[1]))
        maxr = max(maxr, r)
        pts.append((round(float(p[0]),1), round(float(p[1]),1)))
    # 中心角度
    cx = sum(pt[0] for pt in pts)/len(pts)
    cy = sum(pt[1] for pt in pts)/len(pts)
    ang = math.degrees(math.atan2(cy, cx)) % 360
    out.append("%s: maxr=%.2f center_angle=%.0f" % (nm, maxr, ang))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_mag_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
