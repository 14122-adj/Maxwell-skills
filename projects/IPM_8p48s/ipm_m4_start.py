#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPM 8p48s M4 —— 起动工况（机械瞬态，401 点 / 200 ms）

为什么要单独立 M4（与 M1'–M3' 的口径差异）
----------------------------------------
M1'–M3' 是**稳态**：`Consider Mechanical Transient=False`，转速被钉死在 1500 rpm，
求解器从不积分 `J·dω/dt = T_em − T_load`。后果是 t=0 的第一个采样点就已经是额定
转矩——M3' 的 `tq_load.csv` 首行是 26.58 N·m，整条曲线里根本不存在"从零上升"。
（2026-11-24 用户提出「为什么没有转矩从零开始上升的曲线」，根因即此。）

M4 是**机械瞬态**：初速 0、给转动惯量、转速由转矩积分得出，才画得出起动曲线。
参数名与平铺结构取自本机 `MaxwellScriptingGuide.pdf` P758–760 官方示例：

    Array("NAME:Band", "Move Type:=", "Rotate", ...,
          "Consider Mechanical Transient:=", true,
          "Angular Velocity:=", "0deg_per_sec",      # 机械瞬态下它是**初始**转速
          "Moment of Inertia:=", "1", "Damping:=", "0",
          "Load Torque:=", "0NewtonMeter", "Objects:=", Array("band"))

注意两点（都踩过）：① `Moment of Inertia` **不写单位**，按 SI 数值给；
② 机械瞬态下 `Angular Velocity` 不再是"恒转速"，而是 t=0 的初速，单位 deg_per_sec。

时间设置（用户要求「做到和现在的求解时间相同」）
--------------------------------------------
    现在 M1'–M3'：StopTime 0.02 s / TimeStep 0.05 ms → 400 步 = 401 点
    M4：         StopTime 0.20 s / TimeStep 0.5 ms → 400 步 = 401 点

步数与采样点数完全相同，单步非线性求解规模不变；再用
`SaveFieldsType="None"`（M4 只取转矩，不需要场快照）抵消机械瞬态每步的
band remesh + 运动方程积分开销。

转动惯量 J（定源）
----------------
0.0092 kg·m² —— 转子本体（硅钢叠片 + 16 块磁钢，Ø92.325 mm × 叠厚 160 mm）解析估算：

    硅钢：V = π·0.0461625²·0.16 − 16·(0.013·0.003·0.16) = 9.71e-4 m³，ρ=7650 → 7.43 kg
          J = ½·7.43·0.0461625²                       = 7.92e-3
    磁钢：V = 9.98e-5 m³，ρ=7500 → 0.749 kg，r_eff ≈ 0.0415
          J = 0.749·0.0415²                            = 1.29e-3
          合计 J ≈ 9.2e-3 kg·m²
不含轴与联轴器（band 内只有转子本体）。起动时间量级
`t ≈ J·Δω/T ≈ 0.0092·157.08/25 ≈ 58 ms`，200 ms 窗口约为其 3.5 倍。

电流口径
--------
沿用 M3' 的**固定频率**三相正弦（100 Hz = 4 对极 × 1500 rpm），即开环起动：
定子磁场以同步速旋转、转子从静止被牵入同步。因此曲线会先冲击、再振荡收敛，
这正是同步电机起动的典型形状。不引用 `Moving1.Position` 做闭环，避免引入
未在本机验证过的位置反馈表达式（反自演：未验证的写法不进主路径）。

用法
----
    python ipm_m4_start.py                        # 只生成 + 语法自检
    python ipm_m4_start.py --run                  # 真机建模 + 求解 + 导出
    python ipm_m4_start.py --run --bemf 127.744   # 指定实测 BEMF 插值 Imax
    python ipm_m4_start.py --j 0.02 --load 25     # 换惯量 / 带载起动（敏感性）

输出（TEMP 在 D:/ANSYS_Run，汇总 JSON 在 projects/results/ipm8p48s）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ipm_build  # noqa: E402
import ipm_geom  # noqa: E402
import ipm_m3_load  # noqa: E402

AEDT = r"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe"
RUN_DIR = r"D:/ANSYS_Run"
RESULTS = os.path.join(_ROOT, "projects", "results", "ipm8p48s")

