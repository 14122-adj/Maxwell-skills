# -*- coding: utf-8 -*-
"""M2 尺寸校验 v2: 逐对象取 faceID 求面积, 与解析期望值比对."""
import sys

AEDT = "D:/ANSYS_Run/M2_25Nm.aedt"
OUT = "D:/ANSYS_Run/m2_verify.txt"
_lines = []


def log(s):
    _lines.append(str(s))


def flush():
    f = open(OUT, "w")
    f.write("\n".join(_lines))
    f.close()


flush()
log("=== M2 verify v2 ===")
proj = oDesktop.OpenProject(AEDT)
des = proj.SetActiveDesign("Motor_Design")
oEditor = des.SetActiveEditor("3D Modeler")
log("units=" + str(oEditor.GetModelUnits()))
log("bbox=" + str(oEditor.GetModelBoundingBox()))

objs = sorted(list(oEditor.GetObjectsInGroup("Sheets")))
log("n_sheets=%d" % len(objs))
for name in objs:
    try:
        ids = list(oEditor.GetFaceIDs(name))
        area = 0.0
        for fid in ids:
            area += float(oEditor.GetFaceArea(fid))
        log("%-12s nface=%d area=%.5f" % (name, len(ids), area))
    except Exception:
        log("%-12s AREA_FAIL %s" % (name, repr(sys.exc_info()[1])))
log("=== end ===")
flush()
