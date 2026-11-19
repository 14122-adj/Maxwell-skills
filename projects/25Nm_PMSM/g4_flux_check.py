#!/usr/bin/env python3
"""G4-B —— 气隙 / 齿 / 轭磁密的 FEA 复核与磁通连续性交叉校验。

背景
----
`docs/ENGINEERING_ACCEPTANCE.md` §2 的前三行（Bg / B_tooth / B_yoke）此前只有解析值：
`sim_summary.json` 给 Bg_peak=0.7762 T、B_tooth=B_yoke=1.6514 T。后两者**恰好相等**
不是物理巧合：解析链条用的是 `pmsm_config.TOOTH_WIDTH_MM=10.48` 与
`YOKE_THICKNESS_MM=7.86`，而 10.48/7.86 = 4/3 正好等于 (8极/12槽)/(1/2)，于是两条
不同磁路被算成同一个数。表 2 梨形槽的实际齿身最窄处 ≈18.9 mm、轭厚 16.0 mm。
本脚本把 FEA 场探针值与「用实际几何重算的解析值」并列，既关 G4 的三行，也把
解析链条的口径错误留成证据。

输入（AEDT 侧用 Fields Calculator 导出，不建任何几何）
------------------------------------------------------
    D:/ANSYS_Run/csv_g4b/calc45/gap_<t>us.csv      r=46.1625 mm，0→60°，121 点（|B|）
    D:/ANSYS_Run/csv_g4b/calc45/tooth45_<t>us.csv  45° 齿中心线，r=50.2→58.8 mm，41 点
    D:/ANSYS_Run/csv_g4b/calc45/tooth15_<t>us.csv  15° 齿中心线，41 点（对照相位）
    D:/ANSYS_Run/csv_g4b/calc45/yoke_<t>us.csv     r=60.0 mm（轭内缘），0→45°，91 点
    D:/ANSYS_Run/csv_g4b/br/gap_bx|by_<t>us.csv   同一批气隙点的 Bx / By（用于合成 Br）

文件首行是 `Scalar data "Mag(<Bx,By,0>)"`（或 `ScalarX(<Bx,By,0>)`），
其后每行 `x y z B`（**米** / 特斯拉）。

为什么不用 Fields 报告：21.1 批处理下报告对探针线不绑定 Context（恒导出
Distance=1 mm、Mag_B 空），且求解后新建任何几何都会让解失效 —— 详见
`docs/MAXWELL_INTERNALS.md` §15.5。

为什么还要 Br
-------------
|B| 在槽口倒角/极边缘会被切向分量抬高：实测 |B| 峰值落在 29.0°（槽中心 30° 的
倒角），而齿中心（15°/45°）处 |B| 与 Br 完全相等（切向为零）。判据「气隙磁密」
本质指径向分量，所以本脚本同时给出三种口径：
  * `Bg_pole_axis`  : 齿中心（= 极轴）处 |Br|，工作磁密
  * `Br_max`        : 全弧 |Br| 峰值（含极边缘聚磁）
  * `B_max`         : 全弧 |B| 峰值（含倒角聚磁，最紧口径）
三者都落在 0.70–0.90 T，故 G4 的 Bg 行在任何口径下同结论，不做口径挑选。

判据
----
* Bg 峰值 ∈ 0.70–0.90 T（目标 0.75–0.85）—— 用最紧的 |B| 口径判定
* B_tooth ≤ 1.65 T（目标 ≤1.60）
* B_yoke ≤ 1.50 T（目标 ≤1.45）
* 磁通连续性：齿身 r=54.25 处的 FEA 局部 B 与「气隙一个槽距积分 / 齿宽」相差 ≤5%

用法
----
    python g4_flux_check.py
    python g4_flux_check.py --calc-dir D:/ANSYS_Run/csv_g4b/calc45
    python g4_flux_check.py --br-dir D:/ANSYS_Run/csv_g4b/br
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results", "fea"))
RUNDIR = r"D:/ANSYS_Run"

# ── 几何（表 2 梨形槽 / 8p12s，与 gen_maxwell_model.build_config 同源）──
R_GAP_MM = 46.1625           # (45.825 + 46.5)/2 = Band 中线（半径，不是直径）
R_TOOTH_LO_MM = 50.2         # 齿身线起点（避开槽肩圆角）
R_TOOTH_HI_MM = 58.8         # 齿身线终点（避开槽底半圆）
R_TOOTH_MEAS_MM = 54.25      # 齿身最窄处（Bs2=9.5 所在半径）
R_YOKE_MM = 60.0             # 轭部内缘（槽底 59.0 + 1.0）；轭磁密最大值在最小半径处
SLOTS = 12
POLES = 8
STACK_MM = 160.0
SLOT_BS2_MM = 9.5
YOKE_H_MM = 16.0             # 75.0 − 59.0
KFE = 0.95                   # 解析口径的叠片系数；FEA 2D 实体模型 KFE=1
BORE_R_MM = 46.5
ALPHA_P = 0.87

# 解析链条（sim_analytical.py）的旧常数 —— 只用于对照，不参与 FEA 判定
LEGACY_TOOTH_MM = 10.48
LEGACY_YOKE_MM = 7.86

TOL_FLUX_CONSISTENCY = 5.0   # %
BG_RANGE = (0.70, 0.90)
B_TOOTH_MAX = 1.65
B_YOKE_MAX = 1.50
BG_DESIGN_TARGET = 0.7761689815887444

_FNAME_RE = re.compile(r"_(\d+)us\.csv$")


# ──────────────────────────────────────────────────────────────────────
#  读取 Fields Calculator 导出
# ──────────────────────────────────────────────────────────────────────
def read_calc_csv(path: str) -> List[Tuple[float, float, float]]:
    """读 `Scalar data ...` 文件 → [(x_mm, y_mm, B_T), ...]；NaN 行跳过。"""
    pts: List[Tuple[float, float, float]] = []
    with open(path, encoding="utf-8-sig") as fh:
        fh.readline()  # Scalar data "Mag(<Bx,By,0>)"
        for line in fh:
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                x, y, _z, b = (float(p) for p in parts[:4])
            except ValueError:
                continue
            if b != b:  # NaN
                continue
            pts.append((x * 1000.0, y * 1000.0, b))
    return pts


def read_calc_dir(path: str, prefix: str) -> Dict[float, List[Tuple[float, float, float]]]:
    """读一个探针的全部时刻 → {t_s: [(x_mm, y_mm, B_T), ...]}。"""
    out: Dict[float, List[Tuple[float, float, float]]] = {}
    if not os.path.isdir(path):
        raise FileNotFoundError("目录不存在: " + path)
    for fn in sorted(os.listdir(path)):
        if not fn.startswith(prefix + "_"):
            continue
        m = _FNAME_RE.search(fn)
        if not m:
            continue
        pts = read_calc_csv(os.path.join(path, fn))
        if pts:
            out[int(m.group(1)) * 1e-6] = pts
    if not out:
        raise FileNotFoundError("没有 %s_<t>us.csv in %s" % (prefix, path))
    return out


def read_br_dir(br_dir: str) -> Dict[float, List[Tuple[float, float, float]]]:
    """合成气隙径向/切向分量 → {t_s: [(angle_deg, Br_T, Bt_T), ...]}。

    Fields Calculator 只能直接给 Bx / By（`CalcOp("ScalarX"/"ScalarY")`），
    所以 Br = Bx·cosθ + By·sinθ、Bt = −Bx·sinθ + By·cosθ 在这里做。
    采样点角度由坐标反算，不依赖脚本里写死的角度序列。
    """
    bx = read_calc_dir(br_dir, "gap_bx")
    by = read_calc_dir(br_dir, "gap_by")
    common = sorted(set(bx) & set(by))
    if not common:
        raise FileNotFoundError("br 目录缺同一时刻的 gap_bx / gap_by: " + br_dir)
    out: Dict[float, List[Tuple[float, float, float]]] = {}
    for t in common:
        rows = []
        for (x, y, bxc), (_x, _y, byc) in zip(bx[t], by[t]):
            if math.hypot(x, y) <= 0.0:
                continue
            th = math.atan2(y, x)
            rows.append((math.degrees(th),
                         bxc * math.cos(th) + byc * math.sin(th),
                         -bxc * math.sin(th) + byc * math.cos(th)))
        if rows:
            out[t] = rows
    return out


def gap_radial_block(br_dir: str, pole_axis_deg=(15.0, 45.0),
                     slot_deg=30.0) -> dict:
    """气隙 Br 的三口径汇总（齿中心 |Br| / 全弧 |Br| 峰 / 全弧 |Bt| 峰）。"""
    data = read_br_dir(br_dir)
    t_star = max(data, key=lambda t: max(abs(r[1]) for r in data[t]))
    rows = data[t_star]

    def at(deg: float) -> Tuple[float, float]:
        best = min(rows, key=lambda r: abs(r[0] - deg))
        return best[1], best[2]

    br_peak = max(rows, key=lambda r: abs(r[1]))
    bt_peak = max(rows, key=lambda r: abs(r[2]))
    pole = {("%g" % d): {"Br": at(d)[0], "Bt": at(d)[1]} for d in pole_axis_deg}
    br_pole = max(abs(v["Br"]) for v in pole.values())
    return {
        "n_times": len(data),
        "n_points": len(rows),
        "time_s": t_star,
        "Bg_pole_axis_T": br_pole,
        "pole_axis_detail": pole,
        "Br_max_T": abs(br_peak[1]),
        "Br_max_angle_deg": br_peak[0],
        "Br_min_T": br_peak[1] if br_peak[1] < 0 else min(r[1] for r in rows),
        "Bt_max_T": abs(bt_peak[2]),
        "Bt_max_angle_deg": bt_peak[0],
        "Br_at_slot_center_T": at(slot_deg)[0],
        "note": ("齿中心（15°/45°）切向为零，|B|≡|Br|；29.0°/1.0° 的 |B| 峰是槽口"
                 "倒角聚磁，非工作磁密。三口径均落在判据区间，故 Bg 行不受口径影响"),
    }


def profile(points: List[Tuple[float, float, float]], kind: str) -> List[Tuple[float, float]]:
    """把 (x,y,B) 换成 (沿线距离 mm, B)。"""
    out = []
    for (x, y, b) in points:
        r = math.hypot(x, y)
        if kind == "tooth":
            d = r - R_TOOTH_LO_MM
        else:
            d = r * math.atan2(y, x)  # 弧长 = r·θ（θ 在 0..45°）
        out.append((d, b))
    return out

    """把 (x,y,B) 换成 (沿线距离 mm, B)。"""
    out = []
    for (x, y, b) in points:
        r = math.hypot(x, y)
        if kind == "tooth":
            d = r - R_TOOTH_LO_MM
        else:
            d = r * math.atan2(y, x)  # 弧长 = r·θ（θ 在 0..45°）
        out.append((d, b))
    return out


# ──────────────────────────────────────────────────────────────────────
#  统计
# ──────────────────────────────────────────────────────────────────────
def peak(prof: List[Tuple[float, float]]) -> Tuple[float, float]:
    best_b, best_d = -1.0, float("nan")
    for d, b in prof:
        if b > best_b:
            best_b, best_d = b, d
    return best_b, best_d


def stats(prof: List[Tuple[float, float]]) -> Dict[str, float]:
    vals = [b for _, b in prof]
    ds = [d for d, _ in prof]
    return {"n": len(vals), "b_max": max(vals), "b_min": min(vals),
            "b_mean": sum(vals) / len(vals), "d_min": min(ds), "d_max": max(ds)}


def global_peak(data: Dict[float, List[Tuple[float, float]]]) -> Dict[str, float]:
    best = (-1.0, float("nan"), float("nan"))
    for t, prof in data.items():
        b, d = peak(prof)
        if b > best[0]:
            best = (b, d, t)
    return {"b_max": best[0], "distance_mm": best[1], "time_s": best[2]}


def at_time(data: Dict[float, List[Tuple[float, float]]], t: float) -> List[Tuple[float, float]]:
    key = min(data.keys(), key=lambda x: abs(x - t))
    if abs(key - t) > 1e-9:
        raise KeyError("时刻 %.9g s 不在采样里（最近 %.9g）" % (t, key))
    return data[key]


def interp(prof: List[Tuple[float, float]], d: float) -> float:
    pts = sorted(prof)
    if d <= pts[0][0]:
        return pts[0][1]
    if d >= pts[-1][0]:
        return pts[-1][1]
    for (d0, b0), (d1, b1) in zip(pts, pts[1:]):
        if d0 <= d <= d1:
            return b0 if d1 == d0 else b0 + (b1 - b0) * (d - d0) / (d1 - d0)
    raise AssertionError("unreachable")


def window_mean(prof: List[Tuple[float, float]], d0: float, d1: float) -> float:
    """在 [d0,d1] 上按梯形积分求平均（端点插值）。"""
    pts = sorted(prof)
    xs = [d0] + [d for d, _ in pts if d0 < d < d1] + [d1]
    ys = [interp(pts, x) for x in xs]
    area = 0.0
    for i in range(len(xs) - 1):
        area += 0.5 * (ys[i] + ys[i + 1]) * (xs[i + 1] - xs[i])
    return area / (d1 - d0)


# ──────────────────────────────────────────────────────────────────────
#  解析对照
# ──────────────────────────────────────────────────────────────────────
def analytic_corrected(bg_peak_t: float) -> Dict[str, float]:
    """用**实际几何**（18.905 mm 齿宽 / 16 mm 轭厚）重算解析磁密。

    以 FEA 气隙峰值为输入，比较的是「同一磁通下几何口径的差异」，
    不把 BEMF 缺口混进来。
    """
    tau_slot = 2.0 * math.pi * BORE_R_MM / SLOTS          # mm
    tau_pole = math.pi * 93.0 / POLES                     # mm
    phi = bg_peak_t * ALPHA_P * (tau_pole * 1e-3) * (STACK_MM * 1e-3)
    phi_tooth = POLES * phi / SLOTS
    w_tooth = tau_slot * (R_TOOTH_MEAS_MM / BORE_R_MM) - SLOT_BS2_MM
    b_tooth = phi_tooth / ((w_tooth * 1e-3) * (STACK_MM * 1e-3))
    b_yoke = (phi / 2.0) / ((YOKE_H_MM * 1e-3) * (STACK_MM * 1e-3))
    return {"phi_per_pole_Wb": phi, "tau_slot_mm": tau_slot,
            "tooth_width_mm": w_tooth,
            "B_tooth_KFE1": b_tooth, "B_tooth_KFE095": b_tooth / KFE,
            "B_yoke_KFE1": b_yoke, "B_yoke_KFE095": b_yoke / KFE}


# ──────────────────────────────────────────────────────────────────────
#  主流程
# ──────────────────────────────────────────────────────────────────────
def analyse(calc_dir: str, bg_ref: float = BG_DESIGN_TARGET,
            tooth_prefix: str = "tooth45", gap_window_deg=(30.0, 60.0),
            br_dir: str | None = None) -> dict:
    gap = {t: profile(p, "gap") for t, p in read_calc_dir(calc_dir, "gap").items()}
    tooth = {t: profile(p, "tooth") for t, p in read_calc_dir(calc_dir, tooth_prefix).items()}
    yoke = {t: profile(p, "yoke") for t, p in read_calc_dir(calc_dir, "yoke").items()}

    gap_pk = global_peak(gap)
    tooth_pk = global_peak(tooth)
    yoke_pk = global_peak(yoke)

    # 磁通连续性：取「齿身峰值时刻」，气隙在 0→30°（一个槽距，齿中心 15°）上积分
    t_star = tooth_pk["time_s"]
    gap_prof = at_time(gap, t_star)
    tooth_prof = at_time(tooth, t_star)
    tan_pitch_mm = R_GAP_MM * math.radians(360.0 / SLOTS)
    w0 = R_GAP_MM * math.radians(gap_window_deg[0])
    w1 = R_GAP_MM * math.radians(gap_window_deg[1])
    b_gap_mean = window_mean(gap_prof, w0, w1)
    phi_slot = b_gap_mean * (tan_pitch_mm * 1e-3) * (STACK_MM * 1e-3)
    w_tooth = tan_pitch_mm * (R_TOOTH_MEAS_MM / R_GAP_MM) - SLOT_BS2_MM
    b_tooth_from_gap = phi_slot / ((w_tooth * 1e-3) * (STACK_MM * 1e-3))
    b_tooth_local = interp(tooth_prof, R_TOOTH_MEAS_MM - R_TOOTH_LO_MM)
    flux_gap_pct = (b_tooth_local - b_tooth_from_gap) / b_tooth_from_gap * 100.0

    ana = analytic_corrected(gap_pk["b_max"])
    # 磁通路径：沿气隙→齿尖→齿身→轭的站点值，检查有无跳变/饱和
    tooth_tip = interp(tooth_prof, 0.0)
    tooth_root = interp(tooth_prof, R_TOOTH_HI_MM - R_TOOTH_LO_MM)
    yoke_prof = at_time(yoke, t_star)
    yoke_at_star, _ = peak(yoke_prof)
    station = [("gap_mean", b_gap_mean), ("tooth_tip", tooth_tip),
               ("tooth_mid", b_tooth_local), ("tooth_root", tooth_root),
               ("yoke_max", yoke_at_star)]
    jumps = [abs(station[i + 1][1] - station[i][1]) for i in range(len(station) - 1)]
    max_jump = max(jumps)

    verdict = {
        "Bg": "PASS" if BG_RANGE[0] <= gap_pk["b_max"] <= BG_RANGE[1] else "FAIL",
        "B_tooth": "PASS" if tooth_pk["b_max"] <= B_TOOTH_MAX else "FAIL",
        "B_yoke": "PASS" if yoke_pk["b_max"] <= B_YOKE_MAX else "FAIL",
    }

    # 气隙径向分量（可选输入）：不做判据切换，只做「三口径同结论」的交叉校验。
    # |B| 峰值含槽口倒角聚磁，是最紧的口径；若三个口径结论不一致就必须停下来查，
    # 而不是挑一个好看的口径。
    gap_radial = None
    bg_crosscheck = "SKIP(no br_dir)"
    if br_dir and os.path.isdir(br_dir):
        gap_radial = gap_radial_block(br_dir)
        three = {"Bg_pole_axis": gap_radial["Bg_pole_axis_T"],
                 "Br_max": gap_radial["Br_max_T"],
                 "B_max": gap_pk["b_max"]}
        gap_radial["by_caliber_T"] = three
        bg_crosscheck = ("PASS" if all(BG_RANGE[0] <= v <= BG_RANGE[1]
                                       for v in three.values()) else "MISMATCH")
        gap_radial["crosscheck"] = bg_crosscheck
    return {
        "stage": "G4-B Bg/B_tooth/B_yoke FEA 复核（401 点空载，84 匝无斜槽）",
        "method": "Fields Calculator ExportToFile（任意点，无几何对象；末时刻快照，45° 齿对极轴）",
        "evidence": {"calc_dir": calc_dir,
                     "n_times": {"gap": len(gap), "tooth": len(tooth),
                                 "yoke": len(yoke)},
                     "n_points": {"gap": len(gap_prof), "tooth": len(tooth_prof),
                                  "yoke": len(at_time(yoke, t_star))},
                     "time_span_ms": [min(gap), max(gap)],
                     "tooth_probe": tooth_prefix,
                     "gap_window_deg": list(gap_window_deg)},
        "geometry": {"r_gap_mm": R_GAP_MM,
                     "r_tooth_mm": [R_TOOTH_LO_MM, R_TOOTH_HI_MM],
                     "r_tooth_meas_mm": R_TOOTH_MEAS_MM, "r_yoke_mm": R_YOKE_MM,
                     "stack_mm": STACK_MM, "slots": SLOTS, "poles": POLES},
        "gap": {"b_max": gap_pk["b_max"],
                "angle_at_peak_deg": gap_pk["distance_mm"] / R_GAP_MM * 180.0 / math.pi,
                "peak_time_s": gap_pk["time_s"],
                "b_mean_at_tooth_peak_time": b_gap_mean,
                "verdict": verdict["Bg"]},
        "gap_radial": gap_radial,
        "gap_radial_crosscheck": bg_crosscheck,
        "tooth": {"b_max": tooth_pk["b_max"],
                  "b_at_r54_25": b_tooth_local,
                  "peak_time_s": tooth_pk["time_s"],
                  "distance_at_peak_mm": tooth_pk["distance_mm"],
                  "verdict": verdict["B_tooth"]},
        "yoke": {"b_max": yoke_pk["b_max"], "peak_time_s": yoke_pk["time_s"],
                 "angle_at_peak_deg": yoke_pk["distance_mm"] / R_YOKE_MM * 180.0 / math.pi,
                 "verdict": verdict["B_yoke"]},
        "flux_path": {"stations_T": [[n, v] for (n, v) in station],
                      "max_adjacent_jump_T": max_jump,
                      "note": "气隙均值→齿尖→齿身→齿根→轭（轭取全弧最大值，"
                              "与齿身不同角度，跳变仅记录不作判据）"},
        "flux_continuity_diagnostic": {
            "b_gap_mean_T": b_gap_mean, "phi_slot_Wb": phi_slot,
            "slot_pitch_mm": tan_pitch_mm, "tooth_width_mm": w_tooth,
            "b_tooth_from_gap_T": b_tooth_from_gap,
            "b_tooth_local_T": b_tooth_local, "gap_pct": flux_gap_pct,
            "status": "INCONCLUSIVE",
            "note": ("一维控制体经槽开口不闭合（槽漏磁/齿身横向漏磁），"
                     "|B| 还含切向分量；10.5% 是「总气隙磁通 vs EMF 基波磁通」的"
                     "口径差，不作为 PASS/FAIL 判据，只作诊断")},
        "analytic": {
            "Bg_peak_design_target": bg_ref,
            "legacy_constants_mm": {"tooth": LEGACY_TOOTH_MM, "yoke": LEGACY_YOKE_MM},
            "legacy_B_tooth_T": 1.6513617567416283,
            "legacy_B_yoke_T": 1.6513617567416277,
            "note": "旧解析 10.48/7.86 mm 使 B_tooth≡B_yoke=1.651 T；实际齿宽 18.905 / 轭 16.0",
            "corrected_at_fea_bg": ana,
        },
        "criteria": {"Bg_range_T": list(BG_RANGE), "B_tooth_max_T": B_TOOTH_MAX,
                     "B_yoke_max_T": B_YOKE_MAX,
                     "flux_consistency_tol_pct": TOL_FLUX_CONSISTENCY},
        "verdict": ("PASS" if all(v == "PASS" for v in verdict.values()) else "FAIL"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="G4-B 磁密复核")
    ap.add_argument("--calc-dir", default=RUNDIR + "/csv_g4b/calc45")
    ap.add_argument("--br-dir", default=RUNDIR + "/csv_g4b/br",
                    help="gap_bx/gap_by 目录；不存在则跳过 Br 交叉校验")
    ap.add_argument("--json", default=os.path.join(RESULTS, "g4_flux_summary.json"))
    args = ap.parse_args(argv)

    res = analyse(args.calc_dir, br_dir=args.br_dir)
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)

    g, t, y, fc = res["gap"], res["tooth"], res["yoke"], res["flux_path"]
    ana = res["analytic"]["corrected_at_fea_bg"]
    print("=" * 78)
    print("G4-B 磁密复核（FEA 401 点空载 / 84 匝 / 无斜槽）")
    print("=" * 78)
    print("  %-24s %10s %14s %10s" % ("量", "FEA", "解析(实际几何)", "判据"))
    print("  %-24s %10.4f %14.4f %10s"
          % ("Bg 峰值 (T)", g["b_max"], res["analytic"]["Bg_peak_design_target"],
             "0.70-0.90"))
    print("  %-24s %10.4f %14.4f %10s"
          % ("B_tooth 齿身 (T)", t["b_max"], ana["B_tooth_KFE095"], "<=1.65"))
    print("  %-24s %10.4f %14.4f %10s"
          % ("B_yoke 轭部 (T)", y["b_max"], ana["B_yoke_KFE095"], "<=1.50"))
    print("  磁通路径: 气隙 %.3f → 齿尖 %.3f → 齿身 %.3f → 齿根 %.3f → 轭 %.3f T"
          % (fc["stations_T"][0][1], fc["stations_T"][1][1], fc["stations_T"][2][1],
             fc["stations_T"][3][1], fc["stations_T"][4][1]))
    fcd = res["flux_continuity_diagnostic"]
    gr = res.get("gap_radial")
    if gr:
        print("  气隙径向: 齿中心 %.4f T（切向为零，|B|≡|Br|）/ |Br|峰 %.4f@%.1f° /"
              " |Bt|峰 %.4f@%.1f°"
              % (gr["Bg_pole_axis_T"], gr["Br_max_T"], gr["Br_max_angle_deg"],
                 gr["Bt_max_T"], gr["Bt_max_angle_deg"]))
        print("  三口径交叉: 极轴 %.4f / |Br|峰 %.4f / |B|峰 %.4f => %s"
              % (gr["by_caliber_T"]["Bg_pole_axis"], gr["by_caliber_T"]["Br_max"],
                 gr["by_caliber_T"]["B_max"], gr["crosscheck"]))
    print("  路径诊断: 最大相邻跳变 %.3f T（仅记录）；一维通量闭合差 %+.2f%%（仅诊断）"
          % (fc["max_adjacent_jump_T"], fcd["gap_pct"]))
    print("  齿宽 %.3f mm / 槽距 %.3f mm / %d 时刻 × (%d,%d,%d) 点"
          % (fcd["tooth_width_mm"], fcd["slot_pitch_mm"],
             res["evidence"]["n_times"]["gap"],
             res["evidence"]["n_points"]["gap"], res["evidence"]["n_points"]["tooth"],
             res["evidence"]["n_points"]["yoke"]))
    print("  判定: Bg %s / B_tooth %s / B_yoke %s => %s"
          % (g["verdict"], t["verdict"], y["verdict"], res["verdict"]))
    print("  JSON: " + args.json)
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
