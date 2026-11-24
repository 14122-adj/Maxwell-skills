"""IPM 8p48s（2026-11-22 改单层 V + 槽内对称绕组）：48 槽梨形槽 / q=2 双层绕组 / 单层 V 磁钢 的几何护栏。

为什么需要这一组
----------------
新项目的第一天最容易「拍脑袋填数」：把表 2 的 12 槽梨形槽缩小 1/4 当 48 槽用、
把集中绕组的 12 槽相属表加个循环当分布绕组、把 8 块表贴磁钢复制 2 份当单层 V。
这三件事都能建出「看起来像电机」的模型，但 FEA 出来全是废数。本文件把
`projects/IPM_8p48s/ipm_geom.py` 与 `ipm_winding.py` 的定源结论钉死：

1. **I1**：7 个槽尺寸由约束链算出（齿宽/轭厚/槽满/铜耗），槽面积 38.886 mm²（2026-11-24 Bs0=1.0+Hs0=0.5+yoke15）、
   齿部最窄 3.44 mm、轭厚 15.0 mm、`Rs = Bs2/2` 是相切恒等式；
2. **I2**：q=2、y=5 的双层 60° 相带 ⇒ 96 边、每相 16 线圈、k_w1=0.9330、
   k_w5=k_w7=0.0670（短距 1 槽的直接效果）；
3. **I4**：每极 1 组 V × 2 块 × 8 极 = 16 块（单层 V），块块在转子内且桥厚达标。
4. **I2 槽内排布**：两条边按切向 y=0 对称并排（非径向一远一近），距气隙等距。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_IPM = _ROOT / "projects" / "IPM_8p48s"
if str(_IPM) not in sys.path:
    sys.path.insert(0, str(_IPM))

import ipm_geom  # noqa: E402
import ipm_winding  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return ipm_geom.IPMConfig()


@pytest.fixture(scope="module")
def i1(cfg):
    return ipm_geom.derive_slot(cfg)


@pytest.fixture(scope="module")
def i2(cfg):
    return ipm_winding.analyze(cfg)


@pytest.fixture(scope="module")
def i4(cfg):
    return ipm_geom.derive_rotor(cfg)


# ------------------------------------------------------------------ I1 槽型
def test_i1_all_checks_pass(i1):
    assert i1["status"] == "PASS", [c for c in i1["checks"] if c["status"] != "PASS"]


def test_i1_config_matches_derivation(cfg, i1):
    """配置里的 7 个尺寸必须就是推导结果（两边漂移会静默生成错几何）。"""
    d = i1["dims"]
    assert cfg.slot_Bs0 == d["Bs0"]
    assert cfg.slot_Hs0 == d["Hs0"]
    assert cfg.slot_Bs1 == d["Bs1"]
    assert cfg.slot_Hs1 == d["Hs1"]
    assert cfg.slot_Bs2 == d["Bs2"]
    assert cfg.slot_Rs == d["Rs"]
    assert cfg.slot_Hs2 == d["Hs2"]


def test_i1_slot_area_and_yoke(i1):
    # 2026-11-24 Bs0 2.2→1.0（案例定制），槽面积 39.2→34.336
    assert i1["areas"]["slot_analytic"] == pytest.approx(38.886, abs=0.3)
    assert i1["radii"]["h_yoke"] == pytest.approx(15.0, abs=1e-9)
    assert i1["flux"]["B_tooth_min"] <= 1.65
    assert i1["flux"]["B_yoke"] <= 1.45


def test_i1_tangency_holds(cfg):
    """Rs = Bs2/2 不是习惯，是「半圆底与直身相切」的恒等式：两端点必须落在直身边上。"""
    sc = ipm_geom.slot_only(cfg)
    pts = ipm_geom.slot_profile.pear_key_points(sc)
    assert pts[4][1] == pytest.approx(-cfg.slot_Bs2 / 2.0)
    assert pts[6][1] == pytest.approx(cfg.slot_Bs2 / 2.0)
    assert pts[5][0] - pts[4][0] == pytest.approx(cfg.slot_Rs)
    assert pts[5][0] == pytest.approx(cfg.stator_id / 2.0 + cfg.slot_Hs2)


def test_i1_slot_not_through_stator(cfg):
    r_out = cfg.stator_od / 2.0
    x4 = cfg.stator_id / 2.0 + cfg.slot_Hs2
    assert x4 < r_out - 10.0          # 槽底离外圆还有 10 mm 以上
    # 相邻槽底不能相交：圆心处槽距 > 槽宽
    pitch = 2 * math.pi * (x4 - cfg.slot_Rs) / cfg.slots
    assert pitch - cfg.slot_Bs2 > 1.0


def test_i1_coil_inside_slot(cfg):
    """两条边必须都在槽内、关于切向中心线对称、互不相交（0.4 mm 绝缘）。"""
    layers = ipm_geom.coil_layers(cfg)
    sc = ipm_geom.slot_only(cfg)
    outline = ipm_geom.slot_profile.pear_outline(sc)
    assert ipm_geom.poly_dist(layers["upper"], outline) > 0.1
    assert ipm_geom.poly_dist(layers["lower"], outline) > 0.1
    assert ipm_geom.poly_dist(layers["upper"], layers["lower"]) == pytest.approx(0.4, abs=0.02)
    assert layers["area_upper"] == pytest.approx(layers["area_lower"], rel=0.01)
    assert layers["split_axis"] == "tangential_y"
    # 用户 11-22 二次修订：截面必须是矩形（4 点，非异形切分）
    assert layers["shape"] == "rectangle"
    assert len(layers["upper"]) == 4 and len(layers["lower"]) == 4
    for poly in (layers["upper"], layers["lower"]):
        xs = {p[0] for p in poly}
        ys = {p[1] for p in poly}
        assert len(xs) == 2 and len(ys) == 2   # 轴对齐矩形 ⇒ 只有 2 个 x、2 个 y
    # 两条边在径向 x 上覆盖同一范围 ⇒ 到气隙等距，不是一远一近
    ux = [p[0] for p in layers["upper"]]
    lx = [p[0] for p in layers["lower"]]
    assert min(ux) == pytest.approx(min(lx), abs=1e-6)
    assert max(ux) == pytest.approx(max(lx), abs=1e-6)
    # 关于 y=0 镜像
    assert min(p[1] for p in layers["upper"]) == pytest.approx(-max(p[1] for p in layers["lower"]), abs=1e-6)


# ------------------------------------------------------------------ I2 绕组
def test_i2_all_checks_pass(i2):
    assert i2["status"] == "PASS", [c for c in i2["checks"] if c["status"] != "PASS"]


def test_i2_96_sides(i2):
    rows = i2["rows"]
    assert len(rows) == 96
    assert len({(r["slot"], r["layer"]) for r in rows}) == 96
    for ph in ("A", "B", "C"):
        sides = [r for r in rows if r["phase"] == ph]
        assert len(sides) == 32
        assert len({r["coil"] for r in sides}) == 16
        assert sum(1 for r in sides if r["layer"] == "U") == 16
        assert sum(1 for r in sides if r["layer"] == "L") == 16


def test_i2_winding_factors(i2):
    kw = i2["summary"]["kw"]
    assert kw[1] == pytest.approx(0.93296, abs=5e-4)
    assert kw[5] == pytest.approx(0.066987, abs=2e-3)
    assert kw[7] == pytest.approx(0.066987, abs=2e-3)
    assert kw[1] > 10 * kw[5]


def test_i2_phase_sequence(i2):
    s = i2["summary"]
    assert s["d_ab"] == pytest.approx(120.0, abs=0.5)
    assert s["d_bc"] == pytest.approx(120.0, abs=0.5)


def test_i2_upper_lower_are_same_coil(cfg, i2):
    """槽 s 的下层边必须属于线圈 s−y（回边），且极性与该线圈相反。"""
    rows = {(r["slot"], r["layer"]): r for r in i2["rows"]}
    for s in range(1, cfg.slots + 1):
        back = ((s - 1 - cfg.coil_pitch) % cfg.slots) + 1
        assert rows[(s, "L")]["coil"] == back
        up = rows[(back, "U")]
        assert rows[(s, "L")]["sign"] == -up["sign"]
        assert rows[(s, "L")]["phase"] == up["phase"]


# ------------------------------------------------------------------ I4 转子
def test_i4_all_checks_pass(i4):
    assert i4["status"] == "PASS", [c for c in i4["checks"] if c["status"] != "PASS"]


def test_i4_magnet_count(i4):
    assert i4["magnets"] == 16
    assert len(i4["polygons"]) == 16
    assert len(i4["labels"]) == 16


def test_i4_each_magnet_area(i4, cfg):
    """每块面积必须等于 L×t；自交或镜像写错会立刻偏离。"""
    for lab, pts in zip(i4["labels"], i4["polygons"]):
        assert lab.startswith("single_")
        assert ipm_geom.polygon_area(pts) == pytest.approx(cfg.v_single[2] * cfg.pm_thickness, abs=1e-6)


def test_i4_inside_rotor(i4, cfg):
    r_out = cfg.rotor_od / 2
    r_in = cfg.rotor_id / 2
    for pts in i4["polygons"]:
        assert max(math.hypot(*p) for p in pts) <= r_out - 1.0
        assert min(math.hypot(*p) for p in pts) >= r_in + 3.0


# ------------------------------------------------------------ M1' 生成物护栏
def test_build_script_compiles(cfg):
    import ipm_build
    src = ipm_build.build_script(cfg)
    compile(src, "ipm_m1_build.py", "exec")
    # COILS 段：48 个上层 + 48 个下层对象；SIDES 段：同样 96 条 AssignCoil
    coils = src.split("COILS = [")[1].split("\n]")[0]
    assert coils.count('"Coil_T') == cfg.slots
    assert coils.count('"Coil_B') == cfg.slots
    sides = src.split("SIDES = [")[1].split("\n]")[0]
    assert sides.count('"Coil_T') == cfg.slots
    assert sides.count('"Coil_B') == cfg.slots
    assert src.count('("PM_') == 16
    assert "AssignCoil" in src
    assert "ModelDepth" in src
    assert "ValidateDesign" in src


def test_magnet_directions_unit(cfg):
    import ipm_build
    dirs = ipm_build.magnet_directions(cfg)
    assert len(dirs) == 16
    for _pole, gx, gy in dirs:
        assert math.hypot(gx, gy) == pytest.approx(1.0, abs=1e-9)


# ------------------------------------------------------------ I3 匝数/槽满率
def test_i3_cps_sourced_at_10(cfg):
    """I3 定源：cps=10（160 匝/相），不再是 TEMP 值 5。"""
    assert cfg.conductors_per_slot == 10
    assert cfg.conductors_per_slot * 16 == 160


def test_i3_slot_fill_passes_at_1p35(cfg):
    """2026-11-24: Bs0=1.0+yoke15 后 cps=10/Ø1.35 fill=0.7606≤0.78；Ø1.5 越界必须 FAIL。"""
    good = ipm_geom.slot_fill_factor(cfg)
    assert good["cps"] == 10 and good["wires_per_slot"] == 20
    assert good["status"] == "PASS" and good["fill"] <= 0.78
    bad = ipm_geom.slot_fill_factor(cfg, wire_mm=1.5)
    assert bad["status"] == "FAIL" and bad["fill"] > 0.78


def test_i3_build_script_has_cps_10(cfg):
    """M1' 生成物里 Conductor number 必须是定源后的 10。"""
    import ipm_build
    src = ipm_build.build_script(cfg)
    assert "CPS = 10" in src
    assert 'str(CPS), "PolarityType:="' in src


