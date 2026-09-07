# Motor Design Guide — Comprehensive Reference

## §1 Specification Template

```yaml
motor_spec:
  # Topology
  type: PMSM                    # PMSM | IPM | SPM | IM | SynRM | WFSM
  phases: 3
  poles: 8
  slots: 12
  winding_type: concentrated    # concentrated | distributed
  winding_layer: double         # single | double
  connection: wye               # wye | delta

  # Geometry (mm)
  stator_outer_diameter: 120.0
  stator_inner_diameter: 70.0
  rotor_outer_diameter: 68.0
  rotor_inner_diameter: 30.0
  stack_length: 80.0
  airgap_length: 1.0
  magnet_thickness: 3.5
  magnet_arc: 0.85              # pole-arc ratio
  slot_opening: 2.5
  slot_depth: 18.0
  tooth_width: 6.0
  back_iron_thickness: 7.0

  # Operating Points
  rated_speed_rpm: 3000
  max_speed_rpm: 9000
  rated_torque_nm: 5.0
  peak_torque_nm: 15.0
  dc_link_voltage_v: 400
  rated_current_arms: 8.0
  peak_current_arms: 24.0

  # Materials
  magnet_grade: N42SH
  lamination_grade: M270-35A
  winding_material: copper       # copper | aluminum
  wire_awg: 18

  # Limits
  max_current_density_am2: 8.0e6
  max_slot_fill_factor: 0.55
  max_electric_loading_am: 35000
  pm_max_temp_c: 150
  winding_max_temp_c: 155        # class F

  # Targets
  target_efficiency_pct: 93
  target_torque_ripple_pct: 5
  target_cogging_torque_pct: 2
  target_power_kw: 1.57
```

---

## §2 RMxprt Integration Workflow

### Step-by-step process

1. **Create RMxprt design**
   - Use `create_rmxprt_design(design_name, machine_type="PMSM")`

2. **Set specification**
   - Use `set_rmxprt_specification(spec_dict)` with the YAML spec above

3. **Run analytical calculation**
   - Use `rmxprt_analyze(design_name)`

4. **Review RMxprt outputs**
   - `get_rmxprt_output(design_name, quantity="all")`
   - Key outputs: Back-EMF constant, torque constant, slot fill, losses

5. **Create 2D Maxwell design from RMxprt**
   - Use `create_maxwell_2d_from_rmxprt(rmxprt_design, maxwell_design)`

6. **Refine with FEA**
   - Mesh refinement: `assign_mesh_operation(...)`
   - Add motion setup: `assign_band(...)`
   - Run FEA: `analyze_all()`

### Workflow diagram

```
Specification (YAML)
    │
    ▼
RMxprt Analysis ────► Validate: slot fill, AJ, Bg
    │                      │
    │ (pass)               │ (fail)
    ▼                      ▼
Create 2D Maxwell      Adjust geometry
    │                   ▲
    ▼                   │
FEA Refinement ────────┘
    │
    ▼
FEA Results → Post-processing → Report
```

---

## §3 Parameter Calculation Formulas

### 3.1 Airgap Flux Density

Peak airgap flux density (radial):

$$B_g = B_r \cdot \frac{1}{\frac{g_{eff}}{h_m} + \mu_{rec}}$$

| Symbol | Unit | Description |
|--------|------|-------------|
| $B_r$ | T | Magnet remanence (e.g., N42SH: 1.32 T @ 20°C) |
| $g_{eff}$ | m | Effective airgap = $g \cdot k_c$ (Carter factor) |
| $h_m$ | m | Magnet thickness in magnetization direction |
| $\mu_{rec}$ | — | Recoil permeability (NdFeB ≈ 1.05) |

Carter factor for slotted stator:

$$k_c = \frac{\tau_s}{\tau_s - \frac{b_{s0}^2}{5 g + b_{s0}}}$$

where $\tau_s$ = slot pitch, $b_{s0}$ = slot opening width, $g$ = mechanical airgap.

### 3.2 Back-EMF

RMS phase Back-EMF:

$$E_{rms} = \frac{\sqrt{2}}{2} \cdot p \cdot q \cdot N_s \cdot k_{w1} \cdot B_{g1} \cdot L_{stk} \cdot D_{ro} \cdot \omega_m$$

| Symbol | Unit | Description |
|--------|------|-------------|
| $p$ | — | Pole pairs |
| $q$ | — | Slots per pole per phase |
| $N_s$ | — | Turns per slot |
| $k_{w1}$ | — | Fundamental winding factor |
| $B_{g1}$ | T | Fundamental airgap flux density |
| $L_{stk}$ | m | Stack length |
| $D_{ro}$ | m | Rotor outer diameter |
| $\omega_m$ | rad/s | Mechanical angular velocity |

Back-EMF constant: $k_e = E_{rms} / \omega_m$  (V·s/rad)

### 3.3 Torque

Average electromagnetic torque:

$$T_{avg} = \frac{3}{2} \cdot p \cdot [\lambda_{PM} \cdot i_q + (L_d - L_q) \cdot i_d \cdot i_q]$$

For SPM (surface PM) where $L_d \approx L_q$:

