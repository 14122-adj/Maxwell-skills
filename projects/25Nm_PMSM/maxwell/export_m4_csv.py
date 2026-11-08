# -*- coding: utf-8 -*-
"""
export_m4_csv.py — 打开**已求解**的 Maxwell 工程，只补导出 CSV（不重新求解）

为什么单独一支脚本
------------------
2026-11-08 实测：`ReportSetup.CreateReport` 在本机 AEDT 21.1 的**批处理**模式下，
144 种参数组合里只有 1 种可用（见 docs/MAXWELL_INTERNALS.md §9.4）。
一旦求解已耗时 400+ s 才发现导出配方写错，重跑整条 build+solve 是纯浪费；
本脚本把「求解」与「导出」解耦，导出失败随时可以单独重试。

可用的 CreateReport 配方（唯一）
------------------------------
    CreateReport(name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                 ["NAME:Context", "SimValueContext:=",
                  [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]],
                 ["Time:=", ["All"]],
                 ["X Component:=", "Time", "Y Component:=", [expr]],
                 [])

三处与「教科书写法」不同、缺一即 `call failed`：
  1. reportTypeArg 必须是 "Standard"，不是 "Transient"
  2. 第 5 参（simValueCtxtArg）必须是 `NAME:Context` 包一层，不能直接给
     `["Domain:=", "Sweep"]`
  3. 第 7 参（expressionsOfTracesArg）把 X/Y 分量写在一起，且不再有 `expr:="` 前缀

为什么导出的是磁链不是电压
--------------------------
`AssignWindingGroup(Type="Current")` 的绕组没有 `WindingA.Voltage` 这个观测量，
导出会得到 "Report has no data for export"。空载反电势只能由磁链求导：

    e(t) = − dλ(t)/dt          （发电机惯例，由 ingest_fea.py 完成）

产物
----
    <csvdir>/tq_noload.csv     Moving1.Torque   [N·m]  齿槽转矩
    <csvdir>/flux_a.csv        FluxLinkage(WindingA) [Wb]
    <csvdir>/flux_b.csv        FluxLinkage(WindingB) [Wb]
    <csvdir>/flux_c.csv        FluxLinkage(WindingC) [Wb]

运行
----
    "ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/export_m4_csv.py"

注意：不带 -ng；oDesktop 由 AEDT 预注入；本文件必须是 IronPython 2.7 语法
（不能用 f-string / pathlib / `print(..., file=)`）。
"""
import os
import time
import traceback

AEDT = r"D:/ANSYS_Run/M5_25Nm.aedt"
DESIGN = "Motor_Design"
CSVDIR = r"D:/ANSYS_Run/csv"
LOG = r"D:/ANSYS_Run/export_m4_csv_progress.log"

# 报告名 -> (表达式, 文件名)
REPORTS = [
    ("Tq", "Moving1.Torque", "tq_noload.csv"),
    ("FluxA", "FluxLinkage(WindingA)", "flux_a.csv"),
    ("FluxB", "FluxLinkage(WindingB)", "flux_b.csv"),
    ("FluxC", "FluxLinkage(WindingC)", "flux_c.csv"),
]

CTX = ["NAME:Context", "SimValueContext:=",
       [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]]

_L = []


def log(m):
    _L.append("[%s] %s" % (time.strftime("%H:%M:%S"), m))
    try:
        f = open(LOG, "w")
        f.write("\n".join(_L))
        f.close()
    except Exception:
        pass


def data_rows(path):
    """数一下 CSV 的数据行（跳过表头/单位/空行），用于确认导出非空。"""
    n = 0
    try:
        f = open(path)
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            head = s.split("\t")[0].split(",")[0].strip().strip('"')
            try:
                float(head)
                n += 1
            except ValueError:
                pass
        f.close()
    except Exception:
        return -1
    return n


def main():
    log("=== export_m4_csv start ===")
    if not os.path.exists(AEDT):
        log("FAIL project not found: " + AEDT)
        return
    try:
        os.makedirs(CSVDIR)
    except Exception:
        pass

    try:
        oProject = oDesktop.OpenProject(AEDT)
        oDesign = oProject.SetActiveDesign(DESIGN)
    except Exception:
        log("FATAL open project:\n" + traceback.format_exc())
        return

    # 先确认工程里真有解，避免对着空 Setup 导出得到 "no data"
    try:
        setups = list(oDesign.GetModule("AnalysisSetup").GetSetups())
        log("setups = %r" % (setups,))
    except Exception:
        log("setup probe failed (non-fatal)")

    rep = oDesign.GetModule("ReportSetup")
    ok = 0
    for name, expr, fname in REPORTS:
        path = CSVDIR + "/" + fname
        try:
            rep.CreateReport(name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                             CTX, ["Time:=", ["All"]],
                             ["X Component:=", "Time", "Y Component:=", [expr]], [])
        except Exception:
            # 该报告可能已存在（重复 CreateReport 会抛），继续尝试导出同名报告
            log("create %s raised -> try export anyway" % name)
        try:
            try:
                rep.ExportToFile(name, path)
            except Exception:
                rep.ExportToFile(name, path, True)
            n = data_rows(path)
            if n > 1:
                log("OK   %s -> %s (%d rows)" % (expr, fname, n))
                ok += 1
            else:
                log("WARN %s exported but only %d data rows" % (fname, n))
        except Exception:
            log("FAIL export %s :: %s" % (fname, traceback.format_exc().splitlines()[-1]))

    log("exported %d/%d" % (ok, len(REPORTS)))
    try:
        oProject.Save()
    except Exception:
        pass
    log("=== export_m4_csv end ===")


main()
