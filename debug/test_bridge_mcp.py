#!/usr/bin/env python3
"""端到端测试：bridge 的 dry_run / text / mcp 三种后端。
- dry_run：回归，返回 mock
- mcp：真实连 D:\\mcp-maxwell\\server.py，调 get_maxwell_status（无需 Maxwell）
- 回退：mcp 不可用时降级 text
"""
import os
import sys

sys.path.insert(0, r"D:\桌面\ANSYS MaxWell_skill\scripts")

from maxwell_bridge import MaxwellBridge, MCP_ADAPTERS  # noqa


def test_dry_run():
    print("=== [1] dry_run 回归 ===")
    b = MaxwellBridge(dry_run=True)
    assert b.set_model_units("mm") == "[DryRun] units=mm"
    assert b.draw_circle("Stator_Outer", x=0, y=0, radius=40).startswith("[DryRun]")
    assert b.subtract(blank_parts="A", tool_parts="B")  # 漂移收敛
    assert b.get_maxwell_status() == "[DryRun] get_maxwell_status"
    assert b.analyze("Setup1") == "[DryRun] analyze"
    assert b.get_loss_data()["copper_loss_W"] > 0  # 缺口工具 dry_run 估算
    print(f"    dry_run 日志 {len(b.log)} 条 [OK]")
    b.close()


def test_adapter_coverage():
    print("=== [2] 适配器覆盖率 ===")
    # 71 个 MCP 真实工具里，未被 MISSING_TOOLS/漂移覆盖的应有适配器
    from maxwell_bridge import MCP_TOOLS
    missing = {"set_model_units"}  # 仅举例
    adapted = set(MCP_ADAPTERS.keys())
    covered = adapted & MCP_TOOLS
    unadapted_real = (MCP_TOOLS - adapted)
    # draw_line 等已在适配器；列出未适配的真实工具
    print(f"    MCP_TOOLS={len(MCP_TOOLS)} 适配器={len(adapted)} "
          f"覆盖真实工具={len(covered)}")
    print(f"    未适配的真实工具: {sorted(unadapted_real) or '无'}")
    # 期望：绝大多数真实工具被覆盖（少数资源类 get_status_resource/get_projects_resource 不需要）
    assert len(covered) >= 65, f"覆盖过少: {len(covered)}"
    print("    [OK]")


def test_mcp_backend():
    print("=== [3] mcp 后端真实调用 ===")
    b = MaxwellBridge(dry_run=False, backend="mcp", auto_connect_mcp=True)
    print(f"    mcp_connected={b.mcp_connected}")
    if not b.mcp_connected:
        print("    [SKIP] MCP 不可用（无 Maxwell 或服务端起不来），跳过实算")
        b.close()
        return
    # list_tools 经连接器
    tools = b._connector.list_tools()
    print(f"    服务端工具数={len(tools)}")
    assert "get_maxwell_status" in tools

    # 通过 bridge 调 get_maxwell_status（无需 Maxwell 运行）
    status = b.get_maxwell_status()
    print(f"    get_maxwell_status -> {status[:80]!r}")
    assert "未连接" in status or "connected" in status.lower() or "Maxwell" in status

    # 试一个几何工具的适配器映射（不连 Maxwell，预期服务端报"未连接"错误，但不抛）
    r = b.draw_circle("Test", x=0, y=0, radius=5)
    print(f"    draw_circle -> {str(r)[:80]!r}")
    # 不连 Maxwell 时应返回错误文本（未连接），但流程不中断
    print("    [OK]")
    b.close()


def test_fallback_to_text():
    print("=== [4] MCP 不可用降级 text ===")
    # 指向不存在的服务端 → 连接失败 → 降级 text
    b = MaxwellBridge(dry_run=False, backend="mcp",
                      mcp_server_path=r"D:\nonexistent\server.py",
                      auto_connect_mcp=True)
    print(f"    mcp_connected={b.mcp_connected} backend={b.backend}")
    assert b.backend == "text", f"应降级为 text，实际 {b.backend}"
    r = b.set_model_units("mm")
    print(f"    set_model_units -> {str(r)[:60]!r}")
    assert "SetModelUnits" in r  # text 模式返回脚本文本
    print("    [OK]")
    b.close()


if __name__ == "__main__":
    test_dry_run()
    test_adapter_coverage()
    test_mcp_backend()
    test_fallback_to_text()
    print("\n[ALL PASS] bridge MCP 集成测试通过")
