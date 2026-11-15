"""M7（2026-11-15）：模板路径负载工况的激励口径护栏。

为什么需要这一组
----------------
M7 的目标是「同一份模板，换激励就能跑负载」，从而把 G6 最后一条验收
（负载 `T_avg`）从手写路径搬到生成器路径上。这里最容易出的错不是求解，
而是**激励字符串**：

* 相位漏写/写错（120/240/0° → 0/120/240°）⇒ 转矩按 cos(误差) 掉，但波形依旧「像」；
* 符号写成 +1（发电）⇒ T_avg 变负，却仍能解出 401 点；
* 幅值忘了乘 √2 ⇒ 转矩正好小 29.3%。

这些错误在 `.aedt` 里都看不出来（几何加密、表达式是明文但没人逐字比对），
所以必须在生成器层钉死。另外本文件守住一条**基线不可漂移**：
空载生成物必须与 G4/M8 解过的模型逐字一致（`--check` 无漂移），
否则「M8 齿槽 0.8801 N·m」这张证据就不再对应仓库里的模型。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"

I_RMS = 9.89
I_PEAK = I_RMS * math.sqrt(2.0)      # 13.9866 A
F_ELEC = 100.0                       # 8 极 @ 1500 rpm


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "gen_maxwell_model_m7", PROJ / "gen_maxwell_model.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


@pytest.fixture(scope="module")
def noload_scripts(gen):
    return gen.render_scripts(gen.build_config())


@pytest.fixture(scope="module")
def load_scripts(gen):
    return gen.render_scripts(gen.build_config(load=True))


# ────────────────────────────────────────────────────────────────
#  1. 空载必须逐字不变（基线不漂移）
# ────────────────────────────────────────────────────────────────
def test_noload_winding_still_zero_current(noload_scripts):
    """空载绕组仍是 "0A"，且没有引入 CURRENTS 查找表。"""
    src = noload_scripts["winding"]
    assert '"Current:=", "0A"' in src
    assert "CURRENTS" not in src


def test_noload_artifacts_match_frozen_baseline(gen):
    """仓库里的 8 个生成物必须与模板逐字一致（= M8 真机解过的那份模型）。"""
    drift = gen.check(str(MODEL_DIR), gen.build_config())
    assert drift == [], f"空载生成物漂移，M8 基线证据失效: {drift}"


# ────────────────────────────────────────────────────────────────
#  2. 负载激励的三个要素：幅值 / 相位 / 符号
# ────────────────────────────────────────────────────────────────
def test_load_current_amplitude_is_sqrt2_rms(load_scripts):
    src = _code(load_scripts["winding"])
    assert ("'A': '-%.4f*sin(2*pi*%g*Time" % (I_PEAK, F_ELEC)) in src


def test_load_phase_angles_are_120_240_0(load_scripts):
    """A→+120°、B→+240°、C→0°（电角）；与 m4_build_solve.PHASE_DEG 同口径。"""
    src = _code(load_scripts["winding"])
    assert "+%.6f" % math.radians(120.0) in src      # +2.094395
    assert "+%.6f" % math.radians(240.0) in src      # +4.188790
    # C 相无相位项：表达式以 Time 收尾后紧跟右括号
    assert "'C': '-%.4f*sin(2*pi*%g*Time)'" % (I_PEAK, F_ELEC) in src


def test_load_sign_negative_is_motoring(load_scripts):
    """sign=−1 ⇒ 每条表达式带前导负号（电动：i 与 e=−dλ/dt 反相）。"""
    body = [ln for ln in _code(load_scripts["winding"]).splitlines() if ln.startswith("CURRENTS")]
    assert body and body[0].count("'-") == 3


def test_sign_plus_one_flips_to_generating(gen):
    cfg = gen.build_config(load=True)
    cfg.current_sign = 1
    src = gen.render_scripts(cfg)["winding"]
    line = [ln for ln in _code(src).splitlines() if ln.startswith("CURRENTS")][0]
    assert "13.9866*sin" in line and "'-" not in line


# ────────────────────────────────────────────────────────────────
#  3. 负载模型 = 空载模型 + 只换激励
# ────────────────────────────────────────────────────────────────
def test_load_differs_from_noload_only_in_winding(gen, noload_scripts, load_scripts):
    diff = {k for k in noload_scripts if noload_scripts[k] != load_scripts[k]}
    assert diff == {"winding"}, f"负载工况不该改建模，实际差异: {sorted(diff)}"


def test_load_check_flag_is_rejected(gen):
    """负载生成物不入库，--check 只对空载基线有意义。"""
    assert gen.main(["--case", "load", "--check"]) == 2


# ────────────────────────────────────────────────────────────────
#  4. 配置闸口
# ────────────────────────────────────────────────────────────────
def test_load_case_requires_positive_current(gen):
    cfg = gen.build_config(load=True)
    cfg.rated_current_rms = 0.0
    issues = cfg.validate()
    assert any("rated_current_rms" in i and i.startswith("ERROR") for i in issues)


def test_load_case_validates_clean(gen):
    issues = gen.build_config(load=True).validate()
    assert not [i for i in issues if i.startswith("ERROR")]


def test_current_sign_out_of_range_is_error(gen):
    cfg = gen.build_config(load=True)
    cfg.current_sign = 0
    assert any("current_sign" in i for i in cfg.validate())


def _code(src: str) -> str:
    """去掉整行注释（注释里会引用示例表达式，不能拿来做正向断言）。"""
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