$$T_{avg} = \frac{3}{2} \cdot p \cdot \lambda_{PM} \cdot i_q$$

Torque ripple:

$$T_{ripple} = \frac{T_{max} - T_{min}}{T_{avg}} \times 100\%$$

Cogging torque (analytical estimate):

$$T_{cog} \approx \frac{\pi}{2} \cdot D_{ro} \cdot L_{stk} \cdot \frac{B_r^2}{2\mu_0} \cdot \frac{g}{h_m} \cdot \sin\left(\frac{\pi}{N_{LCM}}\right)$$

where $N_{LCM}$ = LCM(poles, slots).

### 3.4 Turns per Phase

$$N_{ph} = \frac{E_{rms}}{\sqrt{2} \cdot \pi \cdot f \cdot k_{w1} \cdot B_{g1} \cdot L_{stk} \cdot D_{ro}}$$

Turns per slot:

$$N_s = \frac{2 \cdot N_{ph} \cdot m}{Q_s \cdot a}$$

where $m$ = number of phases, $Q_s$ = number of slots, $a$ = parallel branches.

### 3.5 Slot Fill Factor

$$k_{fill} = \frac{N_s \cdot A_{wire}}{A_{slot\_copper}} = \frac{N_s \cdot \frac{\pi d_{wire}^2}{4}}{A_{slot\_usable}}$$

| Symbol | Unit | Description |
|--------|------|-------------|
| $N_s$ | — | Turns per slot |
| $d_{wire}$ | m | Wire diameter (including insulation) |
| $A_{slot\_usable}$ | m² | Usable slot area (after insulation) |

Typical max values:
- Hand winding: 0.35–0.45
- Machine winding (needle): 0.45–0.55
- Hairpin winding: 0.55–0.70

### 3.6 Copper Loss (I²R)

$$P_{cu} = m \cdot I_{rms}^2 \cdot R_{ph}$$

Phase resistance:

$$R_{ph} = \rho_{cu} \cdot \frac{N_{ph} \cdot L_{turn}}{A_{wire}} \cdot [1 + \alpha_{cu}(T_w - 20°C)]$$

| Symbol | Value | Unit |
|--------|-------|------|
| $\rho_{cu}$ | $1.72 \times 10^{-8}$ | Ω·m (@ 20°C) |
| $\alpha_{cu}$ | $3.93 \times 10^{-3}$ | 1/°C |
| $L_{turn}$ | — | m (mean turn length) |

Mean turn length (concentrated winding):

$$L_{turn} \approx 2 \cdot L_{stk} + 2 \cdot (w_{tooth} + h_{slot})$$

### 3.7 Iron Loss (Bertotti Model)

$$P_{fe} = k_h \cdot f \cdot B_m^2 + k_e \cdot f^2 \cdot B_m^2 + k_{exc} \cdot f^{1.5} \cdot B_m^{1.5}$$

| Term | Coefficient | Description |
|------|------------|-------------|
| Hysteresis | $k_h$ | Static hysteresis |
| Eddy current | $k_e$ | Classical eddy current |
| Excess | $k_{exc}$ | Anomalous/excess loss |

Total iron loss (applied per-element in FEA):

$$P_{fe\_total} = \sum \left( P_{fe\_stator\_yoke} + P_{fe\_stator\_teeth} + P_{fe\_rotor\_yoke} \right)$$

### 3.8 PM Eddy Current Loss

$$P_{PM\_eddy} = \frac{1}{24} \cdot \sigma_{PM} \cdot \omega_e^2 \cdot h_m^2 \cdot B_{slot}^2 \cdot V_{PM}$$

| Symbol | Unit | Description |
|--------|------|-------------|
| $\sigma_{PM}$ | S/m | PM electrical conductivity (NdFeB ≈ 6.67×10⁵) |
| $\omega_e$ | rad/s | Electrical angular frequency |
| $B_{slot}$ | T | Slot harmonic flux density amplitude |
| $V_{PM}$ | m³ | PM volume |

### 3.9 Electric Loading & AJ Product

**Electric loading (linear current density):**

$$A = \frac{m \cdot N_{ph} \cdot I_{rms}}{\pi \cdot D_{ro}} \quad [A/m]$$

**Current density:**

$$J = \frac{I_{rms}}{a \cdot A_{wire}} \quad [A/m^2]$$

**AJ product (thermal indicator):**

$$AJ = A \cdot J \quad [A^2/m^3]$$

| Cooling Type | Typical Max AJ (×10¹⁰) |
|-------------|------------------------|
| Natural convection | 0.8–1.5 |
| Forced air (fan) | 1.5–3.0 |
| Water jacket | 3.0–5.0 |
| Oil spray | 5.0–8.0 |

---

## §4 Slot Geometry Templates

### Common slot shapes

