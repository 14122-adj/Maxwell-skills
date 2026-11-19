#!/usr/bin/env python3
"""Step 7: 求解器设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "0.0200s",
     "TimeStep:=", "0.000050s",
     "SaveFieldsType:=", "Every N Steps",
     # G4-B 实测（2026-11-19）：21.1 落盘的存场真值是
     #   SaveFieldsType='Every N Steps' + 'N Steps'='0'
     # 即"仅末时刻存场"（t=0.02 s 可查场，0.0105 s 查不到）。
     # 旧版这里写的 "N:=", "2" 是无效键：它既不报错也不生效，
     # 注释里"隔步存场 N=2"的说法与落盘值不符，已删除。
     # 正确键名未测出（已求解的工程上 InsertSetup 全部 raise，无法在解后改 setup），
     # 见 PROBLEM_LEDGER P17；改成多快照存场属未验证变更，须重解确认报表仍 401 行。
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, 0.0200s / 0.000050s")
