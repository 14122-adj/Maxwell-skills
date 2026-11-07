#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S9 参数敏感性 第二小步 —— 叠长 × 匝数 二维扫描（25 N·m 8p12s SPMSM）
====================================================================
问题来源：S9 第一小步证明「斜槽 0.5 槽距 + 极弧 0.80」可把线反电势 THD 从 15.75% 压到 1.59%、
齿槽转矩压到零，但效率降到 93.42%（基线 93.87%）。几何冻结下 THD≤8% 与 η≥94% 不可兼得，
故本步放开**叠长**与**匝数**这两个仅剩的自由度。

基准点（S9-1 推荐值，skew=0.5 槽距、α_p=0.80）：
  L0=160 mm, N0=81 匝/相, I0=10.6635 A, E0=122.796 V, R0=0.47227 Ω,
  P_cu=161.106 W, P_fe=36.824 W, P_pm=0.379 W, P_mech=58.9 W, P_stray=19.6 W.

模型（全部以基准点归一化，比值式，避免绝对量口径争议）：
  1) 转矩守恒：T ∝ N·L·I ⇒ I = I0·(N0·L0)/(N·L)
  2) 每匝平均长度：L_turn(L) = 2·(L + e)，e=0.12 m 由 R0 反标定（R0=ρ·N0·L_turn0/A_w0，
     ρ=1.72e-8 Ω·m，A_w0=1.652 mm² 裸铜）。等价形式 P_cu ∝ (L+e)/L²。
  3) 等槽满率换线：A_w(N) = A_w0·N0/N ⇒ R ∝ N²·L_turn，P_cu ∝ L_turn/L² **与匝数无关**
     ——即本步待验证假设（定转矩下加匝数只降电流、不降铜耗）。
  4) 铁耗/PM 涡流 ∝ 叠长（齿轭磁密不变：磁通与齿面积同比 ∝ L）；机械耗（轴承/风扇）与叠长无关；
     杂散耗 ∝ L。热点沿用 S7 线性叠加 R_hot。
  5) 反电势 E ∝ N·L；电感 Ls ∝ N²·L；三相短路 I_sc = E/Xs（沿用 S4 口径）⇒ 安匝 ∝ E/Xs·N 决定退磁。
  6) 质量：铁芯/铜/磁钢 ∝ L，机壳 3.15 kg 固定；转矩密度 = 25 N·m / 总质量。

假设与局限：斜槽轴向相位近似不变；铁耗谐波分量、端部漏磁、逆变器损耗未建模；绝对铜耗依赖
S4 的 R_phase 口径（端部等效长度 e=0.12 m 为反标定值，非几何实测）。
输出：projects/results/sensitivity_stack_turns.json、sensitivity_stack_turns.csv
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pmsm_config as C  # noqa: E402

RES = os.path.abspath(os.path.join(HERE, "..", "results"))

# ---------------- 基准与常量 ----------------
S9 = json.load(open(os.path.join(RES, "sensitivity_summary.json"), encoding="utf-8"))
SIM = json.load(open(os.path.join(RES, "sim_summary.json"), encoding="utf-8"))
BASE = next(r for r in S9["sweep"] if r["skew_slot"] == 0.5 and abs(r["pole_arc"] - 0.80) < 1e-9)

L0 = C.STACK_LENGTH_MM / 1000.0          # 0.160 m
N0 = C.TURNS_PER_PHASE                   # 81
L0_MM = C.STACK_LENGTH_MM
I_BASE = BASE["I_rms_A"]
E_BASE = BASE["E_rms_V"]
P_CU_B, P_FE_B, P_PM_B = BASE["P_cu_W"], BASE["P_fe_W"], BASE["P_pm_W"]
P_MECH, P_STRAY_B = 58.9, 19.6
P_OUT = C.RATED_POWER_KW * 1e3
ETA_BASE = BASE["efficiency_pct"]
R0 = SIM["copper"]["R_phase"]
LS0 = SIM["inductance"]["Ld_H"]
BR150 = SIM["demag"]["Br150"]
B_MIN_B = BASE["demag_B_min_T"]
B_DEMAG_TH = C.DEMAG_B_MIN_THRESHOLD_T
T_AMB, THETA_HOT_S7, P_TOT_S7 = 40.0, 89.5, SIM["performance"]["P_total_W"]
R_HOT = (THETA_HOT_S7 - T_AMB) / P_TOT_S7           # K/W，S7 等效热点热阻