# ------------------------------------------------------------ D5 斜槽多切片
def test_rotor_init_deg_identity(cfg):
    """0° 转角必须与默认逐位相同（防止斜槽改动污染 baseline）。"""
    import ipm_build
    assert ipm_geom.derive_rotor(cfg, 0.0)["polygons"] == ipm_geom.derive_rotor(cfg)["polygons"]
    assert ipm_build.magnet_directions(cfg, 0.0) == ipm_build.magnet_directions(cfg)


def test_rotor_init_deg_rotates_rigidly(cfg):
    """转子转角只改位形：块数/总面积/6 项几何自检不变，磁化方向同步转。"""
    import ipm_build
    base = ipm_geom.derive_rotor(cfg, 0.0)
    rot = ipm_geom.derive_rotor(cfg, 2.8125)
    assert rot["magnets"] == base["magnets"] == 16
    assert rot["magnet_area_total"] == pytest.approx(base["magnet_area_total"], abs=1e-6)
    assert all(c["status"] == "PASS" for c in rot["checks"])
    d0, d1 = ipm_build.magnet_directions(cfg, 0.0), ipm_build.magnet_directions(cfg, 2.8125)
    for (_p0, gx0, gy0), (_p1, gx1, gy1) in zip(d0, d1):
        assert math.hypot(gx1, gy1) == pytest.approx(1.0, abs=1e-9)
        assert math.hypot(gx0 - gx1, gy0 - gy1) > 1e-3   # 确实转了
