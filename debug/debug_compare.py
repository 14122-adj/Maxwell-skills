#!/usr/bin/env python3
"""
Debug Comparison Tool
Compares ground truth (from .aedt parser) with current Maxwell state (from COM).
Identifies differences and categorizes them by module:
  - Geometry (dimensions, object count)
  - Materials (missing/wrong materials)
  - Excitation (winding config, voltage, current)
  - Boundary conditions
  - Mesh settings
  - Solver configuration
  - Motion setup
"""

import json
import sys
from pathlib import Path


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def compare_materials(gt_mats, cur_mats):
    """Compare material lists and properties."""
    issues = []
    gt_names = set(gt_mats.keys())
    cur_names = set(cur_mats.keys())

    missing = gt_names - cur_names
    extra = cur_names - gt_names

    for name in missing:
        issues.append({
            'module': 'Materials',
            'severity': 'ERROR',
            'issue': f"Material '{name}' exists in reference but NOT in current model",
            'fix': f"Add material '{name}' to the model",
        })

    for name in extra:
        issues.append({
            'module': 'Materials',
            'severity': 'WARNING',
            'issue': f"Material '{name}' exists in current model but NOT in reference",
            'fix': f"Check if '{name}' is needed or remove it",
        })

    # Compare properties of common materials
    for name in gt_names & cur_names:
        gt_mat = gt_mats[name]
        cur_mat = cur_mats[name]

        # Compare BH curve points count
        gt_bh = len(gt_mat.get('bh_curve', []))
        if gt_bh > 0:
            # Check if current material has BH data
            cur_bh = len(cur_mat.get('bh_curve', []))
            if cur_bh == 0 and gt_bh > 0:
                issues.append({
                    'module': 'Materials',
                    'severity': 'WARNING',
                    'issue': f"Material '{name}': reference has {gt_bh//2} BH points, current has none",
                    'fix': f"Import BH curve for '{name}'",
                })

    return issues


def compare_geometry(gt_geom, cur_geom):
    """Compare geometry objects."""
    issues = []
    gt_names = {o['name'] for o in gt_geom}
    cur_names = {o['name'] for o in cur_geom}

    missing = gt_names - cur_names
    extra = cur_names - gt_names

    for name in missing:
        issues.append({
            'module': 'Geometry',
            'severity': 'ERROR',
            'issue': f"Object '{name}' exists in reference but NOT in current model",
            'fix': f"Create object '{name}'",
        })

    for name in extra:
        issues.append({
            'module': 'Geometry',
            'severity': 'INFO',
            'issue': f"Object '{name}' exists in current model but NOT in reference",
            'fix': f"Check if '{name}' is intentional",
        })

    # Compare materials assigned to common objects
    gt_dict = {o['name']: o for o in gt_geom}
    cur_dict = {o['name']: o for o in cur_geom}
    for name in gt_names & cur_names:
        gt_mat = gt_dict[name].get('material', '')
        cur_mat = cur_dict[name].get('material', '')
        if gt_mat and cur_mat and gt_mat != cur_mat:
            issues.append({
                'module': 'Geometry',
                'severity': 'ERROR',
                'issue': f"Object '{name}': reference material='{gt_mat}', current material='{cur_mat}'",
                'fix': f"Change material of '{name}' from '{cur_mat}' to '{gt_mat}'",
            })

    return issues


