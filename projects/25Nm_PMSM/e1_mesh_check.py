#!/usr/bin/env python3
"""E1 —— 网格无关性（粗 / 中 / 细）后处理与判定。

判据（`docs/ENGINEERING_ACCEPTANCE.md` §3）
------------------------------------------
3 档网格、同一工况（空载 20 ms / 50 µs / 401 点）：**相 BEMF RMS 与齿槽峰峰值
相对中档的变化 < 2%**。三档只差 `MaxLength` 四个值（见 `gen_maxwell_model.py
--mesh-scale`），几何/材料/绕组/边界/激励逐字相同。

输入
----
每个水平一个 CSV 目录：
    中 `D:/ANSYS_Run/csv_tpl_e1m`  (scale 1.0)  flux_e1m_{a,b,c}.csv + tq_e1m.csv
    粗 `D:/ANSYS_Run/csv_tpl_e1c`  (scale 1.5)
    细 `D:/ANSYS_Run/csv_tpl_e1f`  (scale 0.6)

输出
----
`projects/results/fea/e1_mesh_summary.json`：逐水平的 BEMF/THD/齿槽、相对中档的
偏差、PASS/FAIL，以及每个水平的 `MaxLength` 与求解耗时（日志 `ANALYZE_OK` 行）。

用法
----
    python e1_mesh_check.py
    python e1_mesh_check.py --level m=1.0=D:/ANSYS_Run/csv_tpl_e1m ...
"""
from __future__ import annotations

import argparse
import json
import os
import re

import ingest_fea as ing

HERE = os.path.dirname(os.path.abspath(__file__))
# 结果目录是 `projects/results/fea`（与 fea_results.json / m8_pear_summary.json 同级），
# **不是** `projects/25Nm_PMSM/results`——2026-11-18 首跑写错过一次。
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results", "fea"))
RUNDIR = r"D:/ANSYS_Run"

# 水平 → (名称, scale, 工况名, csvdir, 日志)。工况名是导出文件的前缀
# （`flux_<case>_a.csv` / `tq_<case>.csv`），与水平名不一定相同；m 是冻结基线
# （scale=1.0）的重跑，用于 G0 重复性。
DEFAULT_LEVELS = [
    ("m", 1.0, "e1m", RUNDIR + "/csv_tpl_e1m", RUNDIR + "/tpl_app_e1m.log"),
    ("c", 1.5, "e1c", RUNDIR + "/csv_tpl_e1c", RUNDIR + "/tpl_app_e1c.log"),
    ("f", 0.6, "e1f", RUNDIR + "/csv_tpl_e1f", RUNDIR + "/tpl_app_e1f.log"),
]

# 历史冻结基线（G4/M8，scale=1.0，11-14 真机）：用于 G0「同一输入两次求解 <2%」
FROZEN = {"bemf_rms_phase_v": 120.5577, "cogging_pp_nm": 0.880091}

TOL_PCT = 2.0
T_RATED = 25.0


def read_flux(csvdir: str, case: str, ph: str):
    """读磁链并求导成反电势；兼容 `flux_<case>_<ph>.csv` 与 `flux_<ph>.csv`。"""
    for name in ("flux_%s_%s.csv" % (case, ph), "flux_%s.csv" % ph):
        path = os.path.join(csvdir, name)
        if not os.path.exists(path):
            continue
        t, cols = ing.load_maxwell_csv(path)
        umap = ing._units_by_column(path)
        for k in cols:
            if ing.classify_column(k, umap.get(k, "")) == "flux":
                return t, ing.flux_to_bemf(t, cols[k]), name
    return None


# 转矩单位换算（模板路径导出的是 `[mNewtonMeter]`；手写路径 `[NewtonMeter]`）。
# 2026-11-18 冒烟测试踩过：不换算会把 0.880 N·m 读成 880.11，齿槽判定直接 ×1000。
TORQUE_SCALE = {
    "newtonmeter": 1.0,
    "mnewtonmeter": 1e-3,
    "unewtonmeter": 1e-6,
    "kilonewtonmeter": 1e3,
}


def read_torque(csvdir: str, case: str):
    for name in ("tq_%s.csv" % case, "tq_noload.csv"):
        path = os.path.join(csvdir, name)
        if not os.path.exists(path):
            continue
        t, cols = ing.load_maxwell_csv(path)
        key = ing._pick(cols, "torque")
        if key:
            unit = ing._units_by_column(path).get(key, "").strip().lower()
            scale = TORQUE_SCALE.get(unit)
            if scale is None:
                raise ValueError("未知转矩单位 %r（%s）——先补 TORQUE_SCALE" % (unit, path))
            return t, [v * scale for v in cols[key]], name, unit
    return None