RHO_CU = 1.72e-8                          # Ω·m，20°C（由 R0 反标定）
A_W0 = C.WIRE_AREA_MM2 * 1e-6             # m²，AWG15 裸铜
END_LEN = 0.12                            # m/端，等效端部长度（反标定）
L_TURN0 = 2.0 * (L0 + END_LEN)
A_USABLE = C.SLOT_BODY_WIDTH_MM * C.SLOT_BODY_DEPTH_MM   # 171 mm² 槽身可用面积
K_FILL0 = C.CONDUCTORS_PER_SLOT * C.WIRE_AREA_MM2 / A_USABLE
M_IRON = SIM["iron"]["m_stator_kg"] + SIM["iron"]["m_rotor_kg"]
M_CU = 2.01                               # kg（S8 取值）
M_PM = SIM["pm_eddy"]["V_pm_m3"] * 7500.0
M_HOUSING = 3.15                          # kg（S8 取值，与叠长无关）

STACKS_MM = [140.0, 160.0, 180.0]
TURNS = [72, 81, 90]
F_EL = C.RATED_FREQUENCY_HZ
OMEGA = 2.0 * math.pi * F_EL
PF = 0.95
V_DC = C.DC_BUS_VOLTAGE_V
V_PH_MAX = 0.9 * V_DC / math.sqrt(6.0)              # 197.4 V，SVPWM 线性区相电压 RMS 上限
ETA_TARGET = ETA_BASE + 0.5                          # 判据：S9-1 基准 +0.5 pt（原绝对 94% 亦列出）
CRIT = {"fill_max": 0.45, "B_tooth_max_T": 1.65, "demag_SF_min": 2.0,
        "hotspot_max_C": 155.0, "J_max_A_mm2": 7.0, "eta_target_pct": ETA_TARGET}


def loss_total(L, n):
    """给定叠长 L(m) 与匝数 n，返回 (各损耗, 电气量) 字典。"""
    i = I_BASE * (N0 * L0) / (n * L)
    l_turn = 2.0 * (L + END_LEN)
    a_w = A_W0 * N0 / n                       # 等槽满率换线
    r_ph = R0 * (n / N0) ** 2 * (l_turn / L_TURN0)
    p_cu = 3.0 * i * i * r_ph
    p_fe = P_FE_B * L / L0
    p_pm = P_PM_B * L / L0
    p_stray = P_STRAY_B * L / L0
    p_tot = p_cu + p_fe + p_pm + P_MECH + p_stray
    e = E_BASE * (L / L0) * (n / N0)
    ls = LS0 * (n / N0) ** 2 * (L / L0)
    xs = OMEGA * ls
    v_ph = math.hypot(e + r_ph * i * PF, xs * i)
    i_sc = e / xs                             # 三相稳态短路（S4 口径，忽略 R）
    nt = n * i_sc
    return dict(i=i, r_ph=r_ph, l_turn=l_turn, a_w=a_w, p_cu=p_cu, p_fe=p_fe, p_pm=p_pm,
                p_stray=p_stray, p_tot=p_tot, e=e, ls=ls, xs=xs, v_ph=v_ph, i_sc=i_sc, nt=nt)


