"""M7 负载验收器（`m7_load_check.py`）的口径测试 — 不依赖 Maxwell。

为什么值得测
------------
M7 的结论是「模板路径能不能跑出与手写路径同量级的负载转矩」。这个结论完全
建立在两件容易被忽略的细节上：

1. **单位**：AEDT 导出表头是 `Time [ms]` / `Torque [mNewtonMeter]`，
   直接当 s / N·m 用会把 22.3 N·m 读成 22300（或反之 0.02）；
2. **窗口**：均值必须取**末个电周期**（10 ms / 200 点），从 t=0 起算会把
   起动暂态算进去，`T_avg` 偏低、脉动虚高。

本文件用合成波形钉死这两点，避免"脚本跑通但口径错"。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"


def _load():
    spec = importlib.util.spec_from_file_location("m7_load_check", PROJ / "m7_load_check.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def m7():
    return _load()


def _write(path: Path, header: str, rows) -> str:
    body = "\n".join("%.6f,%.6f" % (t, v) for t, v in rows)
    path.write_text(header + "\n" + body + "\n", encoding="utf-8")
    return str(path)


def test_reads_ms_header_and_keeps_newton_meter(m7, tmp_path):
    p = _write(tmp_path / "tq.csv", '"Time [ms]","Moving1.Torque [NewtonMeter]"',
               [(0.0, 22.0), (10.0, 22.0)])
    t, v = m7.read_two_col(p)
    assert t == [0.0, 0.01]
    assert v == [22.0, 22.0]


def test_reads_millinewton_meter(m7, tmp_path):
    """mNewtonMeter 必须缩 1e-3，否则转矩会被高估 1000 倍。"""
    p = _write(tmp_path / "tq.csv", '"Time [ms]","Moving1.Torque [mNewtonMeter]"',
               [(0.0, 22334.4), (10.0, 22334.4)])
    _t, v = m7.read_two_col(p)
    assert v[0] == pytest.approx(22.3344, abs=1e-6)


def test_trapezoid_mean_recovers_offset(m7):
    t = [i * 1e-5 * 5 for i in range(201)]          # 0…10 ms，50 µs
    v = [22.0 + 3.0 * math.sin(2 * math.pi * 100 * x) for x in t]
    assert m7.trapezoid_mean(t, v) == pytest.approx(22.0, abs=0.02)


def test_metrics_peak_to_peak_of_pure_sine(m7):
    t = [i * 5e-5 for i in range(201)]
    v = [3.0 * math.cos(2 * math.pi * 100 * x) for x in t]
    m = m7.metrics(t, v)
    assert m["T_pp_nm"] == pytest.approx(6.0, abs=0.02)
    assert m["n_samples"] == 201


def test_window_takes_last_period_only(m7):
    """末周期窗口：t ∈ [t_end−10 ms, t_end]，起动段必须被排除。"""
    t = [i * 5e-5 for i in range(401)]
    v = [10.0 if x < 0.01 else 22.0 for x in t]
    tw, vw = m7.window(t, v, t[-1] - 0.01, t[-1])
    assert min(tw) >= 0.01 - 1e-12          # 起点即末周期起点，起动段被排除
    assert m7.trapezoid_mean(tw, vw) == pytest.approx(22.0, abs=1e-9)


def test_commanded_current_matches_m5_native_readback(m7):
    """A 相 t=0 指令 = −√2·9.89·sin120° = −12.1128 A（与 M5 原生 TrCrv 回读一致）。"""
    assert m7.commanded_current("A", 0.0) == pytest.approx(-12.1128, abs=1e-4)
    assert m7.commanded_current("C", 0.0) == pytest.approx(0.0, abs=1e-9)


def test_find_native_dir_walks_results_tree(m7, tmp_path):
    deep = tmp_path / "T4_tpl_load.aedtresults" / "Motor_Design.results" / "DV1.Data"
    deep.mkdir(parents=True)
    (deep / "WindingA_TrCrv.txt").write_text("WindingA\n5 5\n0\n-12.1 0 0 -0.2 0\n", encoding="utf-8")
    assert m7.find_native_dir(str(tmp_path)) == str(deep)


def test_read_trcrv_parses_pairs(m7, tmp_path):
    p = tmp_path / "WindingA_TrCrv.txt"
    p.write_text("WindingA\n5 2\n0\n-12.1 0 0 -0.2 0.5\n0.0005\n-11.9 0 0 -0.21 0.6\n",
                 encoding="utf-8")
    d = m7.read_trcrv(str(p))
    assert d["t"] == [0.0, 0.0005]
    assert d["current"] == [-12.1, -11.9]
    assert d["flux"] == [-0.2, -0.21]
    assert d["voltage"] == [0.5, 0.6]
