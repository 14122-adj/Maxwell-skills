# -*- coding: utf-8 -*-
"""把「控制台粘贴式」Maxwell 建模脚本转成 `-RunScriptAndExit` 可执行脚本。

背景（M0 踩坑）：
1. `ansysedt.exe -ng` 不能单独用于脚本模式，`-ng` 仅与
   `-batchsolve/-batchsave/-batchextract` 组合；脚本模式应直接
   `ansysedt.exe -RunScriptAndExit <脚本>`。
2. `-RunScriptAndExit` 模式下 AEDT 预注入 `oDesktop` 全局，脚本里调用
   `ScriptEnv.Initialize(...)` / `ScriptEnv.GetDesktop()` 会抛
   `AttributeError: 'module' object has no attribute 'GetDesktop'`。
3. 内嵌 IronPython 为 2.7，不支持 f-string。

本模块负责把建模脚本清洗成可直接批跑的形式，并生成带 SaveAs 与对象
清单的驱动脚本。

用法:
    python prepare_batch.py --workdir D:/ANSYS_Run
    "ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/m2_run.py"
"""
from __future__ import annotations

import argparse
import io
import os
import re

BODY_NAME = "m2_geom_body_run.py"
DRIVER_NAME = "m2_run.py"
REPORT_NAME = "m2_report.txt"

_SKIP_PREFIXES = (
    "import ScriptEnv",
    "ScriptEnv.Initialize(",
    "oDesktop = ScriptEnv.GetDesktop()",
)

_DRIVER = '''# -*- coding: utf-8 -*-
# 由 prepare_batch.py 生成, 勿手改
import sys
import traceback

LOG = r"{log}"
BODY = r"{body}"
AEDT = r"{aedt}"
_lines = []


def log(s):
    _lines.append(str(s))


def flush():
    f = open(LOG, "w")
    f.write("\\n".join(_lines))
    f.close()


flush()
log("=== driver start ===")
try:
    execfile(BODY)
    log("BODY_OK")
except Exception:
    log("BODY_FAIL: " + repr(sys.exc_info()[1]))
    log(traceback.format_exc())
flush()

proj = None
try:
    proj = oDesktop.GetActiveProject()
    log("active_project=" + proj.GetName())
except Exception:
    log("NO_ACTIVE_PROJECT: " + repr(sys.exc_info()[1]))

if proj is not None:
    try:
        proj.SaveAs(AEDT, True)
        log("SAVED_OK " + AEDT)
    except Exception:
        log("SAVE_FAIL: " + repr(sys.exc_info()[1]))
    flush()
    try:
        names = list(proj.GetTopDesignList())
        log("designs=" + ",".join(names))
        des = proj.SetActiveDesign(names[0])
        log("solution_type=" + des.GetSolutionType())
        oEditor = des.SetActiveEditor("3D Modeler")
        for grp in ("Solids", "Sheets"):
            objs = sorted(list(oEditor.GetObjectsInGroup(grp)))
            log("%s=%d" % (grp, len(objs)))
            for n in objs:
                log("OBJ " + n)
    except Exception:
        log("INVENTORY_FAIL: " + repr(sys.exc_info()[1]))
        log(traceback.format_exc())
    for mod, meth in (("BoundarySetup", "GetBoundaries"),
                      ("AnalysisSetup", "GetSetups")):
        try:
            o = des.GetModule(mod)
            f = getattr(o, meth, None)
            log("%s=%s" % (mod, ",".join(list(f())) if f else "N/A"))
        except Exception:
            log("%s.FAIL %s" % (mod, repr(sys.exc_info()[1])))
log("=== driver end ===")
flush()
'''


def to_batch_script(source: str) -> str:
    """剥掉 ScriptEnv 依赖, 并把 f-string 降级为 IronPython 2.7 可用写法。"""
    out = []
    for line in source.splitlines():
        s = line.strip()
        if any(s.startswith(p) for p in _SKIP_PREFIXES):
            if s.startswith("import ScriptEnv,"):
                line = line.replace("import ScriptEnv,", "import")
            else:
                continue
        out.append(line)
    text = "\n".join(out)
    # IronPython 2.7 无 f-string: 仅处理本目录脚本中出现的简单形态
    text = re.sub(r'\bcname = f"Coil_\{([^}]+)\}"',
                  r'cname = "Coil_" + str(\1)', text)
    text = re.sub(r'\bprint\(f"', 'print("', text)
    return text + "\n"


def prepare(repo_script: str, workdir: str) -> dict:
    with io.open(repo_script, encoding="utf-8") as fh:
        src = fh.read()
    body = to_batch_script(src)
    if "ScriptEnv" in body:
        raise ValueError("ScriptEnv 未完全剥离，批跑会失败")

    os.makedirs(workdir, exist_ok=True)
    body_path = os.path.join(workdir, BODY_NAME).replace(chr(92), "/")
    with io.open(body_path, "w", encoding="utf-8") as fh:
        fh.write(body)

    cfg = {"aedt": "M2_25Nm.aedt", "design": "Motor_Design"}
    aedt = os.path.join(workdir, cfg["aedt"]).replace("\\", "/")
    log = os.path.join(workdir, REPORT_NAME).replace("\\", "/")
    driver_path = os.path.join(workdir, DRIVER_NAME).replace(chr(92), "/")
    with io.open(driver_path, "w", encoding="utf-8") as fh:
        fh.write(_DRIVER.format(log=log, body=body_path.replace("\\", "/"), aedt=aedt))
    return {"body": body_path, "driver": driver_path, "aedt": aedt, "log": log}


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", default=os.path.join(here, "build_25Nm_SPMSM.py"))
    ap.add_argument("--workdir", default=r"D:/ANSYS_Run")
    args = ap.parse_args(argv)
    paths = prepare(args.script, args.workdir)
    print("body   :", paths["body"])
    print("driver :", paths["driver"])
    print("aedt   :", paths["aedt"])
    print('run    : "ansysedt.exe" -RunScriptAndExit "%s"' % paths["driver"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
