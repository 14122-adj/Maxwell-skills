# Quick start

5-minute walkthrough from zero to your first Maxwell IronPython script.

## Install

```bash
git clone https://github.com/Torry/ansys-maxwell-motor-skill.git
cd ansys-maxwell-motor-skill
pip install -e ".[dev]"
```

## 1. Look up a winding layout

The most common task. Pick a pole-slot combination:

```bash
python scripts/winding_layout.py 12 8 --list
```

Output:
```
| Slot | Phase+Pol | Coil |
|------|-----------|------|
| 1    | A+        | Coil_1 |
| 2    | A-        | Coil_2 |
| 3    | B+        | Coil_3 |
| 4    | B-        | Coil_4 |
| 5    | C+        | Coil_5 |
| 6    | C-        | Coil_6 |
| 7    | A+        | Coil_7 |
| 8    | A-        | Coil_8 |
| 9    | B+        | Coil_9 |
| 10   | B-        | Coil_10 |
| 11   | C+        | Coil_11 |
| 12   | C-        | Coil_12 |
```

This is the **Pyrhonen AABBCC** pattern for 8p/12s concentrated winding.

## 2. Generate the Maxwell IronPython script

```bash
python scripts/winding_layout.py 12 8 --maxwell > my_motor_winding.py
```

This produces a ~120-line IronPython script with `AssignWindingGroup`,
`AssignCoilGroup`, and `AddWindingCoils` calls — ready to paste into the
Maxwell IronPython console.

## 3. From Python

```python
from pmsm_winding_builder import WindingBuilder

builder = WindingBuilder(slots=12, poles=8)
config = builder.compute_winding()

print(builder.render_slot_map(config))
# Slot:  1   2   3   4   5   6   7   8   9  10  11  12
# Phase: A+  A-  B+  B-  C+  C-  A+  A-  B+  B-  C+  C-
# Coil:  C1  C2  C3  C4  C5  C6  C7  C8  C9  C10 C11 C12

script = builder.generate_maxwell_script(config, conductor_number=40)
print(f"Generated {len(script.splitlines())} lines of IronPython")
```

## 4. Run the test suite

```bash
pytest tests/ -v
# 147 passed in 0.45s
```

## 5. Try the examples

```bash
python examples/01_8p12s_concentrated.py
python examples/02_8p36s_distributed.py
python examples/03_fallback_algorithm.py
python examples/04_compare_layouts.py
```

## Next steps

- 📖 Read [SKILL.md](../SKILL.md) for the full workflow
- 📐 Read [`references/winding_layouts.md`](../references/winding_layouts.md)
  for the full canonical table
- 🛠 Read [CONTRIBUTING.md](../CONTRIBUTING.md) to add a new pole-slot combo
- 🧪 Read [`tests/`](../tests/) to understand the test surface
