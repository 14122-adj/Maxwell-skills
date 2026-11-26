#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M4 起动曲线后处理 + 出图

只读 `D:/ANSYS_Run/csv_ipm_m4_<case>/` 下的原始 CSV，不重算、不插值、不改判据。
单位从 CSV 表头读（I22 陷阱：Moving1.Torque 可能是 µN·m/mN·m，按 N·m 读会放大 1000×），
表头没写单位才按 NewtonMeter 兜底并标注。

用法
----
    python ipm_m4_plot.py                      # 出图 + 打印摘要
    python ipm_m4_plot.py --case start --png out.png
"""
from __future__ import annotations

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")
RUN_DIR = r"D:/ANSYS_Run"

# 转矩单位的换算因子（I22）
_TORQUE_SCALE = {
    "newtonmeter": 1.0, "nm": 1.0, "n*m": 1.0,
    "millinewtonmeter": 1e-3, "mnewtonmeter": 1e-3, "mnm": 1e-3,
    "micronewtonmeter": 1e-6, "unewtonmeter": 1e-6, "unm": 1e-6,
}


def _pick_font() -> str:
    """选一个本机存在的中文字体，避免图上中文变方框。"""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "SimSun", "DejaVu Sans"):
        if name in installed:
            return name
    return "DejaVu Sans"


def read_csv(path: str):
    """读 Maxwell 两列 CSV → (unit, [(t, v), ...])。表头可能是 'Time [ms]' 这种带单位。"""
    rows, unit, t_unit = [], "", "s"
    if not os.path.exists(path):
        return None, rows, t_unit
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            s = ln.strip()
            if not s:
                continue
            parts = [p.strip().strip('"') for p in s.split(",")]
            if len(parts) < 2:
                continue
            try:
                t, v = float(parts[0]), float(parts[1])
            except ValueError:
                # 表头行：顺便抓单位
                if "[" in s and "]" in s:
                    segs = s.split(",")
                    if len(segs) >= 2:
                        h = segs[1]
                        if "[" in h and "]" in h:
                            unit = h[h.index("[") + 1:h.rindex("]")].strip()
                        if "[" in segs[0]:
                            t_unit = segs[0][segs[0].index("[") + 1:segs[0].rindex("]")].strip()
                continue
            rows.append((t, v))
    return (unit or None), rows, t_unit


def summarize(rows, scale: float = 1.0) -> dict:
    if len(rows) < 5:
        return {"status": "NO_DATA", "n": len(rows)}
    ts = [t for t, _v in rows]
    ys = [v * scale for _t, v in rows]
    tail = ys[int(len(ys) * 0.8):]
    y_ss = sum(tail) / len(tail)
    y_max, y_min = max(ys), min(ys)
    band = abs(y_ss) * 0.05 + 1e-9
    t_set = None
    for i in range(len(ys)):
        if all(abs(v - y_ss) <= band for v in ys[i:]):
            t_set = ts[i]
            break
    return {"status": "OK", "n": len(rows), "t_span": [ts[0], ts[-1]],
            "y_start": ys[0], "y_peak": y_max, "t_peak": ts[ys.index(y_max)],
            "y_min": y_min, "y_ss": y_ss, "t_settle": t_set}


def _mode_label(case: str) -> str:
    """从 summary JSON 推断口径标签：转速恒定 → 稳态；转速变化 → 机械瞬态起动。"""
    p = os.path.join(RESULTS, "m4_start_summary_%s.json" % case)
    try:
        d = json.load(open(p, encoding="utf-8"))
        sp = d.get("speed") or {}
        lo, hi = sp.get("y_min"), sp.get("y_peak")
        if lo is not None and hi is not None and abs(hi - lo) < 1e-6:
            return "恒转速稳态 + 电流软启动"
        return "机械瞬态起动"
    except Exception:
        return "转矩曲线"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M4 起动曲线后处理")
    ap.add_argument("--case", default="start")
    ap.add_argument("--csvdir", default=None,
                    help="CSV 目录（默认 D:/ANSYS_Run/csv_ipm_m4_<case>）")
    ap.add_argument("--png", default=None)
    ap.add_argument("--topology", default="IPM 8p48s",
                    help="图标题前缀（默认 IPM 8p48s；SPM 用 'SPM 8p48s 贴片平行充磁'）")
    ap.add_argument("--no-plot", action="store_true")
    args = ap.parse_args(argv)

    csvdir = args.csvdir or os.path.join(RUN_DIR, "csv_ipm_m4_" + args.case)
    tq_unit, tq_rows, t_unit = read_csv(os.path.join(csvdir, "tq_start.csv"))
    sp_unit, sp_rows, _ = read_csv(os.path.join(csvdir, "speed.csv"))

    if not tq_rows:
        print("没有转矩数据：%s/tq_start.csv" % csvdir)
        return 2

    tscale = 1e-3 if t_unit.lower().startswith("ms") else 1.0
    tq_scale = _TORQUE_SCALE.get((tq_unit or "NewtonMeter").replace(" ", "").lower(), 1.0)
    sp_scale = 1.0

    st_tq = summarize(tq_rows, tq_scale)
    st_sp = summarize(sp_rows, sp_scale) if sp_rows else {"status": "NO_DATA"}

    print("=== 转矩 ===")
    print("  CSV 单位: %s（换算 ×%g）；时间单位: %s" % (tq_unit or "隐含 NewtonMeter", tq_scale, t_unit))
    print("  点数 %d，t = %.3f … %.3f ms" % (st_tq["n"], st_tq["t_span"][0] * tscale * 1e3,
                                          st_tq["t_span"][1] * tscale * 1e3))
    print("  t=0   : %8.3f N·m   ← 起动前的第一点" % st_tq["y_start"])
    print("  峰值  : %8.3f N·m @ %.1f ms" % (st_tq["y_peak"], st_tq["t_peak"] * tscale * 1e3))
    print("  谷值  : %8.3f N·m" % st_tq["y_min"])
    print("  末段稳: %8.3f N·m（后 20%% 均值）" % st_tq["y_ss"])
    if st_tq["t_settle"] is not None:
        print("  起转稳: %8.1f ms（首次进入 95%% 稳态带并保持）" % (st_tq["t_settle"] * tscale * 1e3))
    if st_sp["status"] == "OK":
        print("=== 转速 ===")
        print("  t=0   : %8.1f rpm" % st_sp["y_start"])
        print("  峰值  : %8.1f rpm @ %.1f ms" % (st_sp["y_peak"], st_sp["t_peak"] * tscale * 1e3))
        print("  末段稳: %8.1f rpm（同步速 1500）" % st_sp["y_ss"])

    if not args.no_plot:
        font = _pick_font()
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True,
                                       gridspec_kw={"height_ratios": [1.35, 1]})
        T = [t * tscale * 1e3 for t, _v in tq_rows]
        Y = [v * tq_scale for _t, v in tq_rows]
        ax1.plot(T, Y, color="#c0392b", lw=1.1)
        ax1.axhline(0, color="#888", lw=0.6, ls=":")
        ax1.axhline(st_tq["y_ss"], color="#2c3e50", lw=0.9, ls="--",
                    label="末段稳态 %.2f N·m" % st_tq["y_ss"])
        ax1.plot([0], [st_tq["y_start"]], "o", ms=5, color="#c0392b")
        ax1.annotate("t=0: %.2f N·m" % st_tq["y_start"], (0, st_tq["y_start"]),
                     textcoords="offset points", xytext=(12, 14), fontsize=9, color="#c0392b")
        ax1.set_ylabel("转矩 (N·m)")
        ax1.set_title("%s — %s（%d 点）" %
                      (args.topology, _mode_label(args.case), st_tq["n"]), fontsize=11)
        ax1.grid(alpha=0.25, lw=0.5)
        ax1.legend(loc="lower right", fontsize=9, frameon=False)

        if sp_rows:
            Ts = [t * tscale * 1e3 for t, _v in sp_rows]
            Ys = [v * sp_scale for _t, v in sp_rows]
            ax2.plot(Ts, Ys, color="#2980b9", lw=1.3)
            ax2.axhline(1500, color="#888", lw=0.8, ls="--", label="同步速 1500 rpm")
            ax2.set_ylabel("转速 (rpm)")
            ax2.set_xlabel("时间 (ms)")
            ax2.grid(alpha=0.25, lw=0.5)
            ax2.legend(loc="lower right", fontsize=9, frameon=False)
        else:
            ax2.text(0.5, 0.5, "转速数据缺失", ha="center", va="center",
                     transform=ax2.transAxes)
        fig.tight_layout()
        png = args.png or os.path.join(RESULTS, "m4_start_curve_%s.png" % args.case)
        os.makedirs(os.path.dirname(png), exist_ok=True)
        fig.savefig(png, dpi=150)
        print("图：%s" % png)

    out = dict(case=args.case, torque_unit=tq_unit, torque_scale=tq_scale,
               speed_unit=sp_unit, time_unit=t_unit,
               torque=st_tq, speed=st_sp, csvdir=csvdir)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "m4_start_summary_%s.json" % args.case), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("摘要：%s" % os.path.join(RESULTS, "m4_start_summary_%s.json" % args.case))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
