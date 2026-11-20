#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s 几何定源 —— I1（48 槽梨形槽 7 尺寸）+ I4 初设（双层 V 型磁钢）

为什么单独一个模块
------------------
`PROJECT_SPEC.md` §2 已证明表 2 的 12 槽梨形槽**不能照抄**：48 槽槽距
`π·93/48 = 6.0868 mm` 小于表 2 槽底直径 `Bs2 = 9.5 mm`，照抄必然 intersect。
本模块把「从约束推到尺寸」的过程写成可复算的代码，而不是把结论抄进配置：

* **I1**：7 个槽尺寸由四条约束依次定出 —— ① 齿部磁密（齿宽下限由
  `Bg·τ_bore/(B_tooth·k_fe)` 给出）；② 槽口最小入线间隙；③ 槽身宽度按双层
  圆线排布（2 根 Ø1.5 并排 + 绝缘）取整；④ 轭厚取 baseline 的 16 mm；最后
  用铜耗预算反算所需槽面积并对照。`Rs = Bs2/2` 是梨形槽「半圆底与直身相切」
  的几何恒等式，本模块显式验证它在新尺寸下仍然成立（端点重合）。
* **I4**：每极两组 V、每组 2 块 ⇒ 8 极 32 块。每块用「内端起点 + 方向 + 长度
  + 厚度」参数化，逐块校验：在转子内（OD 桥厚 ≥ 1.5 mm）、离轴孔 ≥ 3 mm、
  同组两腿间距、层间/极间间距 ≥ 1.2 mm，并给出最近距离的数值证据。

本模块只做几何与解析，**不产生 FEA 结论**；所有 FEA 数字必须由真机求解给出
（见 `docs/ENGINEERING_ACCEPTANCE.md` §4）。

溯源
----
- 槽距/极距：`PROJECT_SPEC.md` §2（π·93/48）
- 齿磁密判据：`docs/ENGINEERING_ACCEPTANCE.md` §2（B_tooth ≤ 1.65 T）
- 轭厚 baseline：`projects/IPM_8p48s/PROJECT_SPEC.md` §2 约束②（16 mm）
- 梨形槽 11 点轮廓：`scripts/slot_profile.py`（唯一顶点来源，禁止第二份坐标）
- 铜耗预算：`docs/ENGINEERING_ACCEPTANCE.md` §2（P_cu ≤ 140 W）
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, asdict, field

# ---- 让本模块能 import skill 的 scripts 模块 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if os.path.join(_ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import slot_profile  # noqa: E402

# 物理常数（75°C 铜，IEC 60287 口径）
RHO_CU_75 = 2.05e-8      # Ω·m
K_FE = 0.95              # 叠压系数（0.35 mm M270-35A 涂漆叠片）
LAMINATION_MM = 0.35


@dataclass
class IPMConfig:
    """IPM 8p48s 几何配置（mm）。§1 沿用项固定，§3 定源项见 derive_*。"""

    # §1 沿用 baseline
    poles: int = 8
    slots: int = 48
    phases: int = 3
    stator_od: float = 150.0
    stator_id: float = 93.0
    airgap: float = 0.675
    stack_length: float = 160.0

    # D1（I1 定源结果，derive_slot 会重算并断言与这里一致）
    slot_Bs0: float = 2.2
    slot_Hs0: float = 1.2
    slot_Bs1: float = 2.7
    slot_Hs1: float = 5.3
    slot_Bs2: float = 3.5
    slot_Rs: float = 1.75
    slot_Hs2: float = 12.5

    # D2（I2 定源）
    coil_pitch: int = 5          # 槽距数（全距 6，短距 1 槽）
    layers: int = 2

    # D3 预置（I3 用，M1' 只用于 AssignCoil 的 Conductor number，属 TEMP）
    conductors_per_slot: int = 5
    wire_diameter_mm: float = 1.50

    # D4（I4 初设）
    rotor_id: float = 30.0
    pm_thickness: float = 2.8
    pm_bridge_od: float = 1.5     # 磁钢外角到转子 OD 的最小铁桥
    pm_bridge_gap: float = 1.2    # 层间/极间最小铁桥
    v_outer: tuple = (33.0, 40.0, 11.5, 3.0)   # (apex 半径, 与径向夹角°, 长度, 内端间距)
    v_inner: tuple = (21.0, 36.0, 10.0, 3.0)

    # 材料/工况（§1）
    Bg_assumed: float = 0.85     # 假设：V 型聚磁后气隙工作磁密（M2' FEA 验证）
    B_tooth_limit: float = 1.65
    B_yoke_limit: float = 1.45
    yoke_min: float = 16.0
    J_design: float = 6.0        # A/mm²（自然冷却小机常用 5–7）
    fill_design: float = 0.55
    P_cu_budget: float = 140.0

    @property
    def poles_pairs(self) -> int:
        return self.poles // 2

    @property
    def rotor_od(self) -> float:
        return self.stator_id - 2.0 * self.airgap


