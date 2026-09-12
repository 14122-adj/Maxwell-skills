"""
test_pmsm_winding_builder.py — unit tests for the WindingBuilder API.

Covers:
  - Constructor argument validation
  - Winding type detection (concentrated / distributed / fractional)
  - Lookup-first path (source == "canonical")
  - Fallback algorithm (source == "computed")
  - Output formats: render_slot_map, render_phase_belt, render_summary
  - Maxwell script generation (Python syntax validity)
  - Polarity convention flag (standard vs legacy)
"""
from __future__ import annotations

import ast
import re

import pytest

from pmsm_winding_builder import (
    CANONICAL_LAYOUTS,
    CoilGroup,
    LayerType,
    WindingBuilder,
    WindingConfig,
    WindingType,
)


# ────────────────────────────────────────────────────────────────────
#  Constructor
# ────────────────────────────────────────────────────────────────────

class TestConstructor:
    def test_minimal_args(self):
        b = WindingBuilder(slots=12, poles=8)
        assert b.slots == 12
        assert b.poles == 8
        assert b.phases == 3
        assert b.layer == LayerType.DOUBLE

    def test_derived_quantities_8p12s(self):
        b = WindingBuilder(slots=12, poles=8)
        assert b.q == 0.5
        assert b.pole_pairs == 4
        assert b.slot_angle == pytest.approx(30.0)
        assert b.pole_pitch == pytest.approx(45.0)
        assert b.electrical_slot_angle == pytest.approx(120.0)

    def test_winding_type_auto_concentrated(self):
        b = WindingBuilder(slots=12, poles=8)
        assert b.winding_type == WindingType.CONCENTRATED

    def test_winding_type_auto_distributed(self):
        b = WindingBuilder(slots=24, poles=8)
        assert b.winding_type == WindingType.DISTRIBUTED

    def test_winding_type_auto_fractional(self):
        b = WindingBuilder(slots=36, poles=8)
        assert b.winding_type == WindingType.FRACTIONAL

    def test_explicit_winding_type(self):
        b = WindingBuilder(slots=12, poles=8, winding_type=WindingType.DISTRIBUTED)
        assert b.winding_type == WindingType.DISTRIBUTED

    @pytest.mark.parametrize("bad_convention", ["foo", "BAR", ""])
    def test_bad_polarity_convention_raises(self, bad_convention):
        with pytest.raises(AssertionError):
            WindingBuilder(slots=12, poles=8, polarity_convention=bad_convention)

    def test_asserts_on_invalid_dims(self):
        with pytest.raises(AssertionError):
            WindingBuilder(slots=0, poles=8)
        with pytest.raises(AssertionError):
            WindingBuilder(slots=12, poles=0)


# ────────────────────────────────────────────────────────────────────
#  Winding factor
# ────────────────────────────────────────────────────────────────────

class TestWindingFactor:
    @pytest.mark.parametrize("slots,poles,expected", [
        (12, 8, 0.866),    # 8p12s
        (12, 10, 0.933),   # 10p12s
        (24, 4, 0.966),    # 4p24s
        (36, 8, 0.96),     # 8p36s
    ])
    def test_known_combinations(self, slots, poles, expected):
        b = WindingBuilder(slots=slots, poles=poles)
        assert b.compute_winding_factor() == pytest.approx(expected, abs=1e-3)

    def test_unknown_fallback_returns_positive(self):
        b = WindingBuilder(slots=15, poles=4)  # not in CANONICAL_LAYOUTS
        k = b.compute_winding_factor()
        assert 0.0 < k <= 1.0


# ────────────────────────────────────────────────────────────────────
#  compute_winding() — the main entry point
# ────────────────────────────────────────────────────────────────────

class TestComputeWinding:
    def test_canonical_source(self):
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        assert c.source == "canonical"
        assert c.slots == 12
        assert c.poles == 8
        assert len(c.slot_map) == 12

    def test_fallback_source(self):
        b = WindingBuilder(slots=15, poles=4)   # not in CANONICAL_LAYOUTS
        c = b.compute_winding()
        assert c.source == "computed"

    def test_slot_map_lengths(self, slot_pole_pair):
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        assert len(c.slot_map) == slots

    def test_slot_map_phases_valid(self, slot_pole_pair):
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        for i, (ph, pol) in enumerate(c.slot_map):
            assert ph in ("A", "B", "C"), f"slot {i+1} invalid phase {ph!r}"
            assert pol in ("+", "-"), f"slot {i+1} invalid polarity {pol!r}"

    def test_canonical_table_consistency(self):
        """Every entry in CANONICAL_LAYOUTS must equal the builder's slot_map."""
        for slots, poles in CANONICAL_LAYOUTS.keys():
            b = WindingBuilder(slots=slots, poles=poles)
            c = b.compute_winding()
            assert c.slot_map == CANONICAL_LAYOUTS[(slots, poles)], (
                f"({slots}, {poles}) builder slot_map != CANONICAL_LAYOUTS"
            )

    def test_three_phase_balanced(self, slot_pole_pair):
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        n_per_phase = {p: sum(1 for ph, _ in c.slot_map if ph == p) for p in "ABC"}
        counts = set(n_per_phase.values())
        assert len(counts) == 1, f"unbalanced: {n_per_phase}"

    def test_coil_groups_match_slot_map(self, slot_pole_pair):
        """Every (phase, polarity) in slot_map must appear exactly once in coil_groups."""
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        covered = []
        for g in c.coil_groups:
            covered.extend([(g.phase, g.polarity)] * len(g.coil_indices))
        assert sorted(covered) == sorted(c.slot_map), \
            f"coil_groups cover {covered} != slot_map {c.slot_map}"


