# -*- coding: utf-8 -*-
"""
build_m4_solve.py — 25 N·m 8p12s SPMSM 的**可求解** Maxwell 2D 模型 + M4 空载瞬态

为什么需要重建（2026-11-08 真机实测结论）
----------------------------------------
`M4_25Nm.aedt`（M2/M3 产物）在 `oDesign.Analyze("Setup1")` 时被 Maxwell 直接判死，
消息窗口 36 条 intersect + 1 条 non-manifold，四类根因全部是**几何自相交**：

1. 磁钢用**平板弦**放在转子外径之外（XStart=45.825，宽 1.95）⇒ 径向跨 45.825..47.775 mm，
   而定子内径 46.5 mm ⇒ 插入定子铁芯 1.275 mm（`StatorOuter and PM_x intersect`）。
   平板弦在 0.675 mm 气隙里几何上不可行，必须改为**环形扇区**（43.875..45.825，39.15°）。
2. 线圈取 13.2×5.7 矩形，而槽在 r=49.65 处只有 3.2 mm 宽 ⇒ 两侧穿出槽壁
   （`StatorOuter and Coil_x intersect`）。必须按槽形内缩生成。
3. `Region` 是整圆，从未与定子/运动带/线圈布尔分离 ⇒ 全域重叠。
4. 槽多边形首尾重复点导致退化线段 ⇒ `Non-manifold vertices found for "StatorOuter"`。

本脚本从零重建自洽模型，再跑 M4：
  · 定子：圆环 − 12 槽（槽口切入内径 0.2 mm，消除相切非流形）
  · 磁钢：环形扇区内/外弧各离散 24 段（弧矢 4.5 µm），直接多边形，不用布尔切扇楔
  · 转子：圆盘 − 8 磁钢（KeepOriginals）⇒ 弦-弧穿透的薄片被布尔吃掉，界面严格互补
  · 线圈：槽多边形按 0.88 缩放（保凸 ⇒ 必然内含）
  · Band：气隙环（46.1625 外 / 43.9 内）− 8 磁钢，洞内严格包住转子（留 0.025 mm 净空，
    AEDT 要求「band 内必须有对象」，边界完全重合会被判 no objects within the band）
  · Region：整圆 − 定子 − 12 线圈 − Band（KeepOriginals）

产物
----
  D:/ANSYS_Run/M5_25Nm.aedt                 重建后的可求解工程
  D:/ANSYS_Run/m4_build_solve_progress.log  分步进度（与 AEDT 同名 .log 分开）
  D:/ANSYS_Run/csv/tq_noload.csv            Moving1.Torque（齿槽）
  D:/ANSYS_Run/csv/flux_a|b|c.csv           FluxLinkage(WindingA|B|C)（Wb）
                                            ⇒ 空载 BEMF 由 e = −dλ/dt 求导得到

运行
----
  "ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/m4_build_solve.py"
  注意：不带 -ng；oDesktop 由 AEDT 预注入；本文件必须是 IronPython 2.7 语法。
"""
import math
import os
import time
import traceback

LOG = r"D:/ANSYS_Run/m4_build_solve_progress.log"
AEDT_OUT = r"D:/ANSYS_Run/M5_25Nm.aedt"
CSVDIR = r"D:/ANSYS_Run/csv"