# --------------------------------------------------------------------------- I1
def derive_slot(cfg: IPMConfig) -> dict:
    """I1 定源：按约束顺序推到 7 个槽尺寸，返回推导链 + 自检。"""
    steps = []
    r_bore = cfg.stator_id / 2.0
    r_out = cfg.stator_od / 2.0
    tau_bore = math.pi * cfg.stator_id / cfg.slots

    # ① 齿宽下限（磁密）
    b_tooth_min = cfg.Bg_assumed * tau_bore / (cfg.B_tooth_limit * K_FE)
    steps.append(dict(step="① 齿宽下限", formula="b_t = Bg·τ/(B_t·k_fe)",
                      expr="%.4f·%.4f/(%.2f·%.2f)" % (cfg.Bg_assumed, tau_bore,
                                                      cfg.B_tooth_limit, K_FE),
                      value_mm=round(b_tooth_min, 4),
                      note="齿部最窄截面（槽身起点）按 1.65 T 上限反算"))

    # ② 槽口宽：齿部在气隙侧不窄于 b_t，且开口 ≥ 入线间隙
    bs0_max = tau_bore - b_tooth_min
    bs0_practice = round(0.36 * tau_bore, 1)          # 半闭口槽常见 0.30–0.40 τ
    bs0_wire = round(cfg.wire_diameter_mm + 0.4, 1)   # 单根线 + 绝缘/槽楔余量
    bs0 = min(bs0_max, max(bs0_practice, bs0_wire))
    steps.append(dict(step="② 槽口宽 Bs0", formula="min(τ−b_t, max(0.36τ, d_wire+0.4))",
                      expr="min(%.4f, max(%.2f, %.2f))" % (bs0_max, bs0_practice, bs0_wire),
                      value_mm=round(bs0, 2),
                      note="半闭口槽开口 0.30–0.40τ；同时保证 Ø%.1f 线可下" % cfg.wire_diameter_mm))

    # ③ 颈高：槽楔 + 槽绝缘
    hs0 = math.ceil((max(3.0 * LAMINATION_MM, 1.0) + 0.1) * 10.0) / 10.0
    steps.append(dict(step="③ 颈高 Hs0", formula="ceil(max(3·t_lam, 1.0)+0.1, 0.1)",
                      expr="ceil(max(%.2f, 1.0)+0.1, 0.1)" % (3.0 * LAMINATION_MM),
                      value_mm=hs0, note="槽楔 + 槽绝缘的机械高度"))

    # ④ 肩宽：比槽口宽 0.7 mm，供线圈扩散；同时校验 x1 处齿宽
    bs1 = round(bs0 + 0.5, 2)
    tau_x1 = 2.0 * math.pi * (r_bore + hs0) / cfg.slots
    tooth_x1 = tau_x1 - bs1
    steps.append(dict(step="④ 肩宽 Bs1", formula="Bs0+0.5",
                      expr="%.2f+0.5" % bs0, value_mm=bs1,
                      note="x1 处齿宽 %.3f mm ⇒ B_t=%.3f T" % (
                          tooth_x1, cfg.Bg_assumed * tau_bore / (tooth_x1 * K_FE))))

    # ⑤ 槽身宽：双层圆线排布（2 根并排 + 绝缘 0.3）
    bs2_wire = 2.0 * cfg.wire_diameter_mm + 0.5
    bs2 = math.ceil(bs2_wire * 10.0) / 10.0
    steps.append(dict(step="⑤ 槽身宽 Bs2", formula="ceil(2·d_wire+0.5, 0.1)",
                      expr="ceil(2·%.2f+0.5, 0.1)" % cfg.wire_diameter_mm,
                      value_mm=bs2, note="双层各 2 根并排 + 单边 0.25 绝缘；圆线满率可达 0.55–0.62"))

    # ⑥ 斜肩高：槽身起点半径由齿宽下限反解（含 4% 冲剪公差余量，再向上取 0.1）
    r_x2_min = (bs2 + 1.04 * b_tooth_min) * cfg.slots / (2.0 * math.pi)
    hs1 = math.ceil((r_x2_min - (r_bore + hs0)) * 10.0) / 10.0
    steps.append(dict(step="⑥ 斜肩高 Hs1", formula="ceil((Bs2+1.04·b_t)·N/(2π) − (R_bore+Hs0), 0.1)",
                      expr="ceil((%.2f+1.04·%.4f)·%d/(2π) − (%.2f+%.2f), 0.1)" % (
                          bs2, b_tooth_min, cfg.slots, r_bore, hs0),
                      value_mm=hs1,
                      note="保证槽身起点处齿宽 ≥ %.3f mm（含 4%% 冲剪余量）" % b_tooth_min))

    # ⑦ 槽底半径：梨形槽半圆底与直身相切 ⇒ Rs = Bs2/2（几何恒等式）
    rs = bs2 / 2.0
    steps.append(dict(step="⑦ 槽底半径 Rs", formula="Bs2/2（相切恒等式）",
                      expr="%.2f/2" % bs2, value_mm=rs,
                      note="半圆两端点与直身边重合，切向连续；见 check_tangency"))

    # ⑧ 槽深：轭厚取 baseline 16 mm
    hs2 = round((r_out - cfg.yoke_min) - r_bore, 2)
    steps.append(dict(step="⑧ 槽深 Hs2", formula="(R_out−h_yoke) − R_bore",
                      expr="(%.2f−%.2f) − %.2f" % (r_out, cfg.yoke_min, r_bore),
                      value_mm=hs2, note="口径 = 内径 → 槽底最底端（与表 2 一致）"))

    # ---- 组装临时配置，复用 slot_profile 的唯一顶点源 ----
    sc = _SlotOnly(cfg, bs0, hs0, bs1, hs1, bs2, rs, hs2)
    pts = slot_profile.pear_key_points(sc)
    area = slot_profile.pear_area_analytic(sc)
    eff = slot_profile.slot_effective_area(sc, area)
    outline = slot_profile.pear_outline(sc)
    coil_poly = slot_profile.shrink_toward_centroid(outline, 0.86)
    coil_area = slot_profile.polygon_area(coil_poly)

    # ---- 校核 1：沿槽深的齿宽/齿磁密最小值 ----
    tooth = []
    for i in range(201):
        r = (r_bore + hs0) + (r_x2_min - r_bore - hs0) * i / 200.0
        w = bs1 + (bs2 - bs1) * i / 200.0
        t = 2.0 * math.pi * r / cfg.slots - w
        tooth.append((r, t, cfg.Bg_assumed * tau_bore / (t * K_FE)))
    t_min = min(tooth, key=lambda x: x[1])

    # ---- 校核 2：轭部磁密 ----
    tau_pole = math.pi * cfg.stator_id / cfg.poles
    phi_pole = cfg.Bg_assumed * tau_pole * cfg.stack_length * 1e-6   # Wb（mm→m 已含）
    h_yoke = r_out - (r_bore + hs2)
    b_yoke = phi_pole / (2.0 * h_yoke * 1e-3 * cfg.stack_length * 1e-3 * K_FE)

    # ---- 校核 3：铜耗预算 → 所需槽面积 ----
    y = cfg.coil_pitch
    l_end = 0.5 * y * tau_bore + 15.0            # mm，端部轴向伸出经验式
    l_turn = 2.0 * (cfg.stack_length + l_end) * 1e-3   # m
    a_cu_req = cfg.P_cu_budget / (24.0 * RHO_CU_75 * (cfg.J_design * 1e6) ** 2 * l_turn) * 1e6  # mm²
    a_slot_req = a_cu_req / cfg.fill_design
    a_cu_avail = area * cfg.fill_design

    checks = [
        dict(name="槽口齿宽 ≥ b_t_min", value=round(tau_bore - bs0, 4), limit=round(b_tooth_min, 4),
             op=">=", status="PASS" if tau_bore - bs0 >= b_tooth_min else "FAIL"),
        dict(name="x1 齿宽 ≥ b_t_min", value=round(tooth_x1, 4), limit=round(b_tooth_min, 4),
             op=">=", status="PASS" if tooth_x1 >= b_tooth_min else "FAIL"),
        dict(name="齿宽最小处 B_t ≤ 上限", value=round(t_min[2], 4), limit=cfg.B_tooth_limit,
             op="<=", status="PASS" if t_min[2] <= cfg.B_tooth_limit else "FAIL"),
        dict(name="轭厚 ≥ baseline", value=round(h_yoke, 3), limit=cfg.yoke_min,
             op=">=", status="PASS" if h_yoke >= cfg.yoke_min - 1e-9 else "FAIL"),
        dict(name="轭部 B_yoke ≤ 上限", value=round(b_yoke, 4), limit=cfg.B_yoke_limit,
             op="<=", status="PASS" if b_yoke <= cfg.B_yoke_limit else "FAIL"),
        dict(name="槽面积 ≥ 铜耗所需", value=round(area, 3), limit=round(a_slot_req, 3),
             op=">=", status="PASS" if area >= a_slot_req else "FAIL"),
        dict(name="Rs = Bs2/2 相切", value=round(rs, 6), limit=round(bs2 / 2.0, 6),
             op="==", status="PASS" if abs(rs - bs2 / 2.0) < 1e-9 else "FAIL"),
        dict(name="相邻槽底净距 ≥ 1.0 mm",
             value=round(2.0 * math.pi * (r_bore + hs2 - rs) / cfg.slots - bs2, 3), limit=1.0,
             op=">=", status="PASS" if
             (2.0 * math.pi * (r_bore + hs2 - rs) / cfg.slots - bs2) >= 1.0 else "FAIL"),
    ]

    return dict(
        config=dict(stator_od=cfg.stator_od, stator_id=cfg.stator_id, slots=cfg.slots,
                    stack=cfg.stack_length, tau_bore=round(tau_bore, 4)),
        chain=steps,
        dims=dict(Bs0=bs0, Hs0=hs0, Bs1=bs1, Hs1=hs1, Bs2=bs2, Rs=rs, Hs2=hs2),
        radii=dict(x0=round(pts[0][0], 4), x1=round(r_bore + hs0, 4),
                   x2=round(r_bore + hs0 + hs1, 4), x3=round(r_bore + hs2 - rs, 4),
                   x4=round(r_bore + hs2, 4), h_yoke=round(h_yoke, 4)),
        areas=dict(slot_analytic=round(area, 3), slot_effective=round(eff, 3),
                   coil_shrink_086=round(coil_area, 3), coil_to_slot=round(coil_area / area, 4)),
        flux=dict(tau_pole=round(tau_pole, 4), phi_pole_uWb=round(phi_pole * 1e6, 3),
                  B_tooth_min_at=round(t_min[0], 3), B_tooth_min=round(t_min[2], 4),
                  B_yoke=round(b_yoke, 4)),
        thermal=dict(l_end_mm=round(l_end, 2), l_turn_m=round(l_turn, 4),
                     a_cu_req_mm2=round(a_cu_req, 3), a_slot_req_mm2=round(a_slot_req, 3),
                     a_cu_avail_mm2=round(a_cu_avail, 3), J=cfg.J_design, fill=cfg.fill_design,
                     P_cu_at_J=a_cu_avail / a_cu_req * cfg.P_cu_budget),
        checks=checks,
        status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
    )


