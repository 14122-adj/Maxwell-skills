"""G7 斜槽多切片：`rotor_init_deg` 的几何注入（旋转磁钢扇区）。

为什么不走 `AssignBand` 的 `Init Pos`
-------------------------------------
2026-11-15 真机实测：把 `Init Pos` 写成 `"7.5deg"` 跑满 401 点（726 s），
转矩波形与基线**逐点相同**（max 差 3e-5 N·m、互相关滞后 0）——2021.1 的
`Init Pos` 不旋转几何。故 `Init Pos` 固定 `"0deg"`，转子初始角靠**几何**实现：
给 8 块磁钢的 `angle = i*pm_pitch` 加偏置。

为什么这样等价于转子转 Δ
------------------------
* `RotorOuter` 是轴对称环带、`Band`/`Region` 是整圆 ⇒ 转不转都一样；
* 磁化方向由材料里的 `Cylindrical + DirComp1=±1` 给出，是绕全局 Z 的径向，
  绕该轴旋转不变 ⇒ 转几何不需要改材料；
* 槽与绕组在定子上，不动。

两条静默失败必须钉死
--------------------
1. 偏置没进模型 ⇒ 三个切片波形相同，"斜槽结果"其实是基线，且不报错；
2. 顺手改坏了基线 ⇒ `--check` 8/8 漂移，M8 的 0.8801 N·m 不再对应当前仓库模型。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "25Nm_PMSM"
MODEL_DIR = PROJ / "maxwell_model"
SCRIPTS = ROOT / "scripts"


def _load_gen():
    spec = importlib.util.spec_from_file_location("gen_init_deg", PROJ / "gen_maxwell_model.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


def _render(gen, init_deg: float) -> dict:
    cfg = gen.build_config(init_deg=init_deg)
    return {k: v.splitlines() for k, v in gen.render_scripts(cfg).items()}


def _lines(lines, needle: str) -> list:
    """只取**代码行**：模板注释里也会写到同样的键名作为踩坑说明。"""
    return [ln for ln in lines if needle in ln and not ln.lstrip().startswith("#")]


def test_init_pos_stays_zero(gen):
    """`Init Pos` 必须是 "0deg" 常量：实测它不旋转几何，写成变量只会误导。"""
    hits = _lines(_render(gen, 7.5)["boundary"], "Init Pos:=")
    assert len(hits) == 1
    assert '"0deg"' in hits[0]
    assert "7.5" not in hits[0]


def test_default_geometry_has_no_offset(gen):
    """默认 0.0 必须是历史字面量 `angle = i * pm_pitch`（基线逐字不变）。"""
    geom = _render(gen, 0.0)["geometry"]
    hits = _lines(geom, "angle = i * pm_pitch")
    assert len(hits) == 1
    assert hits[0].strip() == "angle = i * pm_pitch"
    # 两处 `if angle > 0:`：线圈块（一直如此）+ 磁钢块（默认无偏置）
    assert len(_lines(geom, "if angle > 0:")) == 2
    assert len(_lines(geom, "if abs(angle) > 1e-9:")) == 0


def test_nonzero_injects_geometry_offset(gen):
    geom = _render(gen, 7.5)["geometry"]
    hits = _lines(geom, "angle = i * pm_pitch")
    assert len(hits) == 1
    assert hits[0].strip() == "angle = i * pm_pitch + 7.5"
    # i=0 的磁钢也要转，磁钢块 guard 必须换成 abs()（线圈块仍是 angle > 0）
    assert len(_lines(geom, "if angle > 0:")) == 1
    assert len(_lines(geom, "if abs(angle) > 1e-9:")) == 1


def test_only_two_lines_change(gen):
    """除 angle 与 guard 两行外，geometry 必须逐字不变（防止改坏基线）。"""
    a = _render(gen, 0.0)["geometry"]
    b = _render(gen, 2.5)["geometry"]
    assert len(a) == len(b)
    diff = [(x, y) for x, y in zip(a, b) if x != y]
    assert len(diff) == 2
    assert any("angle = i * pm_pitch" in x for x, _ in diff)
    assert any("if angle > 0:" in x for x, _ in diff)


def test_other_scripts_untouched(gen):
    """setup/materials/winding/boundary/mesh/solver 六个脚本必须与 init_deg 无关。"""
    a = _render(gen, 0.0)
    b = _render(gen, 12.5)
    for key in ("setup", "materials", "winding", "boundary", "mesh", "solver"):
        assert a[key] == b[key], key


def test_check_passes_on_frozen_baseline(gen):
    """`--check` 语义：默认配置的生成物与磁盘上冻结的 8 个文件逐字一致。"""
    cfg = gen.build_config()
    assert gen.check(str(MODEL_DIR), cfg) == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_validate_rejects_non_finite(gen, bad):
    cfg = gen.build_config()
    cfg.rotor_init_deg = bad
    issues = cfg.validate()
    assert any(i.startswith("ERROR") and "rotor_init_deg" in i for i in issues)


def test_validate_warns_beyond_one_rev(gen):
    cfg = gen.build_config()
    cfg.rotor_init_deg = 375.0
    issues = cfg.validate()
    assert any(i.startswith("WARNING") and "rotor_init_deg" in i for i in issues)


def test_validate_accepts_half_slot_pitch(gen):
    """0.5 槽距 = 15° 机械，是多切片要用的最大合法角。"""
    cfg = gen.build_config()
    cfg.rotor_init_deg = 15.0
    assert not [i for i in cfg.validate() if "rotor_init_deg" in i]


def test_slot_pitch_is_30deg(gen):
    """斜槽 0.5 槽距 = 15° 机械 = 60° 电角 —— 全链路唯一的角度基准。"""
    cfg = gen.build_config()
    assert cfg.slots == 12
    assert 360.0 / cfg.slots == 30.0
    assert 360.0 / cfg.slots * cfg.pole_pairs == 120.0
