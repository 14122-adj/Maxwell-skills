# -*- coding: utf-8 -*-
"""E6 150°C 三相短路退磁 —— AEDT 侧求解驱动（IronPython 2.7）。

由 e6_demag_check.py 把 @@占位符@@ 替换后写到 D:/ANSYS_Run/e6_demag_solver_run.py，
再用 ansysedt.exe -RunScriptAndExit 执行。本文件本身是 KEEP 模板，不直接运行。

工况
----
* 磁钢：NdFe35_N/S 的 Hc/μr 已在 body 里按 150°C 外推改写。
* 绕组：三相 Type="Voltage" / Voltage="0V" + R/L → 三相短路，
  电流由感应电压与绕组阻抗决定（不是强加电流源）。
* 全解：StopTime=10 ms / TimeStep=25 µs → 401 点（1 个电周期）。
* 试算：StopTime=0.1 ms / TimeStep=25 µs → 5 点，只判能解。

导出
----
* current_a/b/c.csv     : Report 路径的 WindingX.Current（电压型绕组应有此表达式）
* current_native.csv    : 原生 WindingX_TrCrv.txt 第 1 列（兜底，m4 路径验证过）
* field/gap_bx_<t>us.csv / gap_by_<t>us.csv : 气隙圆弧 r=46.1625 mm、0→360°、
  121 点的 Bx / By，供宿主合成 Br=Bx·cosθ+By·sinθ 并取 B_min。
"""
import math
import os
import sys
import time
import traceback

BODY = r"@@BODY@@"
AEDT = r"@@AEDT@@"
LOG = r"@@LOG@@"
OUTDIR = r"@@OUTDIR@@"
STOP = r"@@STOP@@"
STEP = "0.000025s"
TRIAL = @@TRIAL@@
NSTEPS = r"@@NSTEPS@@"
SETUP = "Setup1 : Transient"

R_GAP_M = 0.0461625        # 气隙中线半径（mm→m）
N_ANG = 120                # 0→360°，每 3°，121 点
TIMES_US = @@TIMES_US@@

_lines = []


def log(s):
    _lines.append(str(s))
    try:
        f = open(LOG, "w")
        f.write("\n".join(_lines))
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
            h = s.split("\t")[0].split(",")[0].strip().strip('"')
            try:
                float(h)
                n += 1
            except ValueError:
                pass
        f.close()
    except Exception:
        return -1
    return n


def write_points(path, pts):
    f = open(path, "w")
    for (x, y, z) in pts:
        f.write("%.12g\t%.12g\t%.12g\n" % (x, y, z))
    f.close()


def gap_points():
    pts = []
    for i in range(N_ANG + 1):
        a = 2.0 * math.pi * i / float(N_ANG)
        pts.append((R_GAP_M * math.cos(a), R_GAP_M * math.sin(a), 0.0))
    return pts


def native_data_dir():
    base = AEDT + "results"
    best = None
    try:
        des = os.listdir(base)
    except Exception:
        return None
    for d in des:
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            continue
        for s in os.listdir(p):
            if s.endswith(".Data"):
                q = os.path.join(p, s)
                m = os.path.getmtime(q)
                if best is None or m > best[0]:
                    best = (m, q)
    return best[1] if best else None


def winding_cols(path):
    """WindingX_TrCrv.txt → (times, currents, fluxes, volts)。

    E6 真机诊断（2026-11-27 试算，e6_demag_trial）：
    电压型绕组（Type="Voltage", Voltage="0V"）的 5 列是
        vals[0] 恒 0 / vals[1] 恒 0 / vals[2] = i[A] / vals[3] = λ[Wb] / vals[4] = e[V]
    而电流型绕组（m4 路径）是 vals[0]=i，vals[3]=λ，vals[4]=dλ/dt。
    两者列布局不同，必须按 Type 取列；取错会把真短路读成 i≡0。
    验证：t=2.5e-5 s 时 i=0.0936083 A、e=-14.2734 V，
    L·di/dt + R·i + e = 0.0038·3740 + 0.48·0.0936 - 14.2734 = -0.018 V（残差 0.13%），
    回路方程闭合，证明短路电流由感应电压驱动而非空解。
    """
    times, cur, flux, volt = [], [], [], []
    try:
        lines = [ln.strip() for ln in open(path) if ln.strip()]
    except Exception:
        return (times, cur, flux, volt)
    i = 2
    while i + 1 < len(lines):
        try:
            t = float(lines[i])
            vals = [float(x) for x in lines[i + 1].split()]
        except ValueError:
            break
        if len(vals) < 5:
            break
        times.append(t)
        cur.append(vals[2])     # 电压型绕组：第 3 列才是电流
        flux.append(vals[3])
        volt.append(vals[4])
        i += 2
    return (times, cur, flux, volt)


