#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""I2 定源 —— 8p48s q=2 双层 60° 相带分布绕组的 96 个线圈边表

推导（不抄表、不猜）
--------------------
1. 每极每相槽数 `q = N/(2p·m) = 48/(8·3) = 2` ⇒ 整数槽分布绕组，60° 相带，
   每相带 2 个槽。
2. 槽距电角 `α_e = p·360/N = 4·360/48 = 30°`（机械 7.5°）。
3. 相带按 60° 划分，A 相轴取 0°：槽 1(0°)、2(30°) → A+；槽 3(60°)、4(90°) → C−；
   槽 5(120°)、6(150°) → B+；槽 7(180°)、8(210°) → A−；槽 9(240°)、10(270°) → C+；
   槽 11(300°)、12(330°) → B−。**12 槽一循环**（48/12 = 4 个重复单元）。
   ⇒ 相属序列 `A A C C B B A A C C B B`，极性 `+ + − − + + − − + + − −`。
4. 节距 `y = 5` 槽（全距 6，短距 1 槽 = 150° 电角）。为什么短距 1 槽：
   `kp1 = sin(150°/2) = 0.9659`，`kp5 = sin(5·75°) = 0.2588`、`kp7 = 0.2588`
   ⇒ 5/7 次被压到基波的 26.8%，而基波只降 3.4%。这是 48 槽 8 极最常用的选择。
5. 双层：第 k 号线圈的**上层边**在槽 k、**下层边**在槽 k+y（模 48）。
   ⇒ 槽 s 的上层属于线圈 s（极性 σ(s)）；槽 s 的下层属于线圈 s−y（极性 −σ(s−y)，
   因为它是该线圈的回边）。

自检（`analyze`）
-----------------
* 96 边齐全、每相 16 个线圈 / 32 个边；
* `k_w1` 解析值 `kd1·kp1 = 0.9659×0.9659 = 0.9330`；
* 三相基波相量互差 120°±1°（相序 A→B→C 为正序）；
* 3 次/9 次（三倍频）含量 < 1e-6（60° 相带 + 双层对称的必然结果）；
* 5/7 次 < 0.07（短距 1 槽的效果）。

