# `scripts` — the installable package

The `scripts/` directory is the **installable Python package** for
`ansys-maxwell-motor`. After `pip install -e .`, you can import it as:

```python
import scripts                                  # package
from scripts.pmsm_winding_builder import ...     # submodules
```

## Why "scripts"?

Historical naming — the package evolved from a folder of IronPython
scripts that were piped into Maxwell. The name stuck, but the contents
are now a proper Python library.

## Modules

| Module | Purpose | CLI entry point |
|--------|---------|-----------------|
| [`scripts.pmsm_winding_builder`](pmsm_winding_builder.md) | Lookup-first winding layout generator | `maxwell-winding` |
| [`scripts.winding_layout`](winding_layout.md) | CLI for slot-map lookup | (via `maxwell-winding`) |
| [`scripts.main`](main.md) | One-command Maxwell model builder | `maxwell-build` |
| `scripts.maxwell_bridge` | Unified 71-tool Maxwell MCP bridge | — |
| `scripts.mcp_connector` | stdio MCP client | — |
| `scripts.mdao_orchestrator` | Multiphysics MDAO + IGBT reliability | — |
| `scripts.motor_config` | `MotorConfig` dataclass + enums | — |
| `scripts.motor_param_calc` | Parameter auto-completion | — |
| `scripts.motor_optimizer` | NSGA-II / PSO / Bayesian | — |
| `scripts.slot_builder` | Slot geometry | — |
| `scripts.pm_builder` | PM geometry | — |
| `scripts.test_winding_layouts` | Backwards-compat CLI for tests | `maxwell-test` |

## Version

```python
>>> import scripts
>>> scripts.__version__
'4.4.0'
```

## Public API stability

- **`scripts.pmsm_winding_builder`** — public, stable, versioned semver
- **`scripts.winding_layout`** — public, stable
- **`scripts.motor_config`** — public, stable
- **`scripts.main`** — public but mostly thin wrapper around the bridge
- **`scripts.maxwell_bridge`**, **`scripts.mcp_connector`** —
  semi-public, may change as the MCP server evolves
- **`scripts.mdao_orchestrator`** — public but under active development

## Type hints

The package ships with `py.typed` marker (PEP 561), so type checkers
like `mypy` will use the inline type annotations. Not every module
is fully annotated yet — see [CONTRIBUTING.md](../../CONTRIBUTING.md#code-style)
for the migration plan.