def compare_windings(gt_wind, cur_wind):
    """Compare winding configurations."""
    issues = []
    gt_dict = {w['name']: w for w in gt_wind}
    cur_dict = {w['name']: w for w in cur_wind}

    gt_names = set(gt_dict.keys())
    cur_names = set(cur_dict.keys())

    for name in gt_names - cur_names:
        issues.append({
            'module': 'Excitation',
            'severity': 'ERROR',
            'issue': f"Winding '{name}' exists in reference but NOT in current model",
            'fix': f"Create winding '{name}'",
        })

    for name in cur_names - gt_names:
        issues.append({
            'module': 'Excitation',
            'severity': 'WARNING',
            'issue': f"Winding '{name}' exists in current model but NOT in reference",
            'fix': f"Check if '{name}' is needed",
        })

    for name in gt_names & cur_names:
        gt_w = gt_dict[name]
        cur_w = cur_dict[name]

        # Compare voltage
        gt_v = gt_w.get('voltage', '')
        cur_v = cur_w.get('voltage', '')
        if gt_v and cur_v and gt_v != cur_v:
            issues.append({
                'module': 'Excitation',
                'severity': 'ERROR',
                'issue': f"Winding '{name}': voltage mismatch\n  Reference: {gt_v}\n  Current:  {cur_v}",
                'fix': f"Set voltage of '{name}' to '{gt_v}'",
            })

        # Compare resistance
        gt_r = gt_w.get('resistance', '')
        cur_r = cur_w.get('resistance', '')
        if gt_r and cur_r and gt_r != cur_r:
            issues.append({
                'module': 'Excitation',
                'severity': 'WARNING',
                'issue': f"Winding '{name}': resistance mismatch\n  Reference: {gt_r}\n  Current:  {cur_r}",
                'fix': f"Set resistance of '{name}' to '{gt_r}'",
            })

        # Compare inductance
        gt_l = gt_w.get('inductance', '')
        cur_l = cur_w.get('inductance', '')
        if gt_l and cur_l and gt_l != cur_l:
            issues.append({
                'module': 'Excitation',
                'severity': 'WARNING',
                'issue': f"Winding '{name}': inductance mismatch\n  Reference: {gt_l}\n  Current:  {cur_l}",
                'fix': f"Set inductance of '{name}' to '{gt_l}'",
            })

    return issues


def compare_coils(gt_coils, cur_coils):
    """Compare coil configurations."""
    issues = []
    gt_dict = {c['name']: c for c in gt_coils}
    cur_dict = {c['name']: c for c in cur_coils}

    for name in set(gt_dict.keys()) - set(cur_dict.keys()):
        issues.append({
            'module': 'Excitation',
            'severity': 'ERROR',
            'issue': f"Coil '{name}' exists in reference but NOT in current model",
            'fix': f"Create coil '{name}'",
        })

    for name in set(gt_dict.keys()) & set(cur_dict.keys()):
        gt_c = gt_dict[name]
        cur_c = cur_dict[name]

        if gt_c.get('winding_id') != cur_c.get('winding_id'):
            issues.append({
                'module': 'Excitation',
                'severity': 'ERROR',
                'issue': f"Coil '{name}': winding assignment mismatch (ref={gt_c.get('winding_id')}, cur={cur_c.get('winding_id')})",
                'fix': f"Assign '{name}' to correct winding",
            })

        if gt_c.get('polarity') != cur_c.get('polarity'):
            issues.append({
                'module': 'Excitation',
                'severity': 'ERROR',
                'issue': f"Coil '{name}': polarity mismatch (ref={gt_c.get('polarity')}, cur={cur_c.get('polarity')})",
                'fix': f"Set polarity of '{name}' to '{gt_c.get('polarity')}'",
            })

    return issues


def compare_solver(gt_solver, cur_solver):
    """Compare solver setups."""
    issues = []
    gt_dict = {s['name']: s for s in gt_solver}
    cur_dict = {s['name']: s for s in cur_solver}

    for name in set(gt_dict.keys()) - set(cur_dict.keys()):
        issues.append({
            'module': 'Solver',
            'severity': 'ERROR',
            'issue': f"Solver setup '{name}' exists in reference but NOT in current model",
            'fix': f"Create solver setup '{name}'",
        })

    for name in set(gt_dict.keys()) & set(cur_dict.keys()):
        gt_s = gt_dict[name]
        cur_s = cur_dict[name]

        if gt_s.get('stop_time') and cur_s.get('stop_time') and gt_s['stop_time'] != cur_s['stop_time']:
            issues.append({
                'module': 'Solver',
                'severity': 'ERROR',
                'issue': f"Setup '{name}': StopTime mismatch (ref={gt_s['stop_time']}, cur={cur_s['stop_time']})",
                'fix': f"Set StopTime to {gt_s['stop_time']}",
            })

        if gt_s.get('time_step') and cur_s.get('time_step') and gt_s['time_step'] != cur_s['time_step']:
            issues.append({
                'module': 'Solver',
                'severity': 'ERROR',
                'issue': f"Setup '{name}': TimeStep mismatch (ref={gt_s['time_step']}, cur={cur_s['time_step']})",
                'fix': f"Set TimeStep to {gt_s['time_step']}",
            })

    return issues


