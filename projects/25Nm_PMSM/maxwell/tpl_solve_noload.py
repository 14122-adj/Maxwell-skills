# -*- coding: utf-8 -*-
"""模板路径空载求解 + 导出（IronPython 2.7，由 `-RunScriptAndExit` 直接执行）

为什么单独一个脚本
------------------
`maxwell_model/*.py` 是**建模**脚本（由 `gen_maxwell_model.py` 从
`scripts/main.py::MotorModelBuilder` 生成），它只建到 `Setup1` 为止，没有 Analyze、
也没有任何导出。G4 的目标是「模板产出的模型能不能真的解出与手写工程同样的数」，
所以需要一段**只做求解与导出**的驱动，且必须能与生成物一起跑在同一个 AEDT 进程里。

链路
----
1. `execfile(BODY)`：BODY 是 `prepare_batch.prepare()` 把
   `maxwell_model/build_25Nm_SPMSM.py` 清洗成的可批跑脚本（剥掉 ScriptEnv、
   把 f-string 降级）。建模七步（setup/materials/geometry/winding/boundary/mesh/solver）
   全在里面。
2. 面积自检：`GetFaceIDs` + `GetFaceArea`（`.aedt` 是加密块，事后不能 grep 尺寸）。
3. `SaveAs` 到 `T4_tpl_noload.aedt`。
4. `Analyze("Setup1")`：生成物里已是 20 ms / 5e-5 s / 400 步（全时长，不跑试算）。
5. 导出 `FluxLinkage(WindingA|B|C)` 与 `Moving1.Torque` 到 `D:/ANSYS_Run/csv_tpl/`。
   2026-11-08 的教训：`ExportToFile` 会「静默不写」，必须数数据行，不能只看有没有抛异常。

运行
----
  "ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/tpl_solve_noload.py"

  注意：不带 `-ng`；`oDesktop` 由 AEDT 预注入；本文件必须是 IronPython 2.7 语法。
"""
import os
import sys
import time
import traceback

LOG = r"D:/ANSYS_Run/tpl_solve.log"
AEDT_OUT = r"D:/ANSYS_Run/T4_tpl_noload.aedt"
BODY = r"D:/ANSYS_Run/tpl_body.py"
CSVDIR = r"D:/ANSYS_Run/csv_tpl"

_lines = []


def log(s):
    _lines.append(str(s))
    try:
        f = open(LOG, "w")
        f.write("\n".join(_lines))
        f.close()
    except Exception:
        pass


def dump_area(oEditor, name):
    try:
        ids = list(oEditor.GetFaceIDs(name))
        total = sum([float(oEditor.GetFaceArea(f)) for f in ids])
        return "%s: faces=%d area=%.3f mm2" % (name, len(ids), total)
    except Exception:
        return "%s: AREA_FAIL %s" % (name, repr(traceback.format_exc().splitlines()[-1]))


def data_rows(path):
    """数数据行（跳过表头/单位/空行）—— 导出「只给警告不给异常」是常见坑。"""
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


log("=== tpl_solve_noload start ===")

oProject = None
try:
    execfile(BODY)
    log("BODY_OK")
except Exception:
    log("BODY_FAIL: " + repr(sys.exc_info()[1]))
    log(traceback.format_exc())

# ---------------------------------------------------------------- 面积自检
try:
    names = list(oProject.GetTopDesignList())
    log("designs=" + ",".join(names))
    oDesign = oProject.SetActiveDesign(names[0])
    log("solution_type=" + oDesign.GetSolutionType())
    oEditor = oDesign.SetActiveEditor("3D Modeler")
    for grp in ("Solids", "Sheets"):
        objs = sorted(list(oEditor.GetObjectsInGroup(grp)))
        log("%s=%d %s" % (grp, len(objs), ",".join(objs)))
    for nm in ["Region", "StatorOuter", "RotorOuter", "Band", "PM_1", "Coil_1"]:
        log(dump_area(oEditor, nm))
    for mod, meth in (("BoundarySetup", "GetBoundaries"),
                      ("AnalysisSetup", "GetSetups"),
                      ("ModelSetup", "GetMotionSetupNames")):
        try:
            o = oDesign.GetModule(mod)
            f = getattr(o, meth, None)
            log("%s.%s=%s" % (mod, meth, ",".join(list(f())) if f else "N/A"))
        except Exception:
            log("%s.%s.FAIL %s" % (mod, meth, repr(sys.exc_info()[1])))
