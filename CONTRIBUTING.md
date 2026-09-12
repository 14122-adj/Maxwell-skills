# Contributing to ansys-maxwell-motor

Thank you for your interest in contributing! This document covers the dev
workflow, code style, and the most useful ways to contribute.

## Table of contents

1. [Code of conduct](#code-of-conduct)
2. [Quick start](#quick-start)
3. [Development workflow](#development-workflow)
4. [Code style](#code-style)
5. [Testing](#testing)
6. [Adding a new pole-slot combination](#adding-a-new-pole-slot-combination)
7. [Pull request process](#pull-request-process)
8. [Reporting bugs](#reporting-bugs)

---

## Code of conduct

Be respectful. Be technical. Disagree on ideas, not people. We follow the
[Contributor Covenant](https://www.contributor-covenant.org/) spirit.

---

## Quick start

```bash
# 1. Fork & clone
git clone https://github.com/<your-fork>/ansys-maxwell-motor-skill.git
cd ansys-maxwell-motor-skill

# 2. Install in editable mode + dev deps
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 3. Verify your setup
make all    # runs lint + format + tests + build

# 4. Make your change, then
make test   # quick check
make lint
```

---

## Development workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```

2. **Make focused commits** — one logical change per commit. Use
   [Conventional Commits](https://www.conventionalcommits.org/) style:
   ```
   feat(winding): add 12p54s to CANONICAL_LAYOUTS
   fix(builder): correct 8p36s C-phase polarity
   docs: clarify standard vs legacy polarity convention
   test: cover 6p54s q=3 layout
   refactor: extract WindingConfig dataclass
   chore: bump version to 4.5.0
   ```

3. **Run the full check** before pushing:
   ```bash
   make all
   ```

4. **Push & open a PR**:
   ```bash
   git push origin feat/your-feature
   ```
   Then open a Pull Request on GitHub. The PR template will guide you
   through the checklist.

---

## Code style

We use **ruff** for both formatting and linting (replaces black + isort + flake8).

```bash
# Auto-format
make format         # or: ruff format scripts tests examples

# Lint
make lint           # or: ruff check scripts tests examples
```

Style rules (in `pyproject.toml`):

- **Line length**: 110 characters
- **Quotes**: double quotes
- **Imports**: sorted with `isort`-style grouping
- **Naming**: `snake_case` for functions/vars, `PascalCase` for classes,
  `UPPER_SNAKE_CASE` for constants. Math symbols (e.g. `Dsi`, `Bs0`) keep
  their conventional capitalization — exception is documented in
  `pyproject.toml [tool.ruff.lint] ignore`.
- **Type hints**: progressive. New code should be fully typed; legacy
  code is being migrated as it's touched.

### Docstrings

Use Google-style docstrings. Example:

```python
def compute_winding_factor(self) -> float:
    """Compute the fundamental winding factor k_w.

    For distributed windings: k_w = k_d × k_p (distribution × pitch).
    For concentrated windings: derived from coil pitch and slot angle.

    Returns:
        Fundamental winding factor in [0, 1]. Typical values:
        8p/12s: 0.866, 8p/24s: 0.96, 8p/36s: 0.96.
    """
```

---

## Testing

All changes must come with tests. The test suite is in `tests/` and uses
**pytest**.

```bash
# Run all tests
make test                # or: pytest -v

# Run only one test
pytest tests/test_pmsm_winding_builder.py::TestComputeWinding::test_canonical_source -v

# Run with coverage
make test-cov            # or: pytest --cov=scripts --cov-report=term-missing
```

Test naming convention: `test_<unit>.py` for files, `Test<Class>` for
classes, `test_<behavior>` for methods. Use parametrize to test multiple
inputs.

---

## Adding a new pole-slot combination

This is the **most useful contribution** to this project. Here's the
complete checklist:

### 1. Determine the slot map

Use a textbook reference (Pyrhonen §4.4, Hrabovcova, etc.) or
simulation. The slot map is a list of `(phase, polarity)` tuples,
one per slot (1-indexed).

### 2. Add to `CANONICAL_LAYOUTS`

In `scripts/pmsm_winding_builder.py`:

```python
CANONICAL_LAYOUTS = {
    # ... existing entries ...
    (48, 16): [  # 16p/48s (q=1.0, distributed)
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
    ] * 8,  # 8 periods of 6 slots
}
```

Also add to `WINDING_FACTOR_TABLE`:

```python
WINDING_FACTOR_TABLE = {
    # ... existing entries ...
    (48, 16): 0.96,
}
```

### 3. Mirror in `references/winding_layouts.md`

Add a new section with the slot map in canonical format (1-indexed,
ASCII table, per-period × N).

### 4. Run the tests

```bash
pytest tests/test_pmsm_winding_builder.py -v
pytest tests/test_winding_layouts.py -v
```

The parametrized test `test_canonical_layout_integrity` automatically
picks up the new entry and runs all integrity checks.

### 5. Add an example (optional but encouraged)

Create `examples/NN_<name>.py` showing the new layout in action.

### 6. Update CHANGELOG.md

Under `[Unreleased]` → `Added`:

```
- Canonical layout: 16p/48s (q=1.0, distributed)
```

---

## Pull request process

1. **Open a PR** with a clear title and description. Use the
   `.github/PULL_REQUEST_TEMPLATE.md` checklist.

2. **CI must pass** — lint, format, tests on all OS × Python versions.

3. **One approval** is required from a maintainer.

4. **Squash-merge** — your commits will be squashed into one
   with the PR title as the commit message.

5. **Update CHANGELOG.md** under `[Unreleased]`. The maintainer
   will move it to a versioned section on release.

---

## Reporting bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md).
Include:

- Minimal reproduction (code or CLI command)
- Expected vs actual output
- Environment (OS, Python version, package version, Maxwell version)
- Pole-slot combination affected
- Source of truth: is the layout in `CANONICAL_LAYOUTS` or fallback?

---

## Questions?

- 💬 [Open a Q&A discussion](https://github.com/Torry/ansys-maxwell-motor-skill/discussions)
- 🐛 [File an issue](https://github.com/Torry/ansys-maxwell-motor-skill/issues)
- 📖 [Read SKILL.md](SKILL.md) — AI-agent entry point

---

## Maintainers

- [@Torry](https://github.com/Torry) — lead

## License

By contributing, you agree that your contributions will be released
under the [Unlicense](LICENSE) (public domain).
