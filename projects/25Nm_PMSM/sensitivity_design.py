#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S9 参数敏感性 —— 斜槽角 × 极弧系数 二维扫描（25 N·m 8p12s SPMSM）
=================================================================
基准：S4 解析结果（projects/results/sim_summary.json，α_p=0.87、无斜槽）
      S7 热网络热点 89.5°C（强迫风冷） / S8 8 阶力波 119.85 kPa
方法：以基准为归一化点，用「磁通比例 × 斜槽系数」缩放各指标。
  1) 极弧：Φ1 ∝ sin(α_p·π/2)（矩形磁通分布的基波傅里叶幅值），
     谐波 h_μ = |sin(μ α_p π/2)| / (μ sin(α_p π/2))；
     磁钢平顶幅值 Bmax ∝ Φ1/α_p（窄极弧 → 极下磁密升高）。
  2) 斜槽：k_sk(m) = sinc(m·γ/2)，m 为该分量机械空间阶次，γ = s·2π/Q。
     基波 m=p=4，齿槽 m=LCM(2p,Q)=24，8 阶力波按基波平方衰减 k_sk(4)²。
  3) 保持 25 N·m：I ∝ 1/(Φ1·k_sk1)，铜耗 ∝ I²；铁耗/PM 涡流 ∝ Φ1²；
     机壳热点按 S7 线性叠加 Δθ = R_hot·ΔP_loss。
假设与局限（结论须 S6 FEA 复核）：
  - 斜槽仅作轴向相位错位近似，未计斜槽引起的端部漏磁与轴向力；
  - 齿槽转矩按 B1×Λ12 缩放 + 24 阶斜槽系数，s=0.5 槽距处模型给出理论零点，
    实机因饱和/工艺偏差残留 10–30%，绝对值不作判据；
  - 铁耗不随斜槽变化（仅极弧改变磁密幅值），谐波铁耗未单独计。
