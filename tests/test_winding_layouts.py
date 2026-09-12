"""
test_winding_layouts.py — verify all canonical pole-slot combinations.

Migrated from scripts/test_winding_layouts.py for the pytest harness.
This file is the canonical test entry point; the legacy script is kept
as a thin wrapper for backwards compatibility.

Run:
    pytest tests/test_winding_layouts.py -v
    # or
    python scripts/test_winding_layouts.py
"""
from __future__ import annotations

import ast
import sys
from typing import Iterable

import pytest

from pmsm_winding_builder import CANONICAL_LAYOUTS, WindingBuilder


# ────────────────────────────────────────────────────────────────────
#  Pure-Python validation (no Maxwell required)
# ────────────────────────────────────────────────────────────────────

def _check_layout(slots: int, poles: int) -> list[str]:
    """Run all integrity checks on a single layout. Returns list of error strings (empty == OK)."""
    errors: list[str] = []
    key = (slots, poles)
    if key not in CANONICAL_LAYOUTS:
        return [f"({slots}, {poles}) not in CANONICAL_LAYOUTS"]

    layout = CANONICAL_LAYOUTS[key]
    if len(layout) != slots:
        errors.append(f"layout length {len(layout)} != slots {slots}")

    # Phase / polarity validity
    for i, (ph, pol) in enumerate(layout):
        if ph not in ("A", "B", "C"):
            errors.append(f"slot {i+1} phase={ph!r} not in A/B/C")
        if pol not in ("+", "-"):
            errors.append(f"slot {i+1} polarity={pol!r} not in +/-")

    # Three-phase balance (always required)
    n_per_phase = {p: sum(1 for ph, _ in layout if ph == p) for p in "ABC"}
    if len(set(n_per_phase.values())) > 1:
        errors.append(f"3-phase imbalance: {n_per_phase}")

    # Concentrated winding with q >= 0.5: +/- balance required
    builder = WindingBuilder(slots=slots, poles=poles)
    if builder.winding_type.value == "concentrated" and builder.q >= 0.5:
        n_pos = sum(1 for _, pol in layout if pol == "+")
        n_neg = sum(1 for _, pol in layout if pol == "-")
        if n_pos != n_neg:
            errors.append(f"concentrated winding +/- imbalance (q={builder.q:.3f}): + {n_pos} - {n_neg}")

    # Polarity type mapping (standard convention)
    pol_types = {builder.polarity_type(p) for p in "+-"}
    if pol_types != {"Positive", "Negative"}:
        errors.append(f"polarity_type() doesn't return standard pair: {pol_types}")

    # Run compute_winding + Maxwell script gen — must not crash + Python syntax valid
    try:
        config = builder.compute_winding()
        if config.source != "canonical":
            errors.append(f"source={config.source} (expected canonical)")
        script = builder.generate_maxwell_script(config, conductor_number=40)
        ast.parse(script)
    except SyntaxError as e:
        errors.append(f"generated Maxwell script SyntaxError: {e}")
    except Exception as e:  # noqa: BLE001
        errors.append(f"compute/script exception: {type(e).__name__}: {e}")

    return errors


# ────────────────────────────────────────────────────────────────────
#  Pytest parametrized tests
# ────────────────────────────────────────────────────────────────────

ALL_KEYS: list[tuple[int, int]] = sorted(CANONICAL_LAYOUTS.keys(), key=lambda x: (x[0], x[1]))


@pytest.mark.parametrize("slots,poles", ALL_KEYS, ids=lambda v: f"{v[1]}p/{v[0]}s" if isinstance(v, tuple) else str(v))
def test_canonical_layout_integrity(slots: int, poles: int) -> None:
    """Every canonical (slots, poles) entry must be self-consistent."""
    errors = _check_layout(slots, poles)
    assert not errors, "\n".join(f"  - {e}" for e in errors)


