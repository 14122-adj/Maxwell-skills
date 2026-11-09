# -*- coding: utf-8 -*-
"""ingest_fea.py — 读取 Maxwell 导出的 CSV，计算真实 FEA 指标并回填 `fea_results.json`。

背景（M4 踩坑）
--------------
1. 旧版按「首行表头 + 其余数据」硬解析，而 Maxwell `ReportSetup.ExportToFile` 实际输出
   为「表头行 + 单位行 + 空行 + 数据块」，时间单位还可能是 ms/µs ⇒ 旧版会整列错位。
2. 旧版把线电势写成 `va - vc/2 - vb/2`、把频率钉死在 100 Hz，口径不可复用。
3. **零第三方依赖**：本脚本要能在只有标准库的解释器里跑，因此不引入 numpy；
   DFT 只算目标谐波（≤15 阶、几百点样本，纯 Python 足够快）。
4. **电流型绕组没有 `WindingA.Voltage`**（2026-11-08 实测）。`WindingGroup Type="Current"`
   下 Maxwell 只给磁链，空载反电势必须按发电机惯例求导：
        e(t) = − dλ(t)/dt
   本脚本因此支持两种输入口径：`bemf_a|b|c.csv`（voltage 列，直接统计）
   与 `flux_a|b|c.csv`（FluxLinkage 列，Wb，自动求导后再统计）。

用法
----
    python ingest_fea.py                       # 默认读 D:/ANSYS_Run/csv
    python ingest_fea.py --csvdir DIR --out FILE.json
    python ingest_fea.py --turns-model 80      # 折算到设计匝数（默认 80）
"""
from __future__ import annotations

import argparse
import cmath
import csv
import io
import json
import math
import os
import sys

T_RATED = 25.0          # 额定转矩 N·m（判据基准）
F_ELEC = 100.0          # 8 极 @ 1500 rpm ⇒ f_e = p·n/60 = 4·1500/60 = 100 Hz
W_MECH = 2.0 * math.pi * 1500.0 / 60.0   # 157.0796 rad/s（额定转速）
I_LOAD_RMS = 9.89       # 额定相电流 RMS（S4 解析值，M5 负载工况的指令值）
LOAD_TOLERANCE = 0.20    # 负载判据：T_avg 与 25 N·m 偏差 ±20%
PHASE_DEG = {"A": 120.0, "B": 240.0, "C": 0.0}   # 负载电流初相（空载磁链拟合）
TIME_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "µs": 1e-6, "ns": 1e-9}

# ---- 验收基准（全部来自 S4 解析链路 projects/results/sim_summary.json）----
E_ANALYTIC_PHASE_RMS = 132.4     # √2·π·f·Nph·Kw·φ_pm，相 RMS
TURNS_DESIGN = 81                # 设计匝数（相）
TURNS_MODEL_DEFAULT = 80         # 当前 Maxwell 模型匝数（相）：2 绕齿线圈 × 40 导体
COGGING_ANALYTIC_PCT = 1.815     # 解析齿槽峰值占额定比 %
BEMF_TOLERANCE = 0.25            # 「同量级」判据：与解析值偏差 ±25% 内

VOLT_UNITS = {"v", "volt", "volts"}
FLUX_UNITS = {"wb", "w_b", "weber", "v*s", "v.s", "vs"}


def _split_unit(header: str):
    """'Time [ms]' -> ('Time', 'ms')；无单位则返回 ('Time', '')。"""
    h = header.strip().strip('"')
    if "[" in h and h.endswith("]"):
        return h[: h.index("[")].strip(), h[h.index("[") + 1: -1].strip()
    return h, ""


def _is_number(tok: str) -> bool:
    try:
        float(tok)
        return True
    except (TypeError, ValueError):
        return False