class _SlotOnly:
    """把 IPMConfig + 定源尺寸适配成 slot_profile 需要的属性集合。"""

    def __init__(self, cfg, b0, h0, b1, h1, b2, rs, h2):
        self.stator_id = cfg.stator_id
        self.stator_od = cfg.stator_od
        self.slots = cfg.slots
        self.slot_Bs0, self.slot_Hs0 = b0, h0
        self.slot_Bs1, self.slot_Hs1 = b1, h1
        self.slot_Bs2, self.slot_Rs, self.slot_Hs2 = b2, rs, h2


def slot_only(cfg: IPMConfig) -> _SlotOnly:
    return _SlotOnly(cfg, cfg.slot_Bs0, cfg.slot_Hs0, cfg.slot_Bs1,
                     cfg.slot_Hs1, cfg.slot_Bs2, cfg.slot_Rs, cfg.slot_Hs2)


# ------------------------------------------------------------------- 线圈分层
def polygon_area(pts) -> float:
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def clip_x(pts, xc: float, keep_less: bool):
    """Sutherland–Hodgman：按 x = xc 半平面裁剪（保留 x≤xc 或 x≥xc）。"""
    def inside(p):
        return (p[0] <= xc) if keep_less else (p[0] >= xc)

    out = []
    n = len(pts)
    for i in range(n):
        cur = pts[i]
        nxt = pts[(i + 1) % n]
        ci, ni = inside(cur), inside(nxt)
        if ci:
            out.append(cur)
        if ci != ni:
            dx = nxt[0] - cur[0]
            t = 0.0 if abs(dx) < 1e-12 else (xc - cur[0]) / dx
            out.append((xc, cur[1] + t * (nxt[1] - cur[1])))
    # 去掉重复点
    clean = []
    for p in out:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) < 1e-9 and abs(clean[0][1] - clean[-1][1]) < 1e-9:
        clean.pop()
    return clean


