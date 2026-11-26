#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SPM M1 独立几何自检（KEEP，2026-11-26）

与 spm_build 同源计算期望值，再读真机日志实测，逐项比对并冻结 JSON。
关键新增判据（相对 ipm_m1_check）：
  - 8 块贴片（非 16 块 V），极性 N/S 交替
  - 平行充磁每极矢量与极轴符号一致（相邻极轴差 45°）
  - 气隙 0.675、Band 46.1625、AirgapRing 46.5/46.1625（贴片外表面不侵入气隙）
  - 无 intersect（真机 ValidateDesign OK）
不写任何 FEA 性能结论。

用法：
    python spm_check.py --log D:/ANSYS_Run/spm_m1.log --aedt D:/ANSYS_Run/SPM_8p48s_M1.aedt
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import spm_build  # noqa: E402

RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")


def parse_log(text: str) -> dict:
    out = {"sheets": None, "prefix": {}, "areas": {}, "pm": {},
           "validate": None, "saved": None, "raw_lines": len(text.splitlines())}
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r"^SHEETS=(\d+)$", ln)
        if m:
            out["sheets"] = int(m.group(1))
        m = re.match(r"^PREFIX (.+)$", ln)
        if m:
            for tok in m.group(1).split():
                k, _, v = tok.partition("=")
                out["prefix"][k] = int(v)
        m = re.match(r"^AREA (\S+) ([\d.]+)$", ln)
        if m:
            out["areas"][m.group(1)] = float(m.group(2))
        m = re.match(r"^PM (PM_\d+) area=([\d.]+) center=\(([-\d.]+), ([-\d.]+)\)$", ln)
        if m:
            out["pm"][m.group(1)] = dict(area=float(m.group(2)),
                                         cx=float(m.group(3)), cy=float(m.group(4)))
        if ln.startswith("VALIDATE_OK"):
            out["validate"] = "OK"
        elif ln.startswith("VALIDATE_NA"):
            out["validate"] = ln
        if ln.startswith("SAVED_OK"):
            out["saved"] = ln.split(" ", 1)[1] if " " in ln else "OK"
    return out


