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


def test_spm_rotor_init_deg_identity():
    """rotor_init_deg=0 必须与默认几何逐位一致（D5 斜槽恒等护栏）。"""
    base = spm_build.SPMConfig()
    from dataclasses import replace
    rotated = replace(base, rotor_init_deg=0.0)
    a = spm_build.spm_magnets(base)
    b = spm_build.spm_magnets(rotated)
    for ma, mb in zip(a, b):
        assert ma["pts"] == mb["pts"]
        assert ma["gx"] == mb["gx"] and ma["gy"] == mb["gy"]
        assert ma["center_deg"] == mb["center_deg"]


def test_spm_rotor_init_deg_rotates_geometry_and_vectors():
    """旋转角 Δ_mech：极轴与平行充磁矢量同步转 Δ，极性/半径/气隙不变。"""
    import math as _m
    from dataclasses import replace
    cfg = spm_build.SPMConfig()
    delta = 2.8125   # 0.75 × 7.5° 槽距的一半
    rc = replace(cfg, rotor_init_deg=delta)
    for m0, m1 in zip(spm_build.spm_magnets(cfg), spm_build.spm_magnets(rc)):
        assert m1["center_deg"] == pytest.approx(m0["center_deg"] + delta, abs=1e-9)
        a0 = _m.radians(m0["center_deg"])
        a1 = _m.radians(m1["center_deg"])
        s = 1.0 if m0["sign"] > 0 else -1.0
        assert m1["gx"] == pytest.approx(s * _m.cos(a1), abs=1e-9)
        assert m1["gy"] == pytest.approx(s * _m.sin(a1), abs=1e-9)
        assert m1["sign"] == m0["sign"]
        assert math.hypot(m1["gx"], m1["gy"]) == pytest.approx(1.0, abs=1e-9)
        for (x0, y0), (x1, y1) in zip(m0["pts"], m1["pts"]):
            assert math.hypot(x1, y1) == pytest.approx(math.hypot(x0, y0), abs=1e-9)
    snap = spm_build.spm_snapshot(rc)
    assert snap["airgap"] == pytest.approx(0.675, abs=1e-9)
    assert snap["band_r"] == pytest.approx(46.1625, abs=1e-9)


def test_spm_cps_knob_writes_conductor_number_only():
    """I35 降匝数单变量：cps 只改 Conductor number，几何/气隙/Band 逐字不变。"""
    from dataclasses import replace
    base = spm_build.SPMConfig()
    c8 = replace(base, spm_core_od=90.35, pm_pole_arc=0.90,
                 conductors_per_slot=8)
    text = spm_build.build_script(c8, log_path="D:/ANSYS_Run/spm_c8.log")
    compile(text, "<spm_c8>", "exec")
    assert "CPS = 8" in text
    assert "CPS = 10" not in text
    # 几何与气隙/Band 不受匝数影响
    snap = spm_build.spm_snapshot(c8)
    assert snap["pm_t"] == pytest.approx(0.65, abs=1e-9)
    assert snap["airgap"] == pytest.approx(0.675, abs=1e-9)
    assert snap["band_r"] == pytest.approx(46.1625, abs=1e-9)
    # 与 cps=10 同几何对比：除 CPS 行外生成脚本逐字一致
    c10 = replace(c8, conductors_per_slot=10)
    text10 = spm_build.build_script(c10, log_path="D:/ANSYS_Run/spm_c8.log")
    a = [line for line in text.splitlines() if not line.startswith("CPS =")]
    b = [line for line in text10.splitlines() if not line.startswith("CPS =")]
    assert a == b


def test_spm_m4_cps_knob_meta_and_source(tmp_path, monkeypatch):
    """I35 新基线：M4 起动脉冲图的 --cps 必须落进 meta 几何+source。"""
    import spm_m4_start

    # 生成脚本把路径拼进双引号字面量，Windows 反斜杠会产生 \T 非法转义
    tmp_fwd = str(tmp_path).replace("\\", "/")
    monkeypatch.setattr(spm_m4_start, "RUN_DIR", tmp_fwd)
    monkeypatch.setattr(spm_m4_start, "RESULTS", tmp_fwd)
    rc = spm_m4_start.main([
        "--core-od", "90.35", "--pole-arc", "0.90", "--cps", "8",
        "--imax", "13.978", "--case", "cps8_guard",
    ])
    assert rc == 0
    import json

    meta = json.loads((tmp_path / "spm_m4_start_cps8_guard.json").read_text(encoding="utf-8"))
    assert meta["geometry"]["cps"] == 8
    assert meta["geometry"]["turns_per_phase"] == 128
    assert meta["geometry"]["core_od"] == pytest.approx(90.35)
    assert meta["excitation"]["current_A"] == pytest.approx(13.978)
    assert meta["excitation"]["source"] == "spm_t065c8_new_baseline_I35"
    build_py = tmp_path / "spm_m4_build_cps8_guard.py"
    assert "CPS = 8" in build_py.read_text(encoding="utf-8")


def test_spm_m2_field_probe_guard(tmp_path):
    """I35 遗留补验：ClearAll 必须 try/except（2021.1 无该方法，首跑全 FAIL）；坐标为米。"""
    import ipm_geom
    import ipm_m2_noload as m2n
    import spm_m2_field_probe as fp

    pts = m2n.write_point_files(ipm_geom.IPMConfig(), str(tmp_path / "pts"))
    assert set(pts) == {"gap", "tooth", "yoke"}
    assert pts["gap"][1] == 181
    gap_path = pts["gap"][0]
    with open(gap_path, encoding="ascii") as fh:
        first = fh.readline().split()
    # 点文件单位米：x≈0.046 m，若写成 mm 会是 46；判据用数量级避免写死极角
    assert 0.01 < abs(float(first[0])) < 0.05
    assert abs(float(first[1])) < 1e-9

    text = fp.build_script(pts, aedt_in="D:/ANSYS_Run/x.aedt",
                           csvdir="D:/ANSYS_Run/csv_x", log_path="D:/ANSYS_Run/x.log")
    compile(text, "<field_probe>", "exec")
    lines = text.splitlines()
    # ClearAll 前一行必须是 try:，后两行 except/pass（首跑因裸调用 AttributeError 全 FAIL）
    i = next(i for i, ln in enumerate(lines) if "ClearAll()" in ln)
    assert lines[i - 1].strip() == "try:"
    assert "except Exception:" in lines[i + 1]
    assert lines[i + 2].strip() == "pass"
    assert "'Setup1 : Transient'" in text