# ---------------- 设计常量（与 DESIGN_PROGRESS 冻结值一致） ----------------
R_BORE = 46.5          # 定子内径 93 mm
R_STATOR = 75.0        # 定子外径 150 mm
R_REGION = 95.0
T_PM = 1.95            # 磁钢厚
R_PM_OUT = 45.825      # 46.5 − 0.675 气隙
R_PM_IN = R_PM_OUT - T_PM        # 43.875 转子铁芯外径
POLE_PITCH = 45.0      # 8 极
ALPHA_P = 0.87         # 极弧系数
R_BAND_OUT = (R_PM_OUT + R_BORE) / 2.0   # 46.1625
R_ROTOR = R_PM_IN + 0.03                 # 43.905：转子略大于磁钢内半径，
# 2021.1 实测：Band 必须**包住**转子——AEDT 的 "objects within the band" 找的是
# band 内部的对象；做成气隙环（洞内放转子）会被判 no objects within the band。
# 包含式重叠不触发 intersect 检查（只有边界穿越才报），故 Band 取整圆。
SLOT_X0 = R_BORE - 0.2  # 槽口深入内径 0.2 mm，避免相切；且在 Band 之外，不产生薄片
SLOT_X1 = 48.0
SLOT_X2 = 64.5
SLOT_B0 = 2.5
SLOT_B2 = 9.5
COIL_SHRINK = 0.88
COIL_CX = 55.5
# ---- 匝数口径（2026-11-09 修正，此前记错一倍） --------------------------------
# `AssignCoil` 的 `Conductor number` 是**单个槽边**的导体数，不是线圈匝数：
# 一匝必然「进一个槽、出另一个槽」，所以一个绕齿线圈的匝数 = 槽边导体数。
# 相 A 的 4 个槽 {1+,2−,7+,8−} 构成**两个**绕齿线圈（齿 1 与齿 7）：
#   齿 1 线圈 = 槽1(go) + 槽2(return) = TURNS_PER_COIL 匝
#   齿 7 线圈 = 槽7(go) + 槽8(return) = TURNS_PER_COIL 匝
#   ⇒ 相 A 总匝数 = 2 × TURNS_PER_COIL
# 旧值 20 ⇒ 40 匝/相，只有设计 81 匝的 49%，这正是首轮 FEA 反电势 59.3 V
# 只有解析值 132.4 V 一半的直接原因（磁路本身只差 5%，见 MAXWELL_INTERNALS §9.6）。
# 取 40 ⇒ 80 匝/相，与设计 81 匝偏差 −1.2%。
TURNS_PER_COIL = 40
TURNS_PER_PHASE = 2 * TURNS_PER_COIL
MODEL_DEPTH = "160mm"
STOP_FULL = "0.0200s"
STEP = "0.000050s"
STOP_TRIAL = "0.0002s"
NSEG_PM = 24

_L = []


def log(m):
    _L.append("[%s] %s" % (time.strftime("%H:%M:%S"), m))
    try:
        f = open(LOG, "w")
        f.write("\n".join(_L))
        f.close()
    except Exception:
        pass


def step(label, fn):
    """执行一步，成功返回结果，失败只记日志（便于定位，不中断整体）。"""
    try:
        v = fn()
        log("OK   %s" % label)
        return v
    except Exception:
        log("FAIL %s :: %s" % (label, traceback.format_exc().splitlines()[-1]))
        return None


def polygon_area(pts):
    s = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


# ---------------- 期望面积（解析，用于布尔后校验） ----------------
SLOT_PTS = [(SLOT_X0, -SLOT_B0 / 2.0), (SLOT_X1, -SLOT_B0 / 2.0),
            (SLOT_X2, -SLOT_B2 / 2.0), (SLOT_X2, SLOT_B2 / 2.0),
            (SLOT_X1, SLOT_B0 / 2.0), (SLOT_X0, SLOT_B0 / 2.0)]
A_SLOT = polygon_area(SLOT_PTS)
A_SLOT_IRON = A_SLOT - SLOT_B0 * (R_BORE - SLOT_X0)   # 落在定子铁芯内的槽面积
A_STATOR = math.pi * (R_STATOR ** 2 - R_BORE ** 2) - 12.0 * A_SLOT_IRON

HALF_PM = math.radians(ALPHA_P * POLE_PITCH) / 2.0
PM_PTS = []
for _k in range(NSEG_PM + 1):
    _a = -HALF_PM + 2.0 * HALF_PM * _k / NSEG_PM
    PM_PTS.append((R_PM_OUT * math.cos(_a), R_PM_OUT * math.sin(_a)))
for _k in range(NSEG_PM, -1, -1):
    _a = -HALF_PM + 2.0 * HALF_PM * _k / NSEG_PM
    PM_PTS.append((R_PM_IN * math.cos(_a), R_PM_IN * math.sin(_a)))
A_PM = polygon_area(PM_PTS)

COIL_PTS = [(COIL_CX + COIL_SHRINK * (x - COIL_CX), COIL_SHRINK * y) for (x, y) in SLOT_PTS]
A_COIL = polygon_area(COIL_PTS)
A_ROTOR_FULL = math.pi * R_ROTOR ** 2
A_BAND = math.pi * R_BAND_OUT ** 2
A_REGION = (math.pi * R_REGION ** 2 - A_STATOR - 12.0 * A_COIL
            - math.pi * R_BAND_OUT ** 2)


