"""G7 真机 3 切片复核器（`skew_slice_check.py`）的口径测试。

为什么值得测
------------
这个脚本是「斜槽结论有没有真机证据」的唯一入口，它一旦口径漂了，整条链路就变成
自证。三个必须钉死的点：

1. **窗口**：末个电周期、200 点、不含重复端点（与 `skew_multislice` 同口径）；
2. **不能拿空载切片去比负载转矩**：3 片都是空载工程，`T_mean ≈ 0` 才是对的；
   首版把 `T_avg` 放进判据，结果 `0.0007 N·m vs 18.80 N·m` 直接判 FAIL —— 是口径错，
   不是模型错。现改为比「基波降额比 k1」，并在 `not_covered` 里写明负载侧未跑；
3. **切片必须真的转过**：旋转没生效时三片波形逐点相同，"斜槽结果"其实是基线。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
FEA = ROOT / "projects" / "results" / "fea"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def chk():
    return _load("skew_slice_check", PROJ / "skew_slice_check.py")


@pytest.fixture(scope="module")
def sm(chk):
    return chk.SM


def test_archive_present():
    """3 片 × 4 个 CSV 必须入库，否则结论无法离线复算。"""
    for tag in ("s025", "s075", "s125"):
        assert (FEA / "skew_slices" / ("tq_%s.csv" % tag)).exists()
        for ph in ("a", "b", "c"):
            assert (FEA / "skew_slices" / ("flux_%s_%s.csv" % (tag, ph))).exists()


def test_last_period_is_200_points(chk):
    t, y = chk.SM.read_two_col(str(FEA / "skew_slices" / "tq_s025.csv"))
    tt, yy = chk.last_period(t, y)
    assert len(tt) == 200 == len(yy)
    assert tt[0] == pytest.approx(0.010, abs=1e-9)
    assert tt[-1] == pytest.approx(0.01995, abs=1e-9)


def test_average_waves_pointwise(chk):
    assert chk.average_waves([[1.0, 2.0], [3.0, 4.0]]) == [2.0, 3.0]
    assert chk.average_waves([[1.0, 2.0], [1.0, 2.0]]) == [1.0, 2.0]


def test_end_to_end_passes_and_matches(chk, capsys):
    """跑一遍归档数据：必须 PASS，且四项差值落在各自容差内。"""
    rc = chk.main(["--tags", "s025,s075,s125", "--skew-slot", "0.5"])
    assert rc == 0
    import json
    d = json.loads((FEA / "skew_slice_check.json").read_text(encoding="utf-8"))
    c = d["compare"]
    assert c["cogging_pp_nm"]["gap"] <= c["cogging_pp_nm"]["tol"]
    assert abs(c["bemf_phase_rms_v"]["gap_pct"]) <= c["bemf_phase_rms_v"]["tol_pct"]
    assert abs(c["thd_line_pct"]["gap_pt"]) <= c["thd_line_pct"]["tol_pt"]
    assert abs(c["k1_fundamental_ratio"]["gap_pct"]) <= c["k1_fundamental_ratio"]["tol_pct"]
    assert d["pass"] is True


def test_slices_really_rotated(chk):
    """旋转生效的判据：三片波形不能逐点相同（否则是基线被当成斜槽）。"""
    import json
    d = json.loads((FEA / "skew_slice_check.json").read_text(encoding="utf-8"))
    assert d["fea"]["slice_rotation_effective"] is True
    assert d["fea"]["slice_spread_nm"] > 0.1      # 实测 0.64 N·m


def test_noload_slices_have_zero_mean(chk):
    """空载切片的平均转矩必须是 0 量级 —— 拿它比负载转矩就是口径错。"""
    import json
    d = json.loads((FEA / "skew_slice_check.json").read_text(encoding="utf-8"))
    assert abs(d["fea"]["T_mean_of_slices_nm"]) < 0.05


def test_not_covered_is_documented(chk):
    """未覆盖项必须写进 JSON，不许用 PASS 掩盖「负载侧没跑真机」。"""
    import json
    d = json.loads((FEA / "skew_slice_check.json").read_text(encoding="utf-8"))
    nc = d["compare"]["not_covered"]
    assert "load_torque_3slice_fea" in nc
    assert "continuous_vs_3slice" in nc
