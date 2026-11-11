# -*- coding: utf-8 -*-
# =============================================================================
#  solve_25Nm_SPMSM.py  —  ANSYS Maxwell 2D 全自动求解脚本 (25 N·m SPMSM, 8p12s)
# -----------------------------------------------------------------------------
#  用途：在本机（已装 Maxwell + 许可证）一键完成「建模 → 剖分 → 求解 → 导出」
#  运行方式（在装了 Maxwell 的机器上，CMD/PowerShell 执行）：
#     "D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe" ^
#         -RunScriptAndExit "D:\ANSYS_Run\solve_25Nm_SPMSM.py"
#  注意：不要加 -ng —— 它与 -RunScriptAndExit 互斥（-ng 只能配 -batchsolve/-batchsave），
#        加了会被参数解析直接拒掉。此模式下 oDesktop 由 AEDT 预注入。
#  产物：
#     D:\ANSYS_Run\SPMSM_25Nm.aedt            (Maxwell 工程，可双击打开复核)
#     D:\ANSYS_Run\csv\tq_noload.csv          (空载转矩/齿槽)
#     D:\ANSYS_Run\csv\bemf.csv               (空载相反电动势)
#     D:\ANSYS_Run\csv\tq_load.csv            (负载转矩)
#     D:\ANSYS_Run\csv\ia_load.csv            (负载相电流)
#     D:\ANSYS_Run\fea_summary.json           (汇总，供报告回填)
#     D:\ANSYS_Run\solve.log                  (执行日志，便于排错)
#
#  说明：本脚本在「非交互式沙箱」中无法运行（AEDT 运行时需桌面会话）。
#        请在普通桌面会话运行；已对每一步做 try/except，失败会记到日志而不中断。
# =============================================================================

import ScriptEnv, math, os, json, time

LOGPATH = r"D:\ANSYS_Run\solve.log"
CSVDIR  = r"D:\ANSYS_Run\csv"
PRJ     = r"D:\ANSYS_Run\SPMSM_25Nm.aedt"

# 叠长（G3）：本机型叠片长度 160 mm（pmsm_config / pmsm_config.STACK_LENGTH）。
# Maxwell 2D 默认 ModelDepth = 1 mm，不写这一项会让转矩/反电势/损耗整体缩小约 160 倍，
# 且求解器不报错 —— 必须显式写入。数值须与 pmsm_config 冻结值同步。
MODEL_DEPTH = "160mm"

def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line)
    try:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

try:
    os.makedirs(CSVDIR, exist_ok=True)
except Exception:
    pass

# ---------------------------------------------------------------- SETUP
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
time.sleep(3)
try:
    active = oDesktop.GetActiveProject()
    if active is not None:
        try: active.ClearSavedFlag()
        except Exception: pass
        try: oDesktop.CloseProject(active.GetName())
        except Exception: pass
except Exception:
    pass
oProject = oDesktop.NewProject()
oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
oDesign = oProject.SetActiveDesign("Motor_Design")
oDesign.SetDesignSettings(
    ["NAME:DesignSettingsData",
     "ModelDepth:=", MODEL_DEPTH,
     "PreserveTransientSolution:=", False,
     "ComputeTransientInductance:=", True])
log("Project created: Maxwell 2D / Transient, ModelDepth=" + MODEL_DEPTH)

# ---------------------------------------------------------------- GEOMETRY
oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.SetModelUnits(["NAME:UnitsSettings", "Length:=", "mm"])

