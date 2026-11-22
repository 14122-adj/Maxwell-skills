#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M1' 建模脚本生成器 —— 生成可直接 `-RunScriptAndExit` 的 IronPython

为什么是独立生成器而不是改 `scripts/main.py`
--------------------------------------------
`scripts/main.py::MotorModelBuilder` 的几何段是 SPM 专用（单槽单线圈、表贴磁钢、
`PM_1..PM_8` 命名），且被 `gen_maxwell_model.py --check` 逐字门禁。往里面加
「双层线圈 + 16 块单层 V 型磁钢」必然改动那段 f-string 的空白与顺序，一旦生成物与
`maxwell_model/*.py` 不再逐字相同，SPM 基线的可复现性就断了。新项目要的是
**96 个可数线圈边对象 + 16 块独立磁钢多边形**，与 SPM 不共享结构，因此独立生成，
SPM 模板一行不动。

生成物（`D:/ANSYS_Run/ipm_m1_build.py`）内容
--------------------------------------------
setup → materials → geometry → winding → boundary → mesh → solver → 盘点 → SaveAs

* 几何全部在 CPython 侧算好（`ipm_geom`），IronPython 里只做 CreatePolyline；
  几何数字只有一个来源。
* 磁化方向**逐块**写进材料：16 块方向各不相同，用「一块一个材料」换取
  「显式、无隐式坐标系 API」。`SetMaterialOrientation` 的键名在 2021.1 上未验证，
  写错是静默无效键（`MAXWELL_INTERNALS.md` P17 的教训），不用。
* 不求解：M1' 的验收是「48 槽 / 16 磁钢 / 96 线圈边数得出来，且无 intersect」。

用法
----
    python ipm_build.py            # 只生成脚本（并做 CPython 语法自检）
    python ipm_build.py --run      # 生成后直接调 ansysedt 真机建模
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ipm_geom  # noqa: E402
import ipm_winding  # noqa: E402

AEDT = r"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe"
RUN_DIR = r"D:/ANSYS_Run"
SCRIPT = RUN_DIR + "/ipm_m1_build.py"
AEDT_OUT = RUN_DIR + "/IPM_8p48s_M1.aedt"
LOG = RUN_DIR + "/ipm_m1.log"

C_STEEL = "(132 132 193)"
C_COIL = "(255 128 0)"
C_N = "(255 0 0)"
C_S = "(0 0 255)"

# ── M270-35A 直流磁化曲线（2026-11-22，M2' 暴露 I13 后补）──────────────────
# 为什么必须是非线性：SPM 是表贴结构、没有隔磁桥，线性 μr=1000 只是轻微偏乐观；
# 这台 IPM 有 3.08–4.72 mm 的铁桥，桥的磁阻只有气隙的 1/58（3.19 mm 桥 / μr 1000
# vs 0.675 mm 气隙 / μr 1），线性模型下 98% 的磁钢磁通走桥短路 —— M2' 实测气隙
# 0.0296 T 而磁钢内部 0.925 T，就是这个机理。真实铁在 ~2 T 饱和，桥的磁阻随磁通
# 剧增，磁通才被迫改走气隙。所以 BH 不是"精度选项"，是**能不能算**的前提。
#
# 来源类型：公开 datasheet 量级 + 单调解析（M270-35A 级高磁导冷轧无取向硅钢，
# 0.35 mm）。锚点：1.5 T @ ≈400 A/m、膝点 1.85–1.95 T、50 kA/m @ 2.05 T。
# `assumption=待验证`（见账本 I13）：缺厂商原始曲线，膝点 ±5% 的影响待 M4' 敏感性复算。
BH_M270_35A = [
    (0, 0.00), (30, 0.30), (50, 0.52), (80, 0.80), (100, 0.95),
    (130, 1.10), (160, 1.22), (200, 1.33), (250, 1.41), (300, 1.47),
    (400, 1.54), (500, 1.59), (700, 1.65), (1000, 1.70), (1500, 1.75),
    (2000, 1.79), (3000, 1.84), (5000, 1.89), (8000, 1.93), (12000, 1.96),
    (20000, 2.00), (30000, 2.03), (50000, 2.06), (100000, 2.10),
]