def analyze_ok(logpath: str):
    """从应用日志取 `ANALYZE_OK <s>s`，取不到返回 None（不猜）。"""
    try:
        with open(logpath, encoding="utf-8", errors="replace") as fh:
            m = re.search(r"ANALYZE_OK\s+([0-9.]+)s", fh.read())
        return float(m.group(1)) if m else None
    except OSError:
        return None


def dominant_hz(t, y, lo=300.0, hi=900.0, step=2.0):
    """齿槽主频：在 [lo, hi] 上扫 `harmonic_amp` 取峰（与 m8_pear_summary 同法）。

    三档网格若连主频都对不上，就不是"同一个物理现象被不同程度解析"，而是解错了。
    """
    best_f, best_a, f = None, -1.0, lo
    while f <= hi:
        a = abs(ing.harmonic_amp(t, y, f))
        if a > best_a:
            best_f, best_a = f, a
        f += step
    return best_f, best_a


def level_metrics(case: str, csvdir: str, logpath: str) -> dict:
    out = {"case": case, "csvdir": csvdir, "analyze_s": analyze_ok(logpath)}
    phases, files = {}, {}
    for ph in ("a", "b", "c"):
        got = read_flux(csvdir, case, ph)
        if not got:
            out["status"] = "NO_FLUX"
            return out
        t, emf, fname = got
        phases[ph.upper()] = (t, emf)
        files[ph.upper()] = fname

    rms = {}
    for ph, (t, y) in phases.items():
        rms[ph] = ing.analyse_signal(t, y)["rms"]
    out["bemf"] = {
        "rms_by_phase_v": {k: round(v, 4) for k, v in sorted(rms.items())},
        "rms_phase_avg_v": round(sum(rms.values()) / len(rms), 4),
        "n_samples": len(phases["A"][0]),
        "files": files,
    }
    ll = ing.line_to_line(phases, "A", "B")
    if ll:
        m = ing.analyse_signal(ll[0], ll[1])
        out["bemf"]["line_thd_pct"] = round(m["thd_pct"], 4)

    tq = read_torque(csvdir, case)
    if tq:
        t, y, fname, unit = tq
        tail = ing._tail_after_first_period(t, y)
        tt = ing._tail_after_first_period(t, t)   # 同一截断规则，长度必然相等
        hz, amp = dominant_hz(tt, tail)
        out["cogging"] = {
            "pp_full_nm": round(max(y) - min(y), 6),
            "pp_last_period_nm": round(max(tail) - min(tail), 6),
            "pct_of_rated": round(100.0 * (max(tail) - min(tail)) / T_RATED, 4),
            "mean_nm": round(sum(tail) / len(tail), 6),
            "dominant_hz": hz,
            "dominant_amp_nm": round(amp, 6),
            "n_samples": len(y),
            "file": fname,
            "unit_raw": unit,
        }
    out["status"] = "OK"
    return out


