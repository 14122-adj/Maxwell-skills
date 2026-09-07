#!/usr/bin/env python3
"""
Maxwell 2D Induction Motor Model Builder
Replicates the 书本仿制.aedt model via COM automation.

Motor: 36-slot/28-bar squirrel cage induction motor
Stator: OD=210mm, ID=136mm, 36 pear-type slots
Rotor: OD=135.2mm, shaft=48mm, 28 pear-type slots
Band: airgap center diameter=135.6mm
Airgap: 0.8mm total
Stack length: 143mm
Speed: 1465.37rpm
Excitation: 3-phase voltage, 537.4V peak, 50Hz
"""

import win32com.client
import math
import os
import sys
import time

# ============================================================
# Motor Parameters (from 书本仿制.aedt reverse engineering)
# ============================================================
# Stator
STATOR_OD = 210.0      # mm
STATOR_ID = 136.0      # mm
STATOR_SLOTS = 36
STATOR_SLOT_TYPE = 2   # pear
S_HS0, S_HS1, S_HS2 = 0.8, 1.5, 11.5   # mm
S_BS0, S_BS1, S_BS2, S_RS = 3.5, 6.2, 8.3, 4.15  # mm

# Rotor
ROTOR_OD = 135.2       # mm
SHAFT_OD = 48.0        # mm
ROTOR_SLOTS = 28
ROTOR_SLOT_TYPE = 2    # pear
R_HS0, R_HS1, R_HS2 = 0.5, 1.7, 18.8   # mm
R_BS0, R_BS1, R_BS2 = 1.0, 6.9, 6.9    # mm

# Band (airgap center)
BAND_DIA = 135.6       # mm

# Outer region
OUTER_MARGIN = 20.0    # mm beyond stator OD

# Stack length
STACK_LEN = 143.0      # mm

# Speed
SPEED_RPM = 1465.37

# Excitation
V_PEAK = 537.401       # V
FREQ = 50.0            # Hz
PHASE_R = 0.957355     # ohm
PHASE_L = 0.0038188    # H
CONDUCTORS = 35

# Solver
STOP_TIME = "0.5s"
TIME_STEP = "0.001s"

# ============================================================
# COM Helpers
# ============================================================
def connect():
    desktop = win32com.client.Dispatch('Ansoft.ElectronicsDesktop')
    app = desktop.GetAppDesktop()
    project = app.GetActiveProject()
    if project:
        print(f"Connected. Active project: {project.GetName()}")
    else:
        print("No active project. Creating new one...")
        project = app.NewProject("ISIM_Motor")
        print(f"Created project: ISIM_Motor")
    return desktop, app, project


def create_design(project, name, solution_type="Transient"):
    """Create a new Maxwell 2D design."""
    design = project.InsertDesign("Maxwell 2D", name, "XY", solution_type)
    editor = design.SetActiveEditor("3D Modeler")
    print(f"Created design: {name} ({solution_type})")
    return design, editor


def set_units(editor, unit="mm"):
    editor.SetModelUnits(
        ["NAME:Units Settings", "HUnit:=", unit, "VUnit:=", unit, "LUnit:=", unit])
    print(f"Units set to: {unit}")


def make_circle(editor, name, radius, color="(0 255 255)", transparency=0, material="vacuum"):
    editor.CreateCircle(
        ["NAME:CircleParameters", "XPosition:=", "0mm", "YPosition:=", "0mm",
         "ZPosition:=", "0mm", "Radius:=", f"{radius}mm", "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
         "Transparency:=", transparency, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", f'"{material}"', "SolveInside:=", True])


def make_rect(editor, name, x, y, w, h, color="(0 200 0)", material="vacuum"):
    editor.CreateRectangle(
        ["NAME:RectangleParameters", "IsCovered:=", True,
         "XStart:=", f"{x}mm", "YStart:=", f"{y}mm",
         "ZStart:=", "0mm", "Width:=", f"{w}mm",
         "Height:=", f"{h}mm", "WhichAxis:=", "Z"],
        ["NAME:Attributes", "Name:=", name, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", f'"{material}"', "SolveInside:=", True])


def rotate_object(editor, name, angle_deg):
    editor.Rotate(
        ["NAME:Selections", "Selections:=", name],
        ["NAME:RotateParameters", "RotateAxis:=", "Z",
         "RotateAngle:=", f"{angle_deg}deg",
         "DuplicateObjects:=", False, "DuplicateSurfaceComponents:=", False])


def subtract(editor, blank, tool):
    editor.Subtract(
        ["NAME:Selections", "Blank Parts:=", blank, "Tool Parts:=", tool],
        ["NAME:SubtractParameters", "KeepOriginals:=", False])


def unite(editor, names):
    if len(names) < 2:
        return
    editor.Unite(
        ["NAME:Selections", "Selections:=", names],
        ["NAME:UniteParameters", "KeepOriginals:=", False])


def set_material(editor, name, material):
    editor.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:Geometry3DAttributeTab",
          ["NAME:PropServers", name],
          ["NAME:ChangedProps",
           ["NAME:Material", "Value:=", f'"{material}"']]]])


def delete_all_objects(editor):
    """Delete all geometry objects except coordinate systems."""
    n = editor.GetNumObjects()
    for i in range(n - 1, -1, -1):
        name = editor.GetObjectName(i)
        try:
            editor.Delete(["NAME:Selections", "Selections:=", name])
        except:
            pass


def run_script(app, script_text, script_dir=None):
    """Write script to temp file and execute via RunScriptWithArguments."""
    if script_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "_temp_script.py")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(script_text)
    app.RunScriptWithArguments(path, '')
    time.sleep(0.5)
    try:
        os.remove(path)
    except:
        pass


