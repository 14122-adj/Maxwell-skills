# MCP Tools Reference — Ansys Maxwell Motor Design

## Overview

This document catalogs all MCP tools available for Ansys Maxwell automation via the WorkBuddy integration. Tools are organized by functional domain. Each entry includes: function signature, parameter descriptions, pre-conditions, return values, and usage notes.

---

## Project & Design Management

### `create_project(project_name, directory)`

Create a new Maxwell project.

- **Parameters:**
  - `project_name` (str): Name of the new project. Must be unique in the workspace.
  - `directory` (str): Absolute path where project files are stored.
- **Pre-conditions:** Directory must exist, project name must not conflict with existing.
- **Returns:** Project object with `project_id` and status.
- **Notes:** Creates `.aedt` project file. Call `save_project()` after modifications.

### `open_project(project_path)`

Open an existing Maxwell `.aedt` project file.

- **Parameters:**
  - `project_path` (str): Absolute path to `.aedt` file.
- **Pre-conditions:** File must exist and be a valid Maxwell project.
- **Returns:** Loaded project object.
- **Notes:** Sets the project as active in the Maxwell session.

### `save_project()`

Save the currently active project.

- **Parameters:** None
- **Pre-conditions:** An active project must be loaded.
- **Returns:** Boolean success flag.
- **Notes:** Auto-save is not enabled by default; call explicitly after modeling operations.

### `close_project(project_name)`

Close a specific project.

- **Parameters:**
  - `project_name` (str): Name of the project to close.
- **Pre-conditions:** Project must be loaded.
- **Returns:** Boolean success flag.
- **Notes:** Unsaved changes will be lost. Save first.

---

## Design Creation & Setup

### `create_maxwell_2d_design(design_name, solution_type)`

Create a 2D Maxwell design within the active project.

- **Parameters:**
  - `design_name` (str): Unique design name (e.g., "Motor_EM_2D").
  - `solution_type` (str): One of `"Magnetostatic"`, `"Transient"`, `"EddyCurrent"`, `"Electrostatic"`.
- **Pre-conditions:** Active project must be loaded.
- **Returns:** Design object with `design_id`.
- **Notes:** For motor analysis, use `"Transient"` for time-domain or `"Magnetostatic"` for static snapshots.

### `create_maxwell_3d_design(design_name, solution_type)`

Create a 3D Maxwell design.

- **Parameters:**
  - `design_name` (str): Unique design name.
  - `solution_type` (str): As above, also accepts `"Transient3D"`.
- **Pre-conditions:** Active project loaded.
- **Returns:** Design object.
- **Notes:** 3D designs are computationally expensive. Use only when 2D symmetry is insufficient (e.g., axial flux motors, end-winding effects).

### `create_rmxprt_design(design_name, machine_type)`

Create an RMxprt analytical design.

- **Parameters:**
  - `design_name` (str): Unique name (e.g., "Motor_RMxprt").
  - `machine_type` (str): Machine type identifier. Common values: `"PMSM"`, `"IM"`, `"SynRM"`, `"DC"`, `"BLDC"`, `"PMDC"`, `"SRM"`, `"LSPMSM"`.
- **Pre-conditions:** Active project loaded.
- **Returns:** RMxprt design object.
- **Notes:** RMxprt uses analytical models for fast sizing. Results should be validated with FEA.

### `create_maxwell_2d_from_rmxprt(rmxprt_design, maxwell_design, auto_setup=True)`

Convert an RMxprt design to a Maxwell 2D FEA design.

- **Parameters:**
  - `rmxprt_design` (str): Source RMxprt design name.
  - `maxwell_design` (str): Target Maxwell 2D design name.
  - `auto_setup` (bool): If True, auto-generates mesh and motion setup. Default True.
- **Pre-conditions:** RMxprt design must be analyzed successfully.
- **Returns:** Created Maxwell 2D design object.
- **Notes:** Defaults to 1/N symmetry where N is the periodicity. Creates transient setup with rated speed.

---

## Geometry Creation

### `draw_rectangle(name, position, width, height, color)`

Draw a 2D rectangle.

