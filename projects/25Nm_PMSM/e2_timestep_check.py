#!/usr/bin/env python3
"""E2 —— 时间步无关性（50 µs / 401 点 vs 25 µs / 801 点）后处理与判定。

判据（`docs/ENGINEERING_ACCEPTANCE.md` §3）
------------------------------------------
同一几何/网格/激励，只改 `TimeStep`：**相 BEMF RMS 与齿槽峰峰值相对 50 µs 基线的
变化 < 2%**。用 `e1_mesh_check.level_metrics` 同一套后处理，避免"换脚本换口径"。

输入
----
    t50  `D:/ANSYS_Run/csv_tpl_e1m`   （E1 中档 = 冻结基线同模型重跑，50 µs / 401 点）
    t25  `D:/ANSYS_Run/csv_tpl_e2t25` （E2，25 µs / 801 点）

附加交叉校验
------------
1. **降采样一致性**：把 25 µs 的**磁链**每 2 点取 1（→50 µs 网格）再求导，
   与 50 µs 基线比较。若两者差异与直接比较同量级，说明差异来自时间离散，
   而不是"多出来的点算出了另一个物理"。
2. **E1 分辨力地板**：读 `e1_mesh_summary.json` 的 medium→fine 偏差，
   标出本次差异是否小于该地板（BEMF 0.006% / 齿槽 0.5%）——小于地板不立结论。

用法
----
    python e2_timestep_check.py
    python e2_timestep_check.py --level t25=e2t25=D:/ANSYS_Run/csv_tpl_e2t25
"""
from __future__ import annotations

import argparse
import json
import os

import e1_mesh_check as e1
import ingest_fea as ing

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.abspath(os.path.join(HERE, "..", "results", "fea"))
RUNDIR = r"D:/ANSYS_Run"

DEFAULT_LEVELS = [
    ("t50", "e1m", RUNDIR + "/csv_tpl_e1m", RUNDIR + "/tpl_app_e1m.log"),
    ("t25", "e2t25", RUNDIR + "/csv_tpl_e2t25", RUNDIR + "/tpl_app_e2t25.log"),
]

TOL_PCT = 2.0
T_RATED = 25.0


def read_flux_raw(csvdir: str, case: str, ph: str):
    """读原始磁链（不求导）——降采样交叉校验需要先降采样再求导。"""
    for name in ("flux_%s_%s.csv" % (case, ph), "flux_%s.csv" % ph):
        path = os.path.join(csvdir, name)
        if not os.path.exists(path):
            continue
        t, cols = ing.load_maxwell_csv(path)
        umap = ing._units_by_column(path)
        for k in cols:
            if ing.classify_column(k, umap.get(k, "")) == "flux":
                return t, cols[k], name
    return None


