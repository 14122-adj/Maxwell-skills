#!/usr/bin/env python3
"""
MCP 连接器实调效果测试（模拟 Maxwell 连接状态）
================================================
用 mock_maxwell_server.py 作为服务端（注入假 win32com，让 connect_to_maxwell 成功），
跑一条贴近真实电机的完整工作流，验证 connector → server → COM → 响应 全链路：
  connect → new_project → create_design → draw_circle×2 → subtract →
  assign_material → set_variable → create_analysis_setup → analyze →
  get_maxwell_status → list_objects → get_variables → get_force

再切到 bridge(backend="mcp") 跑一遍，验证适配器层。
"""
import json
import os
import sys

sys.path.insert(0, r"D:\桌面\ANSYS MaxWell_skill\scripts")
from mcp_connector import MCPConnector  # noqa: E402

MOCK_SERVER = r"D:\桌面\ANSYS MaxWell_skill\debug\mock_maxwell_server.py"


def _ok(res: dict) -> bool:
    return bool(res.get("ok")) and not res.get("is_error")


def _text(res: dict) -> str:
    return (res.get("text") or "").strip()


def show(step: str, res: dict, expect_ok: bool = True):
    flag = "✓" if _ok(res) == expect_ok else "✗"
    txt = _text(res).replace("\n", " ")[:90]
    print(f"  [{flag}] {step:28s} → {txt}")
    assert _ok(res) == expect_ok, f"{step} 期望 ok={expect_ok} 实际 ok={_ok(res)}: {txt}"


def test_connector_workflow():
    print("=== [A] connector 直调工作流（模拟 Maxwell 已连接）===")
    conn = MCPConnector(server_path=MOCK_SERVER)
    summary = conn.connect()
    print(f"  {summary}")
    tools = conn.list_tools()
    print(f"  服务端工具数: {len(tools)}")
    assert len(tools) == 71

    # 1) 连接（mock 让其成功）
    show("connect_to_maxwell", conn.call_tool("connect_to_maxwell", {"version": "2024.2"}))

    # 2) 新建项目 + 设计
    show("new_project", conn.call_tool("new_project", {}))
    show("create_design", conn.call_tool("create_design", {
        "design_type": "Maxwell 2D", "design_name": "Motor", "solution_type": "Transient"}))

    # 3) 几何：两个圆 + 布尔减（定子环）
    show("draw_circle Stator_Outer", conn.call_tool("draw_circle", {
        "x": "0mm", "y": "0mm", "z": "0mm", "radius": "40mm", "axis": "Z", "name": "Stator_Outer"}))
    show("draw_circle Stator_Inner", conn.call_tool("draw_circle", {
        "x": "0mm", "y": "0mm", "z": "0mm", "radius": "30mm", "axis": "Z", "name": "Stator_Inner"}))
    show("subtract_objects", conn.call_tool("subtract_objects", {
        "blank_objects": ["Stator_Outer"], "tool_objects": ["Stator_Inner"], "keep_originals": False}))

    # 4) 材料 + 变量
    show("assign_material", conn.call_tool("assign_material", {
        "object_name": "Stator_Outer", "material": "M235_35A"}))
    show("set_variable", conn.call_tool("set_variable", {"name": "RotorAngle", "value": "0deg"}))

    # 5) 求解设置 + 求解
    show("create_analysis_setup", conn.call_tool("create_analysis_setup", {
        "setup_name": "Setup1", "solution_type": "Magnetostatic", "max_passes": 15}))
    show("analyze", conn.call_tool("analyze", {"setup_name": "Setup1"}))

    # 6) 状态与结果回读（验证状态往返）
    res_status = conn.call_tool("get_maxwell_status", {})
    show("get_maxwell_status", res_status)
    status = json.loads(_text(res_status))
    assert status["connected"] is True, f"应已连接: {status}"
    print(f"        ↳ connected={status['connected']} "
          f"project={status.get('active_project')} design={status.get('active_design')}")

    res_objs = conn.call_tool("list_objects", {})
    show("list_objects", res_objs)
    objs = json.loads(_text(res_objs))
    print(f"        ↳ sheets={objs['sheets']} solids={objs['solids']} lines={objs['lines']}")
    assert "Stator_Outer" in objs["sheets"] and "Stator_Inner" in objs["sheets"], \
        f"几何对象未回读: {objs}"

    res_vars = conn.call_tool("get_variables", {})
    show("get_variables", res_vars)
    vars_ = json.loads(_text(res_vars))
    print(f"        ↳ variables={vars_}")
    assert vars_.get("RotorAngle") == "0deg", f"变量未回读: {vars_}"

    res_force = conn.call_tool("get_force", {"force_name": "Force1", "setup_name": "Setup1"})
    show("get_force", res_force)
    force = json.loads(_text(res_force))
    print(f"        ↳ force={force}")
    assert "fx" in force, f"力数据未返回: {force}"

    # 7) run_script（缺口工具走这条路径）
    show("run_script", conn.call_tool("run_script", {
        "script_content": 'oEditor.SetModelUnits(["NAME:UnitsSettings","Length:=","mm"])',
        "save_before": False}))

    conn.close()
    print("  [A] connector 工作流通过\n")


def test_bridge_mcp_backend():
    print("=== [B] bridge(backend='mcp') 经适配器工作流 ===")
    from maxwell_bridge import MaxwellBridge
    b = MaxwellBridge(dry_run=False, backend="mcp", mcp_server_path=MOCK_SERVER,
                      auto_connect_mcp=True)
    assert b.mcp_connected, "bridge 应已连上 mock 服务端"
    print(f"  mcp_connected={b.mcp_connected}")

    # bridge 先调 connect（适配器把 version 映射）
    r = b.connect_to_maxwell(version="2024.2")
    print(f"  [-] connect_to_maxwell → {str(r)[:70]!r}")
    assert "已连接" in r, f"连接应成功: {r}"

    b.new_project()
    b.create_design("Motor2D", solution_type="Transient")

    # 适配器：bridge 的 (name, x, y, z, radius) 数值 → server 的 "40mm" 串
    b.draw_circle("Rotor_Outer", x=0, y=0, radius=25)
    b.draw_circle("Shaft", x=0, y=0, radius=10)
    b.subtract(blank_parts="Rotor_Outer", tool_parts="Shaft")  # 漂移收敛名

    b.assign_material("Rotor_Outer", "M235_35A")
    b.set_variable("Speed", "3000rpm")
    b.create_analysis_setup(setup_name="Setup1", solver_type="Magnetostatic", max_passes=10)
    b.analyze("Setup1")

    # 状态回读
    status = b.get_maxwell_status()
    print(f"  [-] get_maxwell_status → {status[:80]!r}")
    assert "connected" in status or "已连接" in status

    objs = b.list_objects()
    print(f"  [-] list_objects → {str(objs)[:80]!r}")
    assert "Rotor_Outer" in str(objs), f"适配器创建的几何未回读: {objs}"

    print(f"  [-] bridge 日志 {len(b.log)} 条")
    print("  [B] bridge mcp 后端通过\n")
    b.close()


if __name__ == "__main__":
    test_connector_workflow()
    test_bridge_mcp_backend()
    print("[ALL PASS] 模拟 Maxwell 连接状态下的 MCP 连接器实调测试通过")
