"""`analyse_signal` 的窗口口径 —— 单周期 DFT 不得因浮点边界换窗口。

对应缺陷（2026-11-18 E2 发现）
-----------------------------
旧实现用 `sel = [i for i in range(len(t)) if t[i] >= t[0] + 1/F_ELEC]` 跳首周期：

* 50 µs 网格：`0.01` 在二进制里不可精确表示，`t[200]=0.010000000000000002` 与
  `t0=0.01` 比较可能落空 ⇒ 窗口从 10.05 ms 开始（199.5 个周期，含泄漏）；
* 25 µs 网格：同一比较恰好命中 ⇒ 窗口从 10.00 ms 开始且**含重复端点**（N+1 点）。

同一物理两个窗口 ⇒ E2 首跑 THD 出现 0.5474 pt 的假差异（11.1797% vs 11.7271%）。
修复：整数索引 `skip=round(T/dt)` + 若跨度是整数个电周期则丢弃重复端点。

本测试钉死：两种步长必须落在**同一个整周期**上（10 ms = 200×50 µs = 400×25 µs），
且合成信号的 THD 不随步长变化。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"


def _load():
    spec = importlib.util.spec_from_file_location("ingest_fea_win", PROJ / "ingest_fea.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ing():
    return _load()


def _signal(dt: float, n: int):
    """基波 100 Hz + 5 次 5% + 衰减直流（模拟未完全衰减的启动暂态）。"""
    t = [i * dt for i in range(n)]
    y = [100.0 * math.sin(2 * math.pi * 100.0 * ti)
         + 5.0 * math.sin(2 * math.pi * 500.0 * ti + 0.7)
         + 0.4 * math.exp(-ti / 0.005) for ti in t]
    return t, y


class TestWindow:
    @pytest.mark.parametrize("dt,n_expect", [(50e-6, 200), (25e-6, 400)])
    def test_one_full_period(self, ing, dt: float, n_expect: int) -> None:
        t, y = _signal(dt, int(round(0.02 / dt)) + 1)
        m = ing.analyse_signal(t, y)
        assert m["n_samples"] == n_expect
        # N 点 + 隐式重复 = N·dt 恰好一个电周期（不靠"少取一点凑数"）
        assert m["n_samples"] * dt == pytest.approx(1.0 / ing.F_ELEC, rel=1e-12)

    def test_thd_independent_of_step(self, ing) -> None:
        """衰减直流不是周期量，允许 1e-3 pt 量级的残差；窗口错位是 0.5 pt 量级。"""
        m50 = ing.analyse_signal(*_signal(50e-6, 401))
        m25 = ing.analyse_signal(*_signal(25e-6, 801))
        assert m50["thd_pct"] == pytest.approx(m25["thd_pct"], abs=1e-3)
        assert m50["thd_pct"] == pytest.approx(5.0, abs=0.05)   # 5 次 5% ⇒ THD≈5%

    def test_rms_independent_of_step(self, ing) -> None:
        m50 = ing.analyse_signal(*_signal(50e-6, 401))
        m25 = ing.analyse_signal(*_signal(25e-6, 801))
        assert m50["rms"] == pytest.approx(m25["rms"], rel=1e-3)

    def test_short_signal_not_crashed(self, ing) -> None:
        """点数不足以跳一个周期时保持原样，不许抛异常。"""
        t, y = _signal(50e-6, 50)
        assert ing.analyse_signal(t, y)["n_samples"] == 50
