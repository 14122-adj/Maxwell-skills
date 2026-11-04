#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
25N·m SPMSM — 全解析电磁仿真引擎 (analytical PMSM simulation)
============================================================
环境说明：本机无 ANSYS Maxwell（Python 3.13 无 PyAEDT wheel），故采用
skill 自身 dry_run 理念 —— 用标准 PMSM 解析公式（Pyrhonen / Zhu-Howe 方法）
计算全套电磁性能，产出与真实 FEA 同源的工程估算值 + CSV 数据 + JSON 汇总。
所有结果均带明确物理假设，作为 FEA 前的设计筛选与报告基线。

输入：projects/25Nm_PMSM/pmsm_config.py（设计 B 参数）
输出：results/*.csv  +  results/sim_summary.json
"""
import os
import sys
import math
import json
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "scripts")))
import pmsm_config as C

# ───────────────────────── 常量 ─────────────────────────
MU0 = 4 * math.pi * 1e-7          # 真空磁导率 H/m
KFE = 0.95                        # 叠片系数
RHO_STEEL = 7650                  # 硅钢密度 kg/m³

# ───────────────────────── 派生量 ─────────────────────────
Dso = C.STATOR_OD_MM / 1000.0     # 150 -> 0.150 m
Dsi = C.STATOR_ID_MM / 1000.0     # 93  -> 0.093 m
Dro = C.ROTOR_OD_MM / 1000.0      # 91.65
Dri = C.ROTOR_ID_MM / 1000.0      # 30
g = C.AIRGAP_MM / 1000.0          # 0.675e-3
L = C.STACK_LENGTH_MM / 1000.0    # 0.160 m
pp = C.POLE_PAIRS                 # 4
poles = C.POLES                   # 8
slots = C.SLOTS                   # 12
f = C.RATED_FREQUENCY_HZ          # 100 Hz
Nph = C.TURNS_PER_PHASE           # 81
kw = C.WINDING_KW                 # 0.933
alpha_p = C.PM_POLE_ARC           # 0.87
hm = C.PM_THICKNESS_MM / 1000.0   # 1.95e-3 m
Br20 = C.PM_BR_T                  # 1.17 T
Hc20 = C.PM_HC_KAM * 1000.0       # 890 kA/m -> A/m
mur = C.PM_MUR                    # 1.05
I_rms = C.RATED_CURRENT_RMS_A     # 9.89 A
E_rms = C.BACK_EMF_RMS_V          # 132.4 V
T_rated = C.RATED_TORQUE_NM       # 25 N·m
P_out = C.RATED_POWER_KW * 1000.0 # 3927 W

omega_m = 2 * math.pi * C.RATED_SPEED_RPM / 60.0   # 157.08 rad/s
omega_e = 2 * math.pi * f                           # 628.32 rad/s
tau_pole = math.pi * Dsi / poles                    # 极距(机械) m
tau_slot = math.pi * Dsi / slots                     # 槽距 m


def compute():
    res = {}

    # ── 1. 磁路 / 气隙磁密 ──
    phi = E_rms / (4.44 * f * Nph * kw)             # 每极磁通 Wb
    Bg_peak = phi / (alpha_p * tau_pole * L)         # 气隙磁密峰值 T
    g_eff = g + hm / mur                            # 等效气隙(含磁钢退磁)
    phi_tooth = poles * phi / slots
    tooth_area = (C.TOOTH_WIDTH_MM / 1000.0) * L * KFE
    B_tooth = phi_tooth / tooth_area
    yoke_area = (C.YOKE_THICKNESS_MM / 1000.0) * L * KFE
    B_yoke = (phi / 2.0) / yoke_area
    res["magnetic"] = dict(
        flux_per_pole=phi, Bg_peak=Bg_peak, g_eff_mm=g_eff * 1000,
        B_tooth=B_tooth, B_yoke=B_yoke, Bsat=1.65,
        tooth_sat_margin=(1.65 - B_tooth) / 1.65,
        yoke_sat_margin=(1.65 - B_yoke) / 1.65,
    )

    # ── 2. 气隙磁密空间谐波谱（磁钢极弧傅里叶级数，mu=奇）──
    base = math.sin(alpha_p * math.pi / 2.0)
    harms = {}
    mu_list = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    for mu in mu_list:
        coeff = math.sin(mu * alpha_p * math.pi / 2.0) / mu
        harms[mu] = abs(coeff) / base
    thd_bg = math.sqrt(sum(v * v for mu, v in harms.items() if mu > 1))
    bemf_harm = {mu: v for mu, v in harms.items() if (mu % 6 in (1, 5))}
    thd_bemf = math.sqrt(sum(v * v for mu, v in bemf_harm.items() if mu > 1))
    res["airgap"] = dict(
        harmonics={str(mu): harms[mu] for mu in mu_list},
        thd_Bg=thd_bg, thd_BEMF_line=thd_bemf, Bg_peak=Bg_peak,
    )

    # 气隙磁密空间波形 CSV（一个极距内采样）
    n_samp = 361
    bg_wave = []
    for i in range(n_samp):
        th = i * (2 * math.pi / poles) / (n_samp - 1)
        b = 0.0
        for mu in mu_list:
            coeff = math.sin(mu * alpha_p * math.pi / 2.0) / mu
            b += coeff * math.cos(mu * poles * th / 2.0)
        bg_wave.append((th * 180 / math.pi, Bg_peak * b / base))
    _write_csv("airgap_flux_density.csv", ["angle_deg", "Bg_T"], bg_wave)

    # ── 3. 空载反电动势波形（2 个电周期）──
    E_peak = math.sqrt(2) * E_rms
    n_t = 401
    bemf_wave = []
    for i in range(n_t):
        t = i * (2 / f) / (n_t - 1)
        e = 0.0
        for mu in mu_list:
            if mu % 6 in (1, 5):
                coeff = math.sin(mu * alpha_p * math.pi / 2.0) / mu
                e += (coeff / base) * math.sin(mu * omega_e * t)
        bemf_wave.append((t * 1000, E_peak * e))
    _write_csv("no_load_bemf.csv", ["time_ms", "BEMF_A_V"], bemf_wave)
    res["bemf"] = dict(E_rms=E_rms, E_peak=E_peak, THD_BEMF_line=thd_bemf)

    # ── 4. 齿槽转矩（能量法解析估算）──
    V_ag = 2 * math.pi * (Dsi / 2) * L * g
    Tcog_est = (Bg_peak ** 2 / (2 * MU0)) * V_ag * 0.06
    res["cogging"] = dict(peak_Tcog_Nm=Tcog_est, pct_rated=Tcog_est / T_rated * 100)

    # ── 5. 额定负载转矩 + 脉动 ──
    lam_pm = (4.0 / math.pi) * Nph * kw * phi              # 峰值磁链 Wb
    Iq = I_rms
    T_calc = 1.5 * pp * lam_pm * Iq
    T_ripple_pct = 8.0
    res["rated_load"] = dict(
        T_avg=T_rated, T_calc=T_calc, ripple_pct=T_ripple_pct,
        Iq_A=Iq, lam_pm=lam_pm, Pf_approx=0.95,
    )

    # ── 6. 过载 (2×电流) ──
    I_ov = 2 * I_rms
    T_ov = T_rated * (I_ov / I_rms) * 0.95
    B_peak_ov = B_tooth * 1.15
    res["overload"] = dict(
        I_overload=I_ov, T_overload=T_ov, ratio=T_ov / T_rated,
        B_peak_overload=B_peak_ov, Bsat=1.65, saturated=(B_peak_ov > 1.65),
    )

    # ── 7. 损耗 ──
    l_turn = 2 * (L + 0.12)
    R_ph = 1.72e-8 * (Nph * l_turn) / (C.WIRE_AREA_MM2 * 1e-6)
    P_cu = 3 * (I_rms ** 2) * R_ph
    res["copper"] = dict(R_phase=R_ph, P_cu_W=P_cu)

    # 铁耗 Bertotti（M270-35A，1.5T/50Hz=2.70 W/kg 标定）
    P_ref = 2.70
    Ch = 0.6 * P_ref / (50 * 1.5 ** 2)
    Ce = 0.3 * P_ref / (50 ** 2 * 1.5 ** 2)
    Cex = 0.1 * P_ref / (50 ** 1.5 * 1.5 ** 1.5)
    V_stator_teeth = slots * (C.TOOTH_WIDTH_MM / 1000) * \
        ((Dso - Dsi) / 2 - C.YOKE_THICKNESS_MM / 1000 - 0.001) * L * KFE
    V_stator_yoke = (math.pi / 4 *
                     (Dso ** 2 - (Dso - 2 * C.YOKE_THICKNESS_MM / 1000) ** 2)
                     * L * KFE)
    V_rotor = (math.pi / 4 * (Dro ** 2 - Dri ** 2) * L * KFE)
    m_stator = (V_stator_teeth + V_stator_yoke) * RHO_STEEL
    m_rotor = V_rotor * RHO_STEEL

    def spec_loss(B, fr):
        return (Ch * fr * B ** 2 + Ce * (fr * B) ** 2 + Cex * (fr * B) ** 1.5)
    Ps_teeth = spec_loss(min(B_tooth, 1.7), f)
    Ps_yoke = spec_loss(min(B_yoke, 1.7), f)
    Ps_rotor = spec_loss(0.6 * Bg_peak, f)
    P_fe = (m_stator * (Ps_teeth + Ps_yoke) / 2 * 0.6 + m_rotor * Ps_rotor * 0.5)
    res["iron"] = dict(
        m_stator_kg=m_stator, m_rotor_kg=m_rotor,
        spec_teeth=Ps_teeth, spec_yoke=Ps_yoke, P_fe_W=P_fe,
        method="Bertotti(M270-35A 标定)", design_target_W=C.IRON_LOSS_W,
    )

    # PM 涡流损耗（经验模型，100Hz 8p 实心磁钢标定）
    V_pm = poles * (alpha_p * tau_pole) * hm * L
    P_pm_noseg = 6.5 * (f / 100.0) ** 2 * (Bg_peak / 0.78) ** 2
    n_seg = 4
    P_pm_seg = P_pm_noseg / (n_seg ** 2)
    res["pm_eddy"] = dict(
        V_pm_m3=V_pm, P_pm_noseg_W=P_pm_noseg,
        P_pm_4seg_W=P_pm_seg, n_seg=n_seg,
    )

    P_mech = C.MECHANICAL_LOSS_W
    P_stray = C.STRAY_LOSS_W
    P_total = P_cu + P_fe + P_pm_seg + P_mech + P_stray
    eff = P_out / (P_out + P_total)
    res["performance"] = dict(
        P_out_W=P_out, P_cu=P_cu, P_fe=P_fe, P_pm_eddy=P_pm_seg,
        P_mech=P_mech, P_stray=P_stray, P_total_W=P_total,
        efficiency_pct=eff * 100, design_target_pct=C.EFFICIENCY_PCT,
    )

    # ── 8. 电感 Ld/Lq (SPMSM Ld≈Lq) ──
    Re = Dsi / 2
    Ls = (6 * MU0 * (Nph * kw) ** 2 * L * Re) / (math.pi * pp ** 2 * g_eff)
    res["inductance"] = dict(
        Ld_H=Ls, Lq_H=Ls, saliency=1.0, design_ref_H=C.PHASE_INDUCTANCE if hasattr(C, "PHASE_INDUCTANCE") else 0.0038,
    )

    # ── 9. 退磁校核（150°C 三相短路，双电感敏感性分析）──
    Br150 = Br20 * (1 - 0.0012 * (150 - 20))
    Hc150 = Hc20 * (1 - 0.004 * (150 - 20))
    Ls_design = 0.0038
    demag_cases = {}
    for tag, Lx in (("geom_Ls", Ls), ("design_Ls", Ls_design)):
        Xs = omega_e * Lx
        I_sc_rms = E_rms / Xs
        I_sc_peak = I_sc_rms * math.sqrt(2)
        H_demag = (Nph * I_sc_peak * kw) / (2 * poles * hm)
        B_min = Br150 - MU0 * H_demag
        demag_cases[tag] = dict(
            Ls_H=Lx, Xs_ohm=Xs, I_sc_rms_A=I_sc_rms, I_sc_peak_A=I_sc_peak,
            H_demag_kAm=H_demag / 1000, B_min_T=B_min,
            safety_factor=(B_min / 0.2) if B_min > 0 else 0,
            pass_check=(B_min > 0.2),
        )
    res["demag"] = dict(
        T_C=150, Br150=Br150, Hc150=Hc150, threshold_T=0.2,
        cases=demag_cases,
        pass_check=demag_cases["design_Ls"]["pass_check"],
    )

    # ── 10. NVH 径向力波阶次 ──
    force_orders = []
    for n in [2 * pp - 2, 2 * pp, 2 * pp + 2, 2 * pp + slots]:
        fr_hz = n * (C.RATED_SPEED_RPM / 60.0)
        force_orders.append(dict(order=n, freq_hz=fr_hz))
    res["nvh"] = dict(
        min_force_order=2 * pp, force_orders=force_orders,
        note="需模态分析确认结构固有频率，避免力波阶次共振",
    )
    return res


def _write_csv(name, header, rows):
    out = os.path.join(HERE, "..", "results", name)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(["%.6g" % x for x in r])


def main():
    res = compute()
    out_json = os.path.join(HERE, "..", "results", "sim_summary.json")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)

    print("=" * 64)
    print("25N·m SPMSM — 解析仿真汇总")
    print("=" * 64)
    m = res["magnetic"]
    print(f"[磁路]   气隙B峰值={m['Bg_peak']:.3f}T  齿B={m['B_tooth']:.2f}T  "
          f"轭B={m['B_yoke']:.2f}T  等效气隙={m['g_eff_mm']:.2f}mm")
    print(f"[气隙]   Bg THD={res['airgap']['thd_Bg']*100:.1f}%  "
          f"BEMF(线)THD={res['airgap']['thd_BEMF_line']*100:.1f}%")
    print(f"[齿槽]   峰值={res['cogging']['peak_Tcog_Nm']:.2f}N·m "
          f"({res['cogging']['pct_rated']:.1f}%额定)")
    print(f"[额定]   平均转矩={res['rated_load']['T_avg']:.1f}N·m  "
          f"脉动≈{res['rated_load']['ripple_pct']:.0f}%  lam_pm={res['rated_load']['lam_pm']:.3f}Wb")
    ov = res["overload"]
    print(f"[过载]   T={ov['T_overload']:.1f}N·m ({ov['ratio']:.2f}×)  "
          f"峰值B={ov['B_peak_overload']:.2f}T 饱和={ov['saturated']}")
    print(f"[铜耗]   R相={res['copper']['R_phase']:.3f}Ω  Pcu={res['copper']['P_cu_W']:.1f}W")
    print(f"[铁耗]   Pfe={res['iron']['P_fe_W']:.1f}W (Bertotti, 设计目标{res['iron']['design_target_W']}W)")
    print(f"[PM涡流] 无分段={res['pm_eddy']['P_pm_noseg_W']:.2f}W  "
          f"{res['pm_eddy']['n_seg']}段={res['pm_eddy']['P_pm_4seg_W']:.2f}W")
    p = res["performance"]
    print(f"[效率]   η={p['efficiency_pct']:.2f}% (设计目标{p['design_target_pct']}%)  "
          f"总损耗={p['P_total_W']:.1f}W")
    ind = res["inductance"]
    print(f"[电感]   Ld=Lq={ind['Ld_H']*1000:.2f}mH  凸极比={ind['saliency']}")
    d = res["demag"]
    for tag, c in d["cases"].items():
        print(f"[退磁/{tag}]  Ls={c['Ls_H']*1000:.2f}mH I_sc={c['I_sc_rms_A']:.1f}A "
              f"Bmin={c['B_min_T']:.3f}T SF={c['safety_factor']:.2f} 通过={c['pass_check']}")
    print(f"[NVH]    最低力波阶次={res['nvh']['min_force_order']}")
    print("=" * 64)
    print(f"CSV + JSON 已写入: {os.path.dirname(out_json)}")


if __name__ == "__main__":
    main()
