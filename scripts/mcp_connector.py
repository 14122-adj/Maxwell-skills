#!/usr/bin/env python3
"""
MCPConnector — ANSYS Maxwell skill 的 MCP 链接工具
====================================================

本模块是 skill 一直缺失的那块拼图：**MCP 客户端连接器**。

在此之前：
  - `D:\\mcp-maxwell\\server.py` 是一个可用的 FastMCP 服务端（71 个工具，stdio 传输）
  - `maxwell_bridge.py` 自称"唯一 MCP 抽象层"，但 `dry_run=True` 只返回 mock 字符串，
    `dry_run=False` 的 `_inject_ironpython()` 仅生成 IronPython 脚本文本并返回——
    从不 spawn 服务端、从不建立 `mcp.ClientSession`、从不真正调用任何 MCP 工具。

本模块补齐这一缺口：以子进程方式启动 `server.py`，经 stdio 建立 MCP 客户端会话，
把工具调用真正路由到 ANSYS Maxwell COM 自动化层。

设计要点
--------
1. **同步 API**：项目脚本（main.py / mdao_orchestrator / 13 步管线）都是同步调用 bridge，
   故本连接器对外暴露同步方法。内部用一个常驻 asyncio 事件循环线程承载 MCP 的异步生命周期。
2. **跨线程异步生命周期**：`stdio_client` + `ClientSession` 是 `async with` 上下文，
   必须在同一个事件循环里常驻。用一个 orchestrator 协程持有上下文，就绪后通过请求队列
   接收来自同步线程的工具调用，结果经 `concurrent.futures.Future` 回传。
   关键：orchestrator 由 connect() 直接调度（而非作为队列请求），避免"消费者要靠请求来启动"
   的死锁。
3. **Windows 兼容**：子进程 stdio 在 Windows 上需要 ProactorEventLoop，在线程内显式设置策略。
4. **优雅降级**：`mcp` 未装 / 服务端起不来 / Maxwell 未运行——连接器抛出清晰异常，
   由 bridge 捕获后回退 dry_run 估算，绝不让流程中断。
5. **服务端路径自动发现**：环境变量 `MAXWELL_MCP_SERVER` → `D:\\mcp-maxwell\\server.py`
   → skill 内置 `mcp-maxwell/server.py`。

用法
-----
    from mcp_connector import MCPConnector
    conn = MCPConnector()
    conn.connect()                          # 启动服务端并初始化会话
    print(conn.list_tools())                # ['connect_to_maxwell', ...]
    print(conn.call_tool("get_maxwell_status", {}))
    conn.close()

    # 便捷方法：直接执行一段 IronPython 脚本（走服务端 run_script 工具）
    conn.run_script('oEditor.SetModelUnits(["NAME:UnitsSettings","Length:=","mm"])')

依赖：mcp>=1.0.0（本机已装）。pywin32 仅在服务端进程内需要（驱动 Maxwell COM）。
"""
from __future__ import annotations

import asyncio
import atexit
import os
import sys
import threading
from concurrent.futures import Future
from typing import Any, Callable, Optional

