"""
ansys-maxwell-motor
===================

ANSYS Maxwell motor modeling + multiphysics MDAO orchestration skill.

Modules:
    pmsm_winding_builder  — Canonical winding layout generator (lookup-first)
    winding_layout        — CLI: look up slot-to-phase mapping for any pole-slot combo
    motor_config          — Central MotorConfig dataclass + slot/PM topology enums
    motor_param_calc      — Auto-fill missing motor design parameters
    motor_optimizer       — NSGA-II / PSO / Bayesian multi-objective optimization
    slot_builder          — Slot geometry generator (rectangular/pear/trapezoidal/round)
    pm_builder            — Permanent magnet topology builder (SPM/IPM_Flat/IPM_V/IPM_Spoke)
    maxwell_bridge        — Unified Maxwell MCP API bridge (71 tools + 15 wrappers)
    mcp_connector         — stdio MCP client (real Maxwell connection)
    mdao_orchestrator     — Multiphysics orchestration (electromagnetic-structural-thermal + IGBT)
    main                  — One-command model builder (MotorModelBuilder)

Entry points (after `pip install -e .`):
    maxwell-winding     → scripts.winding_layout:main
    maxwell-build       → scripts.main:main
    maxwell-test        → scripts.test_winding_layouts:main
"""

__version__ = "4.4.0"
__author__ = "Maxwell Skill Maintainers"
__license__ = "Unlicense (public domain)"