def _fmt(v: float) -> str:
    return ("%.6f" % v).rstrip("0").rstrip(".")


def _pts_literal(pts) -> str:
    return "[" + ", ".join("(%s, %s)" % (_fmt(x), _fmt(y)) for (x, y) in pts) + "]"


def magnet_directions(cfg) -> list:
    """16 块磁钢（单层 V）的**外法线**单位向量（已旋转到全局）。

    厚度沿 +n 偏置（n 指向极轴内侧），故「外侧那条面」是 p1p2 所在面，
    外法线 = (sinβ, −s·cosβ)，s = ±1。偶数极取外法线（N 朝气隙），奇数极反向（S）。
    返回顺序与 `derive_rotor()["polygons"]` 完全一致：
    pole → side(+/-)（单层，无 outer/inner 之分）。
    """
    out = []
    pole_pitch = 360.0 / cfg.poles
    _ra, tilt, _len, _gap = cfg.v_single
    t = math.radians(tilt)
    for pole in range(cfg.poles):
        a = math.radians(pole * pole_pitch)
        for _side, s in (("+", 1.0), ("-", -1.0)):
            ux, uy = math.sin(t), -s * math.cos(t)
            gx = ux * math.cos(a) - uy * math.sin(a)
            gy = ux * math.sin(a) + uy * math.cos(a)
            if pole % 2 == 1:
                gx, gy = -gx, -gy
            out.append((pole, gx, gy))
    return out


