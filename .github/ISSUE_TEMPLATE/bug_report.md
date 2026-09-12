---
name: Bug report
about: Report incorrect behavior or unexpected output
title: "[BUG] "
labels: ["bug"]
assignees: []
---

## Bug Description

<!-- A clear, concise description of what the bug is. -->

## Steps to Reproduce

```python
# Minimal code that triggers the bug
from pmsm_winding_builder import WindingBuilder
b = WindingBuilder(slots=?, poles=?)
print(b.compute_winding().slot_map)
```

or:

```bash
python scripts/winding_layout.py ? ? --list
```

## Expected Behavior

<!-- What you expected to happen -->

## Actual Behavior

<!-- What actually happened. Paste full output (stdout + stderr) below. -->

```
<paste output here>
```

## Environment

- **OS**: [e.g. Windows 11 / Ubuntu 22.04 / macOS 14]
- **Python version**: [run `python --version`]
- **Package version**: [run `pip show ansys-maxwell-motor` or `python -c "import scripts; print(scripts.__version__)"`]
- **ANSYS Maxwell version** (if relevant): [e.g. 2024 R1]

## Additional Context

- Pole-slot combination affected: [e.g. 8p/12s, 4p/24s, ...]
- Source of truth: [is this in `CANONICAL_LAYOUTS` or fallback algorithm?]
- Reference / textbook page: [if you have one, link it here]
