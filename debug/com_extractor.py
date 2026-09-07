#!/usr/bin/env python3
"""
COM-based Maxwell state extractor.
Connects to running ANSYS Electronics Desktop via COM and extracts
the current model state for comparison with ground truth.
"""

import json
import sys
import math


def connect_to_maxwell():
    """Connect to running AEDT instance via COM."""
    import win32com.client
    try:
        app = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
        app.restoreWindow()
        print(f"Connected to AEDT: {app.GetVersion()}")
        return app
    except Exception as e:
        print(f"ERROR: Cannot connect to AEDT: {e}")
        print("Make sure ANSYS Electronics Desktop is running.")
        return None


def get_active_design(app):
    """Get the active Maxwell 2D design."""
    try:
        project = app.getActiveProject()
        if not project:
            print("ERROR: No active project")
            return None, None, None
        design = project.getActiveDesign()
        if not design:
            print("ERROR: No active design")
            return project, None, None
        print(f"Design: {design.getName()}, Type: {design.getDesignType()}")
        return project, design, design.getDesignType()
    except Exception as e:
        print(f"ERROR getting design: {e}")
        return None, None, None


def extract_materials(design):
    """Extract material properties from the current design."""
    materials = {}
    try:
        mat_module = design.getModule("FieldsSetup")
        # Try to get material list from the design
        mat_list = design.getModule("MaterialSetup")
        if mat_list:
            names = mat_list.getNames()
            for name in names:
                mat = {'name': name}
                try:
                    props = mat_list.getItem(name)
                    # Try to get key properties
                    mat['properties'] = str(props)
                except:
                    pass
                materials[name] = mat
    except Exception as e:
        print(f"  Material extraction warning: {e}")
    
    # Fallback: extract from geometry object attributes
    try:
        editor = design.getEditor()
        obj_names = editor.getObjectNames()
        for obj_name in obj_names:
            try:
                mat_name = editor.getObjectMaterial(obj_name)
                if mat_name and mat_name not in materials:
                    materials[mat_name] = {'name': mat_name, 'source': 'object_attribute'}
            except:
                pass
    except Exception as e:
        print(f"  Object material extraction warning: {e}")
    
    return materials


def extract_geometry(design):
    """Extract geometry object names and basic info."""
    objects = []
    try:
        editor = design.getEditor()
        obj_names = editor.getObjectNames()
        for name in obj_names:
            obj = {'name': name}
            try:
                obj['material'] = editor.getObjectMaterial(name)
            except:
                obj['material'] = ''
            try:
                obj['solid'] = editor.isSolid(name)
            except:
                pass
            objects.append(obj)
    except Exception as e:
        print(f"  Geometry extraction warning: {e}")
    return objects


def extract_boundary_setup(design):
    """Extract boundary conditions (windings, coils)."""
    windings = []
    coils = []
    try:
        boundary_module = design.getModule("BoundarySetup")
        if boundary_module:
            names = boundary_module.getNames()
            for name in names:
                try:
                    bound_type = boundary_module.getType(name)
                    info = {'name': name, 'type': bound_type}
                    
                    if bound_type == 'Winding':
                        try:
                            info['voltage'] = boundary_module.getVoltageExcitation(name)
                        except:
                            pass
                        try:
                            info['current'] = boundary_module.getCurrentExcitation(name)
                        except:
                            pass
                        windings.append(info)
                    elif bound_type == 'Coil':
                        try:
                            info['conductor_number'] = boundary_module.getConductorNumber(name)
                        except:
                            pass
                        try:
                            info['polarity'] = boundary_module.getPolarity(name)
                        except:
                            pass
                        coils.append(info)
                except:
                    pass
    except Exception as e:
        print(f"  Boundary extraction warning: {e}")
    return windings, coils


def extract_mesh_setup(design):
    """Extract mesh operations."""
    mesh_ops = []
    try:
        mesh_module = design.getModule("MeshSetup")
        if mesh_module:
            names = mesh_module.getNames()
            for name in names:
                mesh_ops.append({'name': name})
    except Exception as e:
        print(f"  Mesh extraction warning: {e}")
    return mesh_ops


def extract_solver_setup(design):
    """Extract solver configurations."""
    setups = []
    try:
        analysis_module = design.getModule("AnalysisSetup")
        if analysis_module:
            names = analysis_module.getNames()
            for name in names:
                info = {'name': name}
                try:
                    info['stop_time'] = analysis_module.getStopTime(name)
                except:
                    pass
                try:
                    info['time_step'] = analysis_module.getTimeStep(name)
                except:
                    pass
                setups.append(info)
    except Exception as e:
        print(f"  Solver extraction warning: {e}")
    return setups


def extract_motion(design):
    """Extract motion/band setup."""
    motion = {}
    try:
        # Motion is part of the boundary setup
        boundary_module = design.getModule("BoundarySetup")
        if boundary_module:
            names = boundary_module.getNames()
            for name in names:
                try:
                    bound_type = boundary_module.getType(name)
                    if bound_type == 'Band' or 'Motion' in str(bound_type):
                        motion['name'] = name
                        motion['type'] = str(bound_type)
                except:
                    pass
    except Exception as e:
        print(f"  Motion extraction warning: {e}")
    return motion


def extract_model_params(design):
    """Extract basic model parameters."""
    params = {}
    try:
        params['solution_type'] = design.getSolutionType()
    except:
        pass
    try:
        params['model_depth'] = design.getModelDepth()
    except:
        pass
    try:
        params['geometry_mode'] = design.getGeometryMode()
    except:
        pass
    try:
        params['units'] = design.getUnits()
    except:
        pass
    return params


def main():
    app = connect_to_maxwell()
    if not app:
        sys.exit(1)

    project, design, design_type = get_active_design(app)
    if not design:
        sys.exit(1)

    print(f"\nExtracting state from: {design.getName()}")
    print(f"Design type: {design_type}")

    state = {
        'design_name': design.getName(),
        'design_type': design_type,
        'model_params': extract_model_params(design),
        'materials': extract_materials(design),
        'geometry': extract_geometry(design),
        'windings': [],
        'coils': [],
        'mesh_ops': extract_mesh_setup(design),
        'solver_setups': extract_solver_setup(design),
        'motion': extract_motion(design),
    }

    state['windings'], state['coils'] = extract_boundary_setup(design)

    print(f"\n--- Extracted State ---")
    print(f"Model params: {state['model_params']}")
    print(f"Materials ({len(state['materials'])}): {list(state['materials'].keys())}")
    print(f"Geometry ({len(state['geometry'])}): {[o['name'] for o in state['geometry']]}")
    print(f"Windings ({len(state['windings'])})")
    print(f"Coils ({len(state['coils'])})")
    print(f"Mesh ops ({len(state['mesh_ops'])})")
    print(f"Solver setups ({len(state['solver_setups'])})")
    print(f"Motion: {state['motion']}")

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {sys.argv[1]}")

    return state


if __name__ == '__main__':
    main()
