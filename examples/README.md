# Examples

Runnable end-to-end examples for the `ansys-maxwell-motor` skill.

All examples are **self-contained** — they add `scripts/` to `sys.path` at
runtime so you don't need to `pip install -e .` first.

## Run

```bash
# From the project root:
python examples/01_8p12s_concentrated.py
python examples/02_8p36s_distributed.py
python examples/03_fallback_algorithm.py
python examples/04_compare_layouts.py
```

## What each example does

| # | File | What it shows | Output |
|---|------|---------------|--------|
| 01 | `01_8p12s_concentrated.py` | Canonical 8p/12s concentrated (Pyrhonen AABBCC) | Slot map + Maxwell script |
| 02 | `02_8p36s_distributed.py` | 8p/36s q=1.5 distributed (60° phase belt) | Slot map + [INFO] about intrinsic +/- imbalance |
| 03 | `03_fallback_algorithm.py` | 7p/15s non-canonical (fallback algorithm) | [WARN] `source=computed` + next-steps |
| 04 | `04_compare_layouts.py` | Side-by-side 8p/12s vs 8p/24s vs 8p/36s | Decision matrix |

## Outputs

Each example writes a Maxwell IronPython script to `examples/output_*.py`.
These are ready to paste into the Maxwell IronPython console
(after creating the geometry, materials, and band).

## Using as templates

Copy any example to your own project directory, modify the
`slots=` / `poles=` parameters, and re-run. The script regenerates
the Maxwell IronPython code with the correct winding layout.