def _read_rows(path: str):
    """Maxwell 导出用制表符分隔，第三方工具可能是逗号；按首行自动判别。"""
    with io.open(path, encoding="utf-8-sig", errors="ignore") as fh:
        text = fh.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    delim = "\t" if (lines and "\t" in lines[0]) else ","
    out = []
    for r in csv.reader(io.StringIO(text), delimiter=delim):
        while r and not r[-1].strip():      # 去掉行尾空字段（Maxwell 每条数据行都带）
            r.pop()
        if r:
            out.append(r)
    return out


def load_maxwell_csv(path: str):
    """返回 (t_seconds, {signal_name: [values]})；无法解析时抛 ValueError。"""
    rows = _read_rows(path)
    if not rows:
        raise ValueError("empty file: " + path)

    start = None
    for i, row in enumerate(rows):
        if len(row) >= 2 and _is_number(row[0]) and _is_number(row[1]):
            start = i
            break
    if start is None:
        raise ValueError("no numeric block found in " + path)

    names, units = [], []
    for h in rows[0]:
        n, u = _split_unit(h)
        names.append(n or "col%d" % len(names))
        units.append(u)

    data = []
    for row in rows[start:]:
        if len(row) < len(names):
            continue
        cells = row[: len(names)]
        if not all(_is_number(c) for c in cells):
            continue          # 末列常带空字段（行尾制表符），直接跳过而非崩掉
        data.append([float(c) for c in cells])
    if not data:
        raise ValueError("no data rows in " + path)

    scale = TIME_SCALE.get(units[0].lower(), 1.0) if units else 1.0
    t = [row[0] * scale for row in data]
    out = {}
    for k in range(1, len(names)):
        out[names[k]] = [row[k] for row in data]
    return t, out


def _mean(v):
    return sum(v) / float(len(v)) if v else 0.0


def classify_column(name: str, unit: str):
    """按列名/单位判定信号口径，返回 'voltage' / 'flux' / None。

    Maxwell 导出的表头形如 `"FluxLinkage(WindingA) [Wb]"`、`"Moving1.Torque [NewtonMeter]"`，
    单位在方括号里，`load_maxwell_csv` 已拆开。
    """
    u = (unit or "").strip().lower().replace(" ", "")
    n = (name or "").strip().lower()
    if u in VOLT_UNITS or "voltage" in n:
        return "voltage"
    if u in FLUX_UNITS or "fluxlinkage" in n or "flux_linkage" in n:
        return "flux"
    return None


def differentiate(t, y):
    """数值微分 dy/dt：内部中心差分（二阶精度），两端单侧差分。零依赖。"""
    n = len(y)
    if n != len(t):
        raise ValueError("t/y length mismatch: %d vs %d" % (len(t), len(y)))
    if n < 3:
        raise ValueError("need at least 3 samples to differentiate")
    d = [0.0] * n
    d[0] = (y[1] - y[0]) / (t[1] - t[0])
    d[n - 1] = (y[n - 1] - y[n - 2]) / (t[n - 1] - t[n - 2])
    for i in range(1, n - 1):
        d[i] = (y[i + 1] - y[i - 1]) / (t[i + 1] - t[i - 1])
    return d


def flux_to_bemf(t, lam):
    """空载反电势 e = −dλ/dt（发电机惯例），单位 V。

    电流型绕组在 Maxwell 里没有 voltage 输出，只能走磁链求导。
    采样 50 µs 时，中心差分的截断误差量级 (ωΔt)²/6 ≈ 1e-5，可忽略。
    """
    return [-v for v in differentiate(t, lam)]


def _scaled(t, y, factor):
    return [v * factor for v in y]


def harmonic_amp(t, y, f):
    """单频幅值：A = 2/N·|Σ (y-mean)·e^{-j2πft}|。"""
    n = len(y)
    if n == 0:
        return 0.0
    y0 = _mean(y)
    acc = 0j
    for i in range(n):
        acc += (y[i] - y0) * cmath.exp(-2j * math.pi * f * t[i])
    return 2.0 * abs(acc) / n