```
┌──────────────────────────────────────┐
│  TYPE 1: Round-bottom Trapezoid      │
│         ╭──────────────╮             │
│  bs0 ←→ │ opening      │            │
│         │╭────────────╮│             │
│  bs1 ←→││ wedge      ││  ← hs0     │
│        ││╰────────────╯│  ← hs1     │
│  bs2 ←→╰──────────────╯  ← hs2     │
│        ╰──────────────╯             │
└──────────────────────────────────────┘

Key dimensions:
  bs0 = slot opening width
  bs1 = slot wedge width  
  bs2 = slot bottom width
  hs0 = slot opening depth
  hs1 = slot wedge depth
  hs2 = slot body depth
```

```
┌──────────────────────────────────────┐
│  TYPE 2: Parallel Tooth              │
│  ╭──────────────────────────╮        │
│  │          slot body       │        │
│  │  (parallel sides)       │        │
│  ╰──────────────────────────╯        │
│  bs0 (opening at top)                │
│  tooth_width = constant along depth  │
└──────────────────────────────────────┘
```

```
┌──────────────────────────────────────┐
│  TYPE 3: Parallel Slot (used in IM)  │
│  ╭──╮                         ╭──╮   │
│  │  │    parallel sides       │  │   │
│  │  ╰──────────╮  ╭──────────╯  │   │
│  │             │  │             │   │
│  ╰─────────────╯  ╰─────────────╯   │
│  (constant slot width, varying tooth)│
└──────────────────────────────────────┘
```

### Slot area calculation

**Trapezoidal slot:**

$$A_{slot} = \frac{(b_{s1} + b_{s2})}{2} \cdot h_{s2} + b_{s1} \cdot h_{s1}$$

**Usable copper area:**

$$A_{cu} = A_{slot} - A_{insulation} - A_{wedge} - A_{liner}$$

---

## §5 Material Database

### 5.1 Lamination Steels (Non-Oriented Silicon Steel)

| Grade | Thickness (mm) | Max μ_r | Loss @1.5T/50Hz (W/kg) | Loss @1.0T/400Hz (W/kg) | Saturation (T) | Yield (MPa) |
|-------|---------------|---------|------------------------|------------------------|----------------|-------------|
| M235-35A | 0.35 | 4500 | 2.35 | — | 1.80 | 420 |
| M270-35A | 0.35 | 4200 | 2.70 | — | 1.80 | 410 |
| M330-35A | 0.35 | 4000 | 3.30 | — | 1.80 | 400 |
| M400-50A | 0.50 | 3800 | 4.00 | — | 1.78 | 380 |
| 35JN250 | 0.35 | 5000 | 2.50 | 16.5 | 1.79 | 430 |
| 50JN400 | 0.50 | 4400 | 4.00 | 26.0 | 1.78 | 390 |
| 10JNEX900 | 0.10 | 800 | 0.90 | 5.5 | 1.58 | 550 |
| NO20 (amorphous) | 0.025 | 1200 | 0.20 | 1.2 | 1.56 | 900 |

**Bertotti coefficients (example for M270-35A):**

| Coefficient | Stator Yoke | Stator Teeth | Rotor |
|------------|-------------|--------------|-------|
| $k_h$ (W·s/T²·m³) | 220 | 200 | 180 |
| $k_e$ (W·s²/T²·m³) | 0.85 | 0.80 | 0.75 |
| $k_{exc}$ (W·s^1.5/T^1.5·m³) | 3.5 | 3.2 | 2.8 |

### 5.2 Permanent Magnet Grades

#### NdFeB (Neodymium Iron Boron)

| Grade | $B_r$ @20°C (T) | $H_{cj}$ @20°C (kA/m) | $(BH)_{max}$ (kJ/m³) | $\alpha_{Br}$ (%/°C) | $\beta_{Hcj}$ (%/°C) | Max Tw (°C) |
|-------|------------------|------------------------|-----------------------|----------------------|----------------------|-------------|
| N35 | 1.17–1.22 | ≥955 | 263–287 | −0.12 | −0.60 | 80 |
| N42 | 1.28–1.33 | ≥955 | 318–342 | −0.12 | −0.60 | 80 |
| N48 | 1.36–1.42 | ≥876 | 358–390 | −0.12 | −0.60 | 80 |
| N38SH | 1.22–1.28 | ≥1592 | 287–310 | −0.11 | −0.55 | 150 |
| N42SH | 1.28–1.33 | ≥1592 | 318–342 | −0.11 | −0.55 | 150 |
| N48SH | 1.36–1.42 | ≥1592 | 358–390 | −0.11 | −0.55 | 150 |
| N42UH | 1.28–1.33 | ≥1990 | 318–342 | −0.10 | −0.50 | 180 |
| N38EH | 1.22–1.28 | ≥2388 | 287–310 | −0.10 | −0.50 | 200 |

#### SmCo (Samarium Cobalt)

| Grade | $B_r$ (T) | $H_{cj}$ (kA/m) | $(BH)_{max}$ (kJ/m³) | $\alpha_{Br}$ (%/°C) | Max Tw (°C) |
|-------|-----------|-----------------|-----------------------|----------------------|-------------|
| SmCo26 | 1.05 | 1592 | 210 | −0.035 | 350 |
| SmCo30 | 1.08 | 2388 | 230 | −0.035 | 350 |

#### Ferrite (Ceramic)

