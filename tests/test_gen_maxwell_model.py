"""G3b：建模模板 ←→ 生成物一致性 + 4 处真机 API 修复回灌护栏。

背景
----
`maxwell_model/build_25Nm_SPMSM.py` 的 4 处正确写法是 M2 阶段（2026-11-07）
靠真机报错逐条试出来的，但当时只改了产物、没改模板
（`scripts/main.py::_gen_geometry`）。于是重跑 `gen_maxwell_model.py` 会把模型
改回不可解，`pytest` 只测产物是发现不了的（产物当天是对的）。

G3b 已把 4 处修复回灌模板，并补上第 5 处（槽克隆体实名列表）。本文件的职责：
1. 钉死模板输出（而不是产物）里的 4 处写法 —— 回退模板立刻红灯；
2. 钉死「产物 == 模板输出」—— 改模板不重生成、或手改产物，都会红灯；
3. 四种槽型的几何脚本都必须语法自洽（PyLine 嵌套改错会在这里炸）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"


def _code(src: str) -> str:
    """去掉整行注释后的代码正文（注释里会引用"错误写法"，不能拿来做否定断言）。"""
    return "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "gen_maxwell_model_25nm", PROJ / "gen_maxwell_model.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


@pytest.fixture(scope="module")
def geometry(gen) -> str:
    """25 N·m 机型的模板产物（未落盘，直接来自 scripts/main.py）。"""
    return gen.render_scripts()["geometry"]


class TestArtifactsMatchTemplate:
    """生成物必须逐字等于当前模板输出 —— 这是"重生成入口可信"的最低条件。"""

    def test_no_drift(self, gen) -> None:
        drift = gen.check(str(MODEL_DIR))
        assert drift == [], f"生成物与模板漂移: {drift}（改模板后请重跑生成器）"

    def test_check_detects_drift(self, gen, tmp_path) -> None:
        """反向验证：护栏本身不是空转 —— 改一个字必须被 check 抓到。"""
        assert gen.check(str(tmp_path)) != []  # 空目录 ⇒ 全部 missing
        gen.write_all(str(tmp_path))
        assert gen.check(str(tmp_path)) == []
        target = tmp_path / "geometry.py"
        target.write_text(target.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")
        assert gen.check(str(tmp_path)) == ["geometry.py"]

    def test_artifact_count(self, gen) -> None:
        """7 个分脚本 + 1 个合并脚本，一个都不能少。"""
        assert sorted(gen.artifacts(str(MODEL_DIR))) == sorted(
            [f"{k}.py" for k in gen.ORDER] + ["build_25Nm_SPMSM.py"]
        )


class TestTemplateApiFixes:
    """4 处真机修复 + 第 5 处克隆体实名，必须落在**模板输出**里。"""

    def test_set_model_units_key(self, geometry) -> None:
        """`SetModelUnits` 的键是 ``Units``；写 ``Length`` 会被 AEDT 判未知键。"""
        assert '["NAME:UnitsSettings", "Units:=", "mm"]' in geometry
        assert '"Length:=", "mm"' not in geometry

    def test_duplicate_around_axis_has_options(self, geometry) -> None:
        """`DuplicateAroundAxis` 是 3 参接口，缺 ``NAME:Options`` 会报参数个数错误。"""
        idx = geometry.index("DuplicateAroundAxis(")
        block = geometry[idx: idx + 400]
        assert '"NAME:Options", "DuplicateAssignments:=", False' in block

    def test_slot_clone_names(self, geometry) -> None:
        """克隆体实名是 ``Slot_1_1..``，按 ``Slot_2..`` 去减必失败。"""
        assert '"Slot_1_" + str(i) for i in range(1, 12)' in geometry
        assert "Slot_1, Slot_2" not in geometry

    def test_polyline_points_nested_in_parameters(self, geometry) -> None:
        """点/段必须嵌进 ``PolylineParameters`` 字典，不能作为并列实参。"""
        assert '"IsPolylineClosed:=", True,\n     ["NAME:PolylinePoints"' in geometry
        # 旧写法：参数表在第一行就闭合（`True],`），点集被当成第 2 个位置参数
        assert '"IsPolylineClosed:=", True],' not in geometry


class TestGeometrySyntax:
    """四种槽型的几何脚本都必须能通过语法检查（嵌套改错会在这里炸）。"""

    @pytest.mark.parametrize("slot_type", ["rectangular", "pear", "trapezoidal", "round"])
    def test_geometry_compiles(self, gen, slot_type: str) -> None:
        from motor_config import SlotType

        cfg = gen.build_config()
        cfg.update(slot_type=SlotType(slot_type))
        src = gen.render_scripts(cfg)["geometry"]
        compile(src, f"<geometry {slot_type}>", "exec")

    def test_clone_count_follows_slot_count(self, gen) -> None:
        """12 槽 ⇒ range(1, 12)，即 1 个原体 + 11 个克隆。"""
        cfg = gen.build_config()
        assert '"Slot_1_" + str(i) for i in range(1, 12)' in gen.render_scripts(cfg)["geometry"]


class TestWindingTemplate:
    """绕组模板：2021.1 里 ``AssignCoilGroup`` 单数组调用必然失败。"""

    def test_uses_assign_coil_not_coil_group(self, gen) -> None:
        """实机报错：``AssignCoilGroup expects at least 2 arguments. 1 provided``。"""
        winding = _code(gen.render_scripts()["winding"])
        assert "AssignCoilGroup(" not in winding
        assert "AddWindingCoils(" not in winding
        assert winding.count("oModule.AssignCoil(") == 12

    def test_coil_carries_winding_and_polarity(self, gen) -> None:
        winding = gen.render_scripts()["winding"]
        assert '"Winding:=", "WindingA"' in winding
        assert '"PolarityType:=", "Positive"' in winding
        assert '"PolarityType:=", "Negative"' in winding

    def test_conductor_number_is_per_slot_side(self, gen) -> None:
        """`Conductor number` 是单槽边导体数（40），不是线圈匝数（20/40 口径混淆过一次）。"""
        winding = gen.render_scripts()["winding"]
        assert winding.count('"Conductor number:=", "40"') == 12

    def test_winding_groups_are_current_type(self, gen) -> None:
        winding = gen.render_scripts()["winding"]
        assert '"NAME:Winding" + phase' in winding
        assert '"Type:=", "Current"' in winding


class TestBoundaryTemplate:
    """运动带：键名与可选键都必须齐全，否则被当成平动。"""

    def test_band_key_is_init_pos_with_space(self, gen) -> None:
        boundary = _code(gen.render_scripts()["boundary"])
        assert '"Init Pos:=", "0deg"' in boundary
        assert '"InitPos:="' not in boundary

    def test_band_has_rotate_optional_keys(self, gen) -> None:
        boundary = gen.render_scripts()["boundary"]
        for key in ('"Coordinate System:=", "Global"', '"HasRotateLimit:=", False',
                    '"NonCylindrical:=", False', '"Consider Mechanical Transient:=", False'):
            assert key in boundary

    def test_band_objects_is_band_only(self, gen) -> None:
        assert '"Objects:=", ["Band"]' in gen.render_scripts()["boundary"]

    def test_vector_potential_uses_edges(self, gen) -> None:
        """实机报错：``can only be assigned on 1D entities`` —— 不能再传 Region sheet。"""
        boundary = _code(gen.render_scripts()["boundary"])
        assert '"Edges:=", edges' in boundary
        assert 'GetEdgeIDsFromObject("Region")' in boundary
        assert '"Objects:=", ["Region"]' not in boundary


class TestMeshTemplate:
    """2021.1 无 ``AssignSurfApproxOp``（实机不支持该剖分算子）。"""

    def test_no_surf_approx(self, gen) -> None:
        mesh = _code(gen.render_scripts()["mesh"])
        assert "AssignSurfApproxOp(" not in mesh
        assert '"NAME:Mesh_Band"' in mesh

    @pytest.mark.parametrize("key", ["winding", "boundary", "mesh", "solver"])
    def test_scripts_compile(self, gen, key: str) -> None:
        compile(gen.render_scripts()[key], f"<{key}>", "exec")
