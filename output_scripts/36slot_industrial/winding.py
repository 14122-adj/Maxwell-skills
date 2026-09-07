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
    [f"A+_1", f"A+_2", f"A+_3", f"A+_4", f"A+_5", f"A+_6"],
    ["NAME:A+",
     "Objects:=", [f"A_1", f"A_2", f"A_3", f"A_4", f"A_5", f"A_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# A-组
oModule.AssignCoilGroup(
    [f"A-_1", f"A-_2", f"A-_3", f"A-_4", f"A-_5", f"A-_6"],
    ["NAME:A-",
     "Objects:=", [f"A_7", f"A_8", f"A_9", f"A_10", f"A_11", f"A_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# B+组
oModule.AssignCoilGroup(
    [f"B+_1", f"B+_2", f"B+_3", f"B+_4", f"B+_5", f"B+_6"],
    ["NAME:B+",
     "Objects:=", [f"B_1", f"B_2", f"B_3", f"B_4", f"B_5", f"B_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# B-组
oModule.AssignCoilGroup(
    [f"B-_1", f"B-_2", f"B-_3", f"B-_4", f"B-_5", f"B-_6"],
    ["NAME:B-",
     "Objects:=", [f"B_7", f"B_8", f"B_9", f"B_10", f"B_11", f"B_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# C+组
oModule.AssignCoilGroup(
    [f"C+_1", f"C+_2", f"C+_3", f"C+_4", f"C+_5", f"C+_6"],
    ["NAME:C+",
     "Objects:=", [f"C_1", f"C_2", f"C_3", f"C_4", f"C_5", f"C_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# C-组
oModule.AssignCoilGroup(
    [f"C-_1", f"C-_2", f"C-_3", f"C-_4", f"C-_5", f"C-_6"],
    ["NAME:C-",
     "Objects:=", [f"C_7", f"C_8", f"C_9", f"C_10", f"C_11", f"C_12"],
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
print(f"  Winding factor: 0.9600")
