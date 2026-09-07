# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
# 查询 Region 的面和边
try:
    faces = oEditor.GetFaceIDs("Region")
    out = "Region faces: " + str(list(faces))
except Exception as e:
    out = "GetFaceIDs err: " + str(e)
try:
    edges = oEditor.GetEdgeIDs("Region")
    out += "\nRegion edges: " + str(list(edges))
except Exception as e:
    out += "\nGetEdgeIDs err: " + str(e)
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_edges_out.txt", "w", encoding="utf-8")
f.write(out)
f.close()
