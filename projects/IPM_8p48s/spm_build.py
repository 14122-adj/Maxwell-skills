#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 8p48s 贴片式平行充磁 M1 建模脚本生成器（KEEP，2026-11-26）

为什么独立而不改 ipm_build.py
-----------------------------
SPM_DESIGN.md §4 要求"只改转子，定子/绕组/气隙/电流不动"，且 IPM baseline 已冻结
（斜槽 0.75 T_avg 27.0286 / 峰峰 3.2855% PASS）。改 ipm_build.py 会打断 IPM 证据链。
本文件**只 import** ipm_geom / ipm_winding 的定子与绕组几何，转子段独立重写。

几何自洽（关键，与 SPM_DESIGN.md §2 的口径差异已写账本 I31）
-------------------------------------------------------------
转子铁芯 OD 86.89 (r=43.445)，贴片厚 2.38 ⇒ 磁钢外表面 r=45.825，
恰好等于 IPM 转子 OD 半径 (91.65/2)。故气隙 0.675、Band=46.1625、
AirgapRing 46.5/46.1625（厚 0.3375）、Mesh_Airgap 0.15mm（2.58 层）
**全部沿用 IPM，一字不改**。SPM_DESIGN.md 里"Band=43.7825 / 环厚 2.7175"
把贴片占据的空间重复扣成气隙，会导致 Band 切过磁钢 (43.445–45.825)，
物理不成立；本实现取自洽值，FEA 用气隙场探针实测复核（assumption=待验证）。

平行充磁：每极一恒定矢量沿自身极轴 θ=k·45°，N(+)/S(−) 靠符号翻转，
相邻极轴差 45°（不是相邻矢量严格反号）——与 scripts/pm_builder.py 2026-11-25
修复分支及 test_spm_magnetization_alternates_n_s 同口径。

用法
----
    python spm_build.py                 # 生成脚本 + CPython 语法自检
    python spm_build.py --run           # 生成后真机建模（ansysedt -RunScriptAndExit）
    python spm_build.py --core-od X --aedt <path> --log <path>   # 厚度单变量扫描
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from dataclasses import dataclass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ipm_geom  # noqa: E402
import ipm_winding  # noqa: E402

AEDT = r"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe"
RUN_DIR = r"D:/ANSYS_Run"
SCRIPT = RUN_DIR + "/spm_m1_build.py"
AEDT_OUT = RUN_DIR + "/SPM_8p48s_M1.aedt"
LOG = RUN_DIR + "/spm_m1.log"

C_STEEL = "(132 132 193)"
C_COIL = "(255 128 0)"
C_N = "(255 0 0)"
C_S = "(0 0 255)"

ARC_SEG = 10          # 每极每条弧的折线段数（180 点/极，圆弧近似误差 <0.01mm）
SHAFT_R = 15.0        # 轴孔半径，沿用 IPM rotor_id/2


@dataclass
class SPMConfig(ipm_geom.IPMConfig):
    """在 IPMConfig 上只增转子字段；定子/绕组/气隙/叠厚全部继承。"""

    spm_core_od: float = 86.89       # 铁芯 OD + 装配胶缝的基准（磁钢内表面直径，mm）
    pm_pole_arc: float = 0.85        # 极弧系数（贴片张角 = 0.85 × 45° = 38.25°）
    # 2026-11-26 I32：贴片内表面与铁芯外表面严格共面时，Maxwell 求解器报
    # "Parts PM_01..08 and RotorOuter intersect"（ValidateDesign 不报，Analyze 才报）。
    # 留 0.02 mm 装配胶缝（机械上合理的贴片胶层），铁芯 OD 缩小该量，
    # 磁钢内外半径与气隙 0.675 / Band 46.1625 一律不变。assumption=待验证。
    pm_glue_gap: float = 0.02

    @property
    def spm_pm_t(self) -> float:
        """贴片厚度：由 (等效转子 OD − 磁钢内表面直径)/2 推，单一来源。"""
        return (self.rotor_od - self.spm_core_od) / 2.0

    @property
    def spm_iron_r(self) -> float:
        """铁芯外半径 = 磁钢内半径 − 装配胶缝。"""
        return self.spm_core_od / 2.0 - self.pm_glue_gap


def _fmt(v: float) -> str:
    return ("%.6f" % v).rstrip("0").rstrip(".")


def _pts_literal(pts) -> str:
    return "[" + ", ".join("(%s, %s)" % (_fmt(x), _fmt(y)) for (x, y) in pts) + "]"