所有数字都能用 `--verbose` 复算；本模块不做任何 FEA，FEA 归 M2'。
"""
from __future__ import annotations

import cmath
import csv
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ipm_geom import IPMConfig  # noqa: E402

# 12 槽一循环的相带（60° 相带，q=2）
PHASE_PATTERN = ("A", "A", "C", "C", "B", "B", "A", "A", "C", "C", "B", "B")
SIGN_PATTERN = (1, 1, -1, -1, 1, 1, -1, -1, 1, 1, -1, -1)
PHASES = ("A", "B", "C")


def slot_phase(slot_1b: int) -> tuple:
    """槽号（1..48）→ (相, 极性)。极性 +1 = 该槽上层边电流 +z。"""
    i = (slot_1b - 1) % len(PHASE_PATTERN)
    return PHASE_PATTERN[i], SIGN_PATTERN[i]


def build_table(cfg: IPMConfig) -> list:
    """96 个线圈边：槽号 / 层 / 所属线圈 / 相 / 极性。"""
    n, y = cfg.slots, cfg.coil_pitch
    rows = []
    for s in range(1, n + 1):
        ph, sg = slot_phase(s)
        rows.append(dict(slot=s, layer="U", coil=s, phase=ph, sign=sg, obj="Coil_T%02d" % s))
        back = ((s - 1 - y) % n) + 1          # 下层边所属线圈（回边）
        ph2, sg2 = slot_phase(back)
        rows.append(dict(slot=s, layer="L", coil=back, phase=ph2, sign=-sg2,
                         obj="Coil_B%02d" % s))
    return rows


def emf_phasor(rows, phase: str, nu: int, cfg: IPMConfig) -> complex:
    """相电动势的 ν 次谐波相量和（未归一化）。

    线圈 c 的上层边在槽 c，下层边在槽 c+y；该线圈贡献
    `σ(c)·(e^{jνθ_c} − e^{jνθ_{c+y}})`，θ = (slot−1)·α_e，σ(c) 取**槽 c 的相带极性**。
    注意：不能读 `rows` 里先出现的那个边的 sign —— c > N−y 时下层边（回边，极性反号）
    会先出现，用它会把该线圈整体反相（2026-11-20 首版即此 bug）。
    """
    alpha = 2.0 * math.pi * cfg.poles_pairs / cfg.slots
    total = 0j
    for c in range(1, cfg.slots + 1):
        if slot_phase(c)[0] != phase:
            continue
        sg = slot_phase(c)[1]
        th_u = (c - 1) * alpha
        th_l = ((c - 1 + cfg.coil_pitch) % cfg.slots) * alpha
        total += sg * (cmath.exp(1j * nu * th_u) - cmath.exp(1j * nu * th_l))
    return total


def winding_factors(rows, cfg: IPMConfig, max_nu: int = 15) -> dict:
    n_coils = cfg.slots // len(PHASES)
    out = {}
    for nu in range(1, max_nu + 1):
        ph = emf_phasor(rows, "A", nu, cfg)
        out[nu] = round(abs(ph) / (2.0 * n_coils), 6)
    return out


def analyze(cfg: IPMConfig) -> dict:
    rows = build_table(cfg)
    n_coils = cfg.slots // len(PHASES)

    per_phase = {p: dict(coils=set(), sides=0, up=0, low=0) for p in PHASES}
    for r in rows:
        per_phase[r["phase"]]["coils"].add(r["coil"])
        per_phase[r["phase"]]["sides"] += 1
        per_phase[r["phase"]]["up" if r["layer"] == "U" else "low"] += 1

    kw = winding_factors(rows, cfg)
    phasors = {p: emf_phasor(rows, p, 1, cfg) for p in PHASES}
    # 3 次谐波：60° 相带绕组的**相电动势**里 k_w3 = 0.5 并不为零（kd3·kp3 = 0.707×(−0.707)），
    # 但三相对称时三倍频同相，线电压里严格抵消 —— 判据应对线电压成立，不是对相电压。
    ph3 = {p: emf_phasor(rows, p, 3, cfg) for p in PHASES}
    v3_ll = abs(ph3["A"] - ph3["B"]) / abs(phasors["A"])
    ang = {p: math.degrees(cmath.phase(v)) for p, v in phasors.items()}
    # 归一化到 (-180, 180]
    ang = {p: (a + 180.0) % 360.0 - 180.0 for p, a in ang.items()}
    d_ab = (ang["B"] - ang["A"]) % 360.0
    d_bc = (ang["C"] - ang["B"]) % 360.0
    d_ca = (ang["A"] - ang["C"]) % 360.0

    checks = [
        dict(name="线圈边总数 = 96", value=len(rows), limit=96, op="==",
             status="PASS" if len(rows) == 96 else "FAIL"),
        dict(name="每相线圈数 = 16", value=min(len(v["coils"]) for v in per_phase.values()),
             limit=n_coils, op="==",
             status="PASS" if all(len(v["coils"]) == n_coils for v in per_phase.values()) else "FAIL"),
        dict(name="每相边数 = 32（上下各 16）", value=min(v["sides"] for v in per_phase.values()),
             limit=2 * n_coils, op="==",
             status="PASS" if all(v["sides"] == 2 * n_coils and v["up"] == n_coils
                                  and v["low"] == n_coils for v in per_phase.values()) else "FAIL"),
        dict(name="k_w1 = kd1·kp1 = 0.9330", value=kw[1], limit=round(0.9659 * 0.9659, 6),
             op="==", status="PASS" if abs(kw[1] - 0.9659 * 0.9659) < 5e-4 else "FAIL"),
        dict(name="k_w5 ≤ 0.07（短距抑 5 次）", value=kw[5], limit=0.07, op="<=",
             status="PASS" if kw[5] <= 0.07 else "FAIL"),
        dict(name="k_w7 ≤ 0.07（短距抑 7 次）", value=kw[7], limit=0.07, op="<=",
             status="PASS" if kw[7] <= 0.07 else "FAIL"),
        dict(name="三倍频在线电压中抵消", value=round(v3_ll, 9), limit=1e-6, op="<=",
             status="PASS" if v3_ll <= 1e-6 else "FAIL"),
        dict(name="三相基波互差 120°", value=round(max(abs(d - 120.0) for d in (d_ab, d_bc, d_ca)), 4),
             limit=1.0, op="<=",
             status="PASS" if max(abs(d - 120.0) for d in (d_ab, d_bc, d_ca)) <= 1.0 else "FAIL"),
    ]

    return dict(rows=rows,
                summary=dict(q=cfg.slots / (cfg.poles * len(PHASES)), pitch=cfg.coil_pitch,
                             slots_per_pole=cfg.slots / cfg.poles,
                             alpha_e_deg=360.0 * cfg.poles_pairs / cfg.slots,
                             kw=kw, phase_angle_deg=ang,
                             d_ab=round(d_ab, 4), d_bc=round(d_bc, 4), d_ca=round(d_ca, 4)),
                checks=checks,
                status="PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL")


def markdown_table(rows, cfg: IPMConfig) -> str:
    """48 行 × 上下两层的人类可读表（同时给出 96 边的极性）。"""
    by_slot = {}
    for r in rows:
        by_slot.setdefault(r["slot"], {})[r["layer"]] = r
    lines = [
        "# IPM 8p48s 双层绕组槽号→相属表（I2 定源）",
        "",
        "> 由 `projects/IPM_8p48s/ipm_winding.py` 生成，勿手改。",
        "> q = %.2f，节距 y = %d 槽（%d° 电角），k_w1 = %.4f。" % (
            cfg.slots / (cfg.poles * 3), cfg.coil_pitch,
            int(cfg.coil_pitch * 360.0 * cfg.poles_pairs / cfg.slots),
            analyze(cfg)["summary"]["kw"][1]),
        "> 极性 + = 该边电流 +z；− = −z。上层边属线圈 s，下层边属线圈 s−y 的回边。",
        "",
        "| 槽 | 上层相/极性 | 上层对象 | 下层相/极性 | 下层对象 |",
        "|---:|---|---|---|---|",
    ]
    for s in range(1, cfg.slots + 1):
        u, low = by_slot[s]["U"], by_slot[s]["L"]
        lines.append("| %d | %s%s | %s | %s%s | %s |" % (
            s, u["phase"], "+" if u["sign"] > 0 else "−", u["obj"],
            low["phase"], "+" if low["sign"] > 0 else "−", low["obj"]))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="IPM 8p48s 双层绕组定源")
    ap.add_argument("--out", default=os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
    ap.add_argument("--md", default=os.path.join(_HERE, "WINDING_TABLE.md"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    cfg = IPMConfig()
    res = analyze(cfg)
    rows = res["rows"]
    s = res["summary"]

    print("=" * 72)
    print("I2 8p48s 双层绕组  status=%s" % res["status"])
    print("=" * 72)
    print("  q=%.2f  y=%d  α_e=%.1f°  k_w: %s" % (
        s["q"], s["pitch"], s["alpha_e_deg"],
        "  ".join("%d:%.4f" % (k, v) for k, v in list(s["kw"].items())[:7])))
    print("  相角 A=%.2f° B=%.2f° C=%.2f°（互差 %.2f/%.2f/%.2f）" % (
        s["phase_angle_deg"]["A"], s["phase_angle_deg"]["B"], s["phase_angle_deg"]["C"],
        s["d_ab"], s["d_bc"], s["d_ca"]))
    for c in res["checks"]:
        print("    [%s] %-30s %12.6f %s %10.6f" % (c["status"], c["name"], c["value"], c["op"], c["limit"]))
    if args.verbose:
        for r in rows[:16]:
            print("   slot %2d %s %s%s coil=%d" % (r["slot"], r["layer"], r["phase"],
                                                   "+" if r["sign"] > 0 else "−", r["coil"]))

    os.makedirs(args.out, exist_ok=True)
    csv_path = os.path.join(args.out, "i2_winding_sides.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["slot", "layer", "coil", "phase", "sign", "object"])
        for r in rows:
            w.writerow([r["slot"], r["layer"], r["coil"], r["phase"], r["sign"], r["obj"]])
    with open(os.path.join(args.out, "i2_winding.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(summary=res["summary"], checks=res["checks"], status=res["status"]),
                  fh, ensure_ascii=False, indent=2)
    with open(args.md, "w", encoding="utf-8") as fh:
        fh.write(markdown_table(rows, cfg))
    print("  ✔ %s（96 行）" % csv_path)
    print("  ✔ %s" % args.md)
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
