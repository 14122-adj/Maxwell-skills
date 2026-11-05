#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_winding_layouts.py — standalone test / self-check CLI.

Source checkout (tests/ present): delegates to the full pytest-style suite in
tests/test_winding_layouts.py.

Installed wheel (tests/ is not shipped): runs a self-contained smoke check over
the canonical winding layouts, so `maxwell-test` works after `pip install .`.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _SCRIPTS_DIR.parent / "tests"


def _run_selfcheck() -> int:
    """Smoke-check the installed package without requiring tests/."""
    try:
        builder = importlib.import_module("scripts.pmsm_winding_builder")
    except ImportError:
        builder = importlib.import_module("pmsm_winding_builder")

    failures: list[str] = []
    for slots, poles in builder.CANONICAL_LAYOUTS:
        try:
            build = builder.WindingBuilder(slots=slots, poles=poles)
            winding = build.compute_winding()
            if not winding.slot_map:
                failures.append(f"{poles}p/{slots}s: empty slot map")
        except Exception as exc:
            failures.append(f"{poles}p/{slots}s: {type(exc).__name__}: {exc}")

    print(
        f"[{'OK' if not failures else 'FAIL'}] self-check: "
        f"{len(builder.CANONICAL_LAYOUTS)} layouts, {len(failures)} failure(s)"
    )
    for msg in failures:
        print("  -", msg)
    return 0 if not failures else 1


def main() -> int:
    if _TESTS_DIR.is_dir():
        # Insert scripts first, then tests, so tests/ ends up ahead of
        # scripts/ in sys.path (both define a `test_winding_layouts` module).
        for path in (_SCRIPTS_DIR, _TESTS_DIR):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
        from test_winding_layouts import main as _suite_main

        return int(_suite_main())
    return _run_selfcheck()


if __name__ == "__main__":
    sys.exit(main())
