# Simulation Configurations — Complete Reference

Every simulation type below is pre-configured. Replace `<placeholder>` values
with actual design parameters from `motor_param_calc.py` output.

---

## §1 — No-Load Back-EMF & Cogging Torque

**Purpose:** Validate winding layout and PM magnetization. Detect cogging torque magnitude.

**Setup:**
```python
# 1. Create transient setup — 1 electrical cycle, fine time step
add_solution_setup(
    setup_name="NoLoad",
    stop_time="<1/f_e>s",       # e.g., 0.005s for 200Hz
    time_step="<1/(f_e*200)>s",  # e.g., 2.5e-5s
    save_fields_flag=True
)

# 2. Set all currents to zero
run_script(script="""
oDesign.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:CurrentSource",
      "Current:=", "0A"]
    ]
)
""")

# 3. Set rated speed
assign_band(
    objects=["Band"],
    angular_velocity="3000rpm"
)
```

**Expected outputs:**
- Back-EMF waveform (3 phases, 120° shifted sinusoidal)
- Back-EMF THD < 5% (for SPMSM with distributed winding)
- Cogging torque peak-to-peak < 5% of rated torque
- PM flux linkage λ_pm verified against analytical calculation

**Diagnostics:**
- If back-EMF phase sequence is wrong → winding polarity swap
- If back-EMF flat-topped → slot harmonics; consider skewing
- If cogging > 5% → reduce slot opening or increase LCM(pole,slot)

**Extraction:**
```python
create_report(
    report_name="BackEMF_NoLoad",
    report_type="Transient",
    x_quantity="Time",
    y_quantities=["InducedVoltage(Phase_A)", "InducedVoltage(Phase_B)", "InducedVoltage(Phase_C)"],
    display_type="Rectangular Plot"
)

create_report(
    report_name="Cogging_Torque",
    report_type="Transient",
    x_quantity="Time",
    y_quantities=["Moving1.Torque"],
    display_type="Rectangular Plot"
)
```

---

## §2 — Rated Load Simulation

**Purpose:** Verify torque output, efficiency, and thermal margin at rated operating point.

**Setup:**
```python
add_solution_setup(
    setup_name="RatedLoad",
    stop_time="<2/f_e>s",       # 2 electrical cycles for steady state
    time_step="<1/(f_e*100)>s", # 100 steps per cycle
    save_fields_flag=False       # Save only last few steps for plots
)

# Set rated current
assign_current_source(
    objects=["Phase_A"],
    amplitude="<I_peak>A",
    phase=0.0,
    frequency="<f_e>Hz",
    name="Current_A"
)
# ... Phases B, C with -120°, -240°
```

**Expected outputs:**
- Average torque ±3% of target
- Torque ripple < 10% (SPMSM) / < 15% (IPM)
- Efficiency ≥ target
- Power factor ≥ 0.85

**Extraction:**
```python
# Torque
create_report(report_name="Torque_Rated", ...,
    y_quantities=["Moving1.Torque"])
data = get_solution_data(["Moving1.Torque"], "RatedLoad")
# Compute mean over last cycle
T_avg = np.mean(data["Moving1.Torque"][-100:])

# Losses
loss_data = get_solution_data(
    ["CoreLoss", "StrandedLoss", "SolidLoss"], "RatedLoad"
)
```

---

## §3 — Overload (2× Rated Current)

**Purpose:** Verify overload torque capability and check saturation.

**Setup:**
```python
# Same as rated load but with 2× current amplitude
assign_current_source(
    objects=["Phase_A"],
    amplitude="<2*I_peak>A",
    phase=0.0,
    frequency="<f_e>Hz",
    name="Current_A_OL"
)
```

**Expected outputs:**
- Torque ≥ 1.8× rated (accounting for saturation)
- No PM irreversible demagnetization (quick check)
- Core flux density < Bsat everywhere

**Extraction:**
```python
# Saturation check via field plot at peak current
create_report(
    report_name="B_Field_Overload",
    report_type="Fields",
    x_quantity="",
    y_quantities=["Mag_B"],
    display_type="Field Plot"
)
```

---

## §4 — Airgap Flux Density Analysis

**Purpose:** The most critical diagnostic — spatial distribution and harmonic content of Bg.

### §4A — Spatial Waveform (Static/Transient)

**Setup:**
```python
# Method 1: Create a line in airgap, extract B along it
run_script(script="""
oModule = oDesign.GetModule("FieldsReporter")
# Create line at middle of airgap, full circumference
oModule.CreateLine(
    ["NAME:Line_Airgap",
     "Coordinate System:=", "Global",
     "X Start:=", "<Dsi/2 + delta/2>mm", "Y Start:=", "0mm", "Z Start:=", "0mm",
     "X End:=", "<same>mm", "Y End:=", "0mm", "Z End:=", "<La>mm",
     "Points:=", "360"]
)
""")

# Method 2: Circular arc in airgap at specific time
run_script(script="""
oModule = oDesign.GetModule("FieldsReporter")
oModule.CreateCircle(
    ["NAME:Circle_Bg",
     "Coordinate System:=", "Global",
     "Center X:=", "0mm", "Center Y:=", "0mm", "Center Z:=", "0mm",
     "Radius:=", "<R_gap>mm",
     "Points:=", "720"]
)
""")
```

