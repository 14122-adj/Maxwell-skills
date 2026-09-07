#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 5: 边界条件与运动设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# 零矢势边界（定子外边界）
oModule.AssignVectorPotential(
    ["NAME:VectorPotential1",
     "Edges:=", [718],
     "Objects:=", [],
     "Value:=", "0"])

print("Boundary: VectorPotential=0 on Region")

# 运动设置
oDesign.GetModule("ModelSetup").AssignBand(
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

print("Motion band set: 1500rpm")
