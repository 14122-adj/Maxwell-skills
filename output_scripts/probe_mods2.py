# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
mesh = oDesign.GetModule("MeshSetup")
bs = oDesign.GetModule("BoundarySetup")
ms = oDesign.GetModule("ModelSetup")
as_ = oDesign.GetModule("AnalysisSetup")
out = []
out.append("MESH: " + str([m for m in dir(mesh) if "Assign" in m or "Length" in m or "Surf" in m]))
out.append("MODELSETUP: " + str([m for m in dir(ms) if "Band" in m or "Motion" in m or "Assign" in m]))
out.append("BOUNDARY: " + str([m for m in dir(bs) if "Vector" in m or "Boundary" in m or "Slave" in m]))
out.append("ANALYSIS: " + str([m for m in dir(as_) if "Setup" in m or "Insert" in m]))
oDesktop.AddMessage("", "probe_mods2", 0, "\n".join(out))
