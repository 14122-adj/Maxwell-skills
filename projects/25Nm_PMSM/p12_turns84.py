# -*- coding: utf-8 -*-
"""P12 —— 匝数旋钮（80→84 匝，即 40→42 导体/槽边）对斜槽设计点的复核。

为什么这是**单变量**
--------------------
`gen_maxwell_model.py --conductors-per-slot 42` 只改 Maxwell 的 `Conductor number`
（12 个槽边各一行，共 12 行）；几何/材料/网格/边界/激励逐字不变。脚本启动时用
`assert_single_variable()` 复核这条断言，防止「顺手改了别的」被当成匝数效应。

判据（`docs/ENGINEERING_ACCEPTANCE.md` + 账本 P12）
---------------------------------------------------
| 量 | 判据 |
|---|---|
| 相 BEMF RMS | 118–145 V（±10% 窗） |
| 线 BEMF THD | ≤10%（目标 ≤8%） |
| 齿槽峰峰值 | ≤1.25 N·m 且 ≤5% |
| `T_avg` | 25±20% |
| 转矩脉动 | ≤15%（目标 ≤10%） |

**不许拿解析填 FEA 空缺**：线性模型下 BEMF/转矩理论上严格按 42/40=1.05 缩放，
本文件的 `linear_prediction` 只作为**交叉校验**（gap 越小越说明"只改了匝数"），
设计值一律取 FEA 后处理值；两者并列打印，不互相替代。

用法
----
    python p12_turns84.py            # 读 fea/skew_scan_summary.json + fea/n84_skew_summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from skew_multislice import T_ELEC, read_two_col, trapezoid_mean  # noqa: E402

FEA = os.path.normpath(os.path.join(HERE, "..", "results", "fea"))

DESIGN_SKEW = 0.5                 # 推荐设计点：0.5 槽距
RATIO_EXPECTED = 42.0 / 40.0      # 匝数比 = 导体数比（线性模型）
BEMF_WINDOW = (118.0, 145.0)
LEVEL_KEYS = ("bemf_phase_rms_v", "cogging_pp_nm", "cogging_pct",
              "thd_line_pct", "T_avg_nm", "T_ripple_pct")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def row_at(rows: list, skew: float) -> dict:
    for r in rows:
        if abs(float(r.get("skew_slot_pitch", -1)) - skew) < 1e-9:
            return r
    raise KeyError("找不到 skew=%s 的行" % skew)


def criteria(row: dict) -> dict:
    """按工程判据逐项判 PASS/FAIL（不做"基本通过"这种模糊结论）。"""
    bemf = float(row.get("bemf_phase_rms_v", 0.0))
    thd = float(row.get("thd_line_pct", 999.0))
    cog = float(row.get("cogging_pp_nm", 999.0))
    cog_pct = float(row.get("cogging_pct", 999.0))
    t_avg = float(row.get("T_avg_nm", 0.0))
    ripple = float(row.get("T_ripple_pct", 999.0))
    return {
        "bemf_118_145": {"value": bemf, "pass": BEMF_WINDOW[0] <= bemf <= BEMF_WINDOW[1]},
        "thd_le_10": {"value": thd, "pass": thd <= 10.0},
        "cogging_le_1p25": {"value": cog, "pass": cog <= 1.25},
        "cogging_le_5pct": {"value": cog_pct, "pass": cog_pct <= 5.0},
        "t_avg_25_pm20": {"value": t_avg, "pass": 0.8 * 25.0 <= t_avg <= 1.2 * 25.0},
        "ripple_le_15": {"value": ripple, "pass": ripple <= 15.0},
    }


def all_pass(c: dict) -> bool:
    return all(v["pass"] for v in c.values())


def load_mean(path: str) -> float | None:
    """直接对负载转矩 CSV 的**末电周期**做梯形平均（与合成法互为独立通道）。"""
    t, y = read_two_col(path)
    if not t:
        return None
    idx = [i for i in range(len(t)) if t[i] >= t[-1] - T_ELEC - 1e-12]
    return round(trapezoid_mean([t[i] for i in idx], [y[i] for i in idx]), 5)


def assert_single_variable(base_model: str, new_model: str) -> dict:
    """生成物 diff 只允许 12 行 `Conductor number` 变化（40→42）。"""
    with open(base_model, encoding="utf-8") as fh:
        a = fh.read().splitlines()
    with open(new_model, encoding="utf-8") as fh:
        b = fh.read().splitlines()
    if len(a) != len(b):
        raise SystemExit("行数不同（%d vs %d）：不是单变量改动" % (len(a), len(b)))
    changed = [(x, y) for x, y in zip(a, b) if x != y]
    bad = [(x, y) for x, y in changed if "Conductor number:=" not in x]
    if bad or len(changed) != 12:
        raise SystemExit("diff 不是「12 行 Conductor number」（实际 %d 行，非匝数 %d 行）"
                         % (len(changed), len(bad)))
    if not all('"40"' in x and '"42"' in y for x, y in changed):
        raise SystemExit("Conductor number 不是 40→42")
    return {"changed_lines": len(changed), "only_conductor_number": True}


def compare(base: dict, new: dict) -> dict:
    """逐水平对照 + 线性预测（只作交叉校验）。"""
    out = {"levels": []}
    for rb in base["rows"]:
        s = float(rb["skew_slot_pitch"])
        try:
            rn = row_at(new["rows"], s)
        except KeyError:
            continue
        row = {"skew_slot_pitch": s,
               "base": {k: rb.get(k) for k in LEVEL_KEYS},
               "n84": {k: rn.get(k) for k in LEVEL_KEYS},
               "expected_linear": {k: round(float(rb[k]) * RATIO_EXPECTED, 5)
                                   for k in ("bemf_phase_rms_v", "T_avg_nm")},
               "ratio": {k: round(float(rn[k]) / float(rb[k]), 5)
                         for k in ("bemf_phase_rms_v", "T_avg_nm") if float(rb[k])},
               "delta": {"thd_pt": round(float(rn["thd_line_pct"]) - float(rb["thd_line_pct"]), 4),
                         "cogging_nm": round(float(rn["cogging_pp_nm"]) - float(rb["cogging_pp_nm"]), 5)},
               "criteria": criteria(rn)}
        row["verdict"] = "PASS" if all_pass(row["criteria"]) else "FAIL"
        out["levels"].append(row)
    d = next((r for r in out["levels"] if abs(r["skew_slot_pitch"] - DESIGN_SKEW) < 1e-9), None)
    out["design_point"] = d
    out["verdict"] = (d or {}).get("verdict", "NO_DESIGN_POINT")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=os.path.join(FEA, "skew_scan_summary.json"),
                    help="基线（cps=40）斜槽汇总")
    ap.add_argument("--n84", default=os.path.join(FEA, "n84_skew_summary.json"),
                    help="84 匝（cps=42）斜槽汇总")
    ap.add_argument("--json", default=os.path.join(FEA, "p12_turns84_summary.json"))
    ap.add_argument("--load-base", default=r"D:/ANSYS_Run/csv_tpl_load/tq_load.csv")
    ap.add_argument("--load-n84", default=r"D:/ANSYS_Run/csv_tpl_load_n84/tq_load.csv")
    ap.add_argument("--skip-diff", action="store_true", help="跳过生成物 diff 断言")
    args = ap.parse_args(argv)

    base = load_json(args.base)
    new = load_json(args.n84)
    diff = None
    if not args.skip_diff:
        diff = assert_single_variable(
            os.path.join(HERE, "maxwell_model", "build_25Nm_SPMSM.py"),
            os.path.join(HERE, "maxwell_model_n84", "build_25Nm_SPMSM.py"))
        print("单变量断言：%s" % json.dumps(diff, ensure_ascii=False))

    cmp = compare(base, new)
    load_fea = {}
    for tag, path in (("base", args.load_base), ("n84", args.load_n84)):
        m = load_mean(path)
        if m is not None:
            load_fea[tag] = m
    if len(load_fea) == 2 and load_fea["base"]:
        load_fea["ratio"] = round(load_fea["n84"] / load_fea["base"], 5)
        load_fea["expected"] = round(load_fea["base"] * RATIO_EXPECTED, 5)
        load_fea["gap_vs_expected_pct"] = round(
            100.0 * (load_fea["n84"] - load_fea["expected"]) / load_fea["expected"], 4)
        print("负载 FEA 末周期平均：基线 %.4f → n84 %.4f（比 %.5f，线性预测 %.4f）"
              % (load_fea["base"], load_fea["n84"], load_fea["ratio"], load_fea["expected"]))
    for r in cmp["levels"]:
        print("skew=%.2f  基线 BEMF %.4f / T_avg %.4f / THD %.4f / 齿槽 %.5f  →  "
              "n84 BEMF %.4f / T_avg %.4f / THD %.4f / 齿槽 %.5f  ⇒ %s"
              % (r["skew_slot_pitch"], r["base"]["bemf_phase_rms_v"], r["base"]["T_avg_nm"],
                 r["base"]["thd_line_pct"], r["base"]["cogging_pp_nm"],
                 r["n84"]["bemf_phase_rms_v"], r["n84"]["T_avg_nm"],
                 r["n84"]["thd_line_pct"], r["n84"]["cogging_pp_nm"], r["verdict"]))
    d = cmp.get("design_point") or {}
    print("设计点 skew=%.1f：%s" % (DESIGN_SKEW, cmp["verdict"]))
    if d:
        for k, v in d["criteria"].items():
            print("  %-18s %10.4f  %s" % (k, v["value"], "PASS" if v["pass"] else "FAIL"))

    payload = {
        "stage": "P12 turns 80→84 (cps 40→42) on skewed design point",
        "single_variable": diff,
        "n_turns_per_phase": 84,
        "conductors_per_slot": 42,
        "ratio_expected": round(RATIO_EXPECTED, 5),
        "n84_identity_check": new.get("identity_check"),
        "n84_composition_checks": {str(r["skew_slot_pitch"]): r.get("composition_check")
                                   for r in new["rows"] if r.get("composition_check")},
        "design_point_skew_slot_pitch": DESIGN_SKEW,
        "verdict": cmp["verdict"],
        "load_fea_last_period": load_fea,
        "levels": cmp["levels"],
    }
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print("写出 " + args.json)
    return 0 if cmp["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
