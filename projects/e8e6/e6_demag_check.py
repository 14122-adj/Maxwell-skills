#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E6 150°C 三相短路退磁真机 FEA —— 宿主侧编排 + 后处理 + 判据。

设计原则（继承 docs/ENGINEERING_ACCEPTANCE.md §4 反自演规则）
---------------------------------------------------------------
1. 真机数据才写 source="FEA"；解析只作对照，不填 FEA 空缺。
2. 401 点全时长（10 ms / 25 µs）；5 点试算只判能解，不取数。
3. 判据走 e8e6_bridge.E8E6Bridge(dry_run=False).check_demag，阈值不在此脚本里改。
4. FAIL 不删数据：verdict 与 b_min/sf 原值一并写 JSON 与账本。
5. 温度系数是 assumption=待验证（N35 常见值外推），不是厂家数据。

温度外推（20°C → 150°C，ΔT=130 K）
----------------------------------
    Br(150) = Br(20) · [1 + (-0.0012)·130] = Br(20)·0.844
    Hc(150) = Hc(20) · [1 + (-0.006)·130]  = Hc(20)·0.220
    Maxwell 线性退磁模型 Br = μ0·μr·|Hc|，故 μr(150) 随之重算以保持 Br(150)。

短路工况
--------
三相 WindingGroup Type="Voltage" / Voltage="0V" + R=0.48 Ω / L=0.0038 H，
电流由感应电压与绕组阻抗决定。R/L 取 pmsm_config 设计值与解析退磁 design_Ls
口径一致；端部电感全部计入是 assumption=待验证（2D 场已含槽内电感）。

B_min 口径
----------
气隙 r=46.1625 mm、0→360° 121 点、多时刻 Bx/By → Br=Bx·cosθ+By·sinθ。
每个时刻取极下峰值 max_θ|Br|，全时程取最小：
    B_min = min_t [ max_θ |Br(t,θ)| ]
避免把 q 轴（极间）本来就接近 0 的磁密误判为退磁。

SF 口径（主判据）
-----------------
SF = B_min / 0.20 T（与账本解析 SF=B_min/0.2 同源，对应验算下限）。
交叉校验 SF_Hc = |Hc(150)| / H_demag,max（矫顽力对去磁场强裕度），
H_demag 由 FEA 短路电流峰值反算，沿用解析公式。

用法
----
    python e6_demag_check.py gen --trial      # 生成试算脚本（5 点）
    python e6_demag_check.py gen --full       # 生成全解脚本（401 点）
    python e6_demag_check.py check            # 解析已跑结果 → e6_fea.json
    python e6_demag_check.py extrap           # 只打印温度外推（不跑 FEA）
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PROJ = os.path.join(ROOT, "projects", "25Nm_PMSM")
sys.path.insert(0, os.path.join(PROJ, "maxwell_model"))
sys.path.insert(0, HERE)

from prepare_batch import to_batch_script  # noqa: E402
from e8e6_bridge import E8E6Bridge  # noqa: E402

ANSYS_EXE = r"D:/Program Files/AnsysEM/AnsysEM21.1/Win64/ansysedt.exe"
RUNDIR = r"D:/ANSYS_Run"
MODEL_OUT = RUNDIR + "/e6_model"
BODY = RUNDIR + "/e6_body.py"
SOLVER_TMPL = os.path.join(HERE, "e6_demag_solver.py")
OUTDIR = RUNDIR + "/e6_demag_out"
RESULT_JSON = os.path.join(ROOT, "projects", "results", "e8e6", "e6_fea.json")