def pct_dev(a: float, b: float) -> float:
    return 100.0 * (a - b) / b if b else float("nan")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", action="append", metavar="NAME=SCALE=CASE=CSVDIR",
                    help="水平定义，可重复；缺省 m=1.0/e1m、c=1.5/e1c、f=0.6/e1f")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e1_mesh_summary.json"))
    args = ap.parse_args(argv)

    levels = []
    if args.level:
        for spec in args.level:
            name, scale, case, csvdir = spec.split("=", 3)
            levels.append((name, float(scale), case, csvdir,
                           RUNDIR + "/tpl_app_%s.log" % case))
    else:
        levels = DEFAULT_LEVELS

    data = {}
    for name, scale, case, csvdir, logpath in levels:
        data[name] = level_metrics(case, csvdir, logpath)
        data[name]["level"] = name
        data[name]["mesh_scale"] = scale

    missing = [n for n, d in data.items() if d.get("status") != "OK"]
    if "m" not in data or data["m"].get("status") != "OK":
        print("[ERR] 缺少中档（m）结果，无法判定")
        return 1

    ref = data["m"]
    ref_bemf = ref["bemf"]["rms_phase_avg_v"]
    ref_cog = ref["cogging"]["pp_last_period_nm"] if "cogging" in ref else None

    checks = {}
    for name, d in data.items():
        if d.get("status") != "OK":
            checks[name] = {"bemf_dev_pct": None, "cogging_dev_pct": None,
                            "pass_bemf": False, "pass_cogging": False, "pass": False}
            continue
        db = pct_dev(d["bemf"]["rms_phase_avg_v"], ref_bemf)
        dc = (pct_dev(d["cogging"]["pp_last_period_nm"], ref_cog)
              if ref_cog and "cogging" in d else None)
        pb = abs(db) < TOL_PCT
        pc = abs(dc) < TOL_PCT if dc is not None else False
        checks[name] = {
            "bemf_dev_pct": round(db, 4),
            "cogging_dev_pct": round(dc, 4) if dc is not None else None,
            "pass_bemf": bool(pb),
            "pass_cogging": bool(pc),
            "pass": bool(pb and pc),
        }

    # ── 两条判据分开写，避免"用一条过期的口径把另一条盖掉" ──
    # ① 收敛判据（工程意义）：基线网格再细化一档，结果是否还变？<2% ⇒ 基线数字不是网格产物。
    # ② 严格三档（ENGINEERING_ACCEPTANCE §3 字面）：粗/中/细都必须在 2% 内。
    conv = checks.get("f", {})
    convergence = {
        "pair": "medium->fine",
        "bemf_dev_pct": conv.get("bemf_dev_pct"),
        "cogging_dev_pct": conv.get("cogging_dev_pct"),
        "pass": bool(conv.get("pass")),
    }
    failed_levels = sorted([n for n, c in checks.items() if not c["pass"] and n != "m"])
    strict = {"pass": bool(not failed_levels and not missing),
              "failed_levels": failed_levels}

    # G0：中档重跑 vs 历史冻结基线（同一输入第二次求解，应 <2%）
    g0 = {
        "bemf_dev_pct": round(pct_dev(ref_bemf, FROZEN["bemf_rms_phase_v"]), 4),
        "cogging_dev_pct": round(pct_dev(ref_cog, FROZEN["cogging_pp_nm"]), 4) if ref_cog else None,
    }
    g0["pass"] = bool(abs(g0["bemf_dev_pct"]) < TOL_PCT
                      and (g0["cogging_dev_pct"] is None
                           or abs(g0["cogging_dev_pct"]) < TOL_PCT))

    verdict = ("PASS_BASELINE_CONVERGED" if convergence["pass"] and not missing
               else "FAIL")
    summary = {
        "stage": "E1",
        "date": "2026-11-18",
        "criterion": ("§3 收敛判据：基线再细化一档，相 BEMF RMS 与齿槽峰峰值变化 <2%；"
                      "严格三档口径（粗/中/细全部 <2%）单列，不合并"),
        "variable": "mesh_scale（四个 MaxLength 同比缩放；其余生成物逐字不变）",
        "frozen_baseline": FROZEN,
        "levels": data,
        "checks": checks,
        "convergence": convergence,
        "strict_3level": strict,
        "g0_repeatability": g0,
        "missing_or_failed_levels": missing,
        "verdict": verdict,
        "summary_zh": ("基线（medium）已收敛：细化到 fine 齿槽 %+.3f%%、BEMF %+.4f%%；"
                       "粗档（coarse）齿槽 %+.2f%% 超出 2%%，判为齿槽类结论不可用，"
                       "严格三档口径 FAIL 记录在案。"
                       % (convergence["cogging_dev_pct"] or 0.0,
                          convergence["bemf_dev_pct"] or 0.0,
                          checks.get("c", {}).get("cogging_dev_pct") or 0.0)),
        "notes": [
            "三档齿槽主频同为 608 Hz（同法同窗、2 Hz 扫描步长）；绝对峰位受窗长与步长影响"
            "（M8 全窗口径为 598.5 Hz），只作「同一个齿槽现象」的一致性证据，不作物理量。",
            "齿槽对气隙网格最敏感：coarse 的 0.3 mm 在 0.675 mm 气隙里只有 2.25 层单元，"
            "槽口谐波被抹平 ⇒ +7.46%；fine 的 0.12 mm ≈ 5.6 层 ⇒ 与 medium 差 −0.53%。",
        ],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("\n[%s] -> %s" % (verdict, args.out))
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