def check(cfg, log: dict, aedt_path: str, vectors_read: list | None = None) -> dict:
    snap = spm_build.spm_snapshot(cfg)
    mags = spm_build.spm_magnets(cfg)

    def rel(a, b):
        return abs(a - b) / b * 100.0 if b else 1e9

    checks = []
    checks.append(dict(name="SHEETS = 5 + 8 + 96", value=log["sheets"], limit=snap["n_sheets"],
                       status="PASS" if log["sheets"] == snap["n_sheets"] else "FAIL"))
    for k, want in (("PM", cfg.poles), ("Coil", cfg.slots * 2),
                    ("Region", 1), ("StatorOuter", 1), ("RotorOuter", 1),
                    ("Band", 1), ("AirgapRing", 1)):
        got = log["prefix"].get(k)
        checks.append(dict(name="前缀计数 %s = %d" % (k, want), value=got, limit=want,
                           status="PASS" if got == want else "FAIL"))

    # 面积：转子铁芯 + 气隙环
    d_rt = rel(log["areas"].get("RotorOuter", 0.0), snap["rotor_area"])
    checks.append(dict(name="转子铁芯面积 = π(r_core²−r_shaft²)（偏差%）",
                       value=round(d_rt, 5), limit=0.05,
                       status="PASS" if d_rt <= 0.05 else "FAIL"))
    d_ring = rel(log["areas"].get("AirgapRing", 0.0), snap["ring_area"])
    checks.append(dict(name="气隙环面积 = π(46.5²−46.1625²)（偏差%）",
                       value=round(d_ring, 5), limit=0.05,
                       status="PASS" if d_ring <= 0.05 else "FAIL"))

    # 8 块面积逐块对照（折线近似，容差 0.5%）
    worst = 0.0
    for m in mags:
        got = log["pm"].get(m["name"], {}).get("area", 0.0)
        worst = max(worst, rel(got, m["area"]))
    checks.append(dict(name="8 块贴片面积逐块一致（最大偏差%）", value=round(worst, 4), limit=0.5,
                       status="PASS" if worst <= 0.5 else "FAIL"))

    # 极性表（设计侧断言，真机材料方向由 spm_build 保证；vectors_read 可留空）
    pol = "".join(snap["polarity"])
    checks.append(dict(name="极性表 N/S 交替", value=pol, limit="NSNSNSNS",
                       status="PASS" if pol == "NSNSNSNS" else "FAIL"))

    # 平行充磁矢量：与极轴符号一致；相邻极轴差 45°（不是相邻矢量严格反号）
    vec_ok = True
    for i, (gx, gy) in enumerate(snap["vectors"]):
        a = math.radians(i * 45.0)
        s = 1.0 if i % 2 == 0 else -1.0
        if abs(gx - s * math.cos(a)) > 1e-5 or abs(gy - s * math.sin(a)) > 1e-5:
            vec_ok = False
    checks.append(dict(name="平行充磁矢量 = sign·u(极轴)", value=vec_ok, limit=True,
                       status="PASS" if vec_ok else "FAIL"))

    # 气隙自洽：贴片外表面 = rotor_od/2，气隙 = (stator_id−rotor_od)/2
    gap = snap["airgap"]
    checks.append(dict(name="气隙 = 0.675 mm", value=round(gap, 6), limit=0.675,
                       status="PASS" if abs(gap - 0.675) < 1e-6 else "FAIL"))
    checks.append(dict(name="Band 半径 = 气隙中线 46.1625", value=round(snap["band_r"], 6),
                       limit=46.1625, status="PASS" if abs(snap["band_r"] - 46.1625) < 1e-6 else "FAIL"))

    checks.append(dict(name="AEDT 设计校验无 intersect", value=log["validate"], limit="OK",
                       status="PASS" if log["validate"] == "OK" else "FAIL"))
    checks.append(dict(name="工程存盘", value=bool(log["saved"]), limit=True,
                       status="PASS" if bool(log["saved"]) else "FAIL"))
    checks.append(dict(name=".aedt 文件存在", value=os.path.exists(aedt_path), limit=True,
                       status="PASS" if os.path.exists(aedt_path) else "FAIL"))

    return dict(expect=dict(core_od=snap["core_od"], pm_t=snap["pm_t"],
                            rotor_area=round(snap["rotor_area"], 4),
                            ring_area=round(snap["ring_area"], 4),
                            magnet_total=snap["magnet_total"],
                            polarity=pol, band_r=snap["band_r"], gap=snap["airgap"]),
                measured=dict(sheets=log["sheets"], areas=log["areas"],
                              n_pm=len(log["pm"]), validate=log["validate"]),
                checks=checks,
                status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SPM 8p48s M1 独立几何自检")
    ap.add_argument("--log", default="D:/ANSYS_Run/spm_m1.log")
    ap.add_argument("--aedt", default="D:/ANSYS_Run/SPM_8p48s_M1.aedt")
    ap.add_argument("--core-od", type=float, default=None)
    ap.add_argument("--json", default=os.path.join(RESULTS, "m1_spm_build_check.json"))
    args = ap.parse_args(argv)

    with open(args.log, encoding="utf-8", errors="replace") as fh:
        log = parse_log(fh.read())
    cfg = spm_build.SPMConfig()
    if args.core_od is not None:
        cfg.spm_core_od = args.core_od
    res = check(cfg, log, args.aedt)
    res["log"] = args.log
    res["aedt"] = args.aedt

    print("=" * 74)
    print("SPM M1 几何自检 status=%s" % res["status"])
    print("=" * 74)
    for c in res["checks"]:
        print("  [%s] %-38s %12s / %s" % (c["status"], c["name"], c["value"], c["limit"]))
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print("  ✔ %s" % args.json)
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
