# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
faces = oEditor.GetFaceIDs("Region")
out = "Region faces: " + str(list(faces))
edges = oEditor.GetEdgeIDsFromFace(faces[0])
out += "\nRegion face edges: " + str(list(edges))
import io
f = io.open(r"D:\桌面\ANSYS MaxWell_skill\output_scripts\probe_edges_out.txt", "w", encoding="utf-8")
f.write(out)
f.close()