def case(stack_mm, n):
    L = stack_mm / 1000.0
    d = loss_total(L, n)
    eta = P_OUT / (P_OUT + d["p_tot"]) * 100.0
    z = n / 2.0                                # 每槽导体数（a=2 并联，N=2z）
    fill = z * C.WIRE_AREA_MM2 / A_USABLE      # 维持 AWG15 时的槽满率（线规不变的保守分支）
    j = d["i"] / (d["a_w"] * 1e6)              # A/mm²
    b_min = BR150 - (BR150 - B_MIN_B) * (d["nt"] / N_T_SC_BASE)
    sf = b_min / B_DEMAG_TH
    mass = (M_IRON + M_CU + M_PM) * L / L0 + M_HOUSING
    return dict(
        stack_mm=stack_mm, turns=n, I_rms_A=d["i"], J_A_mm2=j, A_wire_mm2=d["a_w"] * 1e6,
        wire_d_mm=2.0 * math.sqrt(d["a_w"] * 1e6 / math.pi), fill_AWG15=fill,
        R_phase_ohm=d["r_ph"], E_rms_V=d["e"], V_phase_V=d["v_ph"], Ls_mH=d["ls"] * 1e3,
        P_cu_W=d["p_cu"], P_fe_W=d["p_fe"], P_pm_W=d["p_pm"], P_stray_W=d["p_stray"],
        P_total_W=d["p_tot"], efficiency_pct=eta, eta_delta_vs_S9_1_pt=eta - ETA_BASE,
        hotspot_C=T_AMB + R_HOT * d["p_tot"], I_sc_A=d["i_sc"], demag_B_min_T=b_min, demag_SF=sf,
        mass_kg=mass, torque_density_Nm_kg=C.RATED_TORQUE_NM / mass,
        B_tooth_T=BASE["B_tooth_T"], THD_BEMF_pct=BASE["THD_BEMF_pct"],
        sigma8_kPa=BASE["sigma8_kPa"],
        pass_fill=bool(fill <= CRIT["fill_max"]),
        pass_voltage=bool(d["v_ph"] <= V_PH_MAX),
        pass_eta=bool(eta >= ETA_TARGET),
        pass_sf=bool(sf >= CRIT["demag_SF_min"]),
        pass_hotspot=bool(T_AMB + R_HOT * d["p_tot"] <= CRIT["hotspot_max_C"]),
        pass_J=bool(j <= CRIT["J_max_A_mm2"]),
    )


def stack_for_eta(target_pct, n=N0):
    """二分求达到目标效率所需叠长（mm）；无解返回 None。仅在损耗单调下降段搜索。"""
    target_loss = P_OUT * (100.0 / target_pct - 1.0)
    prev, lo = None, None
    for k in range(200):
        L = 0.10 + 0.001 * k
        p = loss_total(L, n)["p_tot"]
        if p <= target_loss:
            lo = 0.10 + 0.001 * (k - 1) if k else L
            prev = p
            break
    if lo is None:
        return None
    a, b = lo, lo + 0.001
    for _ in range(60):
        m = 0.5 * (a + b)
        if loss_total(m, n)["p_tot"] > target_loss:
            a = m
        else:
            b = m
    return 0.5 * (a + b) * 1000.0


N_T_SC_BASE = N0 * (E_BASE / (OMEGA * LS0))   # 基准安匝（退磁激励归一化分母）


def self_check(rows):
    base = next(r for r in rows if r["stack_mm"] == L0_MM and r["turns"] == N0)
    by_l = {L: [r for r in rows if r["stack_mm"] == L] for L in STACKS_MM}
    spread = lambda key: [max(r[key] for r in g) - min(r[key] for r in g) for g in by_l.values()]  # noqa: E731
    r_cal = RHO_CU * N0 * L_TURN0 / A_W0
    m_cu_geo = 12 * (K_FILL0 * A_USABLE * 1e-6) * L0 * 8960 * (L_TURN0 / (2.0 * L0))
    checks = {
        "基准_eta_复现": abs(base["efficiency_pct"] - ETA_BASE) < 0.02,
        "基准_Pcu_复现": abs(base["P_cu_W"] - P_CU_B) < 0.5,
        "基准_总损耗_复现": abs(base["P_total_W"] - BASE["P_total_W"]) < 0.5,
        "端部长度_R标定": abs(r_cal - R0) / R0 < 0.01,
        "Pcu_匝数无关(3L)": max(spread("P_cu_W")) < 1e-6,
        "J_匝数无关(3L)": max(spread("J_A_mm2")) < 1e-9,
        "铜质量_几何与S8一致": abs(m_cu_geo - M_CU) / M_CU < 0.30,
        "E_随匝数递增": all(g[0]["E_rms_V"] < g[1]["E_rms_V"] < g[2]["E_rms_V"] for g in by_l.values()),
        "效率_随叠长递增": all(by_l[STACKS_MM[i]][1]["efficiency_pct"]
                              < by_l[STACKS_MM[i + 1]][1]["efficiency_pct"]
                              for i in range(len(STACKS_MM) - 1)),
        "转矩密度_随叠长递减": all(by_l[STACKS_MM[i]][1]["torque_density_Nm_kg"]
                                 > by_l[STACKS_MM[i + 1]][1]["torque_density_Nm_kg"]
                                 for i in range(len(STACKS_MM) - 1)),
        "电压裕度_全部通过": all(r["pass_voltage"] for r in rows),
        "槽满率_全部<=0.45": all(r["pass_fill"] for r in rows),
        "能量平衡": all(abs(P_OUT + r["P_total_W"] - P_OUT / (r["efficiency_pct"] / 100.0)) < 1e-6
                        for r in rows),
        "转矩密度量级(1.0-1.6)": all(1.0 <= r["torque_density_Nm_kg"] <= 1.6 for r in rows),
    }
    return checks, all(checks.values())


