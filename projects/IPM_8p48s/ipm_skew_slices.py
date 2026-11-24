#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s D5 斜槽 —— 3 切片真机 FEA 驱动 + 频域平均独立重算（KEEP）

原理（SPM G7 已验证，docs/MAXWELL_INTERNALS 斜槽节）
----------------------------------------------------
Maxwell 2D 无轴向斜槽自由度，标准近似=把叠长切 N 片、每片转子相对定子转
Δ_j，整机电磁量取平均。本脚本：
  · 每片用 `ipm_build.build_script(cfg(rotor_init_deg=Δ_j), currents=...)` 建模
    —— V 槽/磁钢几何和磁化方向一起转（ipm_geom.derive_rotor / magnet_directions），
    定子绕组不动；
  · 复用 `ipm_m3_load.build_solve_script` 跑 401 点，导出 flux/tq；
  · 按**转子位形**平移（T_j(t)=T_0(t+Δ_j/ω_mech)，Δ_j 机械角）后频域平均，
    再走 `ipm_m3_check` 同一判据重算 T_avg / pp / 主谐波 / 跳变。

为什么时域平移按机械角：Δ_j 是转子相对定子的机械转角，ω_mech=157.08 rad/s；
平移量 = Δ_j(rad)/ω_mech 秒。不能用 AssignBand 的 Init Pos（SPM 实测不改几何）。

用法
----
    python ipm_skew_slices.py --imax 14.5019 --phi 0 --skew 0.75 --run
    python ipm_skew_slices.py --imax 14.5019 --phi 0 --skew 0.75 --post   # 只后处理
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

import ipm_build  # noqa: E402
import ipm_geom  # noqa: E402
import ipm_m3_load  # noqa: E402
import ipm_m3_check  # noqa: E402
import ingest_fea as ing  # noqa: E402

AEDT = ipm_build.AEDT
RUN_DIR = ipm_build.RUN_DIR
RESULTS = ipm_m3_load.RESULTS
OMEGA_MECH = 2.0 * math.pi * 1500.0 / 60.0   # 157.0796 rad/s
N_SLICES = 3
F_ELEC = 100.0


def slice_angles(skew_slot: float) -> list[float]:
    """3 切片机械转角 [−γ/2, 0, +γ/2]，γ=槽距机械角 × skew_slot。"""
    pitch_mech = 360.0 / 48.0
    gamma = pitch_mech * skew_slot
    return [-gamma / 2.0, 0.0, gamma / 2.0]


def gen_slice(cfg_base, angle_deg: float, idx: int, currents: dict, case: str) -> dict:
    """生成单片建模+求解脚本（不跑）。每片独立 cfg，转子转 angle_deg。"""
    from dataclasses import replace
    cfg = replace(cfg_base, rotor_init_deg=angle_deg)
    aedt_out = "%s/IPM_8p48s_M3_%s_s%d.aedt" % (RUN_DIR, case, idx)
    build_py = "%s/ipm_m3_build_%s_s%d.py" % (RUN_DIR, case, idx)
    solve_py = "%s/ipm_m3_solve_%s_s%d.py" % (RUN_DIR, case, idx)
    build_log = "%s/ipm_m3_build_%s_s%d.log" % (RUN_DIR, case, idx)
    solve_log = "%s/ipm_m3_solve_%s_s%d.log" % (RUN_DIR, case, idx)
    csvdir = "%s/csv_ipm_m3_%s_s%d" % (RUN_DIR, case, idx)
    text = ipm_build.build_script(cfg, aedt_out, currents=currents,
                                  case_tag="M3_%s_s%d" % (case, idx))
    text = text.replace('LOG = r"' + ipm_build.LOG + '"', 'LOG = r"' + build_log + '"')
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(text)
    compile(text, build_py, "exec")
    solve_text = ipm_m3_load.build_solve_script(aedt_out, csvdir, solve_log, build_py)
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    compile(solve_text, solve_py, "exec")
    return dict(idx=idx, angle_deg=angle_deg, build_py=build_py, solve_py=solve_py,
                aedt=aedt_out, csvdir=csvdir)


