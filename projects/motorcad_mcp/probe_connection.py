#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 连接验证 —— 最小可用探针（KEEP）

用法（项目级 venv）：
    projects/motorcad_mcp/.venv/Scripts/python.exe projects/motorcad_mcp/probe_connection.py

成功判据：MotorCAD() 返回实例、set_variable/get_variable 往返成功、quit() 正常退出。
版本变量名 "Version" 若不被当前 Motor-CAD 暴露，回退到 Motor-CAD 文件名探测，
并把回退原因打印出来（不编数）。
"""
from __future__ import annotations

import importlib.metadata as md
import os

import ansys.motorcad.core as pymotorcad

# 本机实测路径，来源：D:\桌面\Ansys Motor-CAD 2025.2.1.lnk 的 Shell Link
# LocalBasePath 字段（2026-11-26 解析）。PyMotorCAD 0.8.8 默认从
# MOTORCAD_ACTIVEX batch 文件找 exe，该文件指向不存在的 C:\Program Files\...，
# 故必须显式注入。换版本时改这里或设 MOTORCAD_EXE 环境变量。
DEFAULT_MOTORCAD_EXE = r"F:\ANSYS Motor CAD\AnsysMotorCAD\v252\Motor-CAD_2025_2_1.exe"


def main() -> None:
    pkg_version = md.version("ansys-motorcad-core")
    print(f"pymotorcad_version: {pkg_version}")

    exe = os.environ.get("MOTORCAD_EXE", DEFAULT_MOTORCAD_EXE)
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"Motor-CAD exe 不存在: {exe}")
    pymotorcad.set_motorcad_exe(exe)
    print(f"motorcad_exe: {exe}")

    mc = pymotorcad.MotorCAD()
    try:
        # 关闭 Motor-CAD 的消息弹窗，避免自动化被 GUI 阻塞（官方示例用法）。
        mc.set_variable("MessageDisplayState", 2)

        # 版本读取是 P0 的硬判据：任何异常都不得吞掉后报 PROBE_OK。
        version = mc.get_variable("Version")
        conn = getattr(mc, "connection", None)
        print(f"version: {version}")
        print(f"connection: local JSON-RPC, port={getattr(conn, 'port', 'n/a')}")
        print("PROBE_OK")
    finally:
        mc.quit()


if __name__ == "__main__":
    main()
