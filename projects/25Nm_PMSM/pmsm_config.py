"""
25N·m PMSM Motor Configuration — Design B (Compact)
All geometric and electromagnetic parameters for Maxwell automation.
"""

# ============================================================
# Motor Specifications
# ============================================================
RATED_TORQUE_NM = 25.0
RATED_SPEED_RPM = 1500
RATED_POWER_KW = 3.93
DC_BUS_VOLTAGE_V = 537.0        # 380V AC × √2
RATED_FREQUENCY_HZ = 100.0      # f = p × n / 60 = 4 × 1500 / 60
PHASES = 3
POLE_PAIRS = 4
POLES = 8
SLOTS = 12

# ============================================================
# Geometry (mm) — Design B
# ============================================================
STATOR_OD_MM = 150.0
STATOR_ID_MM = 93.0
ROTOR_OD_MM = 91.65
ROTOR_ID_MM = 30.0              # shaft
AIRGAP_MM = 0.675
STACK_LENGTH_MM = 160.0
TOOTH_WIDTH_MM = 10.48
YOKE_THICKNESS_MM = 7.86
SLOT_AREA_MM2 = 231.6
SPLIT_RATIO = 0.62              # Dsi / Dso

# Slot geometry (parallel-sided) —— M0–M6 基线口径，保留供 S7/S8/S9 冻结分析复现
SLOT_OPENING_MM = 2.5           # bs0
SLOT_WEDGE_DEPTH_MM = 1.5       # hs1
SLOT_BODY_WIDTH_MM = 9.5        # bs2
SLOT_BODY_DEPTH_MM = 18.0       # hs3

# ============================================================
# M8 梨形槽（表 2，2026-11-14 用户指定）—— FEA 齿槽优化的当前几何
# ============================================================
# 口径：Hs2 按「定子内径 → 槽底**最底端**」的总深理解（docs/PEAR_SLOT_SPEC.md §2）。
# 若改口为「内径 → 圆心」，则 x3=r_bore+Hs2、x4=x3+Rs，轭部 16.0 → 11.25 mm。
SLOT_TYPE = "pear"
SLOT_PEAR_BS0_MM = 0.8          # 槽口宽
SLOT_PEAR_HS0_MM = 1.5          # 窄颈高
SLOT_PEAR_HS1_MM = 1.8          # 斜肩高
SLOT_PEAR_HS2_MM = 12.5         # 槽深（到槽底最底端）
SLOT_PEAR_BS1_MM = 6.0          # 肩部宽
SLOT_PEAR_BS2_MM = 9.5          # 槽底直径（半圆底 Rs = 4.75）
SLOT_PEAR_RS_MM = 4.75

# 派生（与 scripts/slot_profile.py 同源，误差 <1e-3 mm²）
SLOT_PEAR_X0_MM = STATOR_ID_MM / 2 - 0.2      # 46.3（槽口压进内孔 0.2）
SLOT_PEAR_X1_MM = STATOR_ID_MM / 2 + SLOT_PEAR_HS0_MM            # 48.0
SLOT_PEAR_X2_MM = STATOR_ID_MM / 2 + SLOT_PEAR_HS0_MM + SLOT_PEAR_HS1_MM   # 49.8
SLOT_PEAR_X3_MM = STATOR_ID_MM / 2 + SLOT_PEAR_HS2_MM - SLOT_PEAR_RS_MM    # 54.25
SLOT_PEAR_X4_MM = STATOR_ID_MM / 2 + SLOT_PEAR_HS2_MM            # 59.0
SLOT_PEAR_YOKE_MM = STATOR_OD_MM / 2 - SLOT_PEAR_X4_MM           # 16.0
SLOT_PEAR_AREA_MM2 = 93.03      # 颈 1.36 + 斜肩 13.95 + 直身 42.28 + 半圆 35.44
SLOT_PEAR_AREA_EFF_MM2 = SLOT_PEAR_AREA_MM2 - 0.2 * SLOT_PEAR_BS0_MM  # 92.87（环带实切）
COIL_AREA_MM2 = 71.9            # 槽形 0.88 内缩（面积比 0.7744）

# PM geometry
PM_THICKNESS_MM = 1.95
PM_POLE_ARC = 0.87              # pole_arc / pole_pitch

