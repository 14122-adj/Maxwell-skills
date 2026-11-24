#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1' 独立复核 —— 把真机日志里的图元/面积读回来，对照 CPython 侧期望值。

为什么单独一个脚本
------------------
`ipm_build.py` 生成模型时已经把「期望面积」算好并写进了日志，但那是**同源自证**：
生成器和核对器如果是同一段代码，代码错了两边一起错。这里只做一件事 ——
**重新从 `ipm_geom` 独立算一遍期望值**，再读 Maxell 落盘的 `GetFaceArea` 实测，
逐项比对，并把结果冻结成 JSON（账本的证据源）。

判据（M1'，`PROJECT_SPEC.md` §4）
--------------------------------
1. `SHEETS = 117`（Region/StatorOuter/RotorOuter/Band/AirgapRing 各 1 + PM 16 + Coil 96）；
2. 前缀计数 `PM=16`、`Coil=96`、`AirgapRing=1`；
3. 定子面积 = 环面积 − 48×槽实切面积（±0.05%）；
4. 转子面积 = 环面积 − Σ磁钢面积（±0.05%）；
5. 96 个线圈面积全部落在 13.88 ±1%（两层各半槽）；
6. 16 块磁钢面积 = L×t（±0.1%），且中心关于极轴镜像；
7. `VALIDATE_OK`（AEDT 设计校验通过）+ `SAVED_OK`。

用法
----
    python ipm_m1_check.py                      # 读 D:/ANSYS_Run/ipm_m1.log
    python ipm_m1_check.py --log <path> --out <dir>
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

import ipm_geom  # noqa: E402

DEFAULT_LOG = r"D:/ANSYS_Run/ipm_m1.log"
# 当前契约版工程（11-22 两次修订：单层 V 16 块 + 矩形绕组 9.8 mm²）。
# 旧双层/异形版工程另存为 *_M1.aedt / *_M1c.aedt，不参与本轮证据链。
AEDT = r"D:/ANSYS_Run/IPM_8p48s_M1_rect.aedt"


