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
# ── G3b 真机修复·边界 1：AssignVectorPotential 只吃 1D 实体（Edges）──
#   传 `"Objects:=", ["Region"]` 会被拒：
#   `Boundary 'VectorPotential1' can only be assigned on 1D entities`。
#   Region 是整圆 sheet，唯一一条边就是外圆；边号必须运行期取。
edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]
oModule.AssignVectorPotential(
    ["NAME:VectorPotential1",
     "Edges:=", edges,
     "Value:=", "0",
     "CoordinateSystem:=", ""])

print("Boundary: VectorPotential=0 on Region")

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
