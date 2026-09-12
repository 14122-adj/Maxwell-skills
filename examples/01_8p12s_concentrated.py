"""
Example 01: 8p/12s concentrated winding (most common servo motor).

Demonstrates the simplest end-to-end use of the skill:
  1. Build a WindingBuilder for 8p/12s
  2. Compute the canonical layout
  3. Print the slot map (human-readable)
  4. Print the phase belt diagram
  5. Print the summary (3-phase balance check)
  6. Generate the Maxwell COM API IronPython script

Run:
    python examples/01_8p12s_concentrated.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable without `pip install -e .`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pmsm_winding_builder import WindingBuilder  # noqa: E402


def main() -> None:
    print("=" * 70)
    print("  Example 01: 8p/12s concentrated winding (PMSM servo motor)")
    print("=" * 70)

    # ── Step 1: build the winding generator ──
    # 12 slots, 8 poles, 3 phases, double-layer, standard polarity convention
    builder = WindingBuilder(
        slots=12,
        poles=8,
        phases=3,
        layer="double",
        polarity_convention="standard",   # A+ → Positive, A- → Negative
    )
    print(f"Builder: {builder.slots} slots / {builder.poles} poles / "
          f"{builder.phases} phases / q={builder.q} / type={builder.winding_type.value}")

    # ── Step 2: compute the canonical layout ──
    config = builder.compute_winding()
    print(f"Source:  {config.source}  (canonical = from references/winding_layouts.md)")

    # ── Step 3: print the slot map (this is what AI/engineering reads) ──
    print()
    print(builder.render_slot_map(config))

    # ── Step 4: print the phase belt diagram ──
    print()
    print(builder.render_phase_belt(config))

    # ── Step 5: print the per-phase balance check ──
    print()
    print(builder.render_summary(config))

    # ── Step 6: generate the Maxwell IronPython script ──
    script = builder.generate_maxwell_script(config, conductor_number=40)

    # Save the Maxwell script to disk for inspection / paste into Maxwell
    out_path = ROOT / "examples" / "output_8p12s_winding.py"
    out_path.write_text(script, encoding="utf-8")

    print()
    print("=" * 70)
    print(f"  Maxwell script written to: {out_path}")
    print(f"  ({len(script.splitlines())} lines, ready to paste into Maxwell IronPython console)")
    print("=" * 70)


if __name__ == "__main__":
    main()
