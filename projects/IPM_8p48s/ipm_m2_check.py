#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M2' —— 401 点空载后处理与判定（BEMF / THD / 齿槽 / 磁密）

判据（`docs/ENGINEERING_ACCEPTANCE.md` §2，与 SPM baseline 同一套）
--------------------------------------------------------------
* 相 BEMF RMS ∈ **118–145 V**
* **线** BEMF THD ≤ **10%**（不是相 THD：60° 相带的 k_w3=0.5 在三相线电压里才抵消）
* 齿槽峰峰值 ≤ **5% × 25 N·m = 1.25 N·m**
* 三相不平衡 ≤ 2%
* Bg 0.70–0.90 T / B_tooth ≤1.65 T / B_yoke ≤1.50 T（磁密三行，G4 口径）

为什么单独一个脚本
------------------
FEA 出的 CSV 只是原料。判定必须由**独立脚本**从磁链 CSV 重算（`ENGINEERING_ACCEPTANCE`
§3「独立重算」），不能拿 AEDT 报表里的数直接当结论。本脚本只读 CSV + JSON，
不碰 AEDT，可离线复算。

输入
----
`D:/ANSYS_Run/csv_ipm_m2/`：
    flux_{a,b,c}.csv   FluxLinkage(WindingX) [Wb]，401 行
    tq_noload.csv      Moving1.Torque，401 行
    gap_mag.csv / gap_bx.csv / gap_by.csv   气隙弧 r=46.3025 mm，0→45°，181 点
    tooth_mag.csv      齿中心径向线 r=48.0→57.0 mm，46 点
    yoke_mag.csv       轭部弧 r=60.0 mm，0→45°，91 点

输出
----
`projects/results/ipm8p48s/m2_noload.json`，并回填 I3（匝数）与 I8（气隙磁密）。

用法
----
    python ipm_m2_check.py
    python ipm_m2_check.py --csvdir D:/ANSYS_Run/csv_ipm_m2 --json out.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_Spm = os.path.join(_ROOT, "projects", "25Nm_PMSM")
for _p in (_HERE, _Spm):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ingest_fea as ing  # noqa: E402
import ipm_geom  # noqa: E402

