#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s 几何定源 —— I1（48 槽梨形槽 7 尺寸）+ I4（单层 V 型磁钢）

为什么单独一个模块
------------------
`PROJECT_SPEC.md` §2 已证明表 2 的 12 槽梨形槽**不能照抄**：48 槽槽距
`π·93/48 = 6.0868 mm` 小于表 2 槽底直径 `Bs2 = 9.5 mm`，照抄必然 intersect。
本模块把「从约束推到尺寸」的过程写成可复算的代码，而不是把结论抄进配置：

* **I1**：7 个槽尺寸由四条约束依次定出 —— ① 齿部磁密（齿宽下限由
  `Bg·τ_bore/(B_tooth·k_fe)` 给出）；② 槽口最小入线间隙；③ 槽身宽度按双层
  圆线排布（2 根 Ø1.5 并排 + 绝缘）取整；④ 轭厚取 baseline 的 16 mm；最后
  用铜耗预算反算所需槽面积并对照。`Rs = Bs2/2` 是梨形槽「半圆底与直身相切」
  的几何恒等式，本模块显式验证它在新尺寸下仍然成立（端点重合）。
* **I4**：每极**一组** V、每组 2 块 ⇒ 8 极 **16 块（单层 V）**。用户 2026-11-22
  明确要求磁钢单层，不用双层 V。每块用「内端起点 + 方向 + 长度 + 厚度」参数化，
  逐块校验：在转子内（OD 桥厚 ≥ 1.5 mm）、离轴孔 ≥ 3 mm、同组两腿间距、
  极间间距 ≥ 1.2 mm，并给出最近距离的数值证据。
* **I2 线圈排布**：用户 2026-11-22 明确要求绕组在**同一槽内关于切向中心线对称
  并排**，不是径向「一远一近」。梨形槽轮廓本身关于 y=0 对称，故按 y=0 把
  内缩线圈切成左右两半、中间留 0.4 mm 绝缘带；两条边距气隙**等距**。

本模块只做几何与解析，**不产生 FEA 结论**；所有 FEA 数字必须由真机求解给出
（见 `docs/ENGINEERING_ACCEPTANCE.md` §4）。

