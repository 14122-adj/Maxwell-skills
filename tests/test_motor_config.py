"""MotorConfig 几何派生回归测试（周目标 G1 / 审计 P1）。

对应缺陷：``rotor_od`` 曾硬编码为 36 槽机型的 135.6 mm，导致 ``stator_id < 135.6``
的中小机型经 ``scripts/main.py`` 从零建模必失败（rc=1「转子外径必须小于定子内径」）。

约定（与 SKILL.md §1 一致）：
    气隙未显式给出时按 δ = clamp(0.3 + Dso/400, 0.35, 2.0) mm 推导，
    转子外径按 Dro = Dsi − 2δ 派生；显式输入的气隙/转子外径永不被覆盖。
"""
from __future__ import annotations

import pytest

from motor_config import (
    MotorConfig,
    create_36slot_industrial,
    create_motor_from_input,
    derive_airgap,
)


class TestAirgapFormula:
    """δ = 0.3 + Dso/400，并夹在 [0.35, 2.0] mm。"""

    @pytest.mark.parametrize(
        "stator_od, expected",
        [
            (150.0, 0.675),   # 25 N·m 8p12s 机型（设计冻结值）
            (210.0, 0.825),   # 36 槽工业机型
            (80.0, 0.500),
            (40.0, 0.400),    # 未触下限
            (10.0, 0.350),    # clamp 下限
            (1200.0, 2.000),  # clamp 上限
        ],
    )
    def test_formula(self, stator_od: float, expected: float) -> None:
        assert derive_airgap(stator_od) == pytest.approx(expected, abs=1e-9)


class TestDerivedGeometry:
    """缺省几何由定子尺寸派生，小机型不再是必败路径。"""

    def test_small_machine_dsi_lt_135_6(self) -> None:
        """Dsi=93 < 135.6：正是本次修复要救回的 25 N·m 机型。"""
        cfg = create_motor_input("slots=12 poles=8 stator_od=150 stator_id=93")
        assert cfg.airgap == pytest.approx(0.675)
        assert cfg.rotor_od == pytest.approx(91.65)
        assert cfg.rotor_od / 2 == pytest.approx(45.825)  # 生成物 RotorOuter
        assert cfg.band_radius == pytest.approx((91.65 + 93.0) / 2)
        assert not [i for i in cfg.validate() if i.startswith("ERROR")]

    def test_large_machine_dsi_gt_135_6(self) -> None:
        """Dsi=180 > 135.6：大机型同样走派生，且气隙随 Dso 变粗。"""
        cfg = create_motor_input("slots=36 poles=4 stator_od=210 stator_id=180")
        assert cfg.airgap == pytest.approx(0.825)
        assert cfg.rotor_od == pytest.approx(180.0 - 2 * 0.825)
        assert not [i for i in cfg.validate() if i.startswith("ERROR")]

    def test_default_config_is_self_consistent(self) -> None:
        """裸 MotorConfig() 也不应再留下 135.6/0.2 这对不自洽的默认值。"""
        cfg = MotorConfig()
        assert cfg.airgap == pytest.approx(derive_airgap(cfg.stator_od))
        assert cfg.rotor_od == pytest.approx(cfg.stator_id - 2 * cfg.airgap)


class TestExplicitGeometryWins:
    """显式输入（含预设）必须原样保留，派生逻辑不得覆盖。"""

    def test_explicit_rotor_od_is_kept(self) -> None:
        cfg = create_motor_input("stator_od=150 stator_id=93 rotor_od=91.0")
        assert cfg.rotor_od == pytest.approx(91.0)
        assert cfg.airgap == pytest.approx(1.0)  # (93-91)/2，由显式几何反推

    def test_explicit_airgap_and_rotor_od_are_kept(self) -> None:
        cfg = create_motor_input(
            "stator_od=150 stator_id=93 rotor_od=92.0 airgap=0.5"
        )
        assert cfg.airgap == pytest.approx(0.5)
        assert cfg.rotor_od == pytest.approx(92.0)

    def test_preset_unchanged(self) -> None:
        cfg = create_36slot_industrial()
        assert cfg.rotor_od == pytest.approx(135.6)
        assert cfg.airgap == pytest.approx(0.2)
        assert not [i for i in cfg.validate() if i.startswith("ERROR")]


class TestUpdateAndValidation:
    """update() 后仍保持几何自洽；非法几何要报 ERROR 而非静默通过。"""

    def test_update_rederives_auto_geometry(self) -> None:
        cfg = MotorConfig(stator_od=150, stator_id=93)
        cfg.update(stator_id=120)
        assert cfg.rotor_od == pytest.approx(120.0 - 2 * 0.675)

    def test_update_with_explicit_rotor_od(self) -> None:
        """显式改写转子外径后，派生气隙随之重解，几何保持自洽而非残留旧值。"""
        cfg = MotorConfig(stator_od=150, stator_id=93)
        cfg.update(rotor_od=90.0)
        assert cfg.rotor_od == pytest.approx(90.0)
        assert cfg.airgap == pytest.approx((93.0 - 90.0) / 2)
        assert not [i for i in cfg.validate() if i.startswith("WARNING: 气隙")]

    def test_inverted_geometry_flagged(self) -> None:
        cfg = MotorConfig(stator_od=150, stator_id=93, rotor_od=95.0, airgap=1.0)
        assert any(i.startswith("ERROR") for i in cfg.validate())

    def test_to_dict_has_no_internal_markers(self) -> None:
        d = MotorConfig().to_dict()
        assert "rotor_od" in d and "airgap" in d
        assert not [k for k in d if k.startswith("_")]


def create_motor_input(params: str) -> MotorConfig:
    """关键词串 → MotorConfig，走与 ``scripts/main.py --params`` 相同的入口。"""
    return create_motor_from_input(params, input_type="keyword")
