#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M4' —— 网格剖分 + 统计导出 + 独立判定（契约 §8）。

链路（真机 2021.1，API 见 docs/MAXWELL_INTERNALS.md §18）
--------------------------------------------------------
1. ``--gen``：生成 IronPython 脚本到 D:/ANSYS_Run/ipm_mesh_<case>.py，
   内容是 OpenProject -> oDesign.GenerateMesh("Setup1") ->
   oDesign.ExportMeshStats("Setup1", "Nominal", out_txt, 1) -> Close，
   并记录生成耗时。
2. 真机：``ansysedt.exe -RunScriptAndExit <gen 脚本>``（不加 -ng）。
3. ``--parse``：宿主 CPython 解析导出的 meshstats 文本 -> KEEP 的
   ``projects/results/ipm8p48s/mesh_<case>.json``，并对照契约 §8.3 判定。

判据（契约 §8.3，失败写 FAIL 不改判据）
--------------------------------------
* 5 组 AssignLengthOp 必须 Enabled 且 MaxLength 与契约一致
  （Band 0.25 / Stator 0.9 / Rotor 1.2 / PM 0.5 / AirgapRing 0.15 mm，I28 新增第 5 组）；
* Band MaxLength ≤ 0.25 mm；
* AirgapRing 径向层数 = 0.3375 mm / rms_edge ≥ 2.0（契约 §9.2）；
* Band/Stator/Rotor/PM/AirgapRing/Coil 六类对象单元数均非 0；
* 质量指标（skewness 等）与节点数：2021.1 ExportMeshStats 不导出，
  写 ``unavailable`` + 原因，**不编数**（§18.3 实测）。

反自演：所有数字来自 ExportMeshStats 文本或 .aedt 真机块，解析与判定分离；
统计单位按 SI(m) 推断（§18.4，assumption=待验证），转 mm ×1000。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
RESULTS = os.path.abspath(os.path.join(_ROOT, "projects", "results", "ipm8p48s"))
RUNDIR = r"D:/ANSYS_Run"

# 契约 §8.1 / §9.2 的 5 组 MaxLength（mm），权威值。
# I28 (2026-11-25) 新增 Mesh_Airgap：气隙厚 0.3375 mm / 0.15 mm = 2.25 层。
EXPECTED_LENGTH_OPS = {
    "Mesh_Band": ("Band", 0.25),
    "Mesh_Stator": ("StatorOuter", 0.9),
    "Mesh_Rotor": ("RotorOuter", 1.2),
    "Mesh_PM": ("PM", 0.5),
    "Mesh_Airgap": ("AirgapRing", 0.15),
}
BAND_MAXLEN_MM = 0.25
# 契约 §9.2：气隙环厚 = airgap/2 = 0.3375 mm；层数 = thickness / rms_edge ≥ 2.0
AIRGAP_RING_THICKNESS_MM = 0.3375
AIRGAP_MIN_LAYERS = 2.0
MM_PER_SI = 1000.0  # 统计长度 SI(m) -> mm（§18.4）

# 六类对象 -> 统计文本里的对象名前缀（PM/Coil 为多实例）
OBJECT_GROUPS = {
    "Band": lambda n: n == "Band",
    "Stator": lambda n: n == "StatorOuter",
    "Rotor": lambda n: n == "RotorOuter",
    "PM": lambda n: bool(re.fullmatch(r"PM_\d+", n)),
    "AirgapRing": lambda n: n == "AirgapRing",
    "Coil": lambda n: bool(re.fullmatch(r"Coil_[TB]\d+", n)),
}


