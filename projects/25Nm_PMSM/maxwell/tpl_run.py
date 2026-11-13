#!/usr/bin/env python3
"""模板路径空载求解 — 宿主侧编排（Python 3，负责清洗脚本 + 起 AEDT + 抓日志）。

链路（G4）
----------
1. `maxwell_model/build_25Nm_SPMSM.py`（模板生成物，7 步建模）
       ↓ `prepare_batch.to_batch_script()`
   `D:/ANSYS_Run/tpl_body.py`（剥 ScriptEnv、f-string 降级到 IronPython 2.7）
2. `maxwell/tpl_solve_noload.py` → `D:/ANSYS_Run/tpl_solve_noload.py`
   （execfile 上面的 body → 存盘 → Analyze 20 ms → 导出 CSV）
3. `ansysedt.exe -RunScriptAndExit`，跑完打印 `tpl_solve.log` 全文。

用法
----
    python tpl_run.py              # 清洗 + 真机求解
    python tpl_run.py --stage      # 只清洗，不起 AEDT（分层验收用）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                     # projects/25Nm_PMSM
sys.path.insert(0, os.path.join(PROJ, "maxwell_model"))

from prepare_batch import to_batch_script  # noqa: E402

ANSYS_EXE = r"D:/Program Files/AnsysEM/AnsysEM21.1/Win64/ansysedt.exe"
RUNDIR = r"D:/ANSYS_Run"
BODY = os.path.join(RUNDIR, "tpl_body.py").replace("\\", "/")
SOLVER = os.path.join(RUNDIR, "tpl_solve_noload.py").replace("\\", "/")
LOG = os.path.join(RUNDIR, "tpl_solve.log").replace("\\", "/")


def stage() -> None:
    """把生成物清洗成可批跑的 body，并把求解驱动拷到运行目录。"""
    src = os.path.join(PROJ, "maxwell_model", "build_25Nm_SPMSM.py")
    with open(src, encoding="utf-8") as fh:
        body = to_batch_script(fh.read())
    if "ScriptEnv" in body:
        raise SystemExit("ScriptEnv 未完全剥离，批跑会失败")
    with open(BODY, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    shutil.copyfile(os.path.join(HERE, "tpl_solve_noload.py"), SOLVER)
    print("body   :", BODY, os.path.getsize(BODY), "B")
    print("solver :", SOLVER)


def run() -> int:
    cmd = [ANSYS_EXE, "-RunScriptAndExit", SOLVER]
    print("run:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                          errors="replace")   # AEDT 的 stdout 是 GBK，不是 UTF-8
    print("rc =", proc.returncode)
    if os.path.exists(LOG):
        print("-" * 60)
        print(open(LOG, encoding="utf-8", errors="replace").read())
    else:
        print("!! 日志未生成：", LOG)
    return proc.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", action="store_true", help="只清洗脚本，不启动 AEDT")
    ap.add_argument("--no-run", action="store_true", help="同 --stage")
    args = ap.parse_args(argv)
    stage()
    if args.stage or args.no_run:
        return 0
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
