# -*- coding: utf-8 -*-
"""G7 斜槽 —— 2D 多切片（multi-slice）等效评估。

为什么用「多切片」而不是「改几何」
----------------------------------
Maxwell 2D 是**二维**求解，没有轴向斜槽自由度。工程上处理斜槽的标准近似是
**多切片法**：把轴向叠长切成 N 片，每片是一个二维问题，第 j 片转子相对定子转过
Δ_j 角，整机电磁量 = N 片的平均。

本文件做**后处理等价**：不新建 FEA 工程，直接对已有 401 点 FEA 波形按 Δ_j 平移后
平均。成立前提只有一条 —— 各切片除转子角度外场分布相同，这正是多切片法本身的
假设。故

    λ_skew(t) = (1/N)·Σ_j λ_FEA(θ(t) + Δ_j)     ⇒  e = −dλ_skew/dt
    T_skew(t) = (1/N)·Σ_j T_FEA(θ(t) + Δ_j)

**为什么用傅里叶表示而不是线性插值**（2026-11-15 实测教训）
    齿槽主频是 600 Hz（24×25 Hz，周期 **1.667 ms**，不是 15° 对应的 5 ms），
    50 µs 采样只有 33 点/周期，且波形带尖峰。线性插值重采样的最大误差
    7.7e-2 N·m ≈ 齿槽峰峰值的 9% —— 恒等校验（skew=0 应逐位复现基线）
    直接差 4.67%，THD 也从 11.180% 漂到 12.422%。改用「一个电周期（10 ms，
    200 点）的 DFT + 谐波复因子」后，平移与平均都是**带限精确**的，
    skew=0 可逐位复现基线（见 `--check-identity`）。

局限（必须随结论一起报）
------------------------
忽略轴向场变化、斜槽漏抗、端部效应 ⇒ 齿槽/THD 收益是**上限**，
基波降额是**下限**。真机 3 切片 FEA 用于校验该等价性（`--slices 3`）。

用法
----
    python skew_multislice.py                    # 0 / 0.5 / 1.0 槽距
    python skew_multislice.py --slices 3         # 3 切片离散（与真机 FEA 切片同口径）
    python skew_multislice.py --check-identity   # 只做恒等校验
"""
from __future__ import annotations

import argparse
import cmath
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))
FEA = os.path.join(RESULTS, "fea")

NOLOAD_DIR = os.path.join(FEA, "m8_pear")
LOAD_DIR = os.path.join(FEA, "m7_load")

# ── 机器常量（8 极 12 槽 @1500 rpm，冻结）──
SLOTS = 12
POLE_PAIRS = 4
POLES = 2 * POLE_PAIRS
RPM = 1500.0
F_MECH = RPM / 60.0                  # 25 Hz
F_ELEC = POLE_PAIRS * F_MECH         # 100 Hz
T_ELEC = 1.0 / F_ELEC                # 10 ms
OMEGA_MECH = 2.0 * math.pi * F_MECH  # 157.0796 rad/s
T_RATED = 25.0
SLOT_PITCH_DEG = 360.0 / SLOTS       # 30° 机械
COGGING_ORDER = math.lcm(SLOTS, POLES)   # 24 次/转 ⇒ 600 Hz，周期 1.667 ms
T_COG = 1.0 / (COGGING_ORDER * F_MECH)

_T_SCALE = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "\u00b5s": 1e-6}
_V_SCALE = {"NewtonMeter": 1.0, "mNewtonMeter": 1e-3, "uNewtonMeter": 1e-6,
            "Wb": 1.0, "V": 1.0, "volt": 1.0}

# ── 负载工况激励（M7 冻结口径，见 m7_load_check.py / docs/MAXWELL_INTERNALS §11）──
I_RMS = 9.89
CURRENT_PHASE_DEG = {"a": 120.0, "b": 240.0, "c": 0.0}
CURRENT_SIGN = -1            # 电动：i 与 e=−dλ/dt 反相


