# -*- coding: utf-8 -*-
# =============================================================================
#  ingest_fea.py  —  读取 Maxwell 导出的 CSV，计算真实 FEA 指标，回填报告
#  运行（无需 Maxwell，本机任意 Python 即可）：
#     python ingest_fea.py
#  前置：先在本机跑 solve_25Nm_SPMSM.py 生成 D:\ANSYS_Run\csv\*.csv
#  产物：D:\ANSYS_Run\fea_results.json  （供 HTML/Markdown 报告回填）
# =============================================================================
import os, csv, json, math
import numpy as np

CSVDIR = r"D:\ANSYS_Run\csv"
OUT    = r"D:\ANSYS_Run\fea_results.json"

def load_csv(name):
    p = os.path.join(CSVDIR, name)
    if not os.path.exists(p):
        return None
    rows = []
    with open(p, encoding="utf-8-sig", errors="ignore") as f:
        r = csv.reader(f)
        data = [row for row in r if row]
    # 找到含数据的数值块：取最后两列意义下的时间+信号
    # Maxwell 导出通常为：header 行 + 数据行，首列 Time
    if len(data) < 2:
        return None
    hdr = data[0]
    tcol = 0
    signals = []
    for i, h in enumerate(hdr):
        try:
            float(data[1][i]); signals.append(i)
        except Exception:
            pass
    t = np.array([float(r[tcol]) for r in data[1:] if r])
    cols = {hdr[i]: np.array([float(r[i]) for r in data[1:] if r]) for i in signals}
    return t, cols

def rms(x):
    return float(np.sqrt(np.mean(x**2))) if len(x) else 0.0

def metrics():
    out = {}
    # 反电动势（空载，取后一个周期排除启动暂态）
    bemf = load_csv("bemf.csv")
    if bemf:
        t, c = bemf
        # 取 t>0.01s 段（100Hz 一个周期=0.01s）
        m = t > 0.01
        if m.sum() == 0: m = np.ones_like(t, bool)
        va = c.get("WindingA.Voltage", np.zeros_like(t))[m]
        vb = c.get("WindingB.Voltage", np.zeros_like(t))[m]
        vc = c.get("WindingC.Voltage", np.zeros_like(t))[m]
        out["bemf_rms_line"] = rms(va - vc/2 - vb/2)  # 线电势近似
        out["bemf_rms_phase"] = rms(va)
        out["bemf_peak_phase"] = float(np.max(np.abs(va)))
    # 负载转矩
    tl = load_csv("tq_load.csv")
    if tl:
        t, c = tl
        m = t > 0.01
        if m.sum() == 0: m = np.ones_like(t, bool)
        tq = c.get("Moving1.Torque", np.zeros_like(t))[m]
        out["T_avg"] = float(np.mean(tq))
        out["T_max"] = float(np.max(tq))
        out["T_min"] = float(np.min(tq))
        out["T_ripple_pct"] = float((np.max(tq)-np.min(tq))/abs(np.mean(tq))*100) if np.mean(tq) else 0.0
    # 空载转矩（齿槽）
    tn = load_csv("tq_noload.csv")
    if tn:
        t, c = tn
        m = t > 0.01
        if m.sum() == 0: m = np.ones_like(t, bool)
        tq0 = c.get("Moving1.Torque", np.zeros_like(t))[m]
        out["cogging_peak_Nm"] = float(np.max(np.abs(tq0)))
    return out

res = metrics()
ok = bool(res)
res["source"] = "ANSYS Maxwell 2021R1 Transient (real FEA)"
res["status"] = "OK" if ok else "NO_DATA: 请先在本机运行 solve_25Nm_SPMSM.py"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2)
print(json.dumps(res, indent=2, ensure_ascii=False))