def parse_log(text: str) -> dict:
    out = {"sheets": None, "prefix": {}, "areas": {}, "coil": {}, "pm": {},
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
        m = re.match(r"^COIL_AREA min=([\d.]+) max=([\d.]+)$", ln)
        if m:
            out["coil"] = {"min": float(m.group(1)), "max": float(m.group(2))}
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


def check(cfg, log: dict, aedt_path: str = AEDT) -> dict:
    i1 = ipm_geom.derive_slot(cfg)
    rotor = ipm_geom.derive_rotor(cfg)
    layers = ipm_geom.coil_layers(cfg)

    ring = math.pi * ((cfg.stator_od / 2) ** 2 - (cfg.stator_id / 2) ** 2)
    exp_stator = ring - cfg.slots * i1["areas"]["slot_effective"]
    exp_rotor = (math.pi * ((cfg.rotor_od / 2) ** 2 - (cfg.rotor_id / 2) ** 2)
                 - rotor["magnet_area_total"])
    n_pm = len(rotor["polygons"])

    def rel(a, b):
        return abs(a - b) / b * 100.0 if b else 1e9

    # 117 = 5 主体（Region/StatorOuter/RotorOuter/Band/AirgapRing）+ 16 PM + 96 Coil
    checks = []
    checks.append(dict(name="SHEETS = 5 + 16 + 96", value=log["sheets"], limit=5 + n_pm + cfg.slots * 2,
                       status="PASS" if log["sheets"] == 5 + n_pm + cfg.slots * 2 else "FAIL"))
    for k, want in (("Coil", cfg.slots * 2), ("PM", n_pm), ("Region", 1), ("StatorOuter", 1),
                    ("RotorOuter", 1), ("Band", 1), ("AirgapRing", 1)):
        checks.append(dict(name="前缀计数 %s = %d" % (k, want), value=log["prefix"].get(k),
                           limit=want, status="PASS" if log["prefix"].get(k) == want else "FAIL"))

    d_st = rel(log["areas"].get("StatorOuter", 0.0), exp_stator)
    checks.append(dict(name="定子面积 = 环 − 48 槽（偏差 %）", value=round(d_st, 5), limit=0.05,
                       status="PASS" if d_st <= 0.05 else "FAIL"))
    d_rt = rel(log["areas"].get("RotorOuter", 0.0), exp_rotor)
    checks.append(dict(name="转子面积 = 环 − Σ 磁钢（偏差 %）", value=round(d_rt, 5), limit=0.05,
                       status="PASS" if d_rt <= 0.05 else "FAIL"))
    # I17 独立气隙环：外 R=定子内径、内 R=气隙中线（= Band 半径），厚=½气隙
    exp_ring = math.pi * ((cfg.stator_id / 2) ** 2 -
                          (cfg.rotor_od / 2 + cfg.airgap / 2) ** 2)
    d_ring = rel(log["areas"].get("AirgapRing", 0.0), exp_ring)
    checks.append(dict(name="气隙环面积 = π(46.5²−46.1625²)（偏差 %）", value=round(d_ring, 5), limit=0.05,
                       status="PASS" if d_ring <= 0.05 else "FAIL"))
    d_cu = max(rel(log["coil"].get("min", 0.0), layers["area_lower"]),
               rel(log["coil"].get("max", 0.0), layers["area_upper"]))
    checks.append(dict(name="96 线圈面积（最大偏差 %）", value=round(d_cu, 4), limit=1.0,
                       status="PASS" if d_cu <= 1.0 else "FAIL"))

    # 每块面积 = L×t（单层 V：全部 16 块同一长度，无 outer/inner 之分）
    lens = {"single": cfg.v_single[2]}
    worst = 0.0
    for lab, m in log["pm"].items():
        worst = max(worst, rel(m["area"], lens["single"] * cfg.pm_thickness))
    checks.append(dict(name="16 块磁钢面积 = L×t（最大偏差 %）", value=round(worst, 4), limit=0.1,
                       status="PASS" if worst <= 0.1 else "FAIL"))

    # 镜像对称：同极内 ± 两条腿的 center y 应互为相反数（极轴局部坐标）
    # 单层 V：每极 2 块（原双层是 4 块两对），只有 (0,1) 一对。
    asym = 0.0
    for pole in range(cfg.poles):
        base = pole * 2
        for j, k in ((0, 1),):
            a = log["pm"].get("PM_%02d" % (base + j + 1))
            b = log["pm"].get("PM_%02d" % (base + k + 1))
            if a and b:
                ang = math.radians(pole * 360.0 / cfg.poles)
                # 旋转到该极的局部坐标，比较 |y| 与 x
                def loc(p):
                    x = p["cx"] * math.cos(-ang) - p["cy"] * math.sin(-ang)
                    y = p["cx"] * math.sin(-ang) + p["cy"] * math.cos(-ang)
                    return x, y
                xa, ya = loc(a)
                xb, yb = loc(b)
                asym = max(asym, abs(xa - xb), abs(abs(ya) - abs(yb)))
    checks.append(dict(name="磁钢中心镜像对称（最大不对称 mm）", value=round(asym, 5), limit=0.02,
                       status="PASS" if asym <= 0.02 else "FAIL"))

    checks.append(dict(name="AEDT 设计校验", value=log["validate"], limit="OK",
                       status="PASS" if log["validate"] == "OK" else "FAIL"))
    checks.append(dict(name="工程存盘", value=bool(log["saved"]), limit=True,
                       status="PASS" if log["saved"] else "FAIL"))
    checks.append(dict(name=".aedt 文件存在", value=os.path.exists(aedt_path), limit=True,
                       status="PASS" if os.path.exists(aedt_path) else "FAIL"))

    return dict(expect=dict(stator_area=round(exp_stator, 4), rotor_area=round(exp_rotor, 4),
                            airgap_ring_area=round(exp_ring, 4),
                            coil_T=layers["area_upper"], coil_B=layers["area_lower"],
                            magnet_total=rotor["magnet_area_total"],
                            v_single=list(cfg.v_single)),
                measured=dict(sheets=log["sheets"], areas=log["areas"], coil=log["coil"],
                              n_pm=len(log["pm"]), validate=log["validate"]),
                checks=checks,
                status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M1' 独立复核")
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--aedt", default=AEDT, help="待核验的矩形版工程路径")
    ap.add_argument("--out", default=os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
    ap.add_argument("--json", default="", help="输出 JSON 全路径（默认 <out>/m1_build_check.json）")
    args = ap.parse_args(argv)

    if not os.path.exists(args.log):
        print("找不到日志：%s" % args.log)
        return 2
    with open(args.log, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    log = parse_log(text)
    cfg = ipm_geom.IPMConfig()
    res = check(cfg, log, args.aedt)
    res["log"] = args.log
    res["aedt"] = args.aedt

    print("=" * 74)
    print("M1' 复核  status=%s" % res["status"])
    print("=" * 74)
    print("  期望：定子 %.3f / 转子 %.3f / 线圈 T %.3f B %.3f / 磁钢总 %.3f mm²"
          % (res["expect"]["stator_area"], res["expect"]["rotor_area"],
             res["expect"]["coil_T"], res["expect"]["coil_B"], res["expect"]["magnet_total"]))
    print("  实测：定子 %.3f / 转子 %.3f / 线圈 %.3f–%.3f / 磁钢 %d 块"
          % (res["measured"]["areas"].get("StatorOuter", 0), res["measured"]["areas"].get("RotorOuter", 0),
             res["measured"]["coil"].get("min", 0), res["measured"]["coil"].get("max", 0),
             res["measured"]["n_pm"]))
    for c in res["checks"]:
        print("    [%s] %-36s %12s / %s" % (c["status"], c["name"], c["value"], c["limit"]))

    os.makedirs(args.out, exist_ok=True)
    path = args.json or os.path.join(args.out, "m1_build_check.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print("  ✔ %s" % path)
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