**Extraction:**
```python
# Get B_normal and B_tangential along the circle
bg_data = get_field_data(
    objects=["Circle_Bg"],
    quantity="Mag_B",
    time="<t_peak>",
    setup_name="RatedLoad"
)
```

### §4B — FFT Harmonic Analysis

```python
# After extracting Bg spatial data, compute FFT
run_script(script="""
import math
# Bg(theta) → FFT → harmonics
# Identify fundamental (p-th harmonic) and slot harmonics (Q/p ± 1)
""")
```

**Expected outputs:**
- Fundamental Bg amplitude (verify against analytical 0.7-0.85 T target)
- 3rd harmonic < 15% of fundamental
- Slot harmonics at orders (Q/p ± 1)
- Total harmonic distortion THD_B

### §4C — Airgap Flux Density Map (2D Colormap)

```python
create_report(
    report_name="Bg_ColorMap",
    report_type="Fields",
    x_quantity="",
    y_quantities=["Mag_B"],
    display_type="Field Plot"
)
```

**Key checks from colormap:**
- No saturation spots (>1.8 T for M270-35A) in stator teeth
- Uniform flux distribution across poles
- No excessive leakage flux at pole gaps

---

## §5 — Inductance Calculation (Ld, Lq)

**Purpose:** Essential for control design (MTPA, flux weakening, sensorless).

**Method: Frozen Permeability**

```python
# Step 1: Run rated load simulation
run_simulation("RatedLoad")

# Step 2: Freeze permeability at rated operating point
run_script(script="""
oDesign.SetDesignSettings(
    ["NAME:DesignSettings", "FrozenPermeability:=", True]
)
""")

# Step 3: Run d-axis excitation (remove PM, inject Id only)
run_script(script="""
oModule = oDesign.GetModule("BoundarySetup")
# Set PM Br=0 temporarily, or use frozen permeability override
oModule.AssignCurrent(
    ["NAME:Id_Excitation",
     "Objects:=", ["Phase_A", "Phase_B", "Phase_C"],
     "Current:=", "<Id_amplitude>A"]
)
""")

# Step 4: Extract flux linkage
ld_data = get_solution_data(["FluxLinkage(Phase_A)"], "Ld_Setup")

# Ld = λ_d / I_d (from frozen permeability results)
# Repeat for Lq with q-axis excitation
```

**Expected values:**
- SPMSM: Ld ≈ Lq (within 10%)
- IPM: Lq > Ld (saliency ratio 1.5-3.0 typical)

---

## §6 — Iron Loss Map (Bertotti)

**Purpose:** Detailed core loss distribution for thermal analysis and efficiency optimization.

**Setup:**
```python
# Enable core loss calculation
run_script(script="""
oModule = oDesign.GetModule("Maxwell2D")
oModule.SetCoreLoss(
    ["NAME:CoreLoss",
     "Objects:=", ["Stator_Core", "Rotor_Core"],
     "DefinedIn:=", "Object"]
)
""")

add_solution_setup(
    setup_name="IronLoss",
    stop_time="<2/f_e>s",
    time_step="<1/(f_e*100)>s",
    save_fields_flag=False
)
```

**Extraction:**
```python
create_report(
    report_name="CoreLoss_Distribution",
    report_type="Fields",
    x_quantity="",
    y_quantities=["CoreLoss"],
    display_type="Field Plot"
)

# Per-component breakdown
loss_data = get_solution_data(
    ["CoreLoss_Hysteresis", "CoreLoss_EddyCurrent", "CoreLoss_Excess"],
    "IronLoss"
)
```

**Validation:**
- Total iron loss within 20% of Bertotti analytical estimate
- Hysteresis dominant at rated frequency (< 200 Hz)
- Eddy current becomes dominant at high frequency (> 400 Hz)

---

## §7 — PM Eddy Current Loss

**Purpose:** PM heating analysis. Critical for high-speed or high-pole-count motors.

**Setup:**
```python
# Assign finite conductivity to PMs
add_custom_material(
    name="NdFeB_N35_Conductive",
    properties={
        "permeability": 1.05,
        "conductivity": 625000,
        "Hc": 890000,
        "Br": 1.17
    }
)
assign_material(objects=["PM_1", ..., "PM_8"], material="NdFeB_N35_Conductive")

# Fine mesh on PM surface for eddy current capture
assign_mesh_operation(
    objects=["PM_1", ..., "PM_8"],
    operation_type="SkinDepthBased",
    max_length="0.3mm",
    name="PM_SkinMesh"
)
```

**Expected outputs:**
- PM loss < 5 W for 500W motor at rated speed
- PM loss dramatic reduction with segmentation (axial: 3-5 pieces)
- Circumferential segmentation more effective than axial

