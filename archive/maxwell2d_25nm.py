#!/usr/bin/env python3
"""
25Nm Induction Motor - Scaled from 48.7Nm reference
Only diameter changed, slot geometry/materials/speed unchanged.
Scaling factor: sqrt(25/48.72) = 0.717
"""

import win32com.client
import math
import time
import os

# ============================================================
# Scaled Parameters
# ============================================================
SCALE = math.sqrt(25.0 / 48.72)  # 0.717

# Stator (scaled)
STATOR_OD = 210.0 * SCALE    # 150.6mm
STATOR_ID = 136.0 * SCALE    # 97.5mm
STATOR_SLOTS = 36
S_HS0, S_HS1, S_HS2 = 0.8, 1.5, 11.5   # unchanged
S_BS0, S_BS1, S_BS2, S_RS = 3.5, 6.2, 8.3, 4.15  # unchanged

# Rotor (scaled)
ROTOR_OD = 135.2 * SCALE     # 96.9mm
SHAFT_OD = 48.0 * SCALE      # 34.4mm
ROTOR_SLOTS = 28
R_HS0, R_HS1, R_HS2 = 0.5, 1.7, 18.8   # unchanged
R_BS0, R_BS1, R_BS2 = 1.0, 6.9, 6.9    # unchanged

# Band
BAND_DIA = 135.6 * SCALE     # 97.2mm

# Outer region
OUTER_MARGIN = 20.0

# Stack length (unchanged)
STACK_LEN = 143.0

# Speed (unchanged)
SPEED_RPM = 1465.37

# Excitation (unchanged)
V_PEAK = 537.401
FREQ = 50.0
PHASE_R = 0.957355
PHASE_L = 0.0038188
CONDUCTORS = 35

# Solver
STOP_TIME = "0.5s"
TIME_STEP = "0.001s"


def connect():
    desktop = win32com.client.Dispatch('Ansoft.ElectronicsDesktop')
    app = desktop.GetAppDesktop()
    project = app.GetActiveProject()
    if not project:
        project = app.NewProject("ISIM_25Nm")
    print(f"Project: {project.GetName()}")
    return desktop, app, project


def create_design(project):
    # Use RunScript to create design (COM InsertDesign has issues)
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "_create_25nm.py")
    with open(script_path, 'w') as f:
        f.write('oDesktop = GetDesktop()\noProject = oDesktop.GetActiveProject()\noDesign = oProject.InsertDesign("Maxwell 2D", "ISIM_25Nm", "XY", "Transient")\n')

    app = win32com.client.Dispatch('Ansoft.ElectronicsDesktop').GetAppDesktop()
    app.RunScriptWithArguments(script_path, '')
    time.sleep(3)

    project = app.GetActiveProject()
    design = project.SetActiveDesign("ISIM_25Nm")
    print(f"Design: {design.GetName()}")
    return design


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


def set_material(editor, name, material):
    editor.ChangeProperty(
        ["NAME:AllTabs",
         ["NAME:Geometry3DAttributeTab",
          ["NAME:PropServers", name],
          ["NAME:ChangedProps",
           ["NAME:Material", "Value:=", f'"{material}"']]]])


def run_script(app, script_text):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "_temp_25nm.py")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(script_text)
    app.RunScriptWithArguments(path, '')
    time.sleep(0.5)


