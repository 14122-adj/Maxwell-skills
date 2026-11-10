"""M6 回归：报告 §11「Maxwell 2D FEA 实测交叉校验」。

背景（M4/M5 踩坑）：报告一度只能出解析结果，FEA 数据无法进入交付物；同时 FEA 侧有两个
会静默产出错值的陷阱，必须由测试钉死：

1. ``fea_results.json`` 是报告 §11 的唯一数据源，字段一旦改名，``make_report.py`` 会在
   格式化时抛 ``KeyError`` —— 本模块锁定其结构；
2. ``results/fea/*.csv`` 必须是 **401 行全时长解**。5 行试算段（0–200 µs）会把 0.2 ms 的
   末点（tq≈0.40 N·m）当成齿槽峰值，产出「齿槽 1.6%」这类假结论；
3. 曲线上图的反电势必须由磁链求导得到（电流型绕组没有 ``WindingA.Voltage``），
   且数据缺失时报告要降级为解析版而不是崩溃。
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJ = ROOT / "projects" / "25Nm_PMSM"
RESULTS = ROOT / "projects" / "results"
FEA_JSON = RESULTS / "fea_results.json"
FEA_CSV = RESULTS / "fea"
MAKE_REPORT = PROJ / "make_report.py"

FULL_SOLUTION_ROWS = 401          # 0–20 ms / 50 µs 全时长解
TRIAL_ROWS_MAX = 25               # 试算段（10–21 行），出现即说明导出绑错解


def _load_ingest():
    """按路径载入 ``projects/25Nm_PMSM/ingest_fea.py``（该目录不是包）。"""
    spec = importlib.util.spec_from_file_location("ingest_fea_report_test",
                                                  PROJ / "ingest_fea.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fea() -> dict:
    assert FEA_JSON.exists(), "缺少 projects/results/fea_results.json（M4/M5 未回填）"
    return json.loads(FEA_JSON.read_text(encoding="utf-8"))


# ──────────────────────────── 数据契约 ────────────────────────────

def test_fea_results_schema() -> None:
    """§11 逐项取用的字段必须存在且为数值。"""
    fea = _fea()
    assert fea["status"] == "OK"
    for key in ("bemf_rms_phase", "bemf_rms_line", "bemf_balance_pct",
                "bemf_rms_phase_at_design_turns", "bemf_analytic_phase_rms",
                "bemf_vs_analytic_pct", "bemf_pass"):
        assert key in fea, "fea_results.json 缺字段 %s" % key
    assert "bemf_phase_A" in fea and "thd_pct" in fea["bemf_phase_A"]
    assert "turns" in fea and fea["turns"]["model_per_phase"] == 80
    assert fea["turns"]["design_per_phase"] == 81

    cg = fea["cogging"]
    for key in ("peak_to_peak_nm", "pct_of_rated", "pass_5pct", "n_samples"):
        assert key in cg, "cogging 缺字段 %s" % key

    load = fea["load"]
    for key in ("T_avg_nm", "T_ripple_pct", "vs_rated_pct", "pass_20pct",
                "Kt_nm_per_a_pk", "power_balance"):
        assert key in load, "load 缺字段 %s" % key


def test_fea_verdicts_match_design_record() -> None:
    """判据口径与 DESIGN_PROGRESS 一致：BEMF 过、负载过、齿槽不过。"""
    fea = _fea()
    assert fea["bemf_pass"] is True, "BEMF ±25% 判据应通过（−9.09%）"
    assert abs(fea["bemf_vs_analytic_pct"]) <= 25.0
    assert fea["cogging"]["pass_5pct"] is False, "齿槽 27.37% 未达标，不得被标成通过"
    assert fea["cogging"]["pct_of_rated"] > 5.0
    assert fea["load"]["pass_20pct"] is True, "负载 −10.66% 落在 ±20% 内"
    assert abs(fea["load"]["vs_rated_pct"]) <= 20.0


def test_fea_physical_sanity() -> None:
    """物理自洽：三相平衡、线=√3×相、BEMF 与转矩同向偏低、功率平衡闭合。"""
    fea = _fea()
    assert fea["bemf_balance_pct"] < 0.5, "三相不平衡应远小于 0.5%"
    line_expected = fea["bemf_rms_phase"] * math.sqrt(3.0)
    assert abs(fea["bemf_rms_line"] - line_expected) / line_expected < 0.01
    # 转矩与 BEMF 应同向偏低（同一个绕组因数口径），不能一正一负
    assert fea["bemf_vs_analytic_pct"] < 0, "BEMF 实测应低于解析（Kw 0.933 vs 0.866）"
    assert fea["load"]["vs_rated_pct"] < 0, "负载转矩实测应低于额定"
    pb = fea["load"]["power_balance"]
    assert pb["pass_10pct"] is True
    assert abs(pb["dev_pct"]) <= 10.0


@pytest.mark.parametrize("stem", ["flux_a", "flux_b", "flux_c", "tq_noload", "tq_load"])
def test_fea_csv_is_full_solution(stem: str) -> None:
    """波形留档必须是 401 行全时长解，且表头带单位方括号（解析器依赖单位行换算）。"""
    path = FEA_CSV / ("%s.csv" % stem)
    assert path.exists(), "缺少 %s —— §11 的图将无法复现" % path
    lines = [ln for ln in path.read_text(encoding="utf-8-sig",
                                         errors="ignore").splitlines() if ln.strip()]
    assert "[" in lines[0] and "]" in lines[0], "表头缺单位方括号：%r" % lines[0]
    n_rows = len(lines) - 1
    assert n_rows > TRIAL_ROWS_MAX, \
        "%s 只有 %d 行数据，疑似试算段（0–200 µs），不可作为全时长解" % (stem, n_rows)
    assert n_rows == FULL_SOLUTION_ROWS, \
        "%s 数据行 %d ≠ %d（0–20 ms / 50 µs）" % (stem, n_rows, FULL_SOLUTION_ROWS)


def test_ingest_reproduces_committed_results() -> None:
    """用留档 CSV 重算一遍，必须复现 fea_results.json（值是回填产物而非手填）。"""
    IF = _load_ingest()
    ref = _fea()
    got = IF.compute(str(FEA_CSV), turns_model=ref["turns"]["model_per_phase"])
    assert got["status"] == "OK"
    assert got["bemf_rms_phase"] == pytest.approx(ref["bemf_rms_phase"], rel=1e-3)
    assert got["bemf_vs_analytic_pct"] == pytest.approx(ref["bemf_vs_analytic_pct"],
                                                        abs=0.05)
    assert got["cogging"]["peak_to_peak_nm"] == pytest.approx(
        ref["cogging"]["peak_to_peak_nm"], rel=1e-3)
    assert got["load"]["T_avg_nm"] == pytest.approx(ref["load"]["T_avg_nm"], rel=1e-3)


# ──────────────────────────── 报告侧契约 ────────────────────────────

def test_make_report_reads_fea_and_derives_bemf() -> None:
    """make_report.py 必须读 fea_results.json，且反电势走 flux→emf 求导通道。"""
    src = MAKE_REPORT.read_text(encoding="utf-8")
    assert "fea_results.json" in src
    assert '"fea"' in src, "波形目录 results/fea 须作为常量出现"
    assert "flux_to_bemf" in src, \
        "电流型绕组无 Voltage 列，§11 的 BEMF 必须由 FluxLinkage 求导"
    assert "11. Maxwell 2D FEA" in src, "报告缺少 §11 章节标题"


def test_make_report_degrades_without_fea() -> None:
    """FEA 数据缺失时必须降级（不抛栈），并给出恢复路径。"""
    src = MAKE_REPORT.read_text(encoding="utf-8")
    assert "def load_fea(" in src
    assert "降级为空" in src
    assert "ingest_fea.py" in src, "降级提示应给出回填命令入口"
