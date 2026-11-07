# -*- coding: utf-8 -*-
# 由 prepare_batch.py 生成, 勿手改
import sys
import traceback

LOG = r"D:/ANSYS_Run/m2_report.txt"
BODY = r"D:/ANSYS_Run/m2_geom_body_run.py"
AEDT = r"D:/ANSYS_Run/M2_25Nm.aedt"
_lines = []


def log(s):
    _lines.append(str(s))


def flush():
    f = open(LOG, "w")
    f.write("\n".join(_lines))
    f.close()


flush()
log("=== driver start ===")
try:
    execfile(BODY)
    log("BODY_OK")
except Exception:
    log("BODY_FAIL: " + repr(sys.exc_info()[1]))
    log(traceback.format_exc())
flush()

proj = None
try:
    proj = oDesktop.GetActiveProject()
    log("active_project=" + proj.GetName())
except Exception:
    log("NO_ACTIVE_PROJECT: " + repr(sys.exc_info()[1]))

if proj is not None:
    try:
        proj.SaveAs(AEDT, True)
        log("SAVED_OK " + AEDT)
    except Exception:
        log("SAVE_FAIL: " + repr(sys.exc_info()[1]))
    flush()
    try:
        names = list(proj.GetTopDesignList())
        log("designs=" + ",".join(names))
        des = proj.SetActiveDesign(names[0])
        log("solution_type=" + des.GetSolutionType())
        oEditor = des.SetActiveEditor("3D Modeler")
        for grp in ("Solids", "Sheets"):
            objs = sorted(list(oEditor.GetObjectsInGroup(grp)))
            log("%s=%d" % (grp, len(objs)))
            for n in objs:
                log("OBJ " + n)
    except Exception:
        log("INVENTORY_FAIL: " + repr(sys.exc_info()[1]))
        log(traceback.format_exc())
    for mod, meth in (("BoundarySetup", "GetBoundaries"),
                      ("AnalysisSetup", "GetSetups")):
        try:
            o = des.GetModule(mod)
            f = getattr(o, meth, None)
            log("%s=%s" % (mod, ",".join(list(f())) if f else "N/A"))
        except Exception:
            log("%s.FAIL %s" % (mod, repr(sys.exc_info()[1])))
log("=== driver end ===")
flush()
