#!/usr/bin/env python3
"""槽轮廓几何 —— 梨形槽 11 点参数化 + 圆弧采样（几何/线圈共用同一份顶点）。

为什么单独一个模块（M8，2026-11-14）
-------------------------------------
`main.py::_gen_geometry` 的梨形分支此前把**同一组尺寸写了两遍**：一遍写进
`CreatePolyline` 的字面量，一遍写进 `_slot_pts`（供线圈 0.88 内缩）。两处只要
有一处改动，线圈就会与槽壁错位 —— 那是 `StatorOuter and Coil_x intersect` 的
经典来源。更严重的是 `_slot_pts` 当时只有 11 个控制点、**没有圆弧采样**：
半圆底被两根弦代替，弦高 `Rs·(1−cos45°) = 1.39 mm`，线圈面积只剩 62.07 mm²
（比目标 72 少 13.8%），且下缘直接切进槽底圆弧。

本模块的做法
------------
1. `pear_key_points()` 给出表 2 的 11 个关键点（逆时针，mm，不含闭合重复点），
   几何字面量与 `_slot_pts` 都**只从它派生**，杜绝双写。
2. `pear_outline()` 把底部半圆按 `n_arc` 段离散（默认 16 段，弦高 0.036 mm），
   供线圈内缩使用 —— 线圈面积对弧段采样极其敏感，必须用密采样。
3. `slot_effective_area()` 区分「解析槽面积」与「从定子环上真正切掉的面积」：
   槽口从 `r_bore − 0.2` 起画，那 0.2 mm 落在内孔里、不在环带上，所以
   `GetFaceArea(StatorOuter)` 反算出来会小 0.16 mm²（12 槽共 1.92 mm²）。
   判据必须用解析值，反算值只用来交叉校验（见 `docs/PEAR_SLOT_SPEC.md` §4）。

坐标约定：x = 径向（mm，从轴心向外），y = 切向（mm）。
"""
from __future__ import annotations

import math

# 圆弧离散段数：半圆 180° 分 16 段，弦高 Rs·(1-cos(5.625°)) ≈ 0.023 mm，
# 面积亏损 0.6%（93.02 → 92.80），线圈仍在 72 ±5% 内。
ARC_SEGMENTS = 16

# 槽口压进内孔的重叠量（避免与内孔圆弧相切触发 Non-manifold vertices）
BORE_OVERLAP_MM = 0.2

# 线圈截面向槽形形心收缩的比例（G4 起沿用；面积比 = 0.88² = 0.7744）
COIL_SHRINK = 0.88


def pear_radii(cfg) -> dict[str, float]:
    """梨形槽五条径向基准线（mm）。`Hs2` 口径 = 内径 → 槽底**最底端**。"""
    r_bore = cfg.stator_id / 2.0
    rs = cfg.slot_Rs
    return {
        "r_bore": r_bore,
        "x0": r_bore - BORE_OVERLAP_MM,
        "x1": r_bore + cfg.slot_Hs0,
        "x2": r_bore + cfg.slot_Hs0 + cfg.slot_Hs1,
        "x3": r_bore + cfg.slot_Hs2 - rs,     # 槽底圆心
        "x4": r_bore + cfg.slot_Hs2,          # 槽底最底端
        "rs": rs,
    }


def pear_key_points(cfg) -> list:
    """表 2 的 11 个轮廓点（逆时针，mm，**不含**闭合重复点）。

    与 `docs/PEAR_SLOT_SPEC.md` §3 的表逐行对应：
    0 颈下缘 → 1 颈末 → 2 肩末 → 3 斜肩末 → 4 直身末（圆心高度）→ 5 槽底
    → 6..10 另一侧镜像。
    """
    r = pear_radii(cfg)
    b0, b1, b2 = cfg.slot_Bs0, cfg.slot_Bs1, cfg.slot_Bs2
    return [
        (r["x0"], -b0 / 2.0),      # 0 槽口起点（压进内孔 0.2 mm）
        (r["x1"], -b0 / 2.0),      # 1 颈末
        (r["x1"], -b1 / 2.0),      # 2 肩部台阶（切向展宽，径向不动）
        (r["x2"], -b2 / 2.0),      # 3 斜肩末 / 直身起点
        (r["x3"], -b2 / 2.0),      # 4 直身末 = 半圆起点（圆心高度）
        (r["x4"], 0.0),            # 5 半圆最底端
        (r["x3"], b2 / 2.0),       # 6 半圆终点
        (r["x2"], b2 / 2.0),       # 7
        (r["x1"], b1 / 2.0),       # 8
        (r["x1"], b0 / 2.0),       # 9
        (r["x0"], b0 / 2.0),       # 10 回到槽口
    ]


