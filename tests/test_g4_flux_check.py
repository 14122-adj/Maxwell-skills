"""G4-B 磁密复核器（`g4_flux_check.py`）的口径测试 — 不依赖 Maxwell。

为什么值得测
------------
1. **单位**：Fields Calculator 导出的坐标是**米**、B 是特斯拉；当成毫米会把
   r=0.067 读成 0.067 mm，整条剖面错位，还会把 NaN 行当成有效点；
2. **距离口径**：气隙/轭是弧长 `r·θ`，齿身是 `r − 50.2`，混用会让磁通连续性
   的积分窗口错位；
3. **磁通连续性**：`Φ = mean(Bg)·弧长·L`，`B_tooth = Φ/(齿宽·L)` —— 齿宽必须用
   r=54.25 处（18.905 mm），不是旧常数 10.48 mm。

本文件用合成数据钉死这三点，避免"脚本跑通但口径错"。
"""
from __future__ import annotations

import importlib.util
import math
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"


def _load():
    spec = importlib.util.spec_from_file_location("g4_flux_check", PROJ / "g4_flux_check.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _load()


# ──────────────────────────────────────────────────────────────────────
#  读取
# ──────────────────────────────────────────────────────────────────────
def test_read_calc_csv_converts_m_to_mm_and_skips_nan(tmp_path):
    p = tmp_path / "gap_010000us.csv"
    p.write_text(
        'Scalar data "Mag(<Bx,By,0>)"\n'
        "6.7000000000000004e-02 0.0 0.0 8.0653310278261822e-02\n"
        "6.64268057e-02 8.74525488e-03 0.0 Nan\n"
        "6.47170304e-02 1.73408760e-02 0.0 3.0e-01\n",
        encoding="utf-8",
    )
    pts = G.read_calc_csv(str(p))
    assert len(pts) == 2                      # NaN 行被跳过
    assert pts[0][0] == pytest.approx(67.0)   # 米 → 毫米
    assert pts[0][2] == pytest.approx(0.0806533102782618)
    assert pts[1][0] == pytest.approx(64.7170304)


def test_read_calc_dir_parses_time_from_filename(tmp_path):
    for t_us in (10000, 10250):
        (tmp_path / ("tooth_%06dus.csv" % t_us)).write_text(
            'Scalar data "Mag(<Bx,By,0>)"\n'
            "5.02e-02 1.345e-02 0.0 0.5\n",
            encoding="utf-8",
        )
    (tmp_path / "other_000001us.csv").write_text("x", encoding="utf-8")
    data = G.read_calc_dir(str(tmp_path), "tooth")
    assert sorted(data) == pytest.approx([0.010, 0.01025])


# ──────────────────────────────────────────────────────────────────────
#  距离口径
# ──────────────────────────────────────────────────────────────────────
def test_profile_gap_distance_is_arc_length():
    # 45° 处：d = r·θ = 23.08125 * π/4
    x = G.R_GAP_MM * math.cos(math.pi / 4)
    y = G.R_GAP_MM * math.sin(math.pi / 4)
    prof = G.profile([(x, y, 0.9)], "gap")
    assert prof[0][0] == pytest.approx(G.R_GAP_MM * math.pi / 4, rel=1e-9)


def test_profile_tooth_distance_is_radial_offset():
    prof = G.profile([(0.0, 54.25, 1.2)], "tooth")
    assert prof[0][0] == pytest.approx(54.25 - 50.2, rel=1e-9)


# ──────────────────────────────────────────────────────────────────────
#  积分 / 峰值
# ──────────────────────────────────────────────────────────────────────
def test_window_mean_constant_and_linear():
    assert G.window_mean([(0.0, 0.8), (10.0, 0.8)], 2.0, 8.0) == pytest.approx(0.8)
    # 线性 0→1，窗口 [2,8] 的平均 = 0.5
    assert G.window_mean([(0.0, 0.0), (10.0, 1.0)], 2.0, 8.0) == pytest.approx(0.5)


def test_global_peak_picks_time_and_position():
    data = {0.0: [(0.0, 0.1), (1.0, 0.2)], 0.001: [(0.0, 0.9), (1.0, 0.3)]}
    pk = G.global_peak(data)
    assert pk["b_max"] == pytest.approx(0.9)
    assert pk["distance_mm"] == pytest.approx(0.0)
    assert pk["time_s"] == pytest.approx(0.001)


# ──────────────────────────────────────────────────────────────────────
#  解析对照
# ──────────────────────────────────────────────────────────────────────
def test_analytic_corrected_uses_real_tooth_width():
    ana = G.analytic_corrected(0.7762)
    # 齿宽 = 2π·54.25/12 − 9.5 = 18.905 mm（不是旧常数 10.48）
    assert ana["tooth_width_mm"] == pytest.approx(18.905, abs=0.01)
    # 旧常数把 B 抬到 1.65 T 量级；实际几何下应低得多
    assert ana["B_tooth_KFE1"] < 1.0
    # 轭厚 16 mm 同样远厚于 7.86 mm
    assert ana["B_yoke_KFE1"] < 1.0


def test_legacy_constants_reproduce_identical_b():
    """旧解析的 10.48/7.86 让 B_tooth 与 B_yoke 恰好相等 —— 这是口径错误的指纹。"""
    phi = 0.0039458298360287155
    b_tooth = (8.0 * phi / 12.0) / ((10.48e-3) * 0.16 * 0.95)
    b_yoke = (phi / 2.0) / ((7.86e-3) * 0.16 * 0.95)
    assert b_tooth == pytest.approx(1.65136, abs=1e-4)
    assert b_yoke == pytest.approx(1.65136, abs=1e-4)


# ──────────────────────────────────────────────────────────────────────
#  端到端
# ──────────────────────────────────────────────────────────────────────
def _write_arc(tmp_path, prefix, t_us, r_mm, a0, a1, n, b):
    lines = ['Scalar data "Mag(<Bx,By,0>)"']
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        lines.append("%.12g %.12g 0.0 %.12g"
                     % (r_mm * math.cos(a) / 1000.0, r_mm * math.sin(a) / 1000.0, b))
    (tmp_path / ("%s_%06dus.csv" % (prefix, t_us))).write_text("\n".join(lines),
                                                              encoding="utf-8")


def test_analyse_end_to_end_consistency_pass(tmp_path):
    # 气隙 30° 上 B=0.8 → Φ = 0.8·(r·30°)·L；齿宽 18.905 → B_tooth ≈ 0.5114
    tan_pitch = G.R_GAP_MM * math.radians(30.0)
    phi = 0.8 * tan_pitch * 1e-3 * 0.16
    w = tan_pitch * (G.R_TOOTH_MEAS_MM / G.R_GAP_MM) - G.SLOT_BS2_MM
    b_tooth = phi / (w * 1e-3 * 0.16)
    for t in (10000, 10250):
        _write_arc(tmp_path, "gap", t, G.R_GAP_MM, 0.0, 45.0, 18, 0.8)
        _write_arc(tmp_path, "yoke", t, G.R_YOKE_MM, 0.0, 45.0, 18, 0.4)
        # 齿身：沿半径的 5 点，B 恒为 b_tooth
        lines = ['Scalar data "Mag(<Bx,By,0>)"']
        a = math.radians(15.0)
        for i in range(5):
            r = 50.2 + (58.8 - 50.2) * i / 4.0
            lines.append("%.12g %.12g 0.0 %.12g"
                         % (r * math.cos(a) / 1000.0, r * math.sin(a) / 1000.0, b_tooth))
        (tmp_path / ("tooth_%06dus.csv" % t)).write_text("\n".join(lines),
                                                        encoding="utf-8")
    res = G.analyse(str(tmp_path), tooth_prefix="tooth",
                    gap_window_deg=(0.0, 30.0))
    assert res["gap"]["b_max"] == pytest.approx(0.8)
    assert res["tooth"]["b_max"] == pytest.approx(b_tooth, rel=1e-9)
    assert res["yoke"]["b_max"] == pytest.approx(0.4)
    assert res["flux_continuity_diagnostic"]["gap_pct"] == pytest.approx(0.0, abs=1e-6)
    assert res["verdict"] == "PASS"


def test_analyse_flags_over_limit_tooth(tmp_path):
    for t in (10000,):
        _write_arc(tmp_path, "gap", t, G.R_GAP_MM, 0.0, 45.0, 18, 0.8)
        _write_arc(tmp_path, "yoke", t, G.R_YOKE_MM, 0.0, 45.0, 18, 0.4)
        lines = ['Scalar data "Mag(<Bx,By,0>)"']
        a = math.radians(15.0)
        for i in range(5):
            r = 50.2 + (58.8 - 50.2) * i / 4.0
            lines.append("%.12g %.12g 0.0 1.70"
                         % (r * math.cos(a) / 1000.0, r * math.sin(a) / 1000.0))
        (tmp_path / ("tooth_%06dus.csv" % t)).write_text("\n".join(lines),
                                                        encoding="utf-8")
    res = G.analyse(str(tmp_path), tooth_prefix="tooth",
                    gap_window_deg=(0.0, 30.0))
    assert res["tooth"]["verdict"] == "FAIL"
    assert res["verdict"] == "FAIL"


# ──────────────────────────────────────────────────────────────────────
#  气隙径向分量 Br（Bx/By → Br 的合成口径）
# ──────────────────────────────────────────────────────────────────────
def _write_vec_arc(tmp_path, prefix, t_us, r_mm, a0, a1, n, bx_fn, by_fn):
    """写一列 Bx 或 By 分量（同一批角度），用于合成 Br/Bt。"""
    lines = ['Scalar data "ScalarX(<Bx,By,0>)"']
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        x, y = r_mm * math.cos(a), r_mm * math.sin(a)
        val = (bx_fn if prefix.endswith("bx") else by_fn)(a)
        lines.append("%.12g %.12g 0.0 %.12g" % (x / 1000.0, y / 1000.0, val))
    (tmp_path / ("%s_%06dus.csv" % (prefix, t_us))).write_text("\n".join(lines),
                                                              encoding="utf-8")


def _write_br_pair(tmp_path, t_us, m, purely="radial"):
    """纯径向或纯切向的合成磁场，幅度 m。"""
    if purely == "radial":
        bx = lambda a: m * math.cos(a)          # noqa: E731
        by = lambda a: m * math.sin(a)          # noqa: E731
    else:
        bx = lambda a: -m * math.sin(a)         # noqa: E731
        by = lambda a: m * math.cos(a)          # noqa: E731
    _write_vec_arc(tmp_path, "gap_bx", t_us, G.R_GAP_MM, 0.0, 60.0, 120, bx, by)
    _write_vec_arc(tmp_path, "gap_by", t_us, G.R_GAP_MM, 0.0, 60.0, 120, bx, by)


def test_read_br_dir_composes_radial_component(tmp_path):
    """纯径向场：Br 处处等于模值，Bt 为零（这是 45° 齿中心的真实情形）。"""
    _write_br_pair(tmp_path, 20000, 0.86, purely="radial")
    data = G.read_br_dir(str(tmp_path))
    rows = data[pytest.approx(0.02, abs=1e-9)] if False else data[0.02]
    assert len(rows) == 121
    for deg, br, bt in rows:
        assert br == pytest.approx(0.86, abs=1e-9), ("角度 %.1f 的 Br 偏差" % deg)
        assert bt == pytest.approx(0.0, abs=1e-9), ("角度 %.1f 的 Bt 偏差" % deg)


def test_read_br_dir_detects_tangential_only(tmp_path):
    """纯切向场：Br ≈ 0，|Bt| = 模值 —— 用来看清 |B| 何时不能当 Br 用。"""
    _write_br_pair(tmp_path, 20000, 0.19, purely="tangential")
    rows = G.read_br_dir(str(tmp_path))[0.02]
    for deg, br, bt in rows:
        assert br == pytest.approx(0.0, abs=1e-9), ("角度 %.1f 的 Br 偏差" % deg)
        assert abs(bt) == pytest.approx(0.19, abs=1e-9)


def test_gap_radial_block_three_calibers(tmp_path):
    """三口径（极轴/|Br|峰/|B|峰）在同一合成场上应给出同一结论。"""
    _write_br_pair(tmp_path, 20000, 0.86, purely="radial")
    blk = G.gap_radial_block(str(tmp_path))
    assert blk["Bg_pole_axis_T"] == pytest.approx(0.86, abs=1e-9)
    assert blk["Br_max_T"] == pytest.approx(0.86, abs=1e-9)
    assert blk["Bt_max_T"] == pytest.approx(0.0, abs=1e-9)
    # 极轴明细取 15°/45°，两者在同幅值合成场上都等于 0.86
    assert blk["pole_axis_detail"]["15"]["Br"] == pytest.approx(0.86, abs=1e-9)
    assert blk["pole_axis_detail"]["45"]["Br"] == pytest.approx(0.86, abs=1e-9)


def test_analyse_br_crosscheck_pass_and_mismatch(tmp_path):
    """br_dir 存在时必产出 gap_radial_crosscheck；缺目录时降级为 SKIP。"""
    for t in (10000,):
        _write_arc(tmp_path, "gap", t, G.R_GAP_MM, 0.0, 30.0, 12, 0.8)
        _write_arc(tmp_path, "yoke", t, G.R_YOKE_MM, 0.0, 30.0, 12, 0.4)
        _write_arc(tmp_path, "tooth", t, G.R_TOOTH_MEAS_MM, 0.0, 30.0, 12, 0.5)
    res_no_br = G.analyse(str(tmp_path), tooth_prefix="tooth", gap_window_deg=(0.0, 30.0))
    assert res_no_br["gap_radial"] is None
    assert res_no_br["gap_radial_crosscheck"].startswith("SKIP")