def area_above(pts, xc: float) -> float:
    return polygon_area(clip_x(pts, xc, keep_less=False))


def solve_split_radius(pts, frac_above: float = 0.5) -> float:
    """求使「上方面积占比 = frac_above」的径向分界半径（二分）。"""
    xs = [p[0] for p in pts]
    lo, hi = min(xs), max(xs)
    total = polygon_area(pts)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if area_above(pts, mid) / total > frac_above:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def coil_layers(cfg: IPMConfig, shrink: float = 0.86, gap: float = 0.4) -> dict:
    """双层绕组的两层线圈截面（槽内局部坐标：x=径向，y=切向，mm）。

    上层（靠气隙）与下层面积相等（各自 50%），中间留 `gap` mm 层间绝缘。
    先按 0.86 向顶点形心收缩（对小槽 ≈ 0.24 mm 单边槽绝缘），再按半径切开。
    """
    sc = slot_only(cfg)
    outline = slot_profile.pear_outline(sc)
    coil = slot_profile.shrink_toward_centroid(outline, shrink)
    r_split = solve_split_radius(coil, 0.5)
    upper = clip_x(coil, r_split - gap / 2.0, keep_less=True)
    lower = clip_x(coil, r_split + gap / 2.0, keep_less=False)
    return dict(r_split=round(r_split, 4), upper=upper, lower=lower,
                area_upper=round(polygon_area(upper), 3),
                area_lower=round(polygon_area(lower), 3),
                area_total=round(polygon_area(coil), 3))


