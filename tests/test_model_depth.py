"""G3：2D 叠长（ModelDepth）注入回归测试。

对应缺陷（审计 G3 / S6 前置 blocker）
------------------------------------
``scripts/main.py::_gen_setup()`` 生成的 ``setup.py`` 与
``maxwell_model/solve_25Nm_SPMSM.py`` 都只写
``["NAME:DesignSettingsData", "PreserveTransientSolution:=", False, ...]``，
**从不写 ModelDepth**。Maxwell 2D 的默认深度是 **1 mm**（不是 0），
于是转矩/反电势/铁耗/铜耗全部按 1 mm 计算，物理量整体缩小约 160 倍，
而求解器不报任何错 —— 属"模型自洽、物理错量级"的静默错误。

验收口径（与 WEEKLY_GOALS G3 一致）
-----------------------------------
1. 生成物含 ``ModelDepth:="<stack_length>mm"``，且随 ``stack_length`` 变化；
2. 实机求解脚本 ``solve_25Nm_SPMSM.py`` 同步（且不再推荐互斥的 ``-ng``）；
3. 仓库内已提交的生成物与当前生成逻辑一致（防"改了模板没重生成"的漂移）；
4. ``validate()`` 拒绝非正叠长，``_gen_setup()`` 不产出 ``Nonemm``。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from main import MotorModelBuilder, format_mm
from motor_config import SlotType, create_motor_from_input

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"

# 与 pmsm_config.STACK_LENGTH_MM / m4_build_solve.MODEL_DEPTH 冻结值一致
STACK_MM = 160.0


def _load_pmsm_config():
    """按路径加载 projects/25Nm_PMSM/pmsm_config.py（纯常量模块，无第三方依赖）。"""
    spec = importlib.util.spec_from_file_location("pmsm_config_25nm", PROJ / "pmsm_config.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cfg(stack_length: float = STACK_MM):
    """25 N·m 8p12s 机型配置（几何与 gen_maxwell_model.py 同口径）。"""
    cfg = create_motor_from_input(
        f"slots=12 poles=8 stator_od=150 stator_id=93 stack_length={stack_length}"
    )
    # gen_maxwell_model.py 用的是平行壁矩形槽，默认 pear 会给出不同的 setup 打印串
    cfg.update(slot_type=SlotType.RECTANGULAR)
    return cfg


def _setup_script(stack_length: float = STACK_MM) -> str:
    return MotorModelBuilder(_cfg(stack_length)).generate_all_scripts()["setup"]


class TestFormatMm:
    """``format_mm`` 决定写进 AEDT 的字符串形态。"""

    @pytest.mark.parametrize(
        "value, expected",
        [
            (160.0, "160mm"),      # 冻结值：不能写成 160.0mm
            (160, "160mm"),
            (142.5, "142.5mm"),
            (0.675, "0.675mm"),    # 气隙口径也需要这种精度
            (50.0, "50mm"),
        ],
    )
    def test_values(self, value, expected) -> None:
        assert format_mm(value) == expected


class TestGeneratedSetup:
    """``_gen_setup()`` 必须把叠长写进 DesignSettingsData。"""

    def test_model_depth_present(self) -> None:
        script = _setup_script()
        assert '"ModelDepth:="' in script
        assert '"ModelDepth:=", "160mm"' in script

    def test_model_depth_in_design_settings_block(self) -> None:
        """必须位于 SetDesignSettings 的 DesignSettingsData 列表内，而不是散落的注释。"""
        script = _setup_script()
        block = re.search(
            r"SetDesignSettings\(\s*\[\"NAME:DesignSettingsData\",(.*?)\]\)",
            script,
            re.S,
        )
        assert block, "未找到 SetDesignSettings(DesignSettingsData) 调用"
        assert '"ModelDepth:="' in block.group(1)

    @pytest.mark.parametrize("stack", [120.0, 160.0, 180.0, 142.5])
    def test_follows_stack_length(self, stack: float) -> None:
        """换叠长，写进脚本的深度必须跟着变（不是硬编码 160）。"""
        script = _setup_script(stack)
        assert f'"ModelDepth:=", "{format_mm(stack)}"' in script

    def test_generated_code_is_syntactically_valid(self) -> None:
        """生成的文本必须是合法 Python（AEDT 内嵌 IronPython 2.7 更严格，
        先保证 py3 语法通过可拦住引号/换行类低级错误）。"""
        compile(_setup_script(), "<generated setup.py>", "exec")

    def test_rejects_non_positive_stack_length(self) -> None:
        for bad in (0.0, -5.0):
            with pytest.raises(ValueError):
                _setup_script(bad)


class TestValidateStackLength:
    """``validate()`` 是错误的第一道闸：非正叠长必须拦下。"""

    def test_zero_stack_length_is_error(self) -> None:
        issues = _cfg(0.0).validate()
        assert any(i.startswith("ERROR") and "叠" in i for i in issues)

    def test_negative_stack_length_is_error(self) -> None:
        issues = _cfg(-3.0).validate()
        assert any(i.startswith("ERROR") and "叠" in i for i in issues)

    def test_nominal_stack_length_passes(self) -> None:
        issues = _cfg(STACK_MM).validate()
        assert not [i for i in issues if i.startswith("ERROR")]

    def test_aspect_ratio_warning(self) -> None:
        """L/D > 3 只告警不报错（保留长机可行性，但提醒叠长异常）。"""
        issues = _cfg(500.0).validate()
        assert not [i for i in issues if i.startswith("ERROR")]
        assert any(i.startswith("WARNING") and "长径比" in i for i in issues)


class TestCommittedArtifacts:
    """仓库里的生成物不能与模板漂移（改模板必须重跑 gen_maxwell_model.py）。"""

    @pytest.mark.parametrize("fname", ["setup.py", "build_25Nm_SPMSM.py"])
    def test_generated_files_contain_model_depth(self, fname: str) -> None:
        path = MODEL_DIR / fname
        assert path.exists(), f"{path} 缺失"
        text = path.read_text(encoding="utf-8")
        assert f'"ModelDepth:=", "{format_mm(STACK_MM)}"' in text

    def test_generated_setup_matches_template(self) -> None:
        """生成物与当前模板逐字一致 —— 漂移即红灯（重跑生成器即可修复）。"""
        on_disk = (MODEL_DIR / "setup.py").read_text(encoding="utf-8")
        assert on_disk == _setup_script(STACK_MM)


class TestCombinedScriptApiFixes:
    """合并脚本里的 4 处真机修复不能被"重新生成"冲掉（G3 连带护栏）。

    背景：`maxwell_model/build_25Nm_SPMSM.py` 是 M2 阶段用真机报错逐条修出来的
    （`89d099e`），其中 4 处修复**没有回灌**到 `scripts/main.py` 的模板里。
    任何人重跑 `gen_maxwell_model.py` 都会把这 4 处改回旧写法，模型当场不可解，
    而 pytest 若只测 ModelDepth 是发现不了的 —— 所以在这里钉死。
    """

    def _text(self) -> str:
        return (MODEL_DIR / "build_25Nm_SPMSM.py").read_text(encoding="utf-8")

    def test_set_model_units_key(self) -> None:
        assert '["NAME:UnitsSettings", "Units:=", "mm"]' in self._text()
        assert '"Length:=", "mm"' not in self._text()

    def test_duplicate_around_axis_has_options(self) -> None:
        text = self._text()
        assert '"NAME:Options", "DuplicateAssignments:=", False' in text

    def test_slot_clone_names(self) -> None:
        """`DuplicateAroundAxis` 产出 Slot_1_1..Slot_1_11，按 Slot_2.. 去减必失败。"""
        text = self._text()
        assert '"Slot_1_" + str(i)' in text
        assert "Slot_1, Slot_2, Slot_3" not in text

    def test_model_depth_present(self) -> None:
        assert '"ModelDepth:=", "160mm"' in self._text()


class TestSolveScriptSync:
    """手写求解脚本 ``solve_25Nm_SPMSM.py`` 必须与配置同源。"""

    def _text(self) -> str:
        return (MODEL_DIR / "solve_25Nm_SPMSM.py").read_text(encoding="utf-8")

    def test_model_depth_matches_config(self) -> None:
        text = self._text()
        m = re.search(r'^MODEL_DEPTH\s*=\s*"([^"]+)"', text, re.M)
        assert m, "solve_25Nm_SPMSM.py 未定义 MODEL_DEPTH"
        cfg_stack = _load_pmsm_config().STACK_LENGTH_MM
        assert m.group(1) == format_mm(cfg_stack)

    def test_model_depth_used_in_design_settings(self) -> None:
        text = self._text()
        block = re.search(
            r'SetDesignSettings\(\s*\[\"NAME:DesignSettingsData\",(.*?)\]\)',
            text,
            re.S,
        )
        assert block, "未找到 SetDesignSettings(DesignSettingsData) 调用"
        assert '"ModelDepth:=", MODEL_DEPTH' in block.group(1)

    def test_no_mutually_exclusive_ng_flag(self) -> None:
        """``-ng`` 只能配 -batchsolve/-batchsave，与 -RunScriptAndExit 互斥。

        首行注释里若仍写着 ``-ng -RunScriptAndExit``，会把人再带回
        2026-11-07 之前的"启动即失败"老路。
        """
        text = self._text()
        assert "-ng -RunScriptAndExit" not in text
        assert "-RunScriptAndExit" in text
