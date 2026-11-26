#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E8 效率 / E6 退磁 / 热网络 —— Maxwell 原生能力桥
=====================================================

为什么有这个文件
----------------
Motor-CAD 2025.2.1 的 license 是第三方签发（Team SolidSQUAD-SSQ），
`motorcad` feature checkout 报 FlexNet -8,544，P0 连接验证 BLOCKED（账本 I30）。
本模块改走 Maxwell 原生链路补齐 E8/E6/热网络能力，不依赖 Motor-CAD。

设计原则（继承 scripts/maxwell_bridge.py 的 dry_run 抽象）
----------------------------------------------------------
1. dry_run=True 时不依赖 Maxwell / 不读真机文件即可跑通全部方法与返回结构，CI 可测。
2. 判据来自 docs/ENGINEERING_ACCEPTANCE.md §2，硬编码在此并注明来源；
   不因结果不好而改阈值。
3. 不编造数据：M270-35A 缺 Kh/Kc/Ke 时 core_loss_coefficients() 明确返回
   status=MISSING，E8 真机 FEA 被 gate 拦住，不许用经验值填。
4. mock 值一律带 source="DRY_RUN_MOCK"，与真机数据严格区分。

判据来源（docs/ENGINEERING_ACCEPTANCE.md §2 电磁性能判据表）
-----------------------------------------------------------
- 效率 η: 工程目标 >=93.8%, 验收下限 >=93.0%
- 退磁 B_min (150C 三相短路): 工程目标 >=0.30 T, 验收下限 >=0.20 T
- 退磁安全系数 SF: 工程目标 >=2.5, 验收下限 >=2.0
- 绕组热点 <=155C (F 级), 磁钢 <=120C (N35) —— G5 热
"""
from __future__ import annotations

import json
import os
from typing import Any

# ── 判据（来自 ENGINEERING_ACCEPTANCE.md §2，禁止事后修改）────────
E8_EFFICIENCY_TARGET = 0.938
E8_EFFICIENCY_MIN = 0.930
E6_BMIN_TARGET_T = 0.30
E6_BMIN_MIN_T = 0.20
E6_SF_TARGET = 2.5
E6_SF_MIN = 2.0
G5_WINDING_HOTSPOT_MAX_C = 155.0
G5_MAGNET_MAX_C = 120.0

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_MATERIALS_PY = os.path.join(
    _ROOT, "projects", "25Nm_PMSM", "maxwell_model", "materials.py"
)
_THERMAL_JSON = os.path.join(_ROOT, "projects", "results", "thermal_summary.json")


class E8E6Bridge:
    """E8/E6/热网络统一入口，dry_run 模式可脱离 Maxwell 运行。"""

    def __init__(self, dry_run: bool = True) -> None:
        self.dry_run = bool(dry_run)

    # ── E8 效率 ──────────────────────────────────────────────
    def compute_efficiency(
        self,
        p_mech_w: float,
        losses_w: dict[str, float],
        source: str = "FEA",
    ) -> dict[str, Any]:
        """由机械功率与分项损耗计算效率。

        η = P_mech / (P_mech + ΣP_loss)。losses_w 的键仅作留档，不参与判据。
        dry_run 下返回 mock 值（source=DRY_RUN_MOCK），绝不冒充真机。
        """
        if self.dry_run:
            return {
                "efficiency": 0.9387,
                "p_mech_w": 3508.3,
                "p_loss_total_w": 228.6,
                "source": "DRY_RUN_MOCK",
                "criterion": {
                    "target": E8_EFFICIENCY_TARGET,
                    "min": E8_EFFICIENCY_MIN,
                },
                "verdict": "MOCK_PASS",
            }
        if p_mech_w <= 0:
            raise ValueError("p_mech_w must be positive")
        p_loss = float(sum(float(v) for v in losses_w.values()))
        eta = p_mech_w / (p_mech_w + p_loss)
        if eta >= E8_EFFICIENCY_TARGET:
            verdict = "PASS_TARGET"
        elif eta >= E8_EFFICIENCY_MIN:
            verdict = "PASS_MIN"
        else:
            verdict = "FAIL"
        return {
            "efficiency": round(eta, 6),
            "p_mech_w": round(float(p_mech_w), 4),
            "p_loss_total_w": round(p_loss, 4),
            "p_loss_breakdown_w": {
                str(k): round(float(v), 4) for k, v in losses_w.items()
            },
            "source": source,
            "criterion": {
                "target": E8_EFFICIENCY_TARGET,
                "min": E8_EFFICIENCY_MIN,
            },
            "verdict": verdict,
        }

    # ── E6 退磁 ──────────────────────────────────────────────
    def check_demag(
        self,
        b_min_t: float | None = None,
        sf: float | None = None,
        temperature_c: float = 150.0,
        source: str = "FEA",
    ) -> dict[str, Any]:
        """150C 三相短路退磁判据（B_min 与 SF 双指标）。

        dry_run 下不要求入参；真机模式下 b_min_t 必填且 temperature_c 必须 >=150。
        """
        if self.dry_run:
            return {
                "b_min_t": 0.627,
                "sf": 3.1,
                "temperature_c": temperature_c,
                "source": "DRY_RUN_MOCK",
                "criterion": {
                    "b_min_target_t": E6_BMIN_TARGET_T,
                    "b_min_min_t": E6_BMIN_MIN_T,
                    "sf_target": E6_SF_TARGET,
                    "sf_min": E6_SF_MIN,
                },
                "verdict": "MOCK_PASS",
            }
        if b_min_t is None:
            raise ValueError("b_min_t is required when dry_run=False")
        if temperature_c < 150.0:
            raise ValueError(
                "E6 criterion is defined at >=150C; got %s" % temperature_c
            )
        b_ok = float(b_min_t) >= E6_BMIN_MIN_T
        b_target_ok = float(b_min_t) >= E6_BMIN_TARGET_T
        sf_value = None if sf is None else float(sf)
        sf_ok = sf_value is not None and sf_value >= E6_SF_MIN
        sf_target_ok = sf_value is not None and sf_value >= E6_SF_TARGET
        if b_target_ok and (sf_value is None or sf_target_ok):
            verdict = "PASS_TARGET"
        elif b_ok and (sf_value is None or sf_ok):
            verdict = "PASS_MIN"
        else:
            verdict = "FAIL"
        return {
            "b_min_t": round(float(b_min_t), 6),
            "sf": sf_value,
            "temperature_c": float(temperature_c),
            "source": source,
            "criterion": {
                "b_min_target_t": E6_BMIN_TARGET_T,
                "b_min_min_t": E6_BMIN_MIN_T,
                "sf_target": E6_SF_TARGET,
                "sf_min": E6_SF_MIN,
            },
            "verdict": verdict,
        }

    # ── E8 前置：铁耗系数 ────────────────────────────────────
    def core_loss_coefficients(self, material: str = "M270_35A") -> dict[str, Any]:
        """检查 Maxwell 材料定义是否含 Kh/Kc/Ke 铁耗系数。

        账本 E8 明确：M270_35A 无 Kh/Kc/Ke，缺厂商标定曲线，
        补系数前不许用经验值跑 CoreLoss。此方法是真机 E8 的硬 gate。
        """
        if self.dry_run:
            return {
                "material": material,
                "status": "MISSING",
                "coefficients": {},
                "source": "DRY_RUN_MOCK",
                "note": (
                    "DRY_RUN mock mirrors known blocker (账本 E8): "
                    "M270_35A 缺 Kh/Kc/Ke，禁止用经验值跑 CoreLoss；"
                    "本次未做真实材料扫描"
                ),
            }
        if not os.path.isfile(_MATERIALS_PY):
            return {
                "material": material,
                "status": "FILE_NOT_FOUND",
                "coefficients": {},
                "source": os.path.basename(_MATERIALS_PY),
                "note": "材料脚本不存在，无法定源",
            }
        with open(_MATERIALS_PY, encoding="utf-8") as _f:
            text = _f.read()
        lowered = text.lower()
        found = {
            key: key.lower() in lowered
            for key in ("Kh", "Kc", "Ke", "core_loss", "coreloss")
        }
        # 只认 Kh/Kc/Ke 三系数同时存在；core_loss 字样单独不算（可能是注释）
        has_all = all(found[k] for k in ("Kh", "Kc", "Ke"))
        return {
            "material": material,
            "status": "PRESENT" if has_all else "MISSING",
            "coefficients": {k: found[k] for k in ("Kh", "Kc", "Ke")},
            "source": os.path.relpath(_MATERIALS_PY, _ROOT).replace("\\", "/"),
            "note": (
                "三系数齐备，可跑 CoreLoss"
                if has_all
                else "缺 Kh/Kc/Ke，禁止用经验值跑 CoreLoss；需厂商标定曲线（账本 E8）"
            ),
        }

    # ── G5 热网络 ────────────────────────────────────────────
    def thermal_nodes(self) -> dict[str, Any]:
        """读取现有 7 节点 LPTN 结果并做 G5 判据。

        现有 thermal_summary.json 是解析 LPTN（S4 损耗输入），非 FEA 热网络；
        source 字段如实标注，不许当真机数据。
        """
        if self.dry_run:
            return {
                "winding_hotspot_c": 89.47,
                "magnet_c": 76.06,
                "source": "DRY_RUN_MOCK",
                "verdict": "MOCK_PASS",
            }
        if not os.path.isfile(_THERMAL_JSON):
            raise FileNotFoundError(_THERMAL_JSON)
        with open(_THERMAL_JSON, encoding="utf-8") as _f:
            data = json.load(_f)
        scenario = data["scenarios"]["forced_air_pm4seg"]
        hotspot = float(scenario["hotspot_C"])
        magnet = float(scenario["nodes_C"]["MAGNET"])
        ok = (
            hotspot <= G5_WINDING_HOTSPOT_MAX_C
            and magnet <= G5_MAGNET_MAX_C
        )
        return {
            "winding_hotspot_c": hotspot,
            "magnet_c": magnet,
            "source": "ANALYTIC_LPTN_S4_LOSS",
            "criterion": {
                "winding_hotspot_max_c": G5_WINDING_HOTSPOT_MAX_C,
                "magnet_max_c": G5_MAGNET_MAX_C,
            },
            "verdict": "PASS" if ok else "FAIL",
        }

    def status(self) -> dict[str, Any]:
        """汇总当前 E8/E6/热网络能力状态（供报告与账本引用）。"""
        core = self.core_loss_coefficients()
        thermal = self.thermal_nodes()
        return {
            "motorcad_route": "BLOCKED_I30_FLEXNET_8544",
            "maxwell_route": "ACTIVE",
            "e8_gate": core["status"],
            "e8_note": core["note"],
            "thermal_source": thermal["source"],
            "thermal_verdict": thermal["verdict"],
            "e6_source": "PENDING_REAL_FEA",
            "dry_run": self.dry_run,
        }


__all__ = [
    "E8E6Bridge",
    "E8_EFFICIENCY_TARGET",
    "E8_EFFICIENCY_MIN",
    "E6_BMIN_TARGET_T",
    "E6_BMIN_MIN_T",
    "E6_SF_TARGET",
    "E6_SF_MIN",
    "G5_WINDING_HOTSPOT_MAX_C",
    "G5_MAGNET_MAX_C",
]
