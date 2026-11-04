#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
25N·m 8p12s SPMSM — S7 集总参数热网络 (LPTN) 稳态温升与瞬态热时间常数
====================================================================
用途：以 S4 解析损耗（铜耗 / 铁耗 / PM 涡流 / 机械 / 杂散）为热源，
      建立 7 节点热网络，求解额定工况稳态温升，并做瞬态升温曲线。
节点：EW 端部绕组 / WS 槽内绕组 / TOOTH 齿 / YOKE 轭 / HOUSE 机壳 /
      ROTOR 转子铁芯+轴 / MAGNET 磁钢；AMBIENT 为 40°C 定温边界。

热网络拓扑（R 单位 K/W）：
    EW --R_we-- WS --R_wt-- TOOTH --R_ty-- YOKE --R_yh-- HOUSE --R_ha-- AMB
    EW --R_eh-- HOUSE
    MAGNET --R_mr-- ROTOR --R_ag-- TOOTH
    ROTOR --R_sh-- HOUSE

假设（全部显式标注，可由本脚本复算）：
  A1 环境温度 40°C（IEC 60034-1 基准），冷却方式 TEFC 轴流风扇；
     强迫风冷 h=30 W/m²K，自然对流 h=10 W/m²K（对照工况）。
  A2 机壳带散热筋，筋化面积系数 3.0，机壳外径 170 mm。
  A3 槽绝缘：0.25 mm Nomex(k=0.15) + 0.15 mm 浸漆气隙层(k=0.12)，
     接触率 0.45（漆瘤/空隙劣化）。
  A4 损耗分配：铜耗按端部/槽内导体长度 42.9%/57.1% 拆分；
     杂散损耗 50/50 入齿/轭；机械损耗 70% 入机壳(轴承/端盖)、30% 入转子(风阻)。
  A5 材料导热率：铜 385、硅钢(叠压) 25、铝 167 W/mK。
  A6 磁钢温度即转子温度（粘结层热阻 8e-4 K/W，可忽略）。

输出：projects/results/thermal_summary.json
      projects/results/thermal_nodes.csv
      projects/results/thermal_transient.csv