# ────────────────────────────────────────────────────────────────────
#  Renderers
# ────────────────────────────────────────────────────────────────────

class TestRenderSlotMap:
    def test_format_8p12s(self):
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        out = b.render_slot_map(c)
        assert "Slot:" in out
        assert "Phase:" in out
        assert "Coil:" in out
        # 8p12s Pyrhonen: A+ A- B+ B- C+ C- A+ A- B+ B- C+ C-
        # The rendered format puts a space between phase letter and polarity:
        #   "A  + A  - B  + B  - C  + C  - A  + A  - B  + B  - C  + C  -"
        assert "A  + A  - B  + B  - C  + C  -" in out

    def test_format_36slot(self):
        b = WindingBuilder(slots=36, poles=8)
        c = b.compute_winding()
        out = b.render_slot_map(c)
        # The 36-slot map uses multi-row format (3 rows of 12 + the Coil row)
        # Coil_1 through Coil_36 must all appear
        for i in range(1, 37):
            assert f"C{i}" in out, f"missing C{i} in render output"

    def test_render_phase_belt_includes_metadata(self):
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        out = b.render_phase_belt(c)
        assert "Slot angle" in out
        assert "Pole pitch" in out
        assert "Winding factor" in out

    def test_render_summary_warns_for_fallback(self):
        b = WindingBuilder(slots=15, poles=4)
        c = b.compute_winding()
        out = b.render_summary(c)
        assert "[WARN]" in out   # source=computed


# ────────────────────────────────────────────────────────────────────
#  Maxwell script generation
# ────────────────────────────────────────────────────────────────────

class TestMaxwellScript:
    def test_generates_valid_python(self, slot_pole_pair):
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        script = b.generate_maxwell_script(c, conductor_number=40)
        ast.parse(script)   # raises on SyntaxError

    def test_uses_standard_polarity(self):
        b = WindingBuilder(slots=12, poles=8, polarity_convention="standard")
        c = b.compute_winding()
        script = b.generate_maxwell_script(c, conductor_number=40)
        # standard: A+ → Positive, A- → Negative
        assert '"PolarityType:=", "Positive"' in script
        assert '"PolarityType:=", "Negative"' in script

    def test_legacy_convention_inverts(self):
        b = WindingBuilder(slots=12, poles=8, polarity_convention="legacy")
        c = b.compute_winding()
        script = b.generate_maxwell_script(c, conductor_number=40)
        # legacy: A+ → Negative, A- → Positive
        # A+ group name is "A+" — it should have Negative polarity
        a_pos_section = re.search(r'"NAME:A\+".*?"PolarityType:=", "(Positive|Negative)"', script, re.DOTALL)
        assert a_pos_section is not None
        assert a_pos_section.group(1) == "Negative"

    def test_script_has_winding_groups(self):
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        script = b.generate_maxwell_script(c, conductor_number=40)
        assert "AssignWindingGroup" in script
        assert "WindingA" in script
        assert "WindingB" in script
        assert "WindingC" in script
        assert "AssignCoilGroup" in script
        assert "AddWindingCoils" in script

    def test_coil_names_are_coil_n(self, slot_pole_pair):
        """Coil names must be Coil_1, Coil_2, ... — the canonical Maxwell naming."""
        slots, poles = slot_pole_pair
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        script = b.generate_maxwell_script(c, conductor_number=40)
        # Should reference Coil_1 at least
        assert '"Coil_1"' in script
        # Should reference Coil_N
        assert f'"Coil_{slots}"' in script


# ────────────────────────────────────────────────────────────────────
#  Concentrated winding bug regression tests
# ────────────────────────────────────────────────────────────────────

class TestConcentratedWindingRegression:
    """These tests guard against the v1 bug where 8p12s all came out + polarity."""

    def test_8p12s_alternating_polarity(self):
        """8p12s must have AABBCC alternating +/- pattern, NOT all +."""
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        # 4 unique polarities expected (within A, B, C)
        polarities = [pol for _, pol in c.slot_map]
        assert "+" in polarities and "-" in polarities, "all + would be the v1 bug"
        # Pyrhonen pattern: A+ A- B+ B- C+ C- A+ A- B+ B- C+ C-
        assert polarities == ["+", "-", "+", "-", "+", "-",
                              "+", "-", "+", "-", "+", "-"], (
            f"expected Pyrhonen AABBCC pattern, got {''.join(polarities)}"
        )

    def test_8p12s_balanced_per_phase(self):
        """Each phase must have equal + and - coils (q=0.5 concentrated)."""
        b = WindingBuilder(slots=12, poles=8)
        c = b.compute_winding()
        for phase in "ABC":
            n_pos = sum(1 for p, pol in c.slot_map if p == phase and pol == "+")
            n_neg = sum(1 for p, pol in c.slot_map if p == phase and pol == "-")
            assert n_pos == n_neg, f"phase {phase} + {n_pos} != - {n_neg}"
