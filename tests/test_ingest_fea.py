"""`ingest_fea.py` 回归测试（M4 数据回填链路）。

对应缺陷：旧版把 Maxwell `ExportToFile` 的输出当成「首行表头 + 纯数据」硬解析，
遇到「表头行 + 单位行 + 空行 + 数据块」的格式会整列错位；时间单位 ms 也未换算，
THD/线电势用错口径。本测试用合成 CSV 锁定解析与指标口径。
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"


def _load():
    spec = importlib.util.spec_from_file_location("ingest_fea", PROJ / "ingest_fea.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ing():
    return _load()


def _write_csv(path: Path, t_ms, cols: dict, units="ms", col_unit="V"):
    """按 Maxwell ExportToFile 的真实排版写文件：表头行 + 单位行 + 空行 + 数据。"""
    names = list(cols)
    lines = ["Time [%s]\t%s\t" % (units, "\t".join("%s [%s]" % (n, col_unit) for n in names)),
             ",".join([units] + [col_unit] * len(names)) + ",",
             ""]
    for i in range(len(t_ms)):
        lines.append("\t".join([repr(float(t_ms[i]))]
                               + [repr(float(cols[k][i])) for k in names]) + "\t")
    path.write_text("\n".join(lines), encoding="utf-8")


class TestCsvParsing:
    def test_header_units_and_scale(self, ing, tmp_path):
        p = tmp_path / "x.csv"
        _write_csv(p, [0.0, 0.05, 0.1], {"WindingA.Voltage": [0.0, 1.0, 2.0]})
        t, cols = ing.load_maxwell_csv(str(p))
        assert list(cols) == ["WindingA.Voltage"]
        assert t[0] == 0.0
        assert t[-1] == pytest.approx(1e-4, rel=1e-9)      # 0.1 ms -> 1e-4 s
        assert cols["WindingA.Voltage"][-1] == pytest.approx(2.0)

    def test_missing_numeric_block_raises(self, ing, tmp_path):
        p = tmp_path / "empty.csv"
        p.write_text("Time [ms]\tTorque\nms,Nm\n", encoding="utf-8")
        with pytest.raises(ValueError):
            ing.load_maxwell_csv(str(p))

    def test_seconds_unit_not_scaled(self, ing, tmp_path):
        p = tmp_path / "s.csv"
        _write_csv(p, [0.0, 0.5, 1.0], {"Moving1.Torque": [0.0, 1.0, 2.0]}, units="s")
        t, _ = ing.load_maxwell_csv(str(p))
        assert t[-1] == pytest.approx(1.0)


class TestMetrics:
    def test_rms_of_pure_sine(self, ing):
        f = ing.F_ELEC
        n = 3001
        t = [i * 0.06 / (n - 1) for i in range(n)]
        amp = 132.4 * math.sqrt(2.0)
        y = [amp * math.sin(2 * math.pi * f * ti) for ti in t]
        m = ing.analyse_signal(t, y, skip_first_period=False)
        assert m["rms"] == pytest.approx(132.4, rel=5e-3)
        assert m["peak"] == pytest.approx(amp, rel=5e-3)

    def test_thd_of_pure_sine_is_small(self, ing):
        f = ing.F_ELEC
        n = 1201
        t = [i * 0.06 / (n - 1) for i in range(n)]
        y = [math.sin(2 * math.pi * f * ti) for ti in t]
        assert ing.thd_percent(t, y) < 1.0

    def test_thd_rises_with_harmonic(self, ing):
        f = ing.F_ELEC
        n = 1201
        t = [i * 0.06 / (n - 1) for i in range(n)]
        y = [math.sin(2 * math.pi * f * ti) + 0.2 * math.sin(2 * math.pi * 5 * f * ti)
             for ti in t]
        assert ing.thd_percent(t, y) == pytest.approx(20.0, rel=0.05)

    def test_skips_first_period(self, ing):
        f = ing.F_ELEC
        n = 4001
        t = [i * 0.04 / (n - 1) for i in range(n)]
        y = [100.0 if ti < 1.0 / f else 1.0 for ti in t]   # 首周期人为污染
        m = ing.analyse_signal(t, y, skip_first_period=True)
        assert m["rms"] < 5.0


class TestFluxDerivative:
    """电流型绕组只有磁链输出，BEMF 必须由 e = −dλ/dt 得到（2026-11-08 实测）。"""

    def test_classify_column(self, ing):
        assert ing.classify_column("FluxLinkage(WindingA)", "Wb") == "flux"
        assert ing.classify_column("WindingA.Voltage", "V") == "voltage"
        assert ing.classify_column("Moving1.Torque", "NewtonMeter") is None

    def test_differentiate_linear_is_exact(self, ing):
        t = [0.0, 0.1, 0.2, 0.3]
        y = [0.0, 2.0, 4.0, 6.0]
        assert ing.differentiate(t, y) == pytest.approx([20.0] * 4)

    def test_differentiate_sine_matches_analytic(self, ing):
        w = 2 * math.pi * ing.F_ELEC
        n = 4001
        t = [i * 0.02 / (n - 1) for i in range(n)]
        lam = [math.sin(w * ti) for ti in t]
        d = ing.differentiate(t, lam)
        # 中心差分在内部点为二阶精度；跳过端点后逐点比对
        err = max(abs(d[i] - w * math.cos(w * t[i])) for i in range(1, n - 1))
        assert err < 1e-3 * w

    def test_flux_to_bemf_is_negative_derivative(self, ing):
        t = [0.0, 0.1, 0.2, 0.3]
        lam = [0.0, 2.0, 4.0, 6.0]
        assert ing.flux_to_bemf(t, lam) == pytest.approx([-20.0] * 4)

    def test_differentiate_rejects_short_input(self, ing):
        with pytest.raises(ValueError):
            ing.differentiate([0.0, 1.0], [0.0, 1.0])

    def test_differentiate_rejects_length_mismatch(self, ing):
        with pytest.raises(ValueError):
            ing.differentiate([0.0, 1.0, 2.0], [0.0, 1.0])


class TestFluxPath:
    """compute() 走 flux_*.csv → 求导 的完整链路。"""

    def _flux_set(self, tmp_path, ing, n=3001):
        """构造 λ = Λ·sin(ωt)，使求导后的 E_rms 恰好等于 132.4×(80/81)。"""
        f = ing.F_ELEC
        w = 2 * math.pi * f
        t = [i * 0.06 / (n - 1) for i in range(n)]
        e_rms_target = ing.E_ANALYTIC_PHASE_RMS * ing.TURNS_MODEL_DEFAULT / ing.TURNS_DESIGN
        lam_peak = e_rms_target * math.sqrt(2.0) / w
        for k, ph in enumerate("abc"):
            shift = -2.0944 * k
            _write_csv(tmp_path / ("flux_%s.csv" % ph), [ti * 1e3 for ti in t],
                       {"FluxLinkage(Winding%s)" % ph.upper():
                        [lam_peak * math.sin(w * ti + shift) for ti in t]},
                       col_unit="Wb")
        return t

    def test_compute_from_flux_csv(self, ing, tmp_path):
        self._flux_set(tmp_path, ing)
        res = ing.compute(str(tmp_path))
        assert res["status"] == "OK"
        assert res["bemf_source"]["A"].startswith("d(FluxLinkage")
        assert res["bemf_rms_phase"] == pytest.approx(130.77, rel=1e-2)
        assert res["turns"]["scale_to_design"] == pytest.approx(81.0 / 80.0, rel=1e-9)
        assert res["bemf_rms_phase_at_design_turns"] == pytest.approx(132.4, rel=1e-2)
        assert res["bemf_vs_analytic_pct"] == pytest.approx(0.0, abs=1.5)
        assert res["bemf_pass"] is True

    def test_line_direct_uses_a_minus_b(self, ing, tmp_path):
        self._flux_set(tmp_path, ing)
        res = ing.compute(str(tmp_path))
        ll = res["bemf_line_direct"]
        # 三相平衡时线电势 = 相电势 × √3
        assert ll["rms_v"] == pytest.approx(res["bemf_rms_phase"] * math.sqrt(3), rel=5e-3)

    def test_voltage_csv_preferred_over_flux(self, ing, tmp_path):
        n = 3001
        f = ing.F_ELEC
        t = [i * 0.06 / (n - 1) for i in range(n)]
        _write_csv(tmp_path / "bemf_a.csv", [ti * 1e3 for ti in t],
                   {"WindingA.Voltage": [10.0 * math.sqrt(2) * math.sin(2 * math.pi * f * ti)
                                         for ti in t]})
        _write_csv(tmp_path / "flux_a.csv", [ti * 1e3 for ti in t],
                   {"FluxLinkage(WindingA)": [0.1 * math.sin(2 * math.pi * f * ti)
                                              for ti in t]}, col_unit="Wb")
        res = ing.compute(str(tmp_path))
        assert res["bemf_source"]["A"] == "WindingA.Voltage"
        assert res["bemf_phase_A"]["rms_v"] == pytest.approx(10.0, rel=0.02)

    def test_line_to_line_needs_common_timebase(self, ing):
        phases = {"A": ([0.0, 0.1, 0.2], [1.0, 2.0, 3.0]),
                  "B": ([0.0, 0.1], [1.0, 2.0])}
        assert ing.line_to_line(phases, "A", "B") is None

    def test_turns_scale_one_means_no_change(self, ing, tmp_path):
        self._flux_set(tmp_path, ing)
        res = ing.compute(str(tmp_path), turns_model=ing.TURNS_DESIGN)
        assert res["bemf_rms_phase_at_design_turns"] == pytest.approx(res["bemf_rms_phase"])


class TestCompute:
    def test_three_phase_balance_and_cogging(self, ing, tmp_path):
        f = ing.F_ELEC
        n = 3001
        t = [i * 0.06 / (n - 1) for i in range(n)]
        amp = 132.4 * math.sqrt(2.0)
        _write_csv(tmp_path / "bemf_a.csv", [ti * 1e3 for ti in t],
                   {"WindingA.Voltage": [amp * math.sin(2 * math.pi * f * ti) for ti in t]})
        _write_csv(tmp_path / "bemf_b.csv", [ti * 1e3 for ti in t],
                   {"WindingB.Voltage": [amp * math.sin(2 * math.pi * f * ti - 2.0944)
                                         for ti in t]})
        _write_csv(tmp_path / "bemf_c.csv", [ti * 1e3 for ti in t],
                   {"WindingC.Voltage": [amp * math.sin(2 * math.pi * f * ti + 2.0944)
                                         for ti in t]})
        _write_csv(tmp_path / "tq_noload.csv", [ti * 1e3 for ti in t],
                   {"Moving1.Torque": [0.45 * math.cos(2 * math.pi * 12 * f * ti)
                                       for ti in t]})

        res = ing.compute(str(tmp_path))
        assert res["status"] == "OK"
        assert res["bemf_rms_phase"] == pytest.approx(132.4, rel=5e-3)
        assert res["bemf_rms_line"] == pytest.approx(132.4 * math.sqrt(3), rel=5e-3)
        assert res["bemf_balance_pct"] < 1.0
        assert res["cogging"]["peak_to_peak_nm"] == pytest.approx(0.9, rel=0.05)
        assert res["cogging"]["pct_of_rated"] == pytest.approx(3.6, rel=0.06)

    def test_status_no_data(self, ing, tmp_path):
        res = ing.compute(str(tmp_path))
        assert res["status"] == "NO_DATA"
        assert "hint" in res

    def test_main_writes_json(self, ing, tmp_path):
        f = ing.F_ELEC
        n = 3001
        t = [i * 0.06 / (n - 1) for i in range(n)]
        _write_csv(tmp_path / "bemf_a.csv", [ti * 1e3 for ti in t],
                   {"WindingA.Voltage": [10.0 * math.sqrt(2) * math.sin(2 * math.pi * f * ti)
                                          for ti in t]})
        out = tmp_path / "res.json"
        rc = ing.main(["--csvdir", str(tmp_path), "--out", str(out)])
        assert rc == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["bemf_phase_A"]["rms_v"] == pytest.approx(10.0, rel=0.02)

    def test_main_returns_3_on_no_data(self, ing, tmp_path):
        out = tmp_path / "res.json"
        rc = ing.main(["--csvdir", str(tmp_path), "--out", str(out)])
        assert rc == 3