MU0 = 4.0 * math.pi * 1e-7
# 20°C 磁钢（与 maxwell_model/materials.py 冻结值一致）
MUR_20 = 1.0997785406
HC_20 = 890000.0
T_REF_C = 20.0
T_DEMAG_C = 150.0
A_BR_PER_K = -0.0012      # assumption=待验证：N35 常见 Br 温度系数
A_HC_PER_K = -0.006       # assumption=待验证：N35 常见 Hc 温度系数
# 短路阻抗（pmsm_config 设计值 / 解析退磁 design_Ls 口径）
R_PHASE_OHM = 0.48
L_PHASE_H = 0.0038
F_ELEC_HZ = 100.0
# 绕组 / 磁路（设计点 cps=42 ⇒ 84 匝/相）
CPS = 42
TURNS_PER_PHASE = 2 * CPS
KW = 0.933
POLES = 8
PM_H_M = 1.95e-3
B_MIN_THRESHOLD_T = 0.20  # 与 bridge E6_BMIN_MIN_T 一致

# 存场时刻（µs）：5 点试算不导场；全解每 10 步存一次场（250 µs），
# 取 2.0–10.0 ms 共 33 个时刻覆盖 1 个电周期。
TIMES_US_FULL = [2000 + 250 * i for i in range(33)]
TIMES_US_TRIAL = [25, 50, 75, 100]


def extrap() -> dict:
    dT = T_DEMAG_C - T_REF_C
    br20 = MU0 * MUR_20 * HC_20
    br150 = br20 * (1.0 + A_BR_PER_K * dT)
    hc150 = HC_20 * (1.0 + A_HC_PER_K * dT)
    mur150 = br150 / (MU0 * hc150)
    return {
        "dT_K": dT,
        "Br20_T": round(br20, 6),
        "Br150_T": round(br150, 6),
        "Hc20_A_per_m": HC_20,
        "Hc150_A_per_m": round(hc150, 2),
        "mur20": MUR_20,
        "mur150": round(mur150, 10),
        "formula_Br": "Br(T) = Br(20C) * (1 + (-0.0012)*(T-20))",
        "formula_Hc": "Hc(T) = Hc(20C) * (1 + (-0.006)*(T-20))",
        "formula_mur": "mur(T) = Br(T) / (mu0 * |Hc(T)|); Br = mu0*mur*|Hc|",
        "assumption": (
            "待验证：Br -0.12%/K、Hc -0.6%/K 为 N35 常见值外推，"
            "非本项目磁钢厂家数据；需采购牌号 datasheet 或 150°C 实测退磁曲线确认。"
        ),
    }


def gen_model() -> list:
    """调 gen_maxwell_model.py 生成 cps=42 设计点到 TEMP 区，返回生成物路径。"""
    cmd = [sys.executable, os.path.join(PROJ, "gen_maxwell_model.py"),
           "--conductors-per-slot", str(CPS), "--out_dir", MODEL_OUT]
    import subprocess
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("gen_maxwell_model failed: " + proc.stdout + proc.stderr)
    build = os.path.join(MODEL_OUT, "build_25Nm_SPMSM.py")
    if not os.path.isfile(build):
        raise RuntimeError("模型生成物缺失: " + build)
    return [build]