- **Parameters:**
  - `name` (str): Object name (must be unique in design).
  - `position` (tuple[float, float]): (x, y) of bottom-left corner in model units.
  - `width` (float): X dimension.
  - `height` (float): Y dimension.
  - `color` (tuple[int,int,int]): RGB values (0–255). Optional, defaults to (0,255,0).
- **Pre-conditions:** Active design must be a 2D design.
- **Returns:** Created object reference.
- **Notes:** Coordinates are in the model coordinate system. Use `set_model_units()` first.

### `draw_circle(name, center, radius, color)`

Draw a 2D circle.

- **Parameters:**
  - `name` (str): Object name.
  - `center` (tuple[float, float]): (x, y) center coordinates.
  - `radius` (float): Circle radius.
  - `color` (tuple[int,int,int]): Optional RGB.
- **Pre-conditions:** Active 2D design.
- **Returns:** Created object reference.

### `draw_arc(name, center, start_angle, end_angle, radius, color)`

Draw a 2D arc.

- **Parameters:**
  - `name` (str): Object name.
  - `center` (tuple[float, float]): Arc center.
  - `start_angle` (float): Start angle in degrees (0° = +X axis, CCW).
  - `end_angle` (float): End angle in degrees.
  - `radius` (float): Arc radius.
  - `color` (tuple[int,int,int]): Optional RGB.
- **Pre-conditions:** Active 2D design.
- **Returns:** Created object reference.
- **Notes:** Used for slot arcs, magnet edges, and fillet definitions.

### `draw_polyline(name, points)`

Draw a 2D polyline from a list of points.

- **Parameters:**
  - `name` (str): Object name.
  - `points` (list[tuple[float,float]]): Ordered list of (x,y) vertex coordinates.
- **Pre-conditions:** Active 2D design. Minimum 2 points.
- **Returns:** Created polyline object reference.
- **Notes:** Does NOT auto-close. For closed shapes (slots, magnets), ensure the last point equals the first point, or use `Boolean operations` to close the loop.

### `draw_line(name, start_point, end_point)`

Draw a single straight line segment.

- **Parameters:**
  - `name` (str): Object name.
  - `start_point` (tuple[float, float]): Starting (x, y).
  - `end_point` (tuple[float, float]): Ending (x, y).
- **Pre-conditions:** Active 2D design.
- **Returns:** Created line object reference.

### `draw_region_pad(name, padding)`

Create a boundary region around the model.

- **Parameters:**
  - `name` (str): Region name.
  - `padding` (dict): Padding offsets, e.g. `{"X": 50, "Y": 50, "direction": "absolute"}` for mm offsets, or `{"X": 20, "Y": 20, "direction": "percentage"}` for percentage of model extent.
- **Pre-conditions:** Model geometry must exist.
- **Returns:** Region object reference.
- **Notes:** Required for FEA boundary conditions. Typical padding: 20–50% of motor diameter.

---

## Boolean Operations

### `unite(objects, name)`

Union (merge) two or more 2D objects into a single object.

- **Parameters:**
  - `objects` (list[str]): Names of objects to unite. Minimum 2.
  - `name` (str): Name for the resulting united object.
- **Pre-conditions:** All objects must exist in the active 2D design. Objects must overlap or touch.
- **Returns:** Created united object reference.
- **Notes:** Original objects are consumed. Useful for creating complex pole shapes or combined slot+wedge geometry.

### `subtract(blank_objects, tool_objects, name, keep_originals=False)`

Subtract tool objects from blank objects (Boolean difference).

- **Parameters:**
  - `blank_objects` (list[str]): Objects to subtract FROM (the blanks).
  - `tool_objects` (list[str]): Objects to subtract WITH (the tools).
  - `name` (str): Name for the resulting object.
  - `keep_originals` (bool): If True, preserves original objects. Default False.
- **Pre-conditions:** All objects must exist in active 2D design. Tools must intersect blanks.
- **Returns:** Created subtracted object reference.
- **Notes:** Common use: creating airgap by subtracting rotor from stator region, or magnet slots by subtracting magnets from rotor.

### `intersect(objects, name, keep_originals=False)`

Compute intersection (common area) of two or more objects.

- **Parameters:**
  - `objects` (list[str]): Objects to intersect. Minimum 2.
  - `name` (str): Name for the resulting intersection.
  - `keep_originals` (bool): If True, preserves original objects. Default False.
