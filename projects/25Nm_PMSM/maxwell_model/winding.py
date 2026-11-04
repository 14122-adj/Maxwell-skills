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
print("  同相/同极性的所有槽属于同一 AssignCoilGroup")
print("  按 A+/A-/B+/B-/C+/C- 的顺序连到 WindingA/B/C")

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

# ── Step 2: 线圈组赋值(按 builder.coil_groups 逐组) ──
oModule.AssignCoilGroup(
    ["NAME:A+",
     "Objects:=", ["Coil_1", "Coil_7"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:A-",
     "Objects:=", ["Coil_2", "Coil_8"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])

oModule.AssignCoilGroup(
    ["NAME:B+",
     "Objects:=", ["Coil_3", "Coil_9"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:B-",
     "Objects:=", ["Coil_4", "Coil_10"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])

oModule.AssignCoilGroup(
    ["NAME:C+",
     "Objects:=", ["Coil_5", "Coil_11"],
     "Conductor number:=", "40",
     "PolarityType:=", "Positive"])

oModule.AssignCoilGroup(
    ["NAME:C-",
     "Objects:=", ["Coil_6", "Coil_12"],
     "Conductor number:=", "40",
     "PolarityType:=", "Negative"])


# ── Step 3: 把线圈组连到对应相绕组 ──
oModule.AddWindingCoils("WindingA", ["A+", "A-"])
oModule.AddWindingCoils("WindingB", ["B+", "B-"])
oModule.AddWindingCoils("WindingC", ["C+", "C-"])

print("Winding assignment complete: 12 slots, 8 poles, 3 phases")
print(f"  Winding factor kw = 0.8660")
print(f"  Coil groups: A+=1 A-=1 B+=1 B-=1 C+=1 C-=1")
print(f"  Layout source = canonical  (真值表 references/winding_layouts.md)")
print(f"  Polarity convention = standard  (A+→Positive, A-→Negative)")