def main():
    log("=== build_m4_solve start ===")
    log("expected areas: slot=%.2f stator=%.2f coil=%.2f pm=%.2f rotor(full)=%.2f band=%.2f region=%.2f"
        % (A_SLOT, A_STATOR, A_COIL, A_PM, A_ROTOR_FULL, A_BAND, A_REGION))

    # ------------------------------------------------ 工程与设计设置
    oProject = oDesktop.NewProject()
    oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
    oDesign = oProject.SetActiveDesign("Motor_Design")
    oDesign.SetDesignSettings(
        ["NAME:DesignSettingsData",
         "ModelDepth:=", MODEL_DEPTH,
         "PreserveTransientSolution:=", False,
         "ComputeTransientInductance:=", True])
    log("design created, ModelDepth=" + MODEL_DEPTH)
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    oEditor.SetModelUnits(["NAME:UnitsSettings", "Units:=", "mm"])

    # ------------------------------------------------ 材料（必须先于几何）
    oDef = oProject.GetDefinitionManager()
    for mat, sign in (("NdFe35_N", 1), ("NdFe35_S", -1)):
        step("material " + mat, lambda m=mat, s=sign: oDef.EditMaterial(
            m, ["NAME:" + m, "CoordinateSystemType:=", "Cylindrical",
                "BulkOrSurfaceType:=", 1,
                ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal", "Structural"]],
                "permittivity:=", "1", "permeability:=", "1.0997785406",
                "conductivity:=", "625000", "dielectric_loss_tangent:=", "0",
                "magnetic_loss_tangent:=", "0",
                ["NAME:magnetic_coercivity", "property_type:=", "VectorProperty",
                 "Magnitude:=", "-890000.0A_per_meter",
                 "DirComp1:=", str(s), "DirComp2:=", "0", "DirComp3:=", "0"],
                "mass_density:=", "7400", "youngs_modulus:=", "147000000000"]))
    step("material M270_35A", lambda: oDef.EditMaterial(
        "M270_35A", ["NAME:M270_35A", "CoordinateSystemType:=", "Cartesian",
                     "BulkOrSurfaceType:=", 1,
                     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal", "Structural"]],
                     "permittivity:=", "1", "permeability:=", "1000",
                     "conductivity:=", "2000000", "dielectric_loss_tangent:=", "0",
                     "magnetic_loss_tangent:=", "0", "mass_density:=", "7650",
                     "youngs_modulus:=", "200000000000"]))

    # ------------------------------------------------ 工具函数
    def circle(name, r, mat='"vacuum"', color="(132 132 193)", trans=0):
        oEditor.CreateCircle(
            ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
             "ZCenter:=", "0mm", "Radius:=", ("%gmm" % r), "WhichAxis:=", "Z"],
            ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
             "Transparency:=", trans, "PartCoordinateSystem:=", "Global",
             "MaterialValue:=", mat, "SolveInside:=", True])

    def poly(name, pts, mat='"vacuum"', color="(0 200 0)"):
        # 2021.1 实测：N 顶点必须给 N+1 个点（末点复写首点）+ N 段（StartIndex 0..N-1），
        # 否则 Acis 报 "Fail to cover lines. The given curve is open!"。
        loop = list(pts) + [pts[0]]
        plpts = []
        for (x, y) in loop:
            plpts.append(["NAME:PLPoint", "X:=", ("%gmm" % x), "Y:=", ("%gmm" % y),
                          "Z:=", "0mm"])
        segs = ["NAME:PolylineSegments"]
        for i in range(len(pts)):
            segs.append(["NAME:PLSegment", "SegmentType:=", "Line",
                         "StartIndex:=", i, "NoOfPoints:=", 2])
        oEditor.CreatePolyline(
            ["NAME:PolylineParameters", "IsPolylineCovered:=", True,
             "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + plpts, segs],
            ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
             "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
             "MaterialValue:=", mat, "SolveInside:=", True])

    def sub(blank, tools, keep):
        oEditor.Subtract(
            ["NAME:Selections", "Blank Parts:=", blank, "Tool Parts:=", ", ".join(tools)],
            ["NAME:SubtractParameters", "KeepOriginals:=", keep])

    def dup_axis(name, angle_deg, nclones):
        oEditor.DuplicateAroundAxis(
            ["NAME:Selections", "Selections:=", name, "NewPartsModelFlag:=", "Model"],
            ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
             "WhichAxis:=", "Z", "AngleStr:=", ("%gdeg" % angle_deg),
             "Numclones:=", str(nclones)],
            ["NAME:Options", "DuplicateAssignments:=", False])

    def area(name):
        ids = list(oEditor.GetFaceIDs(name))
        return sum([float(oEditor.GetFaceArea(f)) for f in ids])

    def set_mat(name, mat):
        oEditor.ChangeProperty(
            ["NAME:AllTabs",
             ["NAME:Geometry3DAttributeTab", ["NAME:PropServers", name],
              ["NAME:ChangedProps", ["NAME:Material", "Value:=", '"' + mat + '"']]]])

    def rename(old, new):
        if old == new:
            return
        oEditor.ChangeProperty(
            ["NAME:AllTabs",
             ["NAME:Geometry3DAttributeTab", ["NAME:PropServers", old],
              ["NAME:ChangedProps", ["NAME:Name", "Value:=", new]]]])

    def check(label, got, want, tol=0.005):
        rel = abs(got - want) / want if want else 1.0
        flag = "PASS" if rel <= tol else "FAIL"
        log("%s %s = %.4f (expected %.4f, rel %.3f%%)"
            % (flag, label, got, want, rel * 100.0))

    # ------------------------------------------------ Region（先赋边界，此时只有 1 条边）
    circle("Region", R_REGION, '"vacuum"', "(143 175 143)", 1)
    oBnd = oDesign.GetModule("BoundarySetup")

    def assign_vp():
        edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]
        oBnd.AssignVectorPotential(
            ["NAME:VectorPotential1", "Edges:=", edges, "Value:=", "0",
             "CoordinateSystem:=", ""])
        return len(edges)
    log("VP edges = %r" % (step("AssignVectorPotential on pristine Region", assign_vp),))

    # ------------------------------------------------ 定子：圆环 − 12 槽
    circle("StatorOuter", R_STATOR)
    circle("Bore", R_BORE)
    step("subtract bore", lambda: sub("StatorOuter", ["Bore"], False))
    step("polyline Slot_1", lambda: poly("Slot_1", SLOT_PTS))
    step("duplicate 12 slots", lambda: dup_axis("Slot_1", 30.0, 12))
    slots = ["Slot_1"] + ["Slot_1_" + str(i) for i in range(1, 12)]
    step("subtract 12 slots", lambda: sub("StatorOuter", slots, False))
    check("stator area", area("StatorOuter"), A_STATOR)

    # ------------------------------------------------ 转子 + 磁钢（扇区）
    circle("RotorOuter", R_ROTOR)
    step("polyline PM_1", lambda: poly("PM_1", PM_PTS, '"NdFe35_N"', "(255 0 0)"))
    step("duplicate 8 PM", lambda: dup_axis("PM_1", POLE_PITCH, 8))
    pm_objs = ["PM_1"] + ["PM_1_" + str(i) for i in range(1, 8)]
    for i, nm in enumerate(pm_objs):
        step("rename %s -> PM_%d" % (nm, i + 1),
             lambda o=nm, n="PM_%d" % (i + 1): rename(o, n))
    for i in range(8):
        step("material PM_%d" % (i + 1),
             lambda k=i: set_mat("PM_%d" % (k + 1), "NdFe35_N" if k % 2 == 0 else "NdFe35_S"))
    pm_all = ["PM_%d" % (i + 1) for i in range(8)]
    check("PM_1 area", area("PM_1"), A_PM)
    # 转子半径比磁钢内半径大 30 µm ⇒ 磁钢在转子上"嵌"进去一点，布尔开出闭合浅坑，
    # 两侧边界严格互补、无相切顶点（相切会触发 Non-manifold vertices）。
    step("rotor minus PM", lambda: sub("RotorOuter", pm_all, True))
    log("rotor area = %.3f (full disk %.3f, 8 磁钢投影被挖去)" % (area("RotorOuter"), A_ROTOR_FULL))

    # ------------------------------------------------ 运动带：气隙环 − 磁钢
    circle("Band", R_BAND_OUT, '"vacuum"', "(0 255 255)", 0.75)
    check("Band area", area("Band"), A_BAND, 0.002)

    # ------------------------------------------------ 线圈：槽形内缩 0.88
    step("polyline Coil_1", lambda: poly("Coil_1", COIL_PTS, '"copper"', "(255 128 0)"))
    step("duplicate 12 coils", lambda: dup_axis("Coil_1", 30.0, 12))
    coil_objs = ["Coil_1"] + ["Coil_1_" + str(i) for i in range(1, 12)]
    for i, nm in enumerate(coil_objs):
        step("rename %s -> Coil_%d" % (nm, i + 1),
             lambda o=nm, n="Coil_%d" % (i + 1): rename(o, n))
    coil_all = ["Coil_%d" % (i + 1) for i in range(12)]
    check("Coil_1 area", area("Coil_1"), A_COIL)

    # ------------------------------------------------ 布尔分离 Region（消除全域重叠）
    step("region cleanup", lambda: sub(
        "Region", ["StatorOuter", "RotorOuter"] + pm_all + coil_all + ["Band"], True))
    parts = (area("Region") + area("StatorOuter") + sum([area(c) for c in coil_all])
             + area("Band"))
    check("area conservation (sum of parts vs disk r=95)", parts,
          math.pi * R_REGION ** 2, 0.002)

    # ------------------------------------------------ 材料绑定
    for nm in ("StatorOuter", "RotorOuter"):
        step("material %s" % nm, lambda o=nm: set_mat(o, "M270_35A"))

    # ------------------------------------------------ 绕组（一个槽边 = 一个 Coil 对象）
    # 12 个槽边 Coil 按 12S8P 单层集中绕组分配（槽距电角 360°×4/12 = 120°）：
    #   A = {1+,2−,7+,8−}  B = {3+,4−,9+,10−}  C = {5+,6−,11+,12−}
    # 「+ 槽 k / − 槽 k+1」成对 ⇒ 一个绕齿线圈；故每相 2 线圈 × TURNS_PER_COIL 匝。
    for ph in ("A", "B", "C"):
        step("WindingGroup " + ph, lambda p=ph: oBnd.AssignWindingGroup(
            ["NAME:Winding" + p, "Type:=", "Current", "IsSolid:=", False,
             "Current:=", "0A", "Resistance:=", "0.1ohm", "Inductance:=", "0.001H",
             "Voltage:=", "0V", "ParallelBranchesNum:=", "1"]))
    for k in range(1, 13):
        ph = "ABC"[((k - 1) // 2) % 3]
        pol = "Positive" if k % 2 == 1 else "Negative"
        step("AssignCoil Coil_%d->%s %s" % (k, ph, pol),
             lambda kk=k, pp=ph, po=pol: oBnd.AssignCoil(
                 ["NAME:" + pp + "_" + str(kk), "Objects:=", ["Coil_%d" % kk],
                  "Conductor number:=", str(TURNS_PER_COIL), "PolarityType:=", po,
                  "Winding:=", "Winding" + pp]))

    # 回读校验：12 个 Coil 的 Conductor number 必须都等于 TURNS_PER_COIL。
    # （2026-11-08 就是因为这个值被当成「线圈匝数」而少了一半，见文件头常量注释）
    # 2021.1 实测：`oDesign.GetChildObject("Boundaries")` 直接 call failed，
    # 因此这里做多路径尝试；全部失败时不致命——`Conductor number'='40'` 也可以
    # 直接从 .aedt 文本核验：
    #     grep -c "Conductor number'='40'" D:/ANSYS_Run/M5_25Nm.aedt   # 期望 12
    def verify_turns():
        for path in ("Boundaries", "Excitations", "Boundaries/Current"):
            try:
                bo = oDesign.GetChildObject(path)
            except Exception:
                continue
            got = []
            try:
                names = bo.GetChildNames()
            except Exception:
                continue
            for nm in names:
                for key in ("ConductorNumber", "Conductor number"):
                    try:
                        got.append("%s=%s"
                                   % (nm, bo.GetChildObject(nm).GetPropValue(key)))
                        break
                    except Exception:
                        pass
            if got:
                return got
        return "unavailable via API (2021.1) -> grep .aedt for Conductor number'='40'"
    log("conductor readback (expect all =%d): %s"
        % (TURNS_PER_COIL, step("verify turns", verify_turns)))
    log("turns/phase (model) = 2 x %d = %d (design 81)"
        % (TURNS_PER_COIL, TURNS_PER_PHASE))

    # ------------------------------------------------ 运动带（1500 rpm）
    # 2021.1 实测：`"Move Type:=", "Rotate"` + `"InitPos:="` 会被当成**平动**处理，
    # 报 `For 2D XY translation problem, only X or Y axis could be used`。
    # 依次尝试若干已知写法，取第一个成功者。
    def assign_band(variant):
        oDesign.GetModule("ModelSetup").AssignBand(
            ["NAME:BandData"]
            + [x for pair in variant for x in pair]
            + ["Objects:=", ["Band"]])
        return "ok"

    BAND_VARIANTS = [
        ("A Init Pos", [("Move Type:=", "Rotate"), ("Coordinate System:=", "Global"),
                        ("Axis:=", "Z"), ("Is Positive:=", True),
                        ("Init Pos:=", "0deg"), ("HasRotateLimit:=", False),
                        ("NonCylindrical:=", False),
                        ("Consider Mechanical Transient:=", False),
                        ("Angular Velocity:=", "1500rpm")]),
        ("B 无 CS", [("Move Type:=", "Rotate"), ("Axis:=", "Z"),
                     ("Is Positive:=", True), ("Init Pos:=", "0deg"),
                     ("Angular Velocity:=", "1500rpm")]),
        ("C 极简", [("Move Type:=", "Rotate"), ("Axis:=", "Z"),
                    ("Is Positive:=", True), ("Angular Velocity:=", "1500rpm")]),
        ("D rad_per_sec", [("Move Type:=", "Rotate"), ("Axis:=", "Z"),
                           ("Is Positive:=", True),
                           ("Angular Velocity:=", "157.0796rad_per_sec")]),
    ]
    band_ok = None
    for label, v in BAND_VARIANTS:
        if step("AssignBand " + label, lambda vv=v: assign_band(vv)) == "ok":
            band_ok = label
            break
    log("Band motion assigned by variant: %r" % (band_ok,))

    # ------------------------------------------------ 剖分（2021.1 无 AssignSurfApproxOp）
    oMesh = oDesign.GetModule("MeshSetup")
    step("mesh Stator", lambda: oMesh.AssignLengthOp(
        ["NAME:Mesh_Stator", "Objects:=", ["StatorOuter"], "MaxLength:=", "1.5mm",
         "RestrictElem:=", False, "RestrictLength:=", True]))
    step("mesh Rotor", lambda: oMesh.AssignLengthOp(
        ["NAME:Mesh_Rotor", "Objects:=", ["RotorOuter"], "MaxLength:=", "2.0mm",
         "RestrictElem:=", False, "RestrictLength:=", True]))
    step("mesh PM", lambda: oMesh.AssignLengthOp(
        ["NAME:Mesh_PM", "Objects:=", pm_all, "MaxLength:=", "0.6mm",
         "RestrictElem:=", False, "RestrictLength:=", True]))
    step("mesh Coil", lambda: oMesh.AssignLengthOp(
        ["NAME:Mesh_Coil", "Objects:=", coil_all, "MaxLength:=", "0.8mm",
         "RestrictElem:=", False, "RestrictLength:=", True]))
    step("mesh Band", lambda: oMesh.AssignLengthOp(
        ["NAME:Mesh_Band", "Objects:=", ["Band"], "MaxLength:=", "0.3mm",
         "RestrictElem:=", False, "RestrictLength:=", True]))

    # ------------------------------------------------ 求解设置
    oAnaly = oDesign.GetModule("AnalysisSetup")
    step("InsertSetup Setup1", lambda: oAnaly.InsertSetup(
        "Transient",
        ["NAME:Setup1", "StopTime:=", STOP_TRIAL, "TimeStep:=", STEP,
         "SaveFieldsType:=", "None", "N:=", "1",
         "UseAdaptiveTimeStep:=", False, "NonlinearSolverResidual:=", "0.0001",
         "SmoothBHCurve:=", False]))

    oProject.SaveAs(AEDT_OUT, True)
    log("SAVED " + AEDT_OUT)

    # ------------------------------------------------ 试算 4 步
    log("=== trial solve 4 steps ===")
    t0 = time.time()
    trial = step("Analyze trial", lambda: (oDesign.Analyze("Setup1"), True)[1])
    log("trial elapsed %.1fs" % (time.time() - t0))
    if not trial:
        log("trial solve failed -> keep project, skip full run")
        step("save partial", lambda: oProject.Save())
        log("=== end (trial failed) ===")
        return

    # ------------------------------------------------ 全时长求解
    log("=== full solve %s / %s ===" % (STOP_FULL, STEP))
    step("EditSetup full", lambda: oAnaly.EditSetup(
        "Setup1",
        ["NAME:Setup1", "StopTime:=", STOP_FULL, "TimeStep:=", STEP,
         "SaveFieldsType:=", "Every N Steps", "N:=", "2",
         "UseAdaptiveTimeStep:=", False, "NonlinearSolverResidual:=", "0.0001",
         "SmoothBHCurve:=", False]))
    # EditSetup 之后运动带理论上保留，但它是最容易静默丢失的一项（M3 就丢过一次）。
    # 读回校验是廉价保险：有就留着，没有才补挂；补挂复用上面验证过的变体链。
    def band_names():
        try:
            return list(oDesign.GetModule("ModelSetup").GetMotionSetupNames())
        except Exception:
            return []

    def ensure_band():
        got = band_names()
        if got:
            return "kept %r" % (got,)
        for label, v in BAND_VARIANTS:
            try:
                oDesign.GetModule("ModelSetup").AssignBand(
                    ["NAME:BandData"] + [x for pair in v for x in pair]
                    + ["Objects:=", ["Band"]])
                return "assigned via " + label
            except Exception:
                continue
        raise Exception("no motion setup and every band variant failed")

    log("motion setups before full solve: %r" % (band_names(),))
    log("ensure band -> %r" % (step("ensure band", ensure_band),))

    t0 = time.time()
    step("Analyze full", lambda: oDesign.Analyze("Setup1"))
    log("full elapsed %.1fs" % (time.time() - t0))
    log("motion setups after solve: %r" % (band_names(),))
    # 全时长解只活在进程内存里，先存盘再导出：导出再出岔子也不用重跑 400 s。
    step("save after solve", lambda: oProject.Save())

    # ------------------------------------------------ 导出 CSV
    # 2026-11-08 实测：`CreateReport` 只有下面这一种写法在**批处理**下可用，
    # 其余 144 种组合（reportType="Transient"、`["Domain:=","Sweep"]` 形式的 ctx、
    # `[expr+":=",["None","None","None"]]` 形式的 trace 等）一律 `call failed`。
    # 三处关键差异：reportType 必须 "Standard"、SimValueContext 走 NAME:Context、
    # trace 用 `["X Component:=","Time","Y Component:=",[expr]]`。详见 §9.4。
    try:
        os.makedirs(CSVDIR)
    except Exception:
        pass
    rep = oDesign.GetModule("ReportSetup")
    CTX = ["NAME:Context", "SimValueContext:=",
           [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]]

    def data_rows(path):
        """数数据行（跳过表头/单位/空行）——导出「只给警告不给异常」是常见坑。"""
        n = 0
        try:
            f = open(path)
            for ln in f:
                s = ln.strip()
                if not s:
                    continue
                head = s.split("\t")[0].split(",")[0].strip().strip('"')
                try:
                    float(head)
                    n += 1
                except ValueError:
                    pass
            f.close()
        except Exception:
            return -1
        return n

    def export(name, exprs, fname):
        rep.CreateReport(name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                         CTX, ["Time:=", ["All"]],
                         ["X Component:=", "Time", "Y Component:=", [exprs]], [])
        try:
            rep.ExportToFile(name, CSVDIR + "/" + fname)
        except Exception:
            rep.ExportToFile(name, CSVDIR + "/" + fname, True)
        return "%s (%d rows)" % (fname, data_rows(CSVDIR + "/" + fname))

    log("export tq -> %s"
        % (step("export tq_noload", lambda: export("Tq", "Moving1.Torque", "tq_noload.csv")),))
    # 电流型绕组（WindingGroup Type="Current"）**没有** `WindingA.Voltage` 输出，
    # 空载反电势只能由磁链对时间求导得到：e = −dλ/dt（见 ingest_fea.py）。
    for ph in ("A", "B", "C"):
        log("export flux_%s -> %s"
            % (ph.lower(), step("export flux_" + ph.lower(),
                                lambda p=ph: export("Flux" + p, "FluxLinkage(Winding" + p + ")",
                                                    "flux_" + p.lower() + ".csv"))))
    step("save project", lambda: oProject.Save())

    log("=== build_m4_solve end ===")


main()