def build_script(cfg, aedt_out: str = AEDT_OUT, currents=None, case_tag: str = "M1") -> str:
    """生成 M1' 建模 IronPython。

    currents: None（默认，三相 "0A" 空载）或 {"A","B","C"} → Maxwell Current 字面量。
              IronPython 2.7 只收字面量，表达式必须在 CPython 侧算好再传入。
    case_tag: 日志标识，负载版用 "M3_load"。
    """
    i1 = ipm_geom.derive_slot(cfg)
    layers = ipm_geom.coil_layers(cfg)
    rotor = ipm_geom.derive_rotor(cfg)
    wind = ipm_winding.analyze(cfg)

    sc = ipm_geom.slot_only(cfg)
    slot_pts = ipm_geom.slot_profile.pear_key_points(sc)
    slot_segs = ipm_geom.slot_profile.pear_segments()

    slot_angle = 360.0 / cfg.slots
    coils = []
    for s in range(cfg.slots):
        a = s * slot_angle
        coils.append(("Coil_T%02d" % (s + 1), "T", ipm_geom.rotate(layers["upper"], a)))
        coils.append(("Coil_B%02d" % (s + 1), "B", ipm_geom.rotate(layers["lower"], a)))

    dirs = magnet_directions(cfg)
    pm_entries = []
    for i, pts in enumerate(rotor["polygons"]):
        pole, gx, gy = dirs[i]
        pm_entries.append(("PM_%02d" % (i + 1), pts, "NdFe35_%02d" % (i + 1), gx, gy,
                           C_N if pole % 2 == 0 else C_S))

    ring = math.pi * ((cfg.stator_od / 2) ** 2 - (cfg.stator_id / 2) ** 2)
    exp_stator = ring - cfg.slots * i1["areas"]["slot_effective"]
    r_rot = cfg.rotor_od / 2
    exp_rotor = math.pi * (r_rot ** 2 - (cfg.rotor_id / 2) ** 2) - rotor["magnet_area_total"]

    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# IPM 8p48s M1' — 由 projects/IPM_8p48s/ipm_build.py 生成，勿手改。")
    A("# 48 槽梨形槽 + 16 块单层 V 磁钢 + 96 个线圈边；不求解。")
    A("import time")
    A("import traceback")
    A("")
    A('LOG = r"' + LOG + '"')
    A("_lines = []")
    A("")
    A("")
    A("def log(s):")
    A("    _lines.append(str(s))")
    A("    try:")
    A('        f = open(LOG, "w")')
    A('        f.write("\\n".join(_lines))')
    A("        f.close()")
    A("    except Exception:")
    A("        pass")
    A("")
    A("")
    A("def poly(name, pts, mat, color):")
    A("    _pp = []")
    A("    for (x, y) in list(pts) + [pts[0]]:")
    A('        _pp.append(["NAME:PLPoint", "X:=", str(x) + "mm",')
    A('                   "Y:=", str(y) + "mm", "Z:=", "0mm"])')
    A('    _ss = ["NAME:PolylineSegments"]')
    A("    for i in range(len(pts)):")
    A('        _ss.append(["NAME:PLSegment", "SegmentType:=", "Line",')
    A('                  "StartIndex:=", i, "NoOfPoints:=", 2])')
    A("    oEditor.CreatePolyline(")
    A('        ["NAME:PolylineParameters", "IsPolylineCovered:=", True,')
    A('         "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + _pp, _ss],')
    A('        ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,')
    A('         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""         "MaterialValue:=", '"' + mat + '"', "SolveInside:=", True])""")
    A("")
    A("")
    A("def area_of(name):")
    A("    ids = list(oEditor.GetFaceIDs(name))")
    A("    return sum([float(oEditor.GetFaceArea(f)) for f in ids])")
    A("")
    A("")
    A('log("=== IPM 8p48s ' + case_tag + ' build start ===")')
    A("t_all = time.time()")

    # ---------------------------------------------------------------- setup
    A("")
    A("oProject = oDesktop.NewProject()")
    A('oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")')
    A('oDesign = oProject.SetActiveDesign("Motor_Design")')
    A("oDesign.SetDesignSettings(")
    A('    ["NAME:DesignSettingsData",')
    A('     "ModelDepth:=", "%gmm",' % cfg.stack_length)
    A('     "PreserveTransientSolution:=", False,')
    A('     "ComputeTransientInductance:=", True])')
    A('oEditor = oDesign.SetActiveEditor("3D Modeler")')
    A('oEditor.SetModelUnits(["NAME:UnitsSettings", "Units:=", "mm"])')
    A('log("setup ok ModelDepth=%gmm")' % cfg.stack_length)

    # ------------------------------------------------------------ materials
    A("")
    A("oDefinitionManager = oProject.GetDefinitionManager()")
    A("# ── M270_35A 非线性 BH —— 2026-11-22 I13/I14 根因修复 ─────────────────")
    A("# 原实现用 EditMaterial 手工塞 BHCoordinates（顶层 / BValue / 平铺数组），")
    A("# 三种写法实测全部**静默丢弃**：真机 .aedt 材料块既无 permeability 也无 BH，")
    A("# 铁芯按 μr=1 求解 ⇒ Bg 只有 0.182 T（Bg 塌陷根因，不是桥饱和/埋深）。")
    A("# 2021.1 脚本 API 无法注入 BH 点（AddMaterial/EditMaterial 的 Points/Coordinates")
    A("# 键都不落数值，实测 4 种写法）。唯一可行路径：CloneMaterial 从系统库克隆")
    A("# 已带厂商 BH 曲线的 0.35 mm 硅钢，保留项目材料名 M270_35A（契约名不变）。")
    A("# 源材料 JFE_Steel_35JN270：0.35 mm、牌号 270 同 M270 量级，BH 66 点")
    A("# （10A/m@0.02T → 80000A/m@2.094T），厂商实测曲线，assumption=待验证（I13）：")
    A("# 膝点比自造 M270 曲线（400A/m@1.54T）偏软约 9%，Bg 由 FEA 验证。")
    A('# 真机验收：.aedt 中 M270_35A 块必须含 "property_type=\'nonlinear\'" 且')
    A('# BHCoordinates.Points 有 66 个真实点（宿主 grep 复核，不靠 log）。')
    A('oDefinitionManager.CloneMaterial("JFE_Steel_35JN270", "M270_35A")')
    A('log("material M270_35A: cloned JFE_Steel_35JN270 (BH 66pts, nonlinear)")')
    A("")
    for _n, _pts, mat, gx, gy, _c in pm_entries:
        A('oDefinitionManager.EditMaterial("' + mat + '",')
        A('    ["NAME:' + mat + '", "CoordinateSystemType:=", "Cartesian", "BulkOrSurfaceType:=", 1,')
        A('     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal", "Structural"]],')
        A('     "permittivity:=", "1", "permeability:=", "1.0997785406",')
        A('     "conductivity:=", "625000", "dielectric_loss_tangent:=", "0",')
        A('     "magnetic_loss_tangent:=", "0",')
        A('     ["NAME:magnetic_coercivity", "property_type:=", "VectorProperty",')
        A('      "Magnitude:=", "-890000A_per_meter",')
        A('      "DirComp1:=", "' + _fmt(gx) + '", "DirComp2:=", "' + _fmt(gy) + '", "DirComp3:=", "0"],')
        A('     "mass_density:=", "7400", "youngs_modulus:=", "147000000000"])')
    A('log("materials ok: M270_35A + ' + str(len(pm_entries)) + ' PM directions")')

    # --------------------------------------------------------------- region
    A("")
    A("# 零矢势边界必须在 Region 还是整圆时赋（切孔后会把孔边一起返回）")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.stator_od / 2 + 20))
    A('    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",')
    A('     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('_edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]')
    A('oDesign.GetModule("BoundarySetup").AssignVectorPotential(')
    A('    ["NAME:VectorPotential1", "Edges:=", _edges, "Value:=", "0", "CoordinateSystem:=", ""])')
    A('log("boundary VectorPotential=0 on " + str(len(_edges)) + " edge(s)")')

    # --------------------------------------------------------------- stator
    A("")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.stator_od / 2))
    A('    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "' + C_STEEL + '",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"M270_35A"', "SolveInside:=", True])""")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.stator_id / 2))
    A('    ["NAME:Attributes", "Name:=", "StatorInner", "Flags:=", "", "Color:=", "' + C_STEEL + '",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "StatorOuter",')
    A('                   "Tool Parts:=", "StatorInner"],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A('log("stator ring " + str(round(area_of("StatorOuter"), 4)) + " mm2 (expect ' +
      _fmt(math.pi * ((cfg.stator_od / 2) ** 2 - (cfg.stator_id / 2) ** 2)) + ')")')

    # ---------------------------------------------------------------- slots
    A("")
    A("SLOT_PTS = " + _pts_literal(slot_pts))
    A("_pp = []")
    A("for (x, y) in SLOT_PTS + [SLOT_PTS[0]]:")
    A('    _pp.append(["NAME:PLPoint", "X:=", str(x) + "mm", "Y:=", str(y) + "mm", "Z:=", "0mm"])')
    A("_ss = [")
    for kind, start, npt in slot_segs:
        A('    ["NAME:PLSegment", "SegmentType:=", "' + kind + '", "StartIndex:=", ' +
          str(start) + ', "NoOfPoints:=", ' + str(npt) + '],')
    A("]")
    A("oEditor.CreatePolyline(")
    A('    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,')
    A('     ["NAME:PolylinePoints"] + _pp, ["NAME:PolylineSegments"] + _ss],')
    A('    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A("oEditor.DuplicateAroundAxis(")
    A('    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],')
    A('    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,')
    A('     "WhichAxis:=", "Z", "AngleStr:=", "%gdeg", "Numclones:=", %d],' % (slot_angle, cfg.slots))
    A('    ["NAME:Options", "DuplicateAssignments:=", False])')
    A('_slot_names = ["Slot_1"] + ["Slot_1_" + str(i) for i in range(1, ' + str(cfg.slots) + ')]')
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "StatorOuter",')
    A('                   "Tool Parts:=", ", ".join(_slot_names)],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A('log("slots cut ' + str(cfg.slots) + ' -> stator " + str(round(area_of("StatorOuter"), 4)) +')
    A('    " mm2 (expect ' + _fmt(exp_stator) + ')")')

    # ---------------------------------------------------------------- rotor
    A("")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % r_rot)
    A('    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "' + C_STEEL + '",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"M270_35A"', "SolveInside:=", True])""")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.rotor_id / 2))
    A('    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "RotorOuter",')
    A('                   "Tool Parts:=", "Shaft"], ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A("")
    A("PM = [")
    for name, pts, mat, _gx, _gy, color in pm_entries:
        A('    ("' + name + '", ' + _pts_literal(pts) + ', "' + mat + '", "' + color + '"),')
    A("]")
    A("for (_n, _p, _m, _c) in PM:")
    A("    poly(_n, _p, _m, _c)")
    A('_pm_names = ", ".join([p[0] for p in PM])')
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", _pm_names],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", True])')
    A('log("rotor pockets cut -> rotor " + str(round(area_of("RotorOuter"), 4)) + " mm2 (expect ' +
      _fmt(exp_rotor) + ')")')

    # ----------------------------------------------------------------- band
    A("")
    A("band_r = (%g + %g) / 4.0" % (cfg.rotor_od, cfg.stator_id))
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],')
    A('    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",')
    A('     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")

    # ------------------------------------------------- airgap ring (I17)
    # 独立 vacuum 环：外半径=定子内径 46.5，内半径=气隙中线 46.1625，厚 0.3375。
    # 与 Band（整圆 R=46.1625，包住转子、绑定运动）共面于 R=46.1625 —— 是**面接触**
    # 不是体积重叠，Maxwell 只报"边界穿越"型 intersect，共面贴边不报。
    # 为什么不动 Band：MAXWELL_INTERNALS.md §9.2 实测——Band 做成气隙环/收进转子
    # 会触发 `No objects within the band`（运动带失效）。保留整圆 Band + 外壁再贴
    # 一个独立环，是同时满足"独立气隙环"与"运动带包住转子"的唯一拓扑。
    # 假设=待验证：M1' 真机 Validate_OK + 无 intersect + 117 sheet 为准。
    A("")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.stator_id / 2))
    A('    ["NAME:Attributes", "Name:=", "AirgapRing", "Flags:=", "", "Color:=", "(180 180 255)",')
    A('     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.rotor_od / 2 + cfg.airgap / 2))
    A('    ["NAME:Attributes", "Name:=", "AirgapRingInner", "Flags:=", "", "Color:=", "(180 180 255)",')
    A('     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "AirgapRing",')
    A('                   "Tool Parts:=", "AirgapRingInner"],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A('log("airgap ring -> AirgapRing " + str(round(area_of("AirgapRing"), 4)) + " mm2 (expect ' +
      _fmt(math.pi * ((cfg.stator_id / 2) ** 2 -
                     (cfg.rotor_od / 2 + cfg.airgap / 2) ** 2)) + ')")')

    # ---------------------------------------------------------------- coils
    A("")
    A("# 96 个线圈边：上层 = 线圈 s 的 go 边，下层 = 线圈 s−y 的回边")
    A("COILS = [")
    for name, layer, pts in coils:
        A('    ("' + name + '", "' + layer + '", ' + _pts_literal(pts) + '),')
    A("]")
    A("for (_n, _l, _p) in COILS:")
    A('    poly(_n, _p, "copper", "' + C_COIL + '")')
    A('log("coils created " + str(len(COILS)) + " (T area ' + _fmt(layers["area_upper"]) +
      ', B area ' + _fmt(layers["area_lower"]) + ')")')

    # -------------------------------------------------------- region split
    A("")
    A('_tools = ["StatorOuter", "RotorOuter", "Band", "AirgapRing"] + [p[0] for p in PM] + [c[0] for c in COILS]')
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "Region", "Tool Parts:=", ", ".join(_tools)],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", True])')
    A('log("region split -> region " + str(round(area_of("Region"), 4)) + " mm2")')

    # -------------------------------------------------------------- winding
    A("")
    A('oModule = oDesign.GetModule("BoundarySetup")')
    if currents is None:
        # 空载（M1'/M2'）：三相 0A，零电流无额定转矩，只验 BEMF/THD/齿槽/Bg
        A('CURRENTS = {"A": "0A", "B": "0A", "C": "0A"}')
    else:
        # 负载（M3）：三相正弦电流，表达式由 CPython 侧按实测 BEMF 算好（字面量）
        A('CURRENTS = ' + repr(currents))
    A('for phase in ["A", "B", "C"]:')
    A("    oModule.AssignWindingGroup(")
    A('        ["NAME:Winding" + phase, "Type:=", "Current", "IsSolid:=", False,')
    A('         "Current:=", CURRENTS[phase], "Resistance:=", "0.1ohm", "Inductance:=", "0.001H",')
    A('         "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])')
    A("CPS = " + str(cfg.conductors_per_slot) + "   # TEMP：I3 未定源，仅影响 Conductor number")
    A("SIDES = [")
    for r in wind["rows"]:
        A('    ("' + r["obj"] + '", "' + r["phase"] + '", "' +
          ("Positive" if r["sign"] > 0 else "Negative") + '"),')
    A("]")
    A("for (_o, _ph, _pol) in SIDES:")
    A('    oModule.AssignCoil(["NAME:" + _ph + "_" + _o, "Objects:=", [_o],')
    A('                       "Conductor number:=", str(CPS), "PolarityType:=", _pol,')
    A('                       "Winding:=", "Winding" + _ph])')
    A('log("winding " + str(len(SIDES)) + " sides, CPS=" + str(CPS))')

    # ------------------------------------------------------------- boundary
    A("")
    A('oDesign.GetModule("ModelSetup").AssignBand(')
    A('    ["NAME:BandData", "Move Type:=", "Rotate", "Coordinate System:=", "Global",')
    A('     "Axis:=", "Z", "Is Positive:=", True, "Init Pos:=", "0deg",')
    A('     "HasRotateLimit:=", False, "NonCylindrical:=", False,')
    A('     "Consider Mechanical Transient:=", False, "Angular Velocity:=", "1500rpm",')
    A('     "Objects:=", ["Band"]])')

    # ----------------------------------------------------------------- mesh
    A("")
    A('oMesh = oDesign.GetModule("MeshSetup")')
    A('oMesh.AssignLengthOp(["NAME:Mesh_Band", "Objects:=", ["Band"],')
    A('                      "MaxLength:=", "0.25mm", "RestrictElem:=", False, "RestrictLength:=", True])')
    A('oMesh.AssignLengthOp(["NAME:Mesh_Stator", "Objects:=", ["StatorOuter"],')
    A('                      "MaxLength:=", "0.9mm", "RestrictElem:=", False, "RestrictLength:=", True])')
    A('oMesh.AssignLengthOp(["NAME:Mesh_Rotor", "Objects:=", ["RotorOuter"],')
    A('                      "MaxLength:=", "1.2mm", "RestrictElem:=", False, "RestrictLength:=", True])')
    A('oMesh.AssignLengthOp(["NAME:Mesh_PM", "Objects:=", [p[0] for p in PM],')
    A('                      "MaxLength:=", "0.5mm", "RestrictElem:=", False, "RestrictLength:=", True])')

    # --------------------------------------------------------------- solver
    A("")
    A('oDesign.GetModule("AnalysisSetup").InsertSetup("Transient",')
    A('    ["NAME:Setup1", "StopTime:=", "0.02s", "TimeStep:=", "0.00005s",')
    A('     "SaveFieldsType:=", "Every N Steps", "UseAdaptiveTimeStep:=", False,')
    A('     "NonlinearSolverResidual:=", "0.0001", "SmoothBHCurve:=", False])')

    # ------------------------------------------------------------ inventory
    A("")
    A("try:")
    A('    objs = sorted(list(oEditor.GetObjectsInGroup("Sheets")))')
    A('    log("SHEETS=" + str(len(objs)))')
    A("    _pref = {}")
    A("    for o in objs:")
    A('        k = o.split("_")[0]')
    A("        _pref[k] = _pref.get(k, 0) + 1")
    A('    log("PREFIX " + " ".join([k + "=" + str(_pref[k]) for k in sorted(_pref)]))')
    A('    for nm in ("Region", "StatorOuter", "RotorOuter", "Band", "AirgapRing"):')
    A('        log("AREA " + nm + " " + str(round(area_of(nm), 4)))')
    A("    _amin, _amax = 1e9, -1e9")
    A("    for i in range(1, " + str(cfg.slots) + " + 1):")
    A('        for pfx in ("Coil_T", "Coil_B"):')
    A('            a = area_of(pfx + ("%02d" % i))')
    A("            _amin = min(_amin, a)")
    A("            _amax = max(_amax, a)")
    A('    log("COIL_AREA min=" + str(round(_amin, 4)) + " max=" + str(round(_amax, 4)))')
    A("    for i in range(1, " + str(len(pm_entries)) + " + 1):")
    A('        nm = "PM_%02d" % i')
    A("        ids = list(oEditor.GetFaceIDs(nm))")
    A("        c = oEditor.GetFaceCenter(ids[0])")
    A('        log("PM " + nm + " area=" + str(round(area_of(nm), 4)) +')
    A('            " center=(" + str(round(float(c[0]), 4)) + ", " + str(round(float(c[1]), 4)) + ")")')
    A("except Exception:")
    A('    log("INVENTORY_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("")
    A("try:")
    A("    oDesign.ValidateDesign()")
    A('    log("VALIDATE_OK")')
    A("except Exception:")
    A('    log("VALIDATE_NA: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("")
    A("try:")
    A('    oProject.SaveAs(r"' + aedt_out + '", True)')
    A('    log("SAVED_OK ' + aedt_out + '")')
    A("except Exception:")
    A('    log("SAVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("")
    A('log("TOTAL " + str(round(time.time() - t_all, 1)) + "s")')
    A('log("=== end ===")')
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M1' 建模脚本生成")
    ap.add_argument("--run", action="store_true", help="生成后直接调用 ansysedt 真机建模")
    ap.add_argument("--out", default=SCRIPT)
    ap.add_argument("--aedt", default=AEDT_OUT,
                    help="工程落盘路径（换版本时用新名，保留上一版可比对）")
    args = ap.parse_args(argv)

    cfg = ipm_geom.IPMConfig()
    text = build_script(cfg, args.aedt)
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("生成：%s（%.1f KB，%d 行）" % (args.out, len(text) / 1024.0, text.count("\n")))
    print("BH 曲线：%d 点（M270_35A），工程 -> %s" % (len(BH_M270_35A), args.aedt))
    compile(text, args.out, "exec")
    print("语法自检：CPython compile OK")

    if args.run:
        cmd = [AEDT, "-RunScriptAndExit", args.out]
        print("运行：%s" % " ".join(cmd))
        rc = subprocess.call(cmd)
        print("ansysedt rc=%d" % rc)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