RESULTS = os.path.abspath(os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
RUNDIR = r"D:/ANSYS_Run"
CSVDIR = RUNDIR + "/csv_ipm_m2"
LOG = RUNDIR + "/ipm_m2.log"

# 判据（与 SPM 冻结基线同源，不得为新项目放宽）
BEMF_RANGE = (118.0, 145.0)
THD_MAX = 10.0
COGGING_MAX_PCT = 5.0
IMBALANCE_MAX = 2.0
TORQUE_RATED = 25.0
BG_RANGE = (0.70, 0.90)
B_TOOTH_MAX = 1.65
B_YOKE_MAX = 1.50

F_ELEC = 100.0
SLOTS = 48
POLES = 8
STACK_MM = 160.0
CPS_MODEL = 10             # I3 定源（2026-11-24）：cps=5 实测 63.8721 V → 125 V 反推 10
COILS_PER_PHASE = 16       # I2 定源：每相 16 线圈

# 转矩单位换算（2026-11-22 踩坑）：AEDT 2021.1 的 `Moving1.Torque` 在本工程导出的是
# **[uNewtonMeter]（微牛·米）**，不是 SPM 模板路径的 `mNewtonMeter`。只认 mN·m 会把
# 195 µN·m 读成 195 N·m，齿槽判定直接虚报 780% —— 与 E1 那次 ×1000 同源。
TORQUE_SCALE = {
    "newtonmeter": 1.0,
    "mnewtonmeter": 1e-3,
    "unewtonmeter": 1e-6,
    "µnewtonmeter": 1e-6,
    "kilonewtonmeter": 1e3,
}


# ──────────────────────────────────────────────────────────────────
#  文件读取
# ──────────────────────────────────────────────────────────────────
_DATA_RE = re.compile(r"^\s*[-+]?\d")


def read_calc_csv(path: str):
    """读 Fields Calculator 导出 → [(x_mm, y_mm, B_T)]；首行是 `Scalar data "..."`。"""
    pts = []
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                x, y, _z, b = (float(p) for p in parts[:4])
            except ValueError:
                continue
            if b != b:      # NaN
                continue
            pts.append((x * 1000.0, y * 1000.0, b))
    return pts


def read_calc_pair(dirpath: str, tag_x: str, tag_y: str):
    """读 Bx / By 并按坐标反算极角 → [(angle_deg, Br, Bt)]。"""
    bx = read_calc_csv(os.path.join(dirpath, tag_x + ".csv"))
    by = read_calc_csv(os.path.join(dirpath, tag_y + ".csv"))
    n = min(len(bx), len(by))
    rows = []
    for i in range(n):
        x, y, bxc = bx[i]
        _x, _y, byc = by[i]
        if math.hypot(x, y) <= 0.0:
            continue
        th = math.atan2(y, x)
        rows.append((math.degrees(th),
                     bxc * math.cos(th) + byc * math.sin(th),
                     -bxc * math.sin(th) + byc * math.cos(th)))
    return rows


# ──────────────────────────────────────────────────────────────────
#  统计
# ──────────────────────────────────────────────────────────────────
def tail_after_first_period(t, y):
    """丢掉第一个电周期（启动暂态），返回 (t, y)。整数索引，不用浮点比较。"""
    if len(t) < 8:
        return t, y
    diffs = sorted(t[i + 1] - t[i] for i in range(min(len(t) - 1, 50)))
    dt = diffs[len(diffs) // 2] if diffs else 0.0
    n_skip = int(round((1.0 / F_ELEC) / dt)) if dt > 0 else 0
    if n_skip > 0 and len(t) - n_skip > 10:
        return t[n_skip:], y[n_skip:]
    return t, y


def pp_ct(t, y):
    """峰峰值 + 均值 / 脉动率（脉动按 |mean| 归一；mean≈0 时返回 None）。"""
    tt, yy = tail_after_first_period(t, list(y))
    mx, mn = max(yy), min(yy)
    mean = sum(yy) / len(yy)
    rip = (100.0 * (mx - mn) / abs(mean)) if abs(mean) > 1e-9 else None
    return {"pp": mx - mn, "max": mx, "min": mn, "mean": mean,
            "ripple_pct": rip, "n": len(yy)}


def torque_scale(unit: str) -> float:
    """按表头单位返回转矩换算系数；未知单位按 N·m 处理并保持原样。"""
    return TORQUE_SCALE.get((unit or "").strip().lower().replace(" ", ""), 1.0)


def log_analyze_seconds(path: str):
    """从求解日志取 ANALYZE_OK 秒数与对象计数（I7 的耗时证据）。"""
    out = {"analyze_s": None, "sheets": None, "prefix": None, "setups": None,
           "motions": None, "lines": []}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            s = line.strip()
            out["lines"].append(s)
            m = re.match(r"ANALYZE_OK\s+([\d.]+)s", s)
            if m:
                out["analyze_s"] = float(m.group(1))
            m = re.match(r"SHEETS=(\d+)", s)
            if m:
                out["sheets"] = int(m.group(1))
            m = re.match(r"PREFIX\s+(.*)$", s)
            if m:
                out["prefix"] = m.group(1)
            m = re.match(r"SETUPS=(.*)$", s)
            if m:
                out["setups"] = m.group(1)
            m = re.match(r"MOTIONS=(.*)$", s)
            if m:
                out["motions"] = m.group(1)
    return out


# ──────────────────────────────────────────────────────────────────
#  磁密
# ──────────────────────────────────────────────────────────────────
def gap_block(csvdir: str, cfg):
    """气隙：|B| 弧峰 + 径向分量三口径（极轴 |Br| / |Br| 峰 / |B| 峰）。"""
    r_gap, _tooth_deg, _lo, _hi, _yoke_r = (None, None, None, None, None)
    mag = read_calc_csv(os.path.join(csvdir, "gap_mag.csv"))
    if not mag:
        return None
    res = {"n_points": len(mag)}
    peak = max(mag, key=lambda p: p[2])
    res["b_max"] = peak[2]
    res["angle_at_peak_deg"] = math.degrees(math.atan2(peak[1], peak[0]))
    res["r_at_peak_mm"] = math.hypot(peak[0], peak[1])
    res["b_min"] = min(p[2] for p in mag)

    pair_x = os.path.join(csvdir, "gap_bx.csv")
    pair_y = os.path.join(csvdir, "gap_by.csv")
    if os.path.exists(pair_x) and os.path.exists(pair_y):
        rows = read_calc_pair(csvdir, "gap_bx", "gap_by")
        if rows:
            br_pk = max(rows, key=lambda r: abs(r[1]))
            bt_pk = max(rows, key=lambda r: abs(r[2]))
            # 极轴：8 极 ⇒ 极轴在 45° 的整数倍；一个极距内即 0°
            axis = min(rows, key=lambda r: abs(r[0]))
            res["Br_max"] = abs(br_pk[1])
            res["Br_max_angle_deg"] = br_pk[0]
            res["Bt_max"] = abs(bt_pk[2])
            res["Bt_max_angle_deg"] = bt_pk[0]
            res["Br_at_pole_axis"] = abs(axis[1])
            # 一个槽距（7.5°）内的气隙平均磁密 —— 磁通连续性用
            win = [r for r in rows if -0.2 <= r[0] <= 7.5 + 0.2]
            if win:
                res["Br_mean_one_slot_pitch"] = (
                    sum(abs(r[1]) for r in win) / len(win))
    res["verdict"] = ("PASS" if BG_RANGE[0] <= res["b_max"] <= BG_RANGE[1]
                      else "FAIL")
    return res


def tooth_block(csvdir: str, cfg):
    pts = read_calc_csv(os.path.join(csvdir, "tooth_mag.csv"))
    if not pts:
        return None
    rows = [(math.hypot(x, y), b) for (x, y, b) in pts]
    peak = max(rows, key=lambda r: r[1])
    # 齿身最窄处半径（I1 定源：Bs2 所在半径 = R_bore + Hs0 + Hs1 + ... ）
    return {"n_points": len(rows), "b_max": peak[1], "r_at_peak_mm": peak[0],
            "r_span_mm": [min(r[0] for r in rows), max(r[0] for r in rows)],
            "verdict": "PASS" if peak[1] <= B_TOOTH_MAX else "FAIL"}


def yoke_block(csvdir: str, cfg):
    pts = read_calc_csv(os.path.join(csvdir, "yoke_mag.csv"))
    if not pts:
        return None
    peak = max(pts, key=lambda p: p[2])
    return {"n_points": len(pts), "b_max": peak[2],
            "angle_at_peak_deg": math.degrees(math.atan2(peak[1], peak[0])),
            "r_mm": math.hypot(peak[0], peak[1]),
            "verdict": "PASS" if peak[2] <= B_YOKE_MAX else "FAIL"}


# ──────────────────────────────────────────────────────────────────
#  反电势
# ──────────────────────────────────────────────────────────────────
def bemf_block(csvdir: str):
    phases = {}
    src = {}
    for ph in ("a", "b", "c"):
        got = ing.load_phase_bemf(csvdir, ph)
        if got is None:
            raise FileNotFoundError("缺 flux_%s.csv 的磁链列" % ph)
        t, e, how = got
        phases[ph.upper()] = (t, e)
        src[ph.upper()] = how

    out = {"sources": src, "phase": {}, "line": {}}
    rms = {}
    for ph, (t, e) in phases.items():
        st = ing.analyse_signal(t, e)
        rms[ph] = st["rms"]
        out["phase"][ph] = {"rms": st["rms"], "peak": st["peak"],
                            "thd_pct": st["thd_pct"], "n_samples": st["n_samples"]}
    mean_rms = sum(rms.values()) / len(rms)
    imb = 100.0 * (max(rms.values()) - min(rms.values())) / mean_rms
    out["phase_rms_mean"] = mean_rms
    out["imbalance_pct"] = imb

    for name, (p1, p2) in (("AB", ("A", "B")), ("BC", ("B", "C")), ("CA", ("C", "A"))):
        ll = ing.line_to_line(phases, p1, p2)
        if ll is None:
            continue
        t, u = ll
        st = ing.analyse_signal(t, u)
        out["line"][name] = {"rms": st["rms"], "peak": st["peak"],
                             "thd_pct": st["thd_pct"], "n_samples": st["n_samples"]}
    thds = [v["thd_pct"] for v in out["line"].values()]
    out["line_thd_max"] = max(thds) if thds else None
    return out


def turns_backcalc(bemf_rms: float, cps_model: int = CPS_MODEL):
    """由实测 BEMF 反推每槽导体数（N_ph = 16·cps，cps 必须整数）。

    BEMF ∝ N_ph，线性反推；给出「落 118 V 下限」与「落 125 V 设计点」两个口径。
    """
    n_ph = COILS_PER_PHASE * cps_model
    per_turn = bemf_rms / n_ph
    out = {"cps_model": cps_model, "turns_per_phase_model": n_ph,
           "bemf_per_turn_v": per_turn, "targets": {}}
    for label, target in (("lower_118V", BEMF_RANGE[0]),
                          ("design_125V", 125.0),
                          ("upper_145V", BEMF_RANGE[1])):
        cps_req = target / (per_turn * COILS_PER_PHASE)
        out["targets"][label] = {
            "target_v": target,
            "cps_exact": cps_req,
            "cps_int": int(round(cps_req)),
            "turns_int": int(round(cps_req)) * COILS_PER_PHASE,
            "bemf_at_int_v": per_turn * COILS_PER_PHASE * int(round(cps_req)),
        }
    return out


def analytic_crosscheck(bemf: dict, gap: dict, cfg, cps: int = CPS_MODEL):
    """解析 BEMF 交叉校验：E = √2·π·f·N_ph·k_w1·φ_1，φ_1 由**实测** Bg 推。

    只作交叉校验（口径彼此独立：一条走 FEA 磁链求导，一条走气隙磁密积分），
    不填任何 FEA 空缺。
    """
    if not gap or "Br_max" not in gap:
        return None
    kw1 = 0.933013
    tau_p = math.pi * cfg.stator_id / cfg.poles            # mm
    bg = gap["Br_max"]
    phi1 = (2.0 / math.pi) * bg * (tau_p * 1e-3) * (cfg.stack_length * 1e-3)
    n_ph = COILS_PER_PHASE * cps
    e = math.sqrt(2.0) * math.pi * F_ELEC * n_ph * kw1 * phi1
    return {"bg_used_T": bg, "phi1_Wb": phi1, "kw1": kw1, "n_ph": n_ph,
            "e_analytic_v": e,
            "delta_pct": (100.0 * (bemf["phase_rms_mean"] - e) / e)}


# ──────────────────────────────────────────────────────────────────
#  主流程
# ──────────────────────────────────────────────────────────────────
def analyse(csvdir: str = CSVDIR, log_path: str = LOG) -> dict:
    cfg = ipm_geom.IPMConfig()
    bemf = bemf_block(csvdir)
    tq_path = os.path.join(csvdir, "tq_noload.csv")
    t, cols = ing.load_maxwell_csv(tq_path)
    umap = ing._units_by_column(tq_path)
    key = None
    for k in cols:
        u = (umap.get(k, "") or "").lower().replace(" ", "")
        if "torque" in k.lower() or u in ("newtonmeter", "mnewtonmeter"):
            key = k
            break
    if key is None:
        key = list(cols)[0]
    scale = torque_scale(umap.get(key, ""))
    tq = [v * scale for v in cols[key]]
    tq_st = pp_ct(t, tq)

    gap = gap_block(csvdir, cfg)
    tooth = tooth_block(csvdir, cfg)
    yoke = yoke_block(csvdir, cfg)
    ana = analytic_crosscheck(bemf, gap, cfg)
    turns = turns_backcalc(bemf["phase_rms_mean"])

    cog_pct = 100.0 * tq_st["pp"] / TORQUE_RATED
    checks = [
        {"name": "相 BEMF RMS ∈ 118–145 V",
         "value": bemf["phase_rms_mean"], "limit": list(BEMF_RANGE), "op": "in",
         "status": "PASS" if BEMF_RANGE[0] <= bemf["phase_rms_mean"] <= BEMF_RANGE[1]
         else "FAIL"},
        {"name": "线 BEMF THD ≤ 10%",
         "value": bemf["line_thd_max"], "limit": THD_MAX, "op": "<=",
         "status": "PASS" if bemf["line_thd_max"] is not None
         and bemf["line_thd_max"] <= THD_MAX else "FAIL"},
        {"name": "齿槽峰峰值 ≤ 5% (1.25 N·m)",
         "value": tq_st["pp"], "limit": COGGING_MAX_PCT, "op": "<=",
         "status": "PASS" if cog_pct <= COGGING_MAX_PCT else "FAIL"},
        {"name": "三相不平衡 ≤ 2%",
         "value": bemf["imbalance_pct"], "limit": IMBALANCE_MAX, "op": "<=",
         "status": "PASS" if bemf["imbalance_pct"] <= IMBALANCE_MAX else "FAIL"},
    ]
    if gap:
        checks.append({"name": "Bg ∈ 0.70–0.90 T", "value": gap["b_max"],
                       "limit": list(BG_RANGE), "op": "in", "status": gap["verdict"]})
    if tooth:
        checks.append({"name": "B_tooth ≤ 1.65 T", "value": tooth["b_max"],
                       "limit": B_TOOTH_MAX, "op": "<=", "status": tooth["verdict"]})
    if yoke:
        checks.append({"name": "B_yoke ≤ 1.50 T", "value": yoke["b_max"],
                       "limit": B_YOKE_MAX, "op": "<=", "status": yoke["verdict"]})

    info = log_analyze_seconds(log_path)
    return {
        "stage": "M2' 401 点空载（8p48s / 双层绕组 / 16 块单层 V / 无斜槽）",
        "cps_temp": CPS_MODEL,
        "bemf": bemf,
        "torque": {"pp_nm": tq_st["pp"], "max": tq_st["max"], "min": tq_st["min"],
                   "mean": tq_st["mean"], "cogging_pct": cog_pct,
                   "window_samples": tq_st["n"]},
        "flux_density": {"gap": gap, "tooth": tooth, "yoke": yoke},
        "analytic_crosscheck": ana,
        "turns_backcalc": turns,
        "solve": {"analyze_s": info["analyze_s"], "sheets": info["sheets"],
                  "prefix": info["prefix"], "setups": info["setups"],
                  "motions": info["motions"]},
        "checks": checks,
        "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M2' 空载后处理")
    ap.add_argument("--csvdir", default=CSVDIR)
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--json", default=os.path.join(RESULTS, "m2_noload.json"))
    args = ap.parse_args(argv)

    res = analyse(args.csvdir, args.log)
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)

    b, tq, fd = res["bemf"], res["torque"], res["flux_density"]
    print("=" * 76)
    print("IPM 8p48s M2' 空载（401 点，cps=%d 即 %d 匝/相）"
          % (CPS_MODEL, CPS_MODEL * COILS_PER_PHASE))
    print("=" * 76)
    print("  相 BEMF RMS   A %.4f / B %.4f / C %.4f V（均值 %.4f，判据 118–145）"
          % (b["phase"]["A"]["rms"], b["phase"]["B"]["rms"], b["phase"]["C"]["rms"],
             b["phase_rms_mean"]))
    if b["line"]:
        print("  线 BEMF RMS   %s V；THD 最大 %.4f%%（判据 ≤10%%）"
              % (" / ".join("%s %.4f" % (k, v["rms"]) for k, v in sorted(b["line"].items())),
                 b["line_thd_max"]))
    print("  三相不平衡    %.4f%%（判据 ≤2%%）" % b["imbalance_pct"])
    print("  齿槽          %.4f N·m = %.4f%% 额定（判据 ≤5%%）"
          % (tq["pp_nm"], tq["cogging_pct"]))
    if fd["gap"]:
        print("  气隙 |B|峰    %.4f T @ %.2f°"
              % (fd["gap"]["b_max"], fd["gap"]["angle_at_peak_deg"]))
        if "Br_max" in fd["gap"]:
            print("  气隙 |Br|峰   %.4f T @ %.2f°；极轴 %.4f T"
                  % (fd["gap"]["Br_max"], fd["gap"]["Br_max_angle_deg"],
                     fd["gap"]["Br_at_pole_axis"]))
    if fd["tooth"]:
        print("  齿身 B 峰     %.4f T @ r=%.2f mm（判据 ≤1.65）"
              % (fd["tooth"]["b_max"], fd["tooth"]["r_at_peak_mm"]))
    if fd["yoke"]:
        print("  轭部 B 峰     %.4f T（判据 ≤1.50）" % fd["yoke"]["b_max"])
    if res["analytic_crosscheck"]:
        a = res["analytic_crosscheck"]
        print("  解析交叉      E=%.4f V（φ1=%.5f Wb，Bg=%.4f T）差 %+.2f%%"
              % (a["e_analytic_v"], a["phi1_Wb"], a["bg_used_T"], a["delta_pct"]))
    tb = res["turns_backcalc"]
    print("  匝数反推      cps=%d 时 %.4f V/匝/相；118V→cps=%d（%d 匝）/ 125V→cps=%d（%d 匝）"
          % (tb["cps_model"], tb["bemf_per_turn_v"],
             tb["targets"]["lower_118V"]["cps_int"],
             tb["targets"]["lower_118V"]["turns_int"],
             tb["targets"]["design_125V"]["cps_int"],
             tb["targets"]["design_125V"]["turns_int"]))
    print("  求解耗时      %s s；SHEETS=%s" % (res["solve"]["analyze_s"],
                                              res["solve"]["sheets"]))
    print("  " + "-" * 72)
    for c in res["checks"]:
        print("   [%s] %-34s %10.4f" % (c["status"], c["name"], c["value"]))
    print("  总判定：%s    JSON: %s" % (res["status"], args.json))
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
