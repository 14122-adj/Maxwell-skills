"""
Example 02: 8p/36s distributed winding (industrial / wind power).

Demonstrates:
  - A fractional-slot (q=1.5) winding that has inherent +/– imbalance
  - 60° phase belt pattern (Pyrhonen textbook standard)
  - The warning/info messages that the builder produces

Run:
    python examples/02_8p36s_distributed.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pmsm_winding_builder import WindingBuilder  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("  Example 02: 8p/36s distributed winding (wind power / industrial)")
    print("=" * 70)

    # 36 slots, 8 poles, 3 phases, double-layer
    # q = 36 / (3 * 8) = 1.5  → fractional slot
    builder = WindingBuilder(slots=36, poles=8, phases=3)
    print(f"Builder: {builder.slots} slots / {builder.poles} poles / "
          f"q={builder.q} / type={builder.winding_type.value}")

    config = builder.compute_winding()
    print(f"Source:  {config.source}")
    print(f"k_w:     {config.winding_factor:.4f}")

    # ── Slot map (multi-row format for 36 slots) ──
    print()
    print(builder.render_slot_map(config))

    # ── Phase belt diagram (one row per 9-slot fundamental period) ──
    print()
    print(builder.render_phase_belt(config))

    # ── Summary: this will print [INFO] about the q=1.5 imbalance being intrinsic ──
    print()
    print(builder.render_summary(config))

    # ── Save Maxwell script ──
    script = builder.generate_maxwell_script(config, conductor_number=40)
    out_path = ROOT / "examples" / "output_8p36s_winding.py"
    out_path.write_text(script, encoding="utf-8")

    print()
    print("=" * 70)
    print(f"  Maxwell script written to: {out_path}")
    print(f"  9-slot period × 4 = 36 slots; each phase has 4+/8– (intrinsic to q=1.5)")
    print("=" * 70)


if __name__ == "__main__":
    main()
