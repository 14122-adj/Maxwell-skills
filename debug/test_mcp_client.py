#!/usr/bin/env python3
"""End-to-end MCP client test against D:\\mcp-maxwell\\server.py (Windows-safe)."""
import asyncio
import os
import sys

# Windows: use ProactorEventLoop for subprocess stdio support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = r"D:\mcp-maxwell\server.py"
LOG_PATH = r"D:\桌面\ANSYS MaxWell_skill\debug\mcp_client_test.log"

_lines = []
def log(msg):
    print(msg, flush=True)
    _lines.append(str(msg))


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_PATH],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    log(f"[launch] {sys.executable} {SERVER_PATH}")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            log("[init] MCP session initialized")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            log(f"[tools] server exposes {len(names)} tools")
            log("       first 12: " + ", ".join(names[:12]))

            target = "get_maxwell_status"
            if target in names:
                res = await session.call_tool(target, {})
                log(f"[call] {target} -> isError={res.isError}")
                for c in (res.content or []):
                    txt = getattr(c, "text", None) or str(c)
                    log("       content: " + txt[:300])
            else:
                log(f"[call] {target} not found")

            log("[check] connect_to_maxwell present: "
                + str("connect_to_maxwell" in names))

    log("[done] MCP client test PASSED")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        import traceback
        log(f"[FAIL] {type(e).__name__}: {e}")
        log(traceback.format_exc())
    finally:
        try:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(_lines))
        except Exception:
            pass
