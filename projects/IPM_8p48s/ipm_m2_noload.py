#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M2' —— 401 点空载求解驱动（生成 IronPython 并可选真机执行）

为什么复用 M1' 的 `.aedt` 而不是重建
------------------------------------
M1' 的验收是「132 sheet + VALIDATE_OK + 84.0 s」，模型本身已经是受控产物
（`projects/results/ipm8p48s/m1_build_check.json`）。M2' 只改「解不解」，不改几何；
重建一次要 84 s 且会引入「这次建的和上次不是同一个」的风险。所以本驱动
**打开既有工程 → 求解 → 导出**，并用面积/对象数再盘一遍，确认打开的就是 M1'。

导出什么
--------
1. `flux_{a,b,c}.csv`：`FluxLinkage(WindingX)` —— 电流型绕组没有电压输出，
   BEMF 由 `e = −dλ/dt` 求（`ingest_fea.flux_to_bemf`）。
2. `tq_noload.csv`：`Moving1.Torque` —— 空载转矩即齿槽转矩。
3. 场探针（Fields Calculator，**不建任何几何**）：气隙弧的 |B|/Bx/By、齿身径向线、
   轭部弧。仅末时刻（t=0.02 s）有场，这是 `SaveFieldsType='Every N Steps'` +
   `'N Steps'='0'` 的落盘真值（`docs/MAXWELL_INTERNALS.md` §15.5 / P17）。
   点文件坐标**必须是米**，写 mm 不报错但整列为 NaN。

为什么 t=0.02 s 的场可以当「转子 0° 位形」用
--------------------------------------------
1500 rpm × 0.02 s = 0.5 转 = 180° 机械角；8 极的电周期是 90° 机械角，
180° = 2 个整电周期 ⇒ 磁场分布与 t=0 逐点相同。故末时刻快照在**气隙/轭**上
等价于转子初始位形；但**齿身**要注意：48 槽 / 8 极 ⇒ 极轴每 45° 正好落在槽中心
（45/7.5 = 6），末时刻没有「齿正对极轴」的位形，齿磁密快照是**偏保守的下界**，
峰值需 M4' 用多快照或解析通量连续性另测（记 I11）。

用法
----
    python ipm_m2_noload.py            # 只生成脚本 + 点文件（CPython 语法自检）
    python ipm_m2_noload.py --run      # 生成后直接调 ansysedt 真机求解
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ipm_geom  # noqa: E402

AEDT = r"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe"
RUN_DIR = r"D:/ANSYS_Run"
AEDT_IN = RUN_DIR + "/IPM_8p48s_M1.aedt"
AEDT_OUT = RUN_DIR + "/IPM_8p48s_M2.aedt"
CSVDIR = RUN_DIR + "/csv_ipm_m2"
PTSDIR = CSVDIR + "/pts"
SCRIPT = RUN_DIR + "/ipm_m2_solve.py"
LOG = RUN_DIR + "/ipm_m2.log"

# 探针几何（mm）—— 全部由 IPMConfig 推出，不写死表 2 的值
R_GAP_PROBE = None       # 运行时算：(rotor_od/2 + stator_id/2)/2 + 0.14
N_GAP = 181              # 0→45° 一点极距，0.25°/点
N_TOOTH = 46             # r 48.0→57.0，0.2 mm/点
N_YOKE = 91              # 0→45°，0.5°/点


def _fmt(v: float) -> str:
    return ("%.6f" % v).strip()


def probe_geometry(cfg):
    """返回 (gap_r_mm, tooth_angle_deg, tooth_r_lo, tooth_r_hi, yoke_r_mm)。"""
    r_bore = cfg.stator_id / 2.0
    r_rot = r_bore - cfg.airgap
    gap_r = (r_rot + r_bore) / 2.0 + 0.14      # 抬离 Band 中线，避开材料边界插值
    tooth_angle = 180.0 / cfg.slots            # 齿中心 = 半个槽距
    # 槽底半径 = R_bore + Hs2；轭从槽底到外径
    slot_bottom = r_bore + cfg.slot_Hs2
    yoke_r = slot_bottom + 1.0
    return (gap_r, tooth_angle, r_bore + 1.5, slot_bottom - 2.0, yoke_r)


