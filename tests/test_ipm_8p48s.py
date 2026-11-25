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


# ------------------------------------------------------------ M4 起动工况护栏
def test_build_script_default_is_steady_state(cfg):
    """默认调用（M1'/M2'/M3'）必须是恒转速稳态口径，绝不能漏进机械瞬态。

    判据不是"看起来对"：M1'–M3' 的 25 N·m / 峰峰值 ≤10% 全部建立在
    `Consider Mechanical Transient=False` + 转速钉死 1500rpm 之上；一旦默认
    变成 True，那三份历史数据的口径就失效了。
    """
    import ipm_build
    src = ipm_build.build_script(cfg)
    assert '"Consider Mechanical Transient:=", False' in src
    assert '"Angular Velocity:=", "1500rpm"' in src
    assert '"Moment of Inertia' not in src
    assert '"Load Torque' not in src
    # 时间口径一并钉住
    assert '"StopTime:=", "0.02s"' in src
    assert '"TimeStep:=", "0.00005s"' in src


def test_build_script_motion_mechanical_transient(cfg):
    """传 motion 后必须写出官方示例那 5 个键（MaxwellScriptingGuide P760）。"""
    import ipm_build
    motion = dict(init_speed="0deg_per_sec", inertia="0.0092",
                  damping="0", load_torque="0NewtonMeter")
    src = ipm_build.build_script(
        cfg, motion=motion, stop_time="0.2s", time_step="0.0005s", save_fields="None")
    assert '"Consider Mechanical Transient:=", True' in src
    assert '"Angular Velocity:=", "0deg_per_sec"' in src
    assert '"Moment of Inertia:=", "0.0092"' in src
    assert '"Damping:=", "0"' in src
    assert '"Load Torque:=", "0NewtonMeter"' in src
    # 机械瞬态下不能再出现"恒转速"写法
    assert '"1500rpm"' not in src
    # 时间口径
    assert '"StopTime:=", "0.2s"' in src
    assert '"TimeStep:=", "0.0005s"' in src
    assert '"SaveFieldsType:=", "None"' in src
    compile(src, "ipm_m4_build.py", "exec")


def test_m4_timing_keeps_401_points(cfg):
    """M4 的 0.2s / 0.5ms 必须仍是 400 步 401 点 —— 与 M1'–M3' 同规模。"""
    import ipm_m4_start
    steps = int(round(ipm_m4_start._sec("0.2s") / ipm_m4_start._sec("0.0005s")))
    assert steps == 400 and steps + 1 == 401
    old = int(round(ipm_m4_start._sec("0.02s") / ipm_m4_start._sec("0.00005s")))
    assert old == steps


def test_m4_inertia_is_physical(cfg):
    """J 必须落在转子本体解析区间内 —— 防止手滑写成 0.9 或 9e-5。

    转子 Ø92.325 x 160mm 全钢实心 J = ½·m·r²，m = π·r²·L·ρ ≈ 8.4 kg ⇒ 8.9e-3。
    实心是上界，含磁钢后略高一点点（磁钢密度低于钢但靠外圈）。
    """
    import ipm_m4_start
    r = cfg.stator_id / 2.0 - cfg.airgap / 2.0        # 46.1625 mm
    r_m = r * 1e-3
    v = math.pi * r_m ** 2 * cfg.stack_length * 1e-3
    j_upper = 0.5 * v * 7850.0 * r_m ** 2
    assert 0.6 * j_upper < ipm_m4_start.J_ROTOR < 1.15 * j_upper


def test_m4_chirp_phase_is_integral_of_frequency(cfg):
    """变频相位必须是频率的积分 θ(t)=2π[f0·t + k·min(t,T)²/2]。

    两个常见写错：①直接写 2π·f1·t（等于瞬间跳到终频，不是爬坡）；
    ②漏掉 1/2（变成 2 倍频）。判据是核对 k/2 = (f1−f0)/(2T) 这个系数本身。
    """
    import ipm_m4_start
    cur = ipm_m4_start.compute_currents_chirp(14.0, 90.0, f0_hz=2.0, f1_hz=100.0, t_ramp_s=0.12)
    a = cur["A"]
    k_half = (100.0 - 2.0) / (2.0 * 0.12)          # 408.3333...
    assert "min(Time,0.120000)" in a
    assert "%.6f" % k_half in a
    assert "2*pi" in a
    # 三相移 120°：A=+90°, B=−30°, C=+210°
    assert "1.570796327" in cur["A"]
    assert "-0.523598776" in cur["B"]
    assert "3.665191429" in cur["C"]


def test_m4_closed_loop_uses_pole_pairs(cfg):
    """闭环表达式必须是极对数（8 极 → 4），写成极数 8 会让电角翻倍。"""
    import ipm_m4_start
    cur = ipm_m4_start.compute_currents_closed_loop(14.0, 90.0, 4)
    assert "sin(4*Moving1.Position*pi/180" in cur["A"]
    assert "sin(8*Moving1.Position" not in cur["A"]


