#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M3' —— 负载电流工况（401 点）驱动 + 独立重算

为什么要单独立脚本（不复用 ipm_m2_noload.py）
--------------------------------------------
契约 PROJECT_SPEC §7.3：空载=winding 0A、负载=三相正弦电流，两工况的脚本 /
工程 / CSV / JSON **严格分立**。负载必须从头建新设计再 Analyze
（`docs/MAXWELL_INTERNALS.md` §11.1：打开已求解工程改电流再 Analyze 会得到
"解已失效"，导出只有表头），所以本脚本两段式：

  段1 建模：调 `ipm_build.build_script(cfg, aedt_out, currents=...)` 生成含三相
       正弦电流的**未求解**新工程（几何与 M1' 逐字相同，仅 Current 不同）。
  段2 求解：复用与 M2' 同构的"打开未求解工程 → Analyze 401 点 → 导出"路径，
       只导 flux_{a,b,c}.csv + tq_load.csv（负载不导场探针，Bg 只由空载测）。

电流公式（用户截图 2026-11-22，PROJECT_SPEC §7.3）
------------------------------------------------
    Ia = Imax·sin(2πf·t + φ)
    Ib = Imax·sin(2πf·t − 2π/3 + φ)
    Ic = Imax·sin(2πf·t + 2π/3 + φ)
    f = p·n/60 = 4×1500/60 = 100 Hz；ω = 2πf = 628.3185 rad/s
Maxwell 输入框：Imax*sin(628.3185*Time + φ_rad)。电动取负号（current_sign<0，
与 BEMF 反相，docs/MAXWELL_INTERNALS.md §11.3）——通过 --sign 控制，默认 -1。

Imax 来自实测 BEMF（不能钉死）：P=25·2π·1500/60=3926.99 W，P=3·E·I_rms，
Imax=√2·P/(3E)：E=118→15.688 / 125→14.810 / 132→14.024 / 145→12.767 A。
可用 --bemf 自动插值，或 --imax 显式给定（φ 扫描时固定 Imax）。

用法
----
    python ipm_m3_load.py                                   # 只生成 + 自检
    python ipm_m3_load.py --bemf 125 --phi 0 --run          # 按实测 E 插值 Imax 并真机
    python ipm_m3_load.py --imax 14.810 --phi -15 --run     # 显式 Imax
    python ipm_m3_load.py --bemf 125 --phi -30 --run --case phi_m30

输出（全部 TEMP 在 D:/ANSYS_Run，JSON 汇总在 projects/results/ipm8p48s，KEEP）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ipm_build  # noqa: E402
import ipm_geom  # noqa: E402

AEDT = r"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe"
RUN_DIR = r"D:/ANSYS_Run"
RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")

P_PAIRS = 4
RPM = 1500.0
F_ELEC = P_PAIRS * RPM / 60.0          # 100 Hz
OMEGA_E = 2.0 * math.pi * F_ELEC       # 628.3185 rad/s
T_TARGET = 25.0
P_MECH = T_TARGET * 2.0 * math.pi * RPM / 60.0   # 3926.99 W

# 本机 BEMF 反相点（绝对电角）：apex33 空载实测 e_A = 10.4348·sin(ωt+90°)，
# sign=-1 时电流 i_A = -Imax·sin(ωt+φ_abs)；令 φ_abs = 90° 使 i 与 e 反相 ⇒ T_avg 正。
# 真机验证：φ_abs=90° 得 T_avg=+1.5635 N·m（理论 √2 口径 1.5632，误差 0.017%）；
# φ_abs=0° 得 T_avg≈0（正交）。见账本 I20。
# 契约 §7.3 的 φ 是"相对 BEMF 反相点"的偏移：φ=0 即最大转矩，φ=−15/−30 为扫描点。
BEMF_OFFSET_DEG = 90.0

# E(V) → Imax(A) 锚点（契约 §7.3，Imax = √2·P/(3E)）
_IMAX_TABLE = [(118.0, 15.688), (125.0, 14.810), (132.0, 14.024), (145.0, 12.767)]


def imax_from_bemf(e_rms: float) -> float:
    """按实测相 BEMF RMS 线性插值 Imax；超出表范围按端点外推并标注。"""
    if e_rms <= _IMAX_TABLE[0][0]:
        return _IMAX_TABLE[0][1]
    if e_rms >= _IMAX_TABLE[-1][0]:
        return _IMAX_TABLE[-1][1]
    for (e0, i0), (e1, i1) in zip(_IMAX_TABLE, _IMAX_TABLE[1:]):
        if e0 <= e_rms <= e1:
            return i0 + (i1 - i0) * (e_rms - e0) / (e1 - e0)
    raise AssertionError("unreachable")


