#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 8p48s M2 t065c8 空载 —— 已求解工程补导场探针 + 独立重算（KEEP，2026-11-28）

为什么存在
----------
11-27 晚 t=0.65/cps=8 空载 401 点只导了 flux_{a,b,c}.csv 与 tq_load.csv，
未导 gap_mag/gap_bx/gap_by/tooth_mag/yoke_mag，`ipm_m2_check.py` 因缺文件报
FileNotFoundError，Bg / 齿槽 / B_tooth / B_yoke 未重算。本脚本**不重解 401 点**
（工程 `SPM_8p48s_M2_t065c8.aedt` 已 ANALYZE_OK、.aedtresults 完整），只打开
已求解工程，用 FieldsReporter 在末时刻 t=0.02s 补导场探针，再独立重算四项判据。

判据（`docs/ENGINEERING_ACCEPTANCE.md` §2，未改）
------------------------------------------------
* Bg ∈ **0.70–0.90 T**（气隙弧 |B| 峰，r=46.3025 mm，0→45°，181 点）
* 齿槽峰峰值 ≤ **5% × 25 N·m = 1.25 N·m**（tq_load.csv 即零电流空载转矩）
* B_tooth ≤ **1.65 T** / B_yoke ≤ **1.50 T**
* 相 BEMF RMS ∈ 118–145 V（flux 重算，交叉校验已有 m2_noload_spm_t065c8.json）

点坐标必须用**米**（docs/MAXWELL_INTERNALS.md §15.5，写 mm 全 NaN）；
复用 `ipm_m2_noload.write_point_files`（SPM 定子/气隙继承 IPMConfig，几何一致）。
FAIL 原样留档，不改判据、不删数据。

