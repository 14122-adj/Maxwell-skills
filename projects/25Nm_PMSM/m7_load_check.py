#!/usr/bin/env python3
"""M7 负载工况验收 — 模板路径 vs 手写路径（G6 最后一条未测项）。

为什么单独一个脚本
------------------
`ingest_fea.py` 是「CSV → fea_results.json」的工作区通道，但它把空载 BEMF/齿槽
与负载转矩混在同一个 `compute()` 里；负载工况若也导出 `flux_a.csv`，它会把
**负载磁链**当成空载去求 BEMF，得到一个物理上无意义的数。M7 要判的是三件事：

1. 模板路径的 `T_avg` 是否与手写路径 `M5_load_25Nm.aedt` 的 22.3344 N·m 同量级
   （判据 ±10%，见 `docs/ENGINEERING_ACCEPTANCE.md` §3「双路径」）；
2. 是否达到 25 N·m ±20% 的工程下限（`fea_results.json` 同口径）；
3. 电流是否真按指令流（原生 `WindingX_TrCrv.txt` 逐点比对，幅值+相位一起验）。

双法复核（反自演规则 8）
------------------------
* 通道 A：本文件的独立解析（自带单位换算 + 梯形积分）；
* 通道 B：`ingest_fea.load_block()`（工作区脚本，窗口内简单平均）。

两法对 `T_avg` 的偏差必须在 0.5% 内，否则说明 CSV 单位/窗口口径有问题，
结果一律不采信（先修口径，别急着下结论）。

用法
----
    python m7_load_check.py                      # 读 D:/ANSYS_Run/csv_tpl_load
    python m7_load_check.py --csvdir <dir> --json <path>
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))
FEA = os.path.join(RESULTS, "fea")

DEFAULT_CSVDIR = r"D:/ANSYS_Run/csv_tpl_load"
AEDT_LOAD = r"D:/ANSYS_Run/T4_tpl_load.aedt"

F_ELEC = 100.0            # 8 极 @ 1500 rpm
T_ELEC = 1.0 / F_ELEC     # 10 ms
T_RATED = 25.0
W_MECH = 2.0 * math.pi * 1500.0 / 60.0     # 157.0796 rad/s
I_RMS = 9.89
PHASE_DEG = {"A": 120.0, "B": 240.0, "C": 0.0}
SIGN = -1                 # 电动：i 与 e=-dλ/dt 反相

TOL_VS_MANUAL_PCT = 10.0  # 双路径一致性（ACCEPTANCE §3）
TOL_VS_RATED_PCT = 20.0   # 工程下限（fea_results.json 口径）
TOL_RIPPLE_PCT = 15.0     # E7 验收下限（目标 10%）
TOL_TWO_METHOD_PCT = 0.5  # 双法复核

_T_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6}
_V_SCALE = {"NewtonMeter": 1.0, "mNewtonMeter": 1e-3, "uNewtonMeter": 1e-6}


def _unit(header: str, fallback: str) -> str:
    if "[" in header and "]" in header:
        return header[header.index("[") + 1:header.index("]")].strip()
    return fallback


def read_two_col(path: str):
    """独立解析 AEDT 两列导出（时间/转矩），按表头单位换算到 s / N·m。"""
    if not os.path.exists(path):
        return [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        rows = [ln.strip() for ln in fh if ln.strip()]
    if not rows:
        return [], []
    head = [h.strip().strip('"') for h in rows[0].split(",")]
    ts = _T_SCALE.get(_unit(head[0], "ms"), 1e-3)
    vs = _V_SCALE.get(_unit(head[-1], "NewtonMeter"), 1.0)
    t, v = [], []
    for ln in rows[1:]:
        parts = [p.strip().strip('"') for p in ln.split(",")]
        if len(parts) < 2:
            continue
        try:
            t.append(float(parts[0]) * ts)
            v.append(float(parts[1]) * vs)
        except ValueError:
            continue
    return t, v


def window(t, v, t0: float, t1: float):
    idx = [i for i in range(len(t)) if t0 <= t[i] <= t1]
    return [t[i] for i in idx], [v[i] for i in idx]


def trapezoid_mean(t, v) -> float:
    """梯形积分求均值 —— 与工作区脚本的简单平均是两条独立路径。"""
    if len(t) < 2:
        return 0.0
    a = 0.0
    for i in range(len(t) - 1):
        a += 0.5 * (v[i] + v[i + 1]) * (t[i + 1] - t[i])
    span = t[-1] - t[0]
    return a / span if span else 0.0


def metrics(t, v) -> dict:
    if not v:
        return {}
    return {
        "T_avg_nm": round(trapezoid_mean(t, v), 4),
        "T_min_nm": round(min(v), 4),
        "T_max_nm": round(max(v), 4),
        "T_pp_nm": round(max(v) - min(v), 4),
        "n_samples": len(v),
        "t_window_ms": [round(t[0] * 1e3, 3), round(t[-1] * 1e3, 3)],
    }


def commanded_current(ph: str, t: float) -> float:
    rad = math.radians(PHASE_DEG[ph])
    return SIGN * I_RMS * math.sqrt(2.0) * math.sin(2 * math.pi * F_ELEC * t + rad)


def find_native_dir(root: str) -> str | None:
    """在 `.aedtresults` 里找含 `WindingA_TrCrv.txt` 的目录（环形缓冲，尾 10 步）。"""
    for cur, _dirs, files in os.walk(root):
        if "WindingA_TrCrv.txt" in files:
            return cur
    return None


def read_trcrv(path: str) -> dict:
    out = {"t": [], "current": [], "flux": [], "voltage": []}
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return out
    i = 2
    while i + 1 < len(lines):
        try:
            tt = float(lines[i])
            vals = [float(x) for x in lines[i + 1].split()]
        except ValueError:
            break
        if len(vals) < 5:
            break
        out["t"].append(tt)
        out["current"].append(vals[0])
        out["flux"].append(vals[3])
        out["voltage"].append(vals[4])
        i += 2
    return out


def current_check(native_dir: str | None) -> dict:
    """原生 TrCrv：实测电流 vs 指令（幅值+相位一起验），并给 Σv·i 判电动/发电。"""
    if not native_dir:
        return {}
    res, sign_sum = {}, 0.0
    for ph in ("A", "B", "C"):
        p = os.path.join(native_dir, "Winding%s_TrCrv.txt" % ph)
        if not os.path.exists(p):
            continue
        nat = read_trcrv(p)
        if not nat["t"]:
            continue
        err = [abs(nat["current"][i] - commanded_current(ph, nat["t"][i]))
               for i in range(len(nat["t"]))]
        sign_sum += sum(nat["voltage"][i] * nat["current"][i] for i in range(len(nat["t"])))
        res[ph] = {
            "samples": len(nat["t"]),
            "t_window_ms": [round(nat["t"][0] * 1e3, 3), round(nat["t"][-1] * 1e3, 3)],
            "max_dev_a": round(max(err), 5),
            "max_dev_pct_of_peak": round(100.0 * max(err) / (I_RMS * math.sqrt(2.0)), 3),
            "peak_measured_a": round(max(abs(x) for x in nat["current"]), 4),
        }
    if res:
        res["_sum_vi"] = round(sign_sum, 2)
        res["_motoring"] = bool(sign_sum > 0)
    return res


def workspace_crosscheck(csvdir: str, bemf_rms: float, native_dir: str | None) -> dict:
    """通道 B：复用工作区 `ingest_fea.load_block()`（简单平均窗口）。"""
    sys.path.insert(0, HERE)
    try:
        import ingest_fea
    except Exception as exc:                      # pragma: no cover - 环境缺依赖
        return {"error": repr(exc)}
    blk = ingest_fea.load_block(csvdir, bemf_rms=bemf_rms, native_dir=native_dir)
    return blk or {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csvdir", default=DEFAULT_CSVDIR)
    ap.add_argument("--native-dir", default=None, help="缺省自动在 .aedtresults 里找")
    ap.add_argument("--json", default=os.path.join(FEA, "m7_load_summary.json"))
    args = ap.parse_args(argv)

    t, tq = read_two_col(os.path.join(args.csvdir, "tq_load.csv"))
    if not t:
        print("!! 没有 tq_load.csv 数据（求解未完成？）:", args.csvdir)
        return 2

    native = args.native_dir or find_native_dir(AEDT_LOAD + "results")
    t_end = t[-1]
    # 窗口左端点要留半个步长的余量：t_end − 10 ms 与 CSV 里的 10.000 在浮点上
    # 可能差 1 ulp（0.010000000000000002 > 0.01），严格比较会把首样本踢掉，
    # 窗口变成 9.95 ms —— 均值偏 0.03%，属于静默口径偏差。
    dt = (t[1] - t[0]) if len(t) > 1 else 0.0
    tw, vw = window(t, tq, t_end - T_ELEC - 0.5 * dt, t_end)
    m = metrics(tw, vw)
    if not m:
        print("!! 末周期窗口无样本，检查 Time 单位/步长")
        return 2

    t_avg = m["T_avg_nm"]
    ripple = 100.0 * m["T_pp_nm"] / abs(t_avg) if abs(t_avg) > 1e-9 else 0.0
    m["T_ripple_pct"] = round(ripple, 3)

    # 手写路径基线（M5）
    with open(os.path.join(RESULTS, "fea_results.json"), encoding="utf-8") as fh:
        manual = json.load(fh).get("load", {})
    man_avg = manual.get("T_avg_nm")
    man_ripple = manual.get("T_ripple_pct")

    # 空载 BEMF（模板 M8）用于功率平衡；没有就退回手写基线
    bemf = 120.5594
    m8 = os.path.join(FEA, "m8_pear_summary.json")
    if os.path.exists(m8):
        with open(m8, encoding="utf-8") as fh:
            bemf = json.load(fh)["bemf"]["rms_phase_avg_v"]

    blk = workspace_crosscheck(args.csvdir, bemf, native)
    ws_avg = blk.get("T_avg_nm")
    two_method = (abs(t_avg - ws_avg) / abs(ws_avg) * 100.0) if ws_avg else None

    d_manual = (t_avg - man_avg) / man_avg * 100.0 if man_avg else None
    d_rated = (t_avg - T_RATED) / T_RATED * 100.0

    p_mech = t_avg * W_MECH
    p_emf = 3.0 * bemf * I_RMS
    cur = current_check(native)

    ok_manual = d_manual is not None and abs(d_manual) <= TOL_VS_MANUAL_PCT
    ok_rated = abs(d_rated) <= TOL_VS_RATED_PCT
    ok_ripple = ripple <= TOL_RIPPLE_PCT
    ok_two = two_method is not None and two_method <= TOL_TWO_METHOD_PCT
    ok_cur = bool(cur) and max(v["max_dev_pct_of_peak"] for k, v in cur.items()
                               if not k.startswith("_")) <= 5.0
    ok_sign = bool(cur) and cur.get("_motoring", False)

    print("=" * 78)
    print("M7 — 模板路径负载工况验收（2026-11-15）")
    print("=" * 78)
    print("%-26s %12s %12s %10s" % ("项", "手写 M5", "模板 M7", "偏差"))
    print("-" * 78)
    print("%-26s %12s %12.4f %9s"
          % ("T_avg [N·m]", ("%.4f" % man_avg) if man_avg else "—", t_avg,
             ("%+.2f%%" % d_manual) if d_manual is not None else "—"))
    print("%-26s %12s %12.3f %9s"
          % ("转矩脉动 [%]", ("%.3f" % man_ripple) if man_ripple else "—", ripple, "—"))
    print("%-26s %12s %7.4f/%.4f %8s"
          % ("T_min/T_max [N·m]", "—", m["T_min_nm"], m["T_max_nm"], "—"))
    print("%-26s %12s %12d %9s" % ("采样点", "—", m["n_samples"], "—"))
    print("-" * 78)
    print("双法复核: 独立梯形积分 %.4f vs ingest_fea %.4f → 偏差 %s"
          % (t_avg, ws_avg if ws_avg else 0.0,
             ("%.3f%%" % two_method) if two_method is not None else "—"))
    print("功率平衡: P_mech %.1f W vs 3·E·I %.1f W → %+.2f%%（E=%.4f V 空载）"
          % (p_mech, p_emf, 100.0 * (p_mech - p_emf) / p_emf, bemf))
    for ph in ("A", "B", "C"):
        if ph in cur:
            d = cur[ph]
            print("  电流 %s: 峰值 %.4f A / 逐点最大偏差 %.5f A（%.3f%% of peak）"
                  % (ph, d["peak_measured_a"], d["max_dev_a"], d["max_dev_pct_of_peak"]))
    if cur:
        print("  Σ(v·i) = %.2f ⇒ %s"
              % (cur["_sum_vi"], "电动 MOTORING" if cur["_motoring"] else "发电 BRAKING(符号错)"))
    print("-" * 78)
    print("判据: 双路径 ±%.0f%% -> %s | 25±%.0f%% -> %s | 脉动 ≤%.0f%% -> %s | 双法 ≤%.1f%% -> %s | 电流 ≤5%% -> %s | 电动 -> %s"
          % (TOL_VS_MANUAL_PCT, "PASS" if ok_manual else "FAIL",
             TOL_VS_RATED_PCT, "PASS" if ok_rated else "FAIL",
             TOL_RIPPLE_PCT, "PASS" if ok_ripple else "FAIL",
             TOL_TWO_METHOD_PCT, "PASS" if ok_two else "FAIL",
             "PASS" if ok_cur else "FAIL", "PASS" if ok_sign else "FAIL"))
    all_ok = all([ok_manual, ok_rated, ok_ripple, ok_two, ok_cur, ok_sign])
    print("结论:", "PASS（G6 负载项关闭）" if all_ok else "FAIL（保留记录，明日继续）")

    payload = {
        "stage": "M7",
        "date": "2026-11-15",
        "case": "load (template path, gen_maxwell_model --case load)",
        "csvdir": args.csvdir,
        "native_dir": native,
        "torque": m,
        "bemf_noload_v": bemf,
        "manual_m5": {"T_avg_nm": man_avg, "T_ripple_pct": man_ripple,
                      "source": "projects/results/fea_results.json:load"},
        "two_method": {"independent_trapezoid_nm": t_avg,
                       "ingest_fea_simple_mean_nm": ws_avg,
                       "dev_pct": round(two_method, 4) if two_method is not None else None},
        "power_balance": {"P_mech_w": round(p_mech, 1), "P_emf_w": round(p_emf, 1),
                          "dev_pct": round(100.0 * (p_mech - p_emf) / p_emf, 2),
                          "note": "P_emf 用空载 BEMF；差值含电枢反应与齿槽"},
        "currents": cur,
        "deviation_pct": {"vs_manual_m5": round(d_manual, 3) if d_manual is not None else None,
                          "vs_rated_25nm": round(d_rated, 3)},
        "criteria": {
            "dual_path_10pct": bool(ok_manual),
            "rated_20pct": bool(ok_rated),
            "ripple_15pct": bool(ok_ripple),
            "two_method_0p5pct": bool(ok_two),
            "current_5pct": bool(ok_cur),
            "motoring_sign": bool(ok_sign),
        },
        "verdict": "PASS" if all_ok else "FAIL",
    }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print("写入:", args.json)

    dst = os.path.join(FEA, "m7_load")
    os.makedirs(dst, exist_ok=True)
    moved = 0
    for nm in ("tq_load.csv", "flux_load_a.csv", "flux_load_b.csv", "flux_load_c.csv"):
        src = os.path.join(args.csvdir, nm)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, nm))
            moved += 1
    print("证据波形: %d 个 -> %s" % (moved, dst))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