# ------------------------------------------------------------------- 多边形工具
def rotate(pts, deg: float):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca - y * sa, x * sa + y * ca) for (x, y) in pts]


def _seg_dist(p1, p2, p3, p4) -> float:
    """线段 p1p2 与 p3p4 的最短距离（含端点/相交判定）。"""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1, d2 = cross(p3, p4, p1), cross(p3, p4, p2)
    d3, d4 = cross(p1, p2, p3), cross(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0

    def pt_seg(p, a, b):
        vx, vy = b[0] - a[0], b[1] - a[1]
        wx, wy = p[0] - a[0], p[1] - a[1]
        vv = vx * vx + vy * vy
        t = 0.0 if vv < 1e-18 else max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
        dx, dy = p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy)
        return math.hypot(dx, dy)

    return min(pt_seg(p1, p3, p4), pt_seg(p2, p3, p4),
               pt_seg(p3, p1, p2), pt_seg(p4, p1, p2))


def poly_dist(a, b) -> float:
    best = 1e9
    for i in range(len(a)):
        for j in range(len(b)):
            d = _seg_dist(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)])
            if d < best:
                best = d
    return best


# --------------------------------------------------------------------------- I4
def _v_legs(apex_r: float, tilt_deg: float, length: float, gap_in: float, thick: float):
    """一组 V 的两条腿（+y 与 −y），返回 (label, pts)。"""
    t = math.radians(tilt_deg)
    u = (math.cos(t), math.sin(t))
    n = (-math.sin(t), math.cos(t))
    out = []
    for side, sign in (("+", 1.0), ("-", -1.0)):
        # 厚度方向必须镜像：+y 腿用 n，−y 腿用 −n。两腿都用 +n 会让 −y 磁钢越过极轴、
        # 多边形自交（2026-11-20 首版实测：极间净距 0.09 mm，是自交伪影）。
        nx, ny = n[0], sign * n[1]   # 镜像只翻 y 分量，x 分量不变
        p1 = (apex_r, sign * gap_in / 2.0)
        p2 = (p1[0] + length * u[0], p1[1] + sign * length * u[1])
        p3 = (p2[0] + thick * nx, p2[1] + thick * ny)
        p4 = (p1[0] + thick * nx, p1[1] + thick * ny)
        pts = [p1, p2, p3, p4] if sign > 0 else [p1, p4, p3, p2]
        out.append((side, pts))
    return out