# ------------------------------------------------------------------ gen 侧
def gen_ironpython(case: str, aedt_name: str, out_txt: str) -> str:
    """生成真机 IronPython 脚本源码（不用 f-string 拼 %，日志行字符串拼接）。"""
    script_path = RUNDIR + "/ipm_mesh_" + case + ".py"
    # 传进来的 aedt_name 可能带或不带 .aedt，统一去掉再拼（避免 .aedt.aedt）
    aedt_base = aedt_name[:-5] if aedt_name.lower().endswith(".aedt") else aedt_name
    src = "\n".join(
        [
            "# -*- coding: utf-8 -*-",
            "# 由 ipm_mesh_check.py --gen 生成；真机剖分+统计，不保存工程。",
            "import time",
            'LOG = "' + RUNDIR + "/ipm_mesh_" + case + '.log"',
            'def log(m):',
            '    with open(LOG, "a") as f:',
            '        f.write(str(m) + "\\n")',
            'log("=== mesh gen ' + case + ' start ===")',
            "t0 = time.time()",
            "try:",
            '    prj = oDesktop.OpenProject("' + RUNDIR + "/" + aedt_base + '.aedt")',
            '    log("OPEN_OK " + prj.GetName())',
            '    des = prj.GetDesign("Motor_Design")',
            '    r = des.GenerateMesh("Setup1")',
            '    log("GENERATE_MESH r=" + repr(r))',
            '    des.ExportMeshStats("Setup1", "Nominal", "' + out_txt + '", 1)',
            '    log("EXPORT_STATS_OK")',
            '    log("GEN_TIME_S " + repr(time.time() - t0))',
            "    prj.Close()",
            '    log("CLOSE_OK")',
            "except Exception as e:",
            '    log("FATAL " + repr(e))',
            'log("=== end ===")',
            "",
        ]
    )
    with open(script_path, "w") as f:
        f.write(src)
    return script_path


