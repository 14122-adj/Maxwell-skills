"""Maxwell 批跑脚本转换器回归测试（M0/M1/M2 打通）。

对应缺陷（2026-11-07 实测）：
1. ``ansysedt.exe -RunScriptAndExit`` 模式**不能**带 ``-ng``（``-ng`` 仅与
   ``-batchsolve/-batchsave/-batchextract`` 组合），否则 rc=1 且零日志——此前
   被误判为「沙箱环境 blocked」。
2. 该模式由 AEDT 预注入 ``oDesktop``，脚本内 ``ScriptEnv.GetDesktop()`` 会抛
   ``AttributeError: 'module' object has no attribute 'GetDesktop'``。
3. 内嵌 IronPython 为 2.7，f-string 属语法错误。

因此 ``prepare_batch.to_batch_script()`` 必须剥掉 ScriptEnv 依赖并把
f-string 降级，否则 Maxwell 侧必然失败。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "projects" / "25Nm_PMSM" / "maxwell_model"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, MODEL_DIR / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def prepare_batch():
    return _load("prepare_batch")


@pytest.fixture(scope="module")
def build_source() -> str:
    return (MODEL_DIR / "build_25Nm_SPMSM.py").read_text(encoding="utf-8")


class TestScriptEnvStripping:
    def test_initialize_removed(self, prepare_batch, build_source):
        out = prepare_batch.to_batch_script(build_source)
        assert "ScriptEnv.Initialize(" not in out
        assert "ScriptEnv.GetDesktop()" not in out
        assert "ScriptEnv" not in out

    def test_desktop_global_not_rebound(self, prepare_batch, build_source):
        out = prepare_batch.to_batch_script(build_source)
        assert "oDesktop = ScriptEnv" not in out

    def test_multiline_import_keeps_other_modules(self, prepare_batch):
        src = "import ScriptEnv, math\nx = math.pi\n"
        out = prepare_batch.to_batch_script(src)
        assert out.splitlines()[0].strip() == "import math"
        assert "ScriptEnv" not in out


class TestPy2Compat:
    def test_coil_fstring_converted(self, prepare_batch):
        src = 'cname = f"Coil_{k + 1}"\n'
        out = prepare_batch.to_batch_script(src)
        assert "f\"Coil_" not in out
        assert '"Coil_" + str(k + 1)' in out

    def test_print_fstring_converted(self, prepare_batch):
        out = prepare_batch.to_batch_script('print(f"  kw = 0.866")\n')
        assert out.strip() == 'print("  kw = 0.866")'

    def test_no_fstring_left_in_body(self, prepare_batch, build_source):
        out = prepare_batch.to_batch_script(build_source)
        assert 'f"' not in out


class TestPrepareOutputs:
    def test_writes_body_and_driver(self, prepare_batch, build_source, tmp_path):
        script = tmp_path / "build.py"
        script.write_text(build_source, encoding="utf-8")
        paths = prepare_batch.prepare(str(script), str(tmp_path / "work"))

        body = Path(paths["body"]).read_text(encoding="utf-8")
        driver = Path(paths["driver"]).read_text(encoding="utf-8")
        assert "ScriptEnv" not in body
        assert "execfile" in driver
        assert "SaveAs" in driver

    def test_uses_forward_slashes(self, prepare_batch, build_source, tmp_path):
        script = tmp_path / "build.py"
        script.write_text(build_source, encoding="utf-8")
        paths = prepare_batch.prepare(str(script), str(tmp_path / "work"))
        assert "\\" not in paths["driver"]
        assert paths["driver"].endswith("m2_run.py")


class TestModelerApiRegressions:
    """建模脚本里三处 API 误用，均已在真机 rc=1 暴露。"""

    def test_set_model_units_key(self, build_source):
        assert '"NAME:UnitsSettings", "Units:=", "mm"' in build_source
        assert '"NAME:UnitsSettings", "Length:=", "mm"' not in build_source

    def test_duplicate_around_axis_has_options(self, build_source):
        idx = build_source.index("DuplicateAroundAxis(")
        block = build_source[idx: idx + 400]
        assert "NAME:Options" in block

    def test_slot_names_match_duplicate_output(self, build_source):
        # DuplicateAroundAxis 生成 Slot_1_1..Slot_1_11，不是 Slot_2..Slot_12
        assert '"Slot_1_" + str(i)' in build_source
        assert '"Slot_2, Slot_3' not in build_source

    def test_materials_before_geometry(self, build_source):
        # PM 材料必须在几何前定义，否则 CreateRectangle 因未知材料失败
        assert build_source.index("# ============ MATERIALS") < build_source.index(
            "# ============ GEOMETRY"
        )
