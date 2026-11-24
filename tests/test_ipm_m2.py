"""IPM 8p48s M2'（2026-11-22）：空载后处理的数值口径护栏。

为什么需要这一组
----------------
M2' 的结论（BEMF / THD / 齿槽 / 磁密）全部由 CSV 重算得出，一旦后处理口径错了，
FEA 再准也会得出错的判据。这三类错在 SPM 阶段都真实发生过：

1. **窗口含重复端点**：50 µs 网格上 `t[i] >= t0` 会落到 10.05 ms，THD 假差 0.55 pt；
2. **转矩单位**：模板路径导出 `[mNewtonMeter]`，不换算会把 0.88 N·m 读成 880；
3. **判据被悄悄改宽**：把 118 V 写成 110 V 能让 FAIL 变 PASS。

本文件把 `ipm_m2_check.py` 的纯函数与判据常数钉死，不碰 AEDT。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT / "projects" / "IPM_8p48s", _ROOT / "projects" / "25Nm_PMSM"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ipm_m2_check as m2  # noqa: E402


# ────────────────────────────────────────────────────────── 判据常数不得漂移
def test_criteria_match_acceptance_doc():
    """判据与 `docs/ENGINEERING_ACCEPTANCE.md` §2 逐字一致，SPM/IPM 共用。"""
    assert m2.BEMF_RANGE == (118.0, 145.0)
    assert m2.THD_MAX == 10.0
    assert m2.COGGING_MAX_PCT == 5.0
    assert m2.IMBALANCE_MAX == 2.0
    assert m2.TORQUE_RATED == 25.0
    assert m2.BG_RANGE == (0.70, 0.90)
    assert m2.B_TOOTH_MAX == 1.65
    assert m2.B_YOKE_MAX == 1.50


def test_machine_constants_match_contract():
    """8p48s / 160 mm / 每相 16 线圈 / cps=10（I3 定源 11-24）与契约一致。"""
    assert m2.POLES == 8 and m2.SLOTS == 48
    assert m2.STACK_MM == 160.0
    assert m2.COILS_PER_PHASE == 16
    assert m2.CPS_MODEL == 10
    assert m2.CPS_MODEL * m2.COILS_PER_PHASE == 160


# ──────────────────────────────────────────────────────────── 窗口口径
def test_tail_skips_exactly_one_electrical_period():
    """50 µs × 401 点：丢第一个 10 ms（200 点），剩 201 点（含末端点）。"""
    t = [i * 50e-6 for i in range(401)]
    y = list(range(401))
    tt, yy = m2.tail_after_first_period(t, y)
    assert len(tt) == 201
    assert tt[0] == pytest.approx(0.0100, abs=1e-12)
    assert yy[0] == 200


def test_tail_short_signal_is_returned_unchanged():
    t = [i * 50e-6 for i in range(5)]
    y = [1.0, 2.0, 3.0, 4.0, 5.0]
    tt, yy = m2.tail_after_first_period(t, y)
    assert tt == t and yy == y


def test_pp_of_sine_matches_twice_amplitude():
    """10 ms 窗内 1 个 100 Hz 周期 ⇒ pp ≈ 2A（端点采样略差，容差 1%）。"""
    a = 3.0
    t = [i * 50e-6 for i in range(401)]
    y = [a * math.sin(2 * math.pi * 100.0 * ti) for ti in t]
    st = m2.pp_ct(t, y)
    assert st["pp"] == pytest.approx(2 * a, rel=0.01)
    assert st["n"] == 201


def test_pp_ripple_none_when_mean_zero():
    """空载转矩均值≈0 时不要报脉动率（分母为零），避免 inf。"""
    t = [i * 50e-6 for i in range(401)]
    y = [1e-9 * math.sin(2 * math.pi * 100.0 * ti) for ti in t]
    st = m2.pp_ct(t, y)
    assert st["ripple_pct"] is None


# ──────────────────────────────────────────────────────────── 匝数反推
def test_turns_backcalc_is_linear_in_bemf():
    a = m2.turns_backcalc(120.0)
    b = m2.turns_backcalc(240.0)
    assert b["targets"]["lower_118V"]["cps_exact"] == pytest.approx(
        a["targets"]["lower_118V"]["cps_exact"] / 2.0, rel=1e-12)


def test_turns_backcalc_reproduces_model_point():
    """用模型自身 BEMF 反推，必须回到当前 cps —— 恒等校验（I3 定源后 cps=10）。"""
    cps = m2.CPS_MODEL
    n_ph = cps * m2.COILS_PER_PHASE
    tb = m2.turns_backcalc(120.0)
    assert tb["bemf_per_turn_v"] == pytest.approx(120.0 / n_ph, rel=1e-12)
    assert tb["targets"]["design_125V"]["cps_int"] == cps


def test_turns_backcalc_rounds_up_when_below_lower_bound():
    """BEMF 偏低时必须推出更大的 cps（方向不能反）。"""
    tb = m2.turns_backcalc(100.0)
    assert tb["targets"]["lower_118V"]["cps_int"] > m2.CPS_MODEL


# ──────────────────────────────────────────────────────────── 探针 CSV
def test_read_calc_csv_skips_header_and_nan(tmp_path):
    p = tmp_path / "gap_mag.csv"
    p.write_text(
        'Scalar data "Mag(<Bx,By,0>)"\n'
        "4.63e-02 0.0 0.0 8.0e-01\n"
        "4.63e-02 1.0e-04 0.0 NaN\n"
        "4.63e-02 2.0e-04 0.0 7.5e-01\n",
        encoding="utf-8")
    pts = m2.read_calc_csv(str(p))
    assert len(pts) == 2
    assert pts[0][0] == pytest.approx(46.3, abs=1e-6)   # m → mm
    assert pts[1][2] == pytest.approx(0.75)


def test_read_calc_pair_projects_radial_component(tmp_path):
    """θ=0 处 Br=Bx、Bt=+By；θ=90° 处 Br=By、Bt=−Bx。

    旋转矩阵：[Br; Bt] = [[cosθ, sinθ], [−sinθ, cosθ]]·[Bx; By]。
    """
    (tmp_path / "gap_bx.csv").write_text(
        'Scalar data "ScalarX(<Bx,By,0>)"\n'
        "4.63e-02 0.0 0.0 0.80\n"
        "0.0 4.63e-02 0.0 0.60\n", encoding="utf-8")
    (tmp_path / "gap_by.csv").write_text(
        'Scalar data "ScalarY(<Bx,By,0>)"\n'
        "4.63e-02 0.0 0.0 0.10\n"
        "0.0 4.63e-02 0.0 0.55\n", encoding="utf-8")
    rows = m2.read_calc_pair(str(tmp_path), "gap_bx", "gap_by")
    assert rows[0][0] == pytest.approx(0.0, abs=1e-9)
    assert rows[0][1] == pytest.approx(0.80, abs=1e-9)
    assert rows[0][2] == pytest.approx(0.10, abs=1e-9)
    assert rows[1][0] == pytest.approx(90.0, abs=1e-9)
    assert rows[1][1] == pytest.approx(0.55, abs=1e-9)
    assert rows[1][2] == pytest.approx(-0.60, abs=1e-9)


# ──────────────────────────────────────────────────────────── 转矩单位
def test_torque_scale_covers_all_three_prefixes():
    """AEDT 2021.1 的 Moving1.Torque 实测导出 [uNewtonMeter]，SPM 模板是 [mNewtonMeter]。

    2026-11-22 首跑只认 mN·m，把 195.16 µN·m 读成 195.16 N·m，齿槽虚报 780%。
    """
    assert m2.torque_scale("NewtonMeter") == 1.0
    assert m2.torque_scale("mNewtonMeter") == pytest.approx(1e-3)
    assert m2.torque_scale("uNewtonMeter") == pytest.approx(1e-6)
    assert m2.torque_scale("µNewtonMeter") == pytest.approx(1e-6)
    assert m2.torque_scale("") == 1.0


def test_torque_scale_rounds_195_micro_to_2e_minus_4():
    """回归具体读数：195.16 [uN·m] → 1.95e-4 N·m，而不是 195 N·m。"""
    v = 195.16 * m2.torque_scale("uNewtonMeter")
    assert v == pytest.approx(1.9516e-4, rel=1e-9)


# ─────────────────────────────────────────────────────────── 磁密判定
def test_gap_verdict_bounds():
    """0.90 T / 0.70 T 是闭区间；越界一律 FAIL（不许挑口径）。"""
    assert m2.BG_RANGE[0] <= 0.85 <= m2.BG_RANGE[1]
    assert not (m2.BG_RANGE[0] <= 0.95 <= m2.BG_RANGE[1])
    assert not (m2.BG_RANGE[0] <= 0.65 <= m2.BG_RANGE[1])