# ------------------------------------------------------------- .aedt 解析
def parse_length_ops(aedt_path: str) -> dict:
    """从真机 .aedt 文本块读 5 组 LengthBased 的 Enabled / MaxLength。"""
    with open(aedt_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    ops: dict = {}
    # MeshSetup 块内：Type='LengthBased' ... Enabled=... ... MaxLength='..mm'
    pattern = re.compile(
        r"Type='LengthBased'\s+Enabled=(true|false)\s+[^']*?MaxLength='([0-9.]+mm)'",
        re.IGNORECASE,
    )
    found = pattern.findall(text)
    names = list(EXPECTED_LENGTH_OPS)
    if len(found) < len(names):
        # 放宽：Enabled 与 MaxLength 之间可能有其它键，逐段窗口匹配
        found = []
        for m in re.finditer(r"Type='LengthBased'", text):
            window = text[m.start() : m.start() + 500]
            en = re.search(r"Enabled=(true|false)", window, re.IGNORECASE)
            mx = re.search(r"MaxLength='([0-9.]+mm)'", window)
            if en and mx:
                found.append((en.group(1), mx.group(1)))
    for idx, (enabled, maxlen) in enumerate(found[: len(names)]):
        name = names[idx]
        ops[name] = {
            "enabled": enabled.lower() == "true",
            "max_length": maxlen,
            "expected_max_length_mm": EXPECTED_LENGTH_OPS[name][1],
            "objects": EXPECTED_LENGTH_OPS[name][0],
        }
    return ops


# ----------------------------------------------------------- 统计文本解析
def parse_meshstats(txt_path: str) -> dict:
    """解析 ExportMeshStats 文本：总单元数 + 逐对象 8 列统计（SI 原值 + mm 换算）。"""
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    meta = {"project": "", "design": "", "setup": ""}
    total = 0
    per_object: list[dict] = []
    for line in lines:
        s = line.strip()
        m = re.match(r"Project:\s+(.+)$", s)
        if m:
            meta["project"] = m.group(1).strip()
            continue
        m = re.match(r"Design:\s+(.+)$", s)
        if m:
            meta["design"] = m.group(1).strip()
            continue
        m = re.match(r"Solution setup:\s+(.+)$", s)
        if m:
            meta["setup"] = m.group(1).strip()
            continue
        m = re.match(r"Total number of mesh elements:\s+(\d+)", s)
        if m:
            total = int(m.group(1))
            continue
        if "|" not in s:
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 9:
            continue
        name = parts[0]
        try:
            nums = [float(x) for x in parts[1:9]]
        except ValueError:
            continue  # 表头行 / 尾行
        per_object.append(
            {
                "object": name,
                "num_elements": int(nums[0]),
                "min_edge_mm": round(nums[1] * MM_PER_SI, 6),
                "max_edge_mm": round(nums[2] * MM_PER_SI, 6),
                "rms_edge_mm": round(nums[3] * MM_PER_SI, 6),
                "min_elem_area_mm2": nums[4] * MM_PER_SI**2,
                "max_elem_area_mm2": nums[5] * MM_PER_SI**2,
                "mean_elem_area_mm2": nums[6] * MM_PER_SI**2,
                "stdev_area_mm2": nums[7] * MM_PER_SI**2,
            }
        )
    return {"meta": meta, "total_elements": total, "per_object": per_object}


# --------------------------------------------------------------- 判定侧
def judge(stats: dict, ops: dict) -> dict:
    checks: dict = {}
    # 1) 5 组 LengthOp Enabled + MaxLength 与契约一致
    op_ok = True
    op_detail = {}
    for name, (_, expected) in EXPECTED_LENGTH_OPS.items():
        o = ops.get(name)
        if not o:
            op_ok = False
            op_detail[name] = "missing"
            continue
        actual = o["max_length"].replace("mm", "")
        ok = o["enabled"] and abs(float(actual) - expected) < 1e-9
        op_detail[name] = {"enabled": o["enabled"], "max_length_mm": float(actual), "pass": ok}
        op_ok = op_ok and ok
    checks["length_ops_enabled_and_match"] = {"pass": op_ok, "detail": op_detail}

    # 2) Band MaxLength <= 0.25
    band_op = ops.get("Mesh_Band", {})
    band_ml = float(band_op.get("max_length", "999mm").replace("mm", ""))
    checks["band_max_length_le_0p25mm"] = {
        "pass": band_ml <= BAND_MAXLEN_MM,
        "max_length_mm": band_ml,
        "limit_mm": BAND_MAXLEN_MM,
    }

    # 3) 六类对象单元数非 0（按名称归类）
    by_group = {g: {"num_objects": 0, "num_elements": 0} for g in OBJECT_GROUPS}
    for row in stats["per_object"]:
        for g, pred in OBJECT_GROUPS.items():
            if pred(row["object"]):
                by_group[g]["num_objects"] += 1
                by_group[g]["num_elements"] += row["num_elements"]
                break
    group_ok = all(v["num_elements"] > 0 for v in by_group.values())
    checks["all_object_groups_nonzero"] = {"pass": group_ok, "detail": by_group}

    # 3b) I28 / 契约 §9.2：AirgapRing 径向层数 ≥ 2.0（thickness / rms_edge）
    # rms_edge 是周向+径向混合边长，作为层数口径是保守估计（周向拉长会高估 rms、
    # 从而低估层数）；判据按指导书 §3.4 原文口径执行，assumption=待验证。
    ag_rows = [r for r in stats["per_object"] if OBJECT_GROUPS["AirgapRing"](r["object"])]
    ag_rms = ag_rows[0]["rms_edge_mm"] if ag_rows else None
    ag_n = sum(r["num_elements"] for r in ag_rows)
    ag_layers = (AIRGAP_RING_THICKNESS_MM / ag_rms) if ag_rms and ag_rms > 0 else None
    checks["airgap_ring_min_layers"] = {
        "pass": bool(ag_layers is not None and ag_layers >= AIRGAP_MIN_LAYERS),
        "thickness_mm": AIRGAP_RING_THICKNESS_MM,
        "rms_edge_mm": ag_rms,
        "layers": round(ag_layers, 4) if ag_layers else None,
        "limit": AIRGAP_MIN_LAYERS,
        "num_elements": ag_n,
        "assumption": "rms_edge 作径向层厚代理（指导书 §3.4 口径），周向拉长使其保守偏低",
    }

    # 4) 质量指标 / 节点数：真机不导出，写 unavailable + 原因（不编数）
    checks["quality_metrics"] = {
        "status": "unavailable",
        "reason": "2021.1 ExportMeshStats 仅导出 8 列单元统计（Num Elements/min/max/RMS edge/min/max/mean/stdev area），"
        "无 skewness/aspect/orthogonal；dir(oDesign) 仅 ApplyMeshOps/ExportMeshStats/GenerateMesh，无质量 getter（§18.3）",
    }
    checks["node_count"] = {
        "status": "unavailable",
        "reason": "ExportMeshStats 不导出节点数；2021.1 未发现可读节点统计的 API（§18.3）",
    }

    overall = all(
        c.get("pass", True) for c in checks.values()
    )  # unavailable 项不参与判定，但显式留痕
    return {"checks": checks, "overall_pass": overall}


def build_json(case: str, aedt_name: str, stats: dict, ops: dict, gen_time_s: float | None) -> dict:
    verdict = judge(stats, ops)
    edges = [r["max_edge_mm"] for r in stats["per_object"]]
    mins = [r["min_edge_mm"] for r in stats["per_object"]]
    return {
        "case": case,
        "project": stats["meta"]["project"] or aedt_name.replace(".aedt", ""),
        "design": stats["meta"]["design"] or "Motor_Design",
        "setup": stats["meta"]["setup"] or "Setup1",
        "mesh_method": "AnsoftTAU",
        "units": "SI_m_inferred_x1000_to_mm",
        "units_assumption": {
            "value": "统计长度按 SI(m) 读，×1000 转 mm；面积 ×1e6 转 mm²",
            "status": "assumption=待验证",
            "cross_check": "Band RMS 0.000656487 m -> 0.656 mm ≈ 气隙 0.675 mm（2.8%）；若按 mm 读则 0.15 µm 单元不可能",
            "verify_method": "换已知几何（PM 厚 2.8 mm）比对 max edge 是否落 0.1–3 mm 量级",
        },
        "total_elements": stats["total_elements"],
        "element_size_mm": {
            "min_edge": min(mins) if mins else None,
            "max_edge": max(edges) if edges else None,
            "note": "min/max 取逐对象列极值；Band 的 max_edge 是周向长边，与气隙径向厚度无关",
        },
        "length_ops": ops,
        "per_object": stats["per_object"],
        "mesh_generation_time_s": gen_time_s,
        "verdict": verdict,
        "evidence": {
            "api_doc": "docs/MAXWELL_INTERNALS.md §18",
            "probe_logs": [
                "D:/ANSYS_Run/probe_mesh_api.log",
                "D:/ANSYS_Run/probe_mesh_api2.log",
                "D:/ANSYS_Run/probe_mesh_api3.log",
            ],
            "meshstats_txt": "D:/ANSYS_Run/meshstats_" + case + ".txt",
            "aedt": "D:/ANSYS_Run/" + aedt_name,
        },
    }


def read_gen_time(case: str) -> float | None:
    logp = RUNDIR + "/ipm_mesh_" + case + ".log"
    if not os.path.exists(logp):
        return None
    with open(logp, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"GEN_TIME_S\s+([0-9.]+)", line.strip())
            if m:
                return round(float(m.group(1)), 3)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", default="m1_bhfix", help="case 名，决定 mesh_<case>.json 与脚本名")
    ap.add_argument("--aedt", default="IPM_8p48s_M1_bhfix.aedt", help="D:/ANSYS_Run 下的工程文件名")
    ap.add_argument("--gen", action="store_true", help="生成 IronPython 剖分脚本")
    ap.add_argument("--parse", action="store_true", help="解析统计文本 -> mesh_<case>.json + 判定")
    ap.add_argument("--json", default="", help="--parse 时输出路径（默认 results/ipm8p48s/mesh_<case>.json）")
    args = ap.parse_args()

    out_txt = RUNDIR + "/meshstats_" + args.case + ".txt"
    if args.gen:
        p = gen_ironpython(args.case, args.aedt, out_txt)
        print("GEN_SCRIPT " + p)
        return 0
    if args.parse:
        if not os.path.exists(out_txt):
            print("MISSING " + out_txt, file=sys.stderr)
            return 2
        stats = parse_meshstats(out_txt)
        aedt_path = args.aedt if args.aedt.lower().endswith(".aedt") else args.aedt + ".aedt"
        ops = parse_length_ops(RUNDIR + "/" + aedt_path)
        result = build_json(args.case, args.aedt, stats, ops, read_gen_time(args.case))
        out = args.json or os.path.join(RESULTS, "mesh_" + args.case + ".json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("WROTE " + out)
        print("TOTAL_ELEMENTS " + str(result["total_elements"]))
        print("OVERALL_PASS " + str(result["verdict"]["overall_pass"]))
        for k, v in result["verdict"]["checks"].items():
            if "pass" in v:
                print("  " + k + " = " + str(v["pass"]))
        return 0 if result["verdict"]["overall_pass"] else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
