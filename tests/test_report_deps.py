"""G2 回归：报告链路（``make_report.py``）的第三方依赖必须声明在 ``[project].dependencies``。

背景（审计项 P2）：干净 venv 执行 ``pip install -e .`` 后，``projects/25Nm_PMSM/make_report.py``
在 ``import matplotlib`` 处直接 ``ModuleNotFoundError``（rc=1），报告交付链断在第一条 import。
本模块锁定两条契约：

1. numpy / matplotlib 属于核心依赖，不得被挪回 optional extra（否则 ``pip install -e .`` 不再自足）；
2. ``make_report.py`` 缺包时必须给出中文可读提示并以 rc=2 退出，而不是抛裸栈。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
MAKE_REPORT = ROOT / "projects" / "25Nm_PMSM" / "make_report.py"

# 设计链路（sim_analytical / thermal / nvh / sensitivity / make_report）实际 import 的第三方包
REQUIRED_PACKAGES = ("numpy", "matplotlib")


def _normalize(spec: str) -> str:
    """把 ``numpy>=1.24`` / ``matplotlib>=3.7; python_version>'3.9'`` 归一成包名。"""
    return re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0].strip().lower()


def _core_dependencies() -> list[str]:
    """返回 ``[project].dependencies`` 的条目列表。

    CI 矩阵含 Python 3.10（无 ``tomllib``），因此保留文本解析兜底路径，避免用
    ``importorskip`` 直接把测试跳过。
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10 兜底
        block = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)^\]", text)
        assert block, "pyproject.toml 缺少 [project].dependencies"
        return re.findall(r'"([^"]+)"', block.group(1))

    return list(tomllib.loads(text)["project"]["dependencies"])


@pytest.mark.parametrize("pkg", REQUIRED_PACKAGES)
def test_core_dependencies_declare_report_stack(pkg: str) -> None:
    """numpy / matplotlib 必须在核心 dependencies 中（不允许只在 [plot] extra）。"""
    specs = _core_dependencies()
    names = [_normalize(s) for s in specs]
    assert pkg in names, f"{pkg} 未在 [project].dependencies 声明，当前为：{specs}"


def test_make_report_imports_are_all_declared() -> None:
    """make_report.py 里出现的第三方顶层 import 都必须已在 dependencies 中声明。"""
    src = MAKE_REPORT.read_text(encoding="utf-8")
    names = [_normalize(s) for s in _core_dependencies()]
    for mod in REQUIRED_PACKAGES:
        if re.search(rf"^\s*(?:import|from)\s+{mod}\b", src, re.M):
            assert mod in names, f"make_report.py 依赖 {mod}，但未在 dependencies 中声明"


def test_make_report_guards_missing_dependency() -> None:
    """缺包路径：捕获 ModuleNotFoundError、打印安装提示、以 rc=2 退出。"""
    src = MAKE_REPORT.read_text(encoding="utf-8")
    assert "except ModuleNotFoundError" in src, "make_report.py 缺少缺包保护，会抛裸栈"
    assert "pip install -e ." in src, "缺包提示未给出 pyproject 声明后的标准安装命令"
    assert "sys.exit(2)" in src, "缺包时应以 rc=2 退出，便于 CI/脚本区分环境错误"
