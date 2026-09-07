# Troubleshooting Guide — Ansys Maxwell Motor Design

## Quick Diagnostic Flowchart

```
                    ╔══════════════════╗
                    ║ ISSUE DETECTED?  ║
                    ╚══════╤═══════════╝
                           │
              ┌────────────┼────────────┐
              ▼            ▼             ▼
    ┌─────────────┐ ┌────────────┐ ┌──────────┐
    │ Geometry /  │ │  Analysis  │ │ Results  │
    │ Mesh Issue? │ │  Failure?  │ │ Wrong?   │
    └──────┬──────┘ └─────┬──────┘ └────┬─────┘
           │              │              │
           ▼              ▼              ▼
    ┌──────────┐   ┌───────────┐  ┌───────────┐
    │Check:    │   │Check:     │  │Check:     │
    │-Overlaps │   │-Mesh qual │  │-Materials │
    │-Non-manif│   │-Time step │  │-Excitations│
    │-Band gap │   │-BCs       │  │-Units     │
    │-Units    │   │-Non-lin   │  │-Time range│
    └─────┬────┘   │-Converg.  │  └─────┬─────┘
          │        └─────┬─────┘        │
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  ┌──────────────┐
                  │ Apply fix    │
                  │ from below   │
                  └──────────────┘
```

---

## 1. Geometry & Modeling Issues

### 1.1 Band Creation Fails / "Band is not a valid closed region"

**Symptoms:**
- Error: `BandGeometryError: Motion band is not a complete closed circle`
- Band object appears in object tree but analysis fails
- Rotor motion setup rejected

**Root Causes:**
1. Band is not a perfect circle (segments instead of a true circle/arc)
2. Band overlaps with rotor or stator geometry
3. Band radius is exactly at rotor surface or airgap boundary (must be mid-airgap)
4. Multiple objects intersecting the band surface

**Solutions:**
1. Use `draw_circle()` centered at (0,0) with radius exactly `(R_rotor_out + R_stator_in) / 2`
2. Ensure band does NOT touch rotor OD or stator ID — leave 0.05–0.1 mm clearance on each side
3. Use Boolean `subtract()` to split the band into inner (moving) and outer (stationary) parts
4. Verify with: `get_model_bounding_box()` on band circle

**Checklist:**
```
□ Band is a single closed circle (no segments)
□ Band radius = (R_rotor_outer + R_stator_inner) / 2
□ Band does not overlap any material objects
□ Band center is exactly (0, 0)
□ Solution type is "Transient"
□ Band is not assigned any material (it's a non-material object)
```

---

### 1.2 Boolean Operation Fails (Unite / Subtract / Intersect)

**Symptoms:**
- Error: `GeometryOverlapError: Objects do not intersect`
- Result object is empty or malformed
- Geometry tree shows incomplete object

**Root Causes:**
1. Objects don't overlap in the expected region
2. Numerical tolerance issue with imported CAD
3. Self-intersecting geometry from manual drawing
4. Duplicate overlapping objects

**Solutions:**
1. Use `get_model_bounding_box()` on each object to verify overlap regions
2. For near-touching objects, add a small clearance (0.001 mm) between them
3. Check for duplicate objects with `get_active_editor()` and remove extras
4. For imported geometry, use `heal_geometry` if available, or redraw with native Maxwell primitives
5. Simplify: break complex Boolean chains into sequential pairwise operations

---

### 1.3 Symmetry / Master-Slave Boundary Mismatch

**Symptoms:**
- Error: `Master-Slave boundary geometry mismatch`
- Analysis runs but produces asymmetric results where symmetry is expected

**Root Causes:**
1. Master and Slave boundaries not geometrically matched (different arc lengths)
2. Wrong periodicity: model sector angle ≠ 360°/gcd(poles, slots)
3. Slave boundary direction reversed relative to Master
4. Objects crossing the symmetry plane not properly split

