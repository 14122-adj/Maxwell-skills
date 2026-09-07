#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 7: 求解器设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "0.0400s",
     "TimeStep:=", "0.000100s",
     "SaveFieldsType:=", "Every N Steps",
     "N:=", "1",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, 0.0400s / 0.000100s")
