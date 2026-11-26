#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 贴片平行充磁建模护栏（2026-11-26）

钉住三件在 SPM_DESIGN.md 里写错会静默出错的事：
  1. 贴片外表面必须回到 rotor_od/2=45.825 ⇒ 气隙仍 0.675、Band 仍 46.1625；
     若按 SPM_DESIGN.md §2 的 43.7825 会把 Band 切进磁钢。
  2. 8 块磁钢极性 NSNSNSNS；平行充磁矢量 = sign·u(k·45°)，不是辐射状。
  3. 定子/绕组/网格与 IPM 同源，只有转子段变化（sheet=109=5+8+96）。
"""
import math
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJ = os.path.join(_HERE, "projects", "IPM_8p48s")
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

import spm_build  # noqa: E402


def test_spm_geometry_selfconsistent():
    cfg = spm_build.SPMConfig()
    snap = spm_build.spm_snapshot(cfg)
    assert snap["core_od"] == pytest.approx(86.89, abs=1e-9)
    assert snap["pm_t"] == pytest.approx(2.38, abs=1e-9)
    # 磁钢外表面 + 铁芯半径 = 气隙内边界
    assert snap["pm_outer_r"] == pytest.approx(45.825, abs=1e-9)
    assert snap["pm_inner_r"] == pytest.approx(43.445, abs=1e-9)
    # I32：铁芯缩 0.02mm 装配胶缝，避免与贴片共面 intersect
    assert snap["iron_r"] == pytest.approx(43.425, abs=1e-9)
    assert snap["glue_gap"] == pytest.approx(0.02, abs=1e-9)
    assert snap["pm_inner_r"] - snap["iron_r"] == pytest.approx(0.02, abs=1e-9)
    assert snap["airgap"] == pytest.approx(0.675, abs=1e-9)
    # Band 与 AirgapRing 沿用 IPM（不重复扣气隙）
    assert snap["band_r"] == pytest.approx(46.1625, abs=1e-9)
    assert snap["ring_inner_r"] == pytest.approx(46.1625, abs=1e-9)
    assert snap["ring_area"] == pytest.approx(math.pi * (46.5 ** 2 - 46.1625 ** 2), rel=1e-9)
    assert snap["n_sheets"] == 109


def test_spm_magnets_polarity_and_vectors():
    cfg = spm_build.SPMConfig()
    mags = spm_build.spm_magnets(cfg)
    assert len(mags) == 8
    assert "".join("N" if m["sign"] > 0 else "S" for m in mags) == "NSNSNSNS"
    for i, m in enumerate(mags):
        a = math.radians(i * 45.0)
        s = 1.0 if i % 2 == 0 else -1.0
        assert m["gx"] == pytest.approx(s * math.cos(a), abs=1e-9)
        assert m["gy"] == pytest.approx(s * math.sin(a), abs=1e-9)
        assert math.hypot(m["gx"], m["gy"]) == pytest.approx(1.0, abs=1e-9)
        # 极轴相邻差 45°，不是相邻矢量严格反号（后者是辐射状错误实现）
        assert m["center_deg"] == pytest.approx(i * 45.0, abs=1e-9)
    # 8 块面积一致（弧形瓦片，极弧 0.85）
    areas = [m["area"] for m in mags]
    assert max(areas) - min(areas) < 1e-6


def test_spm_magnet_radii_no_airgap_intrusion():
    cfg = spm_build.SPMConfig()
    r_core = cfg.spm_core_od / 2
    r_out = cfg.rotor_od / 2
    for m in spm_build.spm_magnets(cfg):
        rs = [math.hypot(x, y) for (x, y) in m["pts"]]
        assert min(rs) == pytest.approx(r_core, abs=1e-6)
        assert max(rs) == pytest.approx(r_out, abs=1e-6)
        # 任一磁钢点都不得越过气隙内边界
        assert max(rs) <= cfg.stator_id / 2 - cfg.airgap + 1e-6


def test_spm_build_script_has_required_blocks():
    cfg = spm_build.SPMConfig()
    text = spm_build.build_script(cfg, log_path="D:/ANSYS_Run/spm_m1.log")
    compile(text, "<spm>", "exec")
    assert text.count('oDefinitionManager.EditMaterial("NdFe35_') == 8
    assert '"DirComp1:=", "1", "DirComp2:=", "0"' in text
    assert '"DirComp1:=", "-0.707107", "DirComp2:=", "-0.707107"' in text
    assert 'Mesh_Airgap' in text and '"MaxLength:=", "0.15mm"' in text
    assert 'band_r = (91.65 + 93) / 4.0' in text
    assert text.count("CPS = 10") == 1
    assert "CURRENTS = " in text and '"A": "0A"' in text


def test_spm_core_od_single_variable_scan():
    """厚度单变量只改 core_od，气隙/Band/环自动保持。"""
    cfg = spm_build.SPMConfig()
    for core in (84.57, 86.89, 89.21):   # t = 3.54 / 2.38 / 1.22
        cfg.spm_core_od = core
        snap = spm_build.spm_snapshot(cfg)
        assert snap["airgap"] == pytest.approx(0.675, abs=1e-9)
        assert snap["band_r"] == pytest.approx(46.1625, abs=1e-9)
        assert snap["ring_area"] == pytest.approx(98.248892, rel=1e-5)
