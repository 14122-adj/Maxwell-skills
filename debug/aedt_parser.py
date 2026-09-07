#!/usr/bin/env python3
"""
AEDT Ground Truth Extractor v3
Scans .aedt line-by-line, tracking block depth to extract all key parameters.
"""

import re
import json
import sys
from pathlib import Path


def parse_aedt(filepath):
    """Parse AEDT file and return a dict of ground truth parameters."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    gt = {
        'filename': Path(filepath).name,
        'version': '',
        'units': '',
        'solution_type': '',
        'geometry_mode': '',
        'model_depth': '',
        'background_material': '',
        'design_variables': {},
        'materials': {},
        'geometry_objects': [],
        'coils': [],
        'windings': [],
        'mesh_ops': [],
        'solver_setups': [],
        'motion_setup': {},
        'boundaries': [],
    }

    full = ''.join(lines)
    
    # Version
    m = re.search(r"Version\((\d+),\s*(\d+)\)", full)
    if m:
        gt['version'] = f"{m.group(1)}.{m.group(2)}"

    # Find main Maxwell2DModel (has ModelDepth)
    model_start = -1
    model_end = -1
    for i, line in enumerate(lines):
        if "$begin 'Maxwell2DModel'" in line:
            # Check if this one has ModelDepth
            for j in range(i, min(i+30, len(lines))):
                if "ModelDepth=" in lines[j]:
                    model_start = i
                    break
            if model_start >= 0:
                break
    
    if model_start < 0:
        print("ERROR: No Maxwell2DModel found")
        return gt

    # Find end of this Maxwell2DModel (track depth)
    depth = 0
    for i in range(model_start, len(lines)):
        if "$begin 'Maxwell2DModel'" in lines[i]:
            depth += 1
        elif "$end 'Maxwell2DModel'" in lines[i]:
            depth -= 1
            if depth == 0:
                model_end = i
                break

    model_lines = lines[model_start:model_end+1]

    # Extract basic params from model block
    for line in model_lines:
        s = line.strip()
        if s.startswith('ModelDepth='):
            gt['model_depth'] = s.split('=', 1)[1].strip("'\"")
        elif s.startswith('SolutionType='):
            gt['solution_type'] = s.split('=', 1)[1].strip("'\"")
        elif s.startswith('GeometryMode='):
            gt['geometry_mode'] = s.split('=', 1)[1].strip("'\"")
        elif s.startswith('BackgroundMaterialName='):
            gt['background_material'] = s.split('=', 1)[1].strip("'\"")
        elif s.startswith('Units='):
            gt['units'] = s.split('=', 1)[1].strip("'\"")

    # Extract design variables from VariableProp lines
    for line in model_lines:
        vm = re.search(r"VariableProp\('(\w+)',\s*'UD',\s*'[^']*',\s*'([^']*)'\)", line)
        if vm:
            gt['design_variables'][vm.group(1)] = vm.group(2)

    # Extract materials from Definitions block
    def_start = None
    def_end = None
    for i, line in enumerate(lines):
        if "$begin 'Definitions'" in line and i < model_start:
            def_start = i
    if def_start is not None:
        depth = 0
        for i in range(def_start, len(lines)):
            if "$begin 'Definitions'" in lines[i]:
                depth += 1
            elif "$end 'Definitions'" in lines[i]:
                depth -= 1
                if depth == 0:
                    def_end = i
                    break
    
    if def_start and def_end:
        def_lines = lines[def_start:def_end+1]
        # Find Materials block
        mat_start = None
        for i, line in enumerate(def_lines):
            if "$begin 'Materials'" in line:
                mat_start = i
                break
        
        if mat_start is not None:
            # Parse material blocks
            i = mat_start + 1
            while i < len(def_lines):
                line = def_lines[i].strip()
                m = re.match(r"""\$begin\s+'([^']+)'""", line)
                if m:
                    mat_name = m.group(1)
                    # Find matching $end
                    depth = 1
                    mat_content = []
                    j = i + 1
                    while j < len(def_lines) and depth > 0:
                        jl = def_lines[j].strip()
                        if jl.startswith("$begin"):
                            depth += 1
                        elif jl.startswith("$end"):
                            depth -= 1
                        if depth > 0:
                            mat_content.append(def_lines[j])
                        j += 1
                    
                    mat = {'name': mat_name, 'bh_curve': []}
                    for ml in mat_content:
                        s = ml.strip()
                        if s.startswith('permeability='):
                            mat['permeability'] = s.split('=', 1)[1].strip("'\"")
                        elif s.startswith('conductivity='):
                            mat['conductivity'] = s.split('=', 1)[1].strip("'\"")
                        elif s.startswith('mass_density='):
                            mat['mass_density'] = s.split('=', 1)[1].strip("'\"")
                        elif s.startswith('core_loss_kh='):
                            mat['core_loss_kh'] = s.split('=', 1)[1].strip("'\"")
                        elif s.startswith('core_loss_kc='):
                            mat['core_loss_kc'] = s.split('=', 1)[1].strip("'\"")
                        elif s.startswith('core_loss_ke='):
                            mat['core_loss_ke'] = s.split('=', 1)[1].strip("'\"")
                        elif 'Library=' in s:
                            lib_m = re.search(r"Library='([^']*)'", s)
                            if lib_m:
                                mat['library'] = lib_m.group(1)
                        
                        # BH curve
                        bm = re.match(r"""\s*Points\[\d+:\s*(.+)\]""", s)
                        if bm:
                            try:
                                mat['bh_curve'] = [float(x.strip()) for x in bm.group(1).split(',')]
                            except:
                                pass
                        
                        # Coercivity
                        if 'Magnitude=' in s and 'A_per_meter' in s:
                            cm = re.search(r"Magnitude='([^']+)'", s)
                            if cm:
                                mat['coercivity'] = cm.group(1)
                    
                    gt['materials'][mat_name] = mat
                    i = j
                    continue
                i += 1

    # Filter out non-material entries
    non_material_keys = [k for k in gt['materials'] if not gt['materials'][k].get('bh_curve') 
                         and not gt['materials'][k].get('permeability')
                         and not gt['materials'][k].get('conductivity')
                         and not gt['materials'][k].get('mass_density')]
    for k in non_material_keys:
        del gt['materials'][k]

    # Extract geometry objects from ToplevelParts in model
    # Find ToplevelParts within model_lines
    tp_start = -1
    for i, line in enumerate(model_lines):
        if "$begin 'ToplevelParts'" in line:
            tp_start = i
            break

    if tp_start >= 0:
        # Parse GeometryPart blocks within ToplevelParts
        depth = 0
        in_toplevel = False
        i = tp_start
        while i < len(model_lines):
            line = model_lines[i]
            if "$begin 'ToplevelParts'" in line:
                in_toplevel = True
                depth = 1
                i += 1
                continue
            
            if in_toplevel:
                if "$begin 'GeometryPart'" in line:
                    # Found a geometry part, extract its name and material
                    part_name = ""
                    part_material = ""
                    dll_name = ""
                    dll_params = {}
                    
                    # Scan until matching $end 'GeometryPart'
                    pd = 1
                    j = i + 1
                    while j < len(model_lines) and pd > 0:
                        pl = model_lines[j].strip()
                        if "$begin 'GeometryPart'" in pl:
                            pd += 1
                        elif "$end 'GeometryPart'" in pl:
                            pd -= 1
                        
                        if pd > 0:
                            # Extract name
                            nm = re.search(r"Name='([^']+)'", pl)
                            if nm and not part_name:
                                part_name = nm.group(1)
                            # Extract material
                            mv = re.search(r"MaterialValue='\"([^\"]+)\"'", pl)
                            if mv:
                                part_material = mv.group(1)
                            # Extract DLL name
                            dm = re.search(r"DllName='([^']+)'", pl)
                            if dm:
                                dll_name = dm.group(1)
                            # Extract DLL params
                            pm = re.search(r"Name='([^']+)'\s+Value='([^']+)'", pl)
                            if pm:
                                dll_params[pm.group(1)] = pm.group(2)
                        
                        j += 1
                    
                    if part_name:
                        gt['geometry_objects'].append({
                            'name': part_name,
                            'material': part_material,
                            'dll_name': dll_name,
                            'dll_params': dll_params,
                        })
                    i = j
                    continue
                
                if "$end 'ToplevelParts'" in line:
                    break
            i += 1

    # Extract boundary setup (windings + coils) from model_lines
    for i, line in enumerate(model_lines):
        wm = re.match(r"""\s*\$begin\s+'(\w+)'.*""", line.strip())
        if not wm:
            continue
        bname = wm.group(1)
        # Look ahead up to 10 lines to find BoundType
        bound_type = ""
        bparams = {}
        for j in range(i+1, min(i+20, len(model_lines))):
            jl = model_lines[j].strip()
            if jl.startswith('$end'):
                break
            if jl.startswith("BoundType='"):
                bound_type = jl.split("=", 1)[1].strip("'\"")
            for key in ['Type', 'Current', 'Resistance', 'Inductance', 'Voltage',
                        'ParallelBranchesNum', 'ID', 'Conductor number', 'Winding', 'PolarityType']:
                if jl.startswith(key + '=') or jl.startswith("'" + key + "'="):
                    bparams[key] = jl.split('=', 1)[1].strip("'\"")

        if bound_type == 'Winding Group':
            gt['windings'].append({
                'name': bname,
                'type': bparams.get('Type', ''),
                'current': bparams.get('Current', ''),
                'resistance': bparams.get('Resistance', ''),
                'inductance': bparams.get('Inductance', ''),
                'voltage': bparams.get('Voltage', ''),
                'parallel_branches': bparams.get('ParallelBranchesNum', '1'),
            })
        elif bound_type == 'Coil':
            gt['coils'].append({
                'name': bname,
                'conductor_number': bparams.get('Conductor number', '0'),
                'winding_id': bparams.get('Winding', '0'),
                'polarity': bparams.get('PolarityType', ''),
            })

    # Extract mesh operations from model_lines
    for i, line in enumerate(model_lines):
        ml = line.strip()
        if ml.startswith("$begin 'SurfApprox") or ml.startswith("$begin 'Length"):
            opname_m = re.match(r"""\$begin\s+'([^']+)'""", ml)
            if opname_m:
                opname = opname_m.group(1)
                op_params = {}
                for j in range(i+1, min(i+20, len(model_lines))):
                    opl = model_lines[j].strip()
                    if opl.startswith('$end'):
                        break
                    if opl.startswith('Type='):
                        op_params['type'] = opl.split('=', 1)[1].strip("'\"")
                    elif opl.startswith('SurfDev='):
                        op_params['SurfDev'] = opl.split('=', 1)[1].strip("'\"")
                    elif opl.startswith('NormalDev='):
                        op_params['NormalDev'] = opl.split('=', 1)[1].strip("'\"")
                    elif opl.startswith('MaxLength='):
                        op_params['MaxLength'] = opl.split('=', 1)[1].strip("'\"")
                    elif opl.startswith('CurvedSurfaceApproxChoice='):
                        op_params['SurfApprox'] = opl.split('=', 1)[1].strip("'\"")
                gt['mesh_ops'].append({'name': opname, **op_params})

    # Extract solver setups from model_lines
    for i, line in enumerate(model_lines):
        sm = re.match(r"""\s*\$begin\s+'(Setup\d+)'""", line.strip())
        if sm:
            sname = sm.group(1)
            sparams = {}
            depth = 1
            for j in range(i+1, len(model_lines)):
                sl = model_lines[j].strip()
                if "$begin 'MeshLink'" in sl or "$begin " in sl:
                    depth += 1
                elif "$end " in sl:
                    depth -= 1
                    if depth == 0:
                        break
                if depth == 1:
                    if sl.startswith('StopTime='):
                        sparams['stop_time'] = sl.split('=', 1)[1].strip("'\"")
                    elif sl.startswith('TimeStep='):
                        sparams['time_step'] = sl.split('=', 1)[1].strip("'\"")
                    elif sl.startswith('SetupType='):
                        sparams['setup_type'] = sl.split('=', 1)[1].strip("'\"")
            gt['solver_setups'].append({
                'name': sname,
                'setup_type': sparams.get('setup_type', 'Transient'),
                'stop_time': sparams.get('stop_time', ''),
                'time_step': sparams.get('time_step', ''),
            })

    # Extract motion setup
    for i, line in enumerate(model_lines):
        if "$begin 'MotionSetup1'" in line:
            for j in range(i+1, min(i+20, len(model_lines))):
                ml = model_lines[j].strip()
                if ml.startswith('$end'):
                    break
                if ml.startswith("MotionType='"):
                    gt['motion_setup']['type'] = ml.split('=', 1)[1].strip("'\"")
                elif ml.startswith("'Move Type'="):
                    gt['motion_setup']['move_type'] = ml.split('=', 1)[1].strip("'\"")
                elif ml.startswith("'Angular Velocity'="):
                    gt['motion_setup']['angular_velocity'] = ml.split('=', 1)[1].strip("'\"")
                elif ml.startswith("Axis='"):
                    gt['motion_setup']['axis'] = ml.split('=', 1)[1].strip("'\"")
                elif ml.startswith("InitPos='"):
                    gt['motion_setup']['init_pos'] = ml.split('=', 1)[1].strip("'\"")

    return gt