def thd_percent(t, y, f0: float = F_ELEC, n_harm: int = 15):
    """相对基波 f0 的 THD（%），含 2..n_harm 次。"""
    if len(y) < 8:
        return 0.0
    a1 = harmonic_amp(t, y, f0)
    if a1 <= 1e-12:
        return 0.0
    acc = 0.0
    for h in range(2, n_harm + 1):
        acc += harmonic_amp(t, y, f0 * h) ** 2
    return 100.0 * math.sqrt(acc) / a1


def analyse_signal(t, y, skip_first_period: bool = True):
    """RMS/峰值/THD；默认跳过第一个工频周期以排除启动暂态。"""
    if skip_first_period and len(t) > 2:
        t0 = t[0] + 1.0 / F_ELEC
        sel = [i for i in range(len(t)) if t[i] >= t0]
        if len(sel) > 10:
            t = [t[i] for i in sel]
            y = [y[i] for i in sel]
    rms = math.sqrt(_mean([v * v for v in y])) if y else 0.0
    return {
        "rms": rms,
        "peak": max(abs(v) for v in y) if y else 0.0,
        "mean": _mean(y),
        "thd_pct": thd_percent(t, y),
        "n_samples": len(y),
    }


def _pick(cols, needle):
    for k in cols:
        if needle.lower() in k.lower():
            return k
    return None


def _units_by_column(path):
    """返回 {列名: 单位}，与 load_maxwell_csv 的 dict 键对齐。"""
    rows = _read_rows(path)
    if not rows:
        return {}
    units = [_split_unit(h)[1] for h in rows[0]][1:]
    _, cols = load_maxwell_csv(path)
    keys = list(cols.keys())
    if len(units) != len(keys):
        return dict((k, "") for k in keys)
    return dict(zip(keys, units))


def load_phase_bemf(csvdir, ph):
    """取某相的空载反电势，返回 (t, emf, source) 或 None。

    两条通道：
      · `bemf_<ph>.csv` 有 voltage 列 ⇒ 直接统计（绕组设成 Voltage 型时的情形）
      · `flux_<ph>.csv` 有 FluxLinkage 列（Wb）⇒ e = −dλ/dt 后再统计
    电流型绕组只有后者可用，这是 M4 的默认路径。
    """
    pb = os.path.join(csvdir, "bemf_%s.csv" % ph)
    if os.path.exists(pb):
        t, cols = load_maxwell_csv(pb)
        umap = _units_by_column(pb)
        for k in cols:
            if classify_column(k, umap.get(k, "")) == "voltage":
                return t, cols[k], "Winding%s.Voltage" % ph.upper()
    pf = os.path.join(csvdir, "flux_%s.csv" % ph)
    if os.path.exists(pf):
        t, cols = load_maxwell_csv(pf)
        umap = _units_by_column(pf)
        for k in cols:
            if classify_column(k, umap.get(k, "")) == "flux":
                return t, flux_to_bemf(t, cols[k]), "d(FluxLinkage(Winding%s))/dt" % ph.upper()
    return None


def line_to_line(phases, p1, p2):
    """线电势 u_12 = e_1 − e_2（要求同一时间轴）。"""
    if p1 not in phases or p2 not in phases:
        return None
    t1, y1 = phases[p1]
    t2, y2 = phases[p2]
    if len(t1) != len(t2) or abs(t1[0] - t2[0]) > 1e-12:
        return None
    return t1, [a - b for a, b in zip(y1, y2)]


def _tail_after_first_period(t, vals):
    t0 = t[0] + 1.0 / F_ELEC
    sel = [i for i in range(len(t)) if t[i] >= t0]
    return [vals[i] for i in sel] if len(sel) > 10 else vals


def commanded_current(ph: str, t: float, sign: int = -1) -> float:
    """负载工况的指令电流 i = sign·√2·I_rms·sin(2πf·t + φ_ph)（A）。

    相位来自 M4 空载磁链拟合：λ_A = 0.26610·cos(ωt+120.005°)、B = −120°、C = 0°；
    电动需与 e = −dλ/dt **反相** ⇒ sign = −1（见 docs/MAXWELL_INTERNALS.md §11.3）。
    """
    rad = math.radians(PHASE_DEG[ph])
    return sign * I_LOAD_RMS * math.sqrt(2.0) * math.sin(2 * math.pi * F_ELEC * t + rad)