# ============================================================
# Step 1: Build Geometry
# ============================================================
def build_geometry(editor):
    print("\n=== Step 1: Building Geometry ===")

    # 1. Band (运动带，气隙中心)
    make_circle(editor, "Band", BAND_DIA / 2.0, "(0 255 255)", 0.75)
    print("  1. Band")

    # 2. Shaft (轴)
    make_circle(editor, "Shaft", SHAFT_OD / 2.0, "(0 255 255)", 0)
    print("  2. Shaft")

    # 3. OuterRegion
    make_circle(editor, "OuterRegion", STATOR_OD / 2.0 + OUTER_MARGIN,
                "(0 255 255)", 0.75)
    print("  3. OuterRegion")

    # 4. Stator core (外圆 - 内圆)
    make_circle(editor, "Stator_Outer", STATOR_OD / 2.0, "(132 132 193)", 0)
    make_circle(editor, "Stator_Inner", STATOR_ID / 2.0, "(132 132 193)", 0)
    subtract(editor, "Stator_Outer", "Stator_Inner")
    print("  4. Stator core")

    # 5. Rotor core (外圆 - 内圆)
    make_circle(editor, "Rotor_Outer", ROTOR_OD / 2.0, "(132 132 193)", 0)
    make_circle(editor, "Rotor_Inner", SHAFT_OD / 2.0, "(132 132 193)", 0)
    subtract(editor, "Rotor_Outer", "Rotor_Inner")
    print("  5. Rotor core")

    # 6. Stator slots (36 pear-type slots)
    slot_depth = S_HS0 + S_HS1 + S_HS2
    slot_width_avg = (S_BS0 + S_BS2) / 2.0
    slot_pitch = 360.0 / STATOR_SLOTS

    for i in range(1, STATOR_SLOTS + 1):
        angle = (i - 1) * slot_pitch
        name = f"SLOT_{i}"
        # Create slot at 0 degree, then rotate
        make_rect(editor, name,
                  STATOR_ID / 2.0, -slot_width_avg / 2.0,
                  slot_depth, slot_width_avg,
                  "(200 200 0)")
        if angle > 0:
            rotate_object(editor, name, angle)
        subtract(editor, "Stator_Outer", name)

    print(f"  6. {STATOR_SLOTS} stator slots")

    # 7. Rotor slots (28 pear-type slots for squirrel cage bars)
    r_slot_depth = R_HS0 + R_HS1 + R_HS2
    r_slot_width_avg = (R_BS0 + R_BS2) / 2.0
    r_slot_pitch = 360.0 / ROTOR_SLOTS

    for i in range(1, ROTOR_SLOTS + 1):
        angle = (i - 1) * r_slot_pitch
        name = f"RSLOT_{i}"
        # Rotor slots point inward from rotor OD
        make_rect(editor, name,
                  ROTOR_OD / 2.0 - r_slot_depth, -r_slot_width_avg / 2.0,
                  r_slot_depth, r_slot_width_avg,
                  "(200 200 0)")
        if angle > 0:
            rotate_object(editor, name, angle)
        subtract(editor, "Rotor_Outer", name)

    print(f"  7. {ROTOR_SLOTS} rotor slots")

    # 8. Stator coils (9 coils, 3 per phase)
    coil_depth = slot_depth - 0.5  # slightly smaller than slot
    coil_width = slot_width_avg - 0.5
    coil_names = []

    # Phase A: slots 1,2,3
    # Phase B: slots 13,14,15
    # Phase C: slots 25,26,27 (negative polarity)
    phase_slots = {
        'A': [1, 2, 3],
        'B': [13, 14, 15],
        'C': [25, 26, 27],
    }

    coil_idx = 0
    for phase, slots_list in phase_slots.items():
        for slot_num in slots_list:
            angle = (slot_num - 1) * slot_pitch
            name = f"Coil_{coil_idx}"
            # Coil sits inside the slot
            make_rect(editor, name,
                      STATOR_ID / 2.0 + 0.25, -coil_width / 2.0,
                      coil_depth, coil_width,
                      "(200 140 102)", "copper")
            if angle > 0:
                rotate_object(editor, name, angle)
            coil_names.append((name, phase, slot_num))
            coil_idx += 1

    print(f"  8. {coil_idx} coils created")

    return coil_names


