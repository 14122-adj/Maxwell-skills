#!/usr/bin/env python3
"""
Mock Maxwell MCP 服务端启动器
=============================
在被测子进程里：先注入 mock win32com（让 connect_to_maxwell 成功），再加载真实的
`D:\\mcp-maxwell\\server.py` 并以 stdio 传输运行其 FastMCP 服务。

用法（被 MCPConnector 当作 server_path 启动）：
    python mock_maxwell_server.py

效果：服务端 71 个工具的全部 COM 调用落到 mock 对象图，无需真实 ANSYS Maxwell。
"""
from __future__ import annotations

import importlib.util
import os
import sys

# 1) 先注入 mock win32com —— 必须在 import 真实 server 之前
_DEBUG_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DEBUG_DIR)
import mock_maxwell_com  # noqa: F401  导入即注入 sys.modules

# 2) 加载真实 server.py（不触发 __main__，因 __name__ 不是 "__main__"）
_SERVER_PATH = r"D:\mcp-maxwell\server.py"
spec = importlib.util.spec_from_file_location("_maxwell_server_under_mock", _SERVER_PATH)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)
mcp = _mod.mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