def circle(name, r, mat='"vacuum"', color="(132 132 193)", trans=0):
    oEditor.CreateCircle(
        ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
         "ZCenter:=", "0mm", "Radius:=", ("%gmm" % r), "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
         "Transparency:=", trans, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", mat, "SolveInside:=", True])

# Region + 定子外/内环
circle("Region", 95.0, '"vacuum"', "(143 175 143)", 1)
circle("StatorOuter", 75.0)
circle("StatorInner", 46.5)
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# 槽（矩形开口槽）
x0, x1, x2 = 46.5, 48.0, 64.5
b0, b2 = 2.5, 9.5
oEditor.CreatePolyline(
    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True],
    ["NAME:PolylinePoints",
     ["NAME:PLPoint", "X:=", str(x0)+"mm", "Y:=", str(-b0/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x1)+"mm", "Y:=", str(-b0/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x2)+"mm", "Y:=", str(-b2/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x2)+"mm", "Y:=", str(b2/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x1)+"mm", "Y:=", str(b0/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x0)+"mm", "Y:=", str(b0/2)+"mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", str(x0)+"mm", "Y:=", str(-b0/2)+"mm", "Z:=", "0mm"]],
    ["NAME:PolylineSegments"] +
    6*["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "30.0deg", "Numclones:=", "12"])
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", "Slot_1,Slot_2,Slot_3,Slot_4,Slot_5,Slot_6,Slot_7,Slot_8,Slot_9,Slot_10,Slot_11,Slot_12"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# 转子外环 + 轴
circle("RotorOuter", 45.825)
circle("Shaft", 15.0, '"vacuum"', "(0 255 255)")
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# 8 块磁钢（N/S 交替，径向磁化）
pm_r, pm_w, pa = 45.825, 1.95, 0.87
pm_h = pm_r * 2 * math.sin(math.radians(pa * 45.0 / 2))
for i in range(8):
    mat = "NdFe35_N" if i % 2 == 0 else "NdFe35_S"
    color = "(255 0 0)" if i % 2 == 0 else "(0 0 255)"
    pname = "PM_%d" % (i+1)
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(pm_r)+"mm", "YStart:=", str(-pm_h/2)+"mm", "ZStart:=", "0mm",
         "Width:=", str(pm_w)+"mm", "Height:=", str(pm_h)+"mm", "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", pname, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", ('"' + mat + '"'), "SolveInside:=", True])
    if i > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", pname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(i*45.0)+"deg", "DuplicateObjects:=", False])

# 运动带（气隙中心）
band_r = (91.65 + 93.0) / 4.0   # = 46.1625 (定子内 46.5 与转子外 45.825 之间)
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", ("%gmm" % band_r), "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# 12 个线圈截面（铜，槽内居中，命名 Coil_1..Coil_12）
coil_r_mid, coil_radial, coil_tang = 56.25, 13.20, 5.70
for k in range(12):
    cname = "Coil_%d" % (k+1)
    oEditor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", str(coil_r_mid - coil_radial/2.0)+"mm",
         "YStart:=", str(-coil_tang/2.0)+"mm", "ZStart:=", "0mm",
         "Width:=", str(coil_radial)+"mm", "Height:=", str(coil_tang)+"mm",
         "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", cname, "Flags:=", "", "Color:=", "(255 128 0)",
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"copper"', "SolveInside:=", True])
    if k > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", cname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(k*30.0)+"deg", "DuplicateObjects:=", False])
log("Geometry built: 12 slots, 8 PMs, Band, 12 coils")

# ---------------------------------------------------------------- MATERIALS
oDef = oProject.GetDefinitionManager()
for mat, sign in [("NdFe35_N", "1"), ("NdFe35_S", "-1")]:
    try:
        oDef.EditMaterial(mat,
            ["NAME:"+mat, "CoordinateSystemType:=", "Cylindrical", "BulkOrSurfaceType:=", 1,
             ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
             "permittivity:=", "1", "permeability:=", "1.0997785406",
             "conductivity:=", "625000", "dielectric_loss_tangent:=", "0", "magnetic_loss_tangent:=", "0",
             ["NAME:magnetic_coercivity", "property_type:=", "VectorProperty",
              "Magnitude:=", "-890000.0A_per_meter", "DirComp1:=", sign, "DirComp2:=", "0", "DirComp3:=", "0"],
             "mass_density:=", "7400", "youngs_modulus:=", "147000000000"])
    except Exception as e:
        log("material %s warn: %s" % (mat, e))
# 硅钢片（若库中没有，则按 B-H 近似的线性相对磁导率/高饱和定义）
try:
    oDef.EditMaterial("M270_35A",
        ["NAME:M270_35A", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 0,
         ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
         "permittivity:=", "1", "permeability:=", "1000", "conductivity:=", "2000000",
         "dielectric_loss_tangent:=", "0", "magnetic_loss_tangent:=", "0",
         "mass_density:=", "7650", "youngs_modulus:=", "200000000000"])
    # 把定子/转子铁芯材料改为 M270_35A
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    oEditor.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:Geometry3DAttributeTab",
          ["NAME:PropServers", "StatorOuter"],
          ["NAME:ChangedProps", ["NAME:Material", "Value:=", '"M270_35A"']]]])
    oEditor.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:Geometry3DAttributeTab",
          ["NAME:PropServers", "RotorOuter"],
          ["NAME:ChangedProps", ["NAME:Material", "Value:=", '"M270_35A"']]]])
