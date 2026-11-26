#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E8/E6 能力桥回归测试 —— dry_run 全通过，不依赖 Maxwell / Motor-CAD。"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "projects", "e8e6")
    ),
)

from e8e6_bridge import (  # noqa: E402
    E6_BMIN_MIN_T,
    E6_BMIN_TARGET_T,
    E6_SF_MIN,
    E6_SF_TARGET,
    E8_EFFICIENCY_MIN,
    E8_EFFICIENCY_TARGET,
    G5_MAGNET_MAX_C,
    G5_WINDING_HOTSPOT_MAX_C,
    E8E6Bridge,
)


@pytest.fixture
def bridge() -> E8E6Bridge:
    return E8E6Bridge(dry_run=True)


def test_criteria_match_acceptance_doc() -> None:
    """判据钉死 ENGINEERING_ACCEPTANCE.md §2，防事后改阈值。"""
    assert E8_EFFICIENCY_TARGET == 0.938
    assert E8_EFFICIENCY_MIN == 0.930
    assert E6_BMIN_TARGET_T == 0.30
    assert E6_BMIN_MIN_T == 0.20
    assert E6_SF_TARGET == 2.5
    assert E6_SF_MIN == 2.0
    assert G5_WINDING_HOTSPOT_MAX_C == 155.0
    assert G5_MAGNET_MAX_C == 120.0


def test_dry_run_efficiency(bridge: E8E6Bridge) -> None:
    out = bridge.compute_efficiency(p_mech_w=3508.3, losses_w={"P_cu": 138.6})
    assert out["source"] == "DRY_RUN_MOCK"
    assert out["verdict"] == "MOCK_PASS"
    assert out["criterion"]["target"] == E8_EFFICIENCY_TARGET


def test_dry_run_demag(bridge: E8E6Bridge) -> None:
    out = bridge.check_demag()
    assert out["source"] == "DRY_RUN_MOCK"
    assert out["temperature_c"] == 150.0
    assert out["criterion"]["b_min_min_t"] == E6_BMIN_MIN_T
    assert out["verdict"] == "MOCK_PASS"


def test_dry_run_core_loss_gate(bridge: E8E6Bridge) -> None:
    out = bridge.core_loss_coefficients("M270_35A")
    assert out["status"] == "MISSING"
    assert out["material"] == "M270_35A"
    assert "经验值" in out["note"]


def test_dry_run_thermal(bridge: E8E6Bridge) -> None:
    out = bridge.thermal_nodes()
    assert out["source"] == "DRY_RUN_MOCK"
    assert out["verdict"] == "MOCK_PASS"
    assert out["winding_hotspot_c"] <= G5_WINDING_HOTSPOT_MAX_C
    assert out["magnet_c"] <= G5_MAGNET_MAX_C


def test_dry_run_status(bridge: E8E6Bridge) -> None:
    out = bridge.status()
    assert out["motorcad_route"] == "BLOCKED_I30_FLEXNET_8544"
    assert out["maxwell_route"] == "ACTIVE"
    assert out["e8_gate"] == "MISSING"
    assert out["e6_source"] == "PENDING_REAL_FEA"
    assert out["dry_run"] is True


def test_real_mode_efficiency_arithmetic() -> None:
    bridge = E8E6Bridge(dry_run=False)
    # η = 3508.3 / (3508.3 + 228.6) = 0.93884... >= 0.938
    out = bridge.compute_efficiency(
        p_mech_w=3508.3,
        losses_w={"P_cu": 138.6, "P_fe": 90.0},
        source="UNIT_TEST",
    )
    assert out["source"] == "UNIT_TEST"
    assert out["verdict"] == "PASS_TARGET"
    assert 0.938 < out["efficiency"] < 0.939


def test_real_mode_efficiency_fail() -> None:
    bridge = E8E6Bridge(dry_run=False)
    out = bridge.compute_efficiency(
        p_mech_w=100.0, losses_w={"P_cu": 20.0}, source="UNIT_TEST"
    )
    assert out["verdict"] == "FAIL"
    assert abs(out["efficiency"] - 100.0 / 120.0) < 1e-6


def test_real_mode_demag_thresholds() -> None:
    bridge = E8E6Bridge(dry_run=False)
    target = bridge.check_demag(b_min_t=0.31, sf=2.6, source="UNIT_TEST")
    assert target["verdict"] == "PASS_TARGET"
    minimum = bridge.check_demag(b_min_t=0.21, sf=2.1, source="UNIT_TEST")
    assert minimum["verdict"] == "PASS_MIN"
    failed = bridge.check_demag(b_min_t=0.19, sf=1.9, source="UNIT_TEST")
    assert failed["verdict"] == "FAIL"


def test_real_mode_demag_requires_input() -> None:
    bridge = E8E6Bridge(dry_run=False)
    with pytest.raises(ValueError, match="b_min_t"):
        bridge.check_demag()
    with pytest.raises(ValueError, match="150C"):
        bridge.check_demag(b_min_t=0.5, temperature_c=80.0)


def test_real_mode_core_loss_gate_on_this_machine() -> None:
    """本机 materials.py 确无 Kh/Kc/Ke —— 钉住 E8 硬 gate，防经验值回潮。"""
    bridge = E8E6Bridge(dry_run=False)
    out = bridge.core_loss_coefficients("M270_35A")
    assert out["status"] == "MISSING", out
    assert out["coefficients"]["Kh"] is False


def test_real_mode_thermal_reads_existing_lptn() -> None:
    bridge = E8E6Bridge(dry_run=False)
    out = bridge.thermal_nodes()
    assert out["source"] == "ANALYTIC_LPTN_S4_LOSS"
    assert out["verdict"] == "PASS"
    assert out["magnet_c"] == 76.06
