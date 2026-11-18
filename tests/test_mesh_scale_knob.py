"""E1：网格旋钮 `--mesh-scale` 必须是**单变量**（只改网格，不改几何/激励）。

背景
----
`docs/ENGINEERING_ACCEPTANCE.md` §3 要求「3 档网格（粗/中/细），同一工况，
转矩/BEMF 变化 <2%」。在此之前，`mesh_airgap/teeth/pm/yoke` 只能改
`MotorConfig` 默认值，无法从命令行做水平对比，也就无法证明基线数字
（BEMF 120.5577 V / 齿槽 0.88009 N·m）不是网格产物。

必须钉死的四件事
----------------
1. **只改网格**：scale≠1.0 时生成物差异必须恰好是 `mesh.py` 里 4 行 `MaxLength`；
   几何/材料/绕组/边界/求解器逐字不变。否则"网格效应"里混进了别的变量；
2. **基线不动**：scale=1.0 必须仍与磁盘冻结产物逐字一致（`--check` 8/8）；
3. **缩放正确**：四个尺寸同比缩放（0.2/1.5/0.5/3.0 ×s），字符串不带浮点尾数；
4. **门禁不被绕过**：`--check` 只对 scale=1.0 的空载基线有意义，写成别的组合必须 rc=2。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"
UNTOUCHED = ("setup", "materials", "geometry", "winding", "boundary", "solver")


def _load_gen():
    spec = importlib.util.spec_from_file_location("gen_mesh_knob", PROJ / "gen_maxwell_model.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


def _render(gen, scale: float, load: bool = False) -> dict:
    cfg = gen.build_config(load=load, mesh_scale=scale)
    return {k: v.splitlines() for k, v in gen.render_scripts(cfg).items()}


class TestScaling:
    def test_default_is_frozen_baseline(self, gen) -> None:
        cfg = gen.build_config()
        assert (cfg.mesh_airgap, cfg.mesh_teeth, cfg.mesh_pm, cfg.mesh_yoke) == (
            0.2, 1.5, 0.5, 3.0)

    @pytest.mark.parametrize("scale", [1.5, 0.6])
    def test_all_four_lengths_scale(self, gen, scale: float) -> None:
        cfg = gen.build_config(mesh_scale=scale)
        for key, base in gen.MESH_BASE.items():
            got = getattr(cfg, "mesh_" + key)
            assert got == pytest.approx(base * scale, rel=1e-9), key

    def test_no_float_tail_in_script(self, gen) -> None:
        """`MaxLength` 会原样写进 IronPython；0.30000000000000004mm 这种不是参数。"""
        body = "\n".join(_render(gen, 1.5)["mesh"])
        assert "0.3mm" in body and "2.25mm" in body
        assert "4.5mm" in body and "0.75mm" in body
        assert "0000" not in body


class TestSingleVariable:
    @pytest.mark.parametrize("scale", [1.5, 0.6])
    def test_only_mesh_changes(self, gen, scale: float) -> None:
        a, b = _render(gen, 1.0), _render(gen, scale)
        changed = [k for k in a if a[k] != b[k]]
        assert changed == ["mesh"]

    @pytest.mark.parametrize("scale", [1.5, 0.6])
    def test_exactly_four_lines(self, gen, scale: float) -> None:
        a, b = _render(gen, 1.0), _render(gen, scale)
        diff = [(x, y) for x, y in zip(a["mesh"], b["mesh"]) if x != y]
        assert len(diff) == 4
        for x, y in diff:
            assert '"MaxLength:="' in x and '"MaxLength:="' in y

    @pytest.mark.parametrize("key", UNTOUCHED)
    def test_other_scripts_untouched(self, gen, key: str) -> None:
        assert _render(gen, 1.0)[key] == _render(gen, 0.6)[key]

    def test_load_branch_also_scales(self, gen) -> None:
        a, b = _render(gen, 1.0, load=True), _render(gen, 0.6, load=True)
        assert [k for k in a if a[k] != b[k]] == ["mesh"]


class TestBaselineFrozen:
    def test_default_still_matches_disk(self, gen) -> None:
        assert gen.check(str(MODEL_DIR), gen.build_config()) == []

    def test_check_rejects_non_baseline(self, gen, capsys) -> None:
        rc = gen.main(["--check", "--mesh-scale", "0.6"])
        assert rc == 2
        assert "只对空载基线" in capsys.readouterr().out

    def test_rejects_nonpositive_scale(self, gen, tmp_path) -> None:
        assert gen.main(["--mesh-scale", "0", "--out_dir", str(tmp_path)]) == 2