except Exception:
    log("INVENTORY_FAIL: " + repr(sys.exc_info()[1]))
    log(traceback.format_exc())
    oDesign = None

if oDesign is None:
    log("=== end (no design) ===")
else:
    # ------------------------------------------------------------ 存盘（保模型）
    try:
        oProject.SaveAs(AEDT_OUT, True)
        log("SAVED_OK " + AEDT_OUT)
    except Exception:
        log("SAVE_FAIL: " + repr(sys.exc_info()[1]))

    # ------------------------------------------------------------ 全时长求解
    ok = True
    t0 = time.time()
    try:
        # 2026-11-09：`Analyze()` 成功时返回 None，用返回值判成败会把成功当失败。
        oDesign.Analyze("Setup1")
        log("ANALYZE_OK %.1fs" % (time.time() - t0))
    except Exception:
        ok = False
        log("ANALYZE_FAIL %.1fs %s" % (time.time() - t0, repr(sys.exc_info()[1])))
        log(traceback.format_exc())

    # 全时长解只活在进程内存里，先存盘再导出：导出再出岔子也不用重跑。
    try:
        oProject.Save()
        log("SAVE_AFTER_SOLVE_OK")
    except Exception:
        log("SAVE_AFTER_SOLVE_FAIL: " + repr(sys.exc_info()[1]))

    # ------------------------------------------------------------ 导出
    if ok:
        try:
            os.makedirs(CSVDIR)
        except Exception:
            pass
        rep = oDesign.GetModule("ReportSetup")
        CTX = ["NAME:Context", "SimValueContext:=",
               [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]]

        def export(name, exprs, fname):
            """2021.1 批处理下 `CreateReport` 唯一可用结构（详见 MAXWELL_INTERNALS §9.4）：
            reportType="Standard"、SimValueContext 走 NAME:Context、
            trace 用 ["X Component:=","Time","Y Component:=",[expr]]。"""
            rep.CreateReport(name, "Standard", "Rectangular Plot", "Setup1 : Transient",
                             CTX, ["Time:=", ["All"]],
                             ["X Component:=", "Time", "Y Component:=", [exprs]], [])
            path = CSVDIR + "/" + fname
            try:
                rep.ExportToFile(name, path)
            except Exception:
                rep.ExportToFile(name, path, True)
            return "%s (%d rows)" % (fname, data_rows(path))

        try:
            log("export tq -> " + export("TqTpl", "Moving1.Torque", "tq_noload.csv"))
        except Exception:
            log("EXPORT_TQ_FAIL: " + repr(sys.exc_info()[1]))
        for ph in ("A", "B", "C"):
            try:
                log("export flux_%s -> %s"
                    % (ph.lower(),
                       export("FluxTpl" + ph, "FluxLinkage(Winding" + ph + ")",
                              "flux_" + ph.lower() + ".csv")))
            except Exception:
                log("EXPORT_FLUX_%s_FAIL: %s"
                    % (ph, repr(sys.exc_info()[1])))
        # 原生 TrCrv 作为交叉核对（环形缓冲只保最后 10 步，算不了 RMS，但可验口径）
        try:
            base = AEDT_OUT + "results"
            for d in os.listdir(base):
                p = os.path.join(base, d)
                if os.path.isdir(p):
                    log("results_dir=" + p)
                    for s in os.listdir(p):
                        log("  " + s)
        except Exception:
            log("RESULTS_LIST_FAIL: " + repr(sys.exc_info()[1]))
    else:
        log("skip export (solve failed)")

    try:
        oProject.Save()
        log("FINAL_SAVE_OK")
    except Exception:
        log("FINAL_SAVE_FAIL: " + repr(sys.exc_info()[1]))

log("=== tpl_solve_noload end ===")