def main():
    print("=" * 60)
    print("25Nm Induction Motor Builder")
    print(f"Scaling factor: {SCALE:.4f}")
    print(f"Stator: {STATOR_OD:.1f}mm / {STATOR_ID:.1f}mm")
    print(f"Rotor:  {ROTOR_OD:.1f}mm / {SHAFT_OD:.1f}mm")
    print(f"Band:   {BAND_DIA:.1f}mm")
    print("=" * 60)

    desktop, app, project = connect()
    design = create_design(project)
    editor = design.SetActiveEditor("3D Modeler")

    # Set units
    editor.SetModelUnits(["NAME:Units Settings", "HUnit:=", "mm", "VUnit:=", "mm", "LUnit:=", "mm"])

    # 1. Band
    make_circle(editor, "Band", BAND_DIA / 2.0, "(0 255 255)", 0.75)
    print("1. Band")

    # 2. Shaft
    make_circle(editor, "Shaft", SHAFT_OD / 2.0, "(0 255 255)", 0)
    print("2. Shaft")

    # 3. OuterRegion
    make_circle(editor, "OuterRegion", STATOR_OD / 2.0 + OUTER_MARGIN, "(0 255 255)", 0.75)
    print("3. OuterRegion")

    # 4. Stator
    make_circle(editor, "Stator_Outer", STATOR_OD / 2.0, "(132 132 193)", 0)
    make_circle(editor, "Stator_Inner", STATOR_ID / 2.0, "(132 132 193)", 0)
    subtract(editor, "Stator_Outer", "Stator_Inner")
    print("4. Stator")

    # 5. Rotor
    make_circle(editor, "Rotor_Outer", ROTOR_OD / 2.0, "(132 132 193)", 0)
    make_circle(editor, "Rotor_Inner", SHAFT_OD / 2.0, "(132 132 193)", 0)
    subtract(editor, "Rotor_Outer", "Rotor_Inner")
    print("5. Rotor")

    # 6. Stator slots
    slot_depth = S_HS0 + S_HS1 + S_HS2
    slot_width_avg = (S_BS0 + S_BS2) / 2.0
    slot_pitch = 360.0 / STATOR_SLOTS

    for i in range(1, STATOR_SLOTS + 1):
        angle = (i - 1) * slot_pitch
        name = f"SLOT_{i}"
        make_rect(editor, name, STATOR_ID / 2.0, -slot_width_avg / 2.0,
                  slot_depth, slot_width_avg, "(200 200 0)")
        if angle > 0:
            rotate_object(editor, name, angle)
        subtract(editor, "Stator_Outer", name)
    print(f"6. {STATOR_SLOTS} stator slots")

    # 7. Rotor slots
    r_slot_depth = R_HS0 + R_HS1 + R_HS2
    r_slot_width_avg = (R_BS0 + R_BS2) / 2.0
    r_slot_pitch = 360.0 / ROTOR_SLOTS

    for i in range(1, ROTOR_SLOTS + 1):
        angle = (i - 1) * r_slot_pitch
        name = f"RSLOT_{i}"
        make_rect(editor, name, ROTOR_OD / 2.0 - r_slot_depth, -r_slot_width_avg / 2.0,
                  r_slot_depth, r_slot_width_avg, "(200 200 0)")
        if angle > 0:
            rotate_object(editor, name, angle)
        subtract(editor, "Rotor_Outer", name)
    print(f"7. {ROTOR_SLOTS} rotor slots")

    # 8. Coils
    coil_depth = slot_depth - 0.5
    coil_width = slot_width_avg - 0.5
    phase_slots = {'A': [1, 2, 3], 'B': [13, 14, 15], 'C': [25, 26, 27]}
    coil_idx = 0
    for phase, slots_list in phase_slots.items():
        for slot_num in slots_list:
            angle = (slot_num - 1) * slot_pitch
            name = f"Coil_{coil_idx}"
            make_rect(editor, name, STATOR_ID / 2.0 + 0.25, -coil_width / 2.0,
                      coil_depth, coil_width, "(200 140 102)", "copper")
            if angle > 0:
                rotate_object(editor, name, angle)
            coil_idx += 1
    print(f"8. {coil_idx} coils")

    # 9. Materials
    set_material(editor, "Stator_Outer", "D23_50_2DSF0.950")
    set_material(editor, "Rotor_Outer", "D23_50_2DSF0.950")
    set_material(editor, "Shaft", "steel_stainless")
    set_material(editor, "Band", "vacuum")
    set_material(editor, "OuterRegion", "vacuum")
    print("9. Materials")

    project.Save()
    print("10. Saved geometry")

    # 10. Excitations via script
    v_a = f"{V_PEAK}*sin(2*pi*{FREQ}*time)"
    v_b = f"{V_PEAK}*sin(2*pi*{FREQ}*time-2*pi/3)"
    v_c = f"{V_PEAK}*sin(2*pi*{FREQ}*time-4*pi/3)"

    coil_assign = ""
    for phase in ['A', 'B', 'C']:
        winding = f"Phase{phase}"
        coils = phase_slots[phase]
        pol = "Negative" if phase == 'C' else "Positive"
        for i, sn in enumerate(coils):
            cn = f"Coil_{['A','B','C'].index(phase)*3 + i}"
            coil_assign += f'oModule.AssignCoil(["NAME:Ph{phase}_{i}", "Objects:=", ["{cn}"], "Conductor number:=", "{CONDUCTORS}", "PolarityType:=", "{pol}", "Winding:=", "{winding}"])\n'

    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("BoundarySetup")
