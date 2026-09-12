#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 4: 线圈组与绕组定义 — 8p36s (v3 修复: 极性反向 bug)

[历史问题]
旧版 PolarityType 全反 (A+ → Negative, A- → Positive), 导致 BEMF 整流反向,
三相 BEMF 相序为负。本文件已按 references/winding_layouts.md §17.2 的 standard
约定修正: A+/B+/C+ → Positive, A-/B-/C- → Negative。

[本项目槽位图 (与 canonical 不同, 见下)]
本项目使用 legacy "A 在 0-11, B 在 12-23, C 在 24-35" 的 12-槽每段模式,
不是 60° 相带的标准 8p36s 分布绕组。MMF 含 3 次空间谐波, BEMF 较差。
如需教科书标准 8p36s, 请用 scripts/winding_layout.py 36 8 --maxwell 重新生成。

槽位图 (按 coils.py 顺序, 0-indexed):
  slot:   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35
  coil:   A1 A2 A3 A4 A5 A6 A7 A8 A9 A10 A11 A12 B1 B2 ... B12 C1 C2 ... C12
  group:  A+(slots 0-5)  A-(slots 6-11)  B+(12-17)  B-(18-23)  C+(24-29)  C-(30-35)
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
# 旧版 (v2 之前) 是反的, 本文件已修正
# A+组: slots 0-5 = A_1..A_6
oModule.AssignCoilGroup(
    [f"A+_1", f"A+_2", f"A+_3", f"A+_4", f"A+_5", f"A+_6"],
    ["NAME:A+",
     "Objects:=", [f"A_1", f"A_2", f"A_3", f"A_4", f"A_5", f"A_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])   # ← FIXED (旧版写的是 Negative)

# A-组: slots 6-11 = A_7..A_12
oModule.AssignCoilGroup(
    [f"A-_1", f"A-_2", f"A-_3", f"A-_4", f"A-_5", f"A-_6"],
    ["NAME:A-",
     "Objects:=", [f"A_7", f"A_8", f"A_9", f"A_10", f"A_11", f"A_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])   # ← FIXED (旧版写的是 Positive)

# B+组: slots 12-17 = B_1..B_6
oModule.AssignCoilGroup(
    [f"B+_1", f"B+_2", f"B+_3", f"B+_4", f"B+_5", f"B+_6"],
    ["NAME:B+",
     "Objects:=", [f"B_1", f"B_2", f"B_3", f"B_4", f"B_5", f"B_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])   # ← FIXED

# B-组: slots 18-23 = B_7..B_12
oModule.AssignCoilGroup(
    [f"B-_1", f"B-_2", f"B-_3", f"B-_4", f"B-_5", f"B-_6"],
    ["NAME:B-",
     "Objects:=", [f"B_7", f"B_8", f"B_9", f"B_10", f"B_11", f"B_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])   # ← FIXED

# C+组: slots 24-29 = C_1..C_6
oModule.AssignCoilGroup(
    [f"C+_1", f"C+_2", f"C+_3", f"C+_4", f"C+_5", f"C+_6"],
    ["NAME:C+",
     "Objects:=", [f"C_1", f"C_2", f"C_3", f"C_4", f"C_5", f"C_6"],
     "Conductor number:=", "35",
     "PolarityType:=", "Positive"])   # ← FIXED

# C-组: slots 30-35 = C_7..C_12
oModule.AssignCoilGroup(
    [f"C-_1", f"C-_2", f"C-_3", f"C-_4", f"C-_5", f"C-_6"],
    ["NAME:C-",
     "Objects:=", [f"C_7", f"C_8", f"C_9", f"C_10", f"C_11", f"C_12"],
     "Conductor number:=", "35",
     "PolarityType:=", "Negative"])   # ← FIXED

# 连接线圈到绕组
oModule.AddWindingCoils("WindingA", ["A+_1", "A+_2", "A+_3", "A+_4", "A+_5", "A+_6",
                                       "A-_1", "A-_2", "A-_3", "A-_4", "A-_5", "A-_6"])
oModule.AddWindingCoils("WindingB", ["B+_1", "B+_2", "B+_3", "B+_4", "B+_5", "B+_6",
                                       "B-_1", "B-_2", "B-_3", "B-_4", "B-_5", "B-_6"])
oModule.AddWindingCoils("WindingC", ["C+_1", "C+_2", "C+_3", "C+_4", "C+_5", "C+_6",
                                       "C-_1", "C-_2", "C-_3", "C-_4", "C-_5", "C-_6"])

print("Winding assignment complete: 36 slots, 8 poles, 3 phases")
print("  Polarity convention: standard (A+→Positive, A-→Negative)")
print("  Pattern: legacy 12-slot segment (NOT canonical 8p36s; see references/winding_layouts.md)")
print(f"  Winding factor: 0.96 (target; actual may differ due to legacy pattern)")