def rewrite_body(src: str, ex: dict) -> tuple[str, dict]:
    """清洗生成物并改写 150°C 材料 + 三相短路绕组；返回 (body, 替换计数)。"""
    body = to_batch_script(src)
    cnt = {}
    # ── 材料：Hc 与 μr（两处 N/S 磁钢）──
    old_hc = '"Magnitude:=", "-890000.0A_per_meter"'
    new_hc = '"Magnitude:=", "-%.1fA_per_meter"' % abs(ex["Hc150_A_per_m"])
    cnt["hc"] = body.count(old_hc)
    if cnt["hc"] != 2:
        raise RuntimeError("Hc 替换点应为 2，实际 %d" % cnt["hc"])
    body = body.replace(old_hc, new_hc)
    old_mur = '"permeability:=", "1.0997785406"'
    new_mur = '"permeability:=", "%.10f"' % ex["mur150"]
    cnt["mur"] = body.count(old_mur)
    if cnt["mur"] != 2:
        raise RuntimeError("mur 替换点应为 2，实际 %d" % cnt["mur"])
    body = body.replace(old_mur, new_mur)
    # ── 绕组：Current → Voltage / 0V 短接 + R/L ──
    old_wind = ('"Type:=", "Current",\n'
                '         "IsSolid:=", False,\n'
                '         "Current:=", "0A",\n'
                '         "Resistance:=", "0.1ohm",\n'
                '         "Inductance:=", "0.001H",\n'
                '         "Voltage:=", "0V",')
    new_wind = ('"Type:=", "Voltage",\n'
                '         "IsSolid:=", False,\n'
                '         "Voltage:=", "0V",\n'
                '         "Resistance:=", "%.5fohm",\n'
                '         "Inductance:=", "%.4fH",' % (R_PHASE_OHM, L_PHASE_H))
    cnt["winding"] = body.count(old_wind)
    if cnt["winding"] != 1:
        raise RuntimeError("绕组替换点应为 1，实际 %d" % cnt["winding"])
    body = body.replace(old_wind, new_wind)
    if "ScriptEnv" in body:
        raise RuntimeError("ScriptEnv 未剥离")
    if '"Type:=", "Voltage"' not in body:
        raise RuntimeError("短路绕组未写入")
    if new_hc not in body:
        raise RuntimeError("150°C Hc 未写入")
    return body, cnt


def gen_solver(trial: bool) -> dict:
    ex = extrap()
    if not os.path.isfile(BODY):
        raise RuntimeError("body 未生成: " + BODY)
    tmpl = open(SOLVER_TMPL, encoding="utf-8").read()
    stop = "0.000100s" if trial else "0.010000s"
    nsteps = "0" if trial else "10"
    aedt = RUNDIR + ("/e6_demag_trial.aedt" if trial else "/e6_demag_full.aedt")
    log = RUNDIR + ("/app_e6_demag_trial.log" if trial else "/app_e6_demag_full.log")
    solver = RUNDIR + ("/e6_demag_solver_trial.py" if trial else "/e6_demag_solver_full.py")
    outdir = OUTDIR + ("/trial" if trial else "/full")
    times = TIMES_US_TRIAL if trial else TIMES_US_FULL
    rep = {
        "@@BODY@@": BODY,
        "@@AEDT@@": aedt,
        "@@LOG@@": log,
        "@@OUTDIR@@": outdir,
        "@@STOP@@": stop,
        "@@TRIAL@@": "True" if trial else "False",
        "@@NSTEPS@@": nsteps,
        "@@TIMES_US@@": repr(times),
    }
    for k, v in rep.items():
        if k not in tmpl:
            raise RuntimeError("模板缺占位符 " + k)
        tmpl = tmpl.replace(k, v)
    open(solver, "w", encoding="utf-8", newline="\n").write(tmpl)
    return {"solver": solver, "log": log, "aedt": aedt, "outdir": outdir,
            "stop": stop, "nsteps": nsteps, "n_times": len(times)}


def cmd_gen(args) -> int:
    ex = extrap()
    paths = gen_model()
    src = open(paths[0], encoding="utf-8").read()
    body, cnt = rewrite_body(src, ex)
    open(BODY, "w", encoding="utf-8", newline="\n").write(body)
    info = gen_solver(args.trial)
    print("temperature:", json.dumps(ex, ensure_ascii=False))
    print("rewrite counts:", cnt)
    print("body:", BODY, os.path.getsize(BODY), "B")
    print("solver:", info["solver"], "stop=", info["stop"],
          "nsteps=", info["nsteps"], "n_times=", info["n_times"])
    print("log:", info["log"])
    return 0


def read_csv_matrix(path: str) -> list:
    """Read Time + N numeric columns → list of rows (floats)."""
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            s = ln.strip()
            if not s:
                continue
            parts = s.replace(",", "\t").split("\t")
            try:
                rows.append([float(p) for p in parts])
            except ValueError:
                continue
    return rows