**Solutions:**
1. Verify sector angle: `angle = 360 / N_periodicity`, where `N_periodicity = gcd(poles, slots)`
2. For 8p/12s: gcd=4, so use 90° sector
3. For 8p/9s: gcd=1, so full model required (360°)
4. Master should be the +θ edge, Slave the −θ edge of the sector
5. Delete and recreate boundaries: re-draw sector bounding lines with exact angles

---

## 2. Meshing Issues

### 2.1 Mesh Generation Fails / "Meshing Error"

**Symptoms:**
- Error: `MeshGenerationError: Cannot generate mesh`
- Analysis hangs at mesh generation phase
- Some objects fail to mesh while others succeed

**Root Causes:**
1. Extremely small features (slivers, thin gaps) smaller than min mesh size
2. Non-manifold geometry (edges shared by 3+ faces)
3. Objects with nested boundaries or holes that aren't properly defined
4. Airgap too small relative to other dimensions

**Solutions:**
1. Check minimum feature size: `min_feature > 0.001 mm` for mm-scale models
2. Relax mesh constraints temporarily: increase `max_length` values
3. Fix non-manifold issues: use `draw_polyline()` instead of line-by-line assembly
4. For very small airgaps (<0.3 mm), use scale factor: temporarily model at ×10 scale
5. Apply mesh operations object by object to isolate the problematic geometry

**Recommended mesh sizes by region:**

| Region | Min Size (mm) | Max Size (mm) | Notes |
|--------|--------------|---------------|-------|
| Airgap | 0.02 | 0.2 | Critical — use CylindricalGap operation |
| PM surface | 0.1 | 0.5 | Fine near airgap surface |
| PM interior | 0.3 | 1.0 | Coarser acceptable |
| Stator teeth | 0.2 | 1.5 | Fine near tips |
| Stator yoke | 0.5 | 3.0 | Coarse acceptable |
| Rotor yoke | 0.5 | 3.0 | Coarse acceptable |

---

## 3. Solution & Convergence Issues

### 3.1 Transient Solver Does Not Converge

**Symptoms:**
- Solver runs to `max_passes` without reaching `percent_error` target
- Adaptive mesh refinement continues indefinitely
- Results oscillate between passes

**Root Causes:**
1. Time step too large — cannot capture high-frequency content
2. Mesh not fine enough in high-gradient regions (airgap, tooth tips)
3. Nonlinear material not converging (BH curve oscillation)
4. Motion-induced remeshing instability

**Solutions:**
1. **Reduce time step:** $dt \leq 1/(100 \cdot f_{elec})$. For 200 Hz → $dt \leq 5 \times 10^{-5}$ s
2. **Improve airgap mesh:** Use `CylindricalGap` mesh operation with 4–6 layers
3. **Relax nonlinear convergence:** Increase `percent_error` from 0.1% to 0.5% temporarily
4. **Check remesh settings:** Disable auto-remeshing on motion if oscillation occurs
5. **Restart with solved fields:** Save field at last converged pass, restart from there

**Time step guidelines by frequency:**

| Electrical Frequency (Hz) | Max Time Step (s) | Steps per Electrical Cycle |
|---------------------------|-------------------|---------------------------|
| 50 | $2 \times 10^{-4}$ | 100 |
| 100 | $1 \times 10^{-4}$ | 100 |
| 200 | $5 \times 10^{-5}$ | 100 |
| 400 | $2.5 \times 10^{-5}$ | 100 |
| 800 | $1.25 \times 10^{-5}$ | 100 |

---

### 3.2 Magnetostatic Setup Returns Unreasonable Forces

**Symptoms:**
- Torque values orders of magnitude off from expected
- Force integration gives NaN or very large values
- Energy error exceeds 5%

**Root Causes:**
1. Not enough mesh refinement passes (increase `max_passes`)
2. `percent_error` too loose — residual fields cause integration errors
3. Airgap region not properly meshed for Maxwell stress tensor
4. Current excitation not applied to correct objects

