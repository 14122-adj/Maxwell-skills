#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_winding_layouts.py — thin wrapper that re-exports the pytest test suite
as a standalone CLI for users who don't have pytest installed.

For the canonical test entry point, use:
    pytest tests/test_winding_layouts.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the tests/ module importable
_TESTS_DIR = Path(__file__).resolve().parent.parent / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from test_winding_layouts import main   # noqa: E402  (after sys.path manipulation)


if __name__ == "__main__":
    sys.exit(main())