def read_field_csv(path: str) -> list:
    """Fields Calculator 导出：首行 Scalar data，其后 x y z B（米/特斯拉）。"""
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            p = ln.split()
            if len(p) < 4:
                continue
            try:
                x, y, _z, b = (float(v) for v in p[:4])
            except ValueError:
                continue
            if b != b:  # NaN
                continue
            out.append((math.degrees(math.atan2(y, x)), b))
    return out


def read_report_current(path: str, t_unit: str = "ms") -> list:
    """读 Maxwell Report CSV：`Time [ms], Current(WindingX) [A]` → [(t_s, i_A)]。"""
    out = []
    with open(path, encoding="utf-8-sig") as fh:
        for ln in fh:
            s = ln.strip()
            if not s:
                continue
            parts = s.replace(",", "\t").split("\t")
            try:
                t = float(parts[0].strip('"'))
                i = float(parts[1].strip('"'))
            except (ValueError, IndexError):
                continue
            out.append((t * 1e-3 if t_unit == "ms" else t, i))
    return out


def analyse() -> dict:
    ex = extrap()
    full_dir = OUTDIR + "/full"
    if not os.path.isdir(full_dir):
        raise RuntimeError("全解目录不存在: " + full_dir)

    # ── 短路电流：Report 三相 401 点（Current(WindingX)，21.1 正确表达式）──
    # 原生 TrCrv 只保末 10 步（环形缓冲），只能判回路闭合，不能取峰值。
    currents = {}
    for ph in ("A", "B", "C"):
        p = full_dir + "/current_%s.csv" % ph.lower()
        if not os.path.isfile(p):
            raise RuntimeError("短路电流 CSV 缺失: " + p)
        currents[ph] = read_report_current(p, "ms")
        if len(currents[ph]) < 400:
            raise RuntimeError("短路电流不足 401 点: %s (%d)" % (p, len(currents[ph])))
    n_pts = min(len(v) for v in currents.values())
    i_peak = max(abs(i) for ph in ("A", "B", "C") for (_t, i) in currents[ph])
    t_end = currents["A"][-1][0]
    keep_field = os.path.join(ROOT, "projects", "results", "e8e6", "field")
    cur_path = os.path.join(keep_field, "current_a.csv").replace("\\", "/")
    cur_source = ("REPORT Current(WindingX), 3 phases x 401 points; "
                  "native TrCrv (last 10 steps) for circuit-closure check only")
    cur_paths = {
        "A": os.path.join(keep_field, "current_a.csv").replace("\\", "/"),
        "B": os.path.join(keep_field, "current_b.csv").replace("\\", "/"),
        "C": os.path.join(keep_field, "current_c.csv").replace("\\", "/"),
        "native_last10": os.path.join(keep_field, "current_native_last10.csv").replace("\\", "/"),
    }

    # ── 气隙场：多时刻 Bx/By → Br；每时刻极下峰值，全时程取最小 ──
    def _t_us(fn: str, prefix: str) -> int:
        stem = fn[len(prefix):-4]          # e.g. "010000us"
        return int(stem.replace("us", ""))

    bx = {}
    by = {}
    for fn in os.listdir(full_dir + "/field"):
        if not fn.startswith("gap_bx_") or not fn.endswith(".csv"):
            continue
        bx[_t_us(fn, "gap_bx_")] = read_field_csv(full_dir + "/field/" + fn)
    for fn in os.listdir(full_dir + "/field"):
        if not fn.startswith("gap_by_") or not fn.endswith(".csv"):
            continue
        by[_t_us(fn, "gap_by_")] = read_field_csv(full_dir + "/field/" + fn)
    common = sorted(set(bx) & set(by))
    if not common:
        raise RuntimeError("气隙场无 Bx/By 配对数据: " + full_dir + "/field")

    per_time = []
    for t_us in common:
        if len(bx[t_us]) != len(by[t_us]) or not bx[t_us]:
            continue
        vals = []
        for (ang, bxc), (_ang, byc) in zip(bx[t_us], by[t_us]):
            a = math.radians(ang)
            br = bxc * math.cos(a) + byc * math.sin(a)
            vals.append((abs(br), ang, br))
        if not vals:
            continue
        peak = max(vals, key=lambda v: v[0])
        per_time.append({
            "time_us": t_us,
            "peak_abs_br_T": round(peak[0], 6),
            "peak_angle_deg": round(peak[1], 3),
            "br_signed_T": round(peak[2], 6),
            "n_points": len(vals),
        })
    if not per_time:
        raise RuntimeError("气隙场无有效 Br 采样")
    worst = min(per_time, key=lambda d: d["peak_abs_br_T"])
    b_min = worst["peak_abs_br_T"]
    field_limitation = (
        "限制：21.1 的 EditSetup 'N Steps'='10' 被静默忽略（账本 P17），"
        "只有末时刻 t=0.010 s 场可导出，多时刻 66 次导出全失败。"
        "t=0.010 s 恰为 1 个电周期末、转子机械角回 0°，与 G4-B 末时刻快照同口径；"
        "但 B_min 严格性弱于全时程场扫描（无法确认最恶劣去磁相位），"
        "此处如实标注，不把单时刻场冒充全时程最小值。"
    )

    # ── SF ──
    sf_main = b_min / B_MIN_THRESHOLD_T
    omega_e = 2.0 * math.pi * F_ELEC_HZ
    h_demag = TURNS_PER_PHASE * i_peak * KW / (2.0 * POLES * PM_H_M)
    sf_hc = abs(ex["Hc150_A_per_m"]) / h_demag if h_demag > 0 else 0.0
    analytic_bmin = ex["Br150_T"] - MU0 * h_demag

    # ── bridge 判据（阈值不在此改）──
    bridge = E8E6Bridge(dry_run=False)
    verdict = bridge.check_demag(b_min_t=b_min, sf=sf_main,
                                 temperature_c=T_DEMAG_C, source="FEA")
    thermal = bridge.thermal_nodes()

    return {
        "stage": "E6 150°C 三相短路退磁 FEA（真机 Maxwell 2D）",
        "source": "FEA",
        "temperature_c": T_DEMAG_C,
        "solver": {
            "ansys_version": "AnsysEM 21.1",
            "stop_time_s": t_end,
            "time_step_s": 25e-6,
            "n_points": n_pts,
            "full_401_points": n_pts >= 400,
            "trial_points": 5,
            "aedt": RUNDIR + "/e6_demag_full.aedt",
            "log": RUNDIR + "/app_e6_demag_full.log",
        },
        "temperature_extrapolation": ex,
        "short_circuit": {
            "topology": "three-phase short circuit (Voltage=0V, R+L)",
            "winding_type": "Voltage",
            "r_phase_ohm": R_PHASE_OHM,
            "l_phase_h": L_PHASE_H,
            "turns_per_phase": TURNS_PER_PHASE,
            "current_csv": cur_path,
            "current_csv_all_phases": cur_paths,
            "current_source": cur_source,
            "i_sc_peak_a": round(i_peak, 3),
            "h_demag_max_A_per_m": round(h_demag, 2),
            "assumption": (
                "待验证：端部电感按设计相电感 0.0038 H 全额计入；"
                "2D 场已含槽内电感，实际端部电感需按绕组端部几何实测/标定。"
            ),
        },
        "b_min": {
            "value_T": b_min,
            "definition": "min_t [ max_theta |Br(t,theta)| ] on r=46.1625 mm airgap circle",
            "sample": {
                "time_us": worst["time_us"],
                "angle_deg": worst["peak_angle_deg"],
                "radius_mm": 46.1625,
                "br_signed_T": worst["br_signed_T"],
            },
            "n_times": len(per_time),
            "n_points_per_time": per_time[0]["n_points"],
            "per_time_peak": per_time,
            "field_csv_dir": keep_field.replace("\\", "/"),
            "field_csv": {
                "bx": os.path.join(keep_field, "gap_bx_010000us.csv").replace("\\", "/"),
                "by": os.path.join(keep_field, "gap_by_010000us.csv").replace("\\", "/"),
                "points": os.path.join(keep_field, "pts_gap.txt").replace("\\", "/"),
            },
            "field_limitation": field_limitation,
        },
        "safety_factor": {
            "value": round(sf_main, 4),
            "definition": "B_min / 0.20T (same basis as analytic ledger SF=B_min/0.2)",
            "sf_Hc_crosscheck": round(sf_hc, 4),
            "sf_Hc_definition": "|Hc(150C)| / H_demag_max (FEA current driven)",
            "analytic_bmin_reference_T": round(analytic_bmin, 6),
            "note": (
                "解析参考仅作对照，不填 FEA 值；SF_Hc 为独立口径交叉校验，"
                "主判据走 bridge.check_demag(sf=value)。"
            ),
        },
        "demag_verdict": verdict,
        "thermal_crosscheck": {
            "bridge_thermal": thermal,
            "g5_criteria": {
                "winding_hotspot_max_c": 155.0,
                "magnet_max_c": 120.0,
            },
            "note": (
                "E6 FEA 为等温 150°C 工况，未做热-电耦合，未得到磁钢实际工作点温度；"
                "thermal_summary.json 仍为 7 节点 LPTN 解析值(绕组 89.47°C/磁钢 76.06°C，"
                "source=ANALYTIC_LPTN_S4_LOSS)，本项仅把 bridge.thermal_nodes() 的 G5 "
                "对照结论记入，不改原 thermal_summary.json，也不冒充 FEA 热结果。"
            ),
            "verdict": thermal["verdict"],
        },
        "criteria_source": "e8e6_bridge.E8E6Bridge (ENGINEERING_ACCEPTANCE.md §2)",
        "verdict": verdict["verdict"],
    }


