#!/usr/bin/env python3
"""模板路径求解 — 宿主侧编排（Python 3，负责清洗脚本 + 起 AEDT + 抓日志）。

链路
----
1. `maxwell_model*/build_25Nm_SPMSM.py`（模板生成物，7 步建模）
       ↓ `prepare_batch.to_batch_script()`
   `D:/ANSYS_Run/tpl_body[_<case>].py`（剥 ScriptEnv、f-string 降级到 IronPython 2.7）
2. `maxwell/tpl_solve_noload.py` → `D:/ANSYS_Run/tpl_solve_noload.py`
   （execfile 上面的 body → 存盘 → Analyze 20 ms → 导出 CSV）
3. `ansysedt.exe -RunScriptAndExit`，跑完打印日志全文。

工况（2026-11-15 M7 新增）
--------------------------
`--case noload`（默认）：`maxwell_model/` + `T4_tpl_noload.aedt` + `csv_tpl/`
`--case load`           ：`maxwell_model_load/` + `T4_tpl_load.aedt` + `csv_tpl_load/`

负载生成物必须先用
`python gen_maxwell_model.py --case load` 落盘（本脚本只清理/搬运，不生成），
以免「求解的是哪份模型」这件事被隐式决定。

用法
----
    python tpl_run.py                      # 空载：清洗 + 真机求解
    python tpl_run.py --case load          # 负载（M7）：清洗 + 真机求解
    python tpl_run.py --stage              # 只清洗，不起 AEDT（分层验收用）
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                     # projects/25Nm_PMSM
sys.path.insert(0, os.path.join(PROJ, "maxwell_model"))

from prepare_batch import to_batch_script  # noqa: E402

ANSYS_EXE = r"D:/Program Files/AnsysEM/AnsysEM21.1/Win64/ansysedt.exe"
RUNDIR = r"D:/ANSYS_Run"
# noload/load 是冻结的两条历史路径；其余（如 s075 = 斜槽切片 7.5°）走
# `maxwell_model_<case>/`，由 `gen_maxwell_model.py --init-deg ... --out_dir` 落盘。
MODEL_DIRS = {"noload": "maxwell_model", "load": "maxwell_model_load"}


def model_dir(case: str) -> str:
    return MODEL_DIRS.get(case, "maxwell_model_%s" % case)


def paths(case: str) -> dict:
    """按工况返回 (源生成物, body, 求解驱动, 日志)。空载沿用历史路径不变。"""
    if case == "noload":
        return {
            "src": os.path.join(PROJ, model_dir(case), "build_25Nm_SPMSM.py"),
            "body": os.path.join(RUNDIR, "tpl_body.py").replace("\\", "/"),
            "solver": os.path.join(RUNDIR, "tpl_solve_noload.py").replace("\\", "/"),
            "log": os.path.join(RUNDIR, "tpl_solve.log").replace("\\", "/"),
        }
    return {
        "src": os.path.join(PROJ, model_dir(case), "build_25Nm_SPMSM.py"),
        "body": os.path.join(RUNDIR, "tpl_body_%s.py" % case).replace("\\", "/"),
        "solver": os.path.join(RUNDIR, "tpl_solve_%s.py" % case).replace("\\", "/"),
        # 不能叫 tpl_solve_<case>.log：AEDT 会把 message window 写进「脚本同名 .log」，
        # 两份 writer 互相截断（2026-11-15 首次 M7 踩过）。见 tpl_solve_noload.py 注释。
        "log": os.path.join(RUNDIR, "tpl_app_%s.log" % case).replace("\\", "/"),
    }


def stage(case: str = "noload") -> dict:
    """把生成物清洗成可批跑的 body，并把求解驱动拷到运行目录。"""
    p = paths(case)
    if not os.path.exists(p["src"]):
        hint = ("python projects/25Nm_PMSM/gen_maxwell_model.py --case %s" % case
                if case in ("noload", "load") else
                "python projects/25Nm_PMSM/gen_maxwell_model.py --init-deg <deg> "
                "--out_dir projects/25Nm_PMSM/maxwell_model_%s" % case)
        raise SystemExit("缺生成物 %s\n先跑：%s" % (p["src"], hint))
    with open(p["src"], encoding="utf-8") as fh:
        body = to_batch_script(fh.read())
    if "ScriptEnv" in body:
        raise SystemExit("ScriptEnv 未完全剥离，批跑会失败")
    with open(p["body"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)

    # ── 负载工况把 case 与 body 路径**写死**进驱动副本 ──
    # 只靠环境变量有静默风险：若 TPL_CASE 没传进 AEDT，脚本会按 noload 的路径
    # 保存/导出，把负载解**覆盖到空载基线**上（且不报错）。这里改成字面量并断言
    # 恰好命中一行，失败即中止。
    solver_src = open(os.path.join(HERE, "tpl_solve_noload.py"), encoding="utf-8").read()
    if case != "noload":
        a = 'CASE = os.environ.get("TPL_CASE", "noload").strip().lower()'
        b = 'BODY = os.environ.get("TPL_BODY", r"D:/ANSYS_Run/tpl_body_%s.py" % CASE)'
        if solver_src.count(a) != 1 or solver_src.count(b) != 1:
            raise SystemExit("驱动模板已变，case 注入失败（先修 tpl_solve_noload.py 的 CASE/BODY 两行）")
        solver_src = solver_src.replace(a, 'CASE = "%s"' % case)
        solver_src = solver_src.replace(b, 'BODY = r"%s"' % p["body"])
        print("patched: CASE=%s / BODY=%s" % (case, p["body"]))
    with open(p["solver"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write(solver_src)

    print("case   :", case)
    print("body   :", p["body"], os.path.getsize(p["body"]), "B")
    print("solver :", p["solver"])
    return p


def run(case: str = "noload", p: dict | None = None) -> int:
    p = p or paths(case)
    cmd = [ANSYS_EXE, "-RunScriptAndExit", p["solver"]]
    env = dict(os.environ)
    env["TPL_CASE"] = case
    env["TPL_BODY"] = p["body"]
    print("run:", " ".join(cmd), "(TPL_CASE=%s)" % case)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                          errors="replace", env=env)   # AEDT 的 stdout 是 GBK
    print("rc =", proc.returncode)
    if os.path.exists(p["log"]):
        print("-" * 60)
        print(open(p["log"], encoding="utf-8", errors="replace").read())
    else:
        print("!! 日志未生成：", p["log"])
    return proc.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", default="noload",
                    help="工况：noload（默认）/ load（M7）/ 其它任意名（G7 斜槽切片，"
                         "需先 gen_maxwell_model.py --init-deg ... --out_dir maxwell_model_<case>）")
    ap.add_argument("--stage", action="store_true", help="只清洗脚本，不启动 AEDT")
    ap.add_argument("--no-run", action="store_true", help="同 --stage")
    args = ap.parse_args(argv)
    p = stage(args.case)
    if args.stage or args.no_run:
        return 0
    return run(args.case, p)


if __name__ == "__main__":
    raise SystemExit(main())
