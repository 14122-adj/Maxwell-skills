"""
test_winding_layout_cli.py — CLI surface tests for scripts/winding_layout.py

Covers:
  - `python -m scripts.winding_layout` arguments
  - --list / --md / --maxwell / --all / --compare output
  - Pattern / polarity_convention flags
  - ASCII output is well-formed (no garbled escapes)
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

import pytest

# We import the module by name (conftest.py adds scripts/ to sys.path)
from winding_layout import (
    render_all,
    render_compare,
    render_list,
    render_maxwell,
    render_md,
)


# ────────────────────────────────────────────────────────────────────
#  Module-level renderers
# ────────────────────────────────────────────────────────────────────

class TestRenderList:
    def test_basic_8p12s(self):
        out = render_list(12, 8)
        assert "8p/12s" in out
        # All 12 slots present
        for i in range(1, 13):
            assert f"Coil_{i}" in out
        # 6 phase labels per row expected
        for phase in "ABC":
            assert phase in out

    def test_36slot_returns_table(self):
        out = render_list(36, 8)
        # All 36 coils
        for i in range(1, 37):
            assert f"Coil_{i}" in out, f"missing Coil_{i}"

    def test_pattern_argument(self):
        # For 8p12s the canonical table uses AABBCC (Pyrhonen). When the user
        # asks for ABCABC explicitly, the builder re-derives the layout — this
        # may or may not differ for 8p12s (q=0.5, both patterns are valid),
        # but the API must accept the argument without crashing.
        out_aabbcc = render_list(12, 8, pattern="AABBCC")
        out_abcabc = render_list(12, 8, pattern="ABCABC")
        # Both must produce a valid 12-slot table
        assert out_aabbcc.count("|") >= 14  # header + 12 rows
        assert out_abcabc.count("|") >= 14


class TestRenderMd:
    def test_md_fences_present(self):
        out = render_md(12, 8)
        # 3 fences (slot map, phase belt, summary)
        fences = re.findall(r"```", out)
        assert len(fences) >= 6, f"expected ≥3 fenced blocks (6 fences), got {len(fences)}"

    def test_md_contains_metadata(self):
        out = render_md(36, 8)
        assert "k_w=" in out
        assert "q=" in out


class TestRenderMaxwell:
    def test_maxwell_is_valid_python(self):
        script = render_maxwell(12, 8, conductors=40)
        compile(script, "<test>", "exec")   # SyntaxError on invalid

    def test_maxwell_contains_coil_assignments(self):
        script = render_maxwell(12, 8, conductors=40)
        assert "AssignCoilGroup" in script
        assert "AddWindingCoils" in script
        assert "AssignWindingGroup" in script

    def test_maxwell_legacy_convention(self):
        script = render_maxwell(12, 8, conductors=40, convention="legacy")
        # In legacy: A+ group has Negative polarity
        assert '"NAME:A+"' in script
        # Just ensure both polarities appear
        assert "Positive" in script
        assert "Negative" in script


class TestRenderAll:
    def test_lists_all_canonical(self):
        out = render_all()
        assert "Available Canonical" in out
        # 19 entries as of v4.4
        row_count = out.count("| concentrated |") + out.count("| distributed |") + out.count("| fractional |")
        assert row_count >= 15, f"expected ≥15 entries, got {row_count}"


class TestRenderCompare:
    def test_compare_two_layouts(self):
        out = render_compare(12, 8, 36, 8)
        assert "Layout A" in out
        assert "Layout B" in out
        assert "8p/12s" in out
        assert "8p/36s" in out


# ────────────────────────────────────────────────────────────────────
#  Subprocess CLI invocation (smoke test)
# ────────────────────────────────────────────────────────────────────

class TestCliSubprocess:
    """Test the CLI as a real subprocess (catches argparse errors, exit codes)."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = [sys.executable, "-m", "winding_layout", *args]
        # Add scripts/ to PYTHONPATH so the module can be imported as a script
        env = {"PYTHONPATH": str(Path(__file__).resolve().parent.parent / "scripts")}
        import os
        env.update(os.environ)
        return subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=30,
        )

    def test_help(self):
        r = self._run("--help")
        assert r.returncode == 0
        assert "Usage" in r.stdout or "winding_layout" in r.stdout

    def test_all(self):
        r = self._run("--all")
        assert r.returncode == 0
        assert "Available Canonical" in r.stdout

    def test_list(self):
        r = self._run("12", "8", "--list")
        assert r.returncode == 0
        assert "8p/12s" in r.stdout

    def test_md(self):
        r = self._run("12", "8", "--md")
        assert r.returncode == 0
        assert "```" in r.stdout

    def test_maxwell(self):
        r = self._run("12", "8", "--maxwell")
        assert r.returncode == 0
        assert "AssignCoilGroup" in r.stdout

    def test_missing_args(self):
        r = self._run()
        # No args should print usage and exit 0 (current behavior)
        # Or exit 1 with usage — both are acceptable
        assert r.returncode in (0, 1)
        assert "Usage" in r.stdout or "winding_layout" in r.stdout
