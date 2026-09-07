#!/usr/bin/env python3
"""
Maxwell Bridge — 唯一抽象层
==========================
项目脚本永远只跟本文件说话，不直接碰 MCP 工具名、不直接碰 IronPython COM API。

两条运行路径：
  1. MCP 工具逐个调用（backends='mcp'）：通过 run_script 注入 IronPython
  2. 脚本生成（backends='text'）   ：返回 IronPython 脚本文本供 MCP `run_script` 执行

做三件事：
  A. 收敛命名漂移：subtract→subtract_objects、draw_region_pad→create_region
  B. 补齐 15 个真缺口：set_model_units / duplicate_around_axis /
     set_magnet_orientation / add_magnetostatic_setup / add_transient_setup /
     analyze_setup / assign_band / assign_mesh_skin_depth /
     create_winding_setup / export_data / get_field_data /
     get_induced_voltage / get_loss_data 等
  C. 带 dry_run/mock 模式：无 Maxwell 连接也能跑通脚本逻辑

用法：
    from maxwell_bridge import MaxwellBridge
    bridge = MaxwellBridge(dry_run=True)
    bridge.set_model_units("mm")
    out = bridge.get_design_info()    # dry_run 返回 mock 值
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Optional


# ══════════════════════════════════════════════════════════════
#  MCP 真实工具清单（71个，从 server.py 摘录）— 用于实算后端
# ══════════════════════════════════════════════════════════════
MCP_TOOLS: set[str] = {
    # 连接/项目/设计
    "connect_to_maxwell", "disconnect_from_maxwell", "get_maxwell_status",
    "new_project", "open_project", "save_project", "close_project", "list_projects",
    "create_design", "set_active_design", "list_designs", "delete_design", "get_design_info",
    # 几何
    "draw_box", "draw_cylinder", "draw_rectangle", "draw_circle", "draw_line",
    "unite_objects", "subtract_objects", "intersect_objects",
    "move_object", "duplicate_object", "scale_object", "rename_object", "list_objects",
    "create_region",
    # 材料/属性
    "assign_material", "set_object_color", "set_object_solve_inside", "add_custom_material",
    # 边界/激励
    "assign_vector_potential", "assign_balloon_boundary", "assign_master_slave_boundary",
    "assign_current_excitation", "assign_voltage_excitation",
    "assign_winding", "add_turns_to_winding",
    "assign_force_parameter", "assign_torque_parameter", "assign_motion_setup",
    # 网格
    "assign_mesh_operation", "assign_skin_depth_mesh",
    # 求解
    "create_analysis_setup", "create_parametric_sweep", "create_optimization",
    "validate_design", "analyze", "analyze_all", "analyze_parametric_sweep",
    # 后处理
    "get_force", "get_torque", "get_flux_linkage", "get_inductance",
    "get_solution_info", "get_convergence_data",
    "create_field_plot", "export_field_plot", "export_mesh",
    "create_report", "export_report_data",
    # 视图
    "fit_view", "set_view", "hide_object", "show_object", "show_all_objects",
    # 变量
    "set_variable", "get_variables",
    # 通用
    "run_script", "execute_console_command", "export_project_archive",
    "get_status_resource", "get_projects_resource",
}


# ══════════════════════════════════════════════════════════════
#  命名漂移映射 —— 脚本统一干净的名字 → MCP 真实工具名
# ══════════════════════════════════════════════════════════════
NAME_DRIFT: dict[str, str] = {
    "subtract": "subtract_objects",
    "draw_region_pad": "create_region",
    "create_region_pad": "create_region",
    "analyze_setup": "analyze",
    "add_mesh_operation": "assign_mesh_operation",
}


# ══════════════════════════════════════════════════════════════
#  真·缺口清单（server 没有，bridge 内部用 run_script 兜底实现）
# ══════════════════════════════════════════════════════════════
MISSING_TOOLS: set[str] = {
    "set_model_units", "duplicate_around_axis", "set_magnet_orientation",
    "add_magnetostatic_setup", "add_transient_setup",
    "assign_band", "assign_mesh_skin_depth",
    "create_winding_setup",
    "export_data", "get_field_data", "get_induced_voltage", "get_loss_data",
    "create_winding_group", "add_winding_coils", "assign_coil_group",
}


# ══════════════════════════════════════════════════════════════
#  MCP 适配器：bridge 调用 (位置参数, kwargs) → server 工具 arguments
#  ── 仅 backend=="mcp" 实算路径使用；签名差异/单位转换在此收敛 ──
# ══════════════════════════════════════════════════════════════
class _AdapterSkip(Exception):
    """适配器主动放弃 MCP 路由（如 bridge 缺服务端必需参数），回退 text。"""


def _u(v, unit="mm"):
    """数值 → 带单位字符串；字符串/None 原样返回（供 server 的 length/angle 参数）。"""
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return f"{v}{unit}"
    return str(v)


def _as_list(v):
    """标量 → 单元素列表；列表/元组 → list；None → []。"""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _kw(args, kwargs, *names, defaults=()):
    """按 names 顺序从 kwargs 取值，缺失则回退到 args 位置，再缺失用 defaults。"""
    out = []
    ai = 0
    for i, n in enumerate(names):
        if n in kwargs:
            out.append(kwargs[n])
        elif ai < len(args):
            out.append(args[ai]); ai += 1
        else:
            d = defaults[i] if i < len(defaults) else None
            out.append(d)
    return out


# 每个 adapter 签名: (args: tuple, kwargs: dict, unit: str) -> dict | None
# 返回 None 或抛 _AdapterSkip 表示放弃 MCP 路由。
def _a_connect_to_maxwell(a, k, u):
    v, = _kw(a, k, "version", defaults=("",))
    return {"version": v or ""}


def _a_disconnect_from_maxwell(a, k, u):
    return {}


def _a_get_maxwell_status(a, k, u):
    return {}


def _a_new_project(a, k, u):
    return {}


def _a_open_project(a, k, u):
    fp, = _kw(a, k, "file_path")
    return {"file_path": fp}


def _a_save_project(a, k, u):
    fp, = _kw(a, k, "file_path", defaults=("",))
    return {"file_path": fp or ""}


def _a_close_project(a, k, u):
    nm, = _kw(a, k, "name", defaults=("",))
    return {"name": nm or ""}


def _a_list_projects(a, k, u):
    return {}


def _a_create_design(a, k, u):
    # bridge: (name, solution_type) ; server: design_type, design_name, solution_type
    name, stype = _kw(a, k, "name", "solution_type", defaults=("", "Transient"))
    dtype = k.get("design_type", "Maxwell 2D")  # 项目默认 2D 横截面
    return {"design_type": dtype, "design_name": name or "", "solution_type": stype}


def _a_set_active_design(a, k, u):
    nm, = _kw(a, k, "design_name")
    return {"design_name": nm}


def _a_list_designs(a, k, u):
    return {}


def _a_delete_design(a, k, u):
    nm, = _kw(a, k, "design_name")
    return {"design_name": nm}


def _a_get_design_info(a, k, u):
    return {}


def _a_draw_box(a, k, u):
    name, x, y, z, dx, dy, dz, mat = _kw(
        a, k, "name", "x", "y", "z", "dx", "dy", "dz", "material",
        defaults=("", 0, 0, 0, 10, 10, 10, "vacuum"))
    return {"name": name, "x": _u(x, u), "y": _u(y, u), "z": _u(z, u),
            "dx": _u(dx, u), "dy": _u(dy, u), "dz": _u(dz, u), "material": mat}


def _a_draw_cylinder(a, k, u):
    name, x, y, z, r, h, mat = _kw(
        a, k, "name", "x", "y", "z", "radius", "height", "material",
        defaults=("", 0, 0, 0, 5, 10, "vacuum"))
    axis = k.get("axis", "Z")
    return {"name": name, "x": _u(x, u), "y": _u(y, u), "z": _u(z, u),
            "radius": _u(r, u), "height": _u(h, u), "axis": axis, "material": mat}


def _a_draw_rectangle(a, k, u):
    # server 的 draw_rectangle 无 material 参数
    name, x, y, z, w, h = _kw(
        a, k, "name", "x", "y", "z", "width", "height",
        defaults=("", 0, 0, 0, 10, 10))
    axis = k.get("axis", "Z")
    return {"name": name, "x": _u(x, u), "y": _u(y, u), "z": _u(z, u),
            "width": _u(w, u), "height": _u(h, u), "axis": axis}


def _a_draw_circle(a, k, u):
    # server 的 draw_circle 无 material 参数
    name, x, y, z, r = _kw(a, k, "name", "x", "y", "z", "radius",
                           defaults=("", 0, 0, 0, 5))
    axis = k.get("axis", "Z")
    return {"name": name, "x": _u(x, u), "y": _u(y, u), "z": _u(z, u),
            "radius": _u(r, u), "axis": axis}


def _a_draw_line(a, k, u):
    # bridge: (name, points=[p0,p1,...]) ; server: start=[x,y,z], end=[x,y,z]
    name, points = _kw(a, k, "name", "points", defaults=("", None))
    pts = points or k.get("start") and [k.get("start"), k.get("end")]
    if not pts or len(pts) < 2:
        raise _AdapterSkip("draw_line 需要 start/end")
    s, e = pts[0], pts[1]
    return {"name": name, "start": _as_list(s), "end": _as_list(e)}


def _a_unite_objects(a, k, u):
    objs, keep = _kw(a, k, "objects", "keep_originals", defaults=([], False))
    return {"objects": _as_list(objs), "keep_originals": bool(keep)}


def _a_subtract_objects(a, k, u):
    # bridge 用 blank_parts/tool_parts；server 用 blank_objects/tool_objects
    blank, tool, keep = _kw(
        a, k, "blank_parts", "tool_parts", "keep_originals",
        defaults=([], [], False))
    # 兼容旧名
    blank = blank if "blank_parts" in k or len(a) > 0 else k.get("blank_objects", blank)
    tool = tool if "tool_parts" in k or len(a) > 1 else k.get("tool_objects", tool)
    return {"blank_objects": _as_list(blank), "tool_objects": _as_list(tool),
            "keep_originals": bool(keep)}


def _a_intersect_objects(a, k, u):
    objs, keep = _kw(a, k, "objects", "keep_originals", defaults=([], False))
    return {"objects": _as_list(objs), "keep_originals": bool(keep)}


def _a_move_object(a, k, u):
    name, dx, dy, dz = _kw(a, k, "name", "dx", "dy", "dz",
                           defaults=("", 0, 0, 0))
    return {"object_name": name, "dx": _u(dx, u), "dy": _u(dy, u), "dz": _u(dz, u)}


def _a_duplicate_object(a, k, u):
    # bridge 签名 (name, count, dx, dy, dz)；server (object_name, dx, dy, dz, count)
    name, count, dx, dy, dz = _kw(
        a, k, "name", "count", "dx", "dy", "dz", defaults=("", 1, 0, 0, 0))
    return {"object_name": name, "dx": _u(dx, u), "dy": _u(dy, u), "dz": _u(dz, u),
            "count": int(count)}


def _a_scale_object(a, k, u):
    name, factor = _kw(a, k, "name", "factor", defaults=("", 1.0))
    return {"object_name": name, "sx": factor, "sy": factor, "sz": factor}


def _a_rename_object(a, k, u):
    old, new = _kw(a, k, "old_name", "new_name")
    return {"old_name": old, "new_name": new}


def _a_list_objects(a, k, u):
    return {}


def _a_create_region(a, k, u):
    pad, = _kw(a, k, "padding", defaults=(10.0,))
    pad_s = _u(pad, u)
    return {"pad_x": pad_s, "pad_y": pad_s, "pad_z": pad_s}


def _a_assign_material(a, k, u):
    obj, mat = _kw(a, k, "object_name", "material", defaults=("", "vacuum"))
    return {"object_name": obj, "material": mat}


def _a_set_object_color(a, k, u):
    obj, color = _kw(a, k, "object_name", "color", defaults=("", "(255 0 0)"))
    return {"object_name": obj, "color": color}


def _a_set_object_solve_inside(a, k, u):
    obj, si = _kw(a, k, "object_name", "solve_inside", defaults=("", True))
    return {"object_name": obj, "solve_inside": bool(si)}


def _a_add_custom_material(a, k, u):
    name = _kw(a, k, "name", defaults=("",))[0]
    props = {kk: vv for kk, vv in k.items() if kk != "name"}
    if not props:
        props = a[1] if len(a) > 1 and isinstance(a[1], dict) else {}
    return {"material_name": name, "properties": props}


def _a_assign_vector_potential(a, k, u):
    # bridge: objects(list) ; server: object_name(单)
    objs, value = _kw(a, k, "objects", "value", defaults=([], "0"))
    lst = _as_list(objs)
    obj = lst[0] if lst else ""
    return {"object_name": obj, "value": str(value)}


def _a_assign_balloon_boundary(a, k, u):
    objs, = _kw(a, k, "objects", defaults=([],))
    return {"objects": _as_list(objs)}


def _a_assign_master_slave_boundary(a, k, u):
    master, slave = _kw(a, k, "master", "slave", defaults=([], []))
    angle = k.get("angle", "0deg")
    return {"master_objects": _as_list(master), "slave_objects": _as_list(slave),
            "angle": angle}


def _a_assign_current_excitation(a, k, u):
    objs, current = _kw(a, k, "objects", "current", defaults=([], "1A"))
    return {"objects": _as_list(objs), "current": str(current)}


def _a_assign_voltage_excitation(a, k, u):
    objs, voltage = _kw(a, k, "objects", "voltage", defaults=([], "0V"))
    return {"objects": _as_list(objs), "voltage": str(voltage)}


def _a_assign_winding(a, k, u):
    # bridge: name, winding_type, current, resistance, ... ; server: winding_name, excitation_type, ...
    name, wtype, current, resistance = _kw(
        a, k, "name", "winding_type", "current", "resistance",
        defaults=("", "Current", "0A", "0"))
    return {"winding_name": name, "excitation_type": wtype,
            "current": str(current), "resistance": str(resistance),
            "inductance": str(k.get("inductance", "0")),
            "voltage": str(k.get("voltage", "0")),
            "parallel_branches": int(k.get("parallel_branches", 1))}


def _a_add_turns_to_winding(a, k, u):
    # bridge 签名缺 objects（server 必需）→ 放弃 MCP，回退 text
    raise _AdapterSkip("bridge.add_turns_to_winding 缺 objects 参数")


def _a_assign_force_parameter(a, k, u):
    objs, = _kw(a, k, "objects", defaults=([],))
    return {"objects": _as_list(objs)}


def _a_assign_torque_parameter(a, k, u):
    objs, = _kw(a, k, "objects", defaults=([],))
    axis = k.get("axis", "Z")
    return {"objects": _as_list(objs), "axis": axis}


def _a_assign_motion_setup(a, k, u):
    # bridge: name, motion_type, axis, angular_velocity, is_positive
    name, mtype, axis, av, pos = _kw(
        a, k, "name", "motion_type", "axis", "angular_velocity", "is_positive",
        defaults=("Band", "Rotate", "Z", "0rpm", True))
    # server: objects(REQ), motion_type, axis, positive, angular_velocity
    return {"objects": _as_list(name), "motion_type": mtype, "axis": axis,
            "positive": bool(pos), "angular_velocity": str(av)}


def _a_assign_mesh_operation(a, k, u):
    objs, max_len = _kw(a, k, "objects", "max_length", defaults=([], "1mm"))
    return {"objects": _as_list(objs), "element_size": _u(max_len, u)}


def _a_assign_skin_depth_mesh(a, k, u):
    objs, sd = _kw(a, k, "objects", "skin_depth", defaults=([], "1mm"))
    return {"objects": _as_list(objs), "skin_depth": _u(sd, u)}


def _a_create_analysis_setup(a, k, u):
    # bridge 多出 stop_time/time_step（server 无），映射 solver_type→solution_type
    name, stype = _kw(a, k, "setup_name", "solver_type",
                      defaults=("Setup1", "Transient"))
    max_passes = k.get("max_passes", 10)
    return {"setup_name": name, "solution_type": stype,
            "max_passes": int(max_passes) if max_passes else 10}


def _a_create_parametric_sweep(a, k, u):
    name, = _kw(a, k, "sweep_name", defaults=("Sweep1",))
    return {"sweep_name": name}


def _a_create_optimization(a, k, u):
    name, = _kw(a, k, "name", defaults=("Opt1",))
    return {"opt_name": name}


def _a_validate_design(a, k, u):
    return {}


def _a_analyze(a, k, u):
    name, = _kw(a, k, "setup_name", defaults=("Setup1",))
    return {"setup_name": name}


def _a_analyze_all(a, k, u):
    return {}


def _a_analyze_parametric_sweep(a, k, u):
    name, = _kw(a, k, "sweep_name", defaults=("Sweep1",))
    return {"sweep_name": name}


def _a_get_force(a, k, u):
    # bridge: objects=None（与 server 的 force_name 语义不同）；尝试用 objects[0] 作 force_name
    objs, = _kw(a, k, "objects", defaults=(None,))
    if objs:
        fn = _as_list(objs)[0]
        return {"force_name": fn}
    return {"force_name": k.get("force_name", "Force1")}


def _a_get_torque(a, k, u):
    objs, setup = _kw(a, k, "objects", "setup_name", defaults=(None, ""))
    if objs:
        return {"torque_name": _as_list(objs)[0],
                "setup_name": setup or "Setup1"}
    return {"torque_name": k.get("torque_name", "Torque1"),
            "setup_name": setup or "Setup1"}


def _a_get_flux_linkage(a, k, u):
    w, = _kw(a, k, "winding", defaults=("WindingA",))
    return {"winding_name": w}


def _a_get_inductance(a, k, u):
    w, = _kw(a, k, "winding", defaults=("WindingA",))
    return {"winding_name": w}


def _a_get_solution_info(a, k, u):
    name, = _kw(a, k, "setup_name", defaults=("Setup1",))
    return {"setup_name": name}


def _a_get_convergence_data(a, k, u):
    name, = _kw(a, k, "setup_name", defaults=("Setup1",))
    return {"setup_name": name}


def _a_create_field_plot(a, k, u):
    q, objs = _kw(a, k, "quantity", "objects", defaults=("Mag_B", None))
    return {"quantity_name": q, "objects": _as_list(objs) or None}


def _a_export_field_plot(a, k, u):
    name, path = _kw(a, k, "plot_name", "file_path", defaults=("", ""))
    return {"plot_name": name, "file_path": path}


def _a_export_mesh(a, k, u):
    path, = _kw(a, k, "file_path", defaults=("",))
    return {"file_path": path}


def _a_create_report(a, k, u):
    name, rtype, xq, yqs = _kw(
        a, k, "name", "report_type", "x_quantity", "y_quantities",
        defaults=("Report1", "Data Table", "", None))
    return {"report_name": name, "report_type": rtype, "category": xq or "Force",
            "quantity": (yqs[0] if yqs else "Force1")}


def _a_export_report_data(a, k, u):
    name, path = _kw(a, k, "report_name", "file_path", defaults=("", ""))
    return {"report_name": name, "file_path": path}


def _a_export_project_archive(a, k, u):
    path, = _kw(a, k, "file_path", defaults=("",))
    return {"file_path": path}


def _a_fit_view(a, k, u):
    return {}


def _a_set_view(a, k, u):
    v, = _kw(a, k, "view_name", defaults=("iso",))
    return {"view_name": v}


def _a_hide_object(a, k, u):
    o, = _kw(a, k, "object_name")
    return {"object_name": o}


def _a_show_object(a, k, u):
    o, = _kw(a, k, "object_name")
    return {"object_name": o}


def _a_show_all_objects(a, k, u):
    return {}


def _a_set_variable(a, k, u):
    name, value = _kw(a, k, "name", "value")
    return {"name": name, "value": str(value)}


def _a_get_variables(a, k, u):
    return {}


def _a_run_script(a, k, u):
    content = k.get("script") or k.get("script_content")
    if not content and a:
        content = a[0]
    if not content:
        raise _AdapterSkip("run_script 无脚本内容")
    return {"script_content": content, "save_before": bool(k.get("save_before", True))}


def _a_execute_console_command(a, k, u):
    cmd, = _kw(a, k, "command")
    return {"command": cmd}


MCP_ADAPTERS: dict = {
    "connect_to_maxwell": _a_connect_to_maxwell,
    "disconnect_from_maxwell": _a_disconnect_from_maxwell,
    "get_maxwell_status": _a_get_maxwell_status,
    "new_project": _a_new_project,
    "open_project": _a_open_project,
    "save_project": _a_save_project,
    "close_project": _a_close_project,
    "list_projects": _a_list_projects,
    "create_design": _a_create_design,
    "set_active_design": _a_set_active_design,
    "list_designs": _a_list_designs,
    "delete_design": _a_delete_design,
    "get_design_info": _a_get_design_info,
    "draw_box": _a_draw_box, "draw_cylinder": _a_draw_cylinder,
    "draw_rectangle": _a_draw_rectangle, "draw_circle": _a_draw_circle,
    "draw_line": _a_draw_line,
    "unite_objects": _a_unite_objects, "subtract_objects": _a_subtract_objects,
    "intersect_objects": _a_intersect_objects,
    "move_object": _a_move_object, "duplicate_object": _a_duplicate_object,
    "scale_object": _a_scale_object, "rename_object": _a_rename_object,
    "list_objects": _a_list_objects, "create_region": _a_create_region,
    "assign_material": _a_assign_material, "set_object_color": _a_set_object_color,
    "set_object_solve_inside": _a_set_object_solve_inside,
    "add_custom_material": _a_add_custom_material,
    "assign_vector_potential": _a_assign_vector_potential,
    "assign_balloon_boundary": _a_assign_balloon_boundary,
    "assign_master_slave_boundary": _a_assign_master_slave_boundary,
    "assign_current_excitation": _a_assign_current_excitation,
    "assign_voltage_excitation": _a_assign_voltage_excitation,
    "assign_winding": _a_assign_winding,
    "add_turns_to_winding": _a_add_turns_to_winding,
    "assign_force_parameter": _a_assign_force_parameter,
    "assign_torque_parameter": _a_assign_torque_parameter,
    "assign_motion_setup": _a_assign_motion_setup,
    "assign_mesh_operation": _a_assign_mesh_operation,
    "assign_skin_depth_mesh": _a_assign_skin_depth_mesh,
    "create_analysis_setup": _a_create_analysis_setup,
    "create_parametric_sweep": _a_create_parametric_sweep,
    "create_optimization": _a_create_optimization,
    "validate_design": _a_validate_design,
    "analyze": _a_analyze, "analyze_all": _a_analyze_all,
    "analyze_parametric_sweep": _a_analyze_parametric_sweep,
    "get_force": _a_get_force, "get_torque": _a_get_torque,
    "get_flux_linkage": _a_get_flux_linkage, "get_inductance": _a_get_inductance,
    "get_solution_info": _a_get_solution_info,
    "get_convergence_data": _a_get_convergence_data,
    "create_field_plot": _a_create_field_plot,
    "export_field_plot": _a_export_field_plot, "export_mesh": _a_export_mesh,
    "create_report": _a_create_report,
    "export_report_data": _a_export_report_data,
    "export_project_archive": _a_export_project_archive,
    "fit_view": _a_fit_view, "set_view": _a_set_view,
    "hide_object": _a_hide_object, "show_object": _a_show_object,
    "show_all_objects": _a_show_all_objects,
    "set_variable": _a_set_variable, "get_variables": _a_get_variables,
    "run_script": _a_run_script,
    "execute_console_command": _a_execute_console_command,
}


class MaxwellBridge:
    """
    唯一抽象层：项目脚本只调用本类方法，永不直接碰 MCP 名字或 COM API。

    后端策略（Strategy 模式）：
      - dry_run=True            : 返回 mock 值，验证脚本逻辑链路（CI/无 Maxwell）
      - dry_run=False, text     : 生成 IronPython 脚本文本，供外部打包执行
      - dry_run=False, mcp      : ★v4.3 新增★ 经 MCPConnector 真正调用
                                  D:\\mcp-maxwell\\server.py 的 71 个工具，
                                  实算结果回传；服务端/Maxwell 不可用时自动回退 text
    """

    def __init__(self, dry_run: bool = True, backend: str = "text",
                 mcp_server_path: Optional[str] = None,
                 auto_connect_mcp: bool = True):
        self.dry_run = dry_run
        self.backend = backend  # "text"=生成脚本 / "mcp"=经连接器实调
        self.mcp_server_path = mcp_server_path
        self._log: list[dict] = []
        self._vars: dict[str, str] = {}
        # MCP 连接器（lazy），仅 backend=="mcp" 且非 dry_run 时启用
        self._connector = None
        self._mcp_available: Optional[bool] = None  # None=未探测
        self._mcp_unit = "mm"  # 模型单位，由 set_model_units 维护
        if (not dry_run) and backend == "mcp" and auto_connect_mcp:
            self._init_connector()

    # ── MCP 连接器懒加载 ────────────────────────────────────
    def _init_connector(self) -> bool:
        """惰性创建并连接 MCP 连接器。成功返回 True，失败返回 False（不抛）。"""
        if self._connector is not None:
            return self._mcp_available is True
        try:
            from mcp_connector import MCPConnector  # 本目录模块
        except Exception as e:
            print(f"  [Bridge] 无法导入 mcp_connector: {e}，mcp 后端降级为 text")
            self._mcp_available = False
            self.backend = "text"
            return False
        try:
            self._connector = MCPConnector(server_path=self.mcp_server_path)
            self._connector.connect()
            self._mcp_available = True
            print(f"  [Bridge] MCP 后端已就绪: {self._connector.server_path}")
            return True
        except Exception as e:
            print(f"  [Bridge] MCP 连接失败，降级 text: {e}")
            self._connector = None
            self._mcp_available = False
            self.backend = "text"
            return False

    @property
    def mcp_connected(self) -> bool:
        """MCP 连接器是否可用（实算模式）。"""
        if self.dry_run or self.backend != "mcp":
            return False
        if self._mcp_available is None:
            self._init_connector()
        return bool(self._mcp_available and self._connector is not None
                    and self._connector.connected)

    def close(self):
        """关闭底层 MCP 连接器（若有）。进程退出时 atexit 也会调用。"""
        if self._connector is not None:
            try:
                self._connector.close()
            except Exception:
                pass

    # ── 日志记录 ──────────────────────────────────────────
    def _record(self, tool: str, args: tuple, kwargs: dict, result: Any):
        self._log.append({
            "tool": tool, "args": list(args), "kwargs": kwargs,
            "result": result if not isinstance(result, (dict, list)) else "mock",
        })

    @property
    def log(self) -> list[dict]:
        return self._log

    # ══════════════════════════════════════════════════════════════
    #  A. 命名漂移收敛（薄封装直接转发 MCP 真实工具）
    # ══════════════════════════════════════════════════════════════
    def subtract(self, blank_parts: str = "", tool_parts: str = "",
                 keep_originals: bool = False):
        """漂移收敛：subtract → subtract_objects（脚本统一用 blank_parts/tool_parts）"""
        return self.subtract_objects(blank_parts=blank_parts, tool_parts=tool_parts,
                                     keep_originals=keep_originals)

    def draw_region_pad(self, padding: float = 20.0):
        """漂移收敛：draw_region_pad → create_region"""
        return self.create_region(padding=padding)

    def analyze_setup(self, setup_name: str = "Setup1", design_name: str = ""):
        """漂移收敛：analyze_setup → analyze"""
        return self.analyze(setup_name=setup_name)

    # ══════════════════════════════════════════════════════════════
    #  B0. 代理 71 个真实 MCP 工具（薄封装，dry_run 返回 mock）
    #  ── 项目脚本只调用本桥方法，永不直接接触 MCP 命名 ──
    # ══════════════════════════════════════════════════════════════
    def _mock(self, tool: str, *a, **kw) -> str:
        if self.dry_run:
            self._record(tool, a, kw, "mock")
            return f"[DryRun] {tool}"
        # 实算：优先走 MCP 连接器真实调用；不可用则回退 text 脚本生成
        if self.mcp_connected:
            res = self._call_mcp(tool, a, kw)
            if res is not None:
                return res
        return self._inject_ironpython(f"# MCP:{tool}({a},{kw})")

    def _call_mcp(self, tool: str, args: tuple, kwargs: dict) -> Optional[str]:
        """把 bridge 调用经适配器映射为 server 工具参数并真实调用。

        返回:
          - str: 成功/失败的服务端响应文本（已记录日志）
          - None: 该工具未适配或不适合 MCP 路由，由调用方回退 text
        """
        adapter = MCP_ADAPTERS.get(tool)
        if adapter is None:
            return None  # 未适配 → 回退 text 生成脚本
        try:
            arguments = adapter(args, dict(kwargs), self._mcp_unit)
        except _AdapterSkip:
            return None  # 适配器主动放弃 → 回退 text
        if arguments is None:
            return None
        res = self._connector.call_tool(tool, arguments)
        ok = bool(res.get("ok"))
        text = res.get("text", "")
        self._record(tool, args, kwargs, text if ok else f"ERR:{text}")
        if not ok:
            # 服务端报错：打印但不中断，调用方可据 text 判断
            print(f"  [Bridge:MCP] {tool} 失败: {text[:200]}")
        return text

    # 连接/项目/设计（13个）
    def connect_to_maxwell(self, version: str = ""): return self._mock("connect_to_maxwell", version)
    def disconnect_from_maxwell(self): return self._mock("disconnect_from_maxwell")
    def get_maxwell_status(self): return self._mock("get_maxwell_status", result="[DryRun] connected")
    def new_project(self): return self._mock("new_project")
    def open_project(self, file_path: str): return self._mock("open_project", file_path)
    def save_project(self, file_path: str = ""): return self._mock("save_project", file_path)
    def close_project(self, name: str = ""): return self._mock("close_project", name)
    def list_projects(self): return self._mock("list_projects", result="[DryRun] []")
    def create_design(self, name: str, solution_type: str = "Transient"):
        return self._mock("create_design", name, solution_type)
    def set_active_design(self, design_name: str): return self._mock("set_active_design", design_name)
    def list_designs(self): return self._mock("list_designs", result="[DryRun] []")
    def delete_design(self, design_name: str): return self._mock("delete_design", design_name)
    def get_design_info(self):
        if self.dry_run:
            self._record("get_design_info", (), {}, {})
            return {"name": "Motor_Design", "type": "Transient", "units": "mm"}
        return self._mock("get_design_info")

    # 几何（17个）
    def draw_box(self, name: str, x=0, y=0, z=0, dx=10, dy=10, dz=10, material="vacuum"):
        return self._mock("draw_box", name, x, y, z, dx, dy, dz, material)
    def draw_cylinder(self, name: str, x=0, y=0, z=0, radius=10, height=10, material="vacuum"):
        return self._mock("draw_cylinder", name, x, y, z, radius, height, material)
    def draw_rectangle(self, name: str, x=0, y=0, z=0, width=10, height=10, material="vacuum"):
        return self._mock("draw_rectangle", name, x, y, z, width, height, material)
    def draw_circle(self, name: str, x=0, y=0, z=0, radius=10, material="vacuum"):
        return self._mock("draw_circle", name, x, y, z, radius, material)
    def draw_line(self, name: str, points: list = None): return self._mock("draw_line", name, points)
    def unite_objects(self, objects: list, keep_originals: bool = False):
        return self._mock("unite_objects", objects, keep_originals)
    def subtract_objects(self, blank_parts: str, tool_parts: str, keep_originals: bool = False):
        return self._mock("subtract_objects", blank_parts, tool_parts, keep_originals)
    def intersect_objects(self, objects: list, keep_originals: bool = False):
        return self._mock("intersect_objects", objects, keep_originals)
    def move_object(self, name: str, dx=0, dy=0, dz=0): return self._mock("move_object", name, dx, dy, dz)
    def duplicate_object(self, name: str, count: int = 2, dx=0, dy=0, dz=0):
        return self._mock("duplicate_object", name, count, dx, dy, dz)
    def scale_object(self, name: str, factor: float = 1.0): return self._mock("scale_object", name, factor)
    def rename_object(self, old_name: str, new_name: str): return self._mock("rename_object", old_name, new_name)
    def list_objects(self): return self._mock("list_objects", result="[DryRun] []")
    def create_region(self, padding: float = 20.0): return self._mock("create_region", padding)

    # 材料/属性（4个）
    def assign_material(self, object_name: str, material: str = "vacuum"):
        return self._mock("assign_material", object_name, material)
    def set_object_color(self, object_name: str, color: str = "(255 0 0)"):
        return self._mock("set_object_color", object_name, color)
    def set_object_solve_inside(self, object_name: str, solve_inside: bool = True):
        return self._mock("set_object_solve_inside", object_name, solve_inside)
    def add_custom_material(self, name: str, **props): return self._mock("add_custom_material", name, **props)

    # 边界/激励（13个）
    def assign_vector_potential(self, objects: list = None, value: str = "0"):
        return self._mock("assign_vector_potential", objects, value)
    def assign_balloon_boundary(self, objects: list = None): return self._mock("assign_balloon_boundary", objects)
    def assign_master_slave_boundary(self, master: str, slave: str):
        return self._mock("assign_master_slave_boundary", master, slave)
    def assign_current_excitation(self, objects: list, current: str = "1A"):
        return self._mock("assign_current_excitation", objects, current)
    def assign_voltage_excitation(self, objects: list, voltage: str = "0V"):
        return self._mock("assign_voltage_excitation", objects, voltage)
    def assign_winding(self, name: str, winding_type: str = "Current",
                      current: str = "0A", resistance: str = "0ohm",
                      inductance: str = "0H", voltage: str = "0V",
                      parallel_branches: int = 1):
        return self._mock("assign_winding", name, winding_type, current, resistance)
    def add_turns_to_winding(self, winding_name: str, turns: int):
        return self._mock("add_turns_to_winding", winding_name, turns)
    def assign_force_parameter(self, objects: list): return self._mock("assign_force_parameter", objects)
    def assign_torque_parameter(self, objects: list): return self._mock("assign_torque_parameter", objects)
    def assign_motion_setup(self, name: str = "Band", motion_type: str = "Rotate",
                           axis: str = "Z", angular_velocity: str = "0rpm",
                           is_positive: bool = True):
        return self._mock("assign_motion_setup", name, motion_type, axis, angular_velocity)

    # 网格（2个）
    def assign_mesh_operation(self, objects: list, max_length: str = "1mm"):
        return self._mock("assign_mesh_operation", objects, max_length)
    def assign_skin_depth_mesh(self, objects: list, skin_depth: str = "1mm"):
        return self._mock("assign_skin_depth_mesh", objects, skin_depth)

    # 求解（7个）
    def create_analysis_setup(self, setup_name: str = "Setup1", solver_type: str = "Transient",
                              stop_time: str = "", time_step: str = "", max_passes: int = 20):
        return self._mock("create_analysis_setup", setup_name, solver_type, stop_time, time_step)
    def create_parametric_sweep(self, sweep_name: str = "Sweep1"):
        return self._mock("create_parametric_sweep", sweep_name)
    def create_optimization(self, name: str = "Opt1"): return self._mock("create_optimization", name)
    def validate_design(self): return self._mock("validate_design", result="[DryRun] valid")
    def analyze(self, setup_name: str = "Setup1"): return self._mock("analyze", setup_name)
    def analyze_all(self): return self._mock("analyze_all")
    def analyze_parametric_sweep(self, sweep_name: str = "Sweep1"):
        return self._mock("analyze_parametric_sweep", sweep_name)

    # 后处理（13个）
    def get_force(self, objects: list = None):
        if self.dry_run:
            self._record("get_force", (objects,), {}, {})
            return {"value": 0.0, "unit": "N"}
        return self._mock("get_force", objects)
    def get_torque(self, objects: list = None, setup_name: str = ""):
        if self.dry_run:
            self._record("get_torque", (objects, setup_name), {}, {})
            return {"value": 1.59, "unit": "N·m"}
        return self._mock("get_torque", objects)
    def get_flux_linkage(self, winding: str = "WindingA"):
        if self.dry_run:
            self._record("get_flux_linkage", (winding,), {}, {})
            return {"value": 0.001, "unit": "Wb"}
        return self._mock("get_flux_linkage", winding)
    def get_inductance(self, winding: str = "WindingA"):
        if self.dry_run:
            self._record("get_inductance", (winding,), {}, {})
            return {"value": 0.0038, "unit": "H"}
        return self._mock("get_inductance", winding)
    def get_solution_info(self, setup_name: str = "Setup1"):
        return self._mock("get_solution_info", setup_name, result="[DryRun] ready")
    def get_convergence_data(self, setup_name: str = "Setup1"):
        return self._mock("get_convergence_data", setup_name)
    def create_field_plot(self, quantity: str = "Mag_B", objects: list = None):
        return self._mock("create_field_plot", quantity, objects)
    def export_field_plot(self, plot_name: str, file_path: str = ""):
        return self._mock("export_field_plot", plot_name, file_path)
    def export_mesh(self, file_path: str = ""): return self._mock("export_mesh", file_path)
    def create_report(self, name: str = "Report1", report_type: str = "Data Table",
                      report_name: str = "", x_quantity: str = "",
                      y_quantities: list = None, display_type: str = ""):
        name = report_name or name
        return self._mock("create_report", name, report_type, x_quantity,
                          y_quantities, display_type)
    def export_report_data(self, report_name: str, file_path: str = ""):
        return self._mock("export_report_data", report_name, file_path)
    def export_project_archive(self, file_path: str = ""):
        return self._mock("export_project_archive", file_path)

    # 视图（5个）
    def fit_view(self): return self._mock("fit_view")
    def set_view(self, view_name: str = "iso"): return self._mock("set_view", view_name)
    def hide_object(self, object_name: str): return self._mock("hide_object", object_name)
    def show_object(self, object_name: str): return self._mock("show_object", object_name)
    def show_all_objects(self): return self._mock("show_all_objects")

    # 变量（2个）
    def set_variable(self, name: str, value: str):
        self._vars[name] = value
        return self._mock("set_variable", name, value)
    def get_variables(self):
        if self.dry_run:
            self._record("get_variables", (), {}, {})
            return dict(self._vars)
        return self._mock("get_variables")

    # 通用（3个）
    def run_script(self, script_content: str = "", save_before: bool = True,
                   script: str = ""):
        content = script or script_content
        return self._inject_ironpython(content)
    def execute_console_command(self, command: str):
        return self._mock("execute_console_command", command)
    def get_status_resource(self):
        if self.dry_run:
            self._record("get_status_resource", (), {}, {})
            return {"connected": False}
        return self._mock("get_status_resource")


    # ══════════════════════════════════════════════════════════════
    #  B. 真·缺口补齐（dry_run 返回 mock / 实算经 run_script 注入 IronPython）
    # ══════════════════════════════════════════════════════════════

    def set_model_units(self, unit: str = "mm"):
        """缺口：server 无此工具。用 run_script 注入 oEditor.SetModelUnits 兜底。"""
        self._mcp_unit = unit or "mm"  # 供 MCP 适配器做数值→带单位字符串转换
        if self.dry_run:
            self._record("set_model_units", (unit,), {}, "mock")
            return "[DryRun] units=mm"
        return self._inject_ironpython(
            f'oEditor.SetModelUnits(["NAME:UnitsSettings","Length:=", "{unit}"])')

    def duplicate_around_axis(self, name: str, angle_deg: float, num_clones: int):
        """缺口：server 只有 duplicate_object（线性阵列）。绕轴阵列用 InjectScript 兜底。"""
        if self.dry_run:
            self._record("duplicate_around_axis", (name, angle_deg, num_clones), {}, "mock")
            return f"[DryRun] duplicated {name} x{num_clones} @ {angle_deg}deg"
        script = (
            f'oEditor.DuplicateAroundAxis('
            f'["NAME:Selections","Selections:=","{name}","NewPartsModelFlag:=","Model"],'
            f'["NAME:DuplicateAroundAxisParameters","CreateNewObjects:=",True,'
            f'"WhichAxis:=","Z","AngleStr:=","{angle_deg}deg","Numclones:=","{num_clones}"])'
        )
        return self._inject_ironpython(script)

    def set_magnet_orientation(self, pm_name: str, direction: str = "radial"):
        """缺口：server 无。用 run_script 改 magnetic_coercivity DirComp1（+1/-1）。"""
        if self.dry_run:
            self._record("set_magnet_orientation", (pm_name, direction), {}, "mock")
            return f"[DryRun] {pm_name} orient={direction}"
        comp = "1" if direction in ("radial", "outward", "+") else "-1"
        script = (
            f'oDefinitionManager.EditMaterial("{pm_name}", '
            f'["NAME:{pm_name}", '
            f'["NAME:magnetic_coercivity","DirComp1:=","{comp}"]])'
        )
        return self._inject_ironpython(script)

    def add_transient_setup(self, stop_time: str = "0.02s", time_step: str = "5e-5s",
                            setup_name: str = "Setup1"):
        """缺口：server 只有泛化 create_analysis_setup。transient 预置套餐在此。"""
        if self.dry_run:
            self._record("add_transient_setup", (stop_time, time_step), {}, "mock")
            return "[DryRun] transient setup"
        return self.create_analysis_setup(setup_name=setup_name, solver_type="Transient",
                                          stop_time=stop_time, time_step=time_step)

    def add_magnetostatic_setup(self, max_passes: int = 20, setup_name: str = "Setup1"):
        """缺口：magnetostatic 预置套餐。"""
        if self.dry_run:
            self._record("add_magnetostatic_setup", (max_passes,), {}, "mock")
            return "[DryRun] magnetostatic setup"
        return self.create_analysis_setup(setup_name=setup_name, solver_type="Magnetostatic",
                                          max_passes=max_passes)

    def assign_band(self, name: str = "Band", angular_velocity: str = "0rpm",
                    axis: str = "Z", is_positive: bool = True):
        """缺口：assign_motion_setup 是通用入口，band 旋转套餐在此。"""
        if self.dry_run:
            self._record("assign_band", (name, angular_velocity), {}, "mock")
            return f"[DryRun] band={name} omega={angular_velocity}"
        return self.assign_motion_setup(name=name, motion_type="Rotate",
                                        axis=axis, angular_velocity=angular_velocity,
                                        is_positive=is_positive)

    def assign_mesh_skin_depth(self, objects: list[str], skin_depth: str = "1mm"):
        """漂移收敛：assign_mesh_skin_depth → assign_skin_depth_mesh"""
        return self.assign_skin_depth_mesh(objects=objects, skin_depth=skin_depth)

    def create_winding_setup(self, name: str, winding_type: str = "Current",
                             current: str = "0A", resistance: str = "0ohm"):
        """缺口：server 有 assign_winding（外激励三相），无单绕组配置套餐。"""
        if self.dry_run:
            self._record("create_winding_setup", (name,), {}, "mock")
            return f"[DryRun] winding={name}"
        return self.assign_winding(name=name, winding_type=winding_type,
                                   current=current, resistance=resistance)

    def create_winding_group(self, name: str, coils: list[str],
                             conductor_number: int = 50, polarity: str = "Positive"):
        """缺口：教程的 AssignWindingGroup，server 无。用 run_script 兜底。"""
        if self.dry_run:
            self._record("create_winding_group", (name, coils), {}, "mock")
            return f"[DryRun] winding_group={name} coils={len(coils)}"
        coil_list = ",".join(f'"{c}"' for c in coils)
        script = (
            f'oModule.AssignWindingGroup('
            f'["NAME:{name}","Type:=","Current","Current:=","0A",'
            f'"Resistance:=","0ohm","Voltage:=","0V","ParallelBranchesNum:=","1"])'
        )
        return self._inject_ironpython(script)

    def add_winding_coils(self, winding_name: str, coil_names: list[str]):
        """缺口：教程的 AddWindingCoils，server 无。"""
        if self.dry_run:
            self._record("add_winding_coils", (winding_name, coil_names), {}, "mock")
            return f"[DryRun] {winding_name}+{len(coil_names)} coils"
        coil_list = ",".join(f'"{c}"' for c in coil_names)
        script = f'oModule.AddWindingCoils("{winding_name}", [{coil_list}])'
        return self._inject_ironpython(script)

    def assign_coil_group(self, name: str, objects: list[str],
                         conductor_number: int = 50, polarity: str = "Positive"):
        """缺口：教程的 AssignCoilGroup，server 无。用 run_script 兜底。"""
        if self.dry_run:
            self._record("assign_coil_group", (name, objects), {}, "mock")
            return f"[DryRun] coil_group={name} objs={len(objects)}"
        obj_list = ",".join(f'"{o}"' for o in objects)
        script = (
            f'oModule.AssignCoilGroup(["NAME:{name}",'
            f'"Objects:=", [{obj_list}],'
            f'"Conductor number:=", "{conductor_number}",'
            f'"PolarityType:=", "{polarity}"])'
        )
        return self._inject_ironpython(script)

    def export_data(self, design_name: str = "", export_path: str = "",
                    file_path: str = "", expressions: list = None,
                    setup_name: str = "Setup1"):
        """缺口：server 的 export_report_data 偏图表；原始时序数据导出套餐在此。"""
        path = file_path or export_path
        if self.dry_run:
            self._record("export_data", (design_name, path, expressions, setup_name), {}, "mock")
            return "[DryRun] export OK"
        if not path:
            path = os.path.join(tempfile.gettempdir(), "export_data.csv")
        return self._inject_ironpython(
            f'oDesign.ExportDesignData("{path}", "{design_name}")')

    def get_field_data(self, quantity: str = "Mag_B", objects: list[str] = None,
                       setup_name: str = "Setup1"):
        """缺口：server 有 create_field_plot（图形），无数据提取。run_script 兜底。"""
        if self.dry_run:
            self._record("get_field_data", (quantity, objects), {}, {})
            # 返回工程估算值，保证脚本链路连通
            return {"quantity": quantity, "value": 1.2, "unit": "T"}
        obj_list = ",".join(objects or [])
        script = (
            f'data = oDesign.GetChildNamedObject("FieldsReporter").'
            f'GetNamedExpression("{quantity}","{setup_name}")'
        )
        return self._inject_ironpython(script)

    def get_induced_voltage(self, winding_name: str = "WindingA", setup_name: str = ""):
        """缺口：server 有 get_flux_linkage，无 induced voltage。包一层。"""
        if self.dry_run:
            self._record("get_induced_voltage", (winding_name, setup_name), {}, {})
            return {"winding": winding_name, "V_rms": 0.0, "V_peak": 0.0}
        return self._inject_ironpython(
            f'V = oModule.GetWindingVoltage("{winding_name}")')

    def get_loss_data(self, setup_name: str = "Setup1"):
        """缺口：server 无 loss 数据提取。
        DryRun 返回集总估算（与 mdao_orchestrator 一致：copper/iron/eddy）。
        """
        if self.dry_run:
            self._record("get_loss_data", (setup_name,), {}, {})
            return {"copper_loss_W": 25.0, "iron_loss_W": 15.0, "pm_eddy_loss_W": 5.0,
                    "total_loss_W": 45.0, "efficiency": 0.91}
        return self._inject_ironpython(
            f'loss = oDesign.GetLossData("{setup_name}")')

    # ────────────────────────────────────────────────────────────────
    #  D. 扩展分析套餐（Phase 4 增量，对应 08~11 脚本）
    #      dry_run 返回 mock；实算委托到已有工具或 run_script 注入 IronPython
    # ────────────────────────────────────────────────────────────────

    def setup_mtpa_sweep(self, setup_name: str = "MTPA_Sweep",
                         variable: str = "$CurrentAngle",
                         start: float = 0, stop: float = 90, step: float = 5,
                         stop_time: str = "0.02s", time_step: str = "5e-5s"):
        """MTPA 电流角扫描：参数化扫描 + 瞬态求解。"""
        if self.dry_run:
            self._record("setup_mtpa_sweep",
                         (setup_name, variable, start, stop, step), {}, "mock")
            return f"[DryRun] MTPA sweep {variable} {start}->{stop} step {step}"
        self.create_parametric_sweep(sweep_name=setup_name)
        self.create_analysis_setup(setup_name=setup_name, solver_type="Transient",
                                  stop_time=stop_time, time_step=time_step)
        return self._inject_ironpython(
            f'oDesign.ChangeProperty(["NAME:AllTabs",'
            f'["NAME:LocalVariableTab",'
            f'["NAME:PropServers","{variable}"],'
            f'["NAME:ChangedProps",["NAME:{variable}","Value:=","{start}deg"],'
            f'["NAME:{variable}","Min:=","{start}deg"],'
            f'["NAME:{variable}","Max:=","{stop}deg"],'
            f'["NAME:{variable}","Step:=","{step}deg"]]]])')

    def add_thermal_setup(self, setup_name: str = "ThermalTransient",
                          stop_time: float = 100.0, time_step: float = 0.5,
                          loss_source: str = "RatedLoad"):
        """瞬态热分析：耦合电磁损耗。"""
        if self.dry_run:
            self._record("add_thermal_setup",
                         (setup_name, stop_time, time_step, loss_source), {}, "mock")
            return f"[DryRun] thermal {setup_name} {stop_time}s"
        self.create_analysis_setup(setup_name=setup_name, solver_type="Transient",
                                  stop_time=f"{stop_time}s", time_step=f"{time_step}s")
        return self._inject_ironpython(
            f'oModule = oDesign.GetModule("ThermalLoss")\n'
            f'oModule.AssignThermalSetup("{setup_name}", "{loss_source}")')

    def get_temperature_data(self, setup_name: str = "ThermalTransient"):
        """提取温度场数据。"""
        if self.dry_run:
            self._record("get_temperature_data", (setup_name,), {}, {})
            return {"winding_temp_C": 85.0, "magnet_temp_C": 78.0,
                    "stator_temp_C": 82.0}
        return self._inject_ironpython(
            f'data = oDesign.GetModule("Thermal").GetTemperatureData("{setup_name}")')

    def setup_structural_analysis(self, setup_name: str = "Structural_Peak",
                                  load_source: str = "Overload_3x",
                                  mesher: str = "Mechanical"):
        """结构强度 FEA 设置。"""
        if self.dry_run:
            self._record("setup_structural_analysis",
                         (setup_name, load_source, mesher), {}, "mock")
            return f"[DryRun] structural {setup_name} load={load_source}"
        self.create_analysis_setup(setup_name=setup_name, solver_type="Transient")
        return self._inject_ironpython(
            f'oModule = oDesign.GetModule("Mechanical")\n'
            f'oModule.AssignStructuralSetup("{setup_name}", "{load_source}")')

    def setup_nvh_scan(self, setup_name: str = "NVH_Sweep",
                       speed_var: str = "$Speed",
                       speed_rpm_min: int = 500, speed_rpm_max: int = 6000,
                       speed_step_rpm: int = 500,
                       stop_time: str = "0.02s", time_step: str = "5e-5s"):
        """NVH 转速扫描：参数化速度变量 + 瞬态求解。"""
        if self.dry_run:
            self._record("setup_nvh_scan",
                         (setup_name, speed_rpm_min, speed_rpm_max,
                          speed_step_rpm), {}, "mock")
            return f"[DryRun] NVH {setup_name} {speed_rpm_min}-{speed_rpm_max}rpm"
        self.create_parametric_sweep(sweep_name=setup_name)
        self.create_analysis_setup(setup_name=setup_name, solver_type="Transient",
                                  stop_time=stop_time, time_step=time_step)
        return self._inject_ironpython(
            f'oDesign.ChangeProperty(["NAME:AllTabs",'
            f'["NAME:LocalVariableTab",'
            f'["NAME:PropServers","{speed_var}"],'
            f'["NAME:ChangedProps",["NAME:{speed_var}","Min:=","{speed_rpm_min}rpm"],'
            f'["NAME:{speed_var}","Max:=","{speed_rpm_max}rpm"],'
            f'["NAME:{speed_var}","Step:=","{speed_step_rpm}rpm"]]]])')

    # ══════════════════════════════════════════════════════════════
    #  C. 通用实算后端 / 兜底注入
    # ══════════════════════════════════════════════════════════════
    def _inject_ironpython(self, script_body: str) -> str:
        """
        实算兜底：把一段 IronPython 脚本交给 server 的 run_script 工具执行。

        - backend=="mcp" 且连接器可用：真正调 run_script 执行，返回服务端响应
        - 否则（text / dry_run / MCP 不可用）：返回脚本文本，供离线打包执行
        """
        snippet = script_body[:80] + ("..." if len(script_body) > 80 else "")
        if self.mcp_connected:
            res = self._connector.run_script(script_body)
            text = res.get("text", "")
            ok = bool(res.get("ok"))
            self._record("run_script", (snippet,), {}, text if ok else f"ERR:{text}")
            if not ok:
                print(f"  [Bridge:MCP] run_script 失败: {text[:200]}")
            return text or script_body
        # text / dry_run：保持纯文本输出，兼容离线生成脚本场景
        self._record("run_script", (snippet,), {}, "script")
        return script_body

    def get_log(self) -> list[dict]:
        return self._log

    def save_log(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._log, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
#  模块级便捷缓存：复用单例 bridge，避免重复实例化
# ══════════════════════════════════════════════════════════════
_default: Optional[MaxwellBridge] = None


def get_bridge(dry_run: bool = True, backend: str = "text") -> MaxwellBridge:
    global _default
    if _default is None:
        _default = MaxwellBridge(dry_run=dry_run, backend=backend)
    return _default


# ══════════════════════════════════════════════════════════════
#  自检
# ══════════════════════════════════════════════════════════════
def _self_test():
    """模块自检：所有缺口 + 漂移收敛在 dry_run 下应零异常。"""
    bridge = MaxwellBridge(dry_run=True)

    # 漂移收敛
    bridge.subtract("Stator", "Slot_1")
    bridge.draw_region_pad(20)
    bridge.analyze_setup()

    # 缺口修复
    bridge.set_model_units("mm")
    bridge.duplicate_around_axis("Slot_1", 10.0, 36)
    bridge.set_magnet_orientation("NdFe35_N", "radial")
    bridge.add_transient_setup("0.02s", "5e-5s")
    bridge.add_magnetostatic_setup(max_passes=15)
    bridge.assign_band("Band", "2000rpm")
    bridge.assign_mesh_skin_depth(["Band"], "1mm")
    bridge.create_winding_setup("WindingA", "Current", "0A", "0.1ohm")
    bridge.export_data("Motor_Design", "/tmp/x.csv")
    fld = bridge.get_field_data("Mag_B")
    iv = bridge.get_induced_voltage("WindingA")
    ld = bridge.get_loss_data()

    # 教程绕组接缝
    bridge.assign_coil_group("A+", ["A_1", "A_2", "A_3"],
                              conductor_number=50, polarity="Positive")
    bridge.add_winding_coils("WindingA", ["A+_1", "A+_2"])

    # 断言
    assert len(bridge.log) >= 14, f"措施数={len(bridge.log)}"
    assert fld["value"] is not None
    assert iv["V_rms"] == 0.0
    assert ld["copper_loss_W"] > 0
    print(f"[OK] {len(bridge.log)} 项 dry_run 验证通过")
    bridge.save_log(os.path.join(tempfile.gettempdir(), "maxwell_bridge_log.json"))
    return bridge


if __name__ == "__main__":
    _self_test()
