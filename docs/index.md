# ansys-maxwell-motor

ANSYS Maxwell motor modeling + multiphysics MDAO orchestration skill.

> **For the project README, see the [GitHub README](../README.md).**
> **For the AI-agent entry point, see [SKILL.md](../SKILL.md).**

## What you'll find here

- **[Quick start guide](guides/quickstart.md)** — 5-minute walkthrough
- **[Winding layout table](../references/winding_layouts.md)** — 19
  canonical pole-slot combinations, lookup table for "which slot goes
  to which phase + polarity"
- **[API reference](api/)** — auto-generated from Python docstrings
- **[Examples](../examples/)** — 4 runnable scripts
- **[Changelog](../CHANGELOG.md)** — version history
- **[Contributing](../CONTRIBUTING.md)** — how to add a new pole-slot
  combination, fix bugs, etc.

## Build this site locally

```bash
pip install mkdocs mkdocs-material "mkdocstrings[python]"
mkdocs serve
# open http://127.0.0.1:8000
```

## Project layout

```
.
├── README.md             # GitHub landing
├── SKILL.md              # AI agent entry
├── pyproject.toml        # package metadata
├── scripts/              # ★ installable Python package
├── tests/                # pytest suite
├── examples/             # 4 runnable scripts
├── references/           # markdown docs (winding, design theory…)
├── docs/                 # ★ this site (mkdocs source)
└── .github/              # CI + issue/PR templates
```
