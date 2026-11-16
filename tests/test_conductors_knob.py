"""P12：匝数旋钮 `--conductors-per-slot`（40→42）必须是**单变量**。

背景
----
G7 斜槽把线 THD 11.180% → 1.9983%、齿槽 → 0.002%、脉动 → 4.285%，代价是基波降额
k1=0.95493，相 BEMF 120.5577 → 114.3847 V（跌出 118 V 下限）。P12 的对策是提高
每相匝数。Maxwell 的 `Conductor number` 是**单个槽边**的导体数，每相匝数 = 2·cps
（12 槽 × cps ÷ 3 相 ÷ 2），故 cps 40→42 ⇔ 80→84 匝（+5.00%，账本写的 N=85 = +4.94%
在整数约束下只有 42 可实现）。

必须钉死的三件事
----------------
1. **只改匝数**：42 与 40 的生成物差异必须恰好是 12 行 `Conductor number`；
   几何/材料/边界/网格/求解器逐字不变。否则"匝数效应"里混进了别的变量；
2. **基线不动**：默认 cps=40 必须仍与磁盘上的冻结产物逐字一致（`--check` 8/8）；
3. **门禁不被绕过**：`--check` 只对 cps=40 的空载基线有意义，写成别的组合必须 rc=2。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"
OTHER_SCRIPTS = ("setup", "materials", "geometry", "boundary", "mesh", "solver")


def _load_gen():
    spec = importlib.util.spec_from_file_location("gen_cps_knob", PROJ / "gen_maxwell_model.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


def _render(gen, cps: int, load: bool = False) -> dict:
    cfg = gen.build_config(load=load, conductors_per_slot=cps)
    return {k: v.splitlines() for k, v in gen.render_scripts(cfg).items()}


class TestTurnsMapping:
    def test_default_is_80_turns(self, gen) -> None:
        """cps=40 ⇒ 80 匝；文档里的 81 匝是名义值（差 1.25%），历史口径不动。"""
        cfg = gen.build_config()
        assert cfg.conductors_per_slot == 40
        assert cfg.turns_per_phase == 80

    def test_42_conductors_is_84_turns(self, gen) -> None:
        cfg = gen.build_config(conductors_per_slot=42)
        assert cfg.conductors_per_slot == 42
        assert cfg.turns_per_phase == 84
        assert 84 / 80 == pytest.approx(1.05)

    def test_validate_passes(self, gen) -> None:
        cfg = gen.build_config(conductors_per_slot=42)
        assert not [i for i in cfg.validate() if i.startswith("ERROR")]


class TestSingleVariable:
    def test_only_conductor_number_changes(self, gen) -> None:
        a = _render(gen, 40)
        b = _render(gen, 42)
        diff = [(x, y) for x, y in zip(a["winding"], b["winding"]) if x != y]
        assert len(diff) == 12
        for x, y in diff:
            assert '"Conductor number:=", "40"' in x
            assert '"Conductor number:=", "42"' in y

    def test_other_scripts_untouched(self, gen) -> None:
        a = _render(gen, 40)
        b = _render(gen, 42)
        for key in OTHER_SCRIPTS:
            assert a[key] == b[key], key

    def test_load_branch_also_scales(self, gen) -> None:
        """负载生成物同样只差 12 行导体数（激励表达式与 cps 无关）。"""
        a = _render(gen, 40, load=True)
        b = _render(gen, 42, load=True)
        diff = [(x, y) for x, y in zip(a["winding"], b["winding"]) if x != y]
        assert len(diff) == 12
        assert a["solver"] == b["solver"]


class TestBaselineFrozen:
    def test_default_still_matches_disk(self, gen) -> None:
        assert gen.check(str(MODEL_DIR), gen.build_config()) == []

    def test_check_rejects_non_baseline(self, gen, tmp_path, capsys) -> None:
        rc = gen.main(["--check", "--conductors-per-slot", "42"])
        assert rc == 2
        assert "只对空载基线" in capsys.readouterr().out

    def test_rejects_degenerate_turns(self, gen, tmp_path) -> None:
        assert gen.main(["--conductors-per-slot", "1", "--out_dir", str(tmp_path)]) == 2
