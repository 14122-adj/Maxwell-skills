#!/usr/bin/env python3
"""Step 5: 边界条件与运动设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oModule = oDesign.GetModule("BoundarySetup")

# 零矢势边界（定子外边界）
# ── G4 迁移：这段边界已移到 geometry.py，紧跟 Region 建圆之后 ──
#   原因（2026-11-13 真机分析）：本脚本在 geometry 之后运行，此时 Region 已被
#   Subtract 切出孔洞，`GetEdgeIDsFromObject("Region")` 会把外圆**和所有孔边**
#   一起返回，`VectorPotential=0` 就落到材料界面上 ⇒ 磁通被短路。
#   写法规矩本身没变（G3b：只吃 1D 实体，必须传 Edges，不能传 Region sheet），
#   只是**时机**必须早于任何布尔运算。见 geometry.py 同位置的注释。

# 运动设置
# ── G3b 真机修复·边界 2：键名是 "Init Pos:="（带空格）──
#   实测（m4_build_solve_progress.log: `OK AssignBand A Init Pos`，两轮均通过）：
#   带空格且**同时给全** Coordinate System / HasRotateLimit / NonCylindrical /
#   Consider Mechanical Transient 这几个可选键，2021.1 才按旋转带处理；
#   缺键或写成 "InitPos:=" 会被判成平动，报
#   `For 2D XY translation problem, only X or Y axis could be used`。
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData",
     "Move Type:=", "Rotate",
     "Coordinate System:=", "Global",
     "Axis:=", "Z",
     "Is Positive:=", True,
     "Init Pos:=", "0deg",
     "HasRotateLimit:=", False,
     "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "1500.0rpm",
     "Objects:=", ["Band"]])

print("Motion band set: 1500.0rpm")