def write_point_files(cfg, outdir: str = PTSDIR) -> dict:
    """写三个 Fields Calculator 点文件（单位**米**），返回 {tag: (path, n_pts)}。"""
    gap_r, tooth_deg, r_lo, r_hi, yoke_r = probe_geometry(cfg)
    os.makedirs(outdir, exist_ok=True)
    out = {}

    def dump(tag, pts):
        path = outdir + "/pts_" + tag + ".txt"
        with open(path, "w", encoding="ascii") as fh:
            for (r, th_deg) in pts:
                th = math.radians(th_deg)
                fh.write("%.10e %.10e 0\n" % (r * 1e-3 * math.cos(th),
                                              r * 1e-3 * math.sin(th)))
        out[tag] = (path, len(pts))

    span = 180.0 / cfg.poles                    # 一个极距 = 45°
    dump("gap", [(gap_r, span * i / (N_GAP - 1.0)) for i in range(N_GAP)])
    dump("tooth", [(r_lo + (r_hi - r_lo) * i / (N_TOOTH - 1.0), tooth_deg)
                   for i in range(N_TOOTH)])
    dump("yoke", [(yoke_r, span * i / (N_YOKE - 1.0)) for i in range(N_YOKE)])
    return out


def build_script(cfg, points: dict, aedt_in: str = AEDT_IN, aedt_out: str = AEDT_OUT,
                 csvdir: str = CSVDIR, log_path: str = LOG) -> str:
    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# IPM 8p48s M2' 空载求解 —— 由 projects/IPM_8p48s/ipm_m2_noload.py 生成，勿手改。")
    A("# 打开 M1' 工程 → 盘点 → 存为 M2 → Analyze 401 点 → 导出磁链/转矩/场探针。")
    A("import os")
    A("import time")
    A("import traceback")
    A("")
    A('LOG = r"' + log_path + '"')
    A('AEDT_IN = r"' + aedt_in + '"')
    A('AEDT_OUT = r"' + aedt_out + '"')
    A('CSVDIR = r"' + csvdir + '"')
    A('T_LAST = "0.02s"')
    A("")
    A("_lines = []")
    A("")
    A("")
    A("def log(s):")
    A("    _lines.append(str(s))")
    A("    try:")
    A('        f = open(LOG, "w")')
    A('        f.write("\\n".join(_lines))')
    A("        f.close()")
    A("    except Exception:")
    A("        pass")
    A("")
    A("")
    A("def data_rows(path):")
    A('    """数数据行：Fields/Report 导出「只给警告不给异常」是常见坑。"""')
    A("    n = 0")
    A("    try:")
    A("        f = open(path)")
    A("        for ln in f:")
    A("            s = ln.strip()")
    A("            if not s:")
    A("                continue")
    A('            head = s.split()[0].strip(",")')
    A("            try:")
    A("                float(head)")
    A("                n += 1")
    A("            except ValueError:")
    A("                pass")
    A("        f.close()")
    A("    except Exception:")
    A("        return -1")
    A("    return n")
    A("")
    A("")
    A("def area_of(name):")
    A("    ids = list(oEditor.GetFaceIDs(name))")
    A("    return sum([float(oEditor.GetFaceArea(f)) for f in ids])")
    A("")
    A("")
    A('log("=== IPM 8p48s M2 noload start ===")')
    A("t_all = time.time()")
    A("")
    A("try:")
    A("    os.makedirs(CSVDIR)")
    A("except Exception:")
    A("    pass")
    A("")
    A("# ------------------------------------------------------------- 打开工程")
    A("try:")
    A("    oProject = oDesktop.OpenProject(AEDT_IN)")
    A("    oDesign = oProject.SetActiveDesign(\"Motor_Design\")")
    A('    log("OPEN_OK " + AEDT_IN)')
    A("except Exception:")
    A('    log("OPEN_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    oProject = None")
    A("    oDesign = None")
    A("")
    A("if oDesign is None:")
    A('    log("=== end (no design) ===")')
    A("else:")
    A("    oEditor = oDesign.SetActiveEditor(\"3D Modeler\")")
    A("    # ------------------------------------------------------ 盘点（确认是 M1'）")
    A("    try:")
    A('        objs = sorted(list(oEditor.GetObjectsInGroup("Sheets")))')
    A('        log("SHEETS=" + str(len(objs)))')
    A("        _pref = {}")
    A("        for o in objs:")
    A('            k = o.split("_")[0]')
    A("            _pref[k] = _pref.get(k, 0) + 1")
    A('        log("PREFIX " + " ".join([k + "=" + str(_pref[k]) for k in sorted(_pref)]))')
    A('        log("SHEET_AREA StatorOuter=" + str(round(area_of("StatorOuter"), 4)))')
    A('        log("SHEET_AREA RotorOuter=" + str(round(area_of("RotorOuter"), 4)))')
    A('        log("SHEET_AREA Region=" + str(round(area_of("Region"), 4)))')
    A("    except Exception:")
    A('        log("INVENTORY_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    try:")
    A('        oModule = oDesign.GetModule("AnalysisSetup")')
    A('        log("SETUPS=" + ",".join(list(oModule.GetSetups())))')
    A('        oB = oDesign.GetModule("BoundarySetup")')
    A('        log("WINDINGS=" + ",".join([w for w in list(oB.GetBoundaries())'
      ' if w.startswith("Winding")]))')
    A('        oM = oDesign.GetModule("ModelSetup")')
    A('        log("MOTIONS=" + ",".join(list(oM.GetMotionSetupNames())))')
    A("    except Exception:")
    A('        log("SETUP_PROBE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    # ------------------------------------------------------------- 存盘")
    A("    try:")
    A("        oProject.SaveAs(AEDT_OUT, True)")
    A('        log("SAVED_OK " + AEDT_OUT)')
    A("    except Exception:")
    A('        log("SAVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    # ------------------------------------------------------- 401 点求解")
    A("    ok = True")
    A("    t0 = time.time()")
    A("    try:")
    A('        oDesign.Analyze("Setup1")')
    A('        log("ANALYZE_OK " + str(round(time.time() - t0, 1)) + "s")')
    A("    except Exception:")
    A("        ok = False")
    A('        log("ANALYZE_FAIL " + str(round(time.time() - t0, 1)) + "s " +')
    A('            repr(traceback.format_exc().splitlines()[-1]))')
    A("    try:")
    A("        oProject.Save()")
    A('        log("SAVE_AFTER_SOLVE_OK")')
    A("    except Exception:")
    A('        log("SAVE_AFTER_SOLVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    # --------------------------------------------------------- 报表导出")
    A("    if not ok:")
    A('        log("skip export (solve failed)")')
    A("    else:")
    A('        rep = oDesign.GetModule("ReportSetup")')
    A('        CTX = ["NAME:Context", "SimValueContext:=", [1, 0, 2, 0, False, False,')
    A("               -1, 1, 0, 1, 1, \"\", 0, 0]]")
    A("")
    A("        def export(name, expr, fname):")
    A("            try:")
    A('                rep.CreateReport(name, "Standard", "Rectangular Plot",')
    A('                                 "Setup1 : Transient", CTX, ["Time:=", ["All"]],')
    A('                                 ["X Component:=", "Time", "Y Component:=", [expr]], [])')
    A("            except Exception:")
    A('                log("create " + name + " raised -> export anyway")')
    A('            path = CSVDIR + "/" + fname')
    A("            try:")
    A("                rep.ExportToFile(name, path)")
    A("            except Exception:")
    A("                rep.ExportToFile(name, path, True)")
    A('            return fname + " rows=" + str(data_rows(path))')
    A("")
    A("        for ph in (\"A\", \"B\", \"C\"):")
    A("            try:")
    A('                log("export flux_" + ph.lower() + " -> " +')
    A('                    export("FluxIPM" + ph, "FluxLinkage(Winding" + ph + ")",')
    A('                           "flux_" + ph.lower() + ".csv"))')
    A("            except Exception:")
    A('                log("EXPORT_FLUX_" + ph + "_FAIL: " +')
    A('                    repr(traceback.format_exc().splitlines()[-1]))')
    A("        try:")
    A('            log("export tq -> " + export("TqIPM", "Moving1.Torque", "tq_noload.csv"))')
    A("        except Exception:")
    A('            log("EXPORT_TQ_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("        # ------------------------------------------------ 场探针（末时刻）")
    A('        oF = oDesign.GetModule("FieldsReporter")')
    A("")
    A("        def probe(pts_path, out_csv, op):")
    A("            try:")
    A("                oF.ClearAll()")
    A("            except Exception:")
    A("                pass")
    A('            oF.EnterQty("B")')
    A("            if op != \"\":")
    A("                oF.CalcOp(op)")
    A('            oF.ExportToFile(out_csv, pts_path, "Setup1 : Transient",')
    A('                            ["Time:=", T_LAST], 1)')
    A('            return out_csv.split("/")[-1] + " rows=" + str(data_rows(out_csv))')
    A("")
    A("        PROBES = [")
    for tag, (path, n) in sorted(points.items()):
        A('            ("' + tag + '", r"' + path + '", "' + str(n) + '"),')
    A("        ]")
    A("        for (_tag, _pt, _n) in PROBES:")
    A("            try:")
    A('                log("probe " + _tag + "_mag -> " +')
    A('                    probe(_pt, CSVDIR + "/" + _tag + "_mag.csv", "Mag"))')
    A("            except Exception:")
    A('                log("PROBE_" + _tag + "_FAIL: " +')
    A('                    repr(traceback.format_exc().splitlines()[-1]))')
    A("        # 气隙径向分量：Br = Bx·cosθ + By·sinθ，两列都导，后处理合成")
    A('        _gap_pt = ""')
    A("        for (_tag, _pt, _n) in PROBES:")
    A("            if _tag == \"gap\":")
    A("                _gap_pt = _pt")
    A("        for _op, _nm in ((\"ScalarX\", \"gap_bx\"), (\"ScalarY\", \"gap_by\")):")
    A("            try:")
    A('                log("probe " + _nm + " -> " +')
    A('                    probe(_gap_pt, CSVDIR + "/" + _nm + ".csv", _op))')
    A("            except Exception:")
    A('                log("PROBE_" + _nm + "_FAIL: " +')
    A('                    repr(traceback.format_exc().splitlines()[-1]))')
    A("    try:")
    A("        oProject.Save()")
    A('        log("FINAL_SAVE_OK")')
    A("    except Exception:")
    A('        log("FINAL_SAVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("")
    A('log("TOTAL " + str(round(time.time() - t_all, 1)) + "s")')
    A('log("=== end ===")')
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M2' 空载求解驱动")
    ap.add_argument("--run", action="store_true", help="生成后直接调用 ansysedt 求解")
    ap.add_argument("--out", default=SCRIPT)
    ap.add_argument("--aedt-in", default=AEDT_IN, help="被求解的既有工程")
    ap.add_argument("--aedt-out", default=AEDT_OUT, help="求解后另存路径")
    ap.add_argument("--csvdir", default=CSVDIR, help="CSV/探针导出目录")
    ap.add_argument("--log", default=LOG)
    args = ap.parse_args(argv)

    cfg = ipm_geom.IPMConfig()
    points = write_point_files(cfg, args.csvdir + "/pts")
    text = build_script(cfg, points, args.aedt_in, args.aedt_out, args.csvdir, args.log)
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("点文件：%d 个 -> %s" % (len(points), args.csvdir + "/pts"))
    for tag in sorted(points):
        print("  %-6s %4d 点  %s" % (tag, points[tag][1], points[tag][0]))
    print("工程：%s -> %s" % (args.aedt_in, args.aedt_out))
    print("生成：%s（%.1f KB，%d 行）" % (args.out, len(text) / 1024.0, text.count("\n")))
    compile(text, args.out, "exec")
    print("语法自检：CPython compile OK")

    if args.run:
        cmd = [AEDT, "-RunScriptAndExit", args.out]
        print("运行：%s" % " ".join(cmd))
        rc = subprocess.call(cmd)
        print("ansysedt rc=%d" % rc)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