**Solutions:**
1. Increase `max_passes` to 20–25
2. Tighten `percent_error` to 0.05%
3. Add dedicated airgap mesh operation (CylindricalGap type) with at least 4 layers
4. Verify excitation: `get_active_editor()` then check current assignments on each object
5. For torque, use both Maxwell stress tensor AND virtual work method and cross-check

---

## 4. Results & Post-Processing Issues

### 4.1 Back-EMF Waveform Distorted or Wrong Amplitude

**Symptoms:**
- Back-EMF amplitude very different from analytical prediction (>20% error)
- Waveform is triangular/sawtooth instead of sinusoidal
- Phase shift between phases incorrect

**Root Causes:**
1. Wrong speed applied: verify `angular_velocity` in `assign_band()` matches intended RPM
2. PM magnetization direction wrong (rotated 90° or inverted)
3. Wrong number of turns or parallel branches in winding
4. Transient initialization: first cycle has startup transient
5. Mesh not fine enough to capture flux linkage accurately

**Solutions:**
1. **Verify speed:** Band `angular_velocity` in RPM (not rad/s!)
2. **Check magnetization:** Each PM should point radially (for SPM) with alternating N/S poles
3. **Turns verification:** Calculate expected Back-EMF using §3.2 formula; compare
4. **Discard first cycle:** Use data from cycles 2–3 only for steady-state analysis
5. **Verify with formula:** $E_{rms} = k_e \cdot \omega_m$, where $k_e$ from RMxprt

**Open-circuit Back-EMF test checklist:**
```
□ Current excitation set to 0 (open-circuit simulation)
□ Band speed set to rated RPM
□ Run for 2 complete electrical cycles
□ Extract induced voltage from all 3 phases
□ Verify 120° phase separation
□ Compare RMS value to analytical prediction
```

---

### 4.2 Torque Ripple Higher Than Expected

**Symptoms:**
- FEA torque ripple 2–3× larger than analytical estimate
- Cogging torque component dominates
- Ripple waveform has unexpected harmonics

**Root Causes:**
1. Mesh not fine enough in airgap (false torque ripple from mesh noise)
2. Rotor initial position not aligned properly
3. Step size too large — skipping high-frequency ripple components
4. PM edge effects: sharp magnet corners cause local saturation

**Solutions:**
1. **Airgap mesh:** Reduce max element size in airgap to ≤0.1 mm
2. **Time step:** Use at least 200 steps per electrical cycle
3. **Rotor alignment:** Set initial rotor angle to minimize transient
4. **Add fillets/rounding:** 0.2–0.5 mm fillet on magnet edges reduces local saturation
5. **Post-process:** Apply moving average filter to separate electromagnetic torque from cogging

---

### 4.3 Airgap Flux Density Extraction Fails

**Symptoms:**
- `get_field_data()` on airgap line returns empty array or unexpected values
- Radial/tangential components incorrectly decomposed
- FFT of airgap B gives spectral leakage or false harmonics

**Root Causes:**
1. Field data extraction point is not on the analysis contour (outside model domain)
2. The extraction line/arc was created AFTER analysis — data not stored
3. Sampling points too few for FFT (Nyquist violation)
4. Cartesian (Bx, By) not being transformed to cylindrical (Br, Bt)

**Solutions:**
1. **Create contour BEFORE analysis:** Draw a non-model circle at airgap center radius using `draw_circle()` but do NOT assign material. Name it distinctly (e.g., "Airgap_Contour"). Maxwell treats it as a non-model object and stores field data along it.
2. **Sample count:** Use at least 720 points (0.5° resolution) for FFT up to 360th harmonic
3. **Coordinate transform:** Convert from Cartesian to cylindrical:

```python
# Transform Bx, By to Br, Bt at each point (x, y) on contour
import math
for i in range(n_points):
    theta = math.atan2(y[i], x[i])
    Br = Bx[i] * math.cos(theta) + By[i] * math.sin(theta)
    Bt = -Bx[i] * math.sin(theta) + By[i] * math.cos(theta)
```

