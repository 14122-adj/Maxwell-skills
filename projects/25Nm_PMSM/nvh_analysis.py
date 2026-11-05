#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
25N·m 8p12s SPMSM — S8 NVH：定子低阶模态与径向力波避振校核
====================================================================
用途：① 估算定子轭环体面内弯曲模态（m=2…8，薄环理论有效区）与齿一阶弯曲模态；
     ② 由磁钢空间谐波 × 定子齿槽磁导谐波推导径向力波阶次、频率与幅值；
     ③ 逐阶次做「力波频率 vs 同阶模态」避振校核，给出临界转速与裕度。

结构模型（Timoshenko 薄环面内弯曲，忽略延伸变形）：
    f_m = [m(m²-1)/√(m²+1)] · √(E_eff·I/(ρ·A·R⁴)) / (2π)
    I = L·t³/12（绕轴向），A = L·t，R = 轭平均半径
齿模型（根部固支悬臂 + 端部附加质量，Rayleigh 等效质量 33/140）：
    f_1 = √(k/m_eq)/2π，k = 3E_eff·I_t/h³，I_t = L·w³/12

力波模型（Maxwell 应力 σ_r = B_r²/2μ0，B_r 分解为转子空间谐波 × 齿槽磁导谐波）：
    B_r = Σ_μ B_μ cos(μ·2p·θ − ωt) · [1 + Σ_ν ε_ν cos(ν·Q·θ)]
    自乘项    : 阶次 μ·2p，频率 2f_e，幅值 B_μ²/(4μ0)
    齿槽交叉项: 阶次 |μ·2p ± ν·Q|，频率 2f_e，幅值 B_μ·B_ν/(2μ0)
    ε_1 = (k_C − 1)/k_C（Carter 磁导调制幅值），ε_ν = ε_1/ν

假设（全部显式标注，可由本脚本复算）：
  A1 叠压铁芯 E_eff=185 GPa（E=200 GPa × 0.925 叠压/铆接折减），ν=0.3，ρ=7650 kg/m³。
  A2 薄环理论：t/R=0.111，m≤8 误差约 ±15%；m>8 超适用范围，本阶段不做定量判据。
  A3 模态仅计定子铁芯；机壳/绕组作附加质量，用 √(m_core/m_total) 给质量加载下限。
  A4 齿端附加质量 = 50% 槽内铜重（绝缘接触率 0.45，仅部分参与振动）。
  A5 力波频率取两分量角频率之差/和中的非零项：同步稳态下转子谐波与齿槽调制波均
     以 f_e 旋转，交叉项 → 2f_e。S4 曾用「阶次×转频」筛查口径，对 4/20 阶偏低一半
     （4×25=100 Hz vs 实际 200 Hz），本阶段以 2f_e 为准并保留原口径作对照。
  A6 判据：同阶（m=r）模态与力波频率相对偏差 ≥15% 视为通过；m≠r 不激发，不计入。
  A7 转速包络 0–3000 rpm（额定 1500，2:1 弱磁）用于临界转速裕度评估。

输出：projects/results/nvh_summary.json
      projects/results/nvh_modes.csv
      projects/results/nvh_force_orders.csv