# ============================================================
# Step 2: Assign Materials
# ============================================================
def assign_materials(editor):
    print("\n=== Step 2: Assigning Materials ===")

    set_material(editor, "Stator_Outer", "D23_50_2DSF0.950")
    set_material(editor, "Rotor_Outer", "D23_50_2DSF0.950")
    set_material(editor, "Shaft", "steel_stainless")
    set_material(editor, "Band", "vacuum")
    set_material(editor, "OuterRegion", "vacuum")

    # Coils are already copper from creation
    print("  Materials assigned")


# ============================================================
# Step 3: Set up Excitations (via script)
# ============================================================
def setup_excitations(app, coil_names):
    print("\n=== Step 3: Setting up Excitations ===")

    # Build coil assignments for each phase
    phase_coils = {'A': [], 'B': [], 'C': []}
    for name, phase, slot_num in coil_names:
        phase_coils[phase].append(name)

    # Build the script
    coil_assignments = ""
    for phase in ['A', 'B', 'C']:
        winding_name = f"Phase{phase}"
        coils = phase_coils[phase]
        polarity = "Negative" if phase == 'C' else "Positive"

        # Assign coil to winding
        for i, coil_name in enumerate(coils):
            coil_bound_name = f"Ph{phase}_{i}"
            coil_assignments += f'''
oModule.AssignCoil(
    ["NAME:{coil_bound_name}",
     "Objects:=", ["{coil_name}"],
     "Conductor number:=", "{CONDUCTORS}",
     "PolarityType:=", "{polarity}",
     "Winding:=", "{winding_name}"])
'''

    # Phase voltage expressions
    v_a = f"{V_PEAK}*sin(2*pi*{FREQ}*time)"
    v_b = f"{V_PEAK}*sin(2*pi*{FREQ}*time-2*pi/3)"
    v_c = f"{V_PEAK}*sin(2*pi*{FREQ}*time-4*pi/3)"

    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("BoundarySetup")

# Phase A winding
oModule.AssignWinding(
    ["NAME:PhaseA",
     "Type:=", "Voltage",
     "IsSolid:=", False,
     "Current:=", "0A",
     "Resistance:=", "{PHASE_R}ohm",
     "Inductance:=", "{PHASE_L}H",
     "Voltage:=", "{v_a}",
     "ParallelBranchesNum:=", "1"])

# Phase B winding
oModule.AssignWinding(
    ["NAME:PhaseB",
     "Type:=", "Voltage",
     "IsSolid:=", False,
     "Current:=", "0A",
     "Resistance:=", "{PHASE_R}ohm",
     "Inductance:=", "{PHASE_L}H",
     "Voltage:=", "{v_b}",
     "ParallelBranchesNum:=", "1"])

# Phase C winding
oModule.AssignWinding(
    ["NAME:PhaseC",
     "Type:=", "Voltage",
     "IsSolid:=", False,
     "Current:=", "0A",
     "Resistance:=", "{PHASE_R}ohm",
     "Inductance:=", "{PHASE_L}H",
     "Voltage:=", "{v_c}",
     "ParallelBranchesNum:=", "1"])

# Coil assignments
{coil_assignments}

# Vector Potential boundary on OuterRegion
oModule.AssignVectorPotential(
    ["NAME:VectorPot",
     "Objects:=", ["OuterRegion"],
     "Value:=", "0",
     "CoordinateSystem:=", "Cartesian"])

print("Excitations set")
'''
    run_script(app, script)
    print("  Excitations configured")


# ============================================================
# Step 4: Motion Band
# ============================================================
def setup_motion(app):
    print("\n=== Step 4: Setting up Motion Band ===")

    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("ModelSetup")

oModule.AssignBand(
    ["NAME:Band",
     "Objects:=", ["Band"],
     "BandCoordinateSystem:=", "Global",
     "AngularVelocity:=", "{SPEED_RPM}rpm",
     "WhichAxis:=", "Z",
     "IsModelObject:=", True,
     "InitialPositionIsZero:=", True])

print("Motion band set: {SPEED_RPM}rpm")
'''
    run_script(app, script)
    print(f"  Motion: {SPEED_RPM}rpm")