4. **Verify contour radius:** Must be within the airgap: $R_{rotor} + 0.05 < r_{contour} < R_{stator} - 0.05$

---

### 4.4 FFT Analysis Gives Unexpected Harmonics

**Symptoms:**
- FFT of airgap flux density shows strong even-order harmonics where only odd-orders expected
- Sub-harmonics appear below the fundamental
- Spectral spreading (leakage) across multiple bins

**Root Causes:**
1. **Non-integer period sampling:** FFT window does not cover exactly N complete electrical cycles
2. **Transient startup included:** First cycle contains DC transient
3. **Uneven spatial sampling:** Arc length errors in contour geometry
4. **Aliasing:** Spatial sampling rate < 2 × highest spatial frequency of interest
5. **Incorrect FFT reference:** Performing FFT on single time instant instead of space
6. For spatial FFT: the contour must be a complete circle, not a partial sector

**Solutions:**
1. **Integer cycles:** Ensure simulation covers exactly 2–3 complete electrical cycles ($t_{stop} = N \cdot T_{elec}$, where N is integer)
2. **Window function:** Apply Hann or Hamming window to reduce spectral leakage
3. **Spatial FFT validation:**
   - Number of spatial samples must be power of 2 (e.g., 1024, 2048)
   - Contour must be full 360° circle
   - Check that Br(0°) ≈ Br(360°) (periodic)
4. **Separate space and time FFT:**
   - 2D FFT: `Br(theta, time)` → FFT2D → extract spatial orders vs temporal harmonics
   - Or: extract Br(theta) at one time instant for spatial FFT only
5. **Verify harmonics table:**

| For 8p/12s motor: | Expected Orders |
|-------------------|-----------------|
| Working harmonics | 4th, 20th, 28th, 44th, 52nd... |
| Slot harmonics | $k \cdot Q_s/p \pm 1 = 3k \pm 1$: 2, 4, 5, 7, 8, 10... |
| PM harmonics | Odd: 5th, 7th, 11th, 13th... (for distributed winding) |

---

### 4.5 Iron Loss Over-Estimated in FEA

**Symptoms:**
- FEA core loss 2–3× higher than RMxprt prediction
- Loss concentrated in tooth tips
- Loss varies significantly with mesh density

**Root Causes:**
1. Incorrect Bertotti coefficients ($k_h$, $k_e$, $k_{exc}$) for the lamination grade
2. Minor loops not accounted for (FEA includes all B reversals, including PWM ripple)
3. Mesh-induced flux density noise at tooth tips
4. Rotational loss not separated from alternating loss

**Solutions:**
1. **Verify Bertotti coefficients** against §5.1 material database
2. **Apply build factor:** Multiply raw FEA loss by 0.5–0.7 for manufactured stack (accounts for inter-laminar insulation, stress relief annealing, etc.)
3. **Smooth mesh at tooth tips:** Reduce max element size to ≤0.5 mm at tooth tips
4. **Build factor reference table:**

| Lamination Grade | Typical Build Factor | Notes |
|-----------------|---------------------|-------|
| M270-35A | 0.55–0.65 | Standard annealing |
| M330-35A | 0.60–0.70 | Standard annealing |
| 35JN250 | 0.50–0.60 | Japanese grade, tight tolerance |
| 10JNEX900 | 0.70–0.80 | Amorphous, less degradation |
| NO20 | 0.80–0.85 | Amorphous ribbon |

---

## 5. Optimization & Parametric Issues

### 5.1 Optimization Converges to Infeasible Design

**Symptoms:**
- Optimization runs complete but final design violates constraints
- Best design has unrealistic geometry (negative thickness, zero airgap)
- Genetic algorithm converges on boundary of parameter space

**Root Causes:**
1. **Constraint not enforced during evaluation:** Soft constraints in objective function get ignored
2. **Variable bounds too wide:** Permits geometrically impossible combinations
3. **Single-objective optimization ignores secondary requirements**
4. **Discrete variables treated as continuous:** Non-integer slots, poles, turns
5. **Cost function poorly scaled:** One term dominates optimization

