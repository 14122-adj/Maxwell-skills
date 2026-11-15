# -*- coding: utf-8 -*-
"""G7 斜槽 —— 真机 3 切片 FEA 复核（对 `skew_multislice.py` 的独立验证）。

为什么需要这一步
----------------
`skew_multislice.py` 是**后处理**：把同一条 401 点波形按 Δ_j 平移再平均。
它成立的前提是「切片 j 的场 = 基线场在转子角上加 Δ_j」，这是个假设，不是证据。
本文件用**真机**把假设变成可测量的东西：同一份模板只改 `AssignBand` 的
`Init Pos`（机械 deg），跑 N 个独立 401 点空载工程，再对转矩/磁链逐点平均。
两条路子若一致（≲2%），后处理的斜槽结论才算有证据。

口径（必须与基线一致，否则比的是两个不同的东西）
------------------------------------------------
* 窗口：末个电周期 10–20 ms，200 点，不含重复端点；
* 单位：`Time [ms]` / `Torque [mNewtonMeter]` 按表头换算；
* 转矩：3 片直接平均（每片用的是**同一相位**的指令电流，没有换相重标定）
  ⇒ 对应 `skew_multislice` 的 `T_avg_no_realign_nm`，不是 `T_avg_nm`。
  这一条最容易被误读：斜槽后驱动器若沿用旧换相角，会额外损失 cos(γ_e/2)。

用法
----
    python skew_slice_check.py --tags s025,s075,s125 --skew-slot 0.5
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import skew_multislice as SM  # noqa: E402

RESULTS = os.path.normpath(os.path.join(HERE, "..", "results"))
FEA = os.path.join(RESULTS, "fea")
RUNDIR = r"D:/ANSYS_Run"

TOL_COGGING_NM = 0.02      # 绝对容差（齿槽已降到 ~1e-3 量级，相对误差没意义）
TOL_THD_PT = 0.5
TOL_BEMF_PCT = 2.0
TOL_K1_PCT = 1.0           # 基波降额比（= 转矩降额比）


ARCHIVE = os.path.join(FEA, "skew_slices")


def slice_files(tag: str) -> dict:
    """优先读仓库内归档（可离线复算），回退到 AEDT 运行目录（首次跑）。"""
    d = ARCHIVE if os.path.exists(os.path.join(ARCHIVE, "tq_%s.csv" % tag))         else os.path.join(RUNDIR, "csv_tpl_%s" % tag)
    return {
        "tq": os.path.join(d, "tq_%s.csv" % tag),
        "flux": {ph: os.path.join(d, "flux_%s_%s.csv" % (tag, ph)) for ph in ("a", "b", "c")},
        "dir": d,
    }


def last_period(t, y, period: float = SM.T_ELEC):
    """末个电周期内、不含重复端点的等间隔样本。"""
    t0 = t[-1] - period
    idx = [i for i in range(len(t)) if t[i] >= t0 - period * 1e-6]
    n = len(idx) - 1 if abs(t[idx[-1]] - (t[idx[0]] + period)) < period * 1e-6 else len(idx)
    return [t[i] for i in idx[:n]], [y[i] for i in idx[:n]]


def average_waves(waves):
    n = min(len(w) for w in waves)
    return [sum(w[i] for w in waves) / len(waves) for i in range(n)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tags", default="s025,s075,s125",
                    help="切片标签（`csv_tpl_<tag>/`），默认 0.5 槽距的 3 个中点切片")
    ap.add_argument("--skew-slot", type=float, default=0.5)
    ap.add_argument("--json", default=os.path.join(FEA, "skew_slice_check.json"))
    args = ap.parse_args(argv)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    per_slice, tqs, fluxes = {}, [], {"a": [], "b": [], "c": []}
    tref = None
    for tag in tags:
        f = slice_files(tag)
        if not os.path.exists(f["tq"]):
            print("!! 缺 %s（该切片未求解完成？）" % f["tq"])
            return 2
        t, tq = SM.read_two_col(f["tq"])
        tt, yy = last_period(t, tq)
        if tref is None:
            tref = tt
        if len(tt) != len(tref) or abs(tt[0] - tref[0]) > 1e-9:
            print("!! 切片 %s 时间轴与首片不一致（%d vs %d 点）" % (tag, len(tt), len(tref)))
            return 2
        tqs.append(yy)
        per_slice[tag] = {
            "cogging_pp_nm": round(max(yy) - min(yy), 5),
            "T_mean_nm": round(SM.mean(yy), 5),
            "rows": len(yy),
        }
        for ph in ("a", "b", "c"):
            ft, fl = SM.read_two_col(f["flux"][ph])
            _, lam = last_period(ft, fl)
            fluxes[ph].append(lam)
        print("slice %-5s  齿槽 %.5f N·m  <%d 点>" % (tag, max(yy) - min(yy), len(yy)))

    # ── 3 片平均 ──
    tq_avg = average_waves(tqs)
    cog_pp = max(tq_avg) - min(tq_avg)
    t_mean = SM.mean(tq_avg)

    emf = {}
    for ph in ("a", "b", "c"):
        lam_avg = average_waves(fluxes[ph])
        emf[ph] = [-v for v in SM.differentiate(tref, lam_avg)]
    u = [x - y for x, y in zip(emf["a"], emf["b"])]
    amps = SM.spectrum(tref, u, SM.F_ELEC, 15)
    bemf_rms = SM.rms(emf["a"])
    thd = SM.thd_from_amps(amps)

    # 切片差异（证明 Init Pos 真的生效：3 片若逐点相同说明参数没进模型）
    spread = max(max(abs(w[i] - tqs[0][i]) for i in range(len(tq_avg)))
                 for w in tqs[1:])

    fea = {
        "tags": tags,
        "n_slices": len(tags),
        "per_slice": per_slice,
        "slice_spread_nm": round(spread, 5),
        "slice_rotation_effective": bool(spread > 1e-3),
        "cogging_pp_nm": round(cog_pp, 5),
        "cogging_pct": round(100.0 * cog_pp / SM.T_RATED, 4),
        "T_mean_of_slices_nm": round(t_mean, 5),
        "bemf_phase_rms_v": round(bemf_rms, 4),
        "bemf_line_rms_v": round(SM.rms(u), 4),
        "thd_line_pct": round(thd, 4),
    }

    post = SM.evaluate(SM.NOLOAD_DIR, SM.LOAD_DIR, args.skew_slot, 200, len(tags))

    # 基波降额比 k1 —— 斜槽的**代价**侧。T ∝ E_1（同一电流），故转矩降额比 = k1。
    # 用两边的「相对基线」比值比，消除基波绝对幅值的口径差。
    base_sig = SM.phase_flux(SM.NOLOAD_DIR, "a")
    base_sig = (base_sig[0], base_sig[1])
    base_e = [-v for v in SM.differentiate(base_sig[0], base_sig[1])]
    base_b = SM.phase_flux(SM.NOLOAD_DIR, "b")
    base_eb = [-v for v in SM.differentiate(base_b[0], base_b[1])]
    base_u = [x - y for x, y in zip(base_e, base_eb)]
    idx = [i for i in range(len(base_sig[0]))
           if base_sig[0][i] >= base_sig[0][-1] - SM.T_ELEC - 1e-12][:200]
    a1_base = SM.harmonic_amp([base_sig[0][i] for i in idx], [base_u[i] for i in idx],
                              SM.F_ELEC)
    a1_fea = SM.harmonic_amp(tref, u, SM.F_ELEC)
    k1_fea = a1_fea / a1_base
    post_amps = post.get("harmonics_v") or []
    k1_post = (post_amps[0] / a1_base) if post_amps else None

    cmp_ = {
        "cogging_pp_nm": {"fea": round(cog_pp, 5), "post": post.get("cogging_pp_nm"),
                          "gap": round(abs(cog_pp - post.get("cogging_pp_nm", 0)), 5),
                          "tol": TOL_COGGING_NM},
        "bemf_phase_rms_v": {"fea": round(bemf_rms, 4), "post": post.get("bemf_phase_rms_v"),
                             "gap_pct": round(100.0 * (bemf_rms - post["bemf_phase_rms_v"])
                                              / post["bemf_phase_rms_v"], 4),
                             "tol_pct": TOL_BEMF_PCT},
        "thd_line_pct": {"fea": round(thd, 4), "post": post.get("thd_line_pct"),
                         "gap_pt": round(thd - post["thd_line_pct"], 4),
                         "tol_pt": TOL_THD_PT},
        "k1_fundamental_ratio": {
            "fea": round(k1_fea, 5), "post": round(k1_post, 5) if k1_post else None,
            "gap_pct": round(100.0 * (k1_fea - k1_post) / k1_post, 4) if k1_post else None,
            "tol_pct": TOL_K1_PCT,
            "note": "T ∝ E1（同一电流）⇒ 该比值即转矩降额比；斜槽代价由此侧给出",
        },
        "not_covered": {
            "load_torque_3slice_fea": "未做：3 片都是空载工程，负载侧需另跑 3×726 s；"
                                      "T_avg 斜槽降额由「时域合成 + k_sk(1)」两法互证，未过真机",
            "continuous_vs_3slice": "3 片是连续斜槽的离散近似：连续极限齿槽→0、THD→2.00%%，"
                                    "3 片分别 0.233 N·m / 2.47%%；两者都正确，别混用",
        },
    }
    ok = (cmp_["cogging_pp_nm"]["gap"] <= TOL_COGGING_NM
          and abs(cmp_["bemf_phase_rms_v"]["gap_pct"]) <= TOL_BEMF_PCT
          and abs(cmp_["thd_line_pct"]["gap_pt"]) <= TOL_THD_PT
          and (cmp_["k1_fundamental_ratio"]["gap_pct"] is None
               or abs(cmp_["k1_fundamental_ratio"]["gap_pct"]) <= TOL_K1_PCT))

    payload = {
        "stage": "G7 skew — real-FEA 3-slice verification",
        "skew_slot_pitch": args.skew_slot,
        "method": "three independent 401-point noload runs with AssignBand Init Pos offset",
        "fea": fea,
        "postprocess": {k: post.get(k) for k in
                        ("skew_mech_deg", "skew_elec_deg", "cogging_pp_nm", "bemf_phase_rms_v",
                         "thd_line_pct", "T_avg_nm", "T_avg_no_realign_nm", "T_ripple_pct")},
        "compare": cmp_,
        "pass": bool(ok),
    }
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print("\n3 片平均：齿槽 %.5f N·m (%.3f%%)  BEMF %.4f V  THD %.4f%%  <T> %.4f N·m"
          % (cog_pp, 100 * cog_pp / SM.T_RATED, bemf_rms, thd, t_mean))
    print("后处理  ：齿槽 %.5f N·m  BEMF %.4f V  THD %.4f%%  <T>_no_realign %.4f / realign %.4f"
          % (post.get("cogging_pp_nm"), post.get("bemf_phase_rms_v"),
             post.get("thd_line_pct"), post.get("T_avg_no_realign_nm"),
             post.get("T_avg_nm")))
    print("切片旋转生效：%s（切片间最大逐点差 %.5f N·m）"
          % (fea["slice_rotation_effective"], spread))
    print("判定：%s" % ("PASS" if ok else "FAIL"))
    print("写出 " + args.json)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