- **Pre-conditions:** All objects must exist and overlap in active 2D design.
- **Returns:** Created intersection object reference.
- **Notes:** Useful for extracting overlap regions, winding cross-sections multiplied by fill factor, etc.

---

## Duplication & Symmetry

### `duplicate_along_line(objects, vector, n, attach=True)`

Linear array duplication.

- **Parameters:**
  - `objects` (list[str]): Objects to duplicate.
  - `vector` (tuple[float, float]): (dx, dy) spacing vector in model units.
  - `n` (int): Total number of copies (original + n−1 duplicates).
  - `attach` (bool): If True, merges duplicates. Default True.
- **Pre-conditions:** Objects must exist. `n >= 1`.
- **Returns:** List of created objects (or single merged object if `attach=True`).

### `duplicate_around_axis(objects, axis, angle, n, attach=True)`

Circular (polar) array duplication — essential for motor geometry.

- **Parameters:**
  - `objects` (list[str]): Objects to duplicate (typically one pole/slot).
  - `axis` (str): Axis of rotation. For 2D: `"Z"` (default, rotates about origin). Can also specify a point `(x, y)`.
  - `angle` (float): Angular spacing in degrees between copies.
  - `n` (int): Total number of copies.
  - `attach` (bool): If True, merges all copies. Default True.
- **Pre-conditions:** Objects must exist. `angle * (n−1)` must not exceed 360°.
- **Returns:** List of created objects.
- **Notes:** Core pattern for motor modeling — create one slot/pole, duplicate around Z-axis with 360/slots or 360/poles degrees.

### `mirror(objects, mirror_line, name)`

Mirror objects about a line in 2D.

- **Parameters:**
  - `objects` (list[str]): Objects to mirror.
  - `mirror_line` (tuple[tuple, tuple]): Two points defining mirror line, e.g. `((0,0), (1,0))` for X-axis.
  - `name` (str): Base name for mirrored objects.
- **Pre-conditions:** Objects must exist.
- **Returns:** List of mirrored object references.

### `assign_symmetry(objects, symmetry_type, name)`

Assign symmetry boundary condition to selected objects (edges/faces).

- **Parameters:**
  - `objects` (list[str]): Edge or face names to apply symmetry.
  - `symmetry_type` (str): One of `"Odd"` (magnetic — B normal=0, H tangential=0), `"Even"` (electric — B tangential=0, H normal=0), or `"Master"`/`"Slave"` for periodic.
  - `name` (str): Symmetry boundary name.
- **Pre-conditions:** Objects must be edges or faces of the model. Master/Slave boundaries must pair correctly.
- **Returns:** Symmetry boundary object.
- **Notes:** For fractional-slot motors, use Master/Slave on the symmetry sector boundaries. Odd/Even are used for full-model symmetry planes.

---

## Material Assignment

### `assign_material(objects, material_name)`

Assign a material to geometric objects.

- **Parameters:**
  - `objects` (list[str]): Object names to receive material.
  - `material_name` (str): Material name from Maxwell material library or custom materials.
- **Pre-conditions:** Objects must exist. Material must be in the project material list. For PMs, the material must include magnetization direction.
- **Returns:** Boolean success flag.
- **Notes:** Common materials: `"M270-35A"`, `"M400-50A"`, `"NdFeB_N42SH"`, `"copper"`, `"vacuum"` (for airgap), `"aluminum"`.

### `set_magnet_orientation(objects, direction, reference_cs="Global")`

Set magnetization direction for PM objects.

- **Parameters:**
  - `objects` (list[str]): PM object names.
  - `direction` (tuple[float, float]): Normalized (x, y) magnetization vector. For radial magnets: direction from rotor center to magnet center.
  - `reference_cs` (str): Coordinate system. Default `"Global"`.
- **Pre-conditions:** Objects must have a PM material assigned.
- **Returns:** Boolean success flag.
- **Notes:** For Halbach arrays, each segment needs its own orientation. For V-shaped IPM, orientation follows the V-angle.

### `list_materials()`

List all materials available in the current project material library.

- **Parameters:** None
- **Pre-conditions:** Active project with at least one design.
- **Returns:** List of material name strings.
- **Notes:** Includes system materials, RMxprt materials, and any custom materials added to the project. Use to verify material availability before assignment.

