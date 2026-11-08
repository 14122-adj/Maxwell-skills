# -*- coding: utf-8 -*-
"""
m5_export.py — 打开已求解的 M5_25Nm.aedt，导出空载转矩与三相 BEMF。
不重新求解，只创建报告并导出 CSV。
"""
import os
import time
import traceback

LOG = r"D:/ANSYS_Run/m5_export_progress.log"
AEDT = r"D:/ANSYS_Run/M5_25Nm.aedt"
CSVDIR = r"D:/ANSYS_Run/csv"


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(line)
    f = open(LOG, "a")
    f.write(line + "\n")
    f.close()


def main():
    open(LOG, "w").close()
    log("start")
    try:
        oProject = oDesktop.OpenProject(AEDT)
        oDesign = oProject.SetActiveDesign("Motor_Design")
        try:
            os.makedirs(CSVDIR)
        except Exception:
            pass
        rep = oDesign.GetModule("ReportSetup")

        def export(name, exprs, fname):
            rep.CreateReport(
                name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                ["NAME:Context", "SimValueContext:=", [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]],
                ["Time:=", ["All"]],
                ["X Component:=", "Time", "Y Component:=", [exprs]],
                [])
            try:
                rep.ExportToFile(name, CSVDIR + "/" + fname)
            except Exception:
                rep.ExportToFile(name, CSVDIR + "/" + fname, True)
            log("exported " + fname)

        export("Tq", "Moving1.Torque", "tq_noload.csv")
        # 电流型绕组没有 WindingA.Voltage 输出；空载 BEMF 由磁链对时间求导得到
        export("FluxA", "FluxLinkage(WindingA)", "flux_a.csv")
        export("FluxB", "FluxLinkage(WindingB)", "flux_b.csv")
        export("FluxC", "FluxLinkage(WindingC)", "flux_c.csv")
        log("DONE")
    except Exception:
        log("FATAL:\n" + traceback.format_exc())


main()