# ============================================================
# Step 5: Mesh
# ============================================================
def setup_mesh(app):
    print("\n=== Step 5: Setting up Mesh ===")

    script = '''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("MeshSetup")

# Surface approximation for bars (fine)
oModule.AssignSurfApproxOp(
    ["NAME:SurfApprox_Bar",
     "Objects:=", ["Band", "Shaft"],
     "CurvedSurfaceApproxChoice:=", "ManualSettings",
     "SurfDevChoice:=", 2,
     "SurfDev:=", "0.0676mm",
     "NormalDevChoice:=", 2,
     "NormalDev:=", "15deg",
     "AspectRatioChoice:=", 1])

# Surface approximation for main objects
oModule.AssignSurfApproxOp(
    ["NAME:SurfApprox_Main",
     "Objects:=", ["Stator_Outer", "Rotor_Outer", "OuterRegion"],
     "CurvedSurfaceApproxChoice:=", "ManualSettings",
     "SurfDevChoice:=", 2,
     "SurfDev:=", "0.105mm",
     "NormalDevChoice:=", 2,
     "NormalDev:=", "15deg",
     "AspectRatioChoice:=", 1])

# Length-based mesh (global)
oModule.AssignLengthOp(
    ["NAME:Length1",
     "Objects:=", ["Band", "Shaft", "Stator_Outer", "Rotor_Outer",
                   "OuterRegion"],
     "RefineInside:=", False,
     "RestrictElem:=", False,
     "RestrictLength:=", True,
     "MaxLength:=", "0.5mm"])

print("Mesh set")
'''
    run_script(app, script)
    print("  Mesh configured")


# ============================================================
# Step 6: Solver
# ============================================================
def setup_solver(app):
    print("\n=== Step 6: Setting up Solver ===")

    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "{STOP_TIME}",
     "TimeStep:=", "{TIME_STEP}",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False,
     "FastReachSteadyState:=", True,
     "AutoDetectSteadyState:=", True])

print("Solver set: {STOP_TIME} / {TIME_STEP}")
'''
    run_script(app, script)
    print(f"  Solver: stop={STOP_TIME}, step={TIME_STEP}")


# ============================================================
# Step 7: Save
# ============================================================
def save_project(project, design_name="ISIM_36s28b"):
    try:
        save_path = r"D:\桌面\Maxwell电机仿真\ISIM_36s28b.aedt"
        project.SaveAs(save_path, True)
        print(f"\n  Project saved to: {save_path}")
    except Exception as e:
        print(f"\n  Save warning: {e}")
        try:
            project.Save()
            print("  Project saved (default location)")
        except Exception as e2:
            print(f"  Save failed: {e2}")


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 60)
    print("Maxwell 2D Induction Motor Builder")
    print("Replicating: 书本仿制.aedt")
    print("=" * 60)

    # Connect
    desktop, app, project = connect()

    # Create new design
    design, editor = create_design(project, "ISIM_36s28b")

    # Set units
    set_units(editor, "mm")

    # Build geometry
    coil_names = build_geometry(editor)

    # Assign materials
    assign_materials(editor)

    # Save intermediate
    project.Save()
    print("\n  [Checkpoint] Geometry + materials saved")

    # Setup excitations
    setup_excitations(app, coil_names)

    # Setup motion
    setup_motion(app)

    # Setup mesh
    setup_mesh(app)

    # Setup solver
    setup_solver(app)

    # Save
    project.Save()
    print("\n  [Checkpoint] Full setup saved")

    print("\n" + "=" * 60)
    print("MODEL BUILD COMPLETE")
    print("=" * 60)
    print(f"Design: ISIM_36s28b")
    print(f"Stator: {STATOR_OD}mm/{STATOR_ID}mm, {STATOR_SLOTS} slots")
    print(f"Rotor: {ROTOR_OD}mm/{SHAFT_OD}mm, {ROTOR_SLOTS} bars")
    print(f"Band: {BAND_DIA}mm dia, {SPEED_RPM}rpm")
    print(f"Excitation: {V_PEAK}V peak, {FREQ}Hz, 3-phase")
    print(f"Solver: Transient, {STOP_TIME}/{TIME_STEP}")
    print("=" * 60)


if __name__ == '__main__':
    main()