P_PAIRS = 4
RPM_SYNC = 1500.0
F_ELEC = P_PAIRS * RPM_SYNC / 60.0        # 100 Hz
OMEGA_M_SYNC = 2.0 * math.pi * RPM_SYNC / 60.0   # 157.08 rad/s

# 转动惯量定源（见模块 docstring 推导），kg·m²
J_ROTOR = 0.0092

# 时间口径：与 M1'–M3' 同为 400 步 / 401 点
STOP_TIME = "0.2s"
TIME_STEP = "0.0005s"


def compute_currents_closed_loop(imax: float, phi_deg: float, pole_pairs: int) -> dict:
    """位置闭环（自同步）三相电流 —— 电流矢量锁在转子磁极 q 轴。

    为什么必须提供这条路径（2026-11-24 M4 首跑实测）
    ---------------------------------------------
    首跑用固定 100 Hz 开环，结果转子**根本没起来**：转速峰值 59.3 rpm、
    末段 −8.1 rpm，转矩在 ±33.9 N·m 之间来回摆、末段均值 0.38 N·m，
    `position.csv` 停在 358.7° 附近抖动。这不是数值问题——
    **PMSM 没有阻尼绕组，定子磁场以 1500 rpm 旋转时无法自起动**，
    转子只能被正负交替的转矩原地拉扯。异步电机能自起动靠的是鼠笼；
    PMSM 要么带阻尼笼，要么由变频器从低频牵入，要么用编码器闭环。

    本函数实现的就是第三种（等价于伺服驱动器）：令
        θ_e = p · θ_m，   i_A = −Imax·sin(θ_e + φ)
    转子转到哪，电流矢量就跟到哪，始终与磁极正交 ⇒ 恒定正向转矩 ⇒ 平滑加速。

    单位：`Moving1.Position` 在本机 2021.1 实测是 **deg**
    （M4 首跑 `position.csv` 表头 `"Moving1.Position [deg]"`，且 0.5 ms 值
    0.0218° 与 14.95 rpm 的积分自洽），因此 `p*Position` 已是电角度数，
    进 `sin` 前要乘 `pi/180`。

    注意 `pole_pairs` 是**极对数**（8 极 → 4 对），不是极数 `cfg.poles`。
    写成 8 会让电角翻倍、驱动频率错一倍——2026-11-24 现场踩过。
    """
    def expr(ph_deg: float) -> str:
        rad = math.radians(ph_deg)
        if abs(rad) < 1e-12:
            tail = ""
        elif rad < 0:
            tail = "-%.9f" % abs(rad)
        else:
            tail = "+%.9f" % rad
        return "-%.6f*sin(%d*Moving1.Position*pi/180%s)" % (imax, pole_pairs, tail)

    return {"A": expr(phi_deg), "B": expr(phi_deg - 120.0),
            "C": expr(phi_deg + 120.0)}


def compute_currents_chirp(imax: float, phi_deg: float, f0_hz: float,
                           f1_hz: float, t_ramp_s: float) -> dict:
    """变频起动（线性扫频 / V-f 起动）—— 让定子频率从 f0 爬到 f1 再保持。

    为什么最终是这条路（2026-11-24 两次真机否证）
    --------------------------------------------
    ① **开环固定 100 Hz**：转子转速峰值 59.3 rpm、末段 −8.1 rpm，转矩 ±33.9 N·m
       正负交替、均值 0.38 N·m —— PMSM 无阻尼绕组，静止转子追不上 1500 rpm 的
       旋转磁场，这是物理限制而非数值问题。
    ② **位置闭环 `i=−Imax·sin(p·Moving1.Position+φ)`**：转矩只有 55 µN·m、
       位置末值 0.00029°，转子纹丝不动 ⇒ **`Moving1.Position` 在 winding 电流
       表达式里未被实时求值**（当成常量 0），三相退化成固定直流 ⇒ 合成磁动势静止。
       这条路在本机 2021.1 上不可用。

    ③ 本函数：既然不能靠位置反馈，就让**频率自己爬**。等价于变频器 V/f 起动：
       瞬时频率  f(t) = f0 + k·min(t, T)，k = (f1−f0)/T
       相位      θ(t) = 2π·[f0·t + k·min(t, T)²/2]
       `min()` 实现"爬到 f1 就封顶"，t>T 段 θ 线性增长 ⇒ 恒频 100 Hz 稳态。
       纯时间函数，不依赖任何反馈变量。

    参数：f0=2 Hz（30 rpm，起转）、f1=100 Hz（1500 rpm 同步速）、
    t_ramp=0.12 s 爬坡 + 余下 0.08 s 稳态，正好覆盖 0.2 s 窗口。
    """
    k = (f1_hz - f0_hz) / t_ramp_s

    def expr(ph_deg: float) -> str:
        rad = math.radians(ph_deg)
        if abs(rad) < 1e-12:
            tail = ""
        elif rad < 0:
            tail = "-%.9f" % abs(rad)
        else:
            tail = "+%.9f" % rad
        # 2*pi*(f0*Time + k*min(Time,T)^2/2)
        return ("-%.6f*sin(2*pi*(%.6f*Time+%.6f*min(Time,%.6f)*min(Time,%.6f))%s)"
                % (imax, f0_hz, 0.5 * k, t_ramp_s, t_ramp_s, tail))

    return {"A": expr(phi_deg), "B": expr(phi_deg - 120.0),
            "C": expr(phi_deg + 120.0)}