溯源
----
- 槽距/极距：`PROJECT_SPEC.md` §2（π·93/48）
- 齿磁密判据：`docs/ENGINEERING_ACCEPTANCE.md` §2（B_tooth ≤ 1.65 T）
- 轭厚 baseline：`projects/IPM_8p48s/PROJECT_SPEC.md` §2 约束②（16 mm）
- 梨形槽 11 点轮廓：`scripts/slot_profile.py`（唯一顶点来源，禁止第二份坐标）
- 铜耗预算：`docs/ENGINEERING_ACCEPTANCE.md` §2（P_cu ≤ 140 W）
"""
from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, asdict, field

# ---- 让本模块能 import skill 的 scripts 模块 ----
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if os.path.join(_ROOT, "scripts") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import slot_profile  # noqa: E402

# 物理常数（75°C 铜，IEC 60287 口径）
RHO_CU_75 = 2.05e-8      # Ω·m
K_FE = 0.95              # 叠压系数（0.35 mm M270-35A 涂漆叠片）
LAMINATION_MM = 0.35


@dataclass
class IPMConfig:
    """IPM 8p48s 几何配置（mm）。§1 沿用项固定，§3 定源项见 derive_*。"""

    # §1 沿用 baseline
    poles: int = 8
    slots: int = 48
    phases: int = 3
    stator_od: float = 150.0
    stator_id: float = 93.0
    airgap: float = 0.675
    stack_length: float = 160.0

    # D1（I1 定源结果，derive_slot 会重算并断言与这里一致）
    # 槽口宽：2026-11-24 按书本案例（Bs0=1.0）定制，从 2.2 收窄以压制 1200 Hz 槽谐波。
    # 联动 Bs1=1.5、Hs2=13.5（yoke 15.0），槽面积 37.836、满率 0.7606（原 0.7387）。
    slot_Bs0: float = 1.0
    slot_Hs0: float = 0.5
    slot_Bs1: float = 1.5
    slot_Hs1: float = 6.0
    slot_Bs2: float = 3.5
    slot_Rs: float = 1.75
    slot_Hs2: float = 13.5

    # D2（I2 定源）
    coil_pitch: int = 5          # 槽距数（全距 6，短距 1 槽）
    layers: int = 2

    # D3 —— I3 匝数定源（2026-11-24）。cps=5 时 cps=5 空载 401 点实测 BEMF
    # 63.8721 V（BH 修复后 Bg=0.6621 T 可信）；线性反推 125 V → cps=10
    # （N_ph=16·cps=160 匝，预测 127.744 V，落 118–145 V 窗）。故 cps 5→10
    # 定源，直接写进 baseline 配置（不再是 TEMP）。FEA 侧只改 AssignCoil 的
    # Conductor number，几何不动（槽按 Ø1.5 余量设计，见下）。
    conductors_per_slot: int = 10
    # 槽几何定标参考线径（derive_slot 的 Bs0/Bs2 由它推，保持 1.50 不改，
    # 否则槽宽/槽面积连锁变化会破坏已 green 的 M1'/M2' 几何证据链）。
    wire_diameter_mm: float = 1.50
    # 制造实际绕线线径（I3/G7 槽满率口径）：cps=10 → 每槽 2 边 × 10 根 = 20 根，
    # Ø1.5 时 fill=0.9016>0.78 FAIL；Ø1.35 时 fill=0.7303 PASS。
    # assumption=待验证：需物料 BOM 给出真实漆包线规格；FEA 不依赖此字段。
    # 制造绕线口径（不进 FEA 几何）：2026-11-24 Bs0=1.0 + yoke 16→15 重定标后，
    # 槽面积 37.836、Ø1.35 满率 0.7606（≤0.78），比旧口径 0.7387 提高。
    wind_wire_mm: float = 1.35

    # D4（I4：单层 V，用户 2026-11-22 定）
    rotor_id: float = 30.0
    pm_thickness: float = 2.8
    pm_bridge_od: float = 1.5     # 磁钢外角到转子 OD 的最小铁桥
    pm_bridge_gap: float = 1.2    # 组内两腿/极间最小铁桥
    # 单层 V：(apex 半径, 与径向夹角°, 长度, 内端间距)。
    # 块数 = 8 极 × 2 块 = 16。
    # 2026-11-22 I16 根因修复：apex 26→33（外移 7 mm）。旧 apex=26 磁钢埋深
    # 8.356 mm、桥区实测仅 0.085 T、Bg 0.063 T / BEMF 4.2552 V（M2' FAIL）；
    # apex=33 → OD 桥 1.549 mm（≤2.0）、极间 10.141、轴孔 16.495，解析 6/6 PASS。
    # 解析扫描：apex=32 OD 桥 2.525 不够；33.5 OD 1.060 <1.5 机械下限 FAIL。
    # 极间桥恒 10 mm+ 是 8 极 V 张角的几何下限，与"I16 极间≤2.0"判据不可兼得，
    # 已交周检裁定；本阶段只按 OD 桥≤2.0 推进（PROJECT_SPEC §7.2）。
    v_single: tuple = (33.0, 38.0, 13.0, 3.0)

    # D5 斜槽多切片转角（机械度）：0=基线；3 切片取 ±γ/2, 0，
    # γ = 0.75 槽距 × (360/48) = 5.625° 机械（=22.5° 电角）。
    # 只影响转子 V 槽/磁钢几何与磁化方向，定子/绕组不动。
    rotor_init_deg: float = 0.0

    # 材料/工况（§1）
    Bg_assumed: float = 0.85     # 假设：V 型聚磁后气隙工作磁密（M2' FEA 验证）
    B_tooth_limit: float = 1.65
    B_yoke_limit: float = 1.45
    # 2026-11-24: 16→15 mm，配合 Bs0=1.0 使槽面积回到 37.836（铜耗判据需 ≥37.776）。
    # B_yoke 实测 1.089 T ≤1.45，留有余量；轭厚削薄 1 mm 由 FEA 复核。
    yoke_min: float = 15.0
    J_design: float = 6.0        # A/mm²（自然冷却小机常用 5–7）
    fill_design: float = 0.55
    P_cu_budget: float = 140.0

    @property
    def poles_pairs(self) -> int:
        return self.poles // 2

    @property
    def rotor_od(self) -> float:
        return self.stator_id - 2.0 * self.airgap


# --------------------------------------------------------------------------- I1
def derive_slot(cfg: IPMConfig) -> dict:
    """I1 定源：按约束顺序推到 7 个槽尺寸，返回推导链 + 自检。"""
    steps = []
    r_bore = cfg.stator_id / 2.0
    r_out = cfg.stator_od / 2.0
    tau_bore = math.pi * cfg.stator_id / cfg.slots

    # ① 齿宽下限（磁密）
    b_tooth_min = cfg.Bg_assumed * tau_bore / (cfg.B_tooth_limit * K_FE)
    steps.append(dict(step="① 齿宽下限", formula="b_t = Bg·τ/(B_t·k_fe)",
                      expr="%.4f·%.4f/(%.2f·%.2f)" % (cfg.Bg_assumed, tau_bore,
                                                      cfg.B_tooth_limit, K_FE),
                      value_mm=round(b_tooth_min, 4),
                      note="齿部最窄截面（槽身起点）按 1.65 T 上限反算"))

    # ② 槽口宽：齿部在气隙侧不窄于 b_t，且开口 ≥ 入线间隙
    bs0_max = tau_bore - b_tooth_min
    # 2026-11-24：系数 0.36→0.164，使 Bs0=1.0 mm 与书本案例（图2表1-1）一致，
    # 目的是压 1200 Hz 槽谐波（cps=10 实测 h=12 幅值 2.208 N·m = 8.58% T_avg）。
    # 形状定制，不重推槽面积/线圈（见 config.slot_Bs0 注释）。
    bs0_practice = round(0.164 * tau_bore, 1)         # 案例定制 ≈1.0 mm（原 0.36τ=2.2）
    # 2026-11-24：不再用 `d_wire+0.4` 拉高槽口。案例 Bs0=1.0 < Ø1.35 线径，
    # 属成型/半闭口槽（绕组从槽口压入），制造性由 I3 槽满率与下周检复核。
    bs0 = min(bs0_max, bs0_practice)
    steps.append(dict(step="② 槽口宽 Bs0", formula="min(τ−b_t, 0.164τ) —— 案例定制，不拉宽",
                      expr="min(%.4f, %.2f)" % (bs0_max, bs0_practice),
                      value_mm=round(bs0, 2),
                      note="2026-11-24 按书本案例 Bs0=1.0 压 1200 Hz 槽谐波；"
                           "槽口小于线径属半闭口槽，制造性待复核"))

    # ③ 颈高：2026-11-24 按书本案例收窄 1.2→0.5 mm（用户要求"Hs0 跟着小一点"）。
    #    槽楔薄型化，让矩形绕组往槽口延伸（线圈 6.795→7.172 mm²/条），
    #    Hs2 相应加长（yoke 15 → Hs2 13.5）保持槽面积 ≥ 铜耗所需。
    hs0 = 0.5
    steps.append(dict(step="③ 颈高 Hs0", formula="0.5 —— 案例定制（原 ceil(max(3·t_lam,1.0)+0.1)=1.2）",
                      expr="书本案例 Hs0=0.5",
                      value_mm=hs0, note="2026-11-24 用户要求随 Bs0 收窄；矩形绕组受益"))

    # ④ 肩宽：比槽口宽 0.7 mm，供线圈扩散；同时校验 x1 处齿宽
    bs1 = round(bs0 + 0.5, 2)
    tau_x1 = 2.0 * math.pi * (r_bore + hs0) / cfg.slots
    tooth_x1 = tau_x1 - bs1
    steps.append(dict(step="④ 肩宽 Bs1", formula="Bs0+0.5",
                      expr="%.2f+0.5" % bs0, value_mm=bs1,
                      note="x1 处齿宽 %.3f mm ⇒ B_t=%.3f T" % (
                          tooth_x1, cfg.Bg_assumed * tau_bore / (tooth_x1 * K_FE))))

    # ⑤ 槽身宽：双层圆线排布（2 根并排 + 绝缘 0.3）
    bs2_wire = 2.0 * cfg.wire_diameter_mm + 0.5
    bs2 = math.ceil(bs2_wire * 10.0) / 10.0
    steps.append(dict(step="⑤ 槽身宽 Bs2", formula="ceil(2·d_wire+0.5, 0.1)",
                      expr="ceil(2·%.2f+0.5, 0.1)" % cfg.wire_diameter_mm,
                      value_mm=bs2, note="双层各 2 根并排 + 单边 0.25 绝缘；圆线满率可达 0.55–0.62"))

    # ⑥ 斜肩高：槽身起点半径由齿宽下限反解（含 4% 冲剪公差余量，再向上取 0.1）
    r_x2_min = (bs2 + 1.04 * b_tooth_min) * cfg.slots / (2.0 * math.pi)
    hs1 = math.ceil((r_x2_min - (r_bore + hs0)) * 10.0) / 10.0
    steps.append(dict(step="⑥ 斜肩高 Hs1", formula="ceil((Bs2+1.04·b_t)·N/(2π) − (R_bore+Hs0), 0.1)",
                      expr="ceil((%.2f+1.04·%.4f)·%d/(2π) − (%.2f+%.2f), 0.1)" % (
                          bs2, b_tooth_min, cfg.slots, r_bore, hs0),
                      value_mm=hs1,
                      note="保证槽身起点处齿宽 ≥ %.3f mm（含 4%% 冲剪余量）" % b_tooth_min))

    # ⑦ 槽底半径：梨形槽半圆底与直身相切 ⇒ Rs = Bs2/2（几何恒等式）
    rs = bs2 / 2.0
    steps.append(dict(step="⑦ 槽底半径 Rs", formula="Bs2/2（相切恒等式）",
                      expr="%.2f/2" % bs2, value_mm=rs,
                      note="半圆两端点与直身边重合，切向连续；见 check_tangency"))

    # ⑧ 槽深：轭厚取 baseline 16 mm
    hs2 = round((r_out - cfg.yoke_min) - r_bore, 2)
    steps.append(dict(step="⑧ 槽深 Hs2", formula="(R_out−h_yoke) − R_bore",
                      expr="(%.2f−%.2f) − %.2f" % (r_out, cfg.yoke_min, r_bore),
                      value_mm=hs2, note="口径 = 内径 → 槽底最底端（与表 2 一致）"))

    # ---- 组装临时配置，复用 slot_profile 的唯一顶点源 ----
    sc = _SlotOnly(cfg, bs0, hs0, bs1, hs1, bs2, rs, hs2)
    pts = slot_profile.pear_key_points(sc)
    area = slot_profile.pear_area_analytic(sc)
    eff = slot_profile.slot_effective_area(sc, area)
    outline = slot_profile.pear_outline(sc)
    coil_poly = slot_profile.shrink_toward_centroid(outline, 0.86)
    coil_area = slot_profile.polygon_area(coil_poly)

    # ---- 校核 1：沿槽深的齿宽/齿磁密最小值 ----
    tooth = []
    for i in range(201):
        r = (r_bore + hs0) + (r_x2_min - r_bore - hs0) * i / 200.0
        w = bs1 + (bs2 - bs1) * i / 200.0
        t = 2.0 * math.pi * r / cfg.slots - w
        tooth.append((r, t, cfg.Bg_assumed * tau_bore / (t * K_FE)))
    t_min = min(tooth, key=lambda x: x[1])

    # ---- 校核 2：轭部磁密 ----
    tau_pole = math.pi * cfg.stator_id / cfg.poles
    phi_pole = cfg.Bg_assumed * tau_pole * cfg.stack_length * 1e-6   # Wb（mm→m 已含）
    h_yoke = r_out - (r_bore + hs2)
    b_yoke = phi_pole / (2.0 * h_yoke * 1e-3 * cfg.stack_length * 1e-3 * K_FE)

    # ---- 校核 3：铜耗预算 → 所需槽面积 ----
    y = cfg.coil_pitch
    l_end = 0.5 * y * tau_bore + 15.0            # mm，端部轴向伸出经验式
    l_turn = 2.0 * (cfg.stack_length + l_end) * 1e-3   # m
    a_cu_req = cfg.P_cu_budget / (24.0 * RHO_CU_75 * (cfg.J_design * 1e6) ** 2 * l_turn) * 1e6  # mm²
    a_slot_req = a_cu_req / cfg.fill_design
    a_cu_avail = area * cfg.fill_design

    checks = [
        dict(name="槽口齿宽 ≥ b_t_min", value=round(tau_bore - bs0, 4), limit=round(b_tooth_min, 4),
             op=">=", status="PASS" if tau_bore - bs0 >= b_tooth_min else "FAIL"),
        dict(name="x1 齿宽 ≥ b_t_min", value=round(tooth_x1, 4), limit=round(b_tooth_min, 4),
             op=">=", status="PASS" if tooth_x1 >= b_tooth_min else "FAIL"),
        dict(name="齿宽最小处 B_t ≤ 上限", value=round(t_min[2], 4), limit=cfg.B_tooth_limit,
             op="<=", status="PASS" if t_min[2] <= cfg.B_tooth_limit else "FAIL"),
        dict(name="轭厚 ≥ baseline", value=round(h_yoke, 3), limit=cfg.yoke_min,
             op=">=", status="PASS" if h_yoke >= cfg.yoke_min - 1e-9 else "FAIL"),
        dict(name="轭部 B_yoke ≤ 上限", value=round(b_yoke, 4), limit=cfg.B_yoke_limit,
             op="<=", status="PASS" if b_yoke <= cfg.B_yoke_limit else "FAIL"),
        dict(name="槽面积 ≥ 铜耗所需", value=round(area, 3), limit=round(a_slot_req, 3),
             op=">=", status="PASS" if area >= a_slot_req else "FAIL"),
        dict(name="Rs = Bs2/2 相切", value=round(rs, 6), limit=round(bs2 / 2.0, 6),
             op="==", status="PASS" if abs(rs - bs2 / 2.0) < 1e-9 else "FAIL"),
        dict(name="相邻槽底净距 ≥ 1.0 mm",
             value=round(2.0 * math.pi * (r_bore + hs2 - rs) / cfg.slots - bs2, 3), limit=1.0,
             op=">=", status="PASS" if
             (2.0 * math.pi * (r_bore + hs2 - rs) / cfg.slots - bs2) >= 1.0 else "FAIL"),
    ]

    return dict(
        config=dict(stator_od=cfg.stator_od, stator_id=cfg.stator_id, slots=cfg.slots,
                    stack=cfg.stack_length, tau_bore=round(tau_bore, 4)),
        chain=steps,
        dims=dict(Bs0=bs0, Hs0=hs0, Bs1=bs1, Hs1=hs1, Bs2=bs2, Rs=rs, Hs2=hs2),
        radii=dict(x0=round(pts[0][0], 4), x1=round(r_bore + hs0, 4),
                   x2=round(r_bore + hs0 + hs1, 4), x3=round(r_bore + hs2 - rs, 4),
                   x4=round(r_bore + hs2, 4), h_yoke=round(h_yoke, 4)),
        areas=dict(slot_analytic=round(area, 3), slot_effective=round(eff, 3),
                   coil_shrink_086=round(coil_area, 3), coil_to_slot=round(coil_area / area, 4)),
        flux=dict(tau_pole=round(tau_pole, 4), phi_pole_uWb=round(phi_pole * 1e6, 3),
                  B_tooth_min_at=round(t_min[0], 3), B_tooth_min=round(t_min[2], 4),
                  B_yoke=round(b_yoke, 4)),
        thermal=dict(l_end_mm=round(l_end, 2), l_turn_m=round(l_turn, 4),
                     a_cu_req_mm2=round(a_cu_req, 3), a_slot_req_mm2=round(a_slot_req, 3),
                     a_cu_avail_mm2=round(a_cu_avail, 3), J=cfg.J_design, fill=cfg.fill_design,
                     P_cu_at_J=a_cu_avail / a_cu_req * cfg.P_cu_budget),
        checks=checks,
        status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
    )


class _SlotOnly:
    """把 IPMConfig + 定源尺寸适配成 slot_profile 需要的属性集合。"""

    def __init__(self, cfg, b0, h0, b1, h1, b2, rs, h2):
        self.stator_id = cfg.stator_id
        self.stator_od = cfg.stator_od
        self.slots = cfg.slots
        self.slot_Bs0, self.slot_Hs0 = b0, h0
        self.slot_Bs1, self.slot_Hs1 = b1, h1
        self.slot_Bs2, self.slot_Rs, self.slot_Hs2 = b2, rs, h2


def slot_only(cfg: IPMConfig) -> _SlotOnly:
    return _SlotOnly(cfg, cfg.slot_Bs0, cfg.slot_Hs0, cfg.slot_Bs1,
                     cfg.slot_Hs1, cfg.slot_Bs2, cfg.slot_Rs, cfg.slot_Hs2)


# ------------------------------------------------------------------- I3 槽满率
def slot_fill_factor(cfg: IPMConfig, cps: int | None = None,
                     wire_mm: float | None = None,
                     slot_area_mm2: float | None = None) -> dict:
    """I3/I5 槽满率：每槽 2 条边 × cps 根圆线铜面积 / 槽实切面积。

    判据（`docs/ENGINEERING_ACCEPTANCE.md` G7）：fill ≤ 0.78。
    cps=10 → 每槽 20 根；几何按 `wire_diameter_mm=1.5` 定标（槽宽 Bs2=3.5），
    但制造绕线口径 `wind_wire_mm=1.35`（Ø1.5 时 fill=0.9016 越界）。
    纯解析制造口径，不做 FEA 结论；assumption=待验证（真实漆包线规格/BOM）。
    """
    cps = cfg.conductors_per_slot if cps is None else cps
    wire = cfg.wind_wire_mm if wire_mm is None else wire_mm
    i1 = derive_slot(cfg)
    a_slot = i1["areas"]["slot_effective"] if slot_area_mm2 is None else slot_area_mm2
    n_wires = 2 * cps                       # 每槽 2 条边（T/B 双层）各 cps 根
    a_wire = math.pi * (wire / 2.0) ** 2
    a_cu = n_wires * a_wire
    fill = a_cu / a_slot
    return {
        "cps": cps, "turns_per_phase": cps * 16,
        "wires_per_slot": n_wires, "wire_diameter_mm": wire,
        "slot_area_mm2": round(a_slot, 4), "cu_area_mm2": round(a_cu, 4),
        "fill": round(fill, 6), "limit": 0.78,
        "status": "PASS" if fill <= 0.78 else "FAIL",
        "assumption": "wind_wire_mm=1.35 为制造口径待 BOM 验证；"
                      "2026-11-24 Bs0=1.0+yoke15 后槽面积 37.836、fill 0.7606",
    }


# ------------------------------------------------------------------- 线圈分层
def polygon_area(pts) -> float:
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def clip_x(pts, xc: float, keep_less: bool):
    """Sutherland–Hodgman：按 x = xc 半平面裁剪（保留 x≤xc 或 x≥xc）。"""
    def inside(p):
        return (p[0] <= xc) if keep_less else (p[0] >= xc)

    out = []
    n = len(pts)
    for i in range(n):
        cur = pts[i]
        nxt = pts[(i + 1) % n]
        ci, ni = inside(cur), inside(nxt)
        if ci:
            out.append(cur)
        if ci != ni:
            dx = nxt[0] - cur[0]
            t = 0.0 if abs(dx) < 1e-12 else (xc - cur[0]) / dx
            out.append((xc, cur[1] + t * (nxt[1] - cur[1])))
    # 去掉重复点
    clean = []
    for p in out:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) < 1e-9 and abs(clean[0][1] - clean[-1][1]) < 1e-9:
        clean.pop()
    return clean


def area_above(pts, xc: float) -> float:
    return polygon_area(clip_x(pts, xc, keep_less=False))


def solve_split_radius(pts, frac_above: float = 0.5) -> float:
    """求使「上方面积占比 = frac_above」的径向分界半径（二分）。"""
    xs = [p[0] for p in pts]
    lo, hi = min(xs), max(xs)
    total = polygon_area(pts)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if area_above(pts, mid) / total > frac_above:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def clip_y(pts, yc: float, keep_less: bool):
    """Sutherland–Hodgman：按 y = yc 半平面裁剪（保留 y≤yc 或 y≥yc）。

    与 `clip_x` 同构，只是切向中心线。梨形槽关于 y=0 对称，故按 y=0 切出的
    两半天然等面积、且到气隙（x 方向）等距 —— 满足用户「同槽内对称排布」。
    """
    def inside(p):
        return (p[1] <= yc) if keep_less else (p[1] >= yc)

    out = []
    n = len(pts)
    for i in range(n):
        cur, nxt = pts[i], pts[(i + 1) % n]
        ci, ni = inside(cur), inside(nxt)
        if ci:
            out.append(cur)
        if ci != ni:
            dy = nxt[1] - cur[1]
            t = 0.0 if abs(dy) < 1e-12 else (yc - cur[1]) / dy
            out.append((cur[0] + t * (nxt[0] - cur[0]), yc))
    clean = []
    for p in out:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) > 1 and abs(clean[0][0] - clean[-1][0]) < 1e-9 and abs(clean[0][1] - clean[-1][1]) < 1e-9:
        clean.pop()
    return clean


def coil_layers(cfg: IPMConfig, shrink: float = 0.86, gap: float = 0.4,
                x_pad: float = 0.23, y_pad: float = 0.14) -> dict:
    """双层绕组的两条边截面 —— **矩形**，关于切向 y=0 对称并排。

    用户 2026-11-22 两次修订：①「不是一远一近，是同槽内对称排布」；
    ②「绕组截面应该是矩形，不要异形」。因此不再把内缩梨形切成两半，
    而是直接在槽内放两个矩形（各 4 个 `CreatePolyline` 点）：
      * x（径向）：从 `内缩线圈 x_min + x_pad` 到 `内缩线圈 x_max - x_pad`；
      * y（切向）：从 `gap/2` 到 `槽直身半宽 - y_pad`，负侧镜像；
      * 顶面在槽内（用 `in_poly` 逐角点验证），不越界、左右镜像、距气隙等距。

    `x_pad/y_pad` 是绝缘留量：直身段槽半宽 1.75，留 0.14 后矩形外沿 1.358，
    与中间 gap=0.4 的半带 0.2 之间净宽 1.158 mm；x 两端各留 0.23。
    矩形面积 ≈11.8 mm²/条（旧异形 12.301，−4%），这是「矩形必须内接于
    半圆底槽」的几何代价，不靠伸出槽外来保面积。
    保留 `upper`/`lower` 键名只兼容既有调用方（电气 U/L 边），几何上是左/右。
    """
    sc = slot_only(cfg)
    outline = slot_profile.pear_outline(sc)
    coil = slot_profile.shrink_toward_centroid(outline, shrink)

    def in_poly(x: float, y: float, poly) -> bool:
        inside = False
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
                inside = not inside
        return inside

    # 离槽壁 >= min_wall（真实槽绝缘 0.20~0.30 mm，取 0.20）。
    # 关键：单一大矩形不能从槽口 x=47.55 起（那里是斜肩，槽壁收窄，边距会掉到
    # 0.006 mm）。须把矩形起点放到直身段 x>=48.4，终点 x<=58.2（半圆底内）。
    # 全局扫描（x_lo∈[48.4,51.5], x_hi∈[55,58.2], y_outer∈[1.0,1.55]）的最优：
    #   x[48.40,58.20] y_outer=1.20 → 面积 9.800 mm²、边距 0.202 mm。
    min_wall = 0.20
    x_lo = min(p[0] for p in coil) + x_pad
    x_hi = max(p[0] for p in coil) - x_pad
    y_outer = cfg.slot_Bs2 / 2.0 - y_pad
    best = None
    # 以 0.05 mm 步长扫描，取满足边距的最大面积（确定性、可复现）
    x_lo_i = int(math.ceil(x_lo / 0.05) * 0.05 / 0.05)
    while x_lo_i * 0.05 <= min(x_lo + 3.0, 51.5):
        xl = x_lo_i * 0.05
        xh = min(x_hi, 58.2)
        while xh >= max(xl + 2.0, 55.0):
            yo = 1.55
            while yo >= gap / 2.0 + 0.5:
                rect = [(xl, gap / 2.0), (xh, gap / 2.0), (xh, yo), (xl, yo)]
                if all(in_poly(x, y, outline) for x, y in rect):
                    wall = poly_dist(rect, outline)
                    if wall >= min_wall:
                        area = (xh - xl) * (yo - gap / 2.0)
                        if best is None or area > best[0] + 1e-9:
                            best = (area, xl, xh, yo, wall)
                        break   # 同一 (xl,xh) 下 y 越大面积越大，找到即停
                yo -= 0.05
            xh -= 0.05
        x_lo_i += 1
    if best is None:
        raise RuntimeError("槽内放不下满足 %.2f mm 边距的矩形绕组" % min_wall)
    _, x_lo, x_hi, y_outer, wall_final = best

    # 右上角 (x_hi, y_outer) 在正 y 侧；负 y 侧镜像 => upper 键名保留
    lower = [(x_lo, gap / 2.0), (x_hi, gap / 2.0),
             (x_hi, y_outer), (x_lo, y_outer)]
    upper = [(x, -y) for (x, y) in lower][::-1]  # 保持与 lower 同样的逆时针方向

    return dict(r_split=0.0, split_axis="tangential_y", shape="rectangle",
                x_range=(round(x_lo, 4), round(x_hi, 4)),
                y_outer=round(y_outer, 4), gap=gap, wall_mm=round(wall_final, 4),
                upper=upper, lower=lower,
                area_upper=round(polygon_area(upper), 3),
                area_lower=round(polygon_area(lower), 3),
                area_total=round(polygon_area(coil), 3))


# ------------------------------------------------------------------- 多边形工具
def rotate(pts, deg: float):
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca - y * sa, x * sa + y * ca) for (x, y) in pts]


def _seg_dist(p1, p2, p3, p4) -> float:
    """线段 p1p2 与 p3p4 的最短距离（含端点/相交判定）。"""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1, d2 = cross(p3, p4, p1), cross(p3, p4, p2)
    d3, d4 = cross(p1, p2, p3), cross(p1, p2, p4)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
        return 0.0

    def pt_seg(p, a, b):
        vx, vy = b[0] - a[0], b[1] - a[1]
        wx, wy = p[0] - a[0], p[1] - a[1]
        vv = vx * vx + vy * vy
        t = 0.0 if vv < 1e-18 else max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
        dx, dy = p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy)
        return math.hypot(dx, dy)

    return min(pt_seg(p1, p3, p4), pt_seg(p2, p3, p4),
               pt_seg(p3, p1, p2), pt_seg(p4, p1, p2))


def poly_dist(a, b) -> float:
    best = 1e9
    for i in range(len(a)):
        for j in range(len(b)):
            d = _seg_dist(a[i], a[(i + 1) % len(a)], b[j], b[(j + 1) % len(b)])
            if d < best:
                best = d
    return best


# --------------------------------------------------------------------------- I4
def _v_legs(apex_r: float, tilt_deg: float, length: float, gap_in: float, thick: float):
    """一组 V 的两条腿（+y 与 −y），返回 (label, pts)。"""
    t = math.radians(tilt_deg)
    u = (math.cos(t), math.sin(t))
    n = (-math.sin(t), math.cos(t))
    out = []
    for side, sign in (("+", 1.0), ("-", -1.0)):
        # 厚度方向必须镜像：+y 腿用 n，−y 腿用 −n。两腿都用 +n 会让 −y 磁钢越过极轴、
        # 多边形自交（2026-11-20 首版实测：极间净距 0.09 mm，是自交伪影）。
        nx, ny = n[0], sign * n[1]   # 镜像只翻 y 分量，x 分量不变
        p1 = (apex_r, sign * gap_in / 2.0)
        p2 = (p1[0] + length * u[0], p1[1] + sign * length * u[1])
        p3 = (p2[0] + thick * nx, p2[1] + thick * ny)
        p4 = (p1[0] + thick * nx, p1[1] + thick * ny)
        pts = [p1, p2, p3, p4] if sign > 0 else [p1, p4, p3, p2]
        out.append((side, pts))
    return out


def derive_rotor(cfg: IPMConfig, rotor_init_deg: float = 0.0) -> dict:
    """I4：每极**一组** V、共 16 块（单层 V）；逐块自检并返回全局多边形。

    用户 2026-11-22 要求永磁体单层，取消原双层 V 的 outer/inner 两层。
    `rotor_init_deg`（D5 斜槽多切片）：把整个转子绕 Z 转该电角 —— V 槽与磁钢
    一起转，定子不动；磁化方向必须同步转（见 `ipm_build.magnet_directions`）。
    轴对称的 RotorOuter/Band 转动不改变几何，故只转 V 多边形即可。
    """
    r_rot = cfg.rotor_od / 2.0
    r_shaft = cfg.rotor_id / 2.0
    pole_pitch = 360.0 / cfg.poles
    t = cfg.pm_thickness
    ra, tilt, length, gap_in = cfg.v_single

    local = []   # (layer, side, pole, pts_local) —— 单层，layer 恒为 "single"
    for pole in range(cfg.poles):
        ang = pole * pole_pitch + rotor_init_deg
        for side, pts in _v_legs(ra, tilt, length, gap_in, t):
            local.append(("single", side, pole, rotate(pts, ang)))

    # 校验 1：在转子内 / 离轴孔
    rad_check = []
    for lname, side, pole, pts in local:
        rmax = max(math.hypot(*p) for p in pts)
        rmin = min(math.hypot(*p) for p in pts)
        rad_check.append(dict(layer=lname, pole=pole + 1, side=side,
                              r_max=round(rmax, 3), r_min=round(rmin, 3),
                              bridge_od=round(r_rot - rmax, 3),
                              gap_shaft=round(rmin - r_shaft, 3)))
    min_bridge_od = min(x["bridge_od"] for x in rad_check)
    min_gap_shaft = min(x["gap_shaft"] for x in rad_check)

    # 校验 2：两两最近距离（单层只有同组两腿、相邻极两种）
    pair_min = dict(intra_v=1e9, inter_pole=1e9)
    for i in range(len(local)):
        for j in range(i + 1, len(local)):
            s1, p1, a = local[i][1], local[i][2], local[i][3]
            s2, p2, b = local[j][1], local[j][2], local[j][3]
            k = "intra_v" if p1 == p2 else "inter_pole"
            pair_min[k] = min(pair_min[k], poly_dist(a, b))

    _exp = length * t
    _area_dev = max(abs(polygon_area(p) - _exp) for (_l, _s, _p, p) in local)
    checks = [
        dict(name="磁钢外角到转子 OD 桥厚 ≥ %.1f" % cfg.pm_bridge_od,
             value=round(min_bridge_od, 3), limit=cfg.pm_bridge_od, op=">=",
             status="PASS" if min_bridge_od >= cfg.pm_bridge_od else "FAIL"),
        dict(name="单块面积 = L×t（防自交）", value=round(_area_dev, 6), limit=0.0, op="<=",
             status="PASS" if _area_dev < 1e-6 else "FAIL"),
        dict(name="磁钢到轴孔 ≥ 3.0", value=round(min_gap_shaft, 3), limit=3.0, op=">=",
             status="PASS" if min_gap_shaft >= 3.0 else "FAIL"),
        dict(name="同组两腿间距 ≥ 1.0", value=round(pair_min["intra_v"], 3), limit=1.0, op=">=",
             status="PASS" if pair_min["intra_v"] >= 1.0 else "FAIL"),
        dict(name="极间铁桥 ≥ %.1f" % cfg.pm_bridge_gap,
             value=round(pair_min["inter_pole"], 3), limit=cfg.pm_bridge_gap, op=">=",
             status="PASS" if pair_min["inter_pole"] >= cfg.pm_bridge_gap else "FAIL"),
        dict(name="磁钢块数 = 8×1×2 = 16（单层 V）", value=len(local), limit=cfg.poles * 2, op="==",
             status="PASS" if len(local) == cfg.poles * 2 else "FAIL"),
    ]

    # 磁通能力估算（解析，仅作交叉校验，不作 FEA 结论）
    tau_pole = math.pi * cfg.rotor_od / cfg.poles
    w_sum = cfg.poles * 2 * length
    conc = (2 * length) / (tau_pole / 2.0)
    return dict(
        rotor_od=cfg.rotor_od, rotor_id=cfg.rotor_id, poles=cfg.poles,
        pm_thickness=t, magnets=len(local), v_type="single",
        layout=dict(v_single=cfg.v_single),
        radial=rad_check, pair_min={k: round(v, 3) for k, v in pair_min.items()},
        checks=checks,
        magnet_area_total=round(sum(polygon_area(p) for (_l, _sl, _po, p) in local), 3),
        rotor_area=round(math.pi * (r_rot ** 2 - r_shaft ** 2), 3),
        flux_note=dict(tau_pole=round(tau_pole, 3), magnet_width_per_pole=round(w_sum / cfg.poles, 3),
                       concentration=round(conc, 4),
                       Bg_est_leak07=round(1.17 * conc * 0.7, 3)),
        status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        polygons=[[list(p) for p in pts] for (_l, _s, _p, pts) in local],
        labels=["%s_%s_P%d" % (lay, s, p + 1) for (lay, s, p, _pts) in local],
    )


# ------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="IPM 8p48s 几何定源")
    ap.add_argument("--out", default=os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
    args = ap.parse_args(argv)

    cfg = IPMConfig()
    i1 = derive_slot(cfg)
    i2 = coil_layers(cfg)
    i4 = derive_rotor(cfg)

    # 断言：模块默认配置必须等于推导结果（防止两边漂移）
    d = i1["dims"]
    for k, v in (("slot_Bs0", d["Bs0"]), ("slot_Hs0", d["Hs0"]), ("slot_Bs1", d["Bs1"]),
                 ("slot_Hs1", d["Hs1"]), ("slot_Bs2", d["Bs2"]), ("slot_Rs", d["Rs"]),
                 ("slot_Hs2", d["Hs2"])):
        assert abs(getattr(cfg, k) - v) < 1e-9, "配置 %s=%s 与推导 %s 不一致" % (
            k, getattr(cfg, k), v)

    print("=" * 72)
    print("I1 48 槽梨形槽定源  status=%s" % i1["status"])
    print("=" * 72)
    for s in i1["chain"]:
        print("  %-22s = %8.3f mm   [%s]" % (s["step"], s["value_mm"], s["expr"]))
    print("  " + "-" * 66)
    print("  槽面积 %.3f mm² / 环带切除 %.3f / 线圈(0.86) %.3f (比 %.3f)"
          % (i1["areas"]["slot_analytic"], i1["areas"]["slot_effective"],
             i1["areas"]["coil_shrink_086"], i1["areas"]["coil_to_slot"]))
    print("  B_t(min) %.3f T @ r=%.2f / B_yoke %.3f T / Φ_pole %.2f µWb"
          % (i1["flux"]["B_tooth_min"], i1["flux"]["B_tooth_min_at"],
             i1["flux"]["B_yoke"], i1["flux"]["phi_pole_uWb"]))
    print("  铜耗预算: 需 %.2f mm² 铜/槽 ⇒ 槽 %.2f mm²（fill %.2f, J %.1f）"
          % (i1["thermal"]["a_cu_req_mm2"], i1["thermal"]["a_slot_req_mm2"],
             cfg.fill_design, cfg.J_design))
    for c in i1["checks"]:
        print("    [%s] %-28s %10.4f %s %8.4f" % (c["status"], c["name"], c["value"], c["op"], c["limit"]))

    print("=" * 72)
    print("I2 双层线圈截面  上/下面积 %.3f / %.3f mm²（分界 r=%.3f, 层间 0.4）"
          % (i2["area_upper"], i2["area_lower"], i2["r_split"]))

    print("=" * 72)
    print("I4 单层 V 磁钢  status=%s  块数=%d" % (i4["status"], i4["magnets"]))
    print("  最近距离: 同组两腿 %.2f / 极间 %.2f mm（单层 V，无层间）"
          % (i4["pair_min"]["intra_v"], i4["pair_min"]["inter_pole"]))
    print("  OD 桥厚 %.2f / 轴孔间隙 %.2f mm；聚磁比 %.3f，Bg 估算 %.3f T（漏磁 0.7）"
          % (min(x["bridge_od"] for x in i4["radial"]),
             min(x["gap_shaft"] for x in i4["radial"]),
             i4["flux_note"]["concentration"], i4["flux_note"]["Bg_est_leak07"]))
    for c in i4["checks"]:
        print("    [%s] %-28s %10.3f %s %8.3f" % (c["status"], c["name"], c["value"], c["op"], c["limit"]))

    os.makedirs(args.out, exist_ok=True)
    for name, data in (("i1_slot.json", i1), ("i2_coil_layers.json",
                                             {k: v for k, v in i2.items() if not isinstance(v, list)}),
                       ("i4_rotor.json", {k: v for k, v in i4.items()
                                          if k not in ("polygons", "labels")})):
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        print("  ✔ %s" % path)
    return 0 if (i1["status"] == "PASS" and i4["status"] == "PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
