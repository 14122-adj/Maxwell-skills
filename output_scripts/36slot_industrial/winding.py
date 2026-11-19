#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 线圈组与绕组定义 — 8p36s (v4 修复: AssignCoilGroup 调用形式 + 名称一致性)

[修复历史]
  v3 修极性反向 bug (A+→Positive, A-→Negative)。
  v4 修两处致命缺陷:
    1. old: AssignCoilGroup 传了两个位置参数 (多出一个组名列表)。
       Maxwell COM 的 AssignCoilGroup 只接受单个数组参数 → TypeError。
       new: 只传一个数组, 首元素 "NAME:组名"。
    2. old: 组名 "A+" 但 AddWindingCoils 引用 "A+_1".., 名称不一致 → 激励加不上。
       new: 组名统一 A+/A-/B+/B-/C+/C-, AddWindingCoils 引用同名组。
    3. 线圈截面对象须先存在 (见同目录 coils.py), 对象名 A_1..C_12 与 coils.py 对齐。

[本项目槽位图 (legacy 12-槽每段模式)]
  slot:   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35
  coil:   A1 A2 A3 A4 A5 A6 A7 A8 A9 A10 A11 A12 B1 B2 ... B12 C1 C2 ... C12
  group:  A+(0-5)  A-(6-11)  B+(12-17)  B-(18-23)  C+(24-29)  C-(30-35)
"""
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

# 线圈组赋值 (standard 约定: A+/B+/C+ → Positive, A-/B-/C- → Negative)
# v4: 单数组参数 + 组名一致

# A+组: slots 0-5 = A_1..A_6
oModule.AssignCoilGroup(
    ["NAME:A+",
     "Objects:=", ["A_1", "A_2", "A_3", "A_4", "A_5", "A_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# A-组: slots 6-11 = A_7..A_12
oModule.AssignCoilGroup(
    ["NAME:A-",
     "Objects:=", ["A_7", "A_8", "A_9", "A_10", "A_11", "A_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# B+组: slots 12-17 = B_1..B_6
oModule.AssignCoilGroup(
    ["NAME:B+",
     "Objects:=", ["B_1", "B_2", "B_3", "B_4", "B_5", "B_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# B-组: slots 18-23 = B_7..B_12
oModule.AssignCoilGroup(
    ["NAME:B-",
     "Objects:=", ["B_7", "B_8", "B_9", "B_10", "B_11", "B_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# C+组: slots 24-29 = C_1..C_6
oModule.AssignCoilGroup(
    ["NAME:C+",
     "Objects:=", ["C_1", "C_2", "C_3", "C_4", "C_5", "C_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])

# C-组: slots 30-35 = C_7..C_12
oModule.AssignCoilGroup(
    ["NAME:C-",
     "Objects:=", ["C_7", "C_8", "C_9", "C_10", "C_11", "C_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])

# 连接线圈组到绕组 (v4: 引用组名, 与 AssignCoilGroup 的 NAME 一致)
oModule.AddWindingCoils("WindingA", ["A+", "A-"])
oModule.AddWindingCoils("WindingB", ["B+", "B-"])
oModule.AddWindingCoils("WindingC", ["C+", "C-"])

print("Winding assignment complete: 36 slots, 8 poles, 3 phases")
print("  Polarity convention: standard (A+→Positive, A-→Negative)")
print("  Pattern: legacy 12-slot segment (NOT canonical 8p36s; see references/winding_layouts.md)")
print("  Winding factor: 0.96 (target; actual may differ due to legacy pattern)")