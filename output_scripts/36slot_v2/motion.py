# -*- coding: utf-8 -*-
"""重新设置运动（Band 已重建，MotionSetup1 引用失效）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
ms = oDesign.GetModule("ModelSetup")
try:
    for n in list(ms.GetMotionSetupNames()):
        ms.DeleteMotionSetup(n)
except Exception:
    pass
ms.AssignBand(
    ["NAME:BandData",
     "Move Type:=", "Rotate",
     "Coordinate System:=", "Global",
     "Axis:=", "Z",
     "Is Positive:=", True,
     "InitPos:=", "0deg",
     "HasRotateLimit:=", False,
     "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "1500rpm",
     "Objects:=", ["Band"]])
print("motion reassigned")
