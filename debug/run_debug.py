#!/usr/bin/env python3
"""
Master Debug Orchestrator
1. Parse reference .aedt file to extract ground truth
2. Connect to Maxwell via COM and extract current state
3. Compare and generate debug report
4. Optionally auto-fix issues via COM
"""

import json
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from aedt_parser import parse_aedt
from debug_compare import compare_materials, compare_geometry, compare_windings, compare_coils, compare_solver, compare_motion, compare_model_params, generate_report


def extract_com_state():
    """Extract current Maxwell state via COM."""
    try:
        import win32com.client
    except ImportError:
        print("ERROR: win32com not available. Install pywin32.")
        return None

    try:
        app = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
        app.restoreWindow()
        print(f"Connected to AEDT: {app.GetVersion()}")
    except Exception as e:
        print(f"ERROR: Cannot connect to AEDT: {e}")
        return None

    project = app.getActiveProject()
    if not project:
        print("ERROR: No active project")
        return None

    design = project.getActiveDesign()
    if not design:
        print("ERROR: No active design")
        return None

    print(f"Design: {design.getName()} ({design.getDesignType()})")

    state = {
        'design_name': design.getName(),
        'design_type': design.getDesignType(),
        'model_params': {},
        'materials': {},
        'geometry': [],
        'windings': [],
        'coils': [],
        'mesh_ops': [],
        'solver_setups': [],
        'motion': {},
    }

    # Model params
    try:
        state['model_params']['solution_type'] = design.getSolutionType()
    except: pass
    try:
        state['model_params']['model_depth'] = design.getModelDepth()
    except: pass
    try:
        state['model_params']['geometry_mode'] = design.getGeometryMode()
    except: pass

    # Geometry objects
    try:
        editor = design.getEditor()
        obj_names = editor.getObjectNames()
        for name in obj_names:
            obj = {'name': name}
            try:
                obj['material'] = editor.getObjectMaterial(name)
            except:
                obj['material'] = ''
            state['geometry'].append(obj)
    except Exception as e:
        print(f"  Geometry warning: {e}")

    # Boundary setup (windings + coils)
    try:
        bm = design.getModule("BoundarySetup")
        if bm:
            for name in bm.getNames():
                try:
                    btype = bm.getType(name)
                    info = {'name': name, 'type': btype}
                    if 'Winding' in btype:
                        try: info['voltage'] = bm.getVoltageExcitation(name)
                        except: pass
                        try: info['resistance'] = bm.getResistance(name)
                        except: pass
                        try: info['inductance'] = bm.getInductance(name)
                        except: pass
                        state['windings'].append(info)
                    elif 'Coil' in btype:
                        try: info['conductor_number'] = bm.getConductorNumber(name)
                        except: pass
                        try: info['polarity'] = bm.getPolarity(name)
                        except: pass
                        state['coils'].append(info)
                except: pass
    except Exception as e:
        print(f"  Boundary warning: {e}")

    # Mesh
    try:
        mm = design.getModule("MeshSetup")
        if mm:
            for name in mm.getNames():
                state['mesh_ops'].append({'name': name})
    except: pass

    # Solver
    try:
        am = design.getModule("AnalysisSetup")
        if am:
            for name in am.getNames():
                info = {'name': name}
                try: info['stop_time'] = am.getStopTime(name)
                except: pass
                try: info['time_step'] = am.getTimeStep(name)
                except: pass
                state['solver_setups'].append(info)
    except: pass

    # Motion
    try:
        bm = design.getModule("BoundarySetup")
        if bm:
            for name in bm.getNames():
                try:
                    if 'Band' in name or 'Motion' in bm.getType(name):
                        state['motion'] = {'name': name, 'type': bm.getType(name)}
                except: pass
    except: pass

    return state