def polygon_area(pts) -> float:
    """shoelace，返回绝对值 mm²。"""
    s = 0.0
    for i, (x, y) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        s += x * y2 - x2 * y
    return abs(s) / 2.0


def spm_magnets(cfg: SPMConfig) -> list:
    """返回 8 块弧形贴片：多边形点、平行充磁矢量、极性、面积。

    磁钢外表面严格贴在 r = rotor_od/2 = 45.825（= 气隙内边界），
    内表面贴铁芯 r = spm_core_od/2 = 43.445。极弧角 = pm_pole_arc × 极距。
    """
    r_in = cfg.spm_core_od / 2.0
    r_out = cfg.rotor_od / 2.0
    pole_pitch = 360.0 / cfg.poles
    arc_span = cfg.pm_pole_arc * pole_pitch
    out = []
    for k in range(cfg.poles):
        center = k * pole_pitch
        a0 = center - arc_span / 2.0
        sign = 1.0 if k % 2 == 0 else -1.0     # 偶数极 N，奇数极 S
        ang = math.radians(center)
        gx, gy = sign * math.cos(ang), sign * math.sin(ang)
        pts = []
        for j in range(ARC_SEG + 1):
            a = math.radians(a0 + arc_span * j / ARC_SEG)
            pts.append((r_in * math.cos(a), r_in * math.sin(a)))
        for j in range(ARC_SEG, -1, -1):
            a = math.radians(a0 + arc_span * j / ARC_SEG)
            pts.append((r_out * math.cos(a), r_out * math.sin(a)))
        out.append(dict(pole=k, pts=pts, gx=gx, gy=gy, sign=sign,
                        area=polygon_area(pts), center_deg=center,
                        name="PM_%02d" % (k + 1),
                        mat="NdFe35_%02d" % (k + 1)))
    return out


def spm_snapshot(cfg: SPMConfig) -> dict:
    """几何自检的全部期望值（供 spm_check.py 独立复核用，但不写 FEA 结论）。"""
    mags = spm_magnets(cfg)
    r_core = cfg.spm_core_od / 2.0
    r_out = cfg.rotor_od / 2.0
    # 铁芯外半径缩装配胶缝（I32）；贴片内表面仍在 r_core，二者不共面
    rotor_area = math.pi * (cfg.spm_iron_r ** 2 - SHAFT_R ** 2)
    ring_area = math.pi * ((cfg.stator_id / 2) ** 2 -
                           (cfg.rotor_od / 2 + cfg.airgap / 2) ** 2)
    return dict(
        core_od=cfg.spm_core_od, iron_r=cfg.spm_iron_r, glue_gap=cfg.pm_glue_gap,
        pm_t=cfg.spm_pm_t, pm_inner_r=r_core, pm_outer_r=r_out,
        airgap=cfg.stator_id / 2 - r_out,
        band_r=(cfg.rotor_od + cfg.stator_id) / 4.0,
        ring_inner_r=cfg.rotor_od / 2 + cfg.airgap / 2,
        ring_area=ring_area, rotor_area=rotor_area,
        magnet_area_each=[round(m["area"], 4) for m in mags],
        magnet_total=round(sum(m["area"] for m in mags), 4),
        polarity=[("N" if m["sign"] > 0 else "S") for m in mags],
        vectors=[(round(m["gx"], 6), round(m["gy"], 6)) for m in mags],
        n_sheets=5 + len(mags) + cfg.slots * 2,
    )