---

## §8 — Thermal Steady-State

**Purpose:** Verify winding temperature within insulation class limit.

**Setup via Maxwell 3D or coupling to Icepak:**
```python
# Option A: Maxwell built-in thermal
run_script(script="""
oModule = oDesign.GetModule("Thermal")
oModule.AssignConvection(
    ["NAME:Natural_Convection",
     "Objects:=", ["Housing_Outer"],
     "h:=", "10W/m2K",
     "T_ambient:=", "40cel"]
)
oModule.AssignInternalHeat(
    ["NAME:Copper_Loss",
     "Objects:=", ["Winding_A", "Winding_B", "Winding_C"],
     "HeatGeneration:=", "<P_cu>W"]
)
oModule.AssignInternalHeat(
    ["NAME:Core_Loss",
     "Objects:=", ["Stator_Core"],
     "HeatGeneration:=", "<P_fe>W"]
)
""")

# Option B: Export losses to CSV → run in external tool
export_data("D:/thermal/losses.csv", ["CoreLoss", "StrandedLoss"], "RatedLoad")
```

**Expected outputs:**
- Winding hotspot temperature with margin to class limit
- PM temperature (affects Br — iterate if > 20°C above assumed)
- Temperature gradient for thermal stress assessment

---

## §9 — Demagnetization Analysis

**Purpose:** Verify PM safety margin under worst-case conditions.

**Test conditions (run all 3):**

| Test | Speed | Current | Temperature | Pass Criterion |
|------|-------|---------|-------------|---------------|
| Rated short-circuit | Rated | Fault current | 150°C | B_pm > 0.2 T everywhere |
| Max speed short-circuit | 1.2× rated | Fault current | 150°C | B_pm > 0.2 T everywhere |
| 2× overload | Rated | 2× rated | 150°C | B_pm > 0.2 T everywhere |

**Setup:**
```python
# 1. Set PM temperature
run_script(script="""
oDesign.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:MaterialProperty",
      "MaterialProp:=", "NdFe30",
      "Property:=", "Temperature",
      "Value:=", "150cel"]
    ]
)
""")

# 2. Locked rotor, apply 3-phase short
run_script(script="""
oDesign.SetDesignSettings(
    ["NAME:DesignSettings", "StopTime:=", "0.01s",
     "TimeStep:=", "5e-5s"]
)
# Short all windings
oModule = oDesign.GetModule("BoundarySetup")
oModule.AssignResistor(["NAME:Short", "Resistance:=", "0.001ohm"])
""")

# 3. Check B_min in each PM element
bg_data = get_field_data(["PM_1", "PM_2", ..., "PM_8"], "Mag_B",
                         time="<t_peak_current>")
```

**If demagnetization detected:**
1. Increase hm → re-run
2. Upgrade PM grade (N35 → N42SH) → re-run
3. Add flux barrier (IPM) → re-run

---

## §10 — NVH Quick Scan

**Purpose:** Identify risk of electromagnetic vibration and acoustic noise.

**Steps:**

1. Extract radial force density on stator teeth
2. Perform spatial FFT to identify force orders
3. Compare with structural natural frequencies (from modal analysis)
4. Calculate A-weighted sound pressure level estimate

**Setup:**
```python
# Extract radial force on each stator tooth
for tooth in range(1, Q+1):
    force_data = get_field_data(
        objects=[f"Tooth_{tooth}"],
        quantity="Force_Mag",
        time="<full cycle>",
        setup_name="RatedLoad"
    )
```

**Analysis (post-processed externally):**
```python
# Spatial FFT of radial force density
# pr(θ,t) = B_r²(θ,t) / (2μ₀) → FFT in space and time
# Identify dominant spatial orders r = |k1×2p ± k2×Q|
# Lowest non-zero order determines noise level
```

**Pass criteria:**
- Lowest non-zero spatial force order ≥ 4 (acceptable), ≥ 6 (good)
- Force harmonics avoid ±20% of stator natural frequencies
- Sound pressure level estimate < 65 dBA (office), < 75 dBA (industrial)

---

## Simulation Execution Order

Run in this exact order to minimize rework:

```
1. No-Load Back-EMF         (validates model, catches winding errors early)
2. Rated Load               (core performance data)
    │
    ├─ PASS → 3. Airgap Bg   (characterize field quality)
    │         4. Overload     (capability check)
    │         5. Iron Loss    (thermal input)
    │         6. PM Eddy Loss (if high speed or high poles)
    │         7. Inductance   (control design input)
    │         8. Thermal      (requires losses from 5-6)
    │         9. Demag        (requires temp from 8)
    │        10. NVH          (requires force data from 2)
    │
    └─ FAIL → Debug model → re-run from step 1
```

## Auto-Report Generation

After all simulations complete, generate `assets/report_template.md` populated with:
- All simulation plots embedded as images
- Performance summary table with pass/fail against targets
- Pareto front visualization (if optimization was run)
- Manufacturing recommendations
- BOM cost breakdown
