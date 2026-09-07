# ANSYS Maxwell Motor Design — Simulation Report

## 25N·m PMSM (8-Pole 12-Slot SPMSM) — Design B (Compact)

**Date:** 2026-06-17  
**Design:** OD=150mm, L=160mm, Airgap=0.675mm  
**Motor Type:** Surface-Mounted Permanent Magnet Synchronous Motor (SPMSM)

---

## 1. Motor Specifications

| Parameter | Value |
|-----------|-------|
| Rated Torque | 25.0 N·m |
| Rated Speed | 1500 rpm |
| Rated Power | 3.93 kW |
| DC Bus Voltage | 537 V (380V AC × √2) |
| Electrical Frequency | 100 Hz |
| Phases | 3 |
| Poles / Slots | 8 / 12 |

---

## 2. Geometry Summary

| Parameter | Value |
|-----------|-------|
| Stator OD | 150.0 mm |
| Stator ID | 93.0 mm |
| Rotor OD | 91.65 mm |
| Shaft OD | 30.0 mm |
| Airgap | 0.675 mm |
| Stack Length | 160.0 mm |
| Tooth Width | 10.48 mm |
| Yoke Thickness | 7.86 mm |
| Split Ratio | 0.62 |
| Pole Arc | 0.87 |

---

## 3. Materials

| Component | Material | Key Properties |
|-----------|----------|----------------|
| Stator/Rotor Core | M270-35A (0.35mm) | Bsat=1.65T, Fe loss=2.70W/kg@1.5T/50Hz |
| Permanent Magnet | N35 NdFeB | Br=1.17T, Hc=890kA/m, mur=1.05 |
| Conductor | Copper (AWG15) | Ø1.450mm, A=1.652mm² |
| Shaft | AISI 4140 Steel | — |

---

## 4. Winding Data

| Parameter | Value |
|-----------|-------|
| Winding Type | Concentrated (Fractional-Slot) |
| Winding Factor | 0.933 |
| Turns/Phase | 81 |
| Conductors/Slot | 40 |
| Wire Gauge | AWG15 (Ø1.450mm) |
| Slot Fill Factor | 0.40 (40%) |
| Connection | Star (Y) |

### Winding Layout (8p12s)

```
Slot:   1    2    3    4    5    6    7    8    9   10   11   12
Phase:  A+   C-   B+   A-   C+   B-   A+   C-   B+   A-   C+   B-
```

---

## 5. Simulation Results

### 5.1 No-Load Back-EMF

| Parameter | Analytical | FEA | Status |
|-----------|-----------|-----|--------|
| Back-EMF RMS | 132.4 V | _pending_ | ⏳ |
| THD | < 5% | _pending_ | ⏳ |
| Cogging Torque | < 5% rated | _pending_ | ⏳ |

**Expected:** Sinusoidal waveform, THD < 5% for concentrated winding.

### 5.2 Rated Load

| Parameter | Target | Analytical | FEA | Status |
|-----------|--------|-----------|-----|--------|
| Average Torque | 25.0 N·m | 25.0 | _pending_ | ⏳ |
| Torque Ripple | < 10% | — | _pending_ | ⏳ |
| Current RMS | 9.89 A | 9.89 | _pending_ | ⏳ |
| Efficiency | ≥ 93% | 94.0% | _pending_ | ⏳ |
| Power Factor | ≥ 0.85 | — | _pending_ | ⏳ |

### 5.3 Airgap Flux Density

| Parameter | Target | Analytical | FEA | Status |
|-----------|--------|-----------|-----|--------|
| Bg Peak | 0.7-0.85 T | 0.775 T | _pending_ | ⏳ |
| Bg Fundamental | — | — | _pending_ | ⏳ |
| 3rd Harmonic | < 15% | — | _pending_ | ⏳ |
| THD_B | — | — | _pending_ | ⏳ |

### 5.4 Overload (2× Current)