def read_native_trcrv(path: str) -> dict:
    """解析 Maxwell 原生 `WindingX_TrCrv.txt`（电流型绕组）。

    文件结构（2026-11-09 实测）：

        WindingA
          5 5                     <- 5 列 x 5 行
          0                       <- 时间 [s]
          -12.1128  0  0  -0.236714  0     <- i[A], 0, 0, lambda[Wb], v[V]

    返回 {"t": [...], "current": [...], "flux": [...], "voltage": [...]}。
    `voltage` 列是 dλ/dt（**不含** R·i）。报表不可用时这是唯一的兜底通道。
    """
    out = {"t": [], "current": [], "flux": [], "voltage": []}
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
    except OSError:
        return out
    i = 2                                # 跳过名称行与 "N M" 行
    while i + 1 < len(lines):
        try:
            t = float(lines[i])
            vals = [float(x) for x in lines[i + 1].split()]
        except ValueError:
            break
        if len(vals) < 5:
            break
        out["t"].append(t)
        out["current"].append(vals[0])
        out["flux"].append(vals[3])
        out["voltage"].append(vals[4])
        i += 2
    return out


def load_block(csvdir: str, bemf_rms=None, native_dir=None):
    """M5 负载工况：转矩均值/脉动 + 电流校核 + 功率平衡自检。

    判据（任务书）：`T_avg` 与 25 N·m 同量级（±20%）。
    自检 1（电流口径）：三相电流 RMS 必须回到 9.89 A，否则说明激励表达式没生效；
    自检 2（功率平衡）：T_avg·ω_m 应等于 3·E_rms·I_rms（同相驱动），偏差 <10%，
                       这一条能独立抓住「电流相位错 180°」以外的相位失配。
    """
    p = os.path.join(csvdir, "tq_load.csv")
    if not os.path.exists(p):
        return None
    t, cols = load_maxwell_csv(p)
    key = _pick(cols, "torque")
    if not key:
        return None

    tq = _tail_after_first_period(t, cols[key])
    tavg = _mean(tq)
    ripple = 100.0 * (max(tq) - min(tq)) / abs(tavg) if abs(tavg) > 1e-9 else 0.0
    blk = {
        "T_avg_nm": round(tavg, 4),
        "T_min_nm": round(min(tq), 4),
        "T_max_nm": round(max(tq), 4),
        "T_ripple_pct": round(ripple, 3),
        "T_rated_nm": T_RATED,
        "vs_rated_pct": round(100.0 * (tavg - T_RATED) / T_RATED, 3),
        "pass_20pct": bool(abs(tavg - T_RATED) <= LOAD_TOLERANCE * T_RATED),
        "window": "last electrical period (10 ms)",
        "n_samples": len(tq),
    }

    # ---- 电流校核 ----
    # 主通道 cur_a|b|c.csv（整周期）；报表导不出时退回原生 `WindingX_TrCrv.txt`，
    # 但原生文件是**环形缓冲**，只保最后 10 步（0.5 ms）⇒ 算不了 RMS，只能做
    # 「实测 vs 指令波形」的逐点比对（同时验证幅值与相位）。
    cur = {}
    for ph in ("a", "b", "c"):
        pc = os.path.join(csvdir, "cur_%s.csv" % ph)
        if not os.path.exists(pc):
            continue
        tc, cc = load_maxwell_csv(pc)
        kc = _pick(cc, "current")
        if not kc:
            continue
        ig = _tail_after_first_period(tc, cc[kc])
        cur[ph.upper()] = {"rms_a": round(math.sqrt(_mean([v * v for v in ig])), 4),
                           "peak_a": round(max(abs(v) for v in ig), 4)}
    if cur:
        rms_list = [v["rms_a"] for v in cur.values()]
        blk["currents"] = cur
        blk["current_source"] = "cur_a|b|c.csv (full period)"
        blk["current_rms_avg_a"] = round(_mean(rms_list), 4)
        blk["current_balance_pct"] = round(
            100.0 * (max(rms_list) - min(rms_list)) / _mean(rms_list), 3)
        blk["current_commanded_rms_a"] = I_LOAD_RMS
        blk["current_ok"] = bool(
            abs(_mean(rms_list) - I_LOAD_RMS) <= 0.05 * I_LOAD_RMS)
    elif native_dir:
        dev = {}
        for ph in ("a", "b", "c"):
            pn = os.path.join(native_dir, "Winding%s_TrCrv.txt" % ph.upper())
            if not os.path.exists(pn):
                continue
            nat = read_native_trcrv(pn)
            if not nat["t"]:
                continue
            err = [abs(nat["current"][i] - commanded_current(ph.upper(), nat["t"][i]))
                   for i in range(len(nat["t"]))]
            dev[ph.upper()] = {
                "samples": len(nat["t"]),
                "t_window_ms": [round(nat["t"][0] * 1e3, 3), round(nat["t"][-1] * 1e3, 3)],
                "max_dev_a": round(max(err), 4),
                "max_dev_pct_of_peak": round(100.0 * max(err) / (I_LOAD_RMS * math.sqrt(2)), 3),
                "peak_measured_a": round(max(abs(v) for v in nat["current"]), 4),
            }
        if dev:
            worst = max(v["max_dev_pct_of_peak"] for v in dev.values())
            blk["currents"] = dev
            blk["current_source"] = "native WindingX_TrCrv.txt (ring buffer, tail 10 steps)"
            blk["current_commanded_rms_a"] = I_LOAD_RMS
            blk["current_waveform_dev_pct"] = round(worst, 3)
            blk["current_ok"] = bool(worst <= 5.0)

    # ---- 功率平衡：P_mech vs P_emf ----
    if bemf_rms:
        p_mech = tavg * W_MECH
        p_emf = 3.0 * bemf_rms * I_LOAD_RMS
        blk["power_balance"] = {
            "P_mech_w": round(p_mech, 1),
            "P_emf_w": round(p_emf, 1),
            "dev_pct": round(100.0 * (p_mech - p_emf) / p_emf, 2) if p_emf else 0.0,
            "pass_10pct": bool(p_emf and abs(p_mech - p_emf) <= 0.10 * p_emf),
            "note": "P_emf = 3*E_rms*I_rms 用空载 BEMF；差值含电枢反应与齿槽",
        }
    # 转矩常数（按峰值电流，SPMSM 常规口径）
    blk["Kt_nm_per_a_pk"] = round(tavg / (I_LOAD_RMS * math.sqrt(2.0)), 4)
    return blk


