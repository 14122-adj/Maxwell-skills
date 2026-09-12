"""
Example 04: Compare two pole-slot combinations side-by-side.

Useful when deciding which pole/slot combination to use for a new design.
This is the script to run before choosing 8p/12s vs 8p/24s vs 8p/36s.

Run:
    python examples/04_compare_layouts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pmsm_winding_builder import WindingBuilder  # noqa: E402


def compare(slots: int, poles: int) -> str:
    """Return a compact comparison card for one pole-slot combination."""
    builder = WindingBuilder(slots=slots, poles=poles)
    config = builder.compute_winding()

    n_pos = sum(1 for _, pol in config.slot_map if pol == "+")
    n_neg = sum(1 for _, pol in config.slot_map if pol == "-")
    n_per_phase = {p: sum(1 for ph, _ in config.slot_map if ph == p) for p in "ABC"}
    type_name = builder.winding_type.value

    return (
        f"  ┌─ {poles}p/{slots}s ─────────────────────────────────────\n"
        f"  │ q          = {builder.q:.3f}\n"
        f"  │ Type       = {type_name}\n"
        f"  │ k_w        = {config.winding_factor:.4f}\n"
        f"  │ Coils      = {slots} total ({n_per_phase['A']} per phase, balanced)\n"
        f"  │ Polarities = {n_pos}+ {n_neg}–\n"
        f"  │ Source     = {config.source}\n"
        f"  │ Slot map   = {''.join(f'{p}{pol}' for p, pol in config.slot_map[:12])}{'…' if slots > 12 else ''}\n"
        f"  └─────────────────────────────────────────────────────────\n"
    )


def main() -> None:
    print("=" * 70)
    print("  Example 04: Compare 8p/12s, 8p/24s, 8p/36s (8-pole family)")
    print("=" * 70)

    print()
    print(compare(12, 8))
    print(compare(24, 8))
    print(compare(36, 8))

    print()
    print("=" * 70)
    print("  Selection guide:")
    print("    8p/12s  — concentrated, simplest, low cost, lower k_w (0.866)")
    print("    8p/24s  — distributed, balanced +/–, best k_w for distributed (0.96)")
    print("    8p/36s  — distributed, q=1.5, has sub-harmonics, often replaced by 4p/36s")
    print("=" * 70)


if __name__ == "__main__":
    main()