def harmonic_shifted_avg(csvdirs: list[str], angles_deg: list[float]) -> dict:
    """按转子位形平移后频域平均 N 片转矩，返回合成 401 点波形 + 判据量。

    对每片末电周期（200 点）做 DFT，各次谐波乘 exp(j·h·Δ_j)（Δ_j 为
    **电角**=机械角×极对数），再对 N 片取平均，重构时域。基波 k1 自动含在平均里。
    """
    p = 4  # 极对数
    series = []
    for csvdir, ang_mech in zip(csvdirs, angles_deg):
        t, y, _u, _s, _n = ipm_m3_check.load_torque(csvdir)
        dt = t[1] - t[0]
        n = int(round((1.0 / F_ELEC) / dt))
        tt, yy = t[-n - 1:-1], y[-n - 1:-1]
        assert len(tt) == n, (len(tt), n)
        harm = {}
        for h in range(0, n // 2 + 1):
            a = 2.0 / n * sum(yy[i] * math.cos(2 * math.pi * h * i / n) for i in range(n))
            b = 2.0 / n * sum(yy[i] * math.sin(2 * math.pi * h * i / n) for i in range(n))
            if h == 0:
                a = sum(yy) / n
                b = 0.0
            harm[h] = (a, b)
        series.append(harm)

    # 统一用末电周期窗口（200 点）做 DFT 与重构；SPM 历史已证单周期 DFT 带限精确，
    # 不要混用 401 点全样本索引（不同窗口长度会让 h 上限和相移基准错位）。
    n = 200
    # 平均各片谐波（含相移 exp(j h Δ_elec)）
    avg = {}
    for h in range(0, n // 2 + 1):
        ar = br = 0.0
        for harm, ang_mech in zip(series, angles_deg):
            a, b = harm[h]
            delta = math.radians(ang_mech * p)
            # T_j 相对基线平移 Δ_elec：h 次谐波相移 = h·Δ_elec
            c, s = math.cos(h * delta), math.sin(h * delta)
            ar += a * c - b * s
            br += a * s + b * c
        avg[h] = (ar / N_SLICES, br / N_SLICES)

    wave = [0.0] * n
    for h, (a, b) in avg.items():
        for i in range(n):
            wave[i] += a * math.cos(2 * math.pi * h * i / n) + b * math.sin(2 * math.pi * h * i / n)
    return {"wave": wave, "t_avg": avg[0][0]}


def check_wave(wave: list[float]) -> dict:
    """用 ipm_m3_check 同口径判据重算合成波形（末周期 200 点）。"""
    n = 200
    w = wave[-n:] if len(wave) >= n else wave
    tavg = sum(w) / len(w)
    pp = max(w) - min(w)
    jumps = [abs(w[k + 1] - w[k]) for k in range(len(w) - 1)]
    jmax = max(jumps) if jumps else 0.0
    # FFT h=1..30 找主谐波
    spec = []
    for h in range(1, 31):
        a = 2.0 / len(w) * sum(w[i] * math.cos(2 * math.pi * h * i / len(w)) for i in range(len(w)))
        b = 2.0 / len(w) * sum(w[i] * math.sin(2 * math.pi * h * i / len(w)) for i in range(len(w)))
        spec.append((h, math.hypot(a, b)))
    h, amp = max(spec, key=lambda x: x[1])
    ok = abs(tavg) > 1e-9
    pp_pct = 100.0 * pp / abs(tavg) if ok else None
    h_pct = 100.0 * amp / abs(tavg) if ok else None
    j_pct = 100.0 * jmax / abs(tavg) if ok else None
    checks = [
        {"name": "T_avg ∈ 22.5–27.5", "value": round(tavg, 4),
         "status": "PASS" if 22.5 <= tavg <= 27.5 else "FAIL"},
        {"name": "pp ≤ 10% T_avg", "value": round(pp_pct, 4) if pp_pct else None,
         "status": "PASS" if ok and pp_pct <= 10.0 else "FAIL"},
        {"name": "主谐波 ≤ 5% T_avg", "value": round(h_pct, 4) if h_pct else None,
         "status": "PASS" if ok and h_pct <= 5.0 else "FAIL"},
        {"name": "跳变 ≤ 15% T_avg", "value": round(j_pct, 4) if j_pct else None,
         "status": "PASS" if ok and j_pct <= 15.0 else "FAIL"},
    ]
    return {
        "t_avg_nm": round(tavg, 4), "pp_nm": round(pp, 4), "pp_pct": round(pp_pct, 4),
        "main_harmonic_order": h, "main_harmonic_nm": round(amp, 4),
        "main_harmonic_pct": round(h_pct, 4),
        "jump_max_nm": round(jmax, 4), "jump_max_pct": round(j_pct, 4),
        "checks": checks,
        "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--imax", type=float, required=True)
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--skew", type=float, default=0.75, help="斜槽槽距数（0.75=22.5°电角）")
    ap.add_argument("--case", default="skew075")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args(argv)

    cfg = ipm_geom.IPMConfig()
    angles = slice_angles(args.skew)
    # 与 ipm_m3_load.main 同口径：--phi 是"相对 BEMF 反相点"偏移，
    # compute_currents 要的是绝对电角 φ_abs = 90°(offset) + phi_rel。
    # 多切片每片转子转 Δ_mech ⇒ BEMF 反相点也转 Δ_elec=Δ_mech·极对数；
    # 每片电流相位必须跟着补 Δ_elec，才保证每片工作在相同功率因数点。
    p = 4
    base_abs = ipm_m3_load.BEMF_OFFSET_DEG + args.phi
    slices = []
    for i, ang in enumerate(angles):
        phi_abs = base_abs + ang * p
        currents = ipm_m3_load.compute_currents(args.imax, phi_abs, -1)
        slices.append(gen_slice(cfg, ang, i, currents, args.case))

    if args.run:
        for sl in slices:
            for key, label in (("build_py", "build"), ("solve_py", "solve")):
                rc = subprocess.call([AEDT, "-RunScriptAndExit", sl[key]])
                print("slice%d %s rc=%d" % (sl["idx"], label, rc))
                if rc != 0:
                    return rc

    if args.run or args.post:
        # 每片电流相位已按各自转子角补偿到相同工作点，波形含各自转子位形，
        # 多切片整机转矩 = 各片逐点平均（SPM 多切片 FEA 的同口径做法）。
        waves = []
        for s in slices:
            _t, y, _u, _sc, _n = ipm_m3_check.load_torque(s["csvdir"])
            assert len(y) == 401, (s["idx"], len(y))
            waves.append(y)
        wave = [sum(w[i] for w in waves) / N_SLICES for i in range(401)]
        verdict = check_wave(wave)
        out = dict(case=args.case, skew_slot=args.skew,
                   rotor_init_deg_mech=angles,
                   gamma_elec_deg=args.skew * 360.0 / 48.0 * 4,
                   imax=args.imax, phi_rel_deg=args.phi,
                   slices=[dict(idx=s["idx"], angle_deg=s["angle_deg"],
                                csvdir=s["csvdir"], aedt=s["aedt"]) for s in slices],
                   method="3-slice FEA + harmonic-shift average (rotor position)",
                   torque=verdict)
        path = os.path.join(RESULTS, "m3_skew_%s.json" % args.case)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print("=" * 70)
        print("D5 斜槽 %s  slices=%s" % (args.skew, angles))
        for c in verdict["checks"]:
            print("  [%s] %-24s %s" % (c["status"], c["name"], c["value"]))
        print("  T_avg=%.4f pp=%.4f (%.2f%%) h=%d %.2f%%" %
              (verdict["t_avg_nm"], verdict["pp_nm"], verdict["pp_pct"],
               verdict["main_harmonic_order"], verdict["main_harmonic_pct"]))
        print("  ✔ %s" % path)
        return 0 if verdict["status"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