def auto_fix(issues, app):
    """Attempt to auto-fix issues via COM."""
    if not app:
        return

    project = app.getActiveProject()
    design = project.getActiveDesign()
    if not design:
        return

    fixed = 0
    for issue in issues:
        if issue['severity'] != 'ERROR':
            continue

        module = issue['module']
        fix = issue.get('fix', '')

        try:
            if module == 'Solver' and 'StopTime' in fix:
                # Extract setup name and value
                import re
                m = re.search(r"Setup\d+", issue['issue'])
                if m:
                    setup_name = m.group(0)
                    m2 = re.search(r'to (\S+)', fix)
                    if m2:
                        val = m2.group(1)
                        am = design.getModule("AnalysisSetup")
                        am.setStopTime(setup_name, val)
                        print(f"  FIXED: {setup_name} StopTime -> {val}")
                        fixed += 1

            elif module == 'Solver' and 'TimeStep' in fix:
                import re
                m = re.search(r"Setup\d+", issue['issue'])
                if m:
                    setup_name = m.group(0)
                    m2 = re.search(r'to (\S+)', fix)
                    if m2:
                        val = m2.group(1)
                        am = design.getModule("AnalysisSetup")
                        am.setTimeStep(setup_name, val)
                        print(f"  FIXED: {setup_name} TimeStep -> {val}")
                        fixed += 1

        except Exception as e:
            print(f"  Auto-fix failed for: {issue['issue'][:50]}... Error: {e}")

    print(f"\nAuto-fixed {fixed} issues")
    return fixed


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Maxwell Motor Debug System')
    parser.add_argument('--ref', required=True, help='Reference .aedt file path')
    parser.add_argument('--state', help='Pre-extracted current state JSON (skip COM)')
    parser.add_argument('--report', default='debug_report.txt', help='Output report path')
    parser.add_argument('--auto-fix', action='store_true', help='Attempt auto-fix via COM')
    parser.add_argument('--save-gt', default='ground_truth.json', help='Save ground truth JSON')
    parser.add_argument('--save-state', default='current_state.json', help='Save current state JSON')
    args = parser.parse_args()

    print("=" * 60)
    print("MAXWELL MOTOR DEBUG SYSTEM")
    print("=" * 60)

    # Step 1: Parse reference .aedt
    print(f"\n[1/4] Parsing reference: {args.ref}")
    gt_data = parse_aedt(args.ref)
    gt_data['model_params'] = {
        'solution_type': gt_data.get('solution_type', ''),
        'geometry_mode': gt_data.get('geometry_mode', ''),
        'model_depth': gt_data.get('model_depth', ''),
    }
    print(f"  Materials: {len(gt_data.get('materials', {}))}")
    print(f"  Geometry: {len(gt_data.get('geometry_objects', []))}")
    print(f"  Windings: {len(gt_data.get('windings', []))}")
    print(f"  Coils: {len(gt_data.get('coils', []))}")

    # Save ground truth
    with open(args.save_gt, 'w', encoding='utf-8') as f:
        json.dump(gt_data, f, indent=2, ensure_ascii=False)
    print(f"  Saved to: {args.save_gt}")

    # Step 2: Get current state
    if args.state:
        print(f"\n[2/4] Loading current state from: {args.state}")
        cur_data = json.load(open(args.state, 'r', encoding='utf-8'))
    else:
        print(f"\n[2/4] Extracting current state from Maxwell via COM...")
        cur_data = extract_com_state()
        if not cur_data:
            print("ERROR: Failed to extract current state")
            sys.exit(1)
        with open(args.save_state, 'w', encoding='utf-8') as f:
            json.dump(cur_data, f, indent=2, ensure_ascii=False)
        print(f"  Saved to: {args.save_state}")

    # Step 3: Compare
    print(f"\n[3/4] Comparing reference vs current...")
    all_issues = []
    all_issues.extend(compare_model_params(gt_data.get('model_params', {}), cur_data.get('model_params', {})))
    all_issues.extend(compare_materials(gt_data.get('materials', {}), cur_data.get('materials', {})))
    all_issues.extend(compare_geometry(gt_data.get('geometry_objects', []), cur_data.get('geometry', [])))
    all_issues.extend(compare_windings(gt_data.get('windings', []), cur_data.get('windings', [])))
    all_issues.extend(compare_coils(gt_data.get('coils', []), cur_data.get('coils', [])))
    all_issues.extend(compare_solver(gt_data.get('solver_setups', []), cur_data.get('solver_setups', [])))
    all_issues.extend(compare_motion(gt_data.get('motion_setup', {}), cur_data.get('motion', {})))

    # Step 4: Report
    print(f"\n[4/4] Generating report...")
    report = generate_report(all_issues, gt_data, cur_data)
    print(report)

    with open(args.report, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {args.report}")

    # Auto-fix if requested
    if args.auto_fix:
        print("\n[Auto-fix] Attempting fixes...")
        try:
            import win32com.client
            app = win32com.client.Dispatch("Ansoft.ElectronicsDesktop")
            auto_fix(all_issues, app)
        except Exception as e:
            print(f"Auto-fix failed: {e}")

    errors = [i for i in all_issues if i['severity'] == 'ERROR']
    print(f"\n{'='*60}")
    print(f"RESULT: {len(errors)} errors, {len(all_issues) - len(errors)} warnings/info")
    print(f"{'='*60}")

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
