"""
Example 03: Fallback algorithm for a non-canonical pole-slot combination.

Demonstrates:
  - What happens when (slots, poles) is NOT in the canonical table
  - The builder falls back to the algorithmic derivation
  - Output is marked `source=computed` (NOT canonical) — meaning the
    AI / user MUST manually verify the result before trusting it.

The 7p/15s combination used here is intentionally non-canonical —
it has q = 15 / (3*7) = 0.714..., a "real-world but rare" fractional slot.

Run:
    python examples/03_fallback_algorithm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pmsm_winding_builder import WindingBuilder  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("  Example 03: Fallback algorithm for 7p/15s (non-canonical)")
    print("=" * 70)

    # 15 slots, 7 poles — q = 15/21 = 0.714..., rare in industry
    builder = WindingBuilder(slots=15, poles=7, phases=3)
    print(f"Builder: {builder.slots} slots / {builder.poles} poles / "
          f"q={builder.q:.3f} / type={builder.winding_type.value}")

    config = builder.compute_winding()
    print(f"Source:  {config.source}  (computed = NOT in canonical table, fallback used)")

    # ── Slot map ──
    print()
    print(builder.render_slot_map(config))

    # ── Phase belt ──
    print()
    print(builder.render_phase_belt(config))

    # ── Summary: WILL show [WARN] because source=computed ──
    print()
    print(builder.render_summary(config))

    # ── Verdict on whether to use this layout ──
    print()
    print("=" * 70)
    print("  AI / user next steps for source=computed layouts:")
    print("    1. Manually verify the slot map against your motor design")
    print("    2. If correct, contribute the layout to CANONICAL_LAYOUTS in")
    print("       scripts/pmsm_winding_builder.py")
    print("    3. Mirror it in references/winding_layouts.md")
    print("    4. Re-run `pytest tests/test_winding_layouts.py`")
    print("=" * 70)


if __name__ == "__main__":
    main()
