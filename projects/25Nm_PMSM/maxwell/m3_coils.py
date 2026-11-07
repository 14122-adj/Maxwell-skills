# -*- coding: utf-8 -*-
"""
m3_coils.py — 用逐个线圈 AssignCoil 的方式把 12 个 Coil 挂到 WindingA/B/C。
依据 archive/maxwell2d_25nm.py 的可用写法：
  AssignCoil(["NAME:...", "Objects:=", ["Coil_x"],
              "Conductor number:=", "40", "PolarityType:=", "Positive",
              "Winding:=", "WindingA"])
相带（与 M2 脚本一致）：
  Coil_1/7 A+ ; Coil_2/8 A- ; Coil_3/9 B+ ; Coil_4/10 B- ; Coil_5/11 C+ ; Coil_6/12 C-
保存为 M4_25Nm.aedt。
"""
import time
import traceback

LOG = r"D:/ANSYS_Run/m3_coils_progress.log"
SRC = r"D:/ANSYS_Run/M3_25Nm.aedt"
DST = r"D:/ANSYS_Run/M4_25Nm.aedt"


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line)
    f = open(LOG, "a")
    f.write(line + "\n")
    f.close()


def main():
    open(LOG, "w").close()
    log("start")
    oProject = None
    try:
        oProject = oDesktop.OpenProject(SRC)
        oDesign = oProject.SetActiveDesign("Motor_Design")
        oBnd = oDesign.GetModule("BoundarySetup")
        log("opened " + SRC)

        mapping = [
            ("Coil_1", "A", "Positive", "A_1"),
            ("Coil_2", "A", "Negative", "A_2"),
            ("Coil_3", "B", "Positive", "B_1"),
            ("Coil_4", "B", "Negative", "B_2"),
            ("Coil_5", "C", "Positive", "C_1"),
            ("Coil_6", "C", "Negative", "C_2"),
            ("Coil_7", "A", "Positive", "A_3"),
            ("Coil_8", "A", "Negative", "A_4"),
            ("Coil_9", "B", "Positive", "B_3"),
            ("Coil_10", "B", "Negative", "B_4"),
            ("Coil_11", "C", "Positive", "C_3"),
            ("Coil_12", "C", "Negative", "C_4"),
        ]
        for coil, phase, pol, tag in mapping:
            try:
                oBnd.AssignCoil(
                    ["NAME:" + tag, "Objects:=", [coil],
                     "Conductor number:=", "40", "PolarityType:=", pol,
                     "Winding:=", "Winding" + phase])
                log("AssignCoil ok: %s -> Winding%s (%s)" % (coil, phase, pol))
            except Exception:
                log("AssignCoil FAIL %s:\n%s" % (coil, traceback.format_exc()))

        oProject.SaveAs(DST, True)
        log("SAVED " + DST)
        log("DONE")
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        if oProject is not None:
            try:
                oProject.SaveAs(r"D:/ANSYS_Run/M4_partial.aedt", True)
                log("partial saved")
            except Exception:
                log("partial save failed")


main()