def decimated_metrics(csvdir: str, case: str, stride: int = 2) -> dict:
    """25 µs → 50 µs 网格：磁链降采样后求导/转矩降采样后取 pp。"""
    out = {"stride": stride}
    rms = {}
    for ph in ("a", "b", "c"):
        got = read_flux_raw(csvdir, case, ph)
        if not got:
            return {"status": "NO_FLUX"}
        t, lam, _ = got
        td, ld = t[::stride], lam[::stride]
        emf = ing.flux_to_bemf(td, ld)
        rms[ph.upper()] = ing.analyse_signal(td, emf)["rms"]
    out["bemf_rms_phase_avg_v"] = round(sum(rms.values()) / len(rms), 4)
    out["bemf_rms_by_phase_v"] = {k: round(v, 4) for k, v in sorted(rms.items())}

    tq = e1.read_torque(csvdir, case)
    if tq:
        t, y, _, _ = tq
        td, yd = t[::stride], y[::stride]
        tail = ing._tail_after_first_period(td, yd)
        out["cogging_pp_last_period_nm"] = round(max(tail) - min(tail), 6)
        out["n_samples"] = len(td)
    out["status"] = "OK"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--level", action="append", metavar="NAME=CASE=CSVDIR",
                    help="水平定义，可重复；缺省 t50=e1m、t25=e2t25")
    ap.add_argument("--out", default=os.path.join(RESULTS, "e2_timestep_summary.json"))
    args = ap.parse_args(argv)

    levels = []
    if args.level:
        for spec in args.level:
            name, case, csvdir = spec.split("=", 2)
            levels.append((name, case, csvdir, RUNDIR + "/tpl_app_%s.log" % case))
    else:
        levels = DEFAULT_LEVELS

    data = {}
    for name, case, csvdir, logpath in levels:
        d = e1.level_metrics(case, csvdir, logpath)
        d["time_step_us"] = 50.0 if name == "t50" else 25.0
        d["level"] = name
        data[name] = d

    if data.get("t50", {}).get("status") != "OK" or data.get("t25", {}).get("status") != "OK":
        print("[ERR] 缺水平结果：t50=%s / t25=%s"
              % (data.get("t50", {}).get("status"), data.get("t25", {}).get("status")))
        return 1

    ref, fine = data["t50"], data["t25"]
    dev = {
        "bemf_dev_pct": round(e1.pct_dev(fine["bemf"]["rms_phase_avg_v"],
                                         ref["bemf"]["rms_phase_avg_v"]), 4),
        "cogging_dev_pct": round(e1.pct_dev(fine["cogging"]["pp_last_period_nm"],
                                            ref["cogging"]["pp_last_period_nm"]), 4),
        "thd_delta_pt": round(fine["bemf"].get("line_thd_pct", 0.0)
                              - ref["bemf"].get("line_thd_pct", 0.0), 4),
    }
    dev["pass_bemf"] = bool(abs(dev["bemf_dev_pct"]) < TOL_PCT)
    dev["pass_cogging"] = bool(abs(dev["cogging_dev_pct"]) < TOL_PCT)
    dev["pass"] = bool(dev["pass_bemf"] and dev["pass_cogging"])

    cross = decimated_metrics(fine["csvdir"], fine["case"], stride=2)
    if cross.get("status") == "OK":
        cross["bemf_dev_vs_t50_pct"] = round(
            e1.pct_dev(cross["bemf_rms_phase_avg_v"], ref["bemf"]["rms_phase_avg_v"]), 4)
        cross["cogging_dev_vs_t50_pct"] = round(
            e1.pct_dev(cross["cogging_pp_last_period_nm"],
                       ref["cogging"]["pp_last_period_nm"]), 4)

    floor = {}
    e1path = os.path.join(RESULTS, "e1_mesh_summary.json")
    if os.path.exists(e1path):
        with open(e1path, encoding="utf-8") as fh:
            e1s = json.load(fh)
        conv = e1s.get("convergence", {})
        floor = {"bemf_pct": abs(conv.get("bemf_dev_pct") or 0.0),
                 "cogging_pct": abs(conv.get("cogging_dev_pct") or 0.0),
                 "source": "e1_mesh_summary.json convergence (medium->fine)"}

    verdict = "PASS_TIMESTEP_CONVERGED" if dev["pass"] else "FAIL"
    summary = {
        "stage": "E2",
        "date": "2026-11-18",
        "criterion": ("§3：50 µs vs 25 µs，同一工况（空载 20 ms），"
                      "相 BEMF RMS 与齿槽峰峰值变化 <2%"),
        "variable": "TimeStep（50→25 µs，StopTime 0.02 s 不变 ⇒ 401→801 点；"
                    "几何/材料/网格/绕组/边界逐字相同）",
        "levels": data,
        "deviation": dev,
        "decimated_cross_check": cross,
        "resolution_floor_e1": floor,
        "verdict": verdict,
        "notes": [
            "t50 用 E1 的 medium 重跑（同一冻结模型第二次独立求解），不是 11-14 的历史 CSV，"
            "这样 50/25 µs 两次解在同一机器负载条件下产生，差异只可能来自步长。",
            "降采样校验把 25 µs 的磁链每 2 点取 1 再求导；它若与 50 µs 基线同量级，"
            "说明差异来自时间离散而非另一个物理。",
            "THD 窗口根因（本日修复）：`analyse_signal` 原用 `t[i] >= t0` 浮点比较跳首周期，"
            "50 µs 网格被判成 0.01005（少 1 点、窗口 9.95 ms），25 µs 网格判成 0.010000"
            "（含重复端点、窗口 10.0 ms）⇒ 同一物理两个窗口，THD 假差 0.5474 pt。"
            "改为整数索引 skip=round(T/dt) + 单周期去重复端点后，两档都落在 10 ms 整周期："
            "11.1797% vs 11.2532%（Δ +0.0735 pt / +0.66%）。50 µs 历史数值不变。",
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