def circuit_residual(times, cur, volt, r_ohm, l_h):
    """检测 L·di/dt + R·i + e ≈ 0：电压型绕组短路回路闭合的数值证据。"""
    if len(times) < 3:
        return "insufficient points"
    worst = 0.0
    for k in range(1, len(times) - 1):
        dt = times[k + 1] - times[k - 1]
        if dt <= 0:
            continue
        didt = (cur[k + 1] - cur[k - 1]) / dt
        resid = l_h * didt + r_ohm * cur[k] + volt[k]
        worst = max(worst, abs(resid))
    return "max|Ldi/dt+Ri+e|=%.4g V" % worst


def export_native_currents():
    d = native_data_dir()
    log("native data dir = %r" % (d,))
    if not d:
        return False
    cols = {}
    for ph in ("A", "B", "C"):
        p = os.path.join(d, "Winding" + ph + "_TrCrv.txt")
        cols[ph] = winding_cols(p)
        log("  Winding%s_TrCrv rows=%d" % (ph, len(cols[ph][0])))
    n = min([len(cols[ph][0]) for ph in ("A", "B", "C")])
    if n <= 1:
        return False
    out = OUTDIR + "/current_native.csv"
    f = open(out, "w")
    f.write("Time,WindingA.Current,WindingB.Current,WindingC.Current,"
            "FluxA,FluxB,FluxC\n")
    for i in range(n):
        f.write("%.10g,%.10g,%.10g,%.10g,%.10g,%.10g,%.10g\n" % (
            cols["A"][0][i], cols["A"][1][i], cols["B"][1][i], cols["C"][1][i],
            cols["A"][2][i], cols["B"][2][i], cols["C"][2][i]))
    f.close()
    for ph in ("A", "B", "C"):
        log("  %s %s (peak=%.3f A)"
            % (ph, circuit_residual(cols[ph][0], cols[ph][1], cols[ph][3],
                                    0.48, 0.0038), max(
                [abs(x) for x in cols[ph][1]] + [0.0])))
    log("NATIVE_CURRENT_OK %s (%d rows)" % (out, n))
    return True


log("=== e6 demag solver start trial=%s stop=%s ===" % (TRIAL, STOP))
try:
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)
    if not os.path.isdir(OUTDIR + "/field"):
        os.makedirs(OUTDIR + "/field")
except Exception:
    pass

try:
    execfile(BODY)
    log("BODY_OK")
except Exception:
    log("BODY_FAIL: " + repr(sys.exc_info()[1]))
    log(traceback.format_exc())

oProject = None
oDesign = None
try:
    oProject = oDesktop.GetActiveProject()
    oDesign = oProject.SetActiveDesign(list(oProject.GetTopDesignList())[0])
    log("design=" + oProject.GetName() + "/" + oDesign.GetName())
except Exception:
    log("NO_DESIGN: " + repr(sys.exc_info()[1]))

if oDesign is None:
    log("=== end (no design) ===")