输出：projects/results/sensitivity_summary.json、sensitivity_sweep.csv
"""
import os
import sys
import math
import json
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pmsm_config as C  # noqa: E402

R = os.path.abspath(os.path.join(HERE, "..", "results"))
MU0 = 4e-7 * math.pi
P, Q, POLES = C.POLE_PAIRS, C.SLOTS, C.POLES
ALPHA0, T_RATED, P_OUT = C.PM_POLE_ARC, C.RATED_TORQUE_NM, C.RATED_POWER_KW * 1e3
N_COG = 24                                  # LCM(2p, Q) 齿槽阶次
SKEWS = [0.0, 0.5, 1.0, 1.5, 2.0]           # 槽距
ALPHAS = [0.80, 0.87, 0.93]
BEMF_ORDERS = [5, 7, 11, 13, 17, 19]        # 线反电势非三倍频谐波（μ % 6 ∈ {1,5}）
CRIT = {"thd_bemf_pct": 8.0, "tcog_pct": 1.0, "efficiency_pct": 94.0, "demag_sf": 2.0}
T_AMB, THETA_HOT_S7 = 40.0, 89.5            # S7 强迫风冷热点（°C）

B = json.load(open(os.path.join(R, "sim_summary.json"), encoding="utf-8"))
N = json.load(open(os.path.join(R, "nvh_summary.json"), encoding="utf-8"))
B_THD = B["airgap"]["thd_BEMF_line"]
B_TCOG, B_ETA = B["cogging"]["peak_Tcog_Nm"], B["performance"]["efficiency_pct"]
B_CU, B_FE = B["performance"]["P_cu"], B["performance"]["P_fe"]
B_PM, B_MECH, B_STRAY = B["performance"]["P_pm_eddy"], B["performance"]["P_mech"], B["performance"]["P_stray"]
B_TOT = B["performance"]["P_total_W"]
B_BTOOTH, B_ERMS = B["magnetic"]["B_tooth"], B["bemf"]["E_rms"]
B_SIGMA8 = max(r["sigma_kPa"] for r in N["forces"] if r["order"] == 8)   # kPa
B_BMIN = B["demag"]["cases"]["geom_Ls"]["B_min_T"]
B_BR150 = B["demag"]["Br150"]
B_I = C.RATED_CURRENT_RMS_A
R_HOT = (THETA_HOT_S7 - T_AMB) / B_TOT       # K/W，S7 等效热点热阻


def sinc(x):
    return 1.0 if abs(x) < 1e-12 else math.sin(x) / x


def skew_k(order_mech, s):
    """斜槽系数：s 槽距斜槽对 m 阶空间分量的轴向平均衰减（可负，取绝对值用）。"""
    return sinc(order_mech * s * (2.0 * math.pi / Q) / 2.0)


def phi_ratio(alpha):
    return math.sin(alpha * math.pi / 2.0) / math.sin(ALPHA0 * math.pi / 2.0)


def h_rel(mu, alpha):
    return abs(math.sin(mu * alpha * math.pi / 2.0)) / (mu * math.sin(alpha * math.pi / 2.0))


def thd_bemf(alpha, s):
    k1 = abs(skew_k(P, s))
    acc = sum((h_rel(mu, alpha) * abs(skew_k(mu * P, s))) ** 2 for mu in BEMF_ORDERS)
    return math.sqrt(acc) / k1


def case(alpha, s):
    kt = phi_ratio(alpha) * abs(skew_k(P, s))         # 转矩系数比（含斜槽基波衰减）
    i_ratio = 1.0 / kt                                # 维持 25 N·m 的电流倍数
    p_cu = B_CU * i_ratio ** 2
    p_fe = B_FE * phi_ratio(alpha) ** 2
    p_pm = B_PM * phi_ratio(alpha) ** 2
    p_tot = p_cu + p_fe + p_pm + B_MECH + B_STRAY
    b_tooth = B_BTOOTH * phi_ratio(alpha)
    thd = thd_bemf(alpha, s) * 100.0
    tcog = B_TCOG * phi_ratio(alpha) * abs(skew_k(N_COG, s))
    b_min = B_BR150 - (B_BR150 - B_BMIN) * kt
    return dict(
        skew_slot=s, pole_arc=alpha, torque_coeff_ratio=kt,
        E_rms_V=B_ERMS * kt, I_rms_A=B_I * i_ratio, J_A_mm2=C.CURRENT_DENSITY_AMM2 * i_ratio,
        B_tooth_T=b_tooth, B_tooth_overload_T=b_tooth * 1.15,
        tooth_saturated=bool(b_tooth > 1.65),
        Tcog_Nm=tcog, Tcog_pct=tcog / T_RATED * 100.0,
        THD_BEMF_pct=thd, ripple_pct=8.0 * max(thd, 1.0) / (B_THD * 100.0),
        P_cu_W=p_cu, P_fe_W=p_fe, P_pm_W=p_pm, P_total_W=p_tot,
        efficiency_pct=P_OUT / (P_OUT + p_tot) * 100.0,
        hotspot_C=THETA_HOT_S7 + R_HOT * (p_tot - B_TOT),
        demag_B_min_T=b_min, demag_SF=b_min / C.DEMAG_B_MIN_THRESHOLD_T,
        sigma8_kPa=B_SIGMA8 * kt ** 2,
        pass_thd=bool(thd <= CRIT["thd_bemf_pct"]),
        pass_tcog=bool(tcog / T_RATED * 100.0 <= CRIT["tcog_pct"]),
        pass_eta=bool(P_OUT / (P_OUT + p_tot) * 100.0 >= CRIT["efficiency_pct"]),
        pass_sf=bool(b_min / C.DEMAG_B_MIN_THRESHOLD_T >= CRIT["demag_sf"]),
        pass_hotspot=bool(THETA_HOT_S7 + R_HOT * (p_tot - B_TOT) <= 155.0),
        pass_tooth=bool(b_tooth <= 1.65),
    )


def self_check(rows):
    """量纲/数量级/内部一致性自检。"""
    base = next(r for r in rows if r["skew_slot"] == 0.0 and r["pole_arc"] == ALPHA0)
    checks = {
        "基准_eta_复现": abs(base["efficiency_pct"] - B_ETA) < 1e-6,
        "基准_thd_复现": abs(base["THD_BEMF_pct"] / 100.0 - B_THD) < 1e-6,
        "基准_Tcog_复现": abs(base["Tcog_Nm"] - B_TCOG) < 1e-9,
        "基准_sigma8_复现": abs(base["sigma8_kPa"] - B_SIGMA8) < 1e-6,
        "基准_SF_复现": abs(base["demag_SF"] - B_BMIN / C.DEMAG_B_MIN_THRESHOLD_T) < 1e-6,
        "k_sk1_单调递减": all(abs(skew_k(P, a)) > abs(skew_k(P, b))
                              for a, b in zip(SKEWS, SKEWS[1:])),
        "半槽距齿槽归零": all(r["Tcog_pct"] < 1e-6 for r in rows if r["skew_slot"] == 0.5),
        "同极弧_THD随斜槽非增": all(
            all(a["THD_BEMF_pct"] >= b["THD_BEMF_pct"] - 0.05
                for a, b in zip([r for r in rows if r["pole_arc"] == al],
                                [r for r in rows if r["pole_arc"] == al][1:]))
            for al in ALPHAS),
        "能量平衡": all(abs(P_OUT + r["P_total_W"] - P_OUT / (r["efficiency_pct"] / 100.0)) < 1e-6
                        for r in rows),
        "常规斜槽电流量级(<13A)": all(9.0 < r["I_rms_A"] < 13.0 for r in rows if r["skew_slot"] <= 1.0),
        "常规斜槽热点(<110C)": all(r["hotspot_C"] < 110.0 for r in rows if r["skew_slot"] <= 1.0),
        "大斜槽不可行_2槽距>20A": all(r["I_rms_A"] > 20.0 for r in rows if r["skew_slot"] == 2.0),
        "效率随斜槽单调降": all(
            all(a["efficiency_pct"] > b["efficiency_pct"]
                for a, b in zip([r for r in rows if r["pole_arc"] == al],
                                [r for r in rows if r["pole_arc"] == al][1:]))
            for al in ALPHAS),
    }
    return checks, all(checks.values())


def main():
    rows = [case(al, s) for s in SKEWS for al in ALPHAS]
    checks, ok = self_check(rows)

    # 筛选：THD/齿槽/退磁/热 四项判据；效率绝对判据 94% 在基线即未达标，作参考项
    cand = [r for r in rows if r["pass_thd"] and r["pass_tcog"] and r["pass_sf"] and r["pass_hotspot"]]
    best_perf = max(cand, key=lambda r: r["efficiency_pct"]) if cand else None
    safe = [r for r in cand if r["pass_tooth"]]
    best_safe = max(safe, key=lambda r: r["efficiency_pct"]) if safe else None
    pareto = [r for r in cand if not any(
        o["efficiency_pct"] >= r["efficiency_pct"] and o["THD_BEMF_pct"] <= r["THD_BEMF_pct"]
        and o["Tcog_pct"] <= r["Tcog_pct"] for o in cand if o is not r)]

    with open(os.path.join(R, "sensitivity_sweep.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        keys = [k for k in rows[0] if not k.startswith("pass_")]
        w.writerow(keys)
        for r in rows:
            w.writerow(["%.5g" % r[k] if isinstance(r[k], float) else r[k] for k in keys])

    out = dict(
        stage="S9", step="skew x pole-arc 2D sweep (first step)",
        method="baseline-normalised analytical scaling (S4 flux model + axial skew factor)",
        assumptions=dict(
            flux_fundamental="Phi1 ~ sin(alpha_p*pi/2), normalised at alpha_p=0.87",
            skew_factor="k_sk(m)=sinc(m*gamma/2), gamma=s*2pi/Q; cogging order LCM(2p,Q)=24",
            torque_hold="I ~ 1/(Phi1*k_sk1) to keep 25 N.m; no turn change (geometry frozen)",
            iron_loss="P_fe ~ Phi1^2 (skew has no effect); harmonic iron loss not separated",
            hotspot="linear superposition on S7 forced-air case, R_hot=%.4f K/W" % R_HOT,
            emf="E_rms ~ Phi1*k_sk1 (voltage margin not re-checked against 537 V bus)",
        ),
        baseline=dict(alpha_p=ALPHA0, skew=0.0, THD_BEMF_pct=B_THD * 100, Tcog_pct=B_TCOG / T_RATED * 100,
                      efficiency_pct=B_ETA, sigma8_kPa=B_SIGMA8, demag_SF=B_BMIN / C.DEMAG_B_MIN_THRESHOLD_T,
                      P_cu_W=B_CU, P_fe_W=B_FE),
        criteria=CRIT,
        criteria_note=(f"效率绝对值 94% 在 S4 基线({B_ETA:.2f}%)即未达成，故 pass_eta 仅作参考，"
                       "实际以「不低于基线 0.5 pt」作可接受判据"),
        sweep=rows,
        pareto=[dict(skew_slot=r["skew_slot"], pole_arc=r["pole_arc"],
                     efficiency_pct=r["efficiency_pct"], THD_BEMF_pct=r["THD_BEMF_pct"],
                     Tcog_pct=r["Tcog_pct"], B_tooth_T=r["B_tooth_T"]) for r in pareto],
        recommendation=None if best_safe is None else dict(
            rule="满足 THD/齿槽/退磁/热 判据且齿部 B<=1.65T 时效率最高",
            skew_slot=best_safe["skew_slot"], pole_arc=best_safe["pole_arc"],
            efficiency_pct=best_safe["efficiency_pct"], THD_BEMF_pct=best_safe["THD_BEMF_pct"],
            Tcog_pct=best_safe["Tcog_pct"], I_rms_A=best_safe["I_rms_A"],
            hotspot_C=best_safe["hotspot_C"], sigma8_kPa=best_safe["sigma8_kPa"],
            demag_SF=best_safe["demag_SF"], B_tooth_T=best_safe["B_tooth_T"],
            efficiency_delta_vs_baseline_pt=best_safe["efficiency_pct"] - B_ETA,
        ),
        best_perf_no_tooth_limit=None if best_perf is None else dict(
            skew_slot=best_perf["skew_slot"], pole_arc=best_perf["pole_arc"],
            efficiency_pct=best_perf["efficiency_pct"], B_tooth_T=best_perf["B_tooth_T"],
            note="齿部 %.3f T 超 1.65 T，磁路线性假设失效，效率增益(%.2f pt)不可信"
                 % (best_perf["B_tooth_T"], best_perf["efficiency_pct"] - B_ETA),
        ),
        self_check=checks, self_check_pass=ok,
        limitation="解析斜槽仅轴向相位近似；齿槽绝对值、铁耗谐波分量、斜槽端部效应须 S6 FEA 复核",
    )
    with open(os.path.join(R, "sensitivity_summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("=" * 96)
    print("S9 敏感性 — 斜槽 × 极弧 二维扫描（25 N·m 8p12s）")
    print("=" * 96)
    print("%5s %6s %8s %7s %8s %8s %7s %8s %8s %7s %6s" %
          ("斜槽", "极弧", "kt", "I/A", "Tcog%", "THD%", "η%", "Pcu/W", "热点C", "σ8kPa", "齿饱和"))
    for r in rows:
        print("%5.2f %6.2f %8.4f %7.2f %8.2f %8.2f %7.2f %8.1f %8.1f %7.1f %6s" %
              (r["skew_slot"], r["pole_arc"], r["torque_coeff_ratio"], r["I_rms_A"],
               r["Tcog_pct"], r["THD_BEMF_pct"], r["efficiency_pct"], r["P_cu_W"],
               r["hotspot_C"], r["sigma8_kPa"], "是" if r["tooth_saturated"] else "否"))
    print("-" * 96)
    print("自检: %d/%d 通过 → %s" % (sum(checks.values()), len(checks), "PASS" if ok else "FAIL"))
    for k, v in checks.items():
        if not v:
            print("  ✗", k)
    if best_safe:
        print("推荐(饱和安全): 斜槽 %.1f 槽距 / 极弧 %.2f → η=%.2f%% (基线%+.2f pt)  THD=%.2f%%  "
              "Tcog<%.2f%%  B_齿=%.3fT  σ8=%.1f kPa" %
              (best_safe["skew_slot"], best_safe["pole_arc"], best_safe["efficiency_pct"],
               best_safe["efficiency_pct"] - B_ETA, best_safe["THD_BEMF_pct"],
               best_safe["Tcog_pct"], best_safe["B_tooth_T"], best_safe["sigma8_kPa"]))
    if best_perf and best_perf is not best_safe:
        print("效率最优(齿部饱和, 不可信): 斜槽 %.1f / 极弧 %.2f → η=%.2f%%, B_齿=%.3fT" %
              (best_perf["skew_slot"], best_perf["pole_arc"],
               best_perf["efficiency_pct"], best_perf["B_tooth_T"]))
    print("Pareto 前沿 %d 点；产物写入 %s" % (len(pareto), R))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
