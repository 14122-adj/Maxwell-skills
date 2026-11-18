"""E2：时间步旋钮 `--time-step-us` 必须是**单变量**（只改 TimeStep，不改点数以外的任何东西）。

背景
----
`docs/ENGINEERING_ACCEPTANCE.md` §3 要求「50 µs vs 25 µs，转矩/BEMF 变化 <2%」。
在此之前 `TimeStep` 由 `_gen_solver` 按电频率算死（`max(1/(f·200), 5e-5)` = 50 µs），
命令行无法造第二个水平，也就无法证明 401 点是"解收敛"而不是"步长恰好压中峰值"。

必须钉死的五件事
----------------
1. **只改步长**：25 µs 时生成物差异必须恰好是 `solver.py` 里 1 行 `TimeStep`；
   几何/材料/网格/绕组/边界逐字不变，`StopTime` 也不动（否则同时改了时长）；
2. **基线不动**：默认（0 → None）必须仍与磁盘冻结产物逐字一致（`--check` 8/8）；
3. **点数口径**：0.02 s / 25 µs = 800 步 ⇒ 801 个采样点（与 50 µs 的 401 点同口径）；
4. **字符串合法**：`0.000025s`，IronPython 侧不带浮点尾数；
5. **门禁不被绕过**：`--check` 只对空载基线（cps=40 / mesh=1.0 / 50 µs）有意义。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"
UNTOUCHED = ("setup", "materials", "geometry", "winding", "boundary", "mesh")


def _load_gen():
    spec = importlib.util.spec_from_file_location("gen_tstep_knob", PROJ / "gen_maxwell_model.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


def _render(gen, tstep_us: float, load: bool = False) -> dict:
    cfg = gen.build_config(load=load, time_step_us=tstep_us)
    return {k: v.splitlines() for k, v in gen.render_scripts(cfg).items()}


class TestDefaultFrozen:
    def test_default_is_none_override(self, gen) -> None:
        assert gen.build_config().sim_time_step_override is None

    def test_default_solver_is_50us(self, gen) -> None:
        body = "\n".join(_render(gen, 0.0)["solver"])
        assert '"StopTime:=", "0.0200s"' in body
        assert '"TimeStep:=", "0.000050s"' in body

    def test_default_still_matches_disk(self, gen) -> None:
        assert gen.check(str(MODEL_DIR), gen.build_config()) == []


class TestScaling:
    @pytest.mark.parametrize("us,expect", [(25.0, "0.000025s"), (20.0, "0.000020s")])
    def test_time_step_written(self, gen, us: float, expect: str) -> None:
        body = "\n".join(_render(gen, us)["solver"])
        assert '"TimeStep:=", "%s"' % expect in body

    def test_stop_time_unchanged(self, gen) -> None:
        """只动步长：0.02 s 不变 ⇒ 25 µs 就是 801 点，而不是"缩短时长"的假对比。"""
        body = "\n".join(_render(gen, 25.0)["solver"])
        assert '"StopTime:=", "0.0200s"' in body

    def test_no_float_tail(self, gen) -> None:
        body = "\n".join(_render(gen, 25.0)["solver"])
        assert "0000" not in body.replace("0.0200s", "").replace("0.000025s", "")


class TestSingleVariable:
    def test_only_solver_changes(self, gen) -> None:
        a, b = _render(gen, 0.0), _render(gen, 25.0)
        assert [k for k in a if a[k] != b[k]] == ["solver"]

    def test_exactly_one_parameter_line(self, gen) -> None:
        """1 行参数 + 1 行回显（`print("Solver configured...")`），没有第三处。"""
        a, b = _render(gen, 0.0), _render(gen, 25.0)
        diff = [(x, y) for x, y in zip(a["solver"], b["solver"]) if x != y]
        assert len(diff) == 2
        params = [y for _, y in diff if '"TimeStep:="' in y]
        assert len(params) == 1
        assert '"TimeStep:=", "0.000025s"' in params[0]
        assert any("Solver configured" in y for _, y in diff)

    @pytest.mark.parametrize("key", UNTOUCHED)
    def test_other_scripts_untouched(self, gen, key: str) -> None:
        assert _render(gen, 0.0)[key] == _render(gen, 25.0)[key]

    def test_load_branch_also_changes_only_solver(self, gen) -> None:
        a, b = _render(gen, 0.0, load=True), _render(gen, 25.0, load=True)
        assert [k for k in a if a[k] != b[k]] == ["solver"]


class TestGate:
    def test_check_rejects_non_baseline(self, gen, capsys) -> None:
        rc = gen.main(["--check", "--time-step-us", "25"])
        assert rc == 2
        assert "只对空载基线" in capsys.readouterr().out

    def test_rejects_out_of_range(self, gen, tmp_path) -> None:
        assert gen.main(["--time-step-us", "500", "--out_dir", str(tmp_path)]) == 2
        assert gen.main(["--time-step-us", "-1", "--out_dir", str(tmp_path)]) == 2
