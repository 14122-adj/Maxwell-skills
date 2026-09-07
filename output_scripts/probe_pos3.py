# -*- coding: utf-8 -*-
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
def show(obj):
    verts = oEditor.GetVertexIDsFromObject(obj)
    pts = []
    for v in list(verts):
        p = oEditor.GetVertexPosition(v)
        pts.append((round(float(p[0]),2), round(float(p[1]),2)))
    # 计算中心角度与半径
    cx = sum(pt[0] for pt in pts)/len(pts)
    cy = sum(pt[1] for pt in pts)/len(pts)
    r = math.hypot(cx, cy)
    ang = math.degrees(math.atan2(cy, cx)) % 360
    out.append("%s: center_r=%.1f angle=%.1f pts=%s" % (obj, r, ang, pts))
for o in ["A_1", "A_2", "A_3", "A_10", "B_1", "C_1"]:
    show(o)
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_pos3_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