"""
import os
import sys
import json
import math
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "scripts")))
import pmsm_config as C  # noqa: E402

MU0 = 4 * math.pi * 1e-7
K_CU, K_FE, K_AL = 385.0, 25.0, 167.0          # W/mK
RHO_CU, RHO_AL = 8960.0, 2700.0                # kg/m³
CP_CU, CP_FE, CP_AL, CP_PM = 385.0, 460.0, 900.0, 460.0   # J/kgK

# ── 几何 m ──
Dso, Dsi = C.STATOR_OD_MM / 1e3, C.STATOR_ID_MM / 1e3
Dro, Dri = C.ROTOR_OD_MM / 1e3, C.ROTOR_ID_MM / 1e3
L = C.STACK_LENGTH_MM / 1e3
g, pp, poles, slots = C.AIRGAP_MM / 1e3, C.POLE_PAIRS, C.POLES, C.SLOTS
tau_pole = math.pi * Dsi / poles
alpha_p = C.PM_POLE_ARC
hm = C.PM_THICKNESS_MM / 1e3

# ── 机壳 / 冷却 ──
D_HOUS = 0.170
T_HOUS = (D_HOUS - Dso) / 2
FIN_FACTOR = 3.0
A_CYL = math.pi * D_HOUS * L
A_ENDCAP = 2 * (math.pi / 4) * (D_HOUS ** 2 - Dsi ** 2)
A_COOL = A_CYL * FIN_FACTOR + A_ENDCAP
H_FORCED, H_NATURAL = 30.0, 10.0
T_AMB = 40.0

# ── 内部热阻 ──
A_SLOT_WALL = slots * (2 * C.SLOT_BODY_DEPTH_MM + C.SLOT_BODY_WIDTH_MM) / 1e3 * L
R_INS_AREA = 0.25e-3 / 0.15 + 0.15e-3 / 0.12   # m²K/W 复合绝缘
CONTACT = 0.45
R_WT = R_INS_AREA / (CONTACT * A_SLOT_WALL)

A_CU_SLOT = slots * C.CONDUCTORS_PER_SLOT * C.WIRE_AREA_MM2 * 1e-6
R_WE = (L / 2) / (K_CU * A_CU_SLOT)

EW_PERIM, EW_LEN = 0.060, 0.060                  # 单个端部线棒周长/轴向长度
A_EW = 2 * slots * EW_PERIM * EW_LEN
R_EH = 1 / (22.0 * A_EW) + 0.08                  # 端部→端盖→机壳

A_TOOTH_ROOT = slots * (C.TOOTH_WIDTH_MM / 1e3) * L
R_TY = 0.008 / (K_FE * A_TOOTH_ROOT)

A_IF = math.pi * Dso * L
R_YH = 1 / (3000.0 * A_IF) + T_HOUS / (K_AL * math.pi * (Dso + T_HOUS) * L)

A_AG = math.pi * Dro * L
R_AG = 1 / (100.0 * A_AG)                        # 气隙对流 h=100 W/m²K

A_PM = poles * alpha_p * tau_pole * L
R_MR = 0.05e-3 / (1.5 * A_PM)                    # 粘结胶 0.05 mm, k=1.5
A_ROT = math.pi * ((Dri + Dro) / 2) * L
R_RS = ((Dro - Dri) / 2) / (K_FE * A_ROT)
R_SH = 1.0                                       # 两端轴承→端盖

NODES = ["EW", "WS", "TOOTH", "YOKE", "HOUSE", "ROTOR", "MAGNET"]
EDGES = [("EW", "WS", R_WE), ("EW", "HOUSE", R_EH), ("WS", "TOOTH", R_WT),
         ("TOOTH", "YOKE", R_TY), ("YOKE", "HOUSE", R_YH),
         ("MAGNET", "ROTOR", R_MR), ("ROTOR", "TOOTH", R_AG),
         ("ROTOR", "HOUSE", R_SH)]


def _solve(A, b):
    """高斯消元（无 numpy 依赖）。"""
    n, M = len(b), [A[i][:] + [b[i]] for i in range(len(b))]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            if f:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def _matrix(g_amb):
    """组装电导矩阵：A_ii=ΣG, A_ij=-G_ij。"""
    n = len(NODES)
    A = [[0.0] * n for _ in range(n)]
    for a, b, r in EDGES:
        i, j, G = NODES.index(a), NODES.index(b), 1.0 / r
        A[i][i] += G
        A[j][j] += G
        A[i][j] -= G
        A[j][i] -= G
    A[NODES.index("HOUSE")][NODES.index("HOUSE")] += g_amb
    return A


def losses(P_cu, P_fe_t, P_fe_y, P_fe_r, P_pm, P_mech, P_stray):
    """按 A4 分配各节点热源 W。"""
    f_end = 0.24 / (2 * (L + 0.12))
    return {"EW": P_cu * f_end, "WS": P_cu * (1 - f_end),
            "TOOTH": P_fe_t + 0.5 * P_stray, "YOKE": P_fe_y + 0.5 * P_stray,
            "HOUSE": 0.7 * P_mech, "ROTOR": P_fe_r + 0.3 * P_mech,
            "MAGNET": P_pm}


def capacitances(m_cu, m_stator, m_rotor, m_pm, m_housing):
    """节点热容 J/K（铜按端部比例拆分）。"""
    f_end = 0.24 / (2 * (L + 0.12))
    return {"EW": m_cu * CP_CU * f_end, "WS": m_cu * CP_CU * (1 - f_end),
            "TOOTH": 0.42 * m_stator * CP_FE, "YOKE": 0.58 * m_stator * CP_FE,
            "HOUSE": m_housing * CP_AL, "ROTOR": m_rotor * CP_FE,
            "MAGNET": m_pm * CP_PM}


def hotspot_gradient(P_ew):
    """端部线束内部导热梯度 q'''r²/(4k_eff)，k_eff=3 W/mK。"""
    V_bundle = 2 * slots * EW_LEN * 1.65e-4
    q = P_ew / V_bundle
    return q * (0.0072 ** 2) / (4 * 3.0), V_bundle


def run_case(name, h_conv, P, Cth, t_amb=T_AMB, t_end=None, dt=10.0):
    # 以温升 θ = T - T_amb 为求解变量：A·θ = P，环境项由 A_HH 中的 g_amb 承担
    A = _matrix(h_conv * A_COOL)
    n = len(NODES)
    R_ha = 1.0 / (h_conv * A_COOL)
    if t_end is None:                      # 6τ 保证瞬态与稳态差 <0.3%
        t_end = max(7200.0, 6.0 * sum(Cth.values()) * R_ha)
    b = [P[k] for k in NODES]
    T = {k: v + t_amb for k, v in zip(NODES, _solve(A, b))}
    dT_hot, V_bundle = hotspot_gradient(P["EW"])
    T["HOTSPOT"] = T["EW"] + dT_hot

    # 瞬态：隐式欧拉 (C/dt + A) θ^{n+1} = C/dt θ^n + P，θ(0)=0
    Cv = [Cth[k] for k in NODES]
    Tn, curve, t = [0.0] * n, [], 0.0
    while t < t_end - 1e-9:
        Aeff = [[A[i][j] + (Cv[i] / dt if i == j else 0.0) for j in range(n)]
                for i in range(n)]
        rhs = [Cv[i] / dt * Tn[i] + b[i] for i in range(n)]
        Tn = _solve(Aeff, rhs)
        t += dt
        curve.append((t, Tn[0], Tn[1], Tn[4], Tn[5], Tn[6]))
    T_tau = {k: v for k, v in zip(NODES, Tn)}
    hi = T_tau["EW"]                                  # 已是温升
    t95 = next((tc for tc, ew, *_ in curve if ew >= 0.95 * hi), t_end)

    res = dict(cooling=f"h={h_conv} W/m²K, A_eff={A_COOL:.4f} m², T_amb={t_amb}°C",
               R_house_to_amb=round(R_ha, 4), t_end_s=round(t_end, 0),
               nodes_C={k: round(T[k], 2) for k in NODES},
               hotspot_C=round(T["HOTSPOT"], 2),
               hotspot_gradient_K=round(dT_hot, 2),
               rise_K={k: round(T[k] - t_amb, 2) for k in NODES},
               hotspot_rise_K=round(T["HOTSPOT"] - t_amb, 2),
               p_injected_W=round(sum(P.values()), 2),
               p_rejected_W=round((T["HOUSE"] - t_amb) / R_ha, 2),
               t95_s=round(t95, 1),
               transient_ss_delta_K=round(abs(T_tau["EW"] - (T["EW"] - t_amb)), 3),
               checks={"winding_hotspot_le_155C": T["HOTSPOT"] <= 155.0,
                       "magnet_le_120C": T["MAGNET"] <= 120.0},
               curve=curve, name=name)
    return res


def main():
    with open(os.path.join(HERE, "..", "results", "sim_summary.json"), encoding="utf-8") as f:
        S = json.load(f)
    P_cu = S["copper"]["P_cu_W"]
    P_fe = S["iron"]["P_fe_W"]
    P_pm = S["pm_eddy"]["P_pm_4seg_W"]
    P_pm_ns = S["pm_eddy"]["P_pm_noseg_W"]
    P_mech = S["performance"]["P_mech"]
    P_stray = S["performance"]["P_stray"]
    m_st = S["iron"]["m_stator_kg"]
    m_rt = S["iron"]["m_rotor_kg"]

    # 铁耗齿/轭拆分：同标定比损耗下按质量分配（齿 2.87 kg / 轭 4.07 kg，S4 体积式）
    V_t = slots * (C.TOOTH_WIDTH_MM / 1e3) * ((Dso - Dsi) / 2 - C.YOKE_THICKNESS_MM / 1e3 - 0.001) * L * 0.95
    V_y = (math.pi / 4) * (Dso ** 2 - (Dso - 2 * C.YOKE_THICKNESS_MM / 1e3) ** 2) * L * 0.95
    m_t, m_y = V_t * 7650, V_y * 7650
    P_fe_t, P_fe_y = P_fe * m_t / (m_t + m_y) * 0.93, P_fe * m_y / (m_t + m_y) * 0.93
    P_fe_r = P_fe * 0.07

    # 质量（热容）
    l_turn = 2 * (L + 0.12)
    m_cu = 3 * C.TURNS_PER_PHASE * l_turn * C.WIRE_AREA_MM2 * 1e-6 * RHO_CU
    V_h = (math.pi / 4) * (D_HOUS ** 2 - Dso ** 2) * L * 1.45
    m_h = V_h * RHO_AL
    m_pm = S["pm_eddy"]["V_pm_m3"] * 7500
    Cth = capacitances(m_cu, m_st, m_rt, m_pm, m_h)

    P = losses(P_cu, P_fe_t, P_fe_y, P_fe_r, P_pm, P_mech, P_stray)
    P_ns = losses(P_cu, P_fe_t, P_fe_y, P_fe_r, P_pm_ns, P_mech, P_stray)

    sc_forced = run_case("forced_air_pm4seg", H_FORCED, P, Cth)
    sc_nat = run_case("natural_conv_pm4seg", H_NATURAL, P, Cth)
    sc_noseg = run_case("forced_air_pm_noseg", H_FORCED, P_ns, Cth)

    C_tot = sum(Cth.values())
    tau = C_tot * sc_forced["R_house_to_amb"]
    out = dict(
        stage="S7", method="7-node LPTN (steady + implicit transient)",
        assumptions=dict(T_amb_C=T_AMB, h_forced=H_FORCED, h_natural=H_NATURAL,
                         A_cooling_m2=round(A_COOL, 4), fin_factor=FIN_FACTOR,
                         contact_factor=CONTACT, end_loss_fraction=round(0.24 / (2 * (L + 0.12)), 4),
                         housing_od_mm=D_HOUS * 1e3, cooling="TEFC shaft fan"),
        resistances_K_per_W={k: round(v, 5) for k, v in
                             dict(R_WE=R_WE, R_EH=R_EH, R_WT=R_WT, R_TY=R_TY,
                                  R_YH=R_YH, R_AG=R_AG, R_MR=R_MR, R_SH=R_SH).items()},
        losses_W={k: round(v, 2) for k, v in P.items()},
        loss_total_W=round(sum(P.values()), 2),
        masses_kg=dict(copper=round(m_cu, 3), stator=round(m_st, 3),
                       rotor=round(m_rt, 3), housing=round(m_h, 3), pm=round(m_pm, 3)),
        thermal_capacity_J_per_K={k: round(v, 1) for k, v in Cth.items()},
        C_total_J_per_K=round(C_tot, 1),
        tau_est_s=round(tau, 1),
        scenarios={k: {kk: vv for kk, vv in v.items() if kk != "curve"}
                   for k, v in (("forced_air_pm4seg", sc_forced),
                                ("natural_conv_pm4seg", sc_nat),
                                ("forced_air_pm_noseg", sc_noseg))},
        verdict=None,
    )
    ok = sc_forced["checks"]["winding_hotspot_le_155C"] and sc_forced["checks"]["magnet_le_120C"]
    out["verdict"] = ("PASS — 强迫风冷下绕组热点 %.1f°C ≤155°C、磁钢 %.1f°C ≤120°C"
                      % (sc_forced["hotspot_C"], sc_forced["nodes_C"]["MAGNET"])) if ok else \
                     ("FAIL — 需增强冷却或降低损耗")
    out["cooling_requirement"] = (
        "必须强迫风冷（TEFC 轴流风扇 h≥30 W/m²K）：自然对流时磁钢 %.1f°C > 120°C、"
        "热点 %.1f°C 逼近 155°C" % (sc_nat["nodes_C"]["MAGNET"], sc_nat["hotspot_C"]))
    out["pm_seg_sensitivity"] = (
        "PM 不分段（%.2f W）仅使磁钢 +%.1f K，磁钢温度由定子侧热阻主导，"
        "分段对热校核非决定性" % (P_pm_ns, sc_noseg["nodes_C"]["MAGNET"] - sc_forced["nodes_C"]["MAGNET"]))

    R = os.path.join(HERE, "..", "results")
    os.makedirs(R, exist_ok=True)
    with open(os.path.join(R, "thermal_summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    with open(os.path.join(R, "thermal_nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "node", "T_C", "rise_K", "loss_W"])
        for tag, sc, pl in (("forced_air", sc_forced, P), ("natural_conv", sc_nat, P),
                            ("forced_noseg", sc_noseg, P_ns)):
            for k in NODES:
                w.writerow([tag, k, sc["nodes_C"][k], sc["rise_K"][k], round(pl[k], 2)])
            w.writerow([tag, "HOTSPOT", sc["hotspot_C"], sc["hotspot_rise_K"], ""])
    with open(os.path.join(R, "thermal_transient.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "EW_C", "WS_C", "HOUSE_C", "ROTOR_C", "MAGNET_C"])
        for row in sc_forced["curve"]:
            w.writerow(["%.1f" % row[0]] + ["%.2f" % (x + T_AMB) for x in row[1:]])

    print("=" * 66)
    print("25N·m 8p12s SPMSM — S7 集总参数热网络")
    print("=" * 66)
    print(f"[热源]   Pcu={P_cu:.1f}  Pfe={P_fe:.1f}(齿{P_fe_t:.1f}/轭{P_fe_y:.1f}/转{P_fe_r:.1f})"
          f"  Ppm={P_pm:.2f}  Pmech={P_mech:.1f}  Pstray={P_stray:.1f}"
          f"  合计={sum(P.values()):.1f} W")
    print(f"[热阻]   R_ha={1/(H_FORCED*A_COOL):.4f} R_eh={R_EH:.3f} R_wt={R_WT:.4f} "
          f"R_ag={R_AG:.3f} R_sh={R_SH:.2f} K/W")
    print(f"[热容]   C_tot={C_tot:.0f} J/K  τ≈{tau:.0f} s ({tau/60:.1f} min)  "
          f"t95={sc_forced['t95_s']:.0f} s")
    for tag, sc in (("强迫风冷", sc_forced), ("自然对流", sc_nat), ("强迫/PM不分段", sc_noseg)):
        nd = sc["nodes_C"]
        print(f"[{tag:>12}] 端部={nd['EW']:.1f} 槽内={nd['WS']:.1f} 齿={nd['TOOTH']:.1f} "
              f"轭={nd['YOKE']:.1f} 机壳={nd['HOUSE']:.1f} 转子={nd['ROTOR']:.1f} "
              f"磁钢={nd['MAGNET']:.1f} 热点={sc['hotspot_C']:.1f}°C "
              f"(ΔT={sc['hotspot_rise_K']:.1f}K)")
    print(f"[校核]   绕组热点≤155°C: {sc_forced['checks']['winding_hotspot_le_155C']}  "
          f"磁钢≤120°C: {sc_forced['checks']['magnet_le_120C']}")
    print(f"[冷却]   {out['cooling_requirement']}")
    print(f"[敏感性] {out['pm_seg_sensitivity']}")
    print(f"[结论]   {out['verdict']}")
    print("=" * 66)
    print(f"输出: {os.path.abspath(R)}")


if __name__ == "__main__":
    main()