**Solutions:**
1. **Tighten variable bounds:**
   ```python
   # Instead of:
   $airgap: {min: 0.1, max: 5.0}
   # Use:
   $airgap: {min: 0.5, max: 2.0}  # physically realistic
   ```

2. **Add geometric feasibility checks:** Post-evaluation validation:
   ```
   Is $stator_inner > $rotor_outer + 2*$airgap_min ?
   Is $slot_depth < ($stator_outer - $stator_inner)/2 ?
   Is tooth_width > 0 ?
   ```

3. **Use multi-objective optimization:** Assign weights to efficiency, torque ripple AND feasibility
4. **Penalize infeasible designs:** Add penalty term to objective function

### 5.2 Parameter Auto-Complete Produces Unrealistic Values

**Symptoms:**
- RMxprt auto-complete suggests slot depth = 80 mm for a 120 mm diameter motor
- Winding turns auto-calculated to 0.2 (obviously wrong)
- Slot fill factor auto-calculated to 0.95 (impossible to manufacture)

**Root Causes:**
1. **RMxprt falls back to default internal ratios** when input parameters are incomplete
2. **Conflicting inputs:** Speed and voltage combination requires unrealistic flux levels
3. **Extreme operating point:** Very high torque density pushes geometry beyond practical limits
4. **Template mismatch:** Using PMSM template for IPM or vice versa

**Solutions:**
1. **Provide more input parameters:** RMxprt needs at minimum: $D_{so}$, $L_{stk}$, poles, rated speed, rated power, magnet grade
2. **Check RMxprt assumptions:**
   - Split ratio ($D_{si}/D_{so}$) typically 0.55–0.65 for PMSM
   - Electric loading typically 20,000–40,000 A/m
   - Current density typically 4–8 A/mm²
3. **Override auto-calculated values** and re-run RMxprt
4. **Validate against design rules** in Appendix A of motor_design_guide.md before accepting

---

## 6. Performance & Workflow Issues

### 6.1 Analysis Takes Too Long

**Symptoms:**
- Single transient run exceeds 1 hour
- Memory usage exceeds available RAM
- Disk space consumption too high

**Solutions:**
1. **Use symmetry:** Reduce model to smallest periodicity: gcd(poles, slots)
2. **Coarsen initial mesh:** Start with relaxed mesh, refine only in final runs
3. **Reduce save fields frequency:** Set `save_fields_step` to every 10–20 time steps
4. **Use RMxprt first:** Analytical sizing before committing to FEA
5. **Disable unnecessary computations:** Turn off core loss, eddy effect if not needed for current analysis
6. **Hardware scaling:**
   - Use SSD for project storage
   - Assign more cores in Maxwell HPC options
   - 16 GB RAM minimum for 2D; 64 GB for 3D

---

## 7. Quick Reference: Error-to-Fix Mapping

| Error Message | Most Likely Cause | Quick Fix |
|--------------|-------------------|-----------|
| `ObjectNotFoundError` | Wrong object name or design not active | `get_active_editor()` to verify object list |
| `MaterialNotFoundError` | Material missing from project | `list_materials()`, then add via material library |
| `AnalysisFailedError: Convergence` | Mesh too coarse or time step too large | Reduce time step, refine airgap mesh |
| `AnalysisFailedError: Singular matrix` | Floating region or missing BCs | Apply boundary conditions, check all objects have material |
| `BandGeometryError` | Band not a closed circle in airgap | Redraw band with `draw_circle()` at mid-airgap radius |
| `GeometryOverlapError` | Boolean objects don't intersect | Check bounding boxes, add tolerance |
| `FileNotFoundError` | Project file moved or deleted | Use absolute paths, verify file exists |
| `UnitMismatchError` | Inconsistent units across operations | `set_model_units("mm")` at script start |
| `MemoryError` | Model too large for available RAM | Use symmetry, coarsen mesh, or switch to 2D |
| `LicenseError` | Maxwell license not available | Check license server, close unused sessions |
