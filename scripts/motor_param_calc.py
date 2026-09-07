#!/usr/bin/env python3
"""
Motor Parameter Calculator — Standalone Analytical Design Tool.

Computes a complete electromagnetic parameter set for PM synchronous motors
from high-level specifications. No ANSYS Maxwell dependency required.

Usage:
    python motor_param_calc.py --power 500 --speed 3000 --voltage 48 \\
        --poles 8 --slots 12 --outer_dia 80 --length 50

Output: JSON parameter table to stdout (ready for MCP tool consumption)
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional


# ──── Physical Constants ────
MU0 = 4e-7 * math.pi        # Vacuum permeability (H/m)
RHO_CU_20C = 1.68e-8        # Copper resistivity at 20°C (Ω·m)
ALPHA_CU = 0.00393           # Copper temperature coefficient (1/K)

# ──── Material Defaults ────
DEFAULT_PM_BR = 1.17          # N35 Br at 20°C (T)
DEFAULT_PM_MUR = 1.05         # PM recoil permeability
DEFAULT_STEEL_BSAT = 1.65     # Lamination saturation B (T)
DEFAULT_STEEL_KFE = 0.95      # Stacking factor


@dataclass
class MotorSpec:
    """Input specification from user."""
    motor_type: str = "SPMSM"
    rated_power_W: float = 500
    rated_speed_rpm: float = 3000
    dc_voltage_V: float = 48
    phases: int = 3
    pole_pairs: int = 4          # p = 4 → 8 poles
    slots: int = 12               # Q
    outer_diameter_mm: float = 80
    stack_length_mm: float = 50
    airgap_mm: Optional[float] = None
    pm_thickness_mm: Optional[float] = None
    efficiency_target: float = 0.88
    cooling_method: str = "natural"
    max_current_density: float = 6.0
    min_slot_fill: float = 0.30
    max_slot_fill: float = 0.50
    winding_temp_C: float = 80     # operating temperature for resistance calc
    magnet_temp_C: float = 80      # operating temperature for Br derating
    magnet_br_20C: float = 1.17    # N35
    magnet_Hc_kAm: float = 890
    magnet_mur: float = 1.05
    steel_bsat: float = 1.65        # M270-35A
    stacking_factor: float = 0.95
    pm_pole_arc: float = 0.87       # αp
    slot_opening_mm: float = 2.5    # bs0
    target_modulation_index: float = 0.85
    n_airgap_layers: int = 3        # mesh layers across airgap


@dataclass
class MotorParams:
    """Computed motor parameters."""
    # Geometric
    Dso_mm: float = 0            # Stator outer diameter
    Dsi_mm: float = 0            # Stator inner diameter (airgap side)
    Dro_mm: float = 0            # Rotor outer diameter
    delta_mm: float = 0          # Airgap length
    La_mm: float = 0             # Stack length
    tau_p_mm: float = 0          # Pole pitch
    tau_s_mm: float = 0          # Slot pitch
    slot_area_mm2: float = 0     # Net slot area (estimated)
    hm_mm: float = 0             # PM thickness
    wt_mm: float = 0             # Tooth width
    hy_mm: float = 0             # Stator yoke thickness

    # Electromagnetic
    Bg_T: float = 0              # Airgap flux density (peak)
    Bg_avg_T: float = 0          # Airgap flux density (average)
    phi_pm_Wb: float = 0         # PM flux per pole
    lambda_pm_Wb: float = 0      # PM flux linkage
    E_ph_rms_V: float = 0        # Back-EMF per phase (rms)
    f_e_Hz: float = 0            # Electrical frequency

    # Winding
    Nph: int = 0                 # Turns per phase
    Ns: int = 0                  # Conductors per slot
    Kw: float = 0                # Winding factor
    A_wire_mm2: float = 0        # Wire cross-sectional area
    d_wire_mm: float = 0         # Wire diameter
    kf: float = 0                # Slot fill factor

    # Performance
    I_rms_A: float = 0           # Rated current (rms)
    J_Amm2: float = 0            # Current density
    T_avg_Nm: float = 0          # Average torque
    P_cu_W: float = 0            # Copper loss
    P_fe_est_W: float = 0        # Iron loss (estimate)
    eta_est: float = 0           # Estimated efficiency
    A_electric_Am: float = 0     # Electric loading
    AJ_product: float = 0        # Thermal indicator

    # Checks
    split_ratio: float = 0
    hm_delta_ratio: float = 0
    n_parallel: int = 1
    wire_awg: int = 22
    checks: dict = field(default_factory=dict)


def compute_parameters(spec: MotorSpec) -> MotorParams:
    """Main calculation routine."""
    p = MotorParams()

    # ── Step 1: Airgap default ──
    if spec.airgap_mm is not None:
        p.delta_mm = spec.airgap_mm
    else:
        # Engineering rule: δ = 0.3 + D/400 (mm), clamp to practical limits
        p.delta_mm = max(0.35, min(1.2, 0.3 + spec.outer_diameter_mm / 400.0))

    # ── Step 2: Split ratio ──
    # Target Dsi/Dso ≈ 0.60 for PM machines
    p.split_ratio = 0.60
    p.Dso_mm = spec.outer_diameter_mm
    p.Dsi_mm = p.Dso_mm * p.split_ratio
    p.Dro_mm = p.Dsi_mm - 2.0 * p.delta_mm
    p.La_mm = spec.stack_length_mm

    # ── Step 3: PM thickness (magnetic circuit + steel mmf drop) ──
    if spec.pm_thickness_mm is not None:
        p.hm_mm = spec.pm_thickness_mm
    else:
        # Derate Br for operating temperature
        T_diff = spec.magnet_temp_C - 20
        Br_T = spec.magnet_br_20C * (1 + 0.0012 * (-T_diff))

        # Target Bg based on motor class
        if spec.outer_diameter_mm < 100:
            Bg_target = 0.72  # small motors: lower to manage losses
        elif spec.outer_diameter_mm < 200:
            Bg_target = 0.78
        else:
            Bg_target = 0.82

        # Magnetic circuit: Bg = Br / (1 + μr × Cφ × k_sat × δ/hm)
        # Cφ = αp (pole-arc) accounting for fringing and leakage
        # k_sat = 1.3 steel mmf drop factor (iron reluctance is 30% of gap)
        C_phi = spec.pm_pole_arc / 1.05  # leakage derates effective pole arc
        k_sat = 1.30

        if Br_T > Bg_target:
            hm_delta_ratio = spec.magnet_mur * C_phi * k_sat / (Br_T / Bg_target - 1.0)
            # Clamp to practical range
            hm_delta_ratio = max(3.0, min(10.0, hm_delta_ratio))
            p.hm_mm = p.delta_mm * hm_delta_ratio
        else:
            # Fallback: force 4:1 ratio
            p.hm_mm = p.delta_mm * 4.0

    p.hm_delta_ratio = p.hm_mm / p.delta_mm

    # ── Step 4: Pole pitch ──
    p.tau_p_mm = math.pi * p.Dsi_mm / (2.0 * spec.pole_pairs)
    p.tau_s_mm = math.pi * p.Dsi_mm / spec.slots

    # ── Step 5: Flux density ──
    # Bg ≈ Br(T) / (1 + μr × δ / hm × k_leakage)
    k_leakage = 1.10
    T_diff = spec.magnet_temp_C - 20
    Br_T = spec.magnet_br_20C * (1 + 0.0012 * (-T_diff))
    p.Bg_T = Br_T / (1 + spec.magnet_mur * p.delta_mm / p.hm_mm * k_leakage)
    p.Bg_avg_T = p.Bg_T * spec.pm_pole_arc  # average over pole pitch

    # ── Step 6: Flux per pole ──
    p.phi_pm_Wb = p.Bg_avg_T * p.tau_p_mm / 1000.0 * spec.stack_length_mm / 1000.0

    # ── Step 7: Electrical frequency ──
    p.f_e_Hz = spec.pole_pairs * spec.rated_speed_rpm / 60.0

    # ── Step 8: Winding factor ──
    p.Kw = compute_winding_factor(spec.slots, spec.pole_pairs * 2)

    # ── Step 9: Turns per phase ──
    # E_ph_rms ≈ √2 × π × f × Nph × Kw × φ_pm
    # Target: E_ph_rms ≈ V_dc / (2 × √3) × modulation_index
    E_target = spec.dc_voltage_V / (2.0 * math.sqrt(3)) * spec.target_modulation_index
    Nph_float = E_target / (math.sqrt(2) * math.pi * p.f_e_Hz * p.Kw * p.phi_pm_Wb)
    p.Nph = max(1, round(Nph_float))

    p.E_ph_rms_V = math.sqrt(2) * math.pi * p.f_e_Hz * p.Nph * p.Kw * p.phi_pm_Wb

    # ── Step 10: PM flux linkage ──
    p.lambda_pm_Wb = math.sqrt(2) * p.E_ph_rms_V / (2.0 * math.pi * p.f_e_Hz)

    # ── Step 11: Torque ──
    omega_rads = spec.rated_speed_rpm * 2.0 * math.pi / 60.0
    T_target = spec.rated_power_W / omega_rads
    # T = (3/2) × p × λ_pm × I_q  (dq-frame, amplitude-invariant transform)
    # I_q = peak phase current; I_phase_rms = I_q / √2
    I_q_needed = T_target / (1.5 * spec.pole_pairs * p.lambda_pm_Wb)
    p.I_rms_A = I_q_needed / math.sqrt(2)

    p.T_avg_Nm = 1.5 * spec.pole_pairs * p.lambda_pm_Wb * I_q_needed

    # ── Step 12: Conductors per slot ──
    # Nph = (N_slots × N_conductors_per_slot) / (phases × parallel_paths)
    # For double-layer: Ns = 2 × Nph × phases / Q
    parallel_paths = 1
    p.Ns = round(2 * p.Nph * spec.phases / (spec.slots * parallel_paths))

    # ── Step 13: Wire sizing ──
    p.A_wire_mm2 = p.I_rms_A / spec.max_current_density

    # Select nearest standard AWG (largest that fits, or use parallel strands)
    awg_table = [
        (12, 2.053, 3.309), (13, 1.828, 2.624), (14, 1.628, 2.081),
        (15, 1.450, 1.652), (16, 1.291, 1.309), (17, 1.150, 1.038),
        (18, 1.024, 0.823), (19, 0.912, 0.653), (20, 0.812, 0.518),
        (21, 0.723, 0.410), (22, 0.644, 0.326), (23, 0.573, 0.258),
        (24, 0.511, 0.205), (25, 0.455, 0.162), (26, 0.405, 0.129),
    ]

    best_awg = None
    best_d = None
    best_area = None
    n_parallel = 1

    # Try single strand first
    for awg, d, area in awg_table:
        if area >= p.A_wire_mm2:
            if best_awg is None or area < best_area:
                best_awg, best_d, best_area = awg, d, area

    # If no single wire can handle the current, use parallel strands
    if best_awg is None:
        # Use AWG 17 (common max for hand winding) with parallel strands
        awg17_area = 1.038  # mm²
        n_parallel = max(1, round(p.A_wire_mm2 / awg17_area))
        best_awg = 17
        best_d = 1.150
        best_area = awg17_area
        if n_parallel > 4:
            # Fall back to AWG 15 for fewer strands
            n_parallel = max(1, round(p.A_wire_mm2 / 1.652))
            best_awg = 15
            best_d = 1.450
            best_area = 1.652

    p.d_wire_mm = best_d
    p.n_parallel = n_parallel
    p.wire_awg = best_awg
    p.A_wire_mm2 = best_area * n_parallel  # effective copper area

    # ── Step 14: Current density ──
    p.J_Amm2 = p.I_rms_A / p.A_wire_mm2

    # ── Step 15: Slot area and fill factor ──
    # Flux-based tooth width: wt = Bg_avg × τs / (Bsat × k_fe)
    p.wt_mm = p.Bg_avg_T * p.tau_s_mm / (spec.steel_bsat * spec.stacking_factor)
    p.wt_mm = max(1.5, min(p.tau_s_mm * 0.7, p.wt_mm))
    slot_width_mm = p.tau_s_mm - p.wt_mm

    # Yoke thickness: hy = Bg_avg × τp / (2 × Bsat × k_fe)
    p.hy_mm = p.Bg_avg_T * p.tau_p_mm / (2.0 * spec.steel_bsat * spec.stacking_factor)
    p.hy_mm = max(2.0, p.hy_mm)

    total_radial = (p.Dso_mm - p.Dsi_mm) / 2.0
    slot_depth_mm = total_radial - p.hy_mm - 1.0

    liner_factor = 0.82 if slot_width_mm < 8 else 0.85
    net_slot_area = slot_width_mm * slot_depth_mm * liner_factor
    p.slot_area_mm2 = max(1.0, net_slot_area)

    insulation_build = 1.06 if p.d_wire_mm < 0.6 else 1.04
    wire_area_gross = math.pi * ((p.d_wire_mm * insulation_build) / 2.0) ** 2
    # Total copper area: n_parallel strands × Ns conductors
    p.kf = (p.Ns * n_parallel * wire_area_gross) / net_slot_area if net_slot_area > 0 else 1.0

    # ── Step 16: Electric loading ──
    p.A_electric_Am = (spec.phases * p.Nph * p.I_rms_A) / (math.pi * p.Dsi_mm / 1000.0)

    # ── Step 17: AJ product (A²/cm·mm²) — thermal stress indicator
    # A in A/cm, J in A/mm²
    A_Acm = p.A_electric_Am / 100.0
    p.AJ_product = A_Acm * p.J_Amm2
    # p.AJ_product in conventional units: hundreds of A²/cm·mm²
    # < 1500 natural cooling, < 3000 forced, < 8000 water

    # ── Step 18: Loss estimation ──
    # Copper loss @ operating temperature
    R_cu_20C = RHO_CU_20C * (p.Nph * (2 * p.La_mm / 1000.0 + p.tau_p_mm / 1000.0)) / (p.A_wire_mm2 * 1e-6)
    R_cu_T = R_cu_20C * (1 + ALPHA_CU * (spec.winding_temp_C - 20))
    p.P_cu_W = spec.phases * p.I_rms_A ** 2 * R_cu_T

    # Iron loss (simplified Bertotti @ 50Hz, 1.5T → scale by freq and B)
    p.fe_ref_W_kg = 2.70  # M270-35A @ 50Hz, 1.5T
    stator_mass_kg = (math.pi * ((p.Dso_mm / 2) ** 2 - (p.Dsi_mm / 2) ** 2) * p.La_mm) / 1e6 * 7.65 * spec.stacking_factor
    # Scale: P_fe ∝ f^1.5 × B^2 (rough)
    p.P_fe_est_W = p.fe_ref_W_kg * stator_mass_kg * (p.f_e_Hz / 50) ** 1.5 * (p.Bg_T / 1.5) ** 2

    # ── Step 19: Efficiency ──
    P_out = spec.rated_power_W
    # Stray load loss ≈ 0.5% of rated power (IEC 60034-2-1)
    P_stray = 0.005 * P_out
    # Mechanical loss (bearing + windage) ≈ 1-2% of rated power for small motors
    P_mech = 0.015 * P_out
    P_loss = p.P_cu_W + p.P_fe_est_W + P_stray + P_mech
    p.eta_est = P_out / (P_out + P_loss) if (P_out + P_loss) > 0 else 0

    # ── Step 20: Validation checks ──
    p.checks = {
        "airgap_range_ok": 0.35 <= p.delta_mm <= 2.0,
        "Bg_ok": 0.55 <= p.Bg_T <= 1.0,
        "kf_ok": spec.min_slot_fill <= p.kf <= spec.max_slot_fill,
        "J_ok": 2.0 <= p.J_Amm2 <= spec.max_current_density * 1.2,
        "AJ_ok": p.AJ_product <= 8000.0,  # conventional units
        "split_ratio_ok": 0.50 <= p.split_ratio <= 0.72,
        "hm_delta_ok": 2.5 <= p.hm_delta_ratio <= 12.0,
        "eta_ok": p.eta_est >= spec.efficiency_target,
        "hy_ok": p.hy_mm >= 1.5,  # yoke thickness > 1.5mm
        "wt_ok": p.wt_mm >= 1.2,  # tooth width > 1.2mm
    }

    return p


def compute_winding_factor(Q: int, poles_2p: int) -> float:
    """Compute fundamental winding factor for a given slot-pole combination.

    For concentrated fractional-slot windings (single-layer by default,
    multiplied by chording factor for double-layer).
    """
    # This table covers common combinations
    # kw = kd × kp where kd ≈ 1 for concentrated windings (q < 1)
    # and kp = sin(ν × π/2 × coil_span/pole_pitch)

    table = {
        (12, 8):  0.933,   # 8p12s
        (12, 10): 0.933,   # 10p12s
        (9, 8):   0.945,   # 8p9s
        (9, 10):  0.945,   # 10p9s
        (12, 4):  0.933,   # 4p12s (distributed)
        (6, 4):   0.866,   # 4p6s
        (6, 8):   0.866,   # 8p6s
        (24, 4):  0.966,   # 4p24s (overlapping)
        (18, 16): 0.945,   # 16p18s
        (36, 8):  0.960,   # 8p36s (distributed)
        (27, 24): 0.945,   # 24p27s
    }

    key = (Q, poles_2p)
    if key in table:
        return table[key]

    # Generic calculation for unknown combinations
    # q = Q / (poles_2p × phases)
    q = Q / (poles_2p * 3.0)
    if q >= 1:
        # Distributed winding
        alpha = math.pi * poles_2p / Q
        kd = math.sin(q * alpha / 2) / (q * math.sin(alpha / 2))
        # Full-pitch assumed
        kp = 1.0
        return kd * kp
    else:
        # Fractional-slot concentrated — approximate
        return 0.933  # Conservative default


def format_output(params: MotorParams, spec: MotorSpec) -> dict:
    """Format parameters as a JSON-serializable dictionary with checks."""
    checks_summary = {k: "PASS" if v else "FAIL" for k, v in params.checks.items()}
    all_pass = all(params.checks.values())

    return {
        "design_summary": {
            "all_checks_pass": all_pass,
            "checks": checks_summary,
        },
        "geometry": {
            "outer_diameter_mm": round(params.Dso_mm, 2),
            "inner_diameter_mm": round(params.Dsi_mm, 2),
            "rotor_diameter_mm": round(params.Dro_mm, 2),
            "airgap_mm": round(params.delta_mm, 3),
            "stack_length_mm": round(params.La_mm, 1),
            "pm_thickness_mm": round(params.hm_mm, 2),
            "pm_pole_arc": round(spec.pm_pole_arc, 2),
            "slot_opening_mm": round(spec.slot_opening_mm, 2),
            "tooth_width_mm": round(params.wt_mm, 2),
            "yoke_thickness_mm": round(params.hy_mm, 2),
            "slot_area_mm2_est": round(params.slot_area_mm2, 1),
            "split_ratio": round(params.split_ratio, 3),
        },
        "electromagnetic": {
            "Bg_peak_T": round(params.Bg_T, 3),
            "Bg_average_T": round(params.Bg_avg_T, 3),
            "phi_pm_per_pole_mWb": round(params.phi_pm_Wb * 1000, 3),
            "lambda_pm_mWb": round(params.lambda_pm_Wb * 1000, 3),
            "E_ph_rms_V": round(params.E_ph_rms_V, 2),
            "f_e_Hz": round(params.f_e_Hz, 1),
        },
        "winding": {
            "turns_per_phase": params.Nph,
            "conductors_per_slot": params.Ns,
            "winding_factor": round(params.Kw, 4),
            "wire_awg": params.wire_awg,
            "wire_diameter_mm": round(params.d_wire_mm, 3),
            "wire_area_mm2": round(params.A_wire_mm2, 3),
            "parallel_strands": params.n_parallel,
            "slot_fill_factor": round(params.kf, 3),
            "current_density_Amm2": round(params.J_Amm2, 2),
            "electric_loading_Am": round(params.A_electric_Am, 0),
            "AJ_product": round(params.AJ_product, 0),
        },
        "performance": {
            "rated_current_rms_A": round(params.I_rms_A, 2),
            "rated_current_peak_A": round(params.I_rms_A * math.sqrt(2), 2),
            "torque_Nm": round(params.T_avg_Nm, 3),
            "copper_loss_W": round(params.P_cu_W, 1),
            "iron_loss_est_W": round(params.P_fe_est_W, 1),
            "efficiency_est": round(params.eta_est * 100, 1),
        },
        "derived_ratios": {
            "hm_delta": round(params.hm_delta_ratio, 1),
            "airgap_diameter": round(params.delta_mm / params.Dsi_mm * 100, 3),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="PM Synchronous Motor Parameter Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -P 500 -n 3000 -V 48 -p 8 -q 12 -D 80 -L 50
  %(prog)s -P 3000 -n 1500 -V 380 -p 4 -q 36 -D 160 -L 120 --pm N38SH
  %(prog)s --power 750 --speed 6000 --voltage 300 --poles 8 --slots 12 --outer-dia 100 --length 60 --json
        """
    )
    parser.add_argument("-P", "--power", type=float, default=500, help="Rated power (W)")
    parser.add_argument("-n", "--speed", type=float, default=3000, help="Rated speed (rpm)")
    parser.add_argument("-V", "--voltage", type=float, default=48, help="DC bus voltage (V)")
    parser.add_argument("-p", "--poles", type=int, default=8, help="Number of poles")
    parser.add_argument("-q", "--slots", type=int, default=12, help="Number of slots")
    parser.add_argument("-D", "--outer-dia", type=float, default=80, help="Outer diameter (mm)")
    parser.add_argument("-L", "--length", type=float, default=50, help="Stack length (mm)")
    parser.add_argument("--airgap", type=float, default=None, help="Airgap (mm), auto if omitted")
    parser.add_argument("--pm-thickness", type=float, default=None, help="PM thickness (mm), auto if omitted")
    parser.add_argument("--pm", type=str, default="N35", choices=["N35", "N38SH", "N42SH", "N48SH", "SmCo26", "Ferrite"],
                        help="PM grade")
    parser.add_argument("--steel", type=str, default="M270-35A", help="Lamination grade")
    parser.add_argument("--efficiency", type=float, default=0.88, help="Target efficiency")
    parser.add_argument("--cooling", type=str, default="natural", choices=["natural", "forced_air", "water_jacket"])
    parser.add_argument("--winding-temp", type=float, default=80, help="Winding operating temp (°C)")
    parser.add_argument("--magnet-temp", type=float, default=80, help="Magnet operating temp (°C)")
    parser.add_argument("--pole-arc", type=float, default=0.87, help="Pole-arc coefficient")
    parser.add_argument("--json", action="store_true", help="Output JSON only (no comments)")
    parser.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON")

    args = parser.parse_args()

    # PM grade mapping
    pm_db = {
        "N35":    {"Br": 1.17, "Hc": 890},
        "N38SH":  {"Br": 1.24, "Hc": 930},
        "N42SH":  {"Br": 1.30, "Hc": 970},
        "N48SH":  {"Br": 1.39, "Hc": 1015},
        "SmCo26": {"Br": 1.05, "Hc": 756},
        "Ferrite": {"Br": 0.38, "Hc": 240},
    }

    # Cooling → max current density
    cooling_j = {
        "natural": 6.0,
        "forced_air": 8.0,
        "water_jacket": 12.0,
    }

    spec = MotorSpec(
        rated_power_W=args.power,
        rated_speed_rpm=args.speed,
        dc_voltage_V=args.voltage,
        pole_pairs=args.poles // 2,
        slots=args.slots,
        outer_diameter_mm=args.outer_dia,
        stack_length_mm=args.length,
        airgap_mm=args.airgap,
        pm_thickness_mm=args.pm_thickness,
        efficiency_target=args.efficiency,
        cooling_method=args.cooling,
        max_current_density=cooling_j.get(args.cooling, 6.0),
        winding_temp_C=args.winding_temp,
        magnet_temp_C=args.magnet_temp,
        magnet_br_20C=pm_db[args.pm]["Br"],
        magnet_Hc_kAm=pm_db[args.pm]["Hc"],
        pm_pole_arc=args.pole_arc,
    )

    params = compute_parameters(spec)
    output = format_output(params, spec)

    indent = 2 if args.pretty else None
    print(json.dumps(output, indent=indent, ensure_ascii=False))

    # Exit code: 0 = all checks pass, 1 = some checks fail
    if not output["design_summary"]["all_checks_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
