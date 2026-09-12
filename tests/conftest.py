"""
conftest.py — shared pytest fixtures for the ansys-maxwell-motor test suite.

Goals:
  - Make scripts/ importable without installing the package (dev workflow)
  - Provide a `slot_pole_matrix` fixture for parametrize reuse
  - Skip integration tests if ANSYS Maxwell is not installed
"""
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

import pytest

# ────────────────────────────────────────────────────────────────────
#  Make scripts/ importable without `pip install -e .`
# ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# ────────────────────────────────────────────────────────────────────
#  Project-wide fixtures
# ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Repository root directory."""
    return ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> Path:
    """Path to scripts/ — the actual installable package source."""
    return SCRIPTS_DIR


@pytest.fixture(scope="session")
def references_dir() -> Path:
    """Path to references/ — markdown documentation."""
    return ROOT / "references"


# Common (slots, poles) combinations to test against
COMMON_COMBOS: list[tuple[int, int]] = [
    (12, 8),    # 8p/12s concentrated
    (12, 10),   # 10p/12s
    (24, 8),    # 8p/24s distributed
    (36, 8),    # 8p/36s q=1.5
    (48, 8),    # 8p/48s q=2
    (54, 6),    # 6p/54s q=3
    (72, 6),    # 6p/72s q=4
]


@pytest.fixture(params=COMMON_COMBOS, ids=lambda c: f"{c[1]}p/{c[0]}s")
def slot_pole_pair(request) -> tuple[int, int]:
    """Parametrize over the 7 most common pole-slot combinations."""
    return request.param


# ────────────────────────────────────────────────────────────────────
#  Skip markers
# ────────────────────────────────────────────────────────────────────

def _has_ansys_maxwell() -> bool:
    """Detect if ANSYS Maxwell (or a stand-in) is installed."""
    # Real check would look for AEDT or win32com; we keep it simple.
    # Integration tests use this to skip when the simulator is absent.
    return shutil.which("ansysedt") is not None


requires_maxwell = pytest.mark.skipif(
    not _has_ansys_maxwell(),
    reason="ANSYS Maxwell (ansysedt) not found in PATH — integration test skipped",
)
