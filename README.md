# ansys-maxwell-motor

[![CI](https://github.com/Torry/ansys-maxwell-motor-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/Torry/ansys-maxwell-motor-skill/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-147%20passed-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Unlicense-blue)](LICENSE)
[![Version](https://img.shields.io/badge/version-4.4.0-orange)](pyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

ANSYS Maxwell motor modeling + multiphysics MDAO orchestration skill.

> **AI agents — read this first:** [SKILL.md §绕组位置速查](SKILL.md) is the single
> source of truth for "which slot goes to which phase + polarity". The
> `references/winding_layouts.md` table is the canonical mapping. **Never
> guess — look it up.**

---

## What's in this repo

This is an opinionated, end-to-end skill for **electromagnetic + multiphysics
motor design automation in ANSYS Maxwell**:

| Capability | Where | What it does |
|---|---|---|
| **Winding layout** (19 canonical pole-slot combos) | `scripts/pmsm_winding_builder.py` | Lookup-first slot → phase + polarity mapping |
| **Winding CLI** | `scripts/winding_layout.py` | One-line slot map lookup for any (slots, poles) |
| **Auto model builder** | `scripts/main.py` | One-command Maxwell model from `MotorConfig` |
| **71 Maxwell MCP tools** | `scripts/maxwell_bridge.py` | Unified bridge (geometry/material/mesh/solve) |
| **10 simulation types** | `projects/25Nm_PMSM/01_*.py` … `13_*.py` | No-load, rated, overload, demag, NVH, etc. |
| **MDAO** | `scripts/mdao_orchestrator.py` | Electromagnetic-structural-thermal + IGBT reliability |
| **NSGA-II / PSO** | `scripts/motor_optimizer.py` | Multi-objective optimization |
| **Design theory** | `references/motor_design_guide.md` | Formulas, materials, winding theory |
| **Winding table** | `references/winding_layouts.md` | 19 canonical layouts + Maxwell naming + verification |

---

## Installation

### From source (recommended for development)

```bash
git clone https://github.com/Torry/ansys-maxwell-motor-skill.git
cd ansys-maxwell-motor-skill
pip install -e ".[dev]"
```

This installs:

- The `ansys-maxwell-motor` package (importable as `scripts.*`)
- Three CLI entry points: `maxwell-winding`, `maxwell-build`, `maxwell-test`
- Dev tooling: `pytest`, `pytest-cov`, `ruff`, `mypy`

### Optional extras

```bash
pip install -e ".[all]"     # + pywin32 (Windows COM bridge) + matplotlib
pip install -e ".[mcp]"     # MCP server dependency only
```

### Plain source (no install)

The skill works without installation — just add `scripts/` to `PYTHONPATH`:

```bash
PYTHONPATH=./scripts python scripts/winding_layout.py 12 8 --list
```

---

## Quick start

### 1. Look up a winding layout

```bash
# CLI
python scripts/winding_layout.py 12 8 --list

#  ┌──────── Slot ─┬── Phase ─┬─ Coil ─┐
#  │  1   2   3 … │ A+ A- B+ │ C1 C2  │
#  └───────────────┴──────────┴────────┘
```

```
Slot:    1   2   3   4   5   6   7   8   9  10  11  12
Phase:   A+  A-  B+  B-  C+  C-  A+  A-  B+  B-  C+  C-
Coil:    C1  C2  C3  C4  C5  C6  C7  C8  C9  C10 C11 C12
```

### 2. Generate a Maxwell IronPython script

```bash
python scripts/winding_layout.py 12 8 --maxwell > motor_winding.py
# Paste motor_winding.py into the Maxwell IronPython console
# (after geometry + materials + band are set up)
```

### 3. From Python

```python
from pmsm_winding_builder import WindingBuilder

builder = WindingBuilder(slots=12, poles=8, polarity_convention="standard")
config = builder.compute_winding()

print(builder.render_slot_map(config))      # human-readable
print(builder.render_summary(config))       # + phase balance check
script = builder.generate_maxwell_script(config, conductor_number=40)
```

### 4. One-command full model

```bash
python scripts/main.py --preset 8p12s_servo
# Generates geometry + materials + winding + boundary + mesh scripts
```

### 5. Run the test suite

```bash
pytest tests/ -v
# 147 passed in 0.45s
```

---

## Run the examples

| # | File | What it shows |
|---|---|---|
| 01 | [`examples/01_8p12s_concentrated.py`](examples/01_8p12s_concentrated.py) | Canonical 8p/12s Pyrhonen AABBCC |
| 02 | [`examples/02_8p36s_distributed.py`](examples/02_8p36s_distributed.py) | 8p/36s q=1.5 distributed, intrinsic imbalance |
| 03 | [`examples/03_fallback_algorithm.py`](examples/03_fallback_algorithm.py) | 7p/15s non-canonical (fallback) |
| 04 | [`examples/04_compare_layouts.py`](examples/04_compare_layouts.py) | Side-by-side 8p/12s vs 8p/24s vs 8p/36s |

```bash
python examples/01_8p12s_concentrated.py
```

---

## Project structure

```
ansys-maxwell-motor-skill/
├── SKILL.md                # AI entry point: trigger words + workflow + winding cheat sheet
├── README.md               # this file
├── CHANGELOG.md            # version history (Keep a Changelog format)
├── CONTRIBUTING.md         # how to contribute
├── LICENSE                 # Unlicense (public domain)
├── pyproject.toml          # modern Python packaging + ruff/pytest/mypy config
├── Makefile                # make test/lint/format/clean
│
├── scripts/                # ★ the installable Python package
│   ├── __init__.py
│   ├── py.typed
│   ├── pmsm_winding_builder.py   # canonical winding layout generator
│   ├── winding_layout.py         # CLI for slot-map lookup
│   ├── main.py                   # one-command model builder
│   ├── maxwell_bridge.py         # 71-tool Maxwell MCP bridge
│   ├── mcp_connector.py          # stdio MCP client
│   ├── mdao_orchestrator.py      # MDAO chain + IGBT reliability
│   ├── motor_config.py           # MotorConfig dataclass
│   ├── motor_param_calc.py       # parameter auto-completion
│   ├── motor_optimizer.py        # NSGA-II / PSO / Bayesian
│   ├── slot_builder.py           # slot geometry
│   ├── pm_builder.py             # PM geometry
│   ├── test_winding_layouts.py   # thin wrapper for back-compat
│   └── ...                       # (12 modules)
│
├── tests/                  # pytest suite (147 tests)
│   ├── conftest.py
│   ├── test_winding_layouts.py
│   ├── test_pmsm_winding_builder.py
│   └── test_winding_layout_cli.py
│
├── examples/               # 4 runnable examples
│   ├── 01_8p12s_concentrated.py
│   ├── 02_8p36s_distributed.py
│   ├── 03_fallback_algorithm.py
│   ├── 04_compare_layouts.py
│   └── README.md
│
├── references/             # documentation (markdown)
│   ├── winding_layouts.md         # ★ canonical pole-slot table
│   ├── motor_design_guide.md
│   ├── mcp_tools_reference.md
│   ├── simulation_configs.md
│   ├── optimization_guide.md
│   ├── multiphysics_guide.md
│   └── troubleshooting.md
│
├── projects/25Nm_PMSM/     # full design example: 13 simulation scripts
├── mcp-maxwell/            # Maxwell MCP server (71 tools)
├── output_scripts/         # historical debug outputs
├── archive/                # deprecated scripts (kept for reference)
├── debug/                  # one-off diagnostic scripts
└── results/                # CSV exports from test simulations
```

---

## Development

```bash
# Install dev deps
pip install -e ".[dev]"

# Run all checks (mirror CI)
make all         # or individually:
make test        # pytest
make lint        # ruff check
make format      # ruff format
make typecheck   # mypy (non-blocking)
make build       # sdist + wheel
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full dev workflow.

---

## CI

GitHub Actions runs on every push / PR:

- ✅ Lint (ruff format + ruff check)
- ✅ Type-check (mypy, non-blocking)
- ✅ Test (3 OS × 4 Python versions = 12 jobs)
- ✅ Build (sdist + wheel)
- ✅ Smoke test (CLI works after `pip install`)

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

The most useful contributions are:

1. **New canonical pole-slot combinations** — add to `CANONICAL_LAYOUTS` in
   `scripts/pmsm_winding_builder.py` AND mirror in
   `references/winding_layouts.md`. Run `pytest tests/` to validate.
2. **Bug fixes for the Maxwell COM bridge** — wrap missing tools, fix
   signature drift.
3. **New simulation types** — add a script under `projects/25Nm_PMSM/NN_*.py`
   that uses the bridge.
4. **Documentation** — typos, missing examples, unclear wording.

---

## License

[Unlicense](LICENSE) — public domain. Use, modify, redistribute freely.

---

## Acknowledgments

- Slot/pole theory and 19 canonical layouts: based on J. Pyrhonen, T. Jokinen,
  V. Hrabovcova, *Design of Rotating Electrical Machines* (2nd ed., Wiley 2014).
- 25Nm PMSM project template: derived from typical industrial EV traction
  motor specs.
- IGBT reliability workflow: based on GB/T 29332 power cycling test standard.
