#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 贴片 8p48s D5 斜槽 0.75 —— 3 切片 401 点 FEA + 同判据平均（KEEP，2026-11-27）

背景（I34 精调第 3 点）
-----------------------
t_pm=0.45 / 极弧 0.90 命中 T_avg=24.9991 N·m（25.0±0.5），但峰峰
10.1304% 破 10% 硬约束（超 0.1304 pt）；极弧 0.92 反使峰峰恶化到 10.8601%。
FFT 定阶次为 h=24 槽谐波族主导。按 I34 约束走斜槽 0.75 —— IPM 已证
（14.08%→3.29%）且多切片平均不降直流转矩。

口径（完全复用 ipm_skew_slices.py，已真机验证）
------------------------------------------------
* 3 片机械角 [-γ/2, 0, +γ/2]，γ = 0.75 × 7.5° = 5.625°，半角 2.8125°；
* 每片转子几何 + 平行充磁矢量同步转 Δ_mech（spm_build.spm_magnets 用
  cfg.rotor_init_deg，0° 逐位复现基线，有护栏测试）；
* 每片电流相位补 Δ_elec = Δ_mech × 极对数 4，保证每片同一功率因数点；
* 逐点平均 3 片 401 点波形 → 走 ipm_m3_check 同一判据（check_wave）。

用法
----
    python spm_skew_slices.py --core-od 90.75 --pole-arc 0.90 --imax 13.856 \
        --skew 0.75 --case spm_t045_skew075 --run
    python spm_skew_slices.py --case spm_t045_skew075 --post   # 只后处理
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import replace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _p in (_HERE, os.path.join(_ROOT, "projects", "25Nm_PMSM")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ipm_m3_check  # noqa: E402
import ipm_m3_load  # noqa: E402
import ipm_skew_slices  # noqa: E402
import spm_build  # noqa: E402

AEDT = spm_build.AEDT
RUN_DIR = spm_build.RUN_DIR
RESULTS = ipm_m3_load.RESULTS
N_SLICES = ipm_skew_slices.N_SLICES
F_ELEC = ipm_m3_load.F_ELEC
POLE_PAIRS = 4


def gen_slice(cfg_base, angle_deg: float, idx: int, currents: dict, case: str) -> dict:
    """生成单片建模+求解脚本（不跑）。转子几何与充磁矢量同步转 angle_deg。"""
    cfg = replace(cfg_base, rotor_init_deg=angle_deg)
    aedt_out = "%s/SPM_8p48s_M3_%s_s%d.aedt" % (RUN_DIR, case, idx)
    build_py = "%s/spm_m3_build_%s_s%d.py" % (RUN_DIR, case, idx)
    solve_py = "%s/spm_m3_solve_%s_s%d.py" % (RUN_DIR, case, idx)
    build_log = "%s/spm_m3_build_%s_s%d.log" % (RUN_DIR, case, idx)
    solve_log = "%s/spm_m3_solve_%s_s%d.log" % (RUN_DIR, case, idx)
    csvdir = "%s/csv_spm_m3_%s_s%d" % (RUN_DIR, case, idx)
    text = spm_build.build_script(cfg, aedt_out, currents=currents,
                                  case_tag="M3_SPM_%s_s%d" % (case, idx),
                                  log_path=build_log)
    compile(text, build_py, "exec")
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(text)
    solve_text = ipm_m3_load.build_solve_script(aedt_out, csvdir, solve_log, build_py)
    compile(solve_text, solve_py, "exec")
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    snap = spm_build.spm_snapshot(cfg)
    return dict(idx=idx, angle_deg=angle_deg, build_py=build_py, solve_py=solve_py,
                aedt=aedt_out, csvdir=csvdir, core_od=cfg.spm_core_od,
                pole_arc=cfg.pm_pole_arc, pm_t=snap["pm_t"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core-od", type=float, default=90.75)
    ap.add_argument("--pole-arc", type=float, default=0.90)
    ap.add_argument("--imax", type=float, default=13.856)
    ap.add_argument("--phi-rel", type=float, default=0.0)
    ap.add_argument("--skew", type=float, default=0.75)
    ap.add_argument("--case", default="spm_t045_skew075")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args(argv)

    cfg = replace(spm_build.SPMConfig(), spm_core_od=args.core_od,
                  pm_pole_arc=args.pole_arc)
    snap = spm_build.spm_snapshot(cfg)
    angles = ipm_skew_slices.slice_angles(args.skew)
    base_abs = ipm_m3_load.BEMF_OFFSET_DEG + args.phi_rel
    slices = []
    for i, ang in enumerate(angles):
        phi_abs = base_abs + ang * POLE_PAIRS
        currents = ipm_m3_load.compute_currents(args.imax, phi_abs, -1)
        slices.append(gen_slice(cfg, ang, i, currents, args.case))

    print("SPM 斜槽 %s：t_pm=%.3f 极弧=%.2f Imax=%.3f 机械角=%s" %
          (args.skew, snap["pm_t"], args.pole_arc, args.imax, angles))
    for s in slices:
        print("  slice%d %+7.4f° build=%s" % (s["idx"], s["angle_deg"], s["build_py"]))

    if args.run:
        for sl in slices:
            for key, label in (("build_py", "build"), ("solve_py", "solve")):
                rc = subprocess.call([AEDT, "-RunScriptAndExit", sl[key]])
                print("slice%d %s rc=%d" % (sl["idx"], label, rc))
                if rc != 0:
                    return rc

    if args.run or args.post:
        waves = []
        for s in slices:
            _t, y, _u, _sc, _n = ipm_m3_check.load_torque(s["csvdir"])
            assert len(y) == 401, (s["idx"], len(y))
            waves.append(y)
        wave = [sum(w[i] for w in waves) / N_SLICES for i in range(401)]
        verdict = ipm_skew_slices.check_wave(wave)
        out = dict(case=args.case, topology="SPM_8p48s_surface_pm_parallel_mag",
                   skew_slot=args.skew, rotor_init_deg_mech=angles,
                   gamma_elec_deg=args.skew * 360.0 / 48.0 * POLE_PAIRS,
                   core_od=args.core_od, pole_arc=args.pole_arc, pm_t=snap["pm_t"],
                   imax=args.imax, phi_rel_deg=args.phi_rel,
                   slices=[dict(idx=s["idx"], angle_deg=s["angle_deg"],
                                csvdir=s["csvdir"], aedt=s["aedt"]) for s in slices],
                   method="3-slice FEA, phase-compensated pointwise average",
                   torque=verdict)
        path = os.path.join(RESULTS, "spm_m3_skew_%s.json" % args.case)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("=" * 70)
        for c in verdict["checks"]:
            print("  [%s] %-24s %s" % (c["status"], c["name"], c["value"]))
        print("  T_avg=%.4f pp=%.4f (%.4f%%) h=%d %.4f%%" %
              (verdict["t_avg_nm"], verdict["pp_nm"], verdict["pp_pct"],
               verdict["main_harmonic_order"], verdict["main_harmonic_pct"]))
        print("  ✔ %s" % path)
        return 0 if verdict["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
