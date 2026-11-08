# -*- coding: utf-8 -*-
"""m5_post.py — 由磁链 CSV 计算空载 BEMF（E = -dλ/dt）与齿槽转矩指标。"""
import os
import csv
import json
import math

import numpy as np

CSVDIR = r"D:\ANSYS_Run\csv"
OUT = os.path.join(CSVDIR, "fea_results.json")


def load_series(path):
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        rows = [r for r in csv.reader(f) if r]
    # 表头行 + 数据；首列 time [ms]
    t = np.array([float(r[0]) for r in rows[1:] if r and r[0].strip()])
    y = np.array([float(r[1]) for r in rows[1:] if r and len(r) > 1])
    return t * 1e-6, y  # Time [us] -> s


def thd(x, fs):
    n = len(x)
    if n < 16:
        return 0.0
    w = np.hanning(n)
    X = np.fft.rfft((x - np.mean(x)) * w)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    # 基波 100 Hz
    k1 = int(np.argmin(np.abs(f - 100.0)))
    a1 = abs(X[k1])
    if a1 == 0:
        return 0.0
    s = 0.0
    for h in range(2, 20):
        kh = int(np.argmin(np.abs(f - 100.0 * h)))
        s += abs(X[kh]) ** 2
    return math.sqrt(s) / a1


def main():
    res = {}
    fluxes = {}
    for ph in "ABC":
        p = os.path.join(CSVDIR, "flux_%s.csv" % ph.lower())
        if not os.path.exists(p):
            res["error"] = "missing " + p
            break
        t, lam = load_series(p)
        emf = -np.gradient(lam, t)
        fluxes[ph] = (t, lam, emf)
    if "error" not in res:
        # 取最后一个电周期（10 ms）为稳态窗口
        t, lam, emf = fluxes["A"]
        t_end = t[-1]
        mask = t >= (t_end - 0.010)
        eA = emf[mask]; eB = fluxes["B"][2][mask]; eC = fluxes["C"][2][mask]
        eLL = eA - eB
        res["bemf_phase_rms_V"] = float(np.sqrt(np.mean(eA ** 2)))
        res["bemf_line_rms_V"] = float(np.sqrt(np.mean(eLL ** 2)))
        res["bemf_line_thd_pct"] = float(thd(eLL, 1.0 / (t[1] - t[0])) * 100.0)
        res["flux_peak_Wb"] = float(np.max(np.abs(lam)))
        # 转矩
        tp = os.path.join(CSVDIR, "tq_noload.csv")
        if os.path.exists(tp):
            tt, tq = load_series(tp)
            m = tt >= (tt[-1] - 0.010)
            tq = tq * 1e-3  # mNewtonMeter -> N·m
            res["cogging_peak_Nm"] = float(np.max(np.abs(tq[m])))
            res["cogging_pct_rated"] = res["cogging_peak_Nm"] / 25.0 * 100.0
            res["torque_mean_Nm"] = float(np.mean(tq[m]))
        res["window_s"] = [float(t[mask][0]), float(t[mask][-1])]
    res["source"] = "Maxwell 2D transient, M5_25Nm.aedt"
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
