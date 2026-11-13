"""G4：模板 vs 手写路径对比器的单位口径护栏。

背景（2026-11-08 真实踩坑）
--------------------------
AEDT 导出的表头带单位：`Time [us]`、`Torque [mNewtonMeter]`。把 µs 当 s、
mN·m 当 N·m 直接算，会得到 403 N·m 这种"量级正确、数值错 1000 倍"的结论——
而且不报错。本文件把单位换算与求导口径钉死，防止对比器退化。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"


def _load():
    spec = importlib.util.spec_from_file_location("tvm_25nm", PROJ / "template_vs_manual.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_results_dir_points_at_projects_results() -> None:
    """`projects/25Nm_PMSM/../results` —— 早期写成 `25Nm_PMSM/results` 会找不到 JSON。"""
    mod = _load()
    assert Path(mod.RESULTS) == (PROJ.parent / "results").resolve()
    assert (Path(mod.RESULTS) / "fea_results.json").exists()


def test_unit_scale_microsecond_millinewton(tmp_path) -> None:
    """µs + mN·m 必须换算成 s + N·m（403 N·m 的根源）。"""
    mod = _load()
    p = tmp_path / "t.csv"
    p.write_text(
        '"Time [us]","Moving1.Torque [mNewtonMeter]"\n'
        "0,0\n1000,403000\n2000,0\n",
        encoding="utf-8",
    )
    t, v = mod.read_curve(str(p))
    assert t == [0.0, 1e-3, 2e-3]
    assert v[1] == 403.0            # 403000 mN·m = 403 N·m


def test_unit_scale_millisecond_newton(tmp_path) -> None:
    """ms + NewtonMeter（2021.1 的默认导出单位）也必须正确。"""
    mod = _load()
    p = tmp_path / "t.csv"
    p.write_text(
        '"Time [ms]","Moving1.Torque [NewtonMeter]"\n'
        "0,0\n0.05,1.5\n",
        encoding="utf-8",
    )
    t, v = mod.read_curve(str(p))
    assert abs(t[1] - 5e-5) < 1e-15
    assert v[1] == 1.5


def test_derivative_matches_analytic() -> None:
    """空载 BEMF 由 e = -dλ/dt 得到，差分口径必须能还原 2πf·cos。"""
    mod = _load()
    f = 100.0
    n = 401
    t = [i * 5e-5 for i in range(n)]
    lam = [math.sin(2 * math.pi * f * ti) for ti in t]
    e = [-d for d in mod.derivative(t, lam)]
    mid = n // 2
    want = -2 * math.pi * f * math.cos(2 * math.pi * f * t[mid])
    assert abs(e[mid] - want) / abs(want) < 0.01


def test_window_is_last_electrical_period() -> None:
    mod = _load()
    t = [i * 5e-5 for i in range(401)]
    v = list(range(401))
    seg = mod.window(t, v, t[-1] - mod.T_ELEC, t[-1])
    assert seg[0][0] >= t[-1] - mod.T_ELEC - 1e-12
    assert seg[-1][0] == t[-1]


def test_empty_file_is_tolerated(tmp_path) -> None:
    mod = _load()
    p = tmp_path / "none.csv"
    assert mod.read_curve(str(p)) == ([], [])
    p.write_text("", encoding="utf-8")
    assert mod.read_curve(str(p)) == ([], [])
