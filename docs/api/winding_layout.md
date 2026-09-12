# `scripts.winding_layout` — CLI for slot-map lookup

::: scripts.winding_layout
    options:
      show_source: true
      show_root_heading: true
      members_order: source

## Command-line usage

```bash
# Default (table format, ASCII)
python -m scripts.winding_layout 12 8

# List (table per slot)
python -m scripts.winding_layout 12 8 --list

# Markdown (paste into docs)
python -m scripts.winding_layout 12 8 --md

# Maxwell IronPython script
python -m scripts.winding_layout 12 8 --maxwell

# All canonical combinations
python -m scripts.winding_layout --all

# Compare two layouts
python -m scripts.winding_layout --compare 12 8 36 8

# Use legacy polarity convention
python -m scripts.winding_layout 12 8 --list --convention=legacy
```

## Python API

```python
from winding_layout import render_list, render_md, render_maxwell

# All return strings
print(render_list(12, 8))
print(render_md(36, 8))
print(render_maxwell(12, 8, conductors=40, convention="standard"))
```