oModule.AssignWindingGroup(["NAME:PhaseA", "Type:=", "Voltage", "IsSolid:=", False, "Current:=", "0A", "Resistance:=", "{PHASE_R}ohm", "Inductance:=", "{PHASE_L}H", "Voltage:=", "{v_a}", "ParallelBranchesNum:=", "1"])
oModule.AssignWindingGroup(["NAME:PhaseB", "Type:=", "Voltage", "IsSolid:=", False, "Current:=", "0A", "Resistance:=", "{PHASE_R}ohm", "Inductance:=", "{PHASE_L}H", "Voltage:=", "{v_b}", "ParallelBranchesNum:=", "1"])
oModule.AssignWindingGroup(["NAME:PhaseC", "Type:=", "Voltage", "IsSolid:=", False, "Current:=", "0A", "Resistance:=", "{PHASE_R}ohm", "Inductance:=", "{PHASE_L}H", "Voltage:=", "{v_c}", "ParallelBranchesNum:=", "1"])
{coil_assign}
oModule.AssignVectorPotential(["NAME:VectorPot", "Objects:=", ["OuterRegion"], "Value:=", "0", "CoordinateSystem:=", "Cartesian"])
'''
    run_script(app, script)
    print("11. Excitations")

    # 11. Motion
    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("ModelSetup")
oModule.AssignBand(["NAME:Band", "Objects:=", ["Band"], "BandCoordinateSystem:=", "Global", "AngularVelocity:=", "{SPEED_RPM}rpm", "WhichAxis:=", "Z", "IsModelObject:=", True, "InitialPositionIsZero:=", True])
'''
    run_script(app, script)
    print("12. Motion")

    # 12. Mesh
    script = '''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("MeshSetup")
oModule.AssignSurfApproxOp(["NAME:SurfApprox_Bar", "Objects:=", ["Band", "Shaft"], "CurvedSurfaceApproxChoice:=", "ManualSettings", "SurfDevChoice:=", 2, "SurfDev:=", "0.0676mm", "NormalDevChoice:=", 2, "NormalDev:=", "15deg", "AspectRatioChoice:=", 1])
oModule.AssignSurfApproxOp(["NAME:SurfApprox_Main", "Objects:=", ["Stator_Outer", "Rotor_Outer", "OuterRegion"], "CurvedSurfaceApproxChoice:=", "ManualSettings", "SurfDevChoice:=", 2, "SurfDev:=", "0.105mm", "NormalDevChoice:=", 2, "NormalDev:=", "15deg", "AspectRatioChoice:=", 1])
oModule.AssignLengthOp(["NAME:Length1", "Objects:=", ["Band", "Shaft", "Stator_Outer", "Rotor_Outer", "OuterRegion"], "RefineInside:=", False, "RestrictElem:=", False, "RestrictLength:=", True, "MaxLength:=", "0.5mm"])
'''
    run_script(app, script)
    print("13. Mesh")

    # 13. Solver
    script = f'''
oDesign = oProject.GetActiveDesign()
oModule = oDesign.GetModule("AnalysisSetup")
oModule.InsertSetup("Transient", ["NAME:Setup1", "StopTime:=", "{STOP_TIME}", "TimeStep:=", "{TIME_STEP}", "UseAdaptiveTimeStep:=", False, "NonlinearSolverResidual:=", "0.0001", "SmoothBHCurve:=", False, "FastReachSteadyState:=", True, "AutoDetectSteadyState:=", True])
'''
    run_script(app, script)
    print("14. Solver")

    project.Save()
    print("15. Saved")

    print("\n" + "=" * 60)
    print("BUILD COMPLETE - ISIM_25Nm")
    print(f"Stator: {STATOR_OD:.1f}mm / {STATOR_ID:.1f}mm, {STATOR_SLOTS} slots")
    print(f"Rotor:  {ROTOR_OD:.1f}mm / {SHAFT_OD:.1f}mm, {ROTOR_SLOTS} bars")
    print(f"Target: 25 Nm (scaled from 48.7 Nm reference)")
    print("=" * 60)


if __name__ == '__main__':
    main()
