"""求解器存场设置（`scripts/main.py::_gen_solver`）的护栏测试 — 不依赖 Maxwell。

为什么值得测
------------
2026-11-19 的 G4-B 现场核对发现：生成器写的

    "SaveFieldsType:=", "Every N Steps",
    "N:=", "2",

在 21.1 里**只生效一半**。落盘真值是

    SaveFieldsType='Every N Steps' + 'N Steps'='0'

即 `"N:="` 是个静默无效键（不报错、不生效），实际存场退化成"仅末时刻"
（t=0.02 s 能查到场，t=0.0105 s 查不到）。而旧注释却写着"隔步存场（N=2）"，
代码在自我叙述一个不存在的行为 —— 这正是反自演纪律要禁止的。

正确键名至今没测出来：**已求解的工程上 InsertSetup 对所有数组都 raise**
（含历史上能用的旧数组，见 `D:/ANSYS_Run/app_g4b_keytest.log`），
所以无法在解后改 setup 试键名。此处只钉死两件事：

1. 无效键 `"N:="` 不得回潮 —— 它会被误读成"已隔步存场"；
2. 存场开关 `SaveFieldsType` 必须仍然存在 —— 删掉它会让 G4 场探针无场可查。

真值校验不在本测试（要跑 Maxwell），而在 G4-B 的证据链：
`projects/results/fea/g4_flux_summary.json` + `app_g4b_calc45.log`。
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOLVER_PY = ROOT / "projects" / "25Nm_PMSM" / "maxwell_model" / "solver.py"


def _load_main():
    spec = importlib.util.spec_from_file_location("main_mod", ROOT / "scripts" / "main.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def solver_text() -> str:
    assert SOLVER_PY.is_file(), f"生成物缺失: {SOLVER_PY}"
    return SOLVER_PY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def setup_block(solver_text: str) -> str:
    """截出 `InsertSetup("Transient", [...])` 的数组体，避开文件头注释。"""
    m = re.search(r'InsertSetup\("Transient",\s*\[(.*?)\]\)', solver_text, re.S)
    assert m, "solver.py 里找不到 InsertSetup(\"Transient\", [...]) 块"
    return m.group(1)


def _strip_comments(block: str) -> str:
    """去掉 `#` 注释行，避免注释里引用的旧写法被当成真代码。"""
    keep = [ln for ln in block.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(keep).replace(" ", "")


class TestSaveFieldsKeys:
    def test_transient_setup_uses_correct_api_arity(self, solver_text: str):
        """`InsertSetup` 仍然是 (type, array) 两参数调用。"""
        assert 'InsertSetup("Transient"' in solver_text

    def test_invalid_N_key_absent(self, setup_block: str):
        """无效键 `"N:="` 不得回潮（21.1 静默忽略，落成 N Steps='0'）。"""
        assert '"N:="' not in _strip_comments(setup_block), (
            'solver.py 又写回了无效键 "N:="；21.1 会静默忽略它，'
            "实际只存末时刻场，注释不得声称隔步存场"
        )

    def test_save_fields_switch_present(self, setup_block: str):
        """存场开关必须在 —— 没有它 G4 场探针拿不到任何场。"""
        assert '"SaveFieldsType:="' in _strip_comments(setup_block)

    def test_no_unverified_multistep_claim(self, solver_text: str):
        """注释里不得再出现"隔步存场（N=2）"这类与落盘值矛盾的断言。"""
        assert "隔步存场（N=2）" not in solver_text
        assert "存场减半" not in solver_text


@pytest.fixture(scope="module")
def emitted() -> str:
    mod = _load_main()
    # _gen_solver(self, freq) 只读 self.config 的一个字段：
    #   sim_time_step_override（None → 历史口径 max(1/(200f), 5e-5)）
    class _Stub:
        config = type("C", (), {"sim_time_step_override": None})()

    return mod.MotorModelBuilder._gen_solver(_Stub(), 100.0)   # 100 Hz → 2 周期 0.02 s


class TestGeneratorEmission:
    """生成器直接产出的文本也要满足同一约束（防"改了生成物没改模板"）。"""

    def test_emitted_has_no_invalid_N_key(self, emitted: str):
        assert '"N:="' not in _strip_comments(emitted)

    def test_emitted_keeps_save_fields_switch(self, emitted: str):
        assert "SaveFieldsType" in emitted

    def test_emitted_step_matches_artifact_口径(self, emitted: str):
        """100 Hz / 无覆盖 ⇒ 0.0200s + 50 µs，与仓库生成物同一口径。"""
        assert '"StopTime:=", "0.0200s"' in emitted
        assert '"TimeStep:=", "0.000050s"' in emitted
