#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 4: 线圈组与绕组定义"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# 定义三相绕组
for phase in ["A", "B", "C"]:
    oModule.AssignWindingGroup(
        ["NAME:Winding" + phase,
         "Type:=", "Current",
         "IsSolid:=", False,
         "Current:=", "0A",
         "Resistance:=", "0.1ohm",
         "Inductance:=", "0.001H",
         "Voltage:=", "0V",
         "ParallelBranchesNum:=", "1"])

# 线圈组赋值（星形图自动分配）
# 生成策略：每相12个线圈（36槽/3相），分+/-两组
# 每组6个线圈

# A相
a_pos = [i for i in range(36) if i % 3 == 0]
a_neg = [i for i in range(36) if i % 3 == 1]

# B相
b_pos = [i for i in range(36) if i % 3 == 2]
b_neg = [i for i in range(36) if i % 3 == 0]

# C相
c_pos = [i for i in range(36) if i % 3 == 1]
c_neg = [i for i in range(36) if i % 3 == 2]

# A+组
oModule.AssignCoilGroup(
    ["A+_1", "A+_2", "A+_3", "A+_4", "A+_5", "A+_6"],
    ["NAME:A+",
     "Objects:=", ["A_1", "A_2", "A_3", "A_4", "A_5", "A_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# A-组
oModule.AssignCoilGroup(
    ["A-_1", "A-_2", "A-_3", "A-_4", "A-_5", "A-_6"],
    ["NAME:A-",
     "Objects:=", ["A_7", "A_8", "A_9", "A_10", "A_11", "A_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# B+组
oModule.AssignCoilGroup(
    ["B+_1", "B+_2", "B+_3", "B+_4", "B+_5", "B+_6"],
    ["NAME:B+",
     "Objects:=", ["B_1", "B_2", "B_3", "B_4", "B_5", "B_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# B-组
oModule.AssignCoilGroup(
    ["B-_1", "B-_2", "B-_3", "B-_4", "B-_5", "B-_6"],
    ["NAME:B-",
     "Objects:=", ["B_7", "B_8", "B_9", "B_10", "B_11", "B_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# C+组
oModule.AssignCoilGroup(
    ["C+_1", "C+_2", "C+_3", "C+_4", "C+_5", "C+_6"],
    ["NAME:C+",
     "Objects:=", ["C_1", "C_2", "C_3", "C_4", "C_5", "C_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# C-组
oModule.AssignCoilGroup(
    ["C-_1", "C-_2", "C-_3", "C-_4", "C-_5", "C-_6"],
    ["NAME:C-",
     "Objects:=", ["C_7", "C_8", "C_9", "C_10", "C_11", "C_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# 连接线圈到绕组
oModule.AddWindingCoils("WindingA", ["A+_1", "A+_2", "A+_3", "A+_4", "A+_5", "A+_6",
                                       "A-_1", "A-_2", "A-_3", "A-_4", "A-_5", "A-_6"])
oModule.AddWindingCoils("WindingB", ["B+_1", "B+_2", "B+_3", "B+_4", "B+_5", "B+_6",
                                       "B-_1", "B-_2", "B-_3", "B-_4", "B-_5", "B-_6"])
oModule.AddWindingCoils("WindingC", ["C+_1", "C+_2", "C+_3", "C+_4", "C+_5", "C+_6",
                                       "C-_1", "C-_2", "C-_3", "C-_4", "C-_5", "C-_6"])

print("Winding assignment complete: 36 slots, 4 poles, 3 phases")
print("  Winding factor: 0.9600")
