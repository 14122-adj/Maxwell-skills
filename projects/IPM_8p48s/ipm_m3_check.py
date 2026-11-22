#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M3' —— 负载 401 点独立重算 + I19 转矩平直判据

判据（PROJECT_SPEC §7.4 / 账本 I19）
-----------------------------------
* T_avg ∈ 22.5–27.5 N·m（25 ±10%）  —— Moving1.Torque 401 点，末周期均值
* 峰峰值 ≤ 10%·T_avg（≤2.5 N·m）    —— 末周期 201 点 max−min
* 主谐波幅值 ≤ 5%·T_avg             —— 末周期 FFT，剔除直流
* 单点跳变 ≤ 15%·T_avg              —— 末周期逐点差分 max|ΔT|

为什么要独立脚本
----------------
FEA 导出的 tq_load.csv 只是原料；判据必须由**独立脚本**读 CSV 重算，并把
`m3_load_<case>.json` 的 excitation 字段核对为"确实施加了电流"（反自演）。

转矩单位：AEDT 2021.1 本工程 Moving1.Torque 表头可能是 [uNewtonMeter] /
[mNewtonMeter] / [NewtonMeter]，按表头查表换算（与 ipm_m2_check.torque_scale 同源）。

用法
----
    python ipm_m3_check.py --csvdir D:/ANSYS_Run/csv_ipm_m3_load \
        --json projects/results/ipm8p48s/m3_load_load.json --case load
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_Spm = os.path.join(_ROOT, "projects", "25Nm_PMSM")
for _p in (_HERE, _Spm):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ingest_fea as ing  # noqa: E402

RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")
RUN_DIR = r"D:/ANSYS_Run"

T_AVG_RANGE = (22.5, 27.5)
PP_MAX_PCT = 10.0
HARMONIC_MAX_PCT = 5.0
JUMP_MAX_PCT = 15.0
F_ELEC = 100.0
TORQUE_SCALE = {
    "newtonmeter": 1.0, "mnewtonmeter": 1e-3, "unewtonmeter": 1e-6,
    "µnewtonmeter": 1e-6, "kilonewtonmeter": 1e3,
}


def torque_scale(unit: str) -> float:
    return TORQUE_SCALE.get((unit or "").strip().lower().replace(" ", ""), 1.0)