| Parameter | Target | FEA | Status |
|-----------|--------|-----|--------|
| Overload Torque | ≥ 1.8× rated | _pending_ | ⏳ |
| Peak Flux Density | < Bsat (1.65T) | _pending_ | ⏳ |

### 5.5 Iron Loss (Bertotti)

| Component | Analytical | FEA | Status |
|-----------|-----------|-----|--------|
| Stator Tooth Loss | — | _pending_ | ⏳ |
| Stator Yoke Loss | — | _pending_ | ⏳ |
| Rotor Loss | — | _pending_ | ⏳ |
| Total Iron Loss | 25.8 W | _pending_ | ⏳ |

### 5.6 PM Eddy Current Loss

| Parameter | FEA | Status |
|-----------|-----|--------|
| PM Loss (no segmentation) | _pending_ | ⏳ |
| PM Loss (axial segmentation) | _pending_ | ⏳ |

### 5.7 Inductance (Ld/Lq)

| Parameter | SPMSM Expected | FEA | Status |
|-----------|---------------|-----|--------|
| Ld | ≈ Lq | _pending_ | ⏳ |
| Lq | ≈ Ld | _pending_ | ⏳ |
| Saliency Ratio | ≈ 1.0 | _pending_ | ⏳ |

### 5.8 Demagnetization

| Test Condition | B_min Threshold | FEA | Status |
|---------------|-----------------|-----|--------|
| 150°C, 3-phase short | > 0.2 T | _pending_ | ⏳ |
| Safety Factor | ≥ 1.5 | _pending_ | ⏳ |

### 5.9 NVH Quick Scan

| Parameter | Target | FEA | Status |
|-----------|--------|-----|--------|
| Minimum Force Order | ≥ 4 | 4 (8p12s) | ✅ |
| Resonance Risk | ±20% of f_n | _pending_ | ⏳ |

---

## 6. Performance Summary

| Metric | Target | Analytical | FEA | Status |
|--------|--------|-----------|-----|--------|
| Torque | 25.0 N·m | 25.0 | — | — |
| Efficiency | ≥ 93% | 94.0% | — | — |
| Torque Ripple | < 10% | — | — | — |
| Cogging | < 5% | — | — | — |
| Iron Saturation | < 1.7T (teeth) | — | — | — |
| PM Demag Safety | ≥ 1.5 | — | — | — |

---

## 7. Cost Estimate

| Component | Mass (kg) | Cost (¥) |
|-----------|----------|---------|
| NdFeB N35 Magnets | 0.120 | 42 |
| Lamination Steel | 0.850 | 15 |
| Copper Wire | 0.180 | 14 |
| **Total (active materials)** | **1.150** | **~71** |

---

## 8. Conclusions & Recommendations

_To be completed after FEA results._

---

## Appendix: File Manifest

| File | Description |
|------|-------------|
| `scripts/motor_config.py` | Central configuration — all design parameters |
| `scripts/01_build_geometry.py` | Stator/rotor/PM geometry creation |
| `scripts/02_materials_and_excitation.py` | Material assignment, winding, mesh |
| `scripts/03_no_load_bemf.py` | No-load back-EMF simulation |
| `scripts/04_rated_load.py` | Rated load torque simulation |
| `scripts/05_airgap_flux_density.py` | Airgap Bg spatial analysis |
| `scripts/06_overload.py` | 2× overload capability test |
| `scripts/07_iron_loss.py` | Bertotti iron loss analysis |
| `scripts/08_pm_eddy_loss.py` | PM eddy current loss |
| `scripts/09_inductance.py` | Ld/Lq frozen permeability |
| `scripts/10_demagnetization.py` | PM demag safety check |
| `scripts/11_nvh_scan.py` | Radial force harmonics |
| `scripts/run_all_simulations.py` | Master orchestrator |
| `references/motor_design_guide.md` | Theory, formulas, materials |
| `references/mcp_tools_reference.md` | MCP tool catalog |
| `references/simulation_configs.md` | Simulation configurations |