# ── 服务端路径发现 ────────────────────────────────────────────
_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _discover_server_path() -> str:
    """按优先级查找可用的 Maxwell MCP 服务端脚本。"""
    env_path = os.environ.get("MAXWELL_MCP_SERVER", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path
    candidate = r"D:\mcp-maxwell\server.py"
    if os.path.isfile(candidate):
        return candidate
    candidate = os.path.join(_SKILL_ROOT, "mcp-maxwell", "server.py")
    if os.path.isfile(candidate):
        return candidate
    return env_path or r"D:\mcp-maxwell\server.py"


def _import_mcp_client():
    """惰性导入 mcp 客户端，缺失时抛出可读异常。"""
    try:
        from mcp import ClientSession, StdioServerParameters  # noqa: F401
        from mcp.client.stdio import stdio_client  # noqa: F401
        return ClientSession, StdioServerParameters, stdio_client
    except ImportError as e:  # pragma: no cover - 环境依赖
        raise RuntimeError(
            "未安装 mcp 包，无法建立 MCP 客户端会话。"
            " 请运行: pip install \"mcp>=1.0.0,<2.0.0\""
        ) from e


class MCPConnector:
    """连接并驱动 Maxwell MCP 服务端的同步客户端。

    生命周期：
        connect() → [call_tool()/list_tools()/run_script()]* → close()
    线程安全：所有公共方法可从任意线程调用；内部串行化到单一事件循环线程。
    """

    def __init__(
        self,
        server_path: Optional[str] = None,
        python_exe: Optional[str] = None,
        connect_timeout: float = 30.0,
        call_timeout: float = 300.0,
    ) -> None:
        self.server_path = server_path or _discover_server_path()
        self.python_exe = python_exe or sys.executable
        self.connect_timeout = connect_timeout
        self.call_timeout = call_timeout

        self._connected: bool = False
        self._closed: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._req_queue: Optional[asyncio.Queue] = None
        self._orch_task: Optional[asyncio.Task] = None
        self._session = None  # mcp.ClientSession，仅后台循环内使用
        self._ctx_session = None
        self._ctx_stdio = None
        # 跨线程就绪信号
        self._ready_event: Optional[threading.Event] = None
        self._session_error: Optional[BaseException] = None
        self._tools_cache: Optional[list[str]] = None
        self._lock = threading.Lock()

    # ── 公共属性 ──────────────────────────────────────────
    @property
    def connected(self) -> bool:
        return self._connected and not self._closed

    # ── 公共同步 API ─────────────────────────────────────
    def connect(self) -> str:
        """启动服务端子进程并建立 MCP 会话。成功返回摘要。"""
        if not os.path.isfile(self.server_path):
            raise FileNotFoundError(
                f"未找到 Maxwell MCP 服务端脚本: {self.server_path}\n"
                f"设置环境变量 MAXWELL_MCP_SERVER 指向 server.py，"
                f"或放到 D:\\mcp-maxwell\\ 或 skill 内 mcp-maxwell/ 目录。"
            )
        with self._lock:
            if self._connected:
                return f"已连接 → {self.server_path}"
            self._start_loop()
            # 直接在后台循环上调度 orchestrator（不经过队列，避免死锁）
            self._ready_event = threading.Event()
            self._session_error = None
            ClientSession, StdioServerParameters, _ = _import_mcp_client()
            params = StdioServerParameters(
                command=self.python_exe,
                args=[self.server_path],
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self._orch_task = asyncio.run_coroutine_threadsafe(
                self._orchestrator(params), self._loop)
            # 等待就绪
            if not self._ready_event.wait(timeout=self.connect_timeout):
                self._shutdown_loop()
                raise TimeoutError(
                    f"连接 Maxwell MCP 服务端超时（{self.connect_timeout}s）。"
                    f" 服务端: {self.server_path}")
            if self._session_error is not None:
                self._shutdown_loop()
                raise RuntimeError(
                    f"建立 MCP 会话失败: {self._session_error}") from self._session_error
            self._connected = True
            atexit.register(self.close)
            n = len(self._tools_cache) if self._tools_cache else "?"
            return f"已连接 Maxwell MCP 服务端 → {self.server_path}（{n} 个工具）"

    def list_tools(self) -> list[str]:
        """返回服务端暴露的工具名列表。"""
        self._require_connected()
        if self._tools_cache is not None:
            return list(self._tools_cache)
        fut = self._submit(self._async_list_tools)
        names = fut.result(timeout=self.call_timeout)
        self._tools_cache = names
        return list(names)

    def call_tool(self, name: str, arguments: Optional[dict] = None,
                  timeout: Optional[float] = None) -> dict:
        """调用一个 MCP 工具并返回结构化结果。

        返回 dict：
          {"ok": True/False, "text": "...", "is_error": bool, "raw": CallToolResult}
        调用本身不抛异常（除非会话已关闭），便于 bridge 安全降级。
        """
        self._require_connected()
        fut = self._submit(self._async_call_tool, name, arguments or {})
        try:
            return fut.result(timeout=timeout or self.call_timeout)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}",
                    "is_error": True, "raw": None, "text": ""}

    def run_script(self, code: str, save_before: bool = True,
                   timeout: Optional[float] = None) -> dict:
        """便捷方法：经服务端 run_script 工具执行一段 IronPython 脚本。"""
        return self.call_tool("run_script",
                              {"script_content": code, "save_before": save_before},
                              timeout=timeout)

    def close(self) -> None:
        """关闭会话并终止服务端子进程。可重复调用。"""
        if self._closed:
            return
        self._closed = True
        self._connected = False
        try:
            self._shutdown_loop()
        except Exception:
            pass

    # ── 内部：事件循环线程管理 ────────────────────────────
    def _start_loop(self) -> None:
        loop_ready = threading.Event()

        def _runner():
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._req_queue = asyncio.Queue()
            loop_ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        t = threading.Thread(name="mcp-connector-loop", target=_runner, daemon=True)
        t.start()
        self._loop_thread = t
        loop_ready.wait(timeout=10)
        if self._loop is None:
            raise RuntimeError("无法启动 MCP 连接器事件循环线程")

    def _submit(self, fn: Callable, *args, **kwargs) -> Future:
        """把一个协程函数提交到后台循环的请求队列，返回同步 Future。"""
        assert self._loop is not None and self._req_queue is not None
        fut: Future = Future()

        async def _enqueue():
            await self._req_queue.put((fut, fn, args, kwargs))

        try:
            asyncio.run_coroutine_threadsafe(_enqueue(), self._loop).result(timeout=10)
        except Exception as e:
            if not fut.done():
                fut.set_exception(e)
        return fut

    def _shutdown_loop(self) -> None:
        loop = self._loop
        if loop is None:
            return
        # 向队列发结束信号
        if self._req_queue is not None:
            end_fut: Future = Future()

            async def _send_end():
                await self._req_queue.put((end_fut, None, (), {}))

            try:
                asyncio.run_coroutine_threadsafe(_send_end(), loop).result(timeout=5)
                end_fut.result(timeout=5)
            except Exception:
                pass
        # 等 orchestrator 退出（它清理 stdio/session 上下文）
        if self._orch_task is not None:
            try:
                self._orch_task.result(timeout=8)
            except Exception:
                pass
        # 停循环
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
        if self._loop_thread:
            self._loop_thread.join(timeout=5)
        self._loop = None
        self._loop_thread = None
        self._req_queue = None
        self._orch_task = None
        self._session = None

    def _require_connected(self) -> None:
        if not self._connected or self._closed:
            raise RuntimeError("MCP 连接器未连接，请先调用 connect()")

    # ── 内部：后台循环里执行的协程 ────────────────────────
    async def _orchestrator(self, params) -> None:
        """常驻协程：持有 stdio_client + ClientSession 上下文，处理请求队列。"""
        ClientSession, _, stdio_client = _import_mcp_client()
        ctx_stdio = None
        ctx_session = None
        try:
            ctx_stdio = stdio_client(params)
            read, write = await ctx_stdio.__aenter__()
            ctx_session = ClientSession(read, write)
            session = await ctx_session.__aenter__()
            await session.initialize()
            self._session = session
            self._ctx_session = ctx_session
            self._ctx_stdio = ctx_stdio
            # 预热：列出工具
            try:
                result = await session.list_tools()
                self._tools_cache = [t.name for t in result.tools]
            except Exception:
                self._tools_cache = None
            # 通知主线程就绪
            self._ready_event.set()
            # 主循环：处理请求队列
            while True:
                item = await self._req_queue.get()
                fut, fn, args, kwargs = item
                if fn is None:  # 关闭信号
                    if not fut.done():
                        fut.set_result(None)
                    break
                try:
                    result = await fn(*args, **kwargs)
                    if not fut.done():
                        fut.set_result(result)
                except Exception as e:
                    if not fut.done():
                        fut.set_exception(e)
        except BaseException as e:
            self._session_error = e
            if self._ready_event is not None and not self._ready_event.is_set():
                self._ready_event.set()
        finally:
            # 清理上下文（逆序）
            for closer in (ctx_session, ctx_stdio):
                if closer is not None:
                    try:
                        await closer.__aexit__(None, None, None)
                    except Exception:
                        pass
            self._session = None
            self._ctx_session = None
            self._ctx_stdio = None

    async def _async_list_tools(self) -> list[str]:
        if self._session is None:
            raise RuntimeError("MCP 会话不可用")
        result = await self._session.list_tools()
        return [t.name for t in result.tools]

    async def _async_call_tool(self, name: str, arguments: dict) -> dict:
        if self._session is None:
            raise RuntimeError("MCP 会话不可用")
        result = await self._session.call_tool(name, arguments)
        texts = []
        for c in (result.content or []):
            txt = getattr(c, "text", None)
            if txt is None:
                txt = str(c)
            texts.append(txt)
        return {
            "ok": not result.isError,
            "text": "\n".join(texts),
            "is_error": bool(result.isError),
            "raw": result,
        }

    # ── 诊断 ──────────────────────────────────────────────
    def diagnose(self) -> dict:
        """返回连接器与服务端诊断信息（不发起 Maxwell 调用）。"""
        info = {
            "server_path": self.server_path,
            "server_exists": os.path.isfile(self.server_path),
            "python_exe": self.python_exe,
            "connected": self.connected,
            "closed": self._closed,
        }
        try:
            import mcp as _mcp  # noqa
            info["mcp_installed"] = True
            info["mcp_version"] = getattr(_mcp, "__version__", "unknown")
        except Exception as e:
            info["mcp_installed"] = False
            info["mcp_error"] = str(e)
        return info

    def __repr__(self) -> str:
        return (f"<MCPConnector server={self.server_path!r} "
                f"connected={self.connected}>")