def load_torque(csvdir: str):
    path = os.path.join(csvdir, "tq_load.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    t, cols = ing.load_maxwell_csv(path)
    umap = ing._units_by_column(path)
    key = None
    for k in cols:
        u = (umap.get(k, "") or "").lower().replace(" ", "")
        if "torque" in k.lower() or u in TORQUE_SCALE:
            key = k
            break
    if key is None:
        key = list(cols)[0]
    unit = umap.get(key, "")
    scale = torque_scale(unit)
    return t, [v * scale for v in cols[key]], unit, scale, len(t)


def last_period(t, y):
    """末电周期（10 ms）窗口，整数索引，去重复端点。401 点 dt=50µs ⇒ 201 点。"""
    if len(t) < 10:
        return t, y
    diffs = sorted(t[i + 1] - t[i] for i in range(min(len(t) - 1, 50)))
    dt = diffs[len(diffs) // 2] if diffs else 0.0
    n_per = int(round((1.0 / F_ELEC) / dt)) if dt > 0 else 0
    if n_per <= 0 or len(t) <= n_per:
        return t, y
    # 取末尾 N 点（去重复端点：若首末时间相同则丢末点）
    ts, ys = t[-n_per:], y[-n_per:]
    if len(ts) > 1 and abs(ts[0] - ts[-1]) < dt * 0.5:
        ts, ys = ts[:-1], ys[:-1]
    return ts, ys


def dft_magnitudes(t, y):
    """单周期 DFT（去均值），返回 [(谐波次数, 幅值)]，h=1..N/2。"""
    n = len(y)
    if n < 4:
        return []
    mean = sum(y) / n
    out = []
    # 用整数索引采样，避免浮点窗口边界（P16 教训）
    for h in range(1, n // 2 + 1):
        re = sum((y[k] - mean) * math.cos(2.0 * math.pi * h * k / n)
                 for k in range(n))
        im = -sum((y[k] - mean) * math.sin(2.0 * math.pi * h * k / n)
                  for k in range(n))
        out.append((h, 2.0 * abs(complex(re, im)) / n))
    return out


def fundamental(t, y):
    """单周期（第二电周期）基波幅值 + 相位，以 sin(ωt) 为参考。

    与账本 I21 口径一致：跳过第一电周期，取随后 N=round(T/dt)-1 点（去重复端点），
    去均值后单周期 DFT：e(t)=A·sin(ωt+φ)。返回 (amp, phase_deg, rms, n)。
    """
    if len(t) < 10:
        return 0.0, 0.0, 0.0, 0
    diffs = sorted(t[i + 1] - t[i] for i in range(min(len(t) - 1, 50)))
    dt = diffs[len(diffs) // 2] if diffs else 0.0
    n_per = int(round((1.0 / F_ELEC) / dt)) if dt > 0 else 0
    n_skip = n_per
    if n_per <= 0 or len(t) - n_skip < 10:
        return 0.0, 0.0, 0.0, 0
    ts, ys = t[n_skip:], y[n_skip:]
    # 去重复端点：窗口 n_per+1 点时丢弃末点，得整周期 n_per 点
    if len(ts) > n_per and abs(ts[-1] - ts[0] - n_per * dt) < dt * 0.5:
        pass
    if len(ts) > 1 and abs(ts[-1] - ts[-2] - dt) > dt * 0.5:
        ts, ys = ts[:-1], ys[:-1]
    n = len(ys)
    if n < 4:
        return 0.0, 0.0, 0.0, n
    mean = sum(ys) / n
    # e = a·sin(ωt) + b·cos(ωt)；amp=√(a²+b²)，φ=atan2(b,a)
    sa = sum((ys[k] - mean) * math.sin(2.0 * math.pi * k / n) for k in range(n))
    sb = sum((ys[k] - mean) * math.cos(2.0 * math.pi * k / n) for k in range(n))
    a = 2.0 * sa / n
    b = 2.0 * sb / n
    amp = math.hypot(a, b)
    phase = math.degrees(math.atan2(b, a))
    rms = math.sqrt(sum(v * v for v in ys) / n)
    return amp, phase, rms, n


def bemf_load_block(csvdir: str, noload_rms: float | None = None) -> dict | None:
    """I21：负载工况 BEMF 独立重算（与空载分列），写幅值/RMS/相位/相对空载%。

    数据来自负载 flux_<ph>.csv 的 d(FluxLinkage)/dt；没有 flux CSV 时返回 None
    （不阻塞 I19 转矩判据，避免破坏既有 M3 case 回归）。
    """
    phases = {}
    src = {}
    for ph in ("a", "b", "c"):
        got = ing.load_phase_bemf(csvdir, ph)
        if got is None:
            return None
        t, e, how = got
        phases[ph.upper()] = (t, e)
        src[ph.upper()] = how
    out = {"sources": src, "phase": {}, "note": "I21: 负载 BEMF = d(FluxLinkage)/dt，第二电周期基波 DFT"}
    amps = []
    for ph, (t, e) in phases.items():
        amp, phase, rms, n = fundamental(t, e)
        amps.append(amp)
        out["phase"][ph] = {
            "fundamental_amp_v": round(amp, 4),
            "rms_v": round(rms, 4),
            "phase_deg": round(phase, 4),
            "n_samples": n,
        }
    out["fundamental_amp_mean_v"] = round(sum(amps) / len(amps), 4) if amps else 0.0
    if noload_rms and noload_rms > 1e-9:
        load_rms = sum(v["rms_v"] for v in out["phase"].values()) / len(out["phase"])
        out["rms_vs_noload_pct"] = round(100.0 * (load_rms - noload_rms) / noload_rms, 4)
        out["noload_rms_reference_v"] = round(noload_rms, 4)
    return out


def check(csvdir: str, meta: dict, noload_rms: float | None = None) -> dict:
    t_all, tq_all, unit, scale, n_rows = load_torque(csvdir)
    t_win, tq_win = last_period(t_all, tq_all)
    n_win = len(tq_win)
    t_avg = sum(tq_win) / n_win
    pp = max(tq_win) - min(tq_win)
    harm = dft_magnitudes(t_win, tq_win)
    if harm:
        h_top = max(harm, key=lambda x: x[1])
        h_amp = h_top[1]
        h_order = h_top[0]
    else:
        h_top = (0, 0.0)
        h_amp = 0.0
        h_order = 0
    jumps = [abs(tq_win[k + 1] - tq_win[k]) for k in range(n_win - 1)]
    jump_max = max(jumps) if jumps else 0.0

    pp_pct = 100.0 * pp / abs(t_avg) if abs(t_avg) > 1e-9 else float("inf")
    h_pct = 100.0 * h_amp / abs(t_avg) if abs(t_avg) > 1e-9 else float("inf")
    jump_pct = 100.0 * jump_max / abs(t_avg) if abs(t_avg) > 1e-9 else float("inf")

    checks = [
        dict(name="T_avg ∈ 22.5–27.5 N·m", value=round(t_avg, 4),
             limit=list(T_AVG_RANGE), op="in",
             status="PASS" if T_AVG_RANGE[0] <= t_avg <= T_AVG_RANGE[1] else "FAIL"),
        dict(name="峰峰值 ≤ 10% T_avg", value=round(pp_pct, 4),
             limit=PP_MAX_PCT, op="<=",
             status="PASS" if pp_pct <= PP_MAX_PCT else "FAIL"),
        dict(name="主谐波幅值 ≤ 5% T_avg", value=round(h_pct, 4),
             limit=HARMONIC_MAX_PCT, op="<=",
             status="PASS" if h_pct <= HARMONIC_MAX_PCT else "FAIL"),
        dict(name="单点跳变 ≤ 15% T_avg", value=round(jump_pct, 4),
             limit=JUMP_MAX_PCT, op="<=",
             status="PASS" if jump_pct <= JUMP_MAX_PCT else "FAIL"),
    ]

    # excitation 真施加核对（反自演）：负载必须记录非零 Imax
    exc = meta.get("excitation", {}) if isinstance(meta, dict) else {}
    imax = exc.get("current_A", 0) or 0
    checks.append(dict(name="负载 excitation.current_A > 0（真施加电流）",
                       value=imax, limit=0, op=">",
                       status="PASS" if imax > 0 else "FAIL"))

    return dict(
        stage="M3' 401 点负载（I18 电流 + I19 平直）",
        torque=dict(
            t_avg_nm=round(t_avg, 6), pp_nm=round(pp, 6), pp_pct=round(pp_pct, 4),
            main_harmonic_order=h_order, main_harmonic_nm=round(h_amp, 6),
            main_harmonic_pct=round(h_pct, 4), jump_max_nm=round(jump_max, 6),
            jump_max_pct=round(jump_pct, 4),
            window_samples=n_win, total_rows=n_rows,
            torque_unit=unit, torque_scale=scale,
            spectrum_top5=[(h, round(a, 6)) for h, a in sorted(harm, key=lambda x: -x[1])[:5]],
        ),
        excitation=exc,
        bemf_load=bemf_load_block(csvdir, noload_rms),
        checks=checks,
        status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M3' 负载独立重算 + I19")
    ap.add_argument("--csvdir", default=RUN_DIR + "/csv_ipm_m3_load")
    ap.add_argument("--json", default=os.path.join(RESULTS, "m3_load_load.json"))
    ap.add_argument("--out", default=os.path.join(RESULTS, "m3_load_check.json"))
    ap.add_argument("--noload-json", default=None,
                    help="空载 M2' JSON，用于算负载/空载 BEMF 相对%（I21）；缺省则只读绝对量")
    args = ap.parse_args(argv)

    with open(args.json, encoding="utf-8") as fh:
        meta = json.load(fh)
    noload_rms = None
    if args.noload_json and os.path.exists(args.noload_json):
        with open(args.noload_json, encoding="utf-8") as fh:
            nl = json.load(fh)
        noload_rms = nl.get("bemf", {}).get("phase_rms_mean")
    res = check(args.csvdir, meta, noload_rms)
    res["source_json"] = args.json
    res["csvdir"] = args.csvdir

    print("=" * 74)
    print("M3' 负载复核  status=%s" % res["status"])
    print("=" * 74)
    tq = res["torque"]
    print("  T_avg=%.4f N·m  pp=%.4f (%.2f%%)  主谐波 h=%d %.4f N·m (%.2f%%)  跳变 %.4f (%.2f%%)"
          % (tq["t_avg_nm"], tq["pp_nm"], tq["pp_pct"], tq["main_harmonic_order"],
             tq["main_harmonic_nm"], tq["main_harmonic_pct"],
             tq["jump_max_nm"], tq["jump_max_pct"]))
    print("  单位=%s scale=%g 窗口=%d 点 全样本=%d" %
          (tq["torque_unit"], tq["torque_scale"], tq["window_samples"], tq["total_rows"]))
    bl = res.get("bemf_load")
    if bl:
        a = bl["phase"]["A"]
        print("  负载BEMF(I21): A相基波 %.4f V @ %.2f°  RMS %.4f V  相对空载 %s%%"
              % (a["fundamental_amp_v"], a["phase_deg"], a["rms_v"],
                 bl.get("rms_vs_noload_pct", "n/a")))
    for c in res["checks"]:
        print("    [%s] %-40s %12s / %s" % (c["status"], c["name"], c["value"], c["limit"]))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print("  ✔ %s" % args.out)
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
