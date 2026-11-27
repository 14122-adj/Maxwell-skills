#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 贴片电机 —— 厚度-电流 定源计算（KEEP，2026-11-27）

用途
----
解除 Imax=13.856 A 冻结后，为「加厚磁钢 + 重算电流」提供**解析起点**。
任务书反自演条款：本脚本所有输出标 `assumption=待验证`，
必须 401 点 FEA（空载 + 负载）验证后才能当性能结论。

拟合输入（全部 FEA 实测，Imax=13.856 A）
----------------------------------------
| t_pm (mm) | 极弧 | T_avg (N·m) | 证据 |
|---:|---:|---:|---|
| 0.45 | 0.90 | 24.9991 | spm_m3_t045a90_check.json |
| 0.50 | 0.90 | 26.6968 | spm_m3_t050a90_check.json |
| 0.65 | 0.85 | 30.6432 | spm_m3_t065r_check.json |
| 1.30 | 0.85 | 42.0246 | spm_m3_t130_check.json |
| 2.38 | 0.85 | 50.2821 | spm_m3_t238_check.json |

极弧 0.85→0.90 的转矩比取 t=0.50 两点实测：26.6968/26.3363 = 1.013692，
用于把 0.85 数据归一化到 0.90（单变量口径一致）。

Bg / BEMF 推算
--------------
* 解析 Bg(t) = Br·t/(t + μr·g)，Br=1.23 T、μr=1.05、g=0.675 mm；
* 用 t=2.38 实测 Bg=1.0114 T（m2_noload_spm_g03.json）校准解析系数；
* BEMF(t) = 273.4005 V × Bg_cal(t)/1.0114（空载实测外推，非 FEA 结论）。

用法
----
    python spm_sizing_calc.py
    python spm_sizing_calc.py --thickness 0.90     # 单点电流/BEMF 推算
"""
from __future__ import annotations

import argparse
import math

BR = 1.23
MU_R = 1.05
AIRGAP = 0.675
ROTOR_OD = 91.65
GLUE_GAP = 0.02
I_BASE = 13.856
T_TARGET = 25.0
POLE_ARC_RATIO = 26.6968 / 26.3363   # 极弧 0.90/0.85 实测转矩比
BG_MEAS_AT_T238 = 1.0114
BEMF_MEAS_AT_T238 = 273.4005
BEMF_WINDOW = (118.0, 145.0)
SVPWM_380_PHASE_PEAK = 380.0 * math.sqrt(2.0 / 3.0)   # 310.27 V
SVPWM_380_RMS = SVPWM_380_PHASE_PEAK / math.sqrt(2.0)  # 219.39 V

# (t_pm, T_avg, pole_arc) —— 全部 FEA 实测
FE_POINTS = [
    (0.45, 24.9991, 0.90),
    (0.50, 26.6968, 0.90),
    (0.65, 30.6432, 0.85),
    (1.30, 42.0246, 0.85),
    (2.38, 50.2821, 0.85),
]


def normalized_points() -> list[tuple[float, float]]:
    """把全部点归一化到极弧 0.90，返回 [(t, T), ...]。"""
    out = []
    for t, tq, arc in FE_POINTS:
        factor = POLE_ARC_RATIO if abs(arc - 0.85) < 1e-9 else 1.0
        out.append((t, tq * factor))
    return out


def fit_log_model() -> tuple[float, float]:
    """最小二乘拟合 T(t) = a + b·ln(t)，返回 (a, b)。"""
    pts = normalized_points()
    xs = [math.log(t) for t, _ in pts]
    ys = [v for _, v in pts]
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    b = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    a = (sy - b * sx) / n
    return a, b


def bg_analytic(t: float) -> float:
    return BR * t / (t + MU_R * AIRGAP)


def bg_calibration() -> float:
    return BG_MEAS_AT_T238 / bg_analytic(2.38)


def bg_cal(t: float) -> float:
    return bg_analytic(t) * bg_calibration()


def bemf_est(t: float) -> float:
    return BEMF_MEAS_AT_T238 * bg_cal(t) / BG_MEAS_AT_T238


def core_od_for(t: float) -> float:
    """磁钢外表面固定在 rotor_od/2=45.825，加厚往内吃铁芯。"""
    return ROTOR_OD - 2.0 * t


def current_for_target(t: float, a: float, b: float) -> float:
    """线性电流缩放（T ∝ Bg×I，磁路未饱和近似）：I = I_base × 25 / T(t,I_base)。"""
    t_at_base = a + b * math.log(t)
    return I_BASE * T_TARGET / t_at_base


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--thickness", type=float, default=None, help="只算单点")
    args = ap.parse_args(argv)

    a, b = fit_log_model()
    pts = normalized_points()
    print("极弧 0.85→0.90 实测比 = %.6f" % POLE_ARC_RATIO)
    print("拟合 T(t,I=13.856) = %.4f + %.4f·ln(t)，极弧 0.90" % (a, b))
    print("拟合残差（归一化实测 vs 拟合）:")
    for t, tq in pts:
        fit = a + b * math.log(t)
        print("  t=%.2f  实测=%7.4f  拟合=%7.4f  差=%+6.3f%%" %
              (t, tq, fit, (fit - tq) / tq * 100.0))
    print("Bg 校准系数 = %.4f（t=2.38 实测 %.4f / 解析 %.4f）" %
          (bg_calibration(), BG_MEAS_AT_T238, bg_analytic(2.38)))
    print()

    candidates = [0.45, 0.65, 0.90, 1.20] if args.thickness is None else [args.thickness]
    print("%-8s %-11s %-11s %-11s %-10s %-10s" %
          ("t_pm", "core_OD", "I@25Nm", "BEMF_est", "118-145V", "380V余量"))
    for t in candidates:
        i_new = current_for_target(t, a, b)
        emf = bemf_est(t)
        verdict = "PASS" if BEMF_WINDOW[0] <= emf <= BEMF_WINDOW[1] else "FAIL"
        margin = SVPWM_380_RMS / emf
        print("%-8.2f %-11.2f %-11.3f %-11.2f %-10s %-10.3f" %
              (t, core_od_for(t), i_new, emf, verdict, margin))
    print()
    print("assumption=待验证：T(t) 对数拟合、Bg 解析+单点校准、BEMF 线性外推均非 FEA 结论；")
    print("380V 余量 = SVPWM 相 RMS 上限 %.2f V / BEMF_est。" % SVPWM_380_RMS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