def cmd_check(args) -> int:
    res = analyse()
    os.makedirs(os.path.dirname(RESULT_JSON), exist_ok=True)
    with open(RESULT_JSON, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    v = res["demag_verdict"]
    print("=" * 72)
    print("E6 150°C 三相短路退磁 FEA（真机）")
    print("=" * 72)
    print("  401 点全解: %s (n=%d, t_end=%.6g s)"
          % (res["solver"]["full_401_points"], res["solver"]["n_points"],
             res["solver"]["stop_time_s"]))
    print("  I_sc_peak = %.2f A, H_demag = %.2f kA/m"
          % (res["short_circuit"]["i_sc_peak_a"],
             res["short_circuit"]["h_demag_max_A_per_m"] / 1000.0))
    bm = res["b_min"]
    print("  B_min = %.4f T @ t=%d µs / θ=%.1f° (r=%.4f mm), %d 时刻 × %d 点"
          % (bm["value_T"], bm["sample"]["time_us"], bm["sample"]["angle_deg"],
             bm["sample"]["radius_mm"], bm["n_times"], bm["n_points_per_time"]))
    print("  SF = %.4f (主), SF_Hc = %.4f (交叉)"
          % (res["safety_factor"]["value"], res["safety_factor"]["sf_Hc_crosscheck"]))
    print("  判据: B_min %.2f/%.2f T, SF %.1f/%.1f → %s"
          % (v["criterion"]["b_min_target_t"], v["criterion"]["b_min_min_t"],
             v["criterion"]["sf_target"], v["criterion"]["sf_min"], v["verdict"]))
    print("  热网络 G5 对照: %s（解析 LPTN，非 FEA 热）"
          % res["thermal_crosscheck"]["verdict"])
    print("  JSON: " + RESULT_JSON)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("gen")
    g.add_argument("--trial", action="store_true", help="生成 5 点试算脚本")
    g.add_argument("--full", action="store_true", help="生成 401 点全解脚本")
    sub.add_parser("check")
    sub.add_parser("extrap")
    args = ap.parse_args(argv)
    if args.cmd == "gen":
        return cmd_gen(args)
    if args.cmd == "check":
        return cmd_check(args)
    if args.cmd == "extrap":
        print(json.dumps(extrap(), ensure_ascii=False, indent=2))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
