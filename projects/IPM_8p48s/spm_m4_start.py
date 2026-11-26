#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM 8p48s M4 —— 转矩"从 0 升到 25 后稳定"曲线（KEEP，2026-11-26）

与 ipm_m4_start.py 的关系
-------------------------
完全复用其**稳态口径 + 电流软启动**正解（docs/DEMO_CASE_M4_TORQUE.md §3）：
    i(t) = −Imax · min(t/T_soft, 1) · sin(2π·100·t + φ_abs)
    T_soft=0.02 s, 恒转速 1500 rpm（Consider Mechanical Transient=False）
唯一替换：建模用 spm_build.build_script（贴片拓扑），几何取 SPM 最终设计点
t_pm=0.50 mm / 极弧 0.90 / Imax=13.856 A（与 M3 达标点逐字一致）。

三条已证否路线禁止重试（docs/DEMO_CASE_M4_TORQUE.md §2）：
① 固定 100Hz 开环机械瞬态（无阻尼绕组，转子起不来）；
② 位置反馈 Moving1.Position（不进电流表达式，55µN·m）；
③ 为压振荡改 J（0.0092 是解析值，非主因）。
本脚本只走稳态+软启动，不提供机械瞬态/开环路径。

时间口径：0.2 s / 0.5 ms = 401 点（约 16–18 分钟），禁止 0.5 s/1000 点与
其它 401 点工况串同一天（时间预算硬约束）。

用法：
    python spm_m4_start.py --case spm_steady --run
    python spm_m4_start.py --case spm_steady --run --stop 0.1s --dt 0.0005s   # 201 点快速
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

import ipm_m4_start  # noqa: E402
import ipm_m3_load  # noqa: E402
import spm_build  # noqa: E402

AEDT = ipm_m4_start.AEDT
RUN_DIR = ipm_m4_start.RUN_DIR
RESULTS = ipm_m4_start.RESULTS
F_ELEC = ipm_m4_start.F_ELEC


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SPM 8p48s M4 转矩从零起动曲线（稳态+软启动）")
    ap.add_argument("--imax", type=float, default=13.856, help="峰值电流 A（SPM 最终设计点固定）")
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--soft-start", type=float, default=0.02, dest="soft_start",
                    help="电流软启动时长 s（默认 0.02 = 20ms 电流环建立时间）")
    ap.add_argument("--stop", default="0.2s")
    ap.add_argument("--dt", default="0.0005s")
    ap.add_argument("--case", default="spm_steady")
    ap.add_argument("--core-od", type=float, default=90.65, help="转子铁芯 OD（t_pm=0.50）")
    ap.add_argument("--pole-arc", type=float, default=0.90)
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args(argv)

    phi_abs = ipm_m3_load.BEMF_OFFSET_DEG + args.phi
    currents = ipm_m4_start.compute_currents_fixed(
        args.imax, phi_abs, F_ELEC, t_soft=args.soft_start)

    cfg = spm_build.SPMConfig()
    cfg.spm_core_od = args.core_od
    cfg.pm_pole_arc = args.pole_arc
    snap = spm_build.spm_snapshot(cfg)

    aedt_out = "%s/SPM_8p48s_M4_%s.aedt" % (RUN_DIR, args.case)
    build_py = "%s/spm_m4_build_%s.py" % (RUN_DIR, args.case)
    solve_py = "%s/spm_m4_solve_%s.py" % (RUN_DIR, args.case)
    csvdir = "%s/csv_spm_m4_%s" % (RUN_DIR, args.case)
    build_log = "%s/spm_m4_build_%s.log" % (RUN_DIR, args.case)
    solve_log = "%s/spm_m4_solve_%s.log" % (RUN_DIR, args.case)

    # 段1：稳态建模（motion=None，转速钉死 1500rpm）；save_fields=None 省 IO
    build_text = spm_build.build_script(
        cfg, aedt_out, currents=currents, case_tag="M4_SPM_" + args.case,
        stop_time=args.stop, time_step=args.dt, log_path=build_log)
    # 覆盖 Mesh 与场保存：M4 只要转矩，SaveFieldsType=None（spm_build 默认 Every N Steps）
    build_text = build_text.replace(
        '"SaveFieldsType:=", "Every N Steps"', '"SaveFieldsType:=", "None"')
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(build_text)
    compile(build_text, build_py, "exec")

    # 段2：求解脚本完全复用 IPM（已真机验证导出转矩/转速/位置）
    solve_text = ipm_m4_start.build_solve_script(aedt_out, csvdir, solve_log)
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    compile(solve_text, solve_py, "exec")

    n_steps = int(round(ipm_m4_start._sec(args.stop) / ipm_m4_start._sec(args.dt)))
    meta = dict(case=args.case, stage="SPM M4 转矩从零起动（稳态+软启动）",
                topology="SPM_8p48s_surface_pm_parallel_mag",
                geometry=dict(core_od=cfg.spm_core_od, pole_arc=cfg.pm_pole_arc,
                              pm_t_mm=round(snap["pm_t"], 4), airgap=snap["airgap"],
                              polarity=snap["polarity"]),
                excitation=dict(current_A=args.imax, current_unit="A_peak",
                                phase_abs_deg=phi_abs, frequency_hz=F_ELEC,
                                current_sign=-1, soft_start_s=args.soft_start,
                                source="spm_final_design_fixed_13.856A",
                                expressions=currents,
                                mode="steady_soft_start",
                                note="恒转速1500rpm+固定100Hz+电流软启动 ⇒ 转矩0→25后保持"),
                motion=dict(consider_mechanical_transient=False,
                            note="稳态口径，转速钉死，不积分 J·dω/dt"),
                timing=dict(stop_time=args.stop, time_step=args.dt,
                            n_steps=n_steps, n_points=n_steps + 1,
                            save_fields_type="None"),
                build_script=build_py, solve_script=solve_py, aedt=aedt_out,
                csvdir=csvdir, generated=True, solved=False)
    os.makedirs(RESULTS, exist_ok=True)
    mpath = os.path.join(RESULTS, "spm_m4_start_%s.json" % args.case)
    with open(mpath, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    print("SPM M4 从零起动曲线（稳态+软启动）")
    print("  几何 : core_od=%.3f 极弧=%.2f t_pm=%.3f 气隙=%.4f 极性=%s" %
          (cfg.spm_core_od, cfg.pm_pole_arc, snap["pm_t"], snap["airgap"], "".join(snap["polarity"])))
    print("  电流 : Imax=%.3f A φ_abs=%.1f° f=%.1fHz T_soft=%.3fs" %
          (args.imax, phi_abs, F_ELEC, args.soft_start))
    print("  表达式: %s" % currents["A"])
    print("  机械 : 恒转速 1500rpm（稳态口径）")
    print("  时间 : %s / %s → %d 步 = %d 点" % (args.stop, args.dt, n_steps, n_steps + 1))
    print("  脚本 : %s / %s" % (build_py, solve_py))
    print("  meta : %s" % mpath)
    print("  语法自检：CPython compile OK")

    if args.run:
        for script, label in ((build_py, "BUILD"), (solve_py, "SOLVE")):
            cmd = [AEDT, "-RunScriptAndExit", script]
            print("%s 运行：%s" % (label, " ".join(cmd)))
            rc = subprocess.call(cmd)
            print("%s rc=%d" % (label, rc))
            if rc != 0:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