def pear_segments() -> list:
    """10 段（段类型, 起始索引, 点数）。底部半圆是 Arc，起点索引 4。

    12 个 PLPoint（11 关键点 + 闭合重复点）刚好被 10 段覆盖：
    0→1, 1→2, 2→3, 3→4, **Arc 4→5→6**, 6→7, 7→8, 8→9, 9→10, 10→11。
    """
    return [
        ("Line", 0, 2), ("Line", 1, 2), ("Line", 2, 2), ("Line", 3, 2),
        ("Arc", 4, 3),
        ("Line", 6, 2), ("Line", 7, 2), ("Line", 8, 2), ("Line", 9, 2),
        ("Line", 10, 2),
    ]


def arc_points(x3: float, rs: float, n: int = ARC_SEGMENTS) -> list:
    """底部半圆采样：θ ∈ [−90°, +90°]，含两端点，共 n+1 点。"""
    out = []
    for k in range(n + 1):
        a = math.radians(-90.0 + 180.0 * k / n)
        out.append((x3 + rs * math.cos(a), rs * math.sin(a)))
    return out


def pear_outline(cfg, n_arc: int = ARC_SEGMENTS) -> list:
    """线圈内缩用的密采样槽轮廓（mm）—— 半圆底 replaced by n_arc 段折线。"""
    r = pear_radii(cfg)
    b0, b1, b2 = cfg.slot_Bs0, cfg.slot_Bs1, cfg.slot_Bs2
    pts = [
        (r["x0"], -b0 / 2.0),
        (r["x1"], -b0 / 2.0),
        (r["x1"], -b1 / 2.0),
        (r["x2"], -b2 / 2.0),
    ]
    pts += arc_points(r["x3"], r["rs"], n_arc)
    pts += [
        (r["x2"], b2 / 2.0),
        (r["x1"], b1 / 2.0),
        (r["x1"], b0 / 2.0),
        (r["x0"], b0 / 2.0),
    ]
    return pts


def polygon_area(pts) -> float:
    """鞋带公式（mm²，取绝对值）。"""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def mean_centroid(pts) -> tuple:
    """顶点算术平均（不是面积形心）—— 与 G4 起沿用的内缩基准保持一致。"""
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


def shrink_toward_centroid(pts, s: float) -> list:
    """按比例 s 向（顶点平均）形心收缩。凸/星形多边形收缩后必内含原形。"""
    cx, cy = mean_centroid(pts)
    return [(cx + s * (x - cx), cy + s * (y - cy)) for (x, y) in pts]


def pear_area_analytic(cfg) -> float:
    """解析槽面积（mm²）—— 颈 + 斜肩梯形 + 直身 + 半圆底。"""
    r = pear_radii(cfg)
    b0, b1, b2 = float(cfg.slot_Bs0), float(cfg.slot_Bs1), float(cfg.slot_Bs2)
    neck = b0 * (r["x1"] - r["x0"])
    shoulder = (b1 + b2) / 2.0 * float(cfg.slot_Hs1)
    body = b2 * (r["x3"] - r["x2"])
    bottom = math.pi * r["rs"] ** 2 / 2.0
    return neck + shoulder + body + bottom


def slot_effective_area(cfg, area: float | None = None) -> float:
    """从定子环带上**真正**被切掉的面积：解析面积减掉内孔里的槽口重叠段。

    槽口跨 `r_bore−0.2 .. r_bore`，宽 `Bs0`，这一段在环带之外，
    所以 `StatorOuter` 的面只少了 `area − 0.2·Bs0`。
    """
    if area is None:
        area = pear_area_analytic(cfg)
    return area - BORE_OVERLAP_MM * float(cfg.slot_Bs0)


def stator_ring_area(cfg) -> float:
    """整圈定子环（无槽）面积，mm²；用于从 GetFaceArea 反算槽面积。"""
    r_out = float(cfg.stator_od) / 2.0
    r_in = float(cfg.stator_id) / 2.0
    return math.pi * (r_out ** 2 - r_in ** 2)


def slot_area_from_stator_face(cfg, face_area: float) -> float:
    """由 `GetFaceArea(StatorOuter)` 反算单槽面积（含内孔重叠段，可比解析值）。"""
    return (stator_ring_area(cfg) - face_area) / float(cfg.slots) + BORE_OVERLAP_MM * float(cfg.slot_Bs0)