def build_script(cfg: SPMConfig, aedt_out: str = AEDT_OUT, currents=None,
                 case_tag: str = "M1_SPM", stop_time: str = "0.02s",
                 time_step: str = "0.00005s", log_path: str = LOG) -> str:
    """生成 SPM M1 建模 IronPython（结构与 ipm_build.build_script 同构）。"""
    mags = spm_magnets(cfg)
    snap = spm_snapshot(cfg)

    i1 = ipm_geom.derive_slot(cfg)
    layers = ipm_geom.coil_layers(cfg)
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

    ring = math.pi * ((cfg.stator_od / 2) ** 2 - (cfg.stator_id / 2) ** 2)
    exp_stator = ring - cfg.slots * i1["areas"]["slot_effective"]
    r_core = cfg.spm_core_od / 2.0          # 磁钢内表面半径
    r_iron = cfg.spm_iron_r                # 铁芯外半径（缩胶缝，避免共面 intersect）

    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# SPM 8p48s M1 — 由 projects/IPM_8p48s/spm_build.py 生成，勿手改。")
    A("# 48 槽梨形槽 + 8 块弧形贴片 + 96 线圈边；平行充磁 N/S 交替；不求解。")
    A("import time")
    A("import traceback")
    A("")
    A('LOG = r"' + log_path + '"')
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
    A('log("=== SPM 8p48s ' + case_tag + ' build start ===")')
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
    A('# M270_35A BH（同 ipm_build I13/I14 根因修复：CloneMaterial 从系统库克隆）')
    A('oDefinitionManager.CloneMaterial("JFE_Steel_35JN270", "M270_35A")')
    A('log("material M270_35A: cloned JFE_Steel_35JN270 (BH 66pts, nonlinear)")')
    for m in mags:
        mat = m["mat"]
        gx, gy = m["gx"], m["gy"]
        A('oDefinitionManager.EditMaterial("' + mat + '",')
        A('    ["NAME:' + mat + '", "CoordinateSystemType:=", "Cartesian",')
        A('     ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal", "Structural"]],')
        A('     "permittivity:=", "1", "permeability:=", "1.0997785406",')
        A('     "conductivity:=", "625000",')
        A('     ["NAME:magnetic_coercivity", "property_type:=", "VectorProperty",')
        A('      "Magnitude:=", "-890000A_per_meter",')
        A('      "DirComp1:=", "' + _fmt(gx) + '", "DirComp2:=", "' + _fmt(gy) + '", "DirComp3:=", "0"],')
        A('     "mass_density:=", "7400"])')
    A('log("materials ok: M270_35A + 8 SPM PM (parallel N/S alternating)")')

    # --------------------------------------------------------------- region
    A("")
    A("# 零矢势边界在整圆 Region 上赋")
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
      _fmt(ring) + ')")')

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
    A("# 转子铁芯：实心圆（贴片在外，不挖槽）+ 轴孔")
    A("# I32：铁芯外半径 = 磁钢内半径 − 0.02mm 装配胶缝，避免共面 intersect")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % r_iron)
    A('    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "' + C_STEEL + '",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"M270_35A"', "SolveInside:=", True])""")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % SHAFT_R)
    A('    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",')
    A('     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "RotorOuter",')
    A('                   "Tool Parts:=", "Shaft"], ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A('log("rotor core -> area " + str(round(area_of("RotorOuter"), 4)) + " mm2 (expect ' +
      _fmt(snap["rotor_area"]) + ')")')

    # 8 块弧形贴片（独立 polyline，不与铁芯重叠；内表面共面贴合）
    A("PM = [")
    for m in mags:
        color = C_N if m["sign"] > 0 else C_S
        A('    ("' + m["name"] + '", ' + _pts_literal(m["pts"]) + ', "' + m["mat"] + '", "' + color + '"),')
    A("]")
    A("for (_n, _p, _m, _c) in PM:")
    A("    poly(_n, _p, _m, _c)")
    A('log("SPM magnets created " + str(len(PM)) + " (t=' + _fmt(cfg.spm_pm_t) +
      'mm, arc=0.85, r_in=' + _fmt(r_core) + ', r_out=' + _fmt(cfg.rotor_od / 2) + ')")')
    # I32：Maxwell 对"独立贴片与铁芯相邻"求解时报 intersect（ValidateDesign 不报）。
    # IPM baseline 的做法是对铁芯 Subtract(PM, KeepOriginals=True) 显式建立拓扑边界，
    # SPM 沿用同一手段（磁钢在外、铁芯在内，布尔不改变几何，只消歧）。
    A('_pm_names = ", ".join([p[0] for p in PM])')
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", _pm_names],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", True])')
    A('log("rotor subtract PM (disambiguate topology) -> area " + str(round(area_of("RotorOuter"), 4)))')

    # ----------------------------------------------------------------- band
    A("")
    A("# Band 整圆包住转子铁芯 + 贴片（R=46.1625 = 气隙中线），同 IPM")
    A("band_r = (%g + %g) / 4.0" % (cfg.rotor_od, cfg.stator_id))
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],')
    A('    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",')
    A('     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")

    # ------------------------------------------------- airgap ring (I17)
    A("")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % (cfg.stator_id / 2))
    A('    ["NAME:Attributes", "Name:=", "AirgapRing", "Flags:=", "", "Color:=", "(180 180 255)",')
    A('     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A("oEditor.CreateCircle(")
    A('    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",')
    A('     "ZCenter:=", "0mm", "Radius:=", "%gmm", "WhichAxis:=", "Z"],' % snap["ring_inner_r"])
    A('    ["NAME:Attributes", "Name:=", "AirgapRingInner", "Flags:=", "", "Color:=", "(180 180 255)",')
    A('     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",')
    A("""     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])""")
    A('oEditor.Subtract(["NAME:Selections", "Blank Parts:=", "AirgapRing",')
    A('                   "Tool Parts:=", "AirgapRingInner"],')
    A('                  ["NAME:SubtractParameters", "KeepOriginals:=", False])')
    A('log("airgap ring -> AirgapRing " + str(round(area_of("AirgapRing"), 4)) + " mm2 (expect ' +
      _fmt(snap["ring_area"]) + ')")')

    # ---------------------------------------------------------------- coils
    A("")
    A("COILS = [")
    for name, layer, pts in coils:
        A('    ("' + name + '", "' + layer + '", ' + _pts_literal(pts) + '),')
    A("]")
    A("for (_n, _l, _p) in COILS:")
    A('    poly(_n, _p, "copper", "' + C_COIL + '")')
    A('log("coils created " + str(len(COILS)))')

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
        A('CURRENTS = {"A": "0A", "B": "0A", "C": "0A"}')
    else:
        A('CURRENTS = ' + repr(currents))
    A('for phase in ["A", "B", "C"]:')
    A("    oModule.AssignWindingGroup(")
    A('        ["NAME:Winding" + phase, "Type:=", "Current", "IsSolid:=", False,')
    A('         "Current:=", CURRENTS[phase], "Resistance:=", "0.1ohm", "Inductance:=", "0.001H",')
    A('         "Voltage:=", "0V", "ParallelBranchesNum:=", "1"])')
    A("CPS = " + str(cfg.conductors_per_slot))
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
    A('oMesh.AssignLengthOp(["NAME:Mesh_Airgap", "Objects:=", ["AirgapRing"],')
    A('                      "MaxLength:=", "0.15mm", "RestrictElem:=", False, "RestrictLength:=", True])')

    # --------------------------------------------------------------- solver
    A("")
    A('oDesign.GetModule("AnalysisSetup").InsertSetup("Transient",')
    A('    ["NAME:Setup1", "StopTime:=", "' + stop_time + '", "TimeStep:=", "' + time_step + '",')
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
    A("    for i in range(1, " + str(len(mags)) + " + 1):")
    A('        nm = "PM_%02d" % i')
    A('        ids = list(oEditor.GetFaceIDs(nm))')
    A('        c = oEditor.GetFaceCenter(ids[0])')
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
    ap = argparse.ArgumentParser(description="SPM 8p48s 贴片平行充磁建模脚本生成")
    ap.add_argument("--run", action="store_true", help="生成后真机建模")
    ap.add_argument("--out", default=SCRIPT)
    ap.add_argument("--aedt", default=AEDT_OUT)
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--core-od", type=float, default=None,
                    help="转子铁芯 OD(mm)，默认 86.89；单变量扫描时用")
    ap.add_argument("--tag", default="M1_SPM")
    args = ap.parse_args(argv)

    cfg = SPMConfig()
    if args.core_od is not None:
        cfg.spm_core_od = args.core_od
    # log 路径作为显式参数传入，避免模块级可变状态
    text = build_script(cfg, args.aedt, case_tag=args.tag, log_path=args.log)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    snap = spm_snapshot(cfg)
    print("生成：%s（%.1f KB，%d 行）" % (args.out, len(text) / 1024.0, text.count("\n")))
    print("几何：core_od=%.3f pm_t=%.3f 气隙=%.4f Band=%.4f 环内=%.4f sheet=%d" %
          (snap["core_od"], snap["pm_t"], snap["airgap"], snap["band_r"],
           snap["ring_inner_r"], snap["n_sheets"]))
    print("极性：%s" % "".join(snap["polarity"]))
    print("工程：%s" % args.aedt)
    compile(text, args.out, "exec")
    print("语法自检：CPython compile OK")

    if args.run:
        os.makedirs(RUN_DIR, exist_ok=True)
        cmd = [AEDT, "-RunScriptAndExit", args.out]
        print("运行：%s" % " ".join(cmd))
        rc = subprocess.call(cmd)
        print("ansysedt rc=%d" % rc)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
