# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
out = []
for obj in ["PM_1", "PM_2", "PM_3", "PM_4", "A_1", "A_2", "B_1", "C_1"]:
    try:
        # 获取对象的所有顶点
        verts = oEditor.GetVertexIDsFromObject(obj)
        pts = []
        for v in list(verts)[:4]:
            p = oEditor.GetVertexPosition(v)
            pts.append((round(float(p[0]),2), round(float(p[1]),2)))
        out.append("%s: %s" % (obj, pts))
    except Exception as e:
        out.append("%s: ERR %s" % (obj, str(e)[:100]))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_pos_out.txt", "w", encoding="utf-8")
f.write("\n".join(out))
f.close()
