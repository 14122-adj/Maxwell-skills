# -*- coding: utf-8 -*-
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
try:
    oEditor.DuplicateAroundAxis(
        ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
        ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
         "WhichAxis:=", "Z", "AngleStr:=", "10deg", "Numclones:=", "36"],
        ["NAME:Options", "DuplicateBoundaries:=", False, "DuplicateDSOs:=", False])
    print("DUP_OK")
except Exception as e:
    print("DUP_FAIL:", str(e)[:250])