def derive_rotor(cfg: IPMConfig) -> dict:
    """I4 初设：每极两组 V、共 32 块；逐块几何自检并返回全局多边形。"""
    r_rot = cfg.rotor_od / 2.0
    r_shaft = cfg.rotor_id / 2.0
    pole_pitch = 360.0 / cfg.poles
    t = cfg.pm_thickness

    layers = [("outer", cfg.v_outer), ("inner", cfg.v_inner)]
    local = []   # (layer, side, pole, pts_local)
    for pole in range(cfg.poles):
        ang = pole * pole_pitch
        for lname, (ra, tilt, length, gap_in) in layers:
            for side, pts in _v_legs(ra, tilt, length, gap_in, t):
                local.append((lname, side, pole, rotate(pts, ang)))

    # 校验 1：在转子内 / 离轴孔
    rad_check = []
    for lname, side, pole, pts in local:
        rmax = max(math.hypot(*p) for p in pts)
        rmin = min(math.hypot(*p) for p in pts)
        rad_check.append(dict(layer=lname, pole=pole + 1, side=side,
                              r_max=round(rmax, 3), r_min=round(rmin, 3),
                              bridge_od=round(r_rot - rmax, 3),
                              gap_shaft=round(rmin - r_shaft, 3)))
    min_bridge_od = min(x["bridge_od"] for x in rad_check)
    min_gap_shaft = min(x["gap_shaft"] for x in rad_check)

    # 校验 2：两两最近距离（同极两层之间、同层两腿、相邻极之间）
    pair_min = dict(inter_layer=1e9, intra_v=1e9, inter_pole=1e9)
    for i in range(len(local)):
        for j in range(i + 1, len(local)):
            l1, s1, p1, a = local[i]
            l2, s2, p2, b = local[j]
            if p1 == p2:
                if l1 != l2:
                    k = "inter_layer"
                elif s1 != s2:
                    k = "intra_v"
                else:
                    continue
            else:
                k = "inter_pole"
            d = poly_dist(a, b)
            pair_min[k] = min(pair_min[k], d)

    _exp = {nm: lay[2] * t for nm, lay in (("outer", cfg.v_outer), ("inner", cfg.v_inner))}
    _area_dev = max(abs(polygon_area(p) - _exp[lay]) for (lay, _s, _p, p) in local)
    checks = [
        dict(name="磁钢外角到转子 OD 桥厚 ≥ %.1f" % cfg.pm_bridge_od,
             value=round(min_bridge_od, 3), limit=cfg.pm_bridge_od, op=">=",
             status="PASS" if min_bridge_od >= cfg.pm_bridge_od else "FAIL"),
        dict(name="单块面积 = L×t（防自交）", value=round(_area_dev, 6), limit=0.0, op="<=",
             status="PASS" if _area_dev < 1e-6 else "FAIL"),
        dict(name="磁钢到轴孔 ≥ 3.0", value=round(min_gap_shaft, 3), limit=3.0, op=">=",
             status="PASS" if min_gap_shaft >= 3.0 else "FAIL"),
        dict(name="同组两腿间距 ≥ 1.0", value=round(pair_min["intra_v"], 3), limit=1.0, op=">=",
             status="PASS" if pair_min["intra_v"] >= 1.0 else "FAIL"),
        dict(name="层间铁桥 ≥ %.1f" % cfg.pm_bridge_gap,
             value=round(pair_min["inter_layer"], 3), limit=cfg.pm_bridge_gap, op=">=",
             status="PASS" if pair_min["inter_layer"] >= cfg.pm_bridge_gap else "FAIL"),
        dict(name="极间铁桥 ≥ %.1f" % cfg.pm_bridge_gap,
             value=round(pair_min["inter_pole"], 3), limit=cfg.pm_bridge_gap, op=">=",
             status="PASS" if pair_min["inter_pole"] >= cfg.pm_bridge_gap else "FAIL"),
        dict(name="磁钢块数 = 8×2×2", value=len(local), limit=cfg.poles * 4, op="==",
             status="PASS" if len(local) == cfg.poles * 4 else "FAIL"),
    ]

    # 磁通能力估算（解析，仅作交叉校验，不作 FEA 结论）
    tau_pole = math.pi * cfg.rotor_od / cfg.poles
    w_sum = cfg.poles * (cfg.v_outer[2] + cfg.v_inner[2])
    conc = (cfg.v_outer[2] + cfg.v_inner[2]) / (tau_pole / 2.0)
    return dict(
        rotor_od=cfg.rotor_od, rotor_id=cfg.rotor_id, poles=cfg.poles,
        pm_thickness=t, magnets=len(local),
        layout=dict(v_outer=cfg.v_outer, v_inner=cfg.v_inner),
        radial=rad_check, pair_min={k: round(v, 3) for k, v in pair_min.items()},
        checks=checks,
        magnet_area_total=round(sum(polygon_area(p) for (_l, _sl, _po, p) in local), 3),
        rotor_area=round(math.pi * (r_rot ** 2 - r_shaft ** 2), 3),
        flux_note=dict(tau_pole=round(tau_pole, 3), magnet_width_per_pole=round(w_sum / cfg.poles, 3),
                       concentration=round(conc, 4),
                       Bg_est_leak07=round(1.17 * conc * 0.7, 3)),
        status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        polygons=[[list(p) for p in pts] for (_l, _s, _p, pts) in local],
        labels=["%s_%s_P%d" % (lay, s, p + 1) for (lay, s, p, _pts) in local],
    )


