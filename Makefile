# ─────────────────────────────────────────────────────────────────────
#  ansys-maxwell-motor — Makefile
#
#  Common tasks:
#    make help         show this help
#    make install      install package + dev deps in editable mode
#    make test         run pytest
#    make test-cov     run pytest with coverage
#    make lint         run ruff check
#    make format       run ruff format (modifies files)
#    make typecheck    run mypy (non-blocking)
#    make build        build sdist + wheel
#    make clean        remove build artifacts
#    make all          format + lint + test + build
#    make run-example  run an example by name (e.g. `make run-example N=01`)
#    make run-cli      run the winding CLI (uses ARGS="<slots> <poles> --list")
# ─────────────────────────────────────────────────────────────────────

# Use bash on Windows (Git Bash / WSL); fall back to sh on Linux/macOS
SHELL := /bin/bash
ifeq ($(OS),Windows_NT)
    SHELL := pwsh.exe
endif

PYTHON       ?= python
PIP          ?= $(PYTHON) -m pip
RUFF         ?= ruff
PYTEST       ?= pytest
MYPY         ?= mypy
SRC_DIR      := scripts
TEST_DIR     := tests
EXAMPLE_DIR  := examples
ALL_DIRS     := $(SRC_DIR) $(TEST_DIR) $(EXAMPLE_DIR)

.DEFAULT_GOAL := help

# ─────────────────────────────────────────────────────────────────────
#  Help
# ─────────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo "ansys-maxwell-motor — Makefile"
	@echo ""
	@echo "Common targets:"
	@echo "  make install        Install package + dev deps in editable mode"
	@echo "  make test           Run pytest"
	@echo "  make test-cov       Run pytest with coverage report"
	@echo "  make lint           Run ruff check (no changes)"
	@echo "  make format         Run ruff format (modifies files)"
	@echo "  make typecheck      Run mypy (non-blocking, prints issues)"
	@echo "  make build          Build sdist + wheel into dist/"
	@echo "  make clean          Remove build artifacts"
	@echo "  make all            format + lint + test + build (full pre-PR check)"
	@echo "  make run-example N=01   Run example 01 (01_8p12s_concentrated.py)"
	@echo "  make run-cli ARGS=\"12 8 --list\"   Run the winding CLI"
	@echo "  make canonical      Print all canonical pole-slot combinations"
	@echo "  make smoke          Smoke-test the CLI after install"

# ─────────────────────────────────────────────────────────────────────
#  Install
# ─────────────────────────────────────────────────────────────────────

.PHONY: install
install:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

.PHONY: install-all
install-all:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[all]"

# ─────────────────────────────────────────────────────────────────────
#  Test
# ─────────────────────────────────────────────────────────────────────

.PHONY: test
test:
	$(PYTEST) -v

.PHONY: test-fast
test-fast:
	$(PYTEST) -x --tb=short

.PHONY: test-cov
test-cov:
	$(PYTEST) --cov=$(SRC_DIR) --cov-report=term-missing --cov-report=html --cov-report=xml

.PHONY: test-watch
test-watch:
	$(PYTEST) --watch   # requires pytest-watch

# ─────────────────────────────────────────────────────────────────────
#  Lint / format
# ─────────────────────────────────────────────────────────────────────

.PHONY: lint
lint:
	$(RUFF) check $(ALL_DIRS)

.PHONY: format
format:
	$(RUFF) format $(ALL_DIRS)

.PHONY: format-check
format-check:
	$(RUFF) format --check $(ALL_DIRS)

.PHONY: typecheck
typecheck:
	$(MYPY) $(SRC_DIR) || echo "(typecheck issues above are non-blocking)"

# ─────────────────────────────────────────────────────────────────────
#  Build / clean
# ─────────────────────────────────────────────────────────────────────

.PHONY: build
build:
	$(PIP) install --upgrade build
	$(PYTHON) -m build

.PHONY: clean
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov/
	rm -rf */__pycache__ */*/__pycache__
	find . -name "*.pyc" -delete
	find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned build artifacts."

# ─────────────────────────────────────────────────────────────────────
#  Combined targets
# ─────────────────────────────────────────────────────────────────────

.PHONY: all
all: format lint test build
	@echo ""
	@echo "✓ All checks passed."

.PHONY: check
check: format-check lint test-fast
	@echo ""
	@echo "✓ Pre-commit check passed."

# ─────────────────────────────────────────────────────────────────────
#  Run examples / CLI
# ─────────────────────────────────────────────────────────────────────

.PHONY: run-example
run-example:
	@test -n "$(N)" || (echo "Usage: make run-example N=01"; exit 1)
	$(PYTHON) $(EXAMPLE_DIR)/$(N)_*.py

.PHONY: run-cli
run-cli:
	@test -n "$(ARGS)" || (echo "Usage: make run-cli ARGS=\"12 8 --list\""; exit 1)
	$(PYTHON) -m scripts.winding_layout $(ARGS)

.PHONY: canonical
canonical:
	$(PYTHON) -m scripts.winding_layout --all

.PHONY: smoke
smoke:
	@echo "→ Smoke test: import package"
	$(PYTHON) -c "import scripts; print('  scripts version:', scripts.__version__)"
	@echo "→ Smoke test: import builder"
	$(PYTHON) -c "from scripts.pmsm_winding_builder import WindingBuilder; b = WindingBuilder(slots=12, poles=8); c = b.compute_winding(); print('  8p12s coils/phase:', c.coils_per_phase)"
	@echo "→ Smoke test: import CLI"
	$(PYTHON) -c "from scripts.winding_layout import render_list; print(render_list(12, 8)[:200])"
	@echo ""
	@echo "✓ Smoke test passed."

# ─────────────────────────────────────────────────────────────────────
#  Release helpers (maintainers only)
# ─────────────────────────────────────────────────────────────────────

.PHONY: version
version:
	@$(PYTHON) -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

.PHONY: bump
bump:
	@test -n "$(PART)" || (echo "Usage: make bump PART=patch|minor|major"; exit 1)
	@echo "Bumping $(PART) version..."
	@$(PYTHON) -c "import tomllib, pathlib; p = pathlib.Path('pyproject.toml'); t = p.read_text(); import re; old = re.search(r'version = \"(\d+\.\d+\.\d+)\"', t).group(1); parts = old.split('.'); ix = {'patch': 2, 'minor': 1, 'major': 0}[$(PART)]; parts[ix] = str(int(parts[ix]) + 1); new = '.'.join(parts); t = t.replace(old, new, 1); p.write_text(t); print(f'{old} -> {new}')"