# Derived
TAU_POLE_MM = 3.14159 * STATOR_ID_MM / POLES     # pole pitch
TAU_SLOT_MM = 3.14159 * STATOR_ID_MM / SLOTS     # slot pitch
BAND_RADIUS_MM = (ROTOR_OD_MM + STATOR_ID_MM) / 2.0  # = 92.325

# ============================================================
# Materials
# ============================================================
STEEL_MATERIAL = "M270-35A"     # 0.35mm silicon steel
PM_MATERIAL = "N35"             # NdFeB
CONDUCTOR_MATERIAL = "copper"
SHAFT_MATERIAL = "steel_stainless"
AIRGAP_MATERIAL = "vacuum"

# PM properties (N35 @ 20°C)
PM_BR_T = 1.17
PM_HC_KAM = 890
PM_MUR = 1.05
PM_MAX_TEMP_C = 80

# ============================================================
# Winding (8p12s concentrated)
# ============================================================
WINDING_KW = 0.933
TURNS_PER_PHASE = 81
CONDUCTORS_PER_SLOT = 40
WIRE_AWG = 15
WIRE_DIAMETER_MM = 1.450
WIRE_AREA_MM2 = 1.652
SLOT_FILL_FACTOR = 0.40
# M8 梨形槽：40 根 Ø1.45 的净铜面积 / 槽面积 = 66.05 / 93.03 = 0.710（≤0.78，线径不必改）
SLOT_FILL_PEAR = CONDUCTORS_PER_SLOT * WIRE_AREA_MM2 / SLOT_PEAR_AREA_MM2

# Winding layout (8p12s, double-layer concentrated)
# Slot:  1   2   3   4   5   6   7   8   9  10  11  12
# Upper: A+  C-  B+  A-  C+  B-  A+  C-  B+  A-  C+  B-
# Lower: A+  C-  B+  A-  C+  B-  A+  C-  B+  A-  C+  B-
WINDING_LAYOUT = {
    1: ("A+", "A+"), 2: ("C-", "C-"), 3: ("B+", "B+"),
    4: ("A-", "A-"), 5: ("C+", "C+"), 6: ("B-", "B-"),
    7: ("A+", "A+"), 8: ("C-", "C-"), 9: ("B+", "B+"),
    10: ("A-", "A-"), 11: ("C+", "C+"), 12: ("B-", "B-"),
}

# ============================================================
# Electrical Parameters
# ============================================================
RATED_CURRENT_RMS_A = 9.89
RATED_CURRENT_PEAK_A = 14.0
BACK_EMF_RMS_V = 132.4
CURRENT_DENSITY_AMM2 = 6.82
ELECTRIC_LOADING_AM = 8226

# ============================================================
# Performance (analytical estimates)
# ============================================================
EFFICIENCY_PCT = 94.0
COPPER_LOSS_W = 148.0
IRON_LOSS_W = 25.8
MECHANICAL_LOSS_W = 58.9
STRAY_LOSS_W = 19.6
TOTAL_LOSS_W = 252.3

# ============================================================
# Simulation Parameters
# ============================================================
# Transient solver
SIM_STOP_TIME_S = 0.02          # 2 electrical cycles = 2/100 Hz
SIM_TIME_STEP_S = 5.0e-5        # 1/(100×200) = fine
SIM_SAVE_FIELDS = True

# Mesh refinement
MESH_AIRGAP_LENGTH_MM = 0.1     # max element in airgap
MESH_TOOTH_LENGTH_MM = 1.5
MESH_PM_LENGTH_MM = 0.5
MESH_YOKE_LENGTH_MM = 3.0

# Overload
OVERLOAD_CURRENT_MULT = 2.0     # 2x rated current

# Demagnetization
DEMAG_TEMP_C = 150.0            # worst-case PM temperature
DEMAG_B_MIN_THRESHOLD_T = 0.2   # minimum B in PM to avoid irreversible demag

# ============================================================
# Project Paths
# ============================================================
PROJECT_NAME = "Motor_25Nm_SPMSM"
PROJECT_DIR = "D:/Maxwell_Projects/"
DESIGN_NAME = "SPMSM_8p12s"
EXPORT_DIR = "D:/桌面/maxwell-motor-25Nm/results/"
