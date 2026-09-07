#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 6: 网格设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("MeshSetup")

# 气隙网格
oModule.AssignSurfApproxOp(
    ["NAME:SurfApprox_Airgap",
     "Objects:=", ["Band"],
     "CurvedSurfaceApproxChoice:=", "ManualSettings",
     "SurfDevChoice:=", 2,
     "SurfDev:=", "0.2mm",
     "NormalDevChoice:=", 2,
     "NormalDev:=", "15deg"])

# 定转子网格
oModule.AssignLengthOp(
    ["NAME:Mesh_Stator",
     "Objects:=", ["StatorOuter"],
     "MaxLength:=", "1.5mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_Rotor",
     "Objects:=", ["RotorOuter"],
     "MaxLength:=", "3.0mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_PM",
     "Objects:=", ["PM_1", "PM_2", "PM_3", "PM_4"],
     "MaxLength:=", "0.5mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

print("Mesh configured")