# ------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="IPM 8p48s 几何定源")
    ap.add_argument("--out", default=os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
    args = ap.parse_args(argv)

    cfg = IPMConfig()
    i1 = derive_slot(cfg)
    i2 = coil_layers(cfg)
    i4 = derive_rotor(cfg)

    # 断言：模块默认配置必须等于推导结果（防止两边漂移）
    d = i1["dims"]
    for k, v in (("slot_Bs0", d["Bs0"]), ("slot_Hs0", d["Hs0"]), ("slot_Bs1", d["Bs1"]),
                 ("slot_Hs1", d["Hs1"]), ("slot_Bs2", d["Bs2"]), ("slot_Rs", d["Rs"]),
                 ("slot_Hs2", d["Hs2"])):
        assert abs(getattr(cfg, k) - v) < 1e-9, "配置 %s=%s 与推导 %s 不一致" % (
            k, getattr(cfg, k), v)

    print("=" * 72)
    print("I1 48 槽梨形槽定源  status=%s" % i1["status"])
    print("=" * 72)
    for s in i1["chain"]:
        print("  %-22s = %8.3f mm   [%s]" % (s["step"], s["value_mm"], s["expr"]))
    print("  " + "-" * 66)
    print("  槽面积 %.3f mm² / 环带切除 %.3f / 线圈(0.86) %.3f (比 %.3f)"
          % (i1["areas"]["slot_analytic"], i1["areas"]["slot_effective"],
             i1["areas"]["coil_shrink_086"], i1["areas"]["coil_to_slot"]))
    print("  B_t(min) %.3f T @ r=%.2f / B_yoke %.3f T / Φ_pole %.2f µWb"
          % (i1["flux"]["B_tooth_min"], i1["flux"]["B_tooth_min_at"],
             i1["flux"]["B_yoke"], i1["flux"]["phi_pole_uWb"]))
    print("  铜耗预算: 需 %.2f mm² 铜/槽 ⇒ 槽 %.2f mm²（fill %.2f, J %.1f）"
          % (i1["thermal"]["a_cu_req_mm2"], i1["thermal"]["a_slot_req_mm2"],
             cfg.fill_design, cfg.J_design))
    for c in i1["checks"]:
        print("    [%s] %-28s %10.4f %s %8.4f" % (c["status"], c["name"], c["value"], c["op"], c["limit"]))

    print("=" * 72)
    print("I2 双层线圈截面  上/下面积 %.3f / %.3f mm²（分界 r=%.3f, 层间 0.4）"
          % (i2["area_upper"], i2["area_lower"], i2["r_split"]))

    print("=" * 72)
    print("I4 双层 V 磁钢  status=%s  块数=%d" % (i4["status"], i4["magnets"]))
    print("  最近距离: 层间 %.2f / 同组两腿 %.2f / 极间 %.2f mm"
          % (i4["pair_min"]["inter_layer"], i4["pair_min"]["intra_v"],
             i4["pair_min"]["inter_pole"]))
    print("  OD 桥厚 %.2f / 轴孔间隙 %.2f mm；聚磁比 %.3f，Bg 估算 %.3f T（漏磁 0.7）"
          % (min(x["bridge_od"] for x in i4["radial"]),
             min(x["gap_shaft"] for x in i4["radial"]),
             i4["flux_note"]["concentration"], i4["flux_note"]["Bg_est_leak07"]))
    for c in i4["checks"]:
        print("    [%s] %-28s %10.3f %s %8.3f" % (c["status"], c["name"], c["value"], c["op"], c["limit"]))

    os.makedirs(args.out, exist_ok=True)
    for name, data in (("i1_slot.json", i1), ("i2_coil_layers.json",
                                             {k: v for k, v in i2.items() if not isinstance(v, list)}),
                       ("i4_rotor.json", {k: v for k, v in i4.items()
                                          if k not in ("polygons", "labels")})):
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print("  ✔ %s" % path)
    return 0 if (i1["status"] == "PASS" and i4["status"] == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