# ══════════════════════════════════════════════════════════════
#  模块级单例 + 便捷函数
# ══════════════════════════════════════════════════════════════
_default_connector: Optional[MCPConnector] = None
_singleton_lock = threading.Lock()


def get_connector(server_path: Optional[str] = None,
                  auto_connect: bool = False) -> MCPConnector:
    """返回进程级单例连接器。auto_connect=True 时自动 connect()。"""
    global _default_connector
    with _singleton_lock:
        if _default_connector is None or _default_connector._closed:
            _default_connector = MCPConnector(server_path=server_path)
        if auto_connect and not _default_connector.connected:
            _default_connector.connect()
        return _default_connector


def _self_test():
    """自检：连接服务端、列出工具、调用 get_maxwell_status。无需 Maxwell 运行。"""
    print("[1/4] 发现服务端路径...")
    path = _discover_server_path()
    print(f"      server_path = {path}")
    assert os.path.isfile(path), f"服务端不存在: {path}"

    print("[2/4] 建立连接...")
    conn = MCPConnector(server_path=path)
    summary = conn.connect()
    print(f"      {summary}")

    print("[3/4] 列出工具...")
    tools = conn.list_tools()
    print(f"      共 {len(tools)} 个工具，示例: {tools[:5]}")
    assert "get_maxwell_status" in tools
    assert "connect_to_maxwell" in tools

    print("[4/4] 调用 get_maxwell_status（无需 Maxwell）...")
    res = conn.call_tool("get_maxwell_status", {})
    print(f"      ok={res['ok']} is_error={res['is_error']}")
    print(f"      text={res['text'][:120]!r}")
    assert res["ok"], f"工具调用失败: {res}"

    conn.close()
    print("[OK] MCPConnector 自检通过")
    return conn


if __name__ == "__main__":
    _self_test()