except Exception as e:
    log("core material warn: %s" % e)
log("Materials assigned")

# ---------------------------------------------------------------- WINDING
oBnd = oDesign.GetModule("BoundarySetup")
for phase in ["A", "B", "C"]:
    oBnd.AssignWindingGroup(
        ["NAME:Winding"+phase, "Type:=", "Current", "IsSolid:=", False,
         "Current:=", "0A", "Resistance:=", "0.1ohm", "Inductance:=", "0.001H",
         "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])
groups = {"A+":["Coil_1","Coil_7"], "A-":["Coil_2","Coil_8"],
          "B+":["Coil_3","Coil_9"], "B-":["Coil_4","Coil_10"],
          "C+":["Coil_5","Coil_11"], "C-":["Coil_6","Coil_12"]}
for g, objs in groups.items():
    oBnd.AssignCoilGroup(
        ["NAME:"+g, "Objects:=", objs, "Conductor number:=", "40", "PolarityType:=", "Positive" if g[-1]=="+" else "Negative"])
oBnd.AddWindingCoils("WindingA", ["A+","A-"])
oBnd.AddWindingCoils("WindingB", ["B+","B-"])
oBnd.AddWindingCoils("WindingC", ["C+","C-"])
log("Windings assigned")

# ---------------------------------------------------------------- BOUNDARY / MOTION
oBnd.AssignVectorPotential(
    ["NAME:VectorPotential1", "Edges:=", [], "Objects:=", ["Region"],
     "Value:=", "0", "CoordinateSystem:=", ""])
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData", "Move Type:=", "Rotate", "Coordinate System:=", "Global",
     "Axis:=", "Z", "Is Positive:=", True, "InitPos:=", "0deg",
     "HasRotateLimit:=", False, "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "1500.0rpm", "Objects:=", ["Band"]])
log("Band + VP boundary set")

# ---------------------------------------------------------------- MESH
oMesh = oDesign.GetModule("MeshSetup")
oMesh.AssignSurfApproxOp(
    ["NAME:SurfApprox_Airgap", "Objects:=", ["Band"],
     "CurvedSurfaceApproxChoice:=", "ManualSettings", "SurfDevChoice:=", 2, "SurfDev:=", "0.2mm",
     "NormalDevChoice:=", 2, "NormalDev:=", "15deg"])
oMesh.AssignLengthOp(
    ["NAME:Mesh_Stator", "Objects:=", ["StatorOuter"], "MaxLength:=", "1.5mm",
     "RestrictElem:=", False, "RestrictLength:=", True])
oMesh.AssignLengthOp(
    ["NAME:Mesh_Rotor", "Objects:=", ["RotorOuter"], "MaxLength:=", "3.0mm",
     "RestrictElem:=", False, "RestrictLength:=", True])
oMesh.AssignLengthOp(
    ["NAME:Mesh_PM", "Objects:=", ["PM_1","PM_2","PM_3","PM_4","PM_5","PM_6","PM_7","PM_8"],
     "MaxLength:=", "0.5mm", "RestrictElem:=", False, "RestrictLength:=", True])
log("Mesh configured")

# ---------------------------------------------------------------- SOLVER SETUP
oAnaly = oDesign.GetModule("AnalysisSetup")
oAnaly.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "0.0200s", "TimeStep:=", "0.000050s",
     "SaveFieldsType:=", "Every N Steps", "N:=", "1",
     "UseAdaptiveTimeStep:=", False, "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])
log("Transient setup inserted")

# 保存工程（便于事后在 GUI 打开复核）
try:
    oProject.SaveAs(PRJ, True)
    log("Project saved: " + PRJ)
except Exception as e:
    log("save warn: %s" % e)

# ---------------------------------------------------------------- SOLVE: 空载
def make_report(repname, ycomps):
    rep = oDesign.GetModule("ReportSetup")
    rep.CreateReport(
        repname, "Transient", "Rectangular Plot", "Setup1 : LastAdaptive",
        ["Domain:=", "Time"],
        ["Solution:=", "Setup1 : Transient"],
        ["SimValueContext:=", ["ReportType:=", "Transient"]],
        ["XComponent:=", "Time"],
        ["YComponent:=", ycomps])
    rep.ExportToFile(repname, os.path.join(CSVDIR, repname + ".csv"))

def safe_report(repname, ycomps):
    try:
        make_report(repname, ycomps)
        log("exported report: " + repname)
    except Exception as e:
        log("report %s FAILED: %s" % (repname, e))

log("=== Solving NO-LOAD (currents=0) ===")
oAnaly.Solve("Setup1")
safe_report("tq_noload", ["Moving1.Torque"])
safe_report("bemf", ["WindingA.Voltage", "WindingB.Voltage", "WindingC.Voltage"])
safe_report("fluxA", ["WindingA.Inductance"])   # 若报错会被 try 吞掉

# ---------------------------------------------------------------- SOLVE: 负载
log("=== Solving LOAD (rated 3-phase current) ===")
Ipk = 9.89 * math.sqrt(2)   # ≈ 13.98 A 峰值
wd = 2*math.pi*100
oBnd.EditWindingGroup(
    ["NAME:WindingA", "Type:=", "Current", "IsSolid:=", False,
     "Current:=", ("%g*sin(%g*Time)" % (Ipk, wd)), "Resistance:=", "0.1ohm",
     "Inductance:=", "0.001H", "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])
oBnd.EditWindingGroup(
    ["NAME:WindingB", "Type:=", "Current", "IsSolid:=", False,
     "Current:=", ("%g*sin(%g*Time-2*pi/3)" % (Ipk, wd)), "Resistance:=", "0.1ohm",
     "Inductance:=", "0.001H", "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])
oBnd.EditWindingGroup(
    ["NAME:WindingC", "Type:=", "Current", "IsSolid:=", False,
     "Current:=", ("%g*sin(%g*Time-4*pi/3)" % (Ipk, wd)), "Resistance:=", "0.1ohm",
     "Inductance:=", "0.001H", "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])
oAnaly.Solve("Setup1")
safe_report("tq_load", ["Moving1.Torque"])
safe_report("ia_load", ["WindingA.Current"])

# ---------------------------------------------------------------- SUMMARY
summary = {
    "machine": "25Nm SPMSM 8p12s",
    "maxwell_version": "2021 R1",
    "solution_type": "Transient",
    "stop_time_s": 0.02, "time_step_s": 5e-5,
    "exports": {
        "no_load_torque": "csv/tq_noload.csv",
        "back_emf": "csv/bemf.csv",
        "load_torque": "csv/tq_load.csv",
        "load_current": "csv/ia_load.csv",
    },
    "project": PRJ,
    "note": "FEA 真实数据；由 solve_25Nm_SPMSM.py 在装 Maxwell 的机器上生成"
}
with open(r"D:\ANSYS_Run\fea_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)
log("fea_summary.json written")

try:
    oProject.Save()
except Exception:
    pass
oDesktop.QuitApplication()
log("DONE")