def main():
    rows = [case(L, n) for L in STACKS_MM for n in TURNS]
    checks, ok = self_check(rows)
    l_94 = stack_for_eta(94.0)
    l_target = stack_for_eta(ETA_TARGET)
    l_s4 = stack_for_eta(SIM["performance"]["efficiency_pct"] + 0.5)

    with open(os.path.join(RES, "sensitivity_stack_turns.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        keys = [k for k in rows[0] if not k.startswith("pass_")]
        w.writerow(keys)
        for r in rows:
            w.writerow(["%.5g" % r[k] if isinstance(r[k], float) else r[k] for k in keys])

    hard = [r for r in rows if r["pass_fill"] and r["pass_voltage"] and r["pass_sf"]
            and r["pass_hotspot"] and r["pass_J"]]
    # 并列时优先保留 81 匝（沿用现有工装，不重绕）
    tie = lambda r: (-round(r["efficiency_pct"], 6), abs(r["turns"] - N0))    # noqa: E731
    tie_den = lambda r: (-round(r["torque_density_Nm_kg"], 6), abs(r["turns"] - N0))  # noqa: E731
    best_eta = min(hard, key=tie) if hard else None
    best_den = min(hard, key=tie_den) if hard else None
    out = dict(
        stage="S9", step="stack-length x turns 2D sweep (second step)",
        fixed=dict(skew_slot=0.5, pole_arc=0.80,
                   note="S9-1 推荐值固定，仅放开叠长与匝数；磁路不变 ⇒ THD/齿槽/σ8/齿部 B 与基准点相同"),
        anchor=dict(stack_mm=L0_MM, turns=N0, efficiency_pct=ETA_BASE, P_cu_W=P_CU_B,
                    P_fe_W=P_FE_B, P_total_W=BASE["P_total_W"], I_rms_A=I_BASE, E_rms_V=E_BASE,
                    R_phase_ohm=R0),
        assumptions=dict(
            torque_hold="I = I0*(N0*L0)/(N*L)",
            mean_turn="L_turn(L)=2*(L+%.3f) m, end length back-calibrated from R0 (rho=1.72e-8, Aw0=1.652mm2)"
                      % END_LEN,
            rewinding="A_w = Aw0*N0/N (constant slot fill %.4f) => P_cu = f(L) only" % K_FILL0,
            iron_loss="P_fe, P_pm, P_stray ~ L (tooth/yoke flux density invariant, area ~ L)",
            mech_loss="P_mech = 58.9 W constant (bearing + fan at fixed speed)",
            hotspot="S7 linear superposition, R_hot=%.5f K/W" % R_HOT,
            demag="I_sc = E/Xs, ampere-turns normalised to S9-1 point",
            mass="iron+Cu+PM ~ L, housing 3.15 kg fixed",
        ),
        criteria=dict(CRIT, V_phase_max_V=V_PH_MAX,
                      note="效率判据采用 S9-1 设计点 +0.5 pt（=%.2f%%）；同时给出原绝对 94%% 与"
                           "「S4 解析基线+0.5 pt」两种口径所需叠长，避免口径歧义" % ETA_TARGET),
        sweep=rows,
        best_efficiency=None if best_eta is None else dict(
            stack_mm=best_eta["stack_mm"], turns=best_eta["turns"],
            efficiency_pct=best_eta["efficiency_pct"],
            eta_delta_vs_S9_1_pt=best_eta["eta_delta_vs_S9_1_pt"],
            torque_density_Nm_kg=best_eta["torque_density_Nm_kg"], mass_kg=best_eta["mass_kg"]),
        best_density=None if best_den is None else dict(
            stack_mm=best_den["stack_mm"], turns=best_den["turns"],
            efficiency_pct=best_den["efficiency_pct"],
            torque_density_Nm_kg=best_den["torque_density_Nm_kg"]),
        stack_for_94pct_mm=l_94, stack_for_target_mm=l_target,
        stack_for_s4_plus_0p5_mm=l_s4,
        rejected=dict(
            stack_140mm="J=%.2f A/mm² 超 7.0 上限（η=92.82%%）；若放宽至 7.5 A/mm² 则可用，但效率低于 160 mm"
                        % next(r["J_A_mm2"] for r in rows if r["stack_mm"] == 140.0)),
        self_check=checks, self_check_pass=ok,
        limitation="解析比值模型；逆变器损耗未计（N 增大降电流的系统收益未量化）；端部长度 e=0.12 m 为反标定值；"
                   "叠长>180 mm 会突破 150 mm 机座长径比，需同时改机壳/轴系，本步未建模",
    )
    with open(os.path.join(RES, "sensitivity_stack_turns.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("=" * 104)
    print("S9-2 叠长 × 匝数 扫描（skew=0.5 槽距, α_p=0.80 固定）")
    print("=" * 104)
    print("%6s %5s %7s %6s %7s %7s %8s %8s %8s %7s %7s %6s %7s %6s %6s" %
          ("叠长", "匝数", "I/A", "J", "Pcu/W", "Pfe/W", "ΣP/W", "η%", "Δη/pt", "E/V", "Vph/V",
           "SF", "m/kg", "N·m/kg", "满率"))
    for r in rows:
        print("%6.0f %5d %7.2f %6.2f %7.1f %7.1f %8.1f %8.2f %+8.2f %7.1f %7.1f %6.2f %7.2f %6.3f %6.3f" %
              (r["stack_mm"], r["turns"], r["I_rms_A"], r["J_A_mm2"], r["P_cu_W"], r["P_fe_W"],
               r["P_total_W"], r["efficiency_pct"], r["eta_delta_vs_S9_1_pt"], r["E_rms_V"],
               r["V_phase_V"], r["demag_SF"], r["mass_kg"], r["torque_density_Nm_kg"],
               r["fill_AWG15"]))
    print("-" * 104)
    print("自检: %d/%d 通过 → %s" % (sum(checks.values()), len(checks), "PASS" if ok else "FAIL"))
    for k, v in checks.items():
        if not v:
            print("  ✗", k)
    if best_eta:
        print("效率最优(硬约束内): %d mm / %d 匝 → η=%.2f%% (%+.2f pt vs S9-1), 转矩密度 %.3f N·m/kg"
              % (best_eta["stack_mm"], best_eta["turns"], best_eta["efficiency_pct"],
                 best_eta["eta_delta_vs_S9_1_pt"], best_eta["torque_density_Nm_kg"]))
    if best_den:
        print("密度最优(硬约束内): %d mm / %d 匝 → %.3f N·m/kg, η=%.2f%%"
              % (best_den["stack_mm"], best_den["turns"], best_den["torque_density_Nm_kg"],
                 best_den["efficiency_pct"]))
    print("达 η=94.0%% 所需叠长: %s mm；达 η=%.2f%%（S9-1+0.5pt）所需: %s mm；达 η=%.2f%%（S4+0.5pt）所需: %s mm" %
          ("%.1f" % l_94 if l_94 else "无解", ETA_TARGET, "%.1f" % l_target if l_target else "无解",
           SIM["performance"]["efficiency_pct"] + 0.5, "%.1f" % l_s4 if l_s4 else ">300(无解)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