| Grade | $B_r$ (T) | $H_{cj}$ (kA/m) | $(BH)_{max}$ (kJ/m³) | $\alpha_{Br}$ (%/°C) | Max Tw (°C) |
|-------|-----------|-----------------|-----------------------|----------------------|-------------|
| Y30 | 0.38 | 240 | 27.8 | +0.20 | 250 |
| Y35 | 0.41 | 250 | 32.0 | +0.20 | 250 |

### 5.3 Copper Wire Table (AWG — Standard Magnet Wire)

| AWG | Bare Diameter (mm) | Area (mm²) | R @20°C (Ω/km) | I_max @5A/mm² (A) | I_max @8A/mm² (A) | I_max @10A/mm² (A) |
|-----|-------------------|------------|----------------|---------------------|---------------------|----------------------|
| 10 | 2.588 | 5.261 | 3.28 | 26.3 | 42.1 | 52.6 |
| 12 | 2.053 | 3.308 | 5.21 | 16.5 | 26.5 | 33.1 |
| 14 | 1.628 | 2.082 | 8.28 | 10.4 | 16.7 | 20.8 |
| 16 | 1.290 | 1.307 | 13.17 | 6.53 | 10.5 | 13.1 |
| 17 | 1.150 | 1.038 | 16.61 | 5.19 | 8.31 | 10.4 |
| 18 | 1.024 | 0.823 | 20.95 | 4.12 | 6.59 | 8.23 |
| 19 | 0.912 | 0.653 | 26.42 | 3.27 | 5.22 | 6.53 |
| 20 | 0.813 | 0.519 | 33.31 | 2.59 | 4.15 | 5.19 |
| 21 | 0.724 | 0.411 | 41.98 | 2.06 | 3.29 | 4.11 |
| 22 | 0.643 | 0.325 | 53.07 | 1.62 | 2.60 | 3.25 |
| 23 | 0.574 | 0.258 | 66.78 | 1.29 | 2.07 | 2.58 |
| 24 | 0.511 | 0.205 | 84.21 | 1.02 | 1.64 | 2.05 |
| 25 | 0.455 | 0.162 | 106.2 | 0.812 | 1.30 | 1.62 |
| 26 | 0.404 | 0.128 | 134.4 | 0.641 | 1.03 | 1.28 |

### 5.4 Insulation Class Table

| Class | Max Continuous Temp (°C) | Max Hotspot Temp (°C) | Typical Materials | Applications |
|-------|--------------------------|-----------------------|-------------------|-------------|
| A | 105 | 115 | Cotton, silk, paper (impregnated) | Legacy small motors |
| B | 130 | 140 | Mica, polyester film, glass fiber + epoxy | General industrial |
| F | 155 | 170 | Polyester-imide, Nomex, Kapton (Class F) | Automotive traction, servo |
| H | 180 | 195 | Silicone varnish, Kapton (Class H), glass-mica | Aerospace, high-temp industrial |
| C | >200 | >200 | PTFE, ceramic, pure mica | Specialized extreme temp |

**Insulation thickness by voltage:**

| Voltage (V) | Minimum Insulation (mm) |
|-------------|------------------------|
| <250 | 0.18 (Grade 1 enamelled wire) |
| 250–600 | 0.25 (Grade 2) |
| 600–1000 | 0.35 (slot liner + wire enamel) |
| >1000 | 0.50+ |

### 5.5 Housing / Frame Materials

| Material | Thermal Conductivity (W/m·K) | Density (kg/m³) | Tensile Strength (MPa) | Cost Index | Notes |
|----------|------------------------------|-----------------|------------------------|------------|-------|
| Al 6061-T6 | 167 | 2700 | 310 | 2.5 | Machined, good thermal |
| Al Die-Cast (A380) | 96 | 2710 | 324 | 1.5 | Cost-effective, lower thermal |
| Steel (AISI 1045) | 50 | 7850 | 570 | 1.0 | Structural, poor thermal |
| Magnesium AZ91D | 72 | 1810 | 230 | 4.0 | Lightweight, moderate thermal |
| Copper (C110) | 391 | 8940 | 220 | 7.0 | Excellent thermal, heavy, expensive |

### 5.6 Shaft Materials

| Material | Yield (MPa) | Thermal Cond. (W/m·K) | Magnetic? |
|----------|-------------|----------------------|-----------|
| AISI 4140 | 655 | 42 | Yes (affected by rotor flux) |
| AISI 304 (SS) | 215 | 16 | No (non-magnetic) |
| AISI 316 (SS) | 205 | 16 | No (non-magnetic) |

---

## §6 Winding Topology Reference

### Concentrated Winding (FSCW — Fractional Slot Concentrated Winding)

| Poles/Slots | q (spp) | k_w1 | Coil Span (slots) | Periodicity | Torque Quality |
|-------------|---------|------|--------------------|-------------|----------------|
| 8p/12s | 0.5 | 0.866 | 2 (tooth-coil) | 4 | Excellent (low ripple) |
| 10p/12s | 0.4 | 0.933 | 2 (tooth-coil) | 2 | Very good |
| 8p/9s | 0.375 | 0.945 | 2 (tooth-coil) | 1 | Good (unbalanced force) |
| 4p/12s | 1.0 | 0.966 | 3 | 4 | Good |
| 6p/9s | 0.5 | 0.866 | 2 (tooth-coil) | 3 | Good |
| 8p/18s | 0.75 | 0.945 | 2 | 2 | Very good |
| 10p/24s | 0.8 | 0.933 | 2 | 2 | Very good |
| 14p/12s | 0.286 | 0.933 | 2 (tooth-coil) | 2 | Good |