else:
    # 覆盖 setup：短路工况的时长/步长/存场
    oAnaly = oDesign.GetModule("AnalysisSetup")
    try:
        oAnaly.EditSetup("Setup1", [
            "NAME:Setup1",
            "StopTime:=", STOP,
            "TimeStep:=", STEP,
            "SaveFieldsType:=", "Every N Steps",
            "N Steps:=", NSTEPS,
            "UseAdaptiveTimeStep:=", False,
            "NonlinearSolverResidual:=", "0.0001",
            "SmoothBHCurve:=", False])
        log("EDIT_SETUP_OK stop=%s step=%s nsteps=%s" % (STOP, STEP, NSTEPS))
    except Exception:
        log("EDIT_SETUP_FAIL " + repr(sys.exc_info()[1]))

    # 运动带读回（短路仍能解的前提）
    try:
        log("motion_setups=" + ",".join(
            list(oDesign.GetModule("ModelSetup").GetMotionSetupNames())))
    except Exception:
        log("motion_setup_read_fail")

    try:
        oProject.SaveAs(AEDT, True)
        log("SAVED_OK " + AEDT)
    except Exception:
        log("SAVE_FAIL " + repr(sys.exc_info()[1]))

    ok = True
    t0 = time.time()
    try:
        oDesign.Analyze("Setup1")
        log("ANALYZE_OK %.1fs" % (time.time() - t0))
    except Exception:
        ok = False
        log("ANALYZE_FAIL %.1fs %s" % (time.time() - t0, repr(sys.exc_info()[1])))
        log(traceback.format_exc())

    if ok:
        try:
            oProject.Save()
            log("SAVE_AFTER_SOLVE_OK")
        except Exception:
            log("SAVE_AFTER_SOLVE_FAIL " + repr(sys.exc_info()[1]))

        # 短路电流：Report 路径
        rep = oDesign.GetModule("ReportSetup")
        CTX = ["NAME:Context", "SimValueContext:=",
               [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]]
        # 21.1 表达式命名：电压型绕组必须用 Current(WindingX)（402 行含表头），
        # 而 WindingX.Current 对电压型绕组 no data（2026-11-27 真机探测确认）。
        for ph in ("A", "B", "C"):
            try:
                nm = "E6Cur" + ph
                expr = "Current(Winding" + ph + ")"
                rep.CreateReport(nm, "Standard", "Rectangular Plot", SETUP, CTX,
                                 ["Time:=", ["All"]],
                                 ["X Component:=", "Time", "Y Component:=", [expr]], [])
                path = OUTDIR + "/current_" + ph.lower() + ".csv"
                try:
                    rep.ExportToFile(nm, path)
                except Exception:
                    rep.ExportToFile(nm, path, True)
                log("CURRENT_%s %s (%d rows)" % (ph, expr, data_rows(path)))
            except Exception:
                log("CURRENT_%s_FAIL %s" % (ph, repr(sys.exc_info()[1])[:120]))

        # 短路电流：原生 TrCrv 兜底
        try:
            log("native export -> %s" % export_native_currents())
        except Exception:
            log("NATIVE_EXPORT_FAIL " + repr(sys.exc_info()[1]))

        # 气隙场：多时刻 Bx / By（Fields Calculator，坐标用米）
        if not TRIAL:
            pts = gap_points()
            pf = OUTDIR + "/field/pts_gap.txt"
            write_points(pf, pts)
            log("gap points=%d r=%.7f m" % (len(pts), R_GAP_M))
            oF = oDesign.GetModule("FieldsReporter")
            okc = 0
            failc = 0
            for comp, op in (("bx", "ScalarX"), ("by", "ScalarY")):
                try:
                    oF.EnterQty("B")
                    oF.CalcOp(op)
                    log("stack %s ok" % op)
                except Exception:
                    log("STACK_%s_FAIL %s" % (op, repr(sys.exc_info()[1])))
                    continue
                for t_us in TIMES_US:
                    out = OUTDIR + "/field/gap_%s_%06dus.csv" % (comp, t_us)
                    var = ["Time:=", "%.9gs" % (t_us / 1e6)]
                    try:
                        oF.ExportToFile(out, pf, SETUP, var, 1)
                        n = data_rows(out)
                        if n > 1:
                            okc += 1
                        else:
                            failc += 1
                            if failc <= 5:
                                log("FIELD_EMPTY %s %s rows=%d" % (comp, t_us, n))
                    except Exception:
                        failc += 1
                        if failc <= 5:
                            log("FIELD_FAIL %s %s %s"
                                % (comp, t_us, repr(sys.exc_info()[1])[:90]))
            log("FIELD_EXPORT_DONE ok=%d fail=%d" % (okc, failc))
        else:
            log("trial: skip field export")
    else:
        log("skip export (solve failed)")

    try:
        oProject.Save()
        log("FINAL_SAVE_OK")
    except Exception:
        log("FINAL_SAVE_FAIL " + repr(sys.exc_info()[1]))

log("=== e6 demag solver end ===")