def imax_formula(e_rms: float) -> float:
    """解析直算 Imax = √2·P/(3E)（插值表的来源，交叉校验用）。"""
    return math.sqrt(2.0) * P_MECH / (3.0 * e_rms)


def compute_currents(imax: float, phi_deg: float, sign: int = -1) -> dict:
    """三相 Maxwell Current 字面量：A=φ, B=φ−120°, C=φ+120°，电动取负号。"""
    def expr(ph_deg: float) -> str:
        rad = math.radians(ph_deg)
        if abs(rad) < 1e-12:
            tail = ""
        elif rad < 0:
            tail = "-%.9f" % abs(rad)
        else:
            tail = "+%.9f" % rad
        body = "%.6f*sin(%.6f*Time%s)" % (imax, OMEGA_E, tail)
        return body if sign > 0 else "-" + body
    return {"A": expr(phi_deg), "B": expr(phi_deg - 120.0),
            "C": expr(phi_deg + 120.0)}


def build_solve_script(aedt_out: str, csvdir: str, log_path: str,
                       build_script_path: str) -> str:
    """段2：打开段1生成的未求解工程 → Analyze 401 点 → 导出 flux + torque。

    与 ipm_m2_noload.build_script 同构（已真机验证），去掉场探针；tq 文件名
    为 tq_load.csv，与空载 tq_noload.csv 分立。
    """
    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# IPM 8p48s M3' 负载求解 —— 由 projects/IPM_8p48s/ipm_m3_load.py 生成，勿手改。")
    A("import os")
    A("import time")
    A("import traceback")
    A("")
    A('LOG = r"' + log_path + '"')
    A('AEDT_IN = r"' + aedt_out + '"')
    A('CSVDIR = r"' + csvdir + '"')
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
    A('log("=== IPM 8p48s M3 load solve start ===")')
    A("t_all = time.time()")
    A("try:")
    A("    os.makedirs(CSVDIR)")
    A("except Exception:")
    A("    pass")
    A("")
    A("# 打开段1生成的未求解新工程")
    A("try:")
    A("    oProject = oDesktop.OpenProject(AEDT_IN)")
    A('    oDesign = oProject.SetActiveDesign("Motor_Design")')
    A('    log("OPEN_OK " + AEDT_IN)')
    A("except Exception:")
    A('    log("OPEN_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    oProject = None")
    A("    oDesign = None")
    A("")
    A("if oDesign is None:")
    A('    log("=== end (no design) ===")')
    A("else:")
    A('    oB = oDesign.GetModule("BoundarySetup")')
    A("    try:")
    A('        log("CURRENTS=" + str([oB.GetPropertyValue("Winding"+p, "Current") '
      'for p in ("A","B","C")]))')
    A("    except Exception:")
    A('        log("CURRENTS_PROBE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    ok = True")
    A("    t0 = time.time()")
    A("    try:")
    A('        oDesign.Analyze("Setup1")')
    A('        log("ANALYZE_OK " + str(round(time.time() - t0, 1)) + "s")')
    A("    except Exception:")
    A("        ok = False")
    A('        log("ANALYZE_FAIL " + str(round(time.time() - t0, 1)) + "s " +')
    A('            repr(traceback.format_exc().splitlines()[-1]))')
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
    A('                    export("FluxM3" + ph, "FluxLinkage(Winding" + ph + ")",')
    A('                           "flux_" + ph.lower() + ".csv"))')
    A("            except Exception:")
    A('                log("EXPORT_FLUX_" + ph + "_FAIL: " +')
    A('                    repr(traceback.format_exc().splitlines()[-1]))')
    A("        try:")
    A('            log("export tq -> " + export("TqM3", "Moving1.Torque", "tq_load.csv"))')
    A("        except Exception:")
    A('            log("EXPORT_TQ_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    try:")
    A("        oProject.Save()")
    A('        log("FINAL_SAVE_OK")')
    A("    except Exception:")
    A('        log("FINAL_SAVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A('log("TOTAL " + str(round(time.time() - t_all, 1)) + "s")')
    A('log("=== end ===")')
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M3' 负载电流 401 点驱动")
    ap.add_argument("--bemf", type=float, default=None, help="实测相 BEMF RMS(V)，自动插值 Imax")
    ap.add_argument("--imax", type=float, default=None, help="显式峰值电流(A)，优先于 --bemf")
    ap.add_argument("--phi", type=float, default=0.0,
                    help="相对 BEMF 反相点的偏移 φ（电角 deg，默认 0 = 最大转矩反相点；扫描用 -15/-30）")
    ap.add_argument("--phi-abs", type=float, default=None,
                    help="显式绝对电角（覆盖 --phi+offset），用于复现历史 case")
    ap.add_argument("--sign", type=int, default=-1, choices=(-1, 1),
                    help="-1 电动(与 e 反相，默认) / +1 发电")
    ap.add_argument("--case", default="load", help="工况标签，用于工程/CSV/JSON 命名")
    ap.add_argument("--run", action="store_true", help="生成后调用 ansysedt 真机求解")
    args = ap.parse_args(argv)

    phi_abs = args.phi_abs if args.phi_abs is not None else BEMF_OFFSET_DEG + args.phi

    if args.imax is not None:
        imax = args.imax
        src = "explicit"
    elif args.bemf is not None:
        imax = imax_from_bemf(args.bemf)
        src = "bemf_interp@E=%.4f" % args.bemf
    else:
        print("必须给 --imax 或 --bemf（Imax 由实测 BEMF 定，禁止钉死）")
        return 2

    currents = compute_currents(imax, phi_abs, args.sign)
    cfg = ipm_geom.IPMConfig()

    aedt_out = "%s/IPM_8p48s_M3_%s.aedt" % (RUN_DIR, args.case)
    build_py = "%s/ipm_m3_build_%s.py" % (RUN_DIR, args.case)
    solve_py = "%s/ipm_m3_solve_%s.py" % (RUN_DIR, args.case)
    csvdir = "%s/csv_ipm_m3_%s" % (RUN_DIR, args.case)
    build_log = "%s/ipm_m3_build_%s.log" % (RUN_DIR, args.case)
    solve_log = "%s/ipm_m3_solve_%s.log" % (RUN_DIR, args.case)

    # 段1：建模脚本（含电流），复用几何生成器
    build_text = ipm_build.build_script(cfg, aedt_out, currents=currents,
                                        case_tag="M3_load_" + args.case)
    # 段1 的 log 路径要指向负载专用日志（build_script 里 LOG 是模块常量）
    build_text = build_text.replace(
        'LOG = r"' + ipm_build.LOG + '"', 'LOG = r"' + build_log + '"')
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(build_text)
    compile(build_text, build_py, "exec")

    # 段2：求解脚本
    solve_text = build_solve_script(aedt_out, csvdir, solve_log, build_py)
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    compile(solve_text, solve_py, "exec")

    ana = ("%.6f A" % imax_formula(args.bemf)) if args.bemf else "N/A"
    print("Imax = %.6f A (src=%s), 解析直算(√2·P/3E) = %s" % (imax, src, ana))
    print("f = %.1f Hz, ω = %.6f rad/s, φ_rel=%+.1f° / φ_abs=%+.1f° (offset=%.1f), sign=%+d" %
          (F_ELEC, OMEGA_E, args.phi, phi_abs, BEMF_OFFSET_DEG, args.sign))
    for ph in ("A", "B", "C"):
        print("  %s: %s" % (ph, currents[ph]))
    print("建模脚本：%s（%.1f KB）" % (build_py, len(build_text) / 1024.0))
    print("求解脚本：%s（%.1f KB）" % (solve_py, len(solve_text) / 1024.0))
    print("工程：%s" % aedt_out)
    print("CSV：%s" % csvdir)
    print("语法自检：CPython compile OK")

    os.makedirs(RESULTS, exist_ok=True)
    meta = dict(case=args.case, excitation=dict(
        current_A=imax, current_unit="A_peak",
        phase_deg=args.phi, phase_abs_deg=phi_abs, bemf_offset_deg=BEMF_OFFSET_DEG,
        frequency_hz=F_ELEC, omega_rad_s=OMEGA_E, current_sign=args.sign,
        source=src, expressions=currents,
        formula="Imax*sin(2*pi*f*Time + phi_abs), B=phi_abs-120deg, C=phi_abs+120deg; "
                "phi_abs=bemf_offset+phi_rel, bemf_offset=90 (I20)"),
        bemf_input=args.bemf, imax_source=src,
        p_mech_w=P_MECH, build_script=build_py, solve_script=solve_py,
        aedt=aedt_out, csvdir=csvdir, generated=True, solved=False)
    with open(os.path.join(RESULTS, "m3_load_%s.json" % args.case), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    if args.run:
        for script, label in ((build_py, "build"), (solve_py, "solve")):
            cmd = [AEDT, "-RunScriptAndExit", script]
            print("运行 %s：%s" % (label, " ".join(cmd)))
            rc = subprocess.call(cmd)
            print("ansysedt %s rc=%d" % (label, rc))
            if rc != 0:
                return rc
        meta["solved"] = True
        with open(os.path.join(RESULTS, "m3_load_%s.json" % args.case), "w",
                  encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
