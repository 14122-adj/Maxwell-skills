#!/usr/bin/env python3
"""Introspect D:\\mcp-maxwell\\server.py to dump exact tool signatures.

Imports the server module (safe: mcp.run() is guarded by __main__) and prints
each tool's name + JSON-schema parameters so we can build correct adapters.
"""
import importlib.util
import json
import sys

SERVER_PATH = r"D:\mcp-maxwell\server.py"


def load_server():
    spec = importlib.util.spec_from_file_location("maxwell_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_tools(mod):
    mcp = mod.mcp
    # FastMCP stores tools in _tool_manager._tools (dict: name -> Tool)
    tm = getattr(mcp, "_tool_manager", None)
    if tm is not None and hasattr(tm, "_tools"):
        return tm._tools
    # fallback: newer versions may expose differently
    if hasattr(mcp, "_tools"):
        return mcp._tools
    raise RuntimeError("无法定位 FastMCP 工具表")


def main():
    mod = load_server()
    tools = get_tools(mod)
    out = []
    for name in sorted(tools.keys()):
        tool = tools[name]
        schema = None
        for attr in ("parameters", "inputSchema", "input_schema"):
            v = getattr(tool, attr, None)
            if v is not None:
                schema = v
                break
        if schema is None:
            # try building from the function
            try:
                schema = tool.fn.__doc__ or {}
            except Exception:
                schema = {}
        props = {}
        required = []
        if isinstance(schema, dict):
            props = schema.get("properties", {}) or {}
            required = schema.get("required", []) or []
        params = []
        for pname, pinfo in props.items():
            ptype = (pinfo or {}).get("type", "?")
            default = (pinfo or {}).get("default", "<no-default>")
            req = "REQ" if pname in required else "opt"
            params.append(f"{pname}:{ptype}={default!r}[{req}]")
        out.append({"name": name, "params": params})
    for entry in out:
        print(entry["name"])
        for p in entry["params"]:
            print("   ", p)
    print(f"\nTOTAL: {len(out)} tools")
    # dump JSON for programmatic use
    with open(r"D:\桌面\ANSYS MaxWell_skill\debug\server_tools.json", "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
