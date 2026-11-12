#!/usr/bin/env python3
"""Step 4: 线圈组与绕组定义 — 修复 v2: 真正用 builder.compute_winding() 的输出"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# ── 相位带分配表(从 builder 算出, AI 友好: print 出每槽位置 + 拓扑示意) ──
# slots=12, poles=8, q=1.00, layers=LayerType.DOUBLE
# 绕组系数 kw = 0.8660
#
# 算法 (整数槽分布式 Pyrhonen 公式):
#   相 = (slot_idx * pole_pairs) // (slots // 3)  mod 3
#   极性 = '+' if (slot_idx // q) % 2 == 0 else '-'
# 集中绕组 (q=0.5): 槽电角 120°/槽 → A+B-C+A-B+C- 循环
print("=" * 60)
print("  绕组位置分配表 (Phase-Belt Allocation)")
print("  slots=12  poles=8  q=1.00  layers=LayerType.DOUBLE")
print("=" * 60)
print("  槽号  相+/极性  拓扑示意  备注")
print(f"  Slot_ 1   A+    [A+] ★   上 N 极下")
print(f"  Slot_ 2   A-    [A-] ·   下 S 极下")
print(f"  Slot_ 3   B+    [B+] ★   上 N 极下")
print(f"  Slot_ 4   B-    [B-] ·   下 S 极下")
print(f"  Slot_ 5   C+    [C+] ★   上 N 极下")
print(f"  Slot_ 6   C-    [C-] ·   下 S 极下")
print(f"  Slot_ 7   A+    [A+] ★   上 N 极下")
print(f"  Slot_ 8   A-    [A-] ·   下 S 极下")
print(f"  Slot_ 9   B+    [B+] ★   上 N 极下")
print(f"  Slot_10   B-    [B-] ·   下 S 极下")
print(f"  Slot_11   C+    [C+] ★   上 N 极下")
print(f"  Slot_12   C-    [C-] ·   下 S 极下")
print("=" * 60)
print("  说明: ★ = 电流方向 + (N 极下); · = 电流方向 - (S 极下)")
print("  每个槽边 = 一个 Coil 对象 = 一个 AssignCoil（直接挂 Winding:=）")
print("  同一相 +/- 的槽边共用同一个 WindingX，靠 PolarityType 定方向")

# ── Step 1: 定义三相绕组 ──
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

# ── Step 2: 逐槽边 AssignCoil（每对象一个，直接挂 Winding:=）──
oModule.AssignCoil(
    ["NAME:A_1",
     "Objects:=", ["Coil_1"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_7",
     "Objects:=", ["Coil_7"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_2",
     "Objects:=", ["Coil_2"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:A_8",
     "Objects:=", ["Coil_8"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingA"])

oModule.AssignCoil(
    ["NAME:B_3",
     "Objects:=", ["Coil_3"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_9",
     "Objects:=", ["Coil_9"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_4",
     "Objects:=", ["Coil_4"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:B_10",
     "Objects:=", ["Coil_10"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingB"])

oModule.AssignCoil(
    ["NAME:C_5",
     "Objects:=", ["Coil_5"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_11",
     "Objects:=", ["Coil_11"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_6",
     "Objects:=", ["Coil_6"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingC"])

oModule.AssignCoil(
    ["NAME:C_12",
     "Objects:=", ["Coil_12"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative",
     "Winding:=", "WindingC"])


print("Winding assignment complete: 12 slots, 8 poles, 3 phases")
print(f"  Winding factor kw = 0.8660")
print(f"  Coil groups: A+=1 A-=1 B+=1 B-=1 C+=1 C-=1")
print(f"  Layout source = canonical  (真值表 references/winding_layouts.md)")
print(f"  Polarity convention = standard  (A+→Positive, A-→Negative)")