def phase_current(ph: str, t: float, advance: float = 0.0) -> float:
    """M7 指令电流 i_ph(t) = −√2·I_rms·sin(2πf_e·t + φ_ph)，φ 为电角。

    `advance` 为时间超前量（s），用于「斜槽后按平均转子位置换相」：
    斜槽使相电势整体滞后 γ_e/2（电角），若沿用未斜槽的电流相位，会额外损失
    cos(γ_e/2)（γ=0.5 槽距时 0.866）—— 那是驱动器没重新标定，不是斜槽的代价。
    标准做法把电流对齐到平均位置，故默认按 γ/2 超前。
    """
    tt = t + advance
    return (CURRENT_SIGN * I_RMS * math.sqrt(2.0)
            * math.sin(2.0 * math.pi * F_ELEC * tt + math.radians(CURRENT_PHASE_DEG[ph])))


# ────────────────────────────────────────────────── 读入
def _unit(header: str, fallback: str) -> str:
    if "[" in header and "]" in header:
        return header[header.index("[") + 1:header.index("]")].strip()
    return fallback


def read_two_col(path: str):
    """读 AEDT 两列导出（Time + 一列物理量），按表头单位换算到 s / SI。"""
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


# ────────────────────────────────────────────────── 带限周期表示
class FourierPeriodic:
    """一个电周期（10 ms）的 DFT 表示；平移/平均在谐波域精确完成。

    8 极 12 槽的三个量都以 10 ms 为周期（BEMF 100 Hz；齿槽 600 Hz = 6×100 Hz；
    负载转矩 100 Hz），故统一取 T_ELEC 作模板周期，避免多套周期口径。
    """

    def __init__(self, t, y, period: float = T_ELEC):
        if len(t) < 32:
            raise ValueError("样本不足：%d" % len(t))
        self.period = period
        t0 = t[-1] - period
        self.grid_start = t0
        idx = [i for i in range(len(t)) if t[i] >= t0 - period * 1e-6]
        seg_t = [t[i] for i in idx]
        seg_y = [y[i] for i in idx]
        # 丢掉右端点（与左端点同相），只保留 period 内的 N 个等间隔样本
        if abs(seg_t[-1] - (seg_t[0] + period)) < period * 1e-6:
            n = len(seg_t) - 1
        else:
            n = len(seg_t)
        if n < 32:
            raise ValueError("一个周期内样本不足：%d" % n)
        self.n = n
        span = seg_t[-1] - seg_t[0]
        self.dt = span / (len(seg_t) - 1) if len(seg_t) > 1 else period / n
        # 等间隔性自检（数据必须是固定步长导出）
        if len(seg_t) > 2:
            for i in (1, len(seg_t) // 2, len(seg_t) - 1):
                if abs((seg_t[i] - seg_t[0]) - i * self.dt) > 1e-9:
                    raise ValueError("时间轴非等间隔（i=%d）" % i)
        ys = seg_y[:n]
        # 只保留**单边谱** h=0..N/2。2026-11-15 教训：存 0..N−1 的双边谱再按 h/T
        # 乘平移因子，会让 h>N/2 的负频半边走错相位（两者的 f 差 1/T），
        # 重构出的基波直接掉到 47.6%（BEMF 120.56 → 57.43 V），是个静默的假结果。
        self.c = []
        for h in range(n // 2 + 1):
            ch = self._dft(ys, h)
            # DC 与 Nyquist 在实信号下必为实数（虚部只是数值噪声）
            self.c.append(ch.real if h in (0, n // 2) else ch)

    @staticmethod
    def _dft(ys, h: int):
        n = len(ys)
        acc = 0j
        for i in range(n):
            acc += ys[i] * cmath.exp(-2j * math.pi * h * i / n)
        return acc / n

    def coeffs(self):
        return self.c

    def eval(self, t: float, c=None) -> float:
        """实信号单边谱重构：y(τ)=c0 + 2·ReΣ_{h=1}^{N/2−1} c_h e^{j2πhτ/T} + Nyquist 项。"""
        c = c or self.c
        tau = t - self.grid_start
        base = 2j * math.pi * tau / self.period
        acc = c[0].real
        half = len(c) - 1
        for h in range(1, half):
            if c[h]:
                acc += 2.0 * (c[h] * cmath.exp(base * h)).real
        if self.n % 2 == 0 and half >= 1:
            # Nyquist 项无共轭对，权重为 1（实信号下 c_{N/2} 本身是实数）
            acc += (c[half] * cmath.exp(base * half)).real
        return acc

    def sample(self, t_start: float, n: int, dt: float):
        return [self.eval(t_start + i * dt) for i in range(n)]

    def grid(self, n: int | None = None, dt: float | None = None):
        """一个周期内的 N 个采样点，**不含**重复端点。

        2026-11-15 实测：把端点重复计入（N+1 点）会让 a5 从 28.30 漂到 31.27 V、
        THD 从 11.180% 漂到 12.422%（+1.24 pt），而真实信号在 P1/P2 两个周期、
        任意起点上的谱是一致的（a5=16.338 V 相电压，THD 11.179%）。
        单周期 DFT 的约定就是 i=0..N−1，端点属于下一周期。
        """
        n = n or self.n
        dt = dt or (self.period / n)
        return [self.grid_start + i * dt for i in range(n)]


def slice_factor_series(n_half: int, period: float, gamma_deg: float, n_slices: int | None):
    """每个谐波（单边谱 h=0..N/2）的平均复因子 z_h=(1/N)Σ_j exp(j2πh·Δt_j/T)。"""
    ns = n_slices or 64
    offs = [(j + 0.5) * gamma_deg / ns for j in range(ns)]      # 中点法则
    dts = [o * math.pi / 180.0 / OMEGA_MECH for o in offs]
    z = []
    for h in range(n_half):
        acc = 0j
        for d in dts:
            acc += cmath.exp(2j * math.pi * h * d / period)
        z.append(acc / len(dts))
    return z


def skew_average(sig: FourierPeriodic, gamma_deg: float, n_slices=None) -> list:
    """返回平移平均后的（单边）谐波系数，长度 = N/2+1。"""
    z = slice_factor_series(len(sig.c), sig.period, gamma_deg, n_slices)
    return [c * zz for c, zz in zip(sig.c, z)]


# ────────────────────────────────────────────────── 基础统计
def mean(v):
    return sum(v) / len(v) if v else 0.0


def rms(v):
    return math.sqrt(mean([x * x for x in v])) if v else 0.0


def differentiate(t, y):
    n = len(y)
    d = [0.0] * n
    d[0] = (y[1] - y[0]) / (t[1] - t[0])
    d[n - 1] = (y[n - 1] - y[n - 2]) / (t[n - 1] - t[n - 2])
    for i in range(1, n - 1):
        d[i] = (y[i + 1] - y[i - 1]) / (t[i + 1] - t[i - 1])
    return d


def trapezoid_mean(t, v) -> float:
    if len(t) < 2:
        return 0.0
    a = 0.0
    for i in range(len(t) - 1):
        a += 0.5 * (v[i] + v[i + 1]) * (t[i + 1] - t[i])
    span = t[-1] - t[0]
    return a / span if span else 0.0


def harmonic_amp(t, y, f) -> float:
    n = len(y)
    y0 = mean(y)
    re = im = 0.0
    for i in range(n):
        ph = 2.0 * math.pi * f * t[i]
        re += (y[i] - y0) * math.cos(ph)
        im += (y[i] - y0) * math.sin(ph)
    return 2.0 * math.hypot(re, im) / n


def spectrum(t, y, f0: float, n_harm: int) -> list:
    return [harmonic_amp(t, y, f0 * h) for h in range(1, n_harm + 1)]


def thd_from_amps(amps) -> float:
    if not amps or amps[0] <= 1e-12:
        return 0.0
    acc = sum(a * a for a in amps[1:])
    return 100.0 * math.sqrt(acc) / amps[0]


def skew_factor(h: int, gamma_elec_deg: float) -> float:
    """连续斜槽的谐波因子 k_sk(h) = sin(h·γ/2)/(h·γ/2)，γ 为电角（弧度制内算）。"""
    x = math.radians(gamma_elec_deg) * h / 2.0
    if abs(x) < 1e-12:
        return 1.0
    return math.sin(x) / x


def phase_flux(csvdir: str, ph: str, prefix: str = "flux_"):
    return read_two_col(os.path.join(csvdir, "%s%s.csv" % (prefix, ph)))


# ────────────────────────────────────────────────── 单点评估
def evaluate(noload_dir: str, load_dir: str, skew_slot: float,
             n_samples: int = 200, n_slices=None) -> dict:
    """单点斜槽评估。skew_slot 单位 = 槽距（0.5 ⇒ 15° 机械）。"""
    gamma = skew_slot * SLOT_PITCH_DEG
    gamma_e = gamma * POLE_PAIRS
    out = {"skew_slot_pitch": skew_slot, "skew_mech_deg": round(gamma, 4),
           "skew_elec_deg": round(gamma_e, 4),
           "n_slices": n_slices or 64, "continuous": n_slices is None}

    # ── 齿槽（600 Hz 主频，一个电周期内含 6 个齿槽周期）──
    sig_cog, c_cog = None, None
    tc, tq = read_two_col(os.path.join(noload_dir, "tq_noload.csv"))
    if tc:
        sig_cog = FourierPeriodic(tc, tq)
        c_cog = skew_average(sig_cog, gamma, n_slices)
        g = sig_cog.grid(n_samples)
        w = [sig_cog.eval(x, c_cog) for x in g]
        pp = max(w) - min(w)
        out["cogging_pp_nm"] = round(pp, 5)
        out["cogging_pct"] = round(100.0 * pp / T_RATED, 4)
        out["cogging_mean_nm"] = round(mean(w), 5)
        out["cogging_samples"] = len(g)

    # ── 空载磁链 → BEMF（先平均磁链，再中心差分；线性算子可交换）──
    phases, base_phases = {}, {}
    for ph in ("a", "b", "c"):
        t, lam = phase_flux(noload_dir, ph)
        if not t:
            continue
        sig = FourierPeriodic(t, lam)
        c_avg = skew_average(sig, gamma, n_slices)
        g = sig.grid(n_samples)
        lam_s = [sig.eval(x, c_avg) for x in g]
        phases[ph] = (g, [-v for v in differentiate(g, lam_s)])
        lam_b = [sig.eval(x) for x in g]
        base_phases[ph] = (g, [-v for v in differentiate(g, lam_b)])

    if "a" in phases and "b" in phases:
        t, ea = phases["a"]
        _, eb = phases["b"]
        u = [x - y for x, y in zip(ea, eb)]
        amps = spectrum(t, u, F_ELEC, 15)
        out["bemf_phase_rms_v"] = round(rms(ea), 4)
        out["bemf_line_rms_v"] = round(rms(u), 4)
        out["thd_line_pct"] = round(thd_from_amps(amps), 4)
        out["thd_phase_pct"] = round(thd_from_amps(spectrum(t, ea, F_ELEC, 15)), 4)
        out["harmonics_v"] = [round(a, 4) for a in amps]

        # 通道 B：频域因子法（基波谱 × 连续斜槽因子，不做时间平移）
        bt, bea = base_phases["a"]
        _, beb = base_phases["b"]
        bu = [x - y for x, y in zip(bea, beb)]
        b_amps = spectrum(bt, bu, F_ELEC, 15)
        b_sk = [a * skew_factor(h + 1, gamma_e) for h, a in enumerate(b_amps)]
        out["thd_line_pct_freq_method"] = round(thd_from_amps(b_sk), 4)
        out["thd_two_method_gap_pt"] = round(
            abs(out["thd_line_pct"] - out["thd_line_pct_freq_method"]), 4)
        out["k_sk"] = {str(h): round(skew_factor(h, gamma_e), 5)
                       for h in (1, 5, 7, 11, 13)}

    # ── 负载：**不能**直接对转矩波形做时间平移 ──
    # 2026-11-15 教训：T_load(t) 的时间依赖同时来自「转子角度」和「电流相位」，
    # 直接平移会把两者一起移相（重复移相），结果得到「平均转矩与斜槽无关」的
    # 假不变量（首版即如此：三个斜槽水平的 T_avg 都是 22.6296 N·m）。
    # 线性模型（M270_35A 现为线性 μ=1000）下正确口径是：
    #     T(t) = T_cog(θ) − (1/ω)·Σ e_ph(θ)·i_ph(t)
    # 斜槽只作用在「转子角度决定」的量上 ⇒ 平均 e_ph，电流保持不移相。
    # 该口径在 skew=0 时与 FEA 负载转矩吻合 −0.04%（`load_composition`）。
    tl, tql = read_two_col(os.path.join(load_dir, "tq_load.csv"))
    if tl and "a" in phases and "b" in phases and "c" in phases:
        g = phases["a"][0]
        adv = gamma / 2.0 / 360.0 / F_MECH        # 斜槽半角对应的时间超前
        t_em, t_em_raw = [], []
        for i, x in enumerate(g):
            acc, acc_raw = 0.0, 0.0
            for ph in ("a", "b", "c"):
                e = phases[ph][1][i]
                acc += e * phase_current(ph, x, adv)
                acc_raw += e * phase_current(ph, x, 0.0)
            t_em.append(-acc / OMEGA_MECH)
            t_em_raw.append(-acc_raw / OMEGA_MECH)
        w = []
        for i, x in enumerate(g):
            cog_i = sig_cog.eval(x, c_cog) if c_cog is not None else 0.0
            w.append(t_em[i] + cog_i)
        t_avg = mean(w)
        pp = max(w) - min(w)
        out["T_avg_nm"] = round(t_avg, 4)
        out["T_avg_pct_rated"] = round(100.0 * (t_avg - T_RATED) / T_RATED, 3)
        out["T_ripple_pct"] = round(100.0 * pp / abs(t_avg), 3) if abs(t_avg) > 1e-9 else 0.0
        out["T_pp_nm"] = round(pp, 4)
        out["T_min_nm"] = round(min(w), 4)
        out["T_max_nm"] = round(max(w), 4)
        out["T_em_avg_nm"] = round(mean(t_em), 4)
        out["T_avg_no_realign_nm"] = round(mean(t_em_raw), 4)
        out["current_advance_ms"] = round(adv * 1e3, 5)
        out["load_samples"] = len(g)

        # 与 FEA 负载转矩对照（只对 skew=0 有意义，作为口径自检）
        if abs(gamma) < 1e-12:
            sig_load = FourierPeriodic(tl, tql)
            fea = [sig_load.eval(x) for x in g]
            out["composition_check"] = {
                "T_avg_composed": round(t_avg, 4),
                "T_avg_fea": round(mean(fea), 4),
                "gap_pct": round(100.0 * (t_avg - mean(fea)) / mean(fea), 4),
                "T_pp_composed": round(pp, 4),
                "T_pp_fea": round(max(fea) - min(fea), 4),
                "T_pp_gap_pct": round(100.0 * (pp - (max(fea) - min(fea))) /
                                      (max(fea) - min(fea)), 4),
            }
    return out


def check_identity(noload_dir: str, load_dir: str) -> dict:
    """skew=0 必须复现基线：齿槽 0.8801 N·m、THD 11.180%、T_avg 22.6296 N·m。"""
    z = evaluate(noload_dir, load_dir, 0.0, 200, None)
    t, y = read_two_col(os.path.join(noload_dir, "tq_noload.csv"))
    idx = [i for i in range(len(t)) if t[i] >= t[-1] - T_ELEC - 1e-12]
    base_pp = max(y[i] for i in idx) - min(y[i] for i in idx)
    return {
        "cogging_pp_skew0": z.get("cogging_pp_nm"),
        "cogging_pp_baseline": round(base_pp, 5),
        "cogging_gap_pct": round(100.0 * abs(z.get("cogging_pp_nm", 0) - base_pp) / base_pp, 4),
        "thd_skew0": z.get("thd_line_pct"),
        "T_avg_skew0": z.get("T_avg_nm"),
        "T_ripple_skew0": z.get("T_ripple_pct"),
        "bemf_phase_skew0": z.get("bemf_phase_rms_v"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--noload", default=NOLOAD_DIR)
    ap.add_argument("--load", dest="load_dir", default=LOAD_DIR)
    ap.add_argument("--levels", default="0,0.5,1.0", help="斜槽槽距，逗号分隔")
    ap.add_argument("--slices", type=int, default=None,
                    help="离散切片数（默认 64 点连续）；=3 与真机 3 切片同口径")
    ap.add_argument("--json", default=os.path.join(FEA, "skew_scan_summary.json"))
    ap.add_argument("--csv", default=os.path.join(FEA, "skew_scan.csv"))
    ap.add_argument("--tag", default="")
    ap.add_argument("--check-identity", action="store_true")
    args = ap.parse_args(argv)

    idc = check_identity(args.noload, args.load_dir)
    print("恒等校验 skew=0：%s" % json.dumps(idc, ensure_ascii=False))
    if args.check_identity:
        return 0

    rows = []
    for s in [float(x) for x in args.levels.split(",") if x.strip()]:
        r = evaluate(args.noload, args.load_dir, s, 200, args.slices)
        rows.append(r)
        print("skew=%.2f 槽距 (%5.1f°mech / %5.1f°elec)  齿槽 %.5f N·m (%.3f%%)  "
              "THD %.4f%% (频域 %.4f%%)  BEMF %.4f V  T_avg %.4f N·m  脉动 %.3f%%"
              % (r["skew_slot_pitch"], r["skew_mech_deg"], r["skew_elec_deg"],
                 r.get("cogging_pp_nm", -1), r.get("cogging_pct", -1),
                 r.get("thd_line_pct", -1), r.get("thd_line_pct_freq_method", -1),
                 r.get("bemf_phase_rms_v", -1), r.get("T_avg_nm", -1),
                 r.get("T_ripple_pct", -1)))

    payload = {
        "stage": "G7 skew multislice (2D equivalent)",
        "method": ("one-electrical-period DFT representation; per-harmonic complex "
                   "slice factor z_h=(1/N)SUM exp(j2*pi*h*dt_j/T); band-limited exact"),
        "limits": ["ignores axial field variation", "no skew leakage reactance",
                   "no end effects; cogging/THD gain is an upper bound"],
        "machine": {"slots": SLOTS, "poles": POLES, "rpm": RPM, "f_elec_hz": F_ELEC,
                    "slot_pitch_deg": SLOT_PITCH_DEG,
                    "cogging_order_per_rev": COGGING_ORDER,
                    "cogging_hz": round(COGGING_ORDER * F_MECH, 3),
                    "cogging_period_ms": round(T_COG * 1e3, 5)},
        "identity_check": idc,
        "rows": rows,
        "tag": args.tag,
    }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print("写出 " + args.json)

    if rows and args.csv:
        keys = ["skew_slot_pitch", "skew_mech_deg", "skew_elec_deg", "cogging_pp_nm",
                "cogging_pct", "bemf_phase_rms_v", "bemf_line_rms_v", "thd_line_pct",
                "thd_line_pct_freq_method", "T_avg_nm", "T_avg_pct_rated", "T_ripple_pct"]
        with open(args.csv, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(",".join(keys) + "\n")
            for r in rows:
                fh.write(",".join(str(r.get(k, "")) for k in keys) + "\n")
        print("写出 " + args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