用法
----
    python spm_m2_field_probe.py                      # 只生成脚本 + 点文件（语法自检）
    python spm_m2_field_probe.py --run                # 生成后真机补导场探针
    python spm_m2_field_probe.py --check              # 独立重算 + 写 JSON（读已导 CSV）
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
for _p in (_HERE, os.path.join(_ROOT, "projects", "25Nm_PMSM")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ingest_fea as ing  # noqa: E402
import ipm_geom  # noqa: E402
import ipm_m2_check as chk  # noqa: E402
import ipm_m2_noload as m2n  # noqa: E402

AEDT = m2n.AEDT
RUN_DIR = m2n.RUN_DIR
AEDT_IN = RUN_DIR + "/SPM_8p48s_M2_t065c8.aedt"
CSVDIR = RUN_DIR + "/csv_spm_m2_t065c8"
SCRIPT = RUN_DIR + "/spm_m2_fieldprobe_t065c8.py"
LOG = RUN_DIR + "/spm_m2_fieldprobe_t065c8.log"
RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")
JSON_OUT = os.path.join(RESULTS, "m2_noload_spm_t065c8_fields.json")
T_LAST = "0.02s"          # StopTime；2 个电周期末、转子机械角 0°（I11/G4-B 已验证口径）


def build_script(points: dict, aedt_in: str = AEDT_IN, csvdir: str = CSVDIR,
                 log_path: str = LOG) -> str:
    """生成 IronPython 后处理脚本：打开已求解工程 → 只导场探针，不 Analyze。"""
    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# SPM M2 t065c8 场探针补导 —— 由 projects/IPM_8p48s/spm_m2_field_probe.py 生成，勿手改。")
    A("# 打开已求解工程（不再 Analyze），用 FieldsReporter 在末时刻补导气隙/齿/轭场。")
    A("import os")
    A("import time")
    A("import traceback")
    A("")
    A("LOG = r'" + log_path + "'")
    A("_lines = []")
    A("def log(s):")
    A("    _lines.append(str(s))")
    A("    try:")
    A("        f = open(LOG, 'w'); f.write('\\n'.join(_lines)); f.close()")
    A("    except Exception:")
    A("        pass")
    A("")
    A("def data_rows(path):")
    A("    n = 0")
    A("    try:")
    A("        f = open(path)")
    A("        for ln in f:")
    A("            s = ln.strip()")
    A("            if not s:")
    A("                continue")
    A("            head = s.split()[0].strip(',')")
    A("            try:")
    A("                float(head); n += 1")
    A("            except ValueError:")
    A("                pass")
    A("        f.close()")
    A("    except Exception:")
    A("        return -1")
    A("    return n")
    A("")
    A("t_all = time.time()")
    A("log('=== SPM M2 t065c8 FIELD PROBE START ===')")
    A("try:")
    A("    oProject = oDesktop.OpenProject(r'" + aedt_in + "')")
    A("    oDesign = oProject.SetActiveDesign('Motor_Design')")
    A("    log('OPEN_OK ' + r'" + aedt_in + "')")
    A("except Exception:")
    A("    log('OPEN_FAIL: ' + repr(traceback.format_exc().splitlines()[-1]))")
    A("    oDesign = None")
    A("")
    A("if oDesign is not None:")
    A("    oF = oDesign.GetModule('FieldsReporter')")
    A("    CSVDIR = r'" + csvdir + "'")
    A("    T_LAST = '" + T_LAST + "'")
    A("    def probe(pts_path, out_csv, op):")
    A("        try:")
    A("            oF.ClearAll()")
    A("        except Exception:")
    A("            pass")
    A("        oF.EnterQty('B')")
    A("        if op:")
    A("            oF.CalcOp(op)")
    A("        oF.ExportToFile(out_csv, pts_path, 'Setup1 : Transient',")
    A("                        ['Time:=', T_LAST], 1)")
    A("        return out_csv.split('/')[-1] + ' rows=' + str(data_rows(out_csv))")
    A("    PROBES = [")
    for tag, (path, n) in sorted(points.items()):
        A('        ("' + tag + '", r"' + path + '", "' + str(n) + '"),')
    A("    ]")
    A("    for (_tag, _pt, _n) in PROBES:")
    A("        try:")
    A("            log('probe ' + _tag + '_mag -> ' +")
    A("                probe(_pt, CSVDIR + '/' + _tag + '_mag.csv', 'Mag'))")
    A("        except Exception:")
    A("            log('PROBE_' + _tag + '_FAIL: ' +")
    A("                repr(traceback.format_exc().splitlines()[-1]))")
    A("    _gap_pt = ''")
    A("    for (_tag, _pt, _n) in PROBES:")
    A("        if _tag == 'gap':")
    A("            _gap_pt = _pt")
    A("    for _op, _nm in (('ScalarX', 'gap_bx'), ('ScalarY', 'gap_by')):")
    A("        try:")
    A("            log('probe ' + _nm + ' -> ' +")
    A("                probe(_gap_pt, CSVDIR + '/' + _nm + '.csv', _op))")
    A("        except Exception:")
    A("            log('PROBE_' + _nm + '_FAIL: ' +")
    A("                repr(traceback.format_exc().splitlines()[-1]))")
    A("log('TOTAL ' + str(round(time.time() - t_all, 1)) + 's')")
    A("log('=== end ===')")
    return "\n".join(L) + "\n"


def check(csvdir: str = CSVDIR, json_out: str = JSON_OUT) -> dict:
    """独立重算 Bg / 齿槽 / B_tooth / B_yoke + BEMF 交叉校验，写 JSON。"""
    cfg = ipm_geom.IPMConfig()
    gap = chk.gap_block(csvdir, cfg)
    tooth = chk.tooth_block(csvdir, cfg)
    yoke = chk.yoke_block(csvdir, cfg)
    bemf = chk.bemf_block(csvdir)

    tq_path = os.path.join(csvdir, "tq_load.csv")
    t, cols = ing.load_maxwell_csv(tq_path)
    umap = ing._units_by_column(tq_path)
    key = None
    for k in cols:
        u = (umap.get(k, "") or "").lower().replace(" ", "")
        if "torque" in k.lower() or u in ("newtonmeter", "mnewtonmeter"):
            key = k
            break
    if key is None:
        key = list(cols)[0]
    scale = chk.torque_scale(umap.get(key, ""))
    tq = [v * scale for v in cols[key]]
    tq_st = chk.pp_ct(t, tq)
    cog_pct = 100.0 * tq_st["pp"] / chk.TORQUE_RATED

    checks = []
    if gap:
        checks.append({"name": "Bg ∈ 0.70–0.90 T", "value": gap["b_max"],
                       "limit": list(chk.BG_RANGE), "op": "in", "status": gap["verdict"]})
    else:
        checks.append({"name": "Bg ∈ 0.70–0.90 T", "value": None,
                       "limit": list(chk.BG_RANGE), "status": "MISSING"})
    checks.append({"name": "齿槽峰峰值 ≤ 5% (1.25 N·m)", "value": tq_st["pp"],
                   "limit": chk.COGGING_MAX_PCT, "op": "<=",
                   "status": "PASS" if cog_pct <= chk.COGGING_MAX_PCT else "FAIL"})
    if tooth:
        checks.append({"name": "B_tooth ≤ 1.65 T", "value": tooth["b_max"],
                       "limit": chk.B_TOOTH_MAX, "op": "<=", "status": tooth["verdict"]})
    if yoke:
        checks.append({"name": "B_yoke ≤ 1.50 T", "value": yoke["b_max"],
                       "limit": chk.B_YOKE_MAX, "op": "<=", "status": yoke["verdict"]})
    checks.append({"name": "相 BEMF RMS ∈ 118–145 V（交叉校验）",
                   "value": bemf["phase_rms_mean"], "limit": list(chk.BEMF_RANGE),
                   "op": "in",
                   "status": "PASS" if chk.BEMF_RANGE[0] <= bemf["phase_rms_mean"]
                   <= chk.BEMF_RANGE[1] else "FAIL"})

    ana = chk.analytic_crosscheck(bemf, gap, cfg, cps=8)  # 新基线 cps=8（非默认 10）
    out = {
        "case": "spm_t065c8_noload_field_probe",
        "stage": "M2 空载场探针补导（已求解工程，未重解 401 点）",
        "geometry": dict(core_od=90.35, pm_t=0.65, cps=8, poles=8, slots=48,
                         pole_arc=0.90, band_r=46.1625, airgap=0.675),
        "probe": dict(t_last_s=T_LAST, gap_r_mm=round(m2n.probe_geometry(cfg)[0], 4),
                      n_gap=m2n.N_GAP, n_tooth=m2n.N_TOOTH, n_yoke=m2n.N_YOKE,
                      coord_unit="m（导入后 ×1000→mm）"),
        "bemf": {"phase_rms_mean": bemf["phase_rms_mean"],
                 "line_thd_max": bemf["line_thd_max"]},
        "torque": {"unit": umap.get(key, ""), "scale": scale,
                   "pp_nm": tq_st["pp"], "max_nm": tq_st["max"],
                   "min_nm": tq_st["min"], "cogging_pct": cog_pct,
                   "window_samples": tq_st["n"]},
        "flux_density": {"gap": gap, "tooth": tooth, "yoke": yoke},
        "analytic_crosscheck": ana,
        "checks": checks,
        "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        "evidence": "D:/ANSYS_Run/csv_spm_m2_t065c8/{gap_mag,gap_bx,gap_by,tooth_mag,yoke_mag,tq_load,flux_*}.csv",
        "note": "不重解 401 点；gap 场仅末时刻 t=0.02s 快照（P17 口径），判据未改、FAIL 未删",
    }
    os.makedirs(os.path.dirname(json_out), exist_ok=True)
    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SPM M2 t065c8 场探针补导 + 独立重算")
    ap.add_argument("--run", action="store_true", help="生成后真机补导场探针（不重解）")
    ap.add_argument("--check", action="store_true", help="独立重算已导 CSV 并写 JSON")
    ap.add_argument("--aedt", default=AEDT_IN)
    ap.add_argument("--csvdir", default=CSVDIR)
    ap.add_argument("--out", default=SCRIPT)
    ap.add_argument("--log", default=LOG)
    ap.add_argument("--json", default=JSON_OUT)
    args = ap.parse_args(argv)

    if args.check:
        out = check(args.csvdir, args.json)
        print("status=%s" % out["status"])
        for c in out["checks"]:
            print("  %-38s %-10s %s" % (c["name"], str(c["value"]), c["status"]))
        print("JSON -> %s" % args.json)
        return 0 if out["status"] == "PASS" else 1

    cfg = ipm_geom.IPMConfig()
    points = m2n.write_point_files(cfg, args.csvdir + "/pts")
    text = build_script(points, args.aedt, args.csvdir, args.log)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    compile(text, args.out, "exec")
    print("点文件：%d 个 -> %s/pts" % (len(points), args.csvdir))
    for tag in sorted(points):
        print("  %-6s %4d 点" % (tag, points[tag][1]))
    print("生成 %s（%.1f KB）; CPython compile OK" % (args.out, len(text) / 1024.0))

    if args.run:
        cmd = [AEDT, "-RunScriptAndExit", args.out]
        print("运行：%s" % " ".join(cmd))
        rc = subprocess.call(cmd)
        print("ansysedt rc=%d" % rc)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