---

## Excitation Assignment

### `assign_current_excitation(objects, phase, current_function, name)`

Assign current excitation to winding objects.

- **Parameters:**
  - `objects` (list[str]): Winding/cross-section objects.
  - `phase` (str): Phase identifier: `"A"`, `"B"`, `"C"`.
  - `current_function` (str): Current expression. Examples: `"I_peak * sin(2*pi*freq*time + gamma)"`, `"I_peak * sin(2*pi*freq*time + gamma - 2*pi/3)"` (Phase B, −120°).
  - `name` (str): Excitation name (e.g., `"PhaseA_Current"`).
- **Pre-conditions:** Objects must be assigned winding material. For transient solutions, time variable is available.
- **Returns:** Excitation object reference.

### `assign_voltage_excitation(objects, phase, voltage_function, resistance, inductance, name)`

Assign voltage excitation (used for voltage-driven simulations).

- **Parameters:**
  - `objects` (list[str]): Winding objects.
  - `phase` (str): `"A"`, `"B"`, `"C"`.
  - `voltage_function` (str): Voltage expression, e.g., `"V_peak * sin(2*pi*freq*time)"`.
  - `resistance` (float): Phase resistance in Ohms.
  - `inductance` (float): End-winding inductance in Henries.
  - `name` (str): Excitation name.
- **Pre-conditions:** Objects assigned winding material.
- **Returns:** Excitation object reference.

### `create_winding_setup(name, winding_type="Current")`

Create a winding setup that groups phases.

- **Parameters:**
  - `name` (str): Winding setup name (e.g., `"ThreePhase_Winding"`).
  - `winding_type` (str): `"Current"`, `"Voltage"`, or `"External"` (for circuit coupling).
- **Pre-conditions:** Phase excitations should be created before the winding setup.
- **Returns:** Winding setup object reference.

---

## Motion & Band Setup

### `assign_band(objects, angular_velocity, axis, name)`

Assign a rotating motion band to objects — essential for motor rotation simulation.

- **Parameters:**
  - `objects` (list[str]): Objects within the band region (typically rotor assembly, magnets, shaft).
  - `angular_velocity` (float): Rotation speed in RPM. Can be a constant or a function of time, e.g., `"3000"` or `"speed_rpm"`.
  - `axis` (str): Rotation axis. For 2D: `"Z"`. Center of rotation is the origin (0,0) by default.
  - `name` (str): Band object name (e.g., `"MotionBand_Rotor"`).
- **Pre-conditions:** 
  - Objects must form a contiguous rotating region.
  - A band object (typically an arc-segment circle) must exist between rotor outer surface and airgap.
  - Valid for `"Transient"` solution type only.
- **Returns:** Motion setup object reference.
- **Notes:** The band is a non-material object in Maxwell. It must be perfectly circular and concentric with the rotation axis. Typical band radius = (R_rotor + R_stator_inner) / 2.

---

## Mesh Operations

### `assign_mesh_operation(objects, operation_type, max_length, name)`

Apply mesh refinement to selected objects for improved FEA accuracy.

- **Parameters:**
  - `objects` (list[str]): Objects to apply mesh refinement.
  - `operation_type` (str): Mesh operation type:
    - `"LengthBased"` — Specifies maximum element edge length.
    - `"SkinDepth"` — Refines based on skin depth for eddy current analysis.
    - `"CylindricalGap"` — Specialized for airgap meshing.
  - `max_length` (float): Maximum element edge length in model units (mm). Typical values:
    - Airgap: 0.05–0.2 mm (critical for accurate torque)
    - Magnets: 0.5–1.0 mm
    - Stator teeth: 1.0–2.0 mm
    - Yoke: 2.0–4.0 mm
  - `name` (str): Mesh operation name.
- **Pre-conditions:** Objects must exist in the active design.
- **Returns:** Mesh operation object reference.
- **Notes:** For `"CylindricalGap"` type, the object should be the airgap region. This creates a structured mesh layer in the airgap for superior torque computation accuracy.

### `assign_mesh_skin_depth(objects, frequency, skin_depth_layers, name)`

Specialized mesh for eddy current regions (magnets, conductors).