"""
import os
import sys
import json
import math
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pmsm_config as C  # noqa: E402

MU0 = 4e-7 * math.pi
E_FE = 185e9
RHO_FE, RHO_AL, RHO_CU = 7650.0, 2700.0, 8960.0
NU = 0.3
DETUNE_MIN = 0.15                     # 判据：同阶频率相对偏差 ≥15%
M_VALID = 8                           # 薄环模型适用上限
N_MAX_RPM = 3000.0                    # 转速包络上限
SIGMA_CUT = 0.5e3                     # 力波幅值显示门槛 0.5 kPa

# ── 几何 m ──
Dso, Dsi = C.STATOR_OD_MM / 1e3, C.STATOR_ID_MM / 1e3
L, ty, w_t = C.STACK_LENGTH_MM / 1e3, C.YOKE_THICKNESS_MM / 1e3, C.TOOTH_WIDTH_MM / 1e3
b0, g = C.SLOT_OPENING_MM / 1e3, C.AIRGAP_MM / 1e3
p, poles, slots = C.POLE_PAIRS, C.POLES, C.SLOTS
n_rated, f_e = C.RATED_SPEED_RPM, C.RATED_FREQUENCY_HZ

R_Y = (Dso - ty) / 2.0                # 轭平均半径
H_TOOTH = Dso / 2.0 - ty - Dsi / 2.0  # 齿径向高度 = 轭内圆半径 − 定子内圆半径


def ring_modes(m_max=M_VALID):
    """薄环面内弯曲模态频率 Hz（m ≥ 2）。"""
    I = L * ty ** 3 / 12.0
    A = L * ty
    base = math.sqrt(E_FE * I / (RHO_FE * A * R_Y ** 4)) / (2 * math.pi)
    return {m: base * m * (m * m - 1) / math.sqrt(m * m + 1) for m in range(2, m_max + 1)}


def tooth_mode(m_tip):
    """齿一阶弯曲：根部固支悬臂 + 端部附加质量。"""
    I_t = L * w_t ** 3 / 12.0
    k_t = 3.0 * E_FE * I_t / H_TOOTH ** 3
    m_beam = RHO_FE * L * w_t * H_TOOTH
    m_eq = 33.0 / 140.0 * m_beam + m_tip
    return math.sqrt(k_t / m_eq) / (2 * math.pi), dict(
        h_tooth_mm=round(H_TOOTH * 1e3, 2), k_MN_per_m=round(k_t / 1e6, 1),
        m_beam_kg=round(m_beam, 4), m_tip_kg=round(m_tip, 4), m_eq_kg=round(m_eq, 4))


def carter():
    """Carter 系数与齿槽磁导基波调制幅值 ε_1。"""
    tau_s = math.pi * Dsi / slots
    gam = (b0 / g) ** 2 / (5.0 + b0 / g)
    k_c = tau_s / (tau_s - gam * g)
    return k_c, (k_c - 1.0) / k_c, tau_s, gam


def force_orders(bg, harms, eps):
    """转子谐波 × 齿槽磁导 → 径向力波（每阶次取主导分量，幅值 Pa）。"""
    rows, f_force = [], 2 * f_e
    for mu, h in harms.items():
        mu = int(mu)
        b_mu = bg * h
        rows.append(dict(order=mu * poles, freq_hz=f_force,
                         sigma_Pa=b_mu ** 2 / (4 * MU0),
                         source=f"B_{mu}² 自乘", kind="self"))
        for nu in (1, 2):
            b_nu = bg * eps / nu
            for sgn in (-1, 1):
                r = abs(mu * poles + sgn * nu * slots)
                if r == 0:
                    continue
                rows.append(dict(order=r, freq_hz=f_force,
                                 sigma_Pa=b_mu * b_nu / (2 * MU0),
                                 source=f"B_{mu}×Λ_{nu * slots}{'+' if sgn > 0 else '-'}",
                                 kind="slot"))
    agg = {}
    for row in rows:
        o = row["order"]
        if o not in agg or row["sigma_Pa"] > agg[o]["sigma_Pa"]:
            agg[o] = dict(row)
    return sorted(agg.values(), key=lambda d: -d["sigma_Pa"])


def check(forces, modes, legacy):
    """逐阶次避振校核。verified=False 表示超薄环模型适用范围，仅定性。"""
    out = []
    for row in forces:
        if row["sigma_Pa"] < SIGMA_CUT:
            continue
        r = row["order"]
        f_m = modes.get(r)
        item = dict(order=r, freq_hz=row["freq_hz"], sigma_kPa=round(row["sigma_Pa"] / 1e3, 2),
                    share_pct=None, source=row["source"], mode_order=r,
                    f_mode_Hz=None if f_m is None else round(f_m, 1),
                    margin_pct=None, n_crit_rpm=None, n_crit_speed_ratio=None,
                    verified=f_m is not None, pass_check=True,
                    note="" if f_m else f"m={r}>{M_VALID} 超薄环适用范围，需 FEA 复核")
        if f_m:
            margin = abs(f_m - row["freq_hz"]) / row["freq_hz"]
            n_c = 30.0 * f_m / p                       # 2f_e 与 m 阶模态重合时的转速
            item.update(margin_pct=round(margin * 100, 1), n_crit_rpm=round(n_c, 0),
                        n_crit_speed_ratio=round(n_c / N_MAX_RPM, 2),
                        pass_check=margin >= DETUNE_MIN)
        out.append(item)
    for r, note in legacy.items():
        f_m = modes.get(r)
        out.append(dict(order=r, freq_hz=r * n_rated / 60.0, sigma_kPa=0.0, share_pct=0.0,
                        source="S4 启发式口径（本次复核）", mode_order=r,
                        f_mode_Hz=None if f_m is None else round(f_m, 1),
                        margin_pct=None, n_crit_rpm=None, n_crit_speed_ratio=None,
                        verified=f_m is not None, excited=False, pass_check=True, note=note))
    tot = sum(i["sigma_kPa"] for i in out if i.get("excited", True))
    for i in out:
        i["share_pct"] = round(100.0 * i["sigma_kPa"] / tot, 2) if tot else 0.0
    return out


def main():
    with open(os.path.join(HERE, "..", "results", "sim_summary.json"), encoding="utf-8") as f:
        S = json.load(f)
    bg = S["magnetic"]["Bg_peak"]
    harms = S["airgap"]["harmonics"]

    modes = ring_modes()
    k_c, eps, tau_s, gam = carter()

    # 质量加载下限修正（A3）
    m_core = S["iron"]["m_stator_kg"]
    m_hous = (math.pi / 4) * (0.170 ** 2 - Dso ** 2) * L * 1.45 * RHO_AL
    l_turn = 2 * (L + 0.12)
    m_cu = 3 * C.TURNS_PER_PHASE * l_turn * C.WIRE_AREA_MM2 * 1e-6 * RHO_CU
    k_load = math.sqrt(m_core / (m_core + m_hous + m_cu))
    modes_loaded = {m: f * k_load for m, f in modes.items()}

    m_cu_slot = C.CONDUCTORS_PER_SLOT * l_turn * C.WIRE_AREA_MM2 * 1e-6 * RHO_CU
    f_tooth, tooth = tooth_mode(0.5 * m_cu_slot)

    forces = force_orders(bg, harms, eps)
    legacy = {6: "8p12s 无此力波阶次（|μ·2p±ν·Q| 不可能得 6），S4 口径取消",
              10: "8p12s 无此力波阶次（同上），S4 口径取消",
              20: "= 2p+Q，与 B_1×Λ_12+ 交叉项重合，频率应为 2f_e=200 Hz 而非 500 Hz"}
    chk = check(forces, modes, legacy)
    ver = [c for c in chk if c["margin_pct"] is not None]
    ok = all(c["pass_check"] for c in ver)
    min_c = min(ver, key=lambda c: c["margin_pct"]) if ver else None
    dom = max((c for c in chk if c.get("excited", True)), key=lambda c: c["sigma_kPa"])

    # 偏心引起的不平衡磁拉力（2 阶，频率 f_e）——非槽极组合产物，单列对照
    f_m2 = modes[2]
    ump = dict(order=2, freq_hz=f_e, f_mode_Hz=round(f_m2, 1),
               margin_pct=round(abs(f_m2 - f_e) / f_e * 100, 1),
               n_crit_rpm=round(60.0 * f_m2 / p, 0),
               note="静/动偏心产生 2 阶不平衡磁拉力（f_e），非槽极谐波；"
                    "幅值取决于偏心量，本阶段不做定量，仅做频率避振")

    # 自检：量纲/量级
    self_check = {
        "carter_kC_in_range": 1.0 < k_c < 1.3,
        "modes_monotonic": all(modes[m] < modes[m + 1] for m in sorted(modes)[:-1]),
        "dominant_order_equals_2p": dom["order"] == poles,
        "sigma_dominant_matches_B2_4mu0": abs(
            dom["sigma_kPa"] * 1e3 - bg ** 2 / (4 * MU0)) / (bg ** 2 / (4 * MU0)) < 0.01,
        "tooth_mode_above_2kHz": f_tooth > 2000,
        "force_freq_is_2fe": all(c["freq_hz"] == 2 * f_e for c in chk if c.get("excited", True)),
    }

    out = dict(
        stage="S8", method="thin-ring in-plane modes + Maxwell-stress force harmonics",
        assumptions=dict(E_eff_GPa=E_FE / 1e9, poisson=NU, rho_Fe=RHO_FE,
                         thin_ring_t_over_R=round(ty / R_Y, 3),
                         mode_model_valid_max_order=M_VALID,
                         mass_loading_factor=round(k_load, 3),
                         tooth_tip_mass="50% slot copper",
                         force_freq_rule="2*f_e (synchronous rotor harmonic × slot permeance)",
                         detune_criterion=f"|f_mode-f_force|/f_force >= {DETUNE_MIN:.0%}",
                         speed_envelope_rpm=[0, N_MAX_RPM]),
        geometry=dict(R_yoke_mm=round(R_Y * 1e3, 2), yoke_t_mm=ty * 1e3, stack_mm=L * 1e3,
                      tooth_h_mm=round(H_TOOTH * 1e3, 2), tooth_w_mm=w_t * 1e3,
                      tau_slot_mm=round(tau_s * 1e3, 2), slot_opening_mm=b0 * 1e3),
        carter=dict(k_C=round(k_c, 4), gamma=round(gam, 4), eps_1=round(eps, 4),
                    B_slot1_T=round(bg * eps, 4)),
        structure=dict(yoke_modes_Hz={m: round(f, 1) for m, f in modes.items()},
                       yoke_modes_mass_loaded_Hz={m: round(f, 1)
                                                  for m, f in modes_loaded.items()},
                       tooth=dict(f1_Hz=round(f_tooth, 1), **tooth),
                       masses_kg=dict(core=round(m_core, 3), housing=round(m_hous, 3),
                                      copper=round(m_cu, 3))),
        forces=chk,
        unbalanced_magnetic_pull=ump,
        min_margin=dict(order=min_c["order"], margin_pct=min_c["margin_pct"],
                        f_force_Hz=min_c["freq_hz"], f_mode_Hz=min_c["f_mode_Hz"]) if min_c else None,
        self_check=self_check,
        pass_check=ok and all(self_check.values()),
        verdict=None,
    )
    if out["pass_check"]:
        out["verdict"] = ("PASS — 2–8 阶定量避振裕度 ≥%.0f%%（最小 %d 阶：%.0f Hz vs %.0f Hz），"
                          "主导力波 %d 阶 %.1f kPa@200 Hz 对应模态 %.1f kHz（%.0f× 裕度）"
                          % (min_c["margin_pct"], min_c["order"], min_c["freq_hz"],
                             min_c["f_mode_Hz"], dom["order"], dom["sigma_kPa"],
                             modes[dom["order"]] / 1e3,
                             modes[dom["order"]] / dom["freq_hz"]))
    else:
        out["verdict"] = "FAIL — 存在同阶力波与模态偏差 <15% 或自检未通过，需改结构/避转速"
    out["design_implication"] = (
        "力波幅值（8 阶 %.1f kPa）远高于结构柔度风险：噪声治理优先级为降低力波幅值"
        "（斜槽/极弧/磁钢分段），而非加强结构；S9 应把斜槽与极弧纳入扫描"
        % dom["sigma_kPa"])
    out["critical_speed_note"] = (
        "全部 2–8 阶临界转速 ≥%.0f rpm（%.1f× 包络上限 %.0f rpm），工作区内无同阶共振"
        % (min_c["n_crit_rpm"], min_c["n_crit_speed_ratio"], N_MAX_RPM)) if min_c else ""

    R = os.path.join(HERE, "..", "results")
    os.makedirs(R, exist_ok=True)
    with open(os.path.join(R, "nvh_summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    with open(os.path.join(R, "nvh_modes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mode_order", "f_core_Hz", "f_loaded_Hz", "n_crit_rpm_at_2fe"])
        for m in sorted(modes):
            w.writerow([m, "%.1f" % modes[m], "%.1f" % modes_loaded[m],
                        "%.0f" % (30.0 * modes_loaded[m] / p)])
    with open(os.path.join(R, "nvh_force_orders.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["order", "freq_Hz", "sigma_kPa", "share_pct", "source", "f_mode_Hz",
                    "margin_pct", "n_crit_rpm", "verified", "pass", "note"])
        for c in chk:
            w.writerow([c["order"], c["freq_hz"], c["sigma_kPa"], c["share_pct"], c["source"],
                        "" if c["f_mode_Hz"] is None else c["f_mode_Hz"],
                        "" if c["margin_pct"] is None else c["margin_pct"],
                        "" if c["n_crit_rpm"] is None else c["n_crit_rpm"],
                        "yes" if c["verified"] else "no",
                        "yes" if c["pass_check"] else "no", c["note"]])

    print("=" * 78)
    print("25N·m 8p12s SPMSM — S8 NVH 结构模态与力波避振")
    print("=" * 78)
    print(f"[结构]   轭 R={R_Y*1e3:.1f} mm  t={ty*1e3:.2f} mm  t/R={ty/R_Y:.3f}  "
          f"质量加载系数={k_load:.3f}")
    print("[模态]   " + " | ".join(f"m={m}:{modes[m]:.0f}" for m in sorted(modes)) +
          f" Hz（铁芯）  加载后 m=2:{modes_loaded[2]:.0f} Hz")
    print(f"[齿]     f1={f_tooth:.0f} Hz（h={H_TOOTH*1e3:.1f} mm，m_eq={tooth['m_eq_kg']:.3f} kg）")
    print(f"[齿槽]   Carter k_C={k_c:.4f}  ε_1={eps:.4f}  → B_slot1={bg*eps:.4f} T")
    print(f"[力波]   f_rot={n_rated/60:.1f} Hz  f_e={f_e:.0f} Hz  → 力波频率 2f_e={2*f_e:.0f} Hz")
    print(f"{'阶次':>5}{'频率Hz':>8}{'幅值kPa':>9}{'占比%':>7}{'模态Hz':>9}"
          f"{'裕度%':>8}{'临速rpm':>10}  来源")
    for c in chk:
        fm = "—" if c["f_mode_Hz"] is None else "%.0f" % c["f_mode_Hz"]
        mg = "—" if c["margin_pct"] is None else "%.0f" % c["margin_pct"]
        nc = "—" if c["n_crit_rpm"] is None else "%.0f" % c["n_crit_rpm"]
        print(f"{c['order']:>5}{c['freq_hz']:>8.0f}{c['sigma_kPa']:>9.2f}{c['share_pct']:>7.1f}"
              f"{fm:>9}{mg:>8}{nc:>10}  {c['source']}")
    print(f"[校核]   最小裕度 {min_c['margin_pct']:.0f}% @ {min_c['order']} 阶  "
          f"(判据 ≥{DETUNE_MIN*100:.0f}%)；自检 {sum(self_check.values())}/{len(self_check)} 通过")
    print(f"[临界]   {out['critical_speed_note']}")
    print(f"[偏心]   2 阶 UMP@f_e={f_e:.0f} Hz vs m=2 模态 {f_m2:.0f} Hz：裕度 "
          f"{ump['margin_pct']:.0f}%，临界转速 {ump['n_crit_rpm']:.0f} rpm")
    print(f"[结论]   {out['verdict']}")
    print(f"[启示]   {out['design_implication']}")
    print("=" * 78)
    print(f"输出: {os.path.abspath(R)}")


if __name__ == "__main__":
    main()
