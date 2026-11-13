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
     # G4：隔步存场（N=2）与 m4_build_solve.py 的全时长口径一致 ——
     # 报表采样点仍由求解步长决定（20 ms / 5e-5 s = 401 点），存场减半只影响
     # 磁盘占用与写盘耗时，不影响转矩/磁链曲线。
     "N:=", "2",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, 0.0200s / 0.000050s")