**Winding factor calculation for concentrated winding:**

$$k_{w1} = \sin\left(\frac{\pi}{2} \cdot \frac{p}{Q_s}\right) \cdot \frac{\sin\left(q \cdot \frac{\alpha}{2}\right)}{q \cdot \sin\left(\frac{\alpha}{2}\right)}$$

where $q = Q_s / (2p \cdot m)$ (slots per pole per phase), $\alpha = 2\pi p / Q_s$ (slot angle electrical).

**Winding layout matrix for 8p12s (AA'BB'CC' × 2):**

```
Slot:  1   2   3   4   5   6   7   8   9  10  11  12
Phase: A+  A-  B+  B-  C+  C-  A+  A-  B+  B-  C+  C-
```

**Winding layout matrix for 10p12s (ABCABC × 2):**

```
Slot:  1   2   3   4   5   6   7   8   9  10  11  12
Phase: A+  C-  B+  A-  C+  B-  A+  C-  B+  A-  C+  B-
```

### Distributed Winding

For integer-slot distributed windings, the distribution factor:

$$k_{d1} = \frac{\sin(q \cdot \alpha/2)}{q \cdot \sin(\alpha/2)}$$

Pitch factor:

$$k_{p1} = \sin\left(\frac{\pi}{2} \cdot \frac{\tau_c}{\tau_p}\right)$$

where $\tau_c$ = coil pitch (slots), $\tau_p$ = pole pitch (slots).

Total winding factor: $k_{w1} = k_{d1} \cdot k_{p1}$

---

## §7 Cooling & Thermal Limits

### 7.1 Cooling Methods Overview

| Method | Heat Transfer Coeff. (W/m²·K) | Max AJ (×10¹⁰) | Complexity | Cost |
|--------|------------------------------|----------------|------------|------|
| Natural convection (air) | 5–15 | 0.8–1.5 | Minimal | Low |
| Forced air (TEFC fan) | 20–50 | 1.5–3.0 | Low | Medium |
| Liquid jacket (water-glycol) | 500–2000 | 3.0–5.0 | Medium | High |
| Oil spray/immersion | 200–800 | 5.0–8.0 | High | High |
| Direct conductor cooling | 1000–5000 | 8.0–15.0 | Very High | Very High |

### 7.2 Thermal Equivalent Circuit (Simplified Lumped Parameter)

```
P_cu_winding → R_winding-iron → R_iron-housing → R_housing-ambient
                                   ↑
P_fe_stator → ────────────────────┘
                                   ↑
P_fe_rotor → R_rotor-iron → R_airgap → ─┘
                                   ↑
P_PM_eddy → ──────────────────────┘
```

### 7.3 Temperature Rise Estimation

**Winding temperature rise (steady state):**

$$\Delta T_w = P_{loss\_total} \cdot \sum R_{th}$$

Typical $R_{th}$ values:
- Winding to stator iron: 0.02–0.05 K/W
- Stator iron to housing: 0.05–0.10 K/W
- Housing to ambient (natural): 1.0–3.0 K/W
- Housing to ambient (forced air): 0.3–0.8 K/W
- Housing to ambient (water jacket): 0.05–0.15 K/W

### 7.4 Hotspot Rules

- Winding hotspot = average winding temp + 10–15°C
- PM hotspot = average PM temp + 5–10°C
- Safety margin for PM: max operating point ≥ 50°C below Hcj knee

---

## §8 NVH Quick-Check Flow

### 8.1 Workflow

```
1. Compute radial force density
   F_r(θ, t) = B_r²(θ, t) / (2·μ₀)
                │
2. FFT in space (circumferential) and time
   → Force orders (mode shapes)
                │
3. Identify dominant spatial orders (0, 1, 2, ...)
   - Order 0: breathing mode
   - Order 2: elliptical mode
   - Order 4: square mode
   - ...
                │
4. Structural FEA: modal analysis
   → Natural frequencies of stator/yoke
                │
5. Check resonance risk:
   f_excitation matches f_natural within ±10%
                │
6. Acoustic radiation (ERP or BEM)
```

### 8.2 Radial Force Orders for Common Slot/Pole Combos

| Poles/Slots | GCD | Dominant Force Orders | Torque Ripple Order |
|-------------|-----|----------------------|---------------------|
| 8p/12s | 4 | 0, 4, 8, 12 | 24th |
| 10p/12s | 2 | 2, 4, 10, 14 | 60th |
| 8p/9s | 1 | 1, 8, 9, 10 | 72nd |
| 4p/12s | 4 | 0, 4, 8 | 12th |

### 8.3 Quick-Check Formula for Resonance

Lowest stator yoke frequency (breathing mode order 0):

$$f_0 = \frac{1}{2\pi} \sqrt{\frac{E \cdot t_{yoke}}{M_{yoke} \cdot R_{avg}^2}}$$

Elliptical mode (order 2):

$$f_2 \approx f_0 \cdot \frac{2}{\sqrt{1-\nu^2}}$$

where $E$ = Young's modulus, $\nu$ = Poisson ratio, $t_{yoke}$ = yoke thickness, $R_{avg}$ = mean yoke radius.

---

## §9 Demagnetization Analysis

### 9.1 PM Operating Point

PM operating point on the B-H curve:

$$B_m = B_r \cdot \frac{\mu_{rec} \cdot \frac{g_{eff}}{h_m}}{1 + \mu_{rec} \cdot \frac{g_{eff}}{h_m}}$$

Under armature reaction (peak demagnetization):

$$B_{m,min} = B_r - \mu_{rec} \cdot \mu_0 \cdot \frac{H_{armature}}{1 + \mu_{rec} \cdot \frac{g_{eff}}{h_m}}$$

where $H_{armature} \approx \frac{3 I_{peak} N_s}{\delta_{mag\_path}}$ for concentrated winding with peak current.

### 9.2 Demagnetization Safety Factor

$$S_{demag} = \frac{H_{cj}(T_{max})}{H_{demag\_peak}} \geq 1.5$$

where:
- $H_{cj}(T_{max}) = H_{cj,20°C} \cdot (1 + \beta_{Hcj}(T_{max} - 20°C))$
- $H_{demag\_peak}$ = peak opposing H-field in PM under worst-case (max current, max temp)

### 9.3 Demagnetization Analysis in FEA

1. Set PM material to consider demagnetization (non-linear BH)
2. Apply peak demagnetizing current (Id < 0, Iq = 0 for SPM)
3. Evaluate $B_m$ in each PM element
4. If $B_m < B_{knee}$, irreversible demagnetization occurs
5. Compute % irreversible loss: $DM_{pct} = \frac{V_{B<B_{knee}}}{V_{PM}} \times 100\%$

### 9.4 Demag Risk by PM Grade (overload/short-circuit)

| Scenario | N42SH (150°C) | N42UH (180°C) | N38EH (200°C) | SmCo30 (350°C) |
|----------|---------------|---------------|---------------|----------------|
| Rated load @ max temp | Safe | Safe | Safe | Safe |
| 3× overload @ max temp | Risk | Borderline | Safe | Safe |
| 3ph short @ max temp | Demag likely | Risk | Borderline | Safe |
| 3ph short @ 20°C | Safe | Safe | Safe | Safe |

---

## §10 BOM & Cost Estimation

### 10.1 Bill of Materials Template

| # | Component | Material | Quantity | Unit Cost (USD) | Total Cost (USD) | Supplier |
|---|-----------|----------|----------|------------------|------------------|----------|
| 1 | Lamination stack | M270-35A | 1 | 12.50 | 12.50 | — |
| 2 | Permanent magnets | N42SH | 8 | 1.80 | 14.40 | — |
| 3 | Copper windings | AWG 18 | 0.45 kg | 10.00/kg | 4.50 | — |
| 4 | Housing | Al Die-cast | 1 | 15.00 | 15.00 | — |
| 5 | Shaft | AISI 4140 | 1 | 8.00 | 8.00 | — |
| 6 | Bearings | 6204-2RS | 2 | 3.00 | 6.00 | — |
| 7 | Insulation | Nomex 410 | set | 2.00 | 2.00 | — |
| 8 | Resolver/Encoder | — | 1 | 15.00 | 15.00 | — |
| 9 | Terminal box | — | 1 | 3.00 | 3.00 | — |
| 10 | Paint/sealant | — | — | 1.50 | 1.50 | — |
| | **Material Total** | | | | **81.90** | |
| | Assembly labor | | | | 20.00 | |
| | Testing | | | | 8.00 | |
| | **Total Unit Cost** | | | | **109.90** | |

### 10.2 Cost Scaling Factors

| Production Volume | Cost Multiplier |
|-------------------|----------------|
| Prototype (1–10) | ×3.0–5.0 |
| Low volume (100–1k) | ×1.5–2.0 |
| Medium volume (1k–10k) | ×1.0 (base) |
| High volume (10k–100k) | ×0.6–0.8 |
| Mass production (>100k) | ×0.4–0.6 |

---

## §11 Manufacturing Tolerances & Sensitivity

### 11.1 Airgap Eccentricity Effects

**Static eccentricity:** Rotor axis shifted but rotates about its own center.

**Dynamic eccentricity:** Rotor rotates about stator center (rotor orbit).

**Mixed eccentricity (practical):** Combination of both.

Eccentricity ratio:

$$e = \frac{\delta_{ecc}}{g} \times 100\%$$

where $\delta_{ecc}$ = center offset, $g$ = nominal airgap.

| $e$ (%) | Effect |
|---------|--------|
| <10% | Negligible (well-manufactured) |
| 10–20% | Noticeable UMP (Unbalanced Magnetic Pull), increased noise |
| 20–30% | Significant torque ripple increase, bearing life reduction |
| >30% | Risk of rotor-stator contact |

**UMP (Unbalanced Magnetic Pull) estimate:**

$$F_{UMP} \approx \frac{B_{g}^2 \cdot \pi \cdot D_{ro} \cdot L_{stk}}{2\mu_0} \cdot \frac{e}{2}$$

### 11.2 PM Thickness Tolerance Impact on $B_g$

$$\frac{\Delta B_g}{B_g} = \frac{\Delta h_m}{h_m} \cdot \frac{g_{eff}}{h_m + \mu_{rec} \cdot g_{eff}}$$

Example: For $h_m = 3.5$ mm, $g_{eff} = 1.1$ mm, $\mu_{rec} = 1.05$:
- $\pm 0.05$ mm tolerance → $\Delta B_g / B_g \approx \pm 0.6\%$
- $\pm 0.10$ mm tolerance → $\Delta B_g / B_g \approx \pm 1.2\%$

### 11.3 Slot Fill Variation by Winding Method

| Winding Method | $k_{fill}$ Range | $\Delta k_{fill}$ (tolerance) | Comments |
|---------------|------------------|------------------------------|----------|
| Hand winding | 0.35–0.42 | ±0.05 | Operator dependent |
| Needle winding (CNC) | 0.42–0.55 | ±0.03 | Repeatable |
| Flyer winding | 0.38–0.48 | ±0.04 | Moderate |
| Hairpin | 0.55–0.70 | ±0.02 | Very repeatable |
| Segmented stator | 0.50–0.65 | ±0.02 | High precision |

### 11.4 Sensitivity Matrix (First-Order)

| Parameter | $\partial T_{avg}/\partial x$ | $\partial B_g/\partial x$ | $\partial \eta/\partial x$ |
|-----------|-------------------------------|---------------------------|----------------------------|
| $h_m$ (+1%) | +0.3% | +0.5% | +0.1% |
| $g$ (+1%) | −0.5% | −0.8% | −0.2% |
| $L_{stk}$ (+1%) | +1.0% | 0% | +0.5% |
| $D_{ro}$ (+1%) | +1.8% | 0% | +0.3% |
| $N_s$ (+1%) | +0.5% | 0% | +0.5% (at low load) |
| $B_r$ (+1%) | +0.8% | +1.0% | +0.2% |

---

## §12 Design Comparison Matrix Template

### 12.1 Comparison Table Format

| Parameter | Unit | Design A (Baseline) | Design B (Optimized) | Design C (Alternative) | Target |
|-----------|------|---------------------|-----------------------|------------------------|--------|
| **Topology** | | | | | |
| Poles / Slots | — | 8 / 12 | 8 / 12 | 10 / 12 | — |
| Outer diameter | mm | 120 | 120 | 120 | ≤120 |
| Stack length | mm | 80 | 85 | 78 | — |
| Airgap | mm | 1.0 | 0.8 | 1.0 | — |
| Magnet thickness | mm | 3.5 | 3.2 | 3.5 | — |
| **Performance** | | | | | |
| Rated torque | N·m | 5.0 | 5.0 | 5.0 | 5.0 |
| Peak torque | N·m | 14.2 | 15.1 | 14.8 | ≥15.0 |
| Torque ripple | % | 6.2 | 4.8 | 5.5 | ≤5.0 |
| Cogging torque | % | 2.1 | 1.5 | 1.8 | ≤2.0 |
| Rated efficiency | % | 92.5 | 93.2 | 92.8 | ≥93.0 |
| Back-EMF const. | V/(krpm) | 42.5 | 43.1 | 44.0 | — |
| **Thermal** | | | | | |
| Copper loss | W | 85 | 78 | 82 | — |
| Iron loss | W | 32 | 35 | 30 | — |
| PM eddy loss | W | 8 | 5 | 9 | — |
| Total loss | W | 125 | 118 | 121 | — |
| Winding temp rise | °C | 75 | 68 | 72 | <80 |
| AJ product | ×10¹⁰ | 2.8 | 2.5 | 2.7 | ≤3.0 |
| **NVH** | | | | | |
| Max radial force | N/m² | 2.1×10⁵ | 1.8×10⁵ | 2.0×10⁵ | — |
| Dominant order | — | 4th | 4th | 2nd | — |
| Resonance risk | — | Low | Low | Medium | Low |
| **Cost** | | | | | |
| PM cost | USD | 14.40 | 13.20 | 14.40 | — |
| Cu cost | USD | 4.50 | 4.80 | 4.20 | — |
| Total BOM | USD | 81.90 | 80.50 | 79.30 | — |

### 12.2 Decision Matrix (Weighted Scoring)

| Criterion | Weight (%) | Design A | Design B | Design C |
|-----------|-----------|----------|----------|----------|
| Efficiency | 25 | 3 | 4 | 4 |
| Torque quality | 20 | 3 | 4 | 4 |
| Thermal margin | 15 | 3 | 4 | 3 |
| NVH | 10 | 4 | 4 | 3 |
| Cost | 15 | 3 | 3 | 4 |
| Manufacturability | 10 | 4 | 3 | 3 |
| PM demag safety | 5 | 4 | 3 | 4 |
| **Weighted Total** | **100** | **3.10** | **3.65** | **3.60** |

Scoring: 1=Poor, 2=Below, 3=Meets, 4=Exceeds, 5=Excellent

---

## §13 Integration with Control Systems

### 13.1 MTPA Trajectory Calculation

Maximum Torque Per Ampere (MTPA) for IPM machines ($L_d \neq L_q$):

$$i_d = \frac{\lambda_{PM}}{2(L_q - L_d)} - \sqrt{\frac{\lambda_{PM}^2}{4(L_q - L_d)^2} + i_q^2}$$

For SPM machines ($L_d \approx L_q$), MTPA reduces to **Id=0** control ($i_d = 0$).

### 13.2 Flux Weakening Speed Range

**Base speed** (voltage limit intersection):

$$\omega_{base} = \frac{V_{dc}}{\sqrt{3} \cdot \sqrt{(L_d \cdot i_d + \lambda_{PM})^2 + (L_q \cdot i_q)^2}}$$

**Maximum flux-weakening speed (theoretical infinite speed):**

$$\omega_{max} = \frac{V_{dc}}{\sqrt{3} \cdot (\lambda_{PM} - L_d \cdot I_{max})}$$

**Characteristic current:**

$$I_{ch} = \frac{\lambda_{PM}}{L_d}$$

- If $I_{ch} \leq I_{max}$: infinite CPSR (Constant Power Speed Ratio)
- If $I_{ch} > I_{max}$: finite CPSR, limited FW capability

### 13.3 Id=0 vs MTPA Comparison

| Aspect | Id=0 (SPM) | MTPA (IPM) |
|--------|-----------|------------|
| Torque equation | $T = \frac{3}{2} p \lambda_{PM} i_q$ | $T = \frac{3}{2} p [\lambda_{PM} i_q + (L_d-L_q) i_d i_q]$ |
| Current angle (γ) | 90° | 95°–130° (varies with load) |
| Reluctance torque | None | $\frac{3}{2} p (L_d-L_q) i_d i_q$ |
| Saliency ratio ($L_q/L_d$) | ≈1.0 | 1.5–3.0 |
| Efficiency @ rated | Good | Better (same T with less I) |
| Implementation complexity | Simple | Requires 2D LUT |
| Flux weakening | Limited | Better (reluctance torque at FW) |

### 13.4 dq Axis Inductance Estimation

**Analytical (SPM):**

$$L_d \approx L_q \approx \frac{3}{2} \cdot \frac{\mu_0 \cdot D_{ro} \cdot L_{stk}}{g_{eff}} \cdot \left(\frac{N_{ph} \cdot k_{w1}}{p}\right)^2$$

**FEA method:**
1. Freeze permeability at operating point
2. Apply incremental d-axis and q-axis currents
3. Compute flux linkage change: $L_d = \frac{\Delta \lambda_d}{\Delta i_d}$, $L_q = \frac{\Delta \lambda_q}{\Delta i_q}$

### 13.5 Flux Weakening Operating Map

```
    Torque (Nm)
        ↑
  T_peak│   ╭────────╮
        │  ╱          ╲  ← MTPA region (constant torque)
        │ ╱      1      ╲
  T_rated│╱                ╲───── ← FW region (constant power)
        │         2          ╲
        │                      ╲
        │                         ╲────── ← MTPV (max T per volt)
        └──────────────────────────────────→ Speed (rpm)
             ω_base             ω_max

  Region 1 (0 → ω_base): MTPA or Id=0
  Region 2 (ω_base → ω_ref): Flux weakening
  Region 3 (ω_ref → ω_max): MTPV (deep FW)
```

---

## Appendix: Design Rule Quick Reference

### 12 Golden Rules of PM Motor Design

| # | Rule | Rationale |
|---|------|-----------|
| 1 | **$g \geq 0.5$ mm** | Manufacturing limit; smaller gaps risk contact |
| 2 | **$h_m \geq 3\cdot g$** | Ensures PM dominates airgap reluctance |
| 3 | **$t_{yoke\_stator} \geq t_{tooth}/2$** | Avoids yoke saturation bottleneck |
| 4 | **$t_{yoke\_rotor} \geq h_m$** | Return path for PM flux |
| 5 | **$B_{tooth} \leq 1.7$ T** (at rated) | Keeps teeth below saturation knee |
| 6 | **$B_{yoke} \leq 1.5$ T** (at rated) | Yoke saturation margin |
| 7 | **$k_{fill} \leq 0.55$** (needle winding) | Practical manufacturability |
| 8 | **$A J \leq$ limit per cooling method** | Thermal constraint |
| 9 | **$S_{demag} \geq 1.5$** (at max temp+current) | PM safety margin |
| 10 | **$\lambda_{PM} < V_{dc}/(\sqrt{3} \cdot \omega_{base})$** | Voltage limit must be met |
| 11 | **$N_{LCM}(poles, slots) \geq 24$** | Low cogging torque |
| 12 | **Avoid odd GCD(poles, slots)** | Minimizes UMP and vibration |
