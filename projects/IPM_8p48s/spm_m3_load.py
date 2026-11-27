#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 8p48s M3 负载 401 点驱动（KEEP，2026-11-26）

与 ipm_m3_load.py 同构，唯一差异是段1建模改用 spm_build.build_script（贴片转子）。
电流公式/相位口径/段2求解脚本完全复用 IPM（已真机验证），避免引入新变量：
    Imax 固定 13.856 A、φ_abs=90°、sign=-1、f=100Hz、401 点。
任务书硬约束：禁止按 BEMF 重推电流凑数（会污染 25 N·m 判据可比性）。

用法：
    python spm_m3_load.py --imax 13.856 --case t238
    python spm_m3_load.py --imax 13.856 --case t238 --run       # 生成并真机求解
    python spm_m3_load.py --core-od 88.57 --imax 13.856 --case t200   # 厚度单变量
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _p in (_HERE, os.path.join(_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ipm_m3_load  # noqa: E402
import spm_build  # noqa: E402

AEDT = ipm_m3_load.AEDT
RUN_DIR = ipm_m3_load.RUN_DIR
RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SPM 8p48s M3 负载 401 点驱动")
    ap.add_argument("--imax", type=float, default=13.856, help="峰值电流 A（默认 13.856，任务书固定）")
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--phi-abs", type=float, default=None)
    ap.add_argument("--sign", type=int, default=-1, choices=(-1, 1))
    ap.add_argument("--case", default="t238")
    ap.add_argument("--core-od", type=float, default=None,
                    help="转子铁芯 OD(mm)，默认 86.89（t_pm=2.38）；厚度单变量时改此值")
    ap.add_argument("--pole-arc", type=float, default=None,
                    help="极弧系数（默认 0.85）；S5 峰峰优化单变量 0.80/0.85/0.90")
    ap.add_argument("--cps", type=int, default=None,
                    help="每槽导体数（默认 10）；I35 加厚磁钢时降匝数 10→8 抑制 BEMF")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args(argv)

    phi_abs = args.phi_abs if args.phi_abs is not None else ipm_m3_load.BEMF_OFFSET_DEG + args.phi
    currents = ipm_m3_load.compute_currents(args.imax, phi_abs, args.sign)
    cfg = spm_build.SPMConfig()
    if args.core_od is not None:
        cfg.spm_core_od = args.core_od
    if args.pole_arc is not None:
        cfg.pm_pole_arc = args.pole_arc
    if args.cps is not None:
        cfg.conductors_per_slot = args.cps
    snap = spm_build.spm_snapshot(cfg)

    aedt_out = "%s/SPM_8p48s_M3_%s.aedt" % (RUN_DIR, args.case)
    build_py = "%s/spm_m3_build_%s.py" % (RUN_DIR, args.case)
    solve_py = "%s/spm_m3_solve_%s.py" % (RUN_DIR, args.case)
    csvdir = "%s/csv_spm_m3_%s" % (RUN_DIR, args.case)
    build_log = "%s/spm_m3_build_%s.log" % (RUN_DIR, args.case)
    solve_log = "%s/spm_m3_solve_%s.log" % (RUN_DIR, args.case)

    build_text = spm_build.build_script(
        cfg, aedt_out, currents=currents,
        case_tag="M3_SPM_" + args.case, log_path=build_log)
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(build_text)
    compile(build_text, build_py, "exec")

    solve_text = ipm_m3_load.build_solve_script(aedt_out, csvdir, solve_log, build_py)
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    compile(solve_text, solve_py, "exec")

    meta = dict(case=args.case, topology="SPM_8p48s_surface_pm_parallel_mag",
                excitation=dict(current_A=args.imax, current_unit="A_peak",
                                phase_deg=args.phi, phase_abs_deg=phi_abs,
                                bemf_offset_deg=ipm_m3_load.BEMF_OFFSET_DEG,
                                sign=args.sign, frequency_hz=ipm_m3_load.F_ELEC,
                                source="task_fixed_13.856A_no_bemf_refit"),
                geometry=dict(core_od=cfg.spm_core_od, pm_t_mm=round(snap["pm_t"], 4),
                              pole_arc=cfg.pm_pole_arc,
                              conductors_per_slot=cfg.conductors_per_slot,
                              turns_per_phase=cfg.poles * 2 * cfg.conductors_per_slot,
                              pm_outer_r=snap["pm_outer_r"], airgap=snap["airgap"],
                              band_r=snap["band_r"], polarity=snap["polarity"]),
                p_mech_w=ipm_m3_load.P_MECH, build_script=build_py,
                solve_script=solve_py, csvdir=csvdir,
                build_script_src="spm_build.build_script")
    os.makedirs(RESULTS, exist_ok=True)
    mpath = os.path.join(RESULTS, "spm_m3_load_%s.json" % args.case)
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    print("生成：build=%s solve=%s" % (build_py, solve_py))
    print("几何：core_od=%.3f pm_t=%.3f 气隙=%.4f 极性=%s" %
          (cfg.spm_core_od, snap["pm_t"], snap["airgap"], "".join(snap["polarity"])))
    print("激励：Imax=%.3f A φ_abs=%.1f° sign=%d f=%.1fHz（任务书固定，未按 BEMF 重推）" %
          (args.imax, phi_abs, args.sign, ipm_m3_load.F_ELEC))
    print("meta：%s" % mpath)

    if args.run:
        # 两段式：先建模（未求解工程），再求解
        for label, scr in (("BUILD", build_py), ("SOLVE", solve_py)):
            cmd = [AEDT, "-RunScriptAndExit", scr]
            print("%s 运行：%s" % (label, " ".join(cmd)))
            rc = subprocess.call(cmd)
            print("%s rc=%d" % (label, rc))
            if rc != 0:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
