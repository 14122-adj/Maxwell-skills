# -*- coding: utf-8 -*-
"""测试 BEMF 报告表达式：WindingA.Voltage / Voltage(WindingA) / WindingA.TotalVoltage。"""
import os
import time
import traceback

LOG = r"D:/ANSYS_Run/m5_bemf_progress.log"
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
        exprs = ["FluxLinkage(WindingA)", "WindingA.FluxLinkage", "WindingA.Current", "Moving1.Torque"]
        for i, expr in enumerate(exprs):
            name = "BemfTest%d" % i
            fname = os.path.join(CSVDIR, "bemf_test%d.csv" % i)
            try:
                rep.CreateReport(
                    name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                    ["NAME:Context", "SimValueContext:=", [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]],
                    ["Time:=", ["All"]],
                    ["X Component:=", "Time", "Y Component:=", [expr]],
                    [])
                ok = rep.ExportToFile(name, fname)
                log("%s -> Export=%r exists=%s size=%s" % (
                    expr, ok, os.path.exists(fname),
                    os.path.getsize(fname) if os.path.exists(fname) else 0))
            except Exception:
                log("%s FAIL:\n%s" % (expr, traceback.format_exc()))
        log("DONE")
    except Exception:
        log("FATAL:\n" + traceback.format_exc())


main()