def build_solve_script(aedt_out: str, csvdir: str, log_out: str) -> str:
    """段2：打开未求解工程 → Analyze → 导出转矩 / 转速 / 位置。

    转速与位置不是"顺便导"：它们是机械瞬态**真的生效了**的硬证据。
    若 `Consider Mechanical Transient` 被静默丢弃，转速会是一条 1500 rpm 直线，
    一眼可辨；只导转矩则无法区分"没起来"和"起来了但转矩小"。
    """
    L = []
    A = L.append
    A("# -*- coding: utf-8 -*-")
    A("# IPM 8p48s M4 起动求解 —— 由 projects/IPM_8p48s/ipm_m4_start.py 生成，勿手改。")
    A("import os")
    A("import time")
    A("import traceback")
    A("")
    A('LOG = r"' + log_out + '"')
    A('AEDT_IN = r"' + aedt_out + '"')
    A('CSVDIR = r"' + csvdir + '"')
    A("_lines = []")
    A("")
    A("")
    A("def log(s):")
    A("    _lines.append(str(s))")
    A("    try:")
    A('        f = open(LOG, "w")')
    A('        f.write("\\n".join(_lines))')
    A("        f.close()")
    A("    except Exception:")
    A("        pass")
    A("")
    A("")
    A("def data_rows(path):")
    A("    n = 0")
    A("    try:")
    A('        f = open(path)')
    A("        for ln in f:")
    A("            s = ln.strip()")
    A("            if not s:")
    A("                continue")
    A('            head = s.split()[0].strip(",")')
    A("            try:")
    A("                float(head)")
    A("                n += 1")
    A("            except ValueError:")
    A("                pass")
    A("        f.close()")
    A("    except Exception:")
    A("        return -1")
    A("    return n")
    A("")
    A('log("=== IPM 8p48s M4 start-up solve ===")')
    A("t_all = time.time()")
    A("try:")
    A("    os.makedirs(CSVDIR)")
    A("except Exception:")
    A("    pass")
    A("")
    A("try:")
    A("    oProject = oDesktop.OpenProject(AEDT_IN)")
    A('    oDesign = oProject.SetActiveDesign("Motor_Design")')
    A('    log("OPEN_OK " + AEDT_IN)')
    A("except Exception:")
    A('    log("OPEN_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    oProject = None")
    A("    oDesign = None")
    A("")
    A("if oDesign is None:")
    A('    log("=== end (no design) ===")')
    A("else:")
    A("    # 机械瞬态是否真生效：从求解设置回读 band 属性")
    A("    try:")
    A('        ms = oDesign.GetModule("ModelSetup")')
    A('        log("MOTION_NAMES=" + str(list(ms.GetMotionSetupNames())))')
    A("    except Exception:")
    A('        log("MOTION_NAMES_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A("    ok = True")
    A("    t0 = time.time()")
    A("    try:")
    A('        oDesign.Analyze("Setup1")')
    A('        log("ANALYZE_OK " + str(round(time.time() - t0, 1)) + "s")')
    A("    except Exception:")
    A("        ok = False")
    A('        log("ANALYZE_FAIL " + str(round(time.time() - t0, 1)) + "s " +')
    A('            repr(traceback.format_exc().splitlines()[-1]))')
    A("    if not ok:")
    A('        log("skip export (solve failed)")')
    A("    else:")
    A('        rep = oDesign.GetModule("ReportSetup")')
    A('        CTX = ["NAME:Context", "SimValueContext:=", [1, 0, 2, 0, False, False,')
    A("               -1, 1, 0, 1, 1, \"\", 0, 0]]")
    A("")
    A("        def export(name, expr, fname):")
    A("            try:")
    A('                rep.CreateReport(name, "Standard", "Rectangular Plot",')
    A('                                 "Setup1 : Transient", CTX, ["Time:=", ["All"]],')
    A('                                 ["X Component:=", "Time", "Y Component:=", [expr]], [])')
    A("            except Exception:")
    A('                log("create " + name + " raised -> export anyway")')
    A('            path = CSVDIR + "/" + fname')
    A("            try:")
    A("                rep.ExportToFile(name, path)")
    A("            except Exception:")
    A("                rep.ExportToFile(name, path, True)")
    A('            return fname + " rows=" + str(data_rows(path))')
    A("")
    A("        for (_n, _e, _f) in ((\"TqM4\", \"Moving1.Torque\", \"tq_start.csv\"),")
    A("                            (\"SpdM4\", \"Moving1.Speed\", \"speed.csv\"),")
    A("                            (\"PosM4\", \"Moving1.Position\", \"position.csv\")):")
    A("            try:")
    A('                log("export " + _e + " -> " + export(_n, _e, _f))')
    A("            except Exception:")
    A('                log("EXPORT_" + _n + "_FAIL: " +')
    A('                    repr(traceback.format_exc().splitlines()[-1]))')
    A("    try:")
    A("        oProject.Save()")
    A('        log("FINAL_SAVE_OK")')
    A("    except Exception:")
    A('        log("FINAL_SAVE_FAIL: " + repr(traceback.format_exc().splitlines()[-1]))')
    A('log("TOTAL " + str(round(time.time() - t_all, 1)) + "s")')
    A('log("=== end ===")')
    return "\n".join(L) + "\n"


def read_csv(path: str):
    """读 Maxwell 导出的两列 CSV（可能带引号、可能含表头）→ [(t, v), ...]。"""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            s = ln.strip()
            if not s:
                continue
            parts = s.replace('"', "").split(",")
            if len(parts) < 2:
                continue
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return rows


def summarize(rows, unit_scale: float = 1.0) -> dict:
    """起动曲线摘要：起点、峰值、末段稳态值、起动时间（首次达 95% 稳态）。"""
    if len(rows) < 5:
        return {"status": "NO_DATA", "n": len(rows)}
    ys = [v * unit_scale for _t, v in rows]
    ts = [t for t, _v in rows]
    tail = ys[int(len(ys) * 0.8):]
    y_ss = sum(tail) / len(tail)
    y_max = max(ys)
    y_min = min(ys)
    t_peak = ts[ys.index(y_max)]
    # 起动时间：首次进入 95% 稳态带并一直留在带内
    band = abs(y_ss) * 0.05 + 1e-9
    t_set = None
    for i in range(len(ys)):
        if all(abs(v - y_ss) <= band for v in ys[i:]):
            t_set = ts[i]
            break
    return {
        "status": "OK",
        "n": len(rows),
        "t_span_s": [ts[0], ts[-1]],
        "y_start": ys[0],
        "y_peak": y_max,
        "t_peak_s": t_peak,
        "y_min": y_min,
        "y_ss": y_ss,
        "t_settle_s": t_set,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="IPM 8p48s M4 起动工况（机械瞬态 401 点）")
    ap.add_argument("--bemf", type=float, default=127.744,
                    help="实测相 BEMF RMS(V)，插值 Imax（默认 cps=10 实测值）")
    ap.add_argument("--imax", type=float, default=None, help="显式峰值电流(A)，优先于 --bemf")
    ap.add_argument("--phi", type=float, default=0.0, help="相对 BEMF 反相点偏移（deg）")
    ap.add_argument("--j", type=float, default=J_ROTOR, help="转动惯量 kg·m²（默认转子本体估算值）")
    ap.add_argument("--load", type=float, default=0.0, help="负载转矩 N·m（默认 0 = 空载起动）")
    ap.add_argument("--damping", type=float, default=0.0, help="阻尼 N·m·s/rad（默认 0）")
    ap.add_argument("--stop", default=STOP_TIME, help="StopTime（默认 0.2s）")
    ap.add_argument("--dt", default=TIME_STEP, help="TimeStep（默认 0.0005s）")
    ap.add_argument("--case", default="start", help="工况标签，用于工程/CSV/JSON 命名")
    ap.add_argument("--mode", default="chirp", choices=("chirp", "open", "closed"),
                    help="chirp=变频起动（默认，物理可行）；"
                         "open=固定 100Hz 开环（PMSM 无阻尼笼，已真机证否）；"
                         "closed=位置反馈（本机 Moving1.Position 不进表达式，已证否）")
    ap.add_argument("--f0", type=float, default=2.0, help="变频起始频率 Hz（默认 2）")
    ap.add_argument("--f1", type=float, default=F_ELEC, help="变频终止频率 Hz（默认 100）")
    ap.add_argument("--ramp", type=float, default=0.12, help="频率爬坡时长 s（默认 0.12）")
    ap.add_argument("--run", action="store_true", help="生成后调用 ansysedt 真机求解")
    args = ap.parse_args(argv)

    if args.imax is not None:
        imax, src = args.imax, "explicit"
    else:
        imax, src = ipm_m3_load.imax_from_bemf(args.bemf), "bemf_interp@E=%.4f" % args.bemf

    phi_abs = ipm_m3_load.BEMF_OFFSET_DEG + args.phi
    cfg = ipm_geom.IPMConfig()
    if args.mode == "closed":
        # 极对数 = 极数 // 2（8 极 → 4 对），电角 = 4 × 机械角
        currents = compute_currents_closed_loop(imax, phi_abs, cfg.poles // 2)
    elif args.mode == "chirp":
        currents = compute_currents_chirp(imax, phi_abs, args.f0, args.f1, args.ramp)
    else:
        currents = ipm_m3_load.compute_currents(imax, phi_abs, -1)

    aedt_out = "%s/IPM_8p48s_M4_%s.aedt" % (RUN_DIR, args.case)
    build_py = "%s/ipm_m4_build_%s.py" % (RUN_DIR, args.case)
    solve_py = "%s/ipm_m4_solve_%s.py" % (RUN_DIR, args.case)
    csvdir = "%s/csv_ipm_m4_%s" % (RUN_DIR, args.case)
    build_log = "%s/ipm_m4_build_%s.log" % (RUN_DIR, args.case)
    solve_log = "%s/ipm_m4_solve_%s.log" % (RUN_DIR, args.case)

    # 机械瞬态字面量：J 不带单位（官方示例写法），初速 0，负载转矩按 --load
    motion = {
        "init_speed": "0deg_per_sec",
        "inertia": ("%.6f" % args.j).rstrip("0").rstrip("."),
        "damping": ("%.6f" % args.damping).rstrip("0").rstrip(".") or "0",
        "load_torque": ("%.6f" % args.load).rstrip("0").rstrip(".") + "NewtonMeter",
    }

    build_text = ipm_build.build_script(
        cfg, aedt_out, currents=currents, case_tag="M4_start_" + args.case,
        motion=motion, stop_time=args.stop, time_step=args.dt, save_fields="None")
    build_text = build_text.replace(
        'LOG = r"' + ipm_build.LOG + '"', 'LOG = r"' + build_log + '"')
    with open(build_py, "w", encoding="utf-8") as fh:
        fh.write(build_text)
    compile(build_text, build_py, "exec")

    solve_text = build_solve_script(aedt_out, csvdir, solve_log)
    with open(solve_py, "w", encoding="utf-8") as fh:
        fh.write(solve_text)
    compile(solve_text, solve_py, "exec")

    n_steps = int(round(_sec(args.stop) / _sec(args.dt)))
    t_acc = args.j * OMEGA_M_SYNC / max(imax * 1.0, 1e-9)   # 量级参考，非预测值

    _DRIVE_DESC = {
        "chirp": "变频起动 %g→%g Hz / %g s 爬坡后保持（等价变频器 V/f，纯时间函数）"
                 % (args.f0, args.f1, args.ramp),
        "open": "固定 %g Hz 开环（PMSM 无阻尼笼，已真机证否：转子起不来）" % F_ELEC,
        "closed": "位置反馈 i=−Imax·sin(p·Position+φ)（已真机证否：Position 不进表达式）",
    }
    print("M4 起动工况")
    print("  Imax = %.6f A (src=%s), φ_abs=%+.1f°, sign=-1" % (imax, src, phi_abs))
    print("  驱动   : %s" % _DRIVE_DESC[args.mode])
    print("  电流   : %s" % currents["A"])
    print("  机械瞬态: J=%s kg*m^2, Damping=%s, Load Torque=%s, 初速 0"
          % (motion["inertia"], motion["damping"], motion["load_torque"]))
    print("  时间   : StopTime=%s / TimeStep=%s → %d 步 = %d 点（与 M1'-M3' 同规模）"
          % (args.stop, args.dt, n_steps, n_steps + 1))
    print("  SaveFieldsType=None（只取转矩，不存场快照）")
    print("  量级参考: J·ω_sync/Imax = %.1f ms" % (t_acc * 1e3))
    print("建模脚本：%s（%.1f KB）" % (build_py, len(build_text) / 1024.0))
    print("求解脚本：%s（%.1f KB）" % (solve_py, len(solve_text) / 1024.0))
    print("工程：%s" % aedt_out)
    print("CSV：%s" % csvdir)
    print("语法自检：CPython compile OK")

    os.makedirs(RESULTS, exist_ok=True)
    meta = dict(
        case=args.case, stage="M4 起动（机械瞬态 401 点）",
        excitation=dict(
            current_A=imax, current_unit="A_peak", phase_abs_deg=phi_abs,
            frequency_hz=F_ELEC, omega_rad_s=ipm_m3_load.OMEGA_E,
            current_sign=-1, source=src, expressions=currents,
            mode={"chirp": "vf_chirp_start",
                  "open": "open_loop_fixed_frequency",
                  "closed": "position_feedback_unsupported"}[args.mode],
            freq_start_hz=args.f0 if args.mode == "chirp" else F_ELEC,
            freq_end_hz=args.f1 if args.mode == "chirp" else F_ELEC,
            ramp_s=args.ramp if args.mode == "chirp" else None,
            note={"chirp": "变频起动：f(t)=f0+k·min(t,T)，θ(t)=2π[f0·t+k·min(t,T)²/2]；"
                           "等价变频器 V/f 起动，纯时间函数不依赖反馈",
                  "open": "固定 100 Hz 开环；PMSM 无阻尼绕组无法自起动（真机证否）",
                  "closed": "位置反馈 Moving1.Position 未被实时求值（真机证否）"}[args.mode]),
        motion=dict(
            consider_mechanical_transient=True, init_speed_deg_per_sec=0.0,
            moment_of_inertia_kg_m2=args.j, damping=args.damping,
            load_torque_nm=args.load,
            j_source="转子本体解析估算：硅钢 ½·7.43·0.0461625² + 磁钢 0.749·0.0415²；"
                     "不含轴与联轴器"),
        timing=dict(stop_time=args.stop, time_step=args.dt,
                    n_steps=n_steps, n_points=n_steps + 1,
                    save_fields_type="None",
                    note="与 M1'-M3' 同为 400 步 401 点；M4 不存场以抵消 remesh 开销"),
        build_script=build_py, solve_script=solve_py, aedt=aedt_out,
        csvdir=csvdir, generated=True, solved=False)
    with open(os.path.join(RESULTS, "m4_start_%s.json" % args.case), "w",
              encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    if args.run:
        for script, label in ((build_py, "build"), (solve_py, "solve")):
            cmd = [AEDT, "-RunScriptAndExit", script]
            print("运行 %s：%s" % (label, " ".join(cmd)))
            rc = subprocess.call(cmd)
            print("ansysedt %s rc=%d" % (label, rc))
            if rc != 0:
                return rc
        meta["solved"] = True
        # 后处理：转矩曲线摘要
        tq = read_csv(os.path.join(csvdir, "tq_start.csv"))
        spd = read_csv(os.path.join(csvdir, "speed.csv"))
        meta["torque_summary"] = summarize(tq)
        meta["speed_summary"] = summarize(spd)
        with open(os.path.join(RESULTS, "m4_start_%s.json" % args.case), "w",
                  encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        print("转矩摘要：%s" % json.dumps(meta["torque_summary"], ensure_ascii=False))
        print("转速摘要：%s" % json.dumps(meta["speed_summary"], ensure_ascii=False))
    return 0


def _sec(v: str) -> float:
    """'0.2s' / '0.0005s' → 秒。"""
    s = v.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1e3
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


if __name__ == "__main__":
    raise SystemExit(main())
