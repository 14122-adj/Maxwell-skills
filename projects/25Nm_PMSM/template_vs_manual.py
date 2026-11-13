#!/usr/bin/env python3
"""模板路径 vs 手写路径 — 空载 FEA 逐项对比（G4 验收）

两条路径
--------
* **手写路径**：`maxwell/m4_build_solve.py`（M4/M5 阶段，逐条真机报错调出来的）
  → `M5_25Nm.aedt`，401 点空载解，结论落在 `projects/results/fea_results.json`。
* **模板路径**：`maxwell_model/*.py`（`gen_maxwell_model.py` 从 `scripts/main.py`
  生成）→ `T4_tpl_noload.aedt`，同样 401 点。

为什么必须比
------------
G3b 只证明了"模板能建出 24 个图元"，没证明它**解出来的数是对的**。M2/M3 的教训是
"模型建成了、求解全错"。本脚本是 G4 的验收器：两条路径的空载 BEMF 相 RMS 与
齿槽转矩峰峰值若在同一量级（判据 ±10%），模板路径才算可用，此后所有几何试验
都可以走生成器，不必再手写模型。

单位陷阱（2026-11-08 踩过）
--------------------------
AEDT 导出表头带单位：`Time [us]`、`Torque [mNewtonMeter]`。直接当 s / N·m 用
会算出 403 N·m 这种错值。本脚本按表头单位做换算，找不到单位就按 ms / N·m 处理
并给出告警。

用法
----
    python template_vs_manual.py                       # 读默认目录
    python template_vs_manual.py --csvdir <dir>        # 指定模板路径 CSV 目录
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))   # projects/results
FEA = os.path.join(RESULTS, "fea")
DEFAULT_CSVDIR = r"D:/ANSYS_Run/csv_tpl"

# 判据：两条路径视为等价的门限
TOL_BEMF_PCT = 10.0
TOL_COGGING_PCT = 10.0
F_ELEC = 100.0          # 8 极 @ 1500 rpm
T_ELEC = 1.0 / F_ELEC   # 10 ms

_TIME_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}
_TQ_SCALE = {"NewtonMeter": 1.0, "mNewtonMeter": 1e-3, "uNewtonMeter": 1e-6}


def _unit(header: str, fallback: str) -> str:
    """从 `"Time [us]"` / `"Moving1.Torque [NewtonMeter]"` 里抠方括号内容。"""
    if "[" in header and "]" in header:
        return header[header.index("[") + 1:header.index("]")].strip()
    return fallback


def read_curve(path: str, time_fallback: str = "ms", tq_fallback: str = "NewtonMeter"):
    """读 AEDT 导出的两列表 -> (times[s], values[N·m])。"""
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    if not lines:
        return [], []
    head = [h.strip().strip('"') for h in lines[0].split(",")]
    ts = _TIME_SCALE.get(_unit(head[0], time_fallback), 1e-3)
    vs = _TQ_SCALE.get(_unit(head[-1], tq_fallback), 1.0)
    times, vals = [], []
    for ln in lines[1:]:
        parts = [p.strip().strip('"') for p in ln.split(",")]
        if len(parts) < 2:
            continue
        try:
            times.append(float(parts[0]) * ts)
            vals.append(float(parts[1]) * vs)
        except ValueError:
            continue
    return times, vals


def rms(xs) -> float:
    return (sum(x * x for x in xs) / len(xs)) ** 0.5 if xs else 0.0


def window(times, vals, t0: float, t1: float):
    return [(t, v) for (t, v) in zip(times, vals) if t0 <= t <= t1]


def derivative(times, vals):
    """中心差分求 dλ/dt（两端退化为一阶差分）。"""
    out = []
    n = len(times)
    for i in range(n):
        if n < 2:
            break
        if i == 0:
            dt = times[1] - times[0]
            d = (vals[1] - vals[0]) / dt if dt else 0.0
        elif i == n - 1:
            dt = times[-1] - times[-2]
            d = (vals[-1] - vals[-2]) / dt if dt else 0.0
        else:
            dt = times[i + 1] - times[i - 1]
            d = (vals[i + 1] - vals[i - 1]) / dt if dt else 0.0
        out.append(d)
    return out


def analyse(csvdir: str) -> dict:
    """对一条路径的空载 CSV 做同样的后处理，返回可比的量。"""
    out = {"csvdir": csvdir, "phases": {}, "tq_points": 0}
    # 空载 BEMF：e = -dλ/dt（电流型绕组没有 WindingX.Voltage 输出）
    for ph in ("a", "b", "c"):
        t, lam = read_curve(os.path.join(csvdir, "flux_%s.csv" % ph))
        if not t:
            continue
        e = [-d for d in derivative(t, lam)]
        t_end = t[-1]
        seg = window(t, e, t_end - T_ELEC, t_end)
        vals = [v for (_tt, v) in seg]
        out["phases"][ph.upper()] = {
            "n_samples": len(t),
            "t_end_ms": round(t_end * 1e3, 4),
            "rms_v": round(rms(vals), 4),
            "peak_v": round(max((abs(v) for v in vals), default=0.0), 4),
            "flux_pp_wb": round(max(lam) - min(lam), 6),
        }
    tt, tq = read_curve(os.path.join(csvdir, "tq_noload.csv"))
    if tt:
        t_end = tt[-1]
        seg = [v for (_t, v) in window(tt, tq, t_end - T_ELEC, t_end)]
        out["tq_points"] = len(tt)
        out["cogging"] = {
            "n_samples": len(seg),
            "mean_nm": round(sum(seg) / len(seg), 6) if seg else 0.0,
            "min_nm": round(min(seg), 6) if seg else 0.0,
            "max_nm": round(max(seg), 6) if seg else 0.0,
            "peak_to_peak_nm": round(max(seg) - min(seg), 6) if seg else 0.0,
        }
    rms_list = [v["rms_v"] for v in out["phases"].values()]
    out["bemf_rms_phase"] = round(sum(rms_list) / len(rms_list), 4) if rms_list else 0.0
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csvdir", default=DEFAULT_CSVDIR, help="模板路径 CSV 目录")
    ap.add_argument("--json", default=os.path.join(FEA, "template_vs_manual.json"))
    args = ap.parse_args(argv)

    manual_json = os.path.join(RESULTS, "fea_results.json")
    if not os.path.exists(manual_json):
        print("!! 缺手写路径结果:", manual_json)
        return 2
    with open(manual_json, encoding="utf-8") as fh:
        manual = json.load(fh)
    man = {
        "csvdir": manual.get("csvdir"),
        "bemf_rms_phase": manual["bemf_rms_phase"],
        "cogging_pp": manual["cogging"]["peak_to_peak_nm"],
        # 手写路径的原始采样点看波形文件本身（JSON 里的 n_samples 是稳态窗口样本数）
        "tq_points": len(read_curve(os.path.join(FEA, "tq_noload.csv"))[0]),
    }

    tpl = analyse(args.csvdir)
    if not tpl["phases"]:
        print("!! 模板路径没有导出 CSV（求解未完成？）:", args.csvdir)
        return 2

    def dev(a, b):
        return (a - b) / b * 100.0 if b else 0.0

    d_bemf = dev(tpl["bemf_rms_phase"], man["bemf_rms_phase"])
    cog_pp = tpl.get("cogging", {}).get("peak_to_peak_nm", 0.0)
    d_cog = dev(cog_pp, man["cogging_pp"])

    print("=" * 74)
    print("模板路径 vs 手写路径 — 空载 FEA 对比（G4 验收）")
    print("=" * 74)
    print("%-22s %14s %14s %10s" % ("项", "手写(m4)", "模板(G4)", "偏差"))
    print("-" * 74)
    print("%-22s %14.4f %14.4f %9.2f%%"
          % ("BEMF 相 RMS [V]", man["bemf_rms_phase"], tpl["bemf_rms_phase"], d_bemf))
    print("%-22s %14.4f %14.4f %9.2f%%"
          % ("齿槽峰峰值 [N·m]", man["cogging_pp"], cog_pp, d_cog))
    print("%-22s %14d %14d %10s"
          % ("转矩采样点", man["tq_points"], tpl["tq_points"], "-"))
    for ph, d in sorted(tpl["phases"].items()):
        print("  相 %s: RMS %.4f V / 峰值 %.4f V / 磁链峰峰 %.6f Wb / %d 点"
              % (ph, d["rms_v"], d["peak_v"], d["flux_pp_wb"], d["n_samples"]))
    print("-" * 74)
    ok_bemf = abs(d_bemf) <= TOL_BEMF_PCT
    ok_cog = abs(d_cog) <= TOL_COGGING_PCT
    print("判据: BEMF ±%.0f%% -> %s ; 齿槽 ±%.0f%% -> %s"
          % (TOL_BEMF_PCT, "PASS" if ok_bemf else "FAIL",
             TOL_COGGING_PCT, "PASS" if ok_cog else "FAIL"))
    verdict = "EQUIVALENT" if (ok_bemf and ok_cog) else "DIFFERS"
    print("结论:", verdict)

    payload = {
        "stage": "G4",
        "manual": man,
        "template": tpl,
        "deviation_pct": {"bemf_rms_phase": round(d_bemf, 4),
                          "cogging_peak_to_peak": round(d_cog, 4)},
        "tolerance_pct": {"bemf": TOL_BEMF_PCT, "cogging": TOL_COGGING_PCT},
        "pass": {"bemf": ok_bemf, "cogging": ok_cog},
        "verdict": verdict,
    }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print("写入:", args.json)

    # 证据留档：把模板路径的 4 条波形拷进仓库（与 11-10 的 fea/ 同口径）
    dst = os.path.join(FEA, "tpl")
    os.makedirs(dst, exist_ok=True)
    moved = 0
    for nm in ("tq_noload.csv", "flux_a.csv", "flux_b.csv", "flux_c.csv"):
        src = os.path.join(args.csvdir, nm)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, nm))
            moved += 1
    print("证据波形: %d 个 -> %s" % (moved, dst))
    return 0 if (ok_bemf and ok_cog) else 1


if __name__ == "__main__":
    raise SystemExit(main())