- **Parameters:**
  - `objects` (list[str]): Objects with induced eddy currents.
  - `frequency` (float): Fundamental frequency in Hz.
  - `skin_depth_layers` (int): Number of mesh layers within skin depth. Typical: 2–3.
  - `name` (str): Mesh operation name.
- **Pre-conditions:** Objects must have non-zero conductivity.
- **Returns:** Mesh operation object reference.

---

## Analysis Setup

### `add_magnetostatic_setup(setup_name, percent_error=0.1, max_passes=15)`

Add a magnetostatic analysis setup for DC magnetic field solutions.

- **Parameters:**
  - `setup_name` (str): Setup name, e.g., `"Magnetostatic_Setup1"`.
  - `percent_error` (float): Convergence error target as percentage. Default 0.1%. Lower values increase accuracy and solve time.
  - `max_passes` (int): Maximum adaptive mesh refinement passes. Default 15. Higher values allow finer adaptive meshing.
- **Pre-conditions:** Active 2D/3D design with `"Magnetostatic"` solution type. Geometry and materials must be assigned. Exciations (currents, magnets) must be defined.
- **Returns:** Analysis setup object reference.
- **Notes:** Use for rapid static analysis (cogging torque, flux density maps, inductance at fixed rotor positions). Not suitable for time-varying phenomena (use Transient instead).

### `add_transient_setup(setup_name, stop_time, time_step, save_fields_step=None)`

Add a transient analysis setup.

- **Parameters:**
  - `setup_name` (str): Setup name (e.g., `"Transient_Setup1"`).
  - `stop_time` (float): Simulation end time in seconds. Should cover at least 1 electrical cycle: `stop_time = N_cycles / freq`.
  - `time_step` (float): Time step in seconds. Rule of thumb: `time_step < 1 / (freq * 100)`. For 3000 RPM 8-pole motor (freq=200 Hz): time_step ≤ 5e-5 s.
  - `save_fields_step` (float): Interval at which field data is saved. If None, saves every time step.
- **Pre-conditions:** Active 2D/3D design with `"Transient"` solution type. Motion band must be assigned with angular velocity.
- **Returns:** Analysis setup object reference.
- **Notes:** For steady-state torque ripple analysis, run at least 2–3 electrical cycles and discard the first cycle as transient.

### `add_eddy_current_setup(setup_name, frequency, percent_error=0.5)`

Add an eddy current analysis setup.

- **Parameters:**
  - `setup_name` (str): Setup name.
  - `frequency` (float): Excitation frequency in Hz.
  - `percent_error` (float): Convergence target as %. Default 0.5.
- **Pre-conditions:** Active design with `"EddyCurrent"` solution type. Magnet eddy current modeling requires this setup type.
- **Returns:** Analysis setup object reference.

---

## Analysis Execution

### `analyze_setup(design_name, setup_name)`

Run a single analysis setup.

- **Parameters:**
  - `design_name` (str): Design containing the setup.
  - `setup_name` (str): Setup to analyze.
- **Pre-conditions:** Setup must be fully configured (geometry, materials, mesh, excitations).
- **Returns:** Boolean success flag.
- **Notes:** Blocks until analysis completes or fails.

### `analyze_all()`

Run all analysis setups in all designs of the active project.

- **Parameters:** None
- **Pre-conditions:** Active project with configured setups.
- **Returns:** Dictionary mapping `{design_name: {setup_name: success_flag}}`.
- **Notes:** Convenience function for batch analysis. Order is: RMxprt designs first, then Maxwell designs in creation order.

---

## Results & Field Data

### `get_field_data(objects, quantity, time, setup_name)`

Extract field data at specified time step.

- **Parameters:**
  - `objects` (list[str]): Objects or geometric entities to query (e.g., `["Rotor", "Stator"]`, `["Airgap_Line"]`, or element IDs).
  - `quantity` (str): Field quantity to extract. Common values:
    - `"B"` — Magnetic flux density (vector)
    - `"H"` — Magnetic field intensity (vector)
    - `"J"` — Current density (vector)
    - `"Energy"` — Magnetic energy density
    - `"CoreLoss"` — Iron loss density
    - `"OhmicLoss"` — Ohmic loss density
  - `time` (float): Time instant in seconds (for transient). Use `"last"` for final time step. For magnetostatic, use `0`.
  - `setup_name` (str): Setup name from which to extract data.
