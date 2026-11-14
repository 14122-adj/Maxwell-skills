"""M8（2026-11-14）：梨形槽（表 2，11 点 + 半圆底）几何口径护栏。

为什么需要这一组
----------------
旧模板的梨形槽是"浅梨形 8.05 mm"：只有 7 个控制点，斜肩和半圆底被压成一根弦，
槽面积与表 2 完全无关；`_slot_pts`（线圈内缩用）又单独抄了一份坐标，且**没有
圆弧采样** —— 底部半圆被两根弦代替，弦高 `Rs(1−cos45°) = 1.39 mm`，线圈面积
只剩 62.07 mm²（比目标 72 少 13.8%），下缘直接切进槽底圆弧。

本文件把三件事钉死：
1. 表 2 的 11 个点、10 段（Arc 起点索引 4）必须按解析式算出来，不许手抄；
2. 面积口径：解析 93.03 / 环带实切 92.87 / StatorOuter 9,764 —— 三者互相自洽；
3. 线圈：底弧密采样后 0.88 内缩必须落在 72 ±5% 且完全在槽内、不进气隙。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import slot_profile as sp
from motor_config import MotorConfig, SlotType

# 表 2 尺寸（docs/PEAR_SLOT_SPEC.md §1）
TABLE2 = dict(
    stator_od=150.0, stator_id=93.0, slots=12, poles=8,
    slot_Hs0=1.5, slot_Hs1=1.8, slot_Hs2=12.5,
    slot_Bs0=0.8, slot_Bs1=6.0, slot_Bs2=9.5, slot_Rs=4.75,
)


@pytest.fixture()
def cfg() -> SimpleNamespace:
    return SimpleNamespace(**TABLE2)


def inside(poly, p) -> bool:
    """射线法点内判定（槽形在槽肩处是**凹**的，不能用半平面同号判据）。"""
    x, y = p
    n = len(poly)
    hit = False
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        if (ay > y) != (by > y):
            xin = ax + (y - ay) * (bx - ax) / (by - ay)
            if xin > x:
                hit = not hit
    return hit


class TestPearRadii:
    """径向基准线必须从 r_bore 起算（旧版从 x0 = r_bore−0.2 起算，整槽短 0.2）。"""

    def test_five_reference_lines(self, cfg) -> None:
        r = sp.pear_radii(cfg)
        assert r["x0"] == pytest.approx(46.3)
        assert r["x1"] == pytest.approx(48.0)
        assert r["x2"] == pytest.approx(49.8)
        assert r["x3"] == pytest.approx(54.25)
        assert r["x4"] == pytest.approx(59.0)

    def test_yoke_follows_hs2_semantics(self, cfg) -> None:
        """Hs2 口径 = 内径→槽底最底端：轭部 = 75 − 59 = 16.0 mm。"""
        r = sp.pear_radii(cfg)
        assert cfg.stator_od / 2 - r["x4"] == pytest.approx(16.0)

    def test_center_is_above_bottom_by_rs(self, cfg) -> None:
        r = sp.pear_radii(cfg)
        assert r["x4"] - r["x3"] == pytest.approx(r["rs"])


class TestPoints:
    def test_eleven_points(self, cfg) -> None:
        pts = sp.pear_key_points(cfg)
        assert len(pts) == 11

    def test_coordinates_match_table(self, cfg) -> None:
        pts = sp.pear_key_points(cfg)
        expect = [
            (46.3, -0.4), (48.0, -0.4), (48.0, -3.0), (49.8, -4.75),
            (54.25, -4.75), (59.0, 0.0), (54.25, 4.75), (49.8, 4.75),
            (48.0, 3.0), (48.0, 0.4), (46.3, 0.4),
        ]
        for got, want in zip(pts, expect):
            assert got == pytest.approx(want, abs=1e-9)

    def test_symmetric_about_axis(self, cfg) -> None:
        """槽形必须关于 y=0 对称（不对称 = 齿槽转矩里混入伪直流分量）。"""
        pts = sp.pear_key_points(cfg)
        for i in range(5):
            assert pts[i][1] == pytest.approx(-pts[10 - i][1], abs=1e-12)
            assert pts[i][0] == pytest.approx(pts[10 - i][0], abs=1e-12)


class TestSegments:
    def test_ten_segments_with_arc_at_four(self, cfg) -> None:
        segs = sp.pear_segments()
        assert len(segs) == 10
        arcs = [(i, s) for i, s in enumerate(segs) if s[0] == "Arc"]
        assert arcs == [(4, ("Arc", 4, 3))], "底部半圆必须是 StartIndex=4 的 3 点 Arc"

    def test_segments_tile_all_twelve_points(self, cfg) -> None:
        """12 个 PLPoint（11 + 闭合）必须被 10 段无缝覆盖，且不重叠。"""
        n_pts = len(sp.pear_key_points(cfg)) + 1
        covered = []
        for _kind, start, cnt in sp.pear_segments():
            covered.extend(range(start, start + cnt - 1))
        assert covered == list(range(n_pts - 1)), "段序列必须从 0 连续铺到 n-2"
        assert covered[-1] + 1 == n_pts - 1


class TestAreas:
    def test_analytic_area(self, cfg) -> None:
        assert sp.pear_area_analytic(cfg) == pytest.approx(93.026, abs=0.05)

    def test_analytic_matches_component_sum(self, cfg) -> None:
        """颈 1.36 + 斜肩 13.95 + 直身 42.275 + 半圆 35.437 = 93.02。"""
        r = sp.pear_radii(cfg)
        parts = [
            cfg.slot_Bs0 * (r["x1"] - r["x0"]),
            (cfg.slot_Bs1 + cfg.slot_Bs2) / 2 * cfg.slot_Hs1,
            cfg.slot_Bs2 * (r["x3"] - r["x2"]),
            3.141592653589793 * r["rs"] ** 2 / 2,
        ]
        assert sum(parts) == pytest.approx(sp.pear_area_analytic(cfg), abs=1e-6)
        assert parts[0] == pytest.approx(1.36, abs=1e-3)
        assert parts[2] == pytest.approx(42.275, abs=1e-3)
        # 规格表写 35.437 是按 π=3.1416 手算；准确值 π·4.75²/2 = 35.4411
        assert parts[3] == pytest.approx(35.4411, abs=1e-3)

    def test_effective_area_excludes_bore_overlap(self, cfg) -> None:
        """环带上真正被切掉的是 93.03 − 0.2×0.8 = 92.87（槽口那 0.2 mm 在内孔里）。"""
        assert sp.slot_effective_area(cfg) == pytest.approx(92.866, abs=1e-3)

    def test_stator_face_area_matches_expected(self, cfg) -> None:
        """12 槽切完，StatorOuter 面应 ≈ 9,764 mm² —— 现场判据用的就是这个数。"""
        face = sp.stator_ring_area(cfg) - cfg.slots * sp.slot_effective_area(cfg)
        assert face == pytest.approx(9764.2, abs=1.5)

    def test_reverse_from_face_recovers_analytic(self, cfg) -> None:
        """由 GetFaceArea 反算槽面积应回到 93.03（±0.05），否则面积判据就不可信。"""
        face = sp.stator_ring_area(cfg) - cfg.slots * sp.slot_effective_area(cfg)
        assert sp.slot_area_from_stator_face(cfg, face) == pytest.approx(
            sp.pear_area_analytic(cfg), abs=0.05)


class TestOutlineAndCoil:
    def test_outline_is_dense_on_arc(self, cfg) -> None:
        """11 控制点 → 25 个折点：半圆从 2 根弦变成 16 根弦。"""
        assert len(sp.pear_outline(cfg)) == 4 + (sp.ARC_SEGMENTS + 1) + 4
        assert len(sp.pear_outline(cfg)) == 25

    def test_arc_faceting_error_is_small(self, cfg) -> None:
        """折线面积比解析值少 0.6% 以内（16 段弦高 0.023 mm）。"""
        a_poly = sp.polygon_area(sp.pear_outline(cfg))
        a_ana = sp.pear_area_analytic(cfg)
        assert a_poly < a_ana
        assert (a_ana - a_poly) / a_ana < 0.01

    def test_coil_area_within_five_percent(self, cfg) -> None:
        """线圈必须落在 72 ±5%（旧版 11 点无采样只有 62.07 = −13.8%）。"""
        coil = sp.shrink_toward_centroid(sp.pear_outline(cfg), sp.COIL_SHRINK)
        area = sp.polygon_area(coil)
        assert area == pytest.approx(72.0, rel=0.05), "线圈面积 %.2f 超出 72±5%%" % area

    def test_coil_inside_slot(self, cfg) -> None:
        slot = sp.pear_outline(cfg)
        coil = sp.shrink_toward_centroid(slot, sp.COIL_SHRINK)
        for p in coil:
            assert inside(slot, p), "线圈顶点 %s 跑出槽外（会报 StatorOuter/Coil intersect）" % (p,)

    def test_coil_does_not_enter_airgap(self, cfg) -> None:
        """内缩后线圈最内侧必须越过内孔（> r_bore），否则切进气隙区。"""
        coil = sp.shrink_toward_centroid(sp.pear_outline(cfg), sp.COIL_SHRINK)
        assert min(p[0] for p in coil) > cfg.stator_id / 2

    def test_slot_fill_factor(self, cfg) -> None:
        """40 根 Ø1.45：66.05 / 93.03 = 0.710 ≤ 0.78，线径不必改。"""
        fill = 40 * 1.652 / sp.pear_area_analytic(cfg)
        assert fill == pytest.approx(0.710, abs=0.005)
        assert fill <= 0.78


class TestMotorConfigValidation:
    """生成前的闸口：错的梨形尺寸必须被 validate() 拦住，不能建出畸形槽。"""

    def _cfg(self, **over):
        base = dict(
            motor_type=None, slot_type=SlotType.PEAR, pm_topology=None,
            stator_od=150.0, stator_id=93.0, rotor_od=91.65, airgap=0.675,
            stack_length=160.0, slots=12, pole_pairs=4,
        )
        base.update(over)
        cfg = MotorConfig(**base)
        return cfg

    def test_table2_passes(self) -> None:
        cfg = self._cfg(**{k: v for k, v in TABLE2.items()
                           if k in ("slot_Hs0", "slot_Hs1", "slot_Hs2",
                                    "slot_Bs0", "slot_Bs1", "slot_Bs2", "slot_Rs")})
        errs = [i for i in cfg.validate() if i.startswith("ERROR")]
        assert errs == []

    def test_rs_must_equal_half_bs2(self) -> None:
        """Rs ≠ Bs2/2 时半圆起点不在圆上，Acis 会补隐式连线静默变形。"""
        cfg = self._cfg(slot_Bs0=0.8, slot_Hs0=1.5, slot_Hs1=1.8, slot_Hs2=12.5,
                        slot_Bs1=6.0, slot_Bs2=9.5, slot_Rs=4.0)
        errs = [i for i in cfg.validate() if i.startswith("ERROR")]
        assert any("半圆" in e for e in errs), errs

    def test_negative_straight_section_rejected(self) -> None:
        cfg = self._cfg(slot_Bs0=0.8, slot_Hs0=1.5, slot_Hs1=1.8, slot_Hs2=5.0,
                        slot_Bs1=6.0, slot_Bs2=9.5, slot_Rs=4.75)
        errs = [i for i in cfg.validate() if i.startswith("ERROR")]
        assert any("直身段为负" in e for e in errs), errs