def print_summary(gt):
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"AEDT Ground Truth: {gt['filename']}")
    lines.append(f"{'='*60}")
    lines.append(f"Version: {gt['version']}, Units: {gt['units']}")
    lines.append(f"Solution: {gt['solution_type']}, Mode: {gt['geometry_mode']}")
    lines.append(f"Model Depth: {gt['model_depth']}, Background: {gt['background_material']}")
    if gt['design_variables']:
        lines.append(f"Variables: {gt['design_variables']}")
    
    lines.append(f"\n--- Materials ({len(gt['materials'])}) ---")
    for name, mat in gt['materials'].items():
        bh_pts = len(mat.get('bh_curve', [])) // 2
        lines.append(f"  {name}: mu={mat.get('permeability','?')}, sigma={mat.get('conductivity','?')}, "
                     f"rho={mat.get('mass_density','?')}, BH={bh_pts}pts, lib={mat.get('library','?')}")
    
    lines.append(f"\n--- Geometry Objects ({len(gt['geometry_objects'])}) ---")
    for obj in gt['geometry_objects']:
        dll = obj.get('dll_name', '')
        params = obj.get('dll_params', {})
        param_str = ', '.join(f"{k}={v}" for k, v in params.items()) if params else ''
        lines.append(f"  {obj['name']}: mat={obj['material']}, dll={dll}({param_str})")
    
    lines.append(f"\n--- Windings ({len(gt['windings'])}) ---")
    for w in gt['windings']:
        lines.append(f"  {w['name']}: type={w['type']}, V={w['voltage'][:60] if w['voltage'] else 'N/A'}, "
                     f"R={w['resistance']}, L={w['inductance']}")
    
    lines.append(f"\n--- Coils ({len(gt['coils'])}) ---")
    for c in gt['coils']:
        lines.append(f"  {c['name']}: conductors={c['conductor_number']}, winding={c['winding_id']}, "
                     f"polarity={c['polarity']}")
    
    lines.append(f"\n--- Mesh Operations ({len(gt['mesh_ops'])}) ---")
    for m in gt['mesh_ops']:
        lines.append(f"  {m['name']}: {m}")
    
    lines.append(f"\n--- Solver Setups ({len(gt['solver_setups'])}) ---")
    for s in gt['solver_setups']:
        lines.append(f"  {s['name']}: {s['setup_type']}, stop={s['stop_time']}, step={s['time_step']}")
    
    if gt['motion_setup']:
        lines.append(f"\n--- Motion Setup ---")
        lines.append(f"  {gt['motion_setup']}")
    
    print('\n'.join(lines))


def main():
    if len(sys.argv) < 2:
        print("Usage: python aedt_parser.py <file.aedt> [output.json]")
        sys.exit(1)

    gt = parse_aedt(sys.argv[1])
    print_summary(gt)

    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            json.dump(gt, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to: {sys.argv[2]}")


if __name__ == '__main__':
    main()
