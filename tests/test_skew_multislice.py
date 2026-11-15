"""G7 斜槽多切片（`skew_multislice.py`）口径测试 —— 不依赖 Maxwell。

为什么值得测
------------
斜槽结论是「齿槽 3.52% → 0.002%、THD 11.18% → 2.00%」这种量级极大的改动，
一个静默的口径错误就能造出漂亮但假的结果。本次开发中真实踩到三个：

1. **周期插值**：齿槽主频是 600 Hz（周期 1.667 ms），50 µs 采样只有 33 点/周期，
   线性插值在尖峰上误差达 7.7e-2 N·m（≈9% 峰峰值），恒等校验差 4.67%；
2. **单周期端点**：把周期端点重复计入（N+1 点）会让 a5 从 28.30 漂到 31.27 V、
   THD 从 11.180% 漂到 12.422%；
3. **双边谱平移**：DBT 系数存 0..N−1 再按 h/T 乘相位，负频半边走错相位，
   基波掉到 47.6%（BEMF 120.56 → 57.43 V）。

所以本文件把「skew=0 必须逐位复现基线」当第一断言，其余断言都建在它之上。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
FEA = ROOT / "projects" / "results" / "fea"


def _load():
    spec = importlib.util.spec_from_file_location("skew_multislice", PROJ / "skew_multislice.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sm():
    return _load()


@pytest.fixture(scope="module")
def base(sm):
    """skew=0 的评估结果（一次性算完，多个断言共用）。"""
    return sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.0, 200, None)


# ────────────────────────────────────────────── 解析因子
def test_skew_factor_half_slot_pitch(sm):
    """0.5 槽距 = 60° 电角：k1=0.95493、k5=0.19099、k13=0.07346（手算对表）。"""
    assert sm.skew_factor(1, 60.0) == pytest.approx(0.95493, abs=1e-5)
    assert sm.skew_factor(5, 60.0) == pytest.approx(0.19099, abs=1e-5)
    assert sm.skew_factor(7, 60.0) == pytest.approx(-0.13642, abs=1e-5)
    assert sm.skew_factor(13, 60.0) == pytest.approx(0.07346, abs=1e-5)


def test_skew_factor_zero_angle_is_unity(sm):
    for h in (1, 5, 7, 11, 13):
        assert sm.skew_factor(h, 0.0) == pytest.approx(1.0, abs=1e-12)


def test_cogging_period_is_600hz(sm):
    """齿槽 24 次/转 @25 Hz ⇒ 600 Hz / 1.667 ms。写成 5 ms（15° 机械）会算错窗口。"""
    assert sm.COGGING_ORDER == 24
    assert sm.T_COG == pytest.approx(1.0 / 600.0, rel=1e-12)
    assert sm.T_COG * 1e3 == pytest.approx(1.6667, abs=1e-3)


# ────────────────────────────────────────────── 带限表示
def test_fourier_reconstructs_raw_samples(sm):
    """一个周期的 DFT 表示必须能逐点重建**该周期**的样本（误差 <1e-9 Wb）。

    只对模板周期的 N 个样本断言（不含重复端点）：周期端点 t=20 ms 与起点同相，
    重构给出的是起点值，与末点相差 1.7e-7 Wb —— 那是磁钢涡流暂态残差，
    拿它去要求 1e-9 会把"暂态未完全收敛"误判成"重构实现错"。
    """
    t, lam = sm.read_two_col(str(FEA / "m8_pear" / "flux_a.csv"))
    sig = sm.FourierPeriodic(t, lam)
    idx = [i for i in range(len(t)) if t[i] >= sig.grid_start - sig.period * 1e-6]
    worst = max(abs(sig.eval(t[i]) - lam[i]) for i in idx[:sig.n])
    assert worst < 1e-9
    # 跨周期的暂态残差也要落在文档写的量级内（首周期 vs 末周期）
    early = max(abs(sig.eval(t[i]) - lam[i]) for i in range(0, len(t) // 2))
    assert 1e-8 < early < 1e-4


def test_grid_excludes_duplicate_endpoint(sm):
    """单周期网格必须是 N 点（不含周期端点），否则 THD 会偏 +1.24 pt。"""
    t, lam = sm.read_two_col(str(FEA / "m8_pear" / "flux_a.csv"))
    sig = sm.FourierPeriodic(t, lam)
    g = sig.grid(200)
    assert len(g) == 200
    assert g[-1] - g[0] == pytest.approx(sig.period - sig.period / 200, rel=1e-9)


def test_one_slice_shift_equals_mean_shift(sm):
    """N=1 时「斜槽平均」退化为「整体平移 γ/2」——用谐波系数比相位验证。"""
    t, lam = sm.read_two_col(str(FEA / "m8_pear" / "flux_a.csv"))
    sig = sm.FourierPeriodic(t, lam)
    gamma = 15.0
    c1 = sm.skew_average(sig, gamma, 1)
    # 第 1 次谐波应带 exp(j2π·1·Δt/T)，Δt = (γ/2)/ω_mech
    dt = (gamma / 2.0) * math.pi / 180.0 / sm.OMEGA_MECH
    expect = complex(math.cos(2 * math.pi * dt / sm.T_ELEC),
                     math.sin(2 * math.pi * dt / sm.T_ELEC))
    assert c1[1] / sig.c[1] == pytest.approx(expect, abs=1e-9)


# ────────────────────────────────────────────── 恒等校验（最重要）
def test_identity_cogging_matches_baseline(sm, base):
    """skew=0 必须复现 M8 的 0.8801 N·m（`m8_pear_summary.json` 冻结值）。"""
    assert base["cogging_pp_nm"] == pytest.approx(0.8801, abs=5e-4)


def test_identity_thd_matches_ledger(sm, base):
    """skew=0 必须复现账本 P11 的 11.180%（同窗口同口径）。"""
    assert base["thd_line_pct"] == pytest.approx(11.180, abs=0.01)
    assert base["thd_two_method_gap_pt"] == pytest.approx(0.0, abs=0.01)


def test_identity_bemf_matches_baseline(sm, base):
    assert base["bemf_phase_rms_v"] == pytest.approx(120.5594, abs=0.05)


def test_identity_torque_matches_m7(sm, base):
    """skew=0 的合成转矩必须复现 M7 的 22.6296 N·m（判据 0.5%）。"""
    assert base["T_avg_nm"] == pytest.approx(22.6296, rel=5e-3)
    assert base["T_ripple_pct"] == pytest.approx(14.688, abs=0.05)


def test_composition_check_reports_small_gap(sm, base):
    """`composition_check` 是自检字段：合成 vs FEA 的平均/峰峰都要 <0.5%。"""
    chk = base["composition_check"]
    assert abs(chk["gap_pct"]) < 0.5
    assert abs(chk["T_pp_gap_pct"]) < 0.5


# ────────────────────────────────────────────── 物理单调性 / 代价
def test_half_slot_pitch_kills_cogging(sm):
    """0.5 槽距 = 一整个齿槽周期 ⇒ 齿槽在理想多切片下归零（<0.5% 额定的 1/100）。"""
    r = sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.5, 200, None)
    assert r["cogging_pp_nm"] < 0.01
    assert r["cogging_pct"] < 0.05


def test_torque_derating_equals_skew_factor(sm, base):
    """换相重标定后，平均转矩只能按 k_sk(1) 降额（0.5 槽距 ⇒ −4.51%）。"""
    r = sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.5, 200, None)
    ratio = r["T_avg_nm"] / base["T_avg_nm"]
    assert ratio == pytest.approx(sm.skew_factor(1, 60.0), abs=2e-3)


def test_unrealigned_current_costs_cos_half(sm):
    """不做换相重标定会额外损失 cos(γ_e/2)=cos30° ⇒ 比值 1/0.866=1.1547。"""
    r = sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.5, 200, None)
    ratio = r["T_avg_nm"] / r["T_avg_no_realign_nm"]
    assert ratio == pytest.approx(1.0 / math.cos(math.radians(30.0)), abs=5e-3)


def test_thd_drops_but_not_to_zero(sm):
    """THD 从 11.18% 降到 ~2.0%（残余由 11/13 次斜槽因子不为零决定），不装成 0。"""
    r = sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.5, 200, None)
    assert 1.0 < r["thd_line_pct"] < 4.0


def test_skew_does_not_change_cogging_dc(sm):
    """齿槽平均转矩本应为 0；斜槽不应引入直流偏置（<0.01 N·m）。"""
    r = sm.evaluate(str(FEA / "m8_pear"), str(FEA / "m7_load"), 0.5, 200, None)
    assert abs(r["cogging_mean_nm"]) < 0.01
