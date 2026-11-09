# -*- coding: utf-8 -*-
"""
m5_load_export.py — 只导出负载工况结果（不重求解），用于「求解/导出解耦」

为什么单独一支
--------------
2026-11-09 实测：`EditWindingGroup` 改完绕组电流后在本会话直接 `CreateReport` 会失败
（消息窗口只有 `Error in command execution`，随后 `ExportToFile` 报
`Report 'TqTrial' not found`，CSV 只剩表头）。同一份工程重开一个新会话再建报告则正常，
说明失败与会话/后处理器的失效状态有关，与求解结果无关。因此导出必须能脱离求解重跑。

导出顺序（三级回退）
--------------------
1. `CreateReport` 新建名义报告 → `ExportToFile`
2. 新建失败时，复用工程里已有的同名族报告（M4 留下的 `Tq` / `FluxA|B|C`）
3. 仍失败则打印报告名清单，交由人工/原生 `.TrCrv` 兜底

运行
----
    "ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/m5_load_export.py"
"""
import os
import time
import traceback

AEDT = r"D:/ANSYS_Run/M5_load_25Nm.aedt"
DESIGN = "Motor_Design"
SETUP = "Setup1"
CSVDIR = r"D:/ANSYS_Run/csv"
LOG = r"D:/ANSYS_Run/m5_load_export_progress.log"

CTX = ["NAME:Context", "SimValueContext:=",
       [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]]

# (新报告名, 表达式, 输出文件, 可复用的既有报告名)
REPORTS = [
    ("TqLoad", "Moving1.Torque", "tq_load.csv", "Tq"),
    ("CurA", "WindingA.Current", "cur_a.csv", None),
    ("CurB", "WindingB.Current", "cur_b.csv", None),
    ("CurC", "WindingC.Current", "cur_c.csv", None),
    ("FluxLoadA", "FluxLinkage(WindingA)", "flux_load_a.csv", "FluxA"),
    ("FluxLoadB", "FluxLinkage(WindingB)", "flux_load_b.csv", "FluxB"),
    ("FluxLoadC", "FluxLinkage(WindingC)", "flux_load_c.csv", "FluxC"),
]

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
    log("=== m5_load_export start ===")
    if not os.path.exists(AEDT):
        log("FAIL project missing: " + AEDT)
        return
    try:
        os.makedirs(CSVDIR)
    except Exception:
        pass

    try:
        oProject = oDesktop.OpenProject(AEDT)
        oDesign = oProject.SetActiveDesign(DESIGN)
    except Exception:
        log("FATAL open:\n" + traceback.format_exc())
        return

    rep = oDesign.GetModule("ReportSetup")
    try:
        names = list(rep.GetAllReportNames())
    except Exception:
        names = []
    log("existing reports: %r" % (names,))
    try:
        log("solutions: %r" % (list(oDesign.GetModule("Solutions").GetSolutionNames()),))
    except Exception:
        log("solution list unavailable")

    ok = 0
    for new_name, expr, fname, reuse in REPORTS:
        path = CSVDIR + "/" + fname
        created = False
        try:
            rep.CreateReport(new_name, "Standard", "Rectangular Plot",
                             SETUP + " : Transient", CTX, ["Time:=", ["All"]],
                             ["X Component:=", "Time", "Y Component:=", [expr]], [])
            created = True
            log("created report %s (%s)" % (new_name, expr))
        except Exception:
            log("CreateReport %s failed :: %s"
                % (new_name, traceback.format_exc().splitlines()[-1]))

        used = None
        for name in ([new_name] if created else []) + ([reuse] if reuse else []):
            try:
                rep.ExportToFile(name, path)
            except Exception:
                try:
                    rep.ExportToFile(name, path, True)
                except Exception:
                    log("  export via %r failed" % (name,))
                    continue
            n = data_rows(path)
            if n > 1:
                used = (name, n)
                break
            log("  export via %r gave %d rows" % (name, n))
        if used:
            log("OK   %s <- %r (%d rows)" % (fname, used[0], used[1]))
            ok += 1
        else:
            log("FAIL %s (no route worked)" % fname)

    log("exported %d/%d" % (ok, len(REPORTS)))
    try:
        oProject.Save()
    except Exception:
        pass
    log("=== m5_load_export end ===")


main()