def test_m4_soft_start_makes_torque_rise_from_zero(cfg):
    """软启动必须让 t=0 的电流因子为 0，否则转矩第一点就是额定值。

    用户 2026-11-25 追问"能不能让转矩从 0 升到 25"。理想电流源在 t=0 就灌满
    Imax·sin(φ)，转矩首点 25.19 N·m。加 `min(Time/T,1)` 因子等价于真实驱动器的
    电流环上升时间：t=0 → i=0 → T_em≈0。这条测试锁死该因子必须存在且位置正确
    （必须乘在 sin 之前，不能乘在相位里）。
    """
    import ipm_m4_start
    soft = ipm_m4_start.compute_currents_chirp(
        13.856, 90.0, f0_hz=2.0, f1_hz=100.0, t_ramp_s=0.12, t_soft=0.02)
    a = soft["A"]
    assert "min(Time/0.020000,1)*sin(" in a          # 因子在 sin 之前
    assert "-13.856000*min(Time/0.020000,1)*sin(" in a
    # 不启用软启动时不得出现该因子
    hard = ipm_m4_start.compute_currents_chirp(
        13.856, 90.0, f0_hz=2.0, f1_hz=100.0, t_ramp_s=0.12)
    assert "*min(Time/" not in hard["A"]
    # 三相都带该因子
    for ph in ("A", "B", "C"):
        assert "min(Time/0.020000,1)" in soft[ph]


def test_m4_soft_factor_zero_disables(cfg):
    """t_soft<=0 必须返回空串，保证默认行为与历史 M4 数据逐字一致。"""
    import ipm_m4_start
    assert ipm_m4_start._soft_factor(0.0) == ""
    assert ipm_m4_start._soft_factor(-1.0) == ""
    assert ipm_m4_start._soft_factor(0.02) == "min(Time/0.020000,1)*"


def test_airgap_length_op_is_5th_group(cfg):
    """I28：AirgapRing 必须有独立第 5 组 LengthOp，且其余 4 组逐字不动。

    指导书唯一命中的真缺陷是气隙仅 ≈1.48 层。0.15 mm ⇒ 2.25 层。
    本护栏钉住：5 组齐全、组名/MaxLength 与契约一致、其余 4 组数值不变、
    frozen baseline 的稳态口径（False/1500rpm）不被本改动破坏。
    """
    import ipm_build
    import ipm_mesh_check as mc

    src = ipm_build.build_script(cfg)
    assert src.count("AssignLengthOp(") == 5
    assert '"NAME:Mesh_Airgap", "Objects:=", ["AirgapRing"]' in src
    assert '"MaxLength:=", "0.15mm"' in src
    for name, ml in (("Mesh_Band", "0.25mm"), ("Mesh_Stator", "0.9mm"),
                     ("Mesh_Rotor", "1.2mm"), ("Mesh_PM", "0.5mm")):
        assert '"NAME:' + name + '"' in src
        assert '"MaxLength:=", "' + ml + '"' in src
    # §9.2 判据：5 组 + 层数下限 2.0 + 气隙环厚 0.3375 mm
    assert list(mc.EXPECTED_LENGTH_OPS) == ["Mesh_Band", "Mesh_Stator", "Mesh_Rotor",
                                            "Mesh_PM", "Mesh_Airgap"]
    assert mc.EXPECTED_LENGTH_OPS["Mesh_Airgap"] == ("AirgapRing", 0.15)
    assert mc.AIRGAP_RING_THICKNESS_MM == 0.3375
    assert mc.AIRGAP_MIN_LAYERS == 2.0
    # 稳态口径不被本改动破坏
    assert '"Consider Mechanical Transient:=", False' in src
    assert '"Angular Velocity:=", "1500rpm"' in src


def test_airgap_length_op_is_5th_group(cfg):
    """I28：AirgapRing 必须有独立第 5 组 LengthOp，且其余 4 组逐字不动。

    指导书唯一命中的真缺陷是气隙仅 ≈1.48 层。0.15 mm ⇒ 2.25 层。
    本护栏钉住：5 组齐全、组名/MaxLength 与契约一致、其余 4 组数值不变、
    frozen baseline 的稳态口径（False/1500rpm）不被本改动破坏。
    """
    import ipm_build
    import ipm_mesh_check as mc

    src = ipm_build.build_script(cfg)
    assert src.count("AssignLengthOp(") == 5
    assert '"NAME:Mesh_Airgap", "Objects:=", ["AirgapRing"]' in src
    assert '"MaxLength:=", "0.15mm"' in src
    for name, ml in (("Mesh_Band", "0.25mm"), ("Mesh_Stator", "0.9mm"),
                     ("Mesh_Rotor", "1.2mm"), ("Mesh_PM", "0.5mm")):
        assert '"NAME:' + name + '"' in src
        assert '"MaxLength:=", "' + ml + '"' in src
    # §9.2 判据：5 组 + 层数下限 2.0 + 气隙环厚 0.3375 mm
    assert list(mc.EXPECTED_LENGTH_OPS) == ["Mesh_Band", "Mesh_Stator", "Mesh_Rotor",
                                            "Mesh_PM", "Mesh_Airgap"]
    assert mc.EXPECTED_LENGTH_OPS["Mesh_Airgap"] == ("AirgapRing", 0.15)
    assert mc.AIRGAP_RING_THICKNESS_MM == 0.3375
    assert mc.AIRGAP_MIN_LAYERS == 2.0
    # 稳态口径不被本改动破坏
    assert '"Consider Mechanical Transient:=", False' in src
    assert '"Angular Velocity:=", "1500rpm"' in src