def compute(csvdir: str, turns_model: int = TURNS_MODEL_DEFAULT,
            native_dir=None) -> dict:
    res = {"source": "ANSYS Maxwell 2D Transient (real FEA)", "csvdir": csvdir}
    have_any = False

    # ---- 空载反电势（三相：voltage 直读 或 flux 求导）----
    phases = {}
    sources = {}
    for ph in ("a", "b", "c"):
        got = load_phase_bemf(csvdir, ph)
        if got:
            t, emf, src = got
            phases[ph.upper()] = (t, emf)
            sources[ph.upper()] = src
    if phases:
        have_any = True
        rms_by_phase = {}
        for ph in sorted(phases):
            t, y = phases[ph]
            m = analyse_signal(t, y)
            rms_by_phase[ph] = m["rms"]
            res["bemf_phase_%s" % ph] = {
                "rms_v": round(m["rms"], 4),
                "peak_v": round(m["peak"], 4),
                "thd_pct": round(m["thd_pct"], 3),
            }
        mean_phase = _mean(list(rms_by_phase.values()))
        res["bemf_source"] = sources
        res["bemf_rms_phase"] = round(mean_phase, 4)
        res["bemf_rms_line"] = round(mean_phase * math.sqrt(3.0), 4)
        res["bemf_balance_pct"] = round(
            100.0 * (max(rms_by_phase.values()) - min(rms_by_phase.values())) / mean_phase, 3
        )
        # 线电势优先用 A−B 实测（3 次谐波在线上正确抵消），×√3 只作兜底估算
        ll = line_to_line(phases, "A", "B")
        if ll:
            m_ll = analyse_signal(ll[0], ll[1])
            res["bemf_line_direct"] = {
                "rms_v": round(m_ll["rms"], 4),
                "peak_v": round(m_ll["peak"], 4),
                "thd_pct": round(m_ll["thd_pct"], 3),
            }

        # ---- 匝数折算 + M4 验收 ----
        scale = float(TURNS_DESIGN) / float(turns_model) if turns_model else 1.0
        ref = mean_phase * scale
        res["turns"] = {
            "model_per_phase": turns_model,
            "design_per_phase": TURNS_DESIGN,
            "scale_to_design": round(scale, 5),
        }
        res["bemf_rms_phase_at_design_turns"] = round(ref, 4)
        res["bemf_analytic_phase_rms"] = E_ANALYTIC_PHASE_RMS
        res["bemf_vs_analytic_pct"] = round(
            100.0 * (ref - E_ANALYTIC_PHASE_RMS) / E_ANALYTIC_PHASE_RMS, 2
        )
        res["bemf_pass"] = bool(
            abs(ref - E_ANALYTIC_PHASE_RMS) <= BEMF_TOLERANCE * E_ANALYTIC_PHASE_RMS
        )

    # ---- 空载转矩（齿槽）----
    p = os.path.join(csvdir, "tq_noload.csv")
    if os.path.exists(p):
        t, cols = load_maxwell_csv(p)
        key = _pick(cols, "torque")
        if key:
            have_any = True
            tq = _tail_after_first_period(t, cols[key])
            ptp = max(tq) - min(tq)
            pct = 100.0 * ptp / T_RATED
            res["cogging"] = {
                "mean_nm": round(_mean(tq), 5),
                "min_nm": round(min(tq), 5),
                "max_nm": round(max(tq), 5),
                "peak_to_peak_nm": round(ptp, 5),
                "pct_of_rated": round(pct, 3),
                "n_samples": len(tq),
                "analytic_pct_of_rated": COGGING_ANALYTIC_PCT,
                "pass_5pct": bool(pct <= 5.0),
            }

    # ---- 负载转矩与电流（M5 之后才有）----
    blk = load_block(csvdir, res.get("bemf_rms_phase"), native_dir)
    if blk:
        have_any = True
        res["load"] = blk

    res["status"] = "OK" if have_any else "NO_DATA"
    if not have_any:
        res["hint"] = (
            "先在 Maxwell 跑 M4（build_m4_solve.py）并导出 csv；"
            "电流型绕组导出的是 flux_a|b|c.csv（Wb），本脚本会求导成反电势"
        )
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Maxwell CSV -> fea_results.json")
    ap.add_argument("--csvdir", default=r"D:/ANSYS_Run/csv")
    ap.add_argument("--out", default=None,
                    help="默认写入 <repo>/projects/results/fea_results.json")
    ap.add_argument("--native-dir", default=None,
                    help="工程 .aedtresults/<Design>.results/<DV*.Data> 目录；"
                         "报表导不出电流时从这里读 WindingX_TrCrv.txt")
    ap.add_argument("--turns-model", type=int, default=TURNS_MODEL_DEFAULT,
                    help="Maxwell 模型中每相串联匝数（默认 %d），用于折算到设计匝数"
                         % TURNS_MODEL_DEFAULT)
    args = ap.parse_args(argv)

    out = args.out
    if out is None:
        # 与 S4/S7/S8/S9 的结果目录保持一致
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(os.path.dirname(here), "results", "fea_results.json")
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)

    res = compute(args.csvdir, turns_model=args.turns_model, native_dir=args.native_dir)
    with io.open(out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    sys.stdout.write(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
    sys.stdout.write("written: %s\n" % out)
    return 0 if res["status"] == "OK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