@pytest.mark.parametrize("slots,poles", ALL_KEYS, ids=lambda v: f"{v[1]}p/{v[0]}s" if isinstance(v, tuple) else str(v))
def test_three_phase_coil_count(slots: int, poles: int) -> None:
    """The three phases must contain the same number of coils (no missing slots)."""
    layout = CANONICAL_LAYOUTS[(slots, poles)]
    n_per_phase = {p: sum(1 for ph, _ in layout if ph == p) for p in "ABC"}
    counts = list(n_per_phase.values())
    assert len(set(counts)) == 1, f"unbalanced phase counts: {n_per_phase}"


@pytest.mark.parametrize("slots,poles", ALL_KEYS, ids=lambda v: f"{v[1]}p/{v[0]}s" if isinstance(v, tuple) else str(v))
def test_winding_factor_positive(slots: int, poles: int) -> None:
    """k_w must be in the physically meaningful range [0, 1]."""
    builder = WindingBuilder(slots=slots, poles=poles)
    config = builder.compute_winding()
    assert 0.0 < config.winding_factor <= 1.0, (
        f"k_w = {config.winding_factor} out of range"
    )


# ────────────────────────────────────────────────────────────────────
#  CLI surface tests
# ────────────────────────────────────────────────────────────────────

def test_winding_layout_cli_runs(capsys):
    """`winding_layout.py <slots> <poles> --list` prints the table."""
    from winding_layout import render_list
    out = render_list(12, 8)
    assert "8p/12s" in out
    assert "Coil_1" in out
    assert "A+" in out
    assert "A-" in out


def test_winding_layout_cli_36slot(capsys):
    """8p36s must print a valid 36-slot table."""
    from winding_layout import render_list
    out = render_list(36, 8)
    # 36 slot rows + header
    assert "Coil_36" in out
    # Balanced per phase (60° phase belt: 12 each)
    assert "12" in out  # 12 per phase


def test_winding_layout_cli_md_format():
    """`--md` output contains markdown fences + named case."""
    from winding_layout import render_md
    out = render_md(36, 8)
    assert "## 8p/36s" in out
    assert "```" in out
    assert "k_w=" in out


def test_winding_layout_cli_maxwell_syntax():
    """`--maxwell` output is syntactically valid Python."""
    import ast as _ast
    from winding_layout import render_maxwell
    script = render_maxwell(12, 8, conductors=40)
    _ast.parse(script)  # raises SyntaxError if invalid


def test_winding_layout_cli_legacy_convention():
    """polarity_convention='legacy' must invert PolarityType (A+ → Negative)."""
    from pmsm_winding_builder import WindingBuilder
    b = WindingBuilder(slots=12, poles=8, polarity_convention="legacy")
    assert b.polarity_type("+") == "Negative"
    assert b.polarity_type("-") == "Positive"


# ────────────────────────────────────────────────────────────────────
#  Backwards-compat shim — keep `python scripts/test_winding_layouts.py` working
# ────────────────────────────────────────────────────────────────────

def main() -> int:
    """Run all canonical layout checks. Returns 0 on pass, 1 on fail.
    Mirrors the legacy scripts/test_winding_layouts.py CLI for users
    who invoke it directly without going through pytest."""
    print("=" * 70)
    print(f"  Validating {len(CANONICAL_LAYOUTS)} canonical pole-slot combinations")
    print("=" * 70)

    n_pass = n_fail = 0
    for slots, poles in ALL_KEYS:
        b = WindingBuilder(slots=slots, poles=poles)
        kw = b.compute_winding().winding_factor
        errs = _check_layout(slots, poles)
        status = "PASS" if not errs else "FAIL"
        marker = "[OK]" if not errs else "[!!]"
        print(f"  {marker} {poles:>2}p/{slots:<2}s  q={slots/(3*poles):.3f}  "
              f"type={b.winding_type.value:<13}  k_w={kw:.4f}  {status}")
        if errs:
            n_fail += 1
            for e in errs:
                print(f"      - {e}")
        else:
            n_pass += 1

    print()
    print("=" * 70)
    print(f"  Summary: {n_pass} passed, {n_fail} failed (of {len(CANONICAL_LAYOUTS)})")
    print("=" * 70)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
