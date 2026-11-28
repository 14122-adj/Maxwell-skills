#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KEEP (2026-11-28): 齿槽转矩 1.1764(t=2.38/ap0.85) vs 1.6254(t=0.65/ap0.90)
空间 Br 谐波诊断（只读两工况 gap_bx/gap_by CSV，同口径 0→22.5° 半极距）。
用法：python projects/IPM_8p48s/spm_cogging_diag.py
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
for p in (PROJ, os.path.join(os.path.dirname(os.path.dirname(PROJ)), "projects", "25Nm_PMSM")):
    if p not in sys.path:
        sys.path.insert(0, p)
import ipm_m2_check as chk  # noqa: E402


def dft_mag(y):
    """单周期 DFT 幅值谱（去端点），返回 [(h, amp)]，h=0..N//2。"""
    n = len(y)
    y0 = [v - sum(y) / n for v in y]
    out = []
    for h in range(0, n // 2 + 1):
        re = sum(y0[i] * math.cos(2 * math.pi * h * i / n) for i in range(n)) * 2 / n
        im = -sum(y0[i] * math.sin(2 * math.pi * h * i / n) for i in range(n)) * 2 / n
        out.append((h, math.hypot(re, im)))
    return out


for tag, csvdir in (("t=2.38 (ap0.85/cps10)", "D:/ANSYS_Run/csv_spm_m2_g03"),
                    ("t=0.65 (ap0.90/cps8)", "D:/ANSYS_Run/csv_spm_m2_t065c8")):
    tq = os.path.join(csvdir, "tq_noload.csv" if "g03" in csvdir else "tq_load.csv")
    import ingest_fea as ing
    t, cols = ing.load_maxwell_csv(tq)
    key = [k for k in cols if "torque" in k.lower()][0]
    unit = ing._units_by_column(tq).get(key, "")
    scale = chk.torque_scale(unit)
    y = [v * scale for v in cols[key]]
    st = chk.pp_ct(t, y)
    print("\n=== %s ===" % tag)
    print("齿槽 pp=%.4f N·m  max=%.4f min=%.4f  n=%d" % (st["pp"], st["max"], st["min"], st["n"]))
    gap = chk.gap_block(csvdir, None)
    print("Bg(|B|峰)=%.4f  Br_max=%.4f  Br_at_axis=%.4f  Br_mean_slot=%.4f" %
          (gap["b_max"], gap["Br_max"], gap["Br_at_pole_axis"], gap["Br_mean_one_slot_pitch"]))
    rows = chk.read_calc_pair(csvdir, "gap_bx", "gap_by")
    ang = [r[0] for r in rows]
    br = [r[1] for r in rows]
    print("气隙弧角度 %.2f..%.2f  n=%d  Δ=%.4f°" % (ang[0], ang[-1], len(ang), ang[1] - ang[0]))
    spec = dft_mag(br)
    fund = spec[1][1] if len(spec) > 1 else 1.0
    top = sorted(spec[1:], key=lambda x: -x[1])[:8]
    for h, a in top:
        print("  Br 谐波 h=%2d  amp=%.5f T  (%.2f%% of h1)" % (h, a, 100 * a / fund))
