#!/usr/bin/env python3
"""Step 6: 网格设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("MeshSetup")

# 气隙网格
# ── G3b 真机修复·网格 6：2021.1 没有 AssignSurfApproxOp ──
#   用 AssignLengthOp 控 Band 内最大边长即可（m4_build_solve.py 实机验证的写法）。
oModule.AssignLengthOp(
    ["NAME:Mesh_Band",
     "Objects:=", ["Band"],
     "MaxLength:=", "0.2mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

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
     "Objects:=", ["PM_1", "PM_2", "PM_3", "PM_4", "PM_5", "PM_6", "PM_7", "PM_8"],
     "MaxLength:=", "0.5mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

print("Mesh configured")