def compare_motion(gt_motion, cur_motion):
    """Compare motion setup."""
    issues = []
    if not gt_motion:
        return issues
    if not cur_motion:
        issues.append({
            'module': 'Motion',
            'severity': 'ERROR',
            'issue': "Motion setup exists in reference but NOT in current model",
            'fix': "Create Band motion setup",
        })
        return issues

    gt_vel = gt_motion.get('angular_velocity', '')
    cur_vel = cur_motion.get('angular_velocity', '')
    if gt_vel and cur_vel and gt_vel != cur_vel:
        issues.append({
            'module': 'Motion',
            'severity': 'ERROR',
            'issue': f"Angular velocity mismatch (ref={gt_vel}, cur={cur_vel})",
            'fix': f"Set angular velocity to {gt_vel}",
        })

    gt_axis = gt_motion.get('axis', '')
    cur_axis = cur_motion.get('axis', '')
    if gt_axis and cur_axis and gt_axis != cur_axis:
        issues.append({
            'module': 'Motion',
            'severity': 'ERROR',
            'issue': f"Rotation axis mismatch (ref={gt_axis}, cur={cur_axis})",
            'fix': f"Set rotation axis to {gt_axis}",
        })

    return issues


def compare_model_params(gt_params, cur_params):
    """Compare basic model parameters."""
    issues = []
    for key in ['solution_type', 'geometry_mode', 'model_depth']:
        gt_val = gt_params.get(key, '')
        cur_val = cur_params.get(key, '')
        if gt_val and cur_val and gt_val != cur_val:
            issues.append({
                'module': 'Model',
                'severity': 'ERROR',
                'issue': f"{key} mismatch (ref={gt_val}, cur={cur_val})",
                'fix': f"Set {key} to {gt_val}",
            })
    return issues


def generate_report(all_issues, gt_data, cur_data):
    """Generate a formatted debug report."""
    lines = []
    lines.append("=" * 70)
    lines.append("DEBUG COMPARISON REPORT")
    lines.append("=" * 70)
    lines.append(f"Reference: {gt_data.get('filename', 'N/A')}")
    lines.append(f"Current:   {cur_data.get('design_name', 'N/A')}")
    lines.append("")

    # Summary
    errors = [i for i in all_issues if i['severity'] == 'ERROR']
    warnings = [i for i in all_issues if i['severity'] == 'WARNING']
    infos = [i for i in all_issues if i['severity'] == 'INFO']

    lines.append(f"SUMMARY: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")
    lines.append("")

    # Group by module
    modules = {}
    for issue in all_issues:
        mod = issue['module']
        if mod not in modules:
            modules[mod] = []
        modules[mod].append(issue)

    for mod in ['Geometry', 'Materials', 'Excitation', 'Motion', 'Solver', 'Model']:
        if mod not in modules:
            continue
        mod_issues = modules[mod]
        lines.append(f"--- {mod} ({len(mod_issues)} issues) ---")
        for issue in mod_issues:
            sev = issue['severity']
            marker = '!!!' if sev == 'ERROR' else ('! ' if sev == 'WARNING' else '  ')
            lines.append(f"  {marker}[{sev}] {issue['issue']}")
            lines.append(f"       FIX: {issue['fix']}")
        lines.append("")

    if not all_issues:
        lines.append("  No differences found - model matches reference!")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: python debug_compare.py <ground_truth.json> <current_state.json> [report.txt]")
        sys.exit(1)

    gt_data = load_json(sys.argv[1])
    cur_data = load_json(sys.argv[2])

    all_issues = []
    all_issues.extend(compare_model_params(gt_data.get('model_params', {}), cur_data.get('model_params', {})))
    all_issues.extend(compare_materials(gt_data.get('materials', {}), cur_data.get('materials', {})))
    all_issues.extend(compare_geometry(gt_data.get('geometry_objects', []), cur_data.get('geometry', [])))
    all_issues.extend(compare_windings(gt_data.get('windings', []), cur_data.get('windings', [])))
    all_issues.extend(compare_coils(gt_data.get('coils', []), cur_data.get('coils', [])))
    all_issues.extend(compare_solver(gt_data.get('solver_setups', []), cur_data.get('solver_setups', [])))
    all_issues.extend(compare_motion(gt_data.get('motion_setup', {}), cur_data.get('motion', {})))

    report = generate_report(all_issues, gt_data, cur_data)
    print(report)

    if len(sys.argv) > 3:
        with open(sys.argv[3], 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport saved to: {sys.argv[3]}")

    # Return exit code based on errors
    errors = [i for i in all_issues if i['severity'] == 'ERROR']
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