- **Pre-conditions:** Solution must exist for the specified setup and time step.
- **Returns:** Dictionary mapping `{object_name: field_values}`. For vector quantities, returns `{"x": [...], "y": [...], "z": [...]}`.
- **Notes:** For airgap flux density extraction, create a non-model circular line at the airgap center radius before analysis.

### `get_torque(setup_name, object_names=None)`

Extract torque data over time.

- **Parameters:**
  - `setup_name` (str): Setup name.
  - `object_names` (list[str]): Objects to compute torque on. If None, computes on all objects in the band.
- **Pre-conditions:** Transient setup must be analyzed. Motion band must be assigned.
- **Returns:** Dictionary with `{"time": [...], "torque": [...]}` arrays.
- **Notes:** Uses Maxwell Stress Tensor integration. Torque on moving (band) objects is the electromagnetic torque.

### `get_induced_voltage(setup_name, winding_name)`

Extract induced voltage (Back-EMF) for a winding.

- **Parameters:**
  - `setup_name` (str): Setup name with winding.
  - `winding_name` (str): Winding setup name.
- **Pre-conditions:** Transient setup analyzed. Winding must be defined with current or voltage excitation.
- **Returns:** Dictionary with `{"time": [...], "phase_A": [...], "phase_B": [...], "phase_C": [...]}`.
- **Notes:** For open-circuit BEMF, set current to 0 in the excitation or use a very high resistance voltage source.

### `get_rmxprt_output(design_name, quantity)`

Extract RMxprt design outputs.

- **Parameters:**
  - `design_name` (str): RMxprt design name.
  - `quantity` (str): Output quantity or `"all"` for full report. Specific quantities: `"BackEMF"`, `"Torque"`, `"Efficiency"`, `"Current"`, `"SlotFill"`, `"Losses"`, `"FluxDensity"`, `"Thermal"`.
- **Pre-conditions:** RMxprt design must be analyzed.
- **Returns:** For `"all"`: full dict of all results. For specific: single value or dict.
- **Notes:** RMxprt provides analytical estimates. Compare with FEA for critical parameters.

### `get_loss_data(setup_name)`

Extract loss breakdown from FEA results.

- **Parameters:**
  - `setup_name` (str): Setup name.
- **Pre-conditions:** Transient setup analyzed. Core loss must be enabled in the excitation setup.
- **Returns:** Dictionary with `{"stator_yoke_loss": [...], "stator_tooth_loss": [...], "rotor_loss": [...], "pm_eddy_loss": [...], "copper_loss": [...], "total_loss": [...]}` arrays over time.
- **Notes:** Core loss computed via Bertotti model. Requires correct $k_h$, $k_e$, $k_{exc}$ coefficients in material properties.

### `export_data(file_path, expressions, setup_name, design_name=None, objects=None)`

Export simulation data to external file.

- **Parameters:**
  - `file_path` (str): Output file path. Extension determines format: `.csv`, `.txt`, `.tab`.
  - `expressions` (list[str]): Expressions to export, e.g., `["Moving1.Torque", "Time", "CoreLoss"]`.
  - `setup_name` (str): Setup name for data source.
  - `design_name` (str): Optional design name. If None, uses active design.
  - `objects` (list[str]): Optional list of objects to include in export.
- **Pre-conditions:** Setup must be analyzed successfully.
- **Returns:** Path to exported file.
- **Notes:** Common expressions: `"Moving1.Torque"`, `"InputCurrent(PhaseA)"`, `"InducedVoltage(PhaseA)"`, `"CoreLoss"`, `"StrandedLoss"`.

### `export_model(file_path, format)`

Export the geometric model to an external CAD format.

- **Parameters:**
  - `file_path` (str): Output file path with appropriate extension.
  - `format` (str): Export format. Supported: `"STEP"`, `"IGES"`, `"SAT"`, `"DXF"` (2D only), `"SM2"`, `"SM3"`.
- **Pre-conditions:** Active design with geometry.
- **Returns:** Path to exported file.
- **Notes:** STEP is preferred for CAD interoperability. DXF is useful for 2D manufacturing drawings.

---

## Parameterization & Optimization

### `create_variable(name, value, unit="")`

Define a project-level variable for parametric analysis.

- **Parameters:**
  - `name` (str): Variable name (start with `$` by convention, e.g., `"$magnet_thickness"`).
  - `value` (float): Initial value.
  - `unit` (str): Unit string, e.g., `"mm"`, `"deg"`, `""`. Default empty.
- **Pre-conditions:** Variable name must be unique.
- **Returns:** Variable object reference.
- **Notes:** Use `$variable_name` in all geometry and setup parameters to enable parametric sweeping.

### `create_optimization_setup(goals, variables, constraints, algorithm="Genetic")`

Create an optimization study.

- **Parameters:**
  - `goals` (list[dict]): Optimization goals, each with `{"expression": str, "condition": "Minimize"/"Maximize", "weight": float}`.
  - `variables` (list[dict]): Variables to vary, each with `{"name": "$var", "min": float, "max": float, "step": float}`.
  - `constraints` (list[dict]): Constraints, each with `{"expression": str, "condition": "<="/">="/"==", "value": float}`.
  - `algorithm` (str): `"Genetic"`, `"Pattern"`, or `"Gradient"`. Default `"Genetic"` for robustness.
- **Pre-conditions:** Project variables must be defined.
- **Returns:** Optimization setup object reference.

### `create_parametric_setup(variables, sweep_type="LinearStep")`

Create a parametric sweep.

- **Parameters:**
  - `variables` (list[dict]): Variables to sweep, each with `{"name": "$var", "start": float, "stop": float, "step": float}`.
  - `sweep_type` (str): `"LinearStep"`, `"LinearCount"`, or `"SingleValue"`.
- **Pre-conditions:** Variables defined.
- **Returns:** Parametric setup object reference.

---

## View & Utility

### `get_active_editor()`

Get the currently active editor (design) context.

- **Parameters:** None
- **Pre-conditions:** A project must be loaded.
- **Returns:** Editor object with properties: `design_name`, `solution_type`, `is_2d`, `is_3d`, `objects` (list of all object names).
- **Notes:** Use this as a safety check before geometry or setup operations to confirm the correct design is active. Always call at the start of an automation script.

### `set_model_units(units)`

Set the model coordinate system units for the active design.

- **Parameters:**
  - `units` (str): Unit system string. Supported values: `"mm"`, `"cm"`, `"m"`, `"in"`, `"mil"`, `"um"`.
- **Pre-conditions:** Active 2D/3D design.
- **Returns:** Boolean success flag.
- **Notes:** MUST be called before creating any geometry. All subsequent dimensional parameters are interpreted in these units. Motor designs typically use `"mm"`. Changing units after creating geometry is not recommended and may require coordinate transformation.

### `get_model_bounding_box()`

Get the geometric bounding box of the model.

- **Parameters:** None
- **Pre-conditions:** Geometry must exist.
- **Returns:** `{"x_min": float, "x_max": float, "y_min": float, "y_max": float, "z_min": float, "z_max": float}`.
- **Notes:** Useful for region sizing and model validation.

---

## Error Handling

### Common Error Patterns

| Error | Cause | Resolution |
|-------|-------|------------|
| `ObjectNotFoundError` | Referenced object name doesn't exist | Use `get_active_editor()` to verify object list |
| `MaterialNotFoundError` | Material not in project library | Use `list_materials()` to check available materials |
| `AnalysisFailedError` | Solver convergence failure | Check mesh quality, time step size, material properties |
| `GeometryOverlapError` | Boolean operation with non-overlapping objects | Verify object positions with `get_model_bounding_box()` |
| `UnitMismatchError` | Geometry created with different units than expected | Call `set_model_units()` before all geometry operations |
| `BandGeometryError` | Motion band not a complete closed circle | Verify band circle is complete and centered at origin |

### Best Practices

1. **Always start scripts with:** `get_active_editor()` → `set_model_units("mm")`
2. **Check material availability** with `list_materials()` before `assign_material()`
3. **Save project** with `save_project()` after each major modeling step
4. **Validate geometry** with `get_model_bounding_box()` before running analysis
5. **Use variables** (`$var_name`) for all dimensions to enable parametric studies
6. **Close the loop** — export results with `export_data()` for external post-processing
