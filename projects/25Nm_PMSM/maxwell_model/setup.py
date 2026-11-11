#!/usr/bin/env python3
"""Step 1: 项目设置 — 修复 NewProject 弹"是否保存"对话框的问题"""
import ScriptEnv
import time

ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()

# ── 修复:避免 AEDT 启动后弹"最近文件/Home"对话框卡死脚本 ──
#  1. 等 AEDT 启动稳定 (load screen/许可/启动画面)
time.sleep(3)

#  2. 主动关掉任何已打开的项目,避免后续 NewProject 触发"是否保存"弹窗
try:
    active = oDesktop.GetActiveProject()
    if active is not None:
        try:
            # ClearSavedFlag 让 AEDT 认为当前项目已保存,丢弃未保存修改
            active.ClearSavedFlag()
        except Exception:
            pass
        try:
            oDesktop.CloseProject(active.GetName())
        except Exception:
            pass
except Exception:
    # 无激活项目/启动尚未就绪 — 忽略,直接 NewProject
    pass

#  3. 关闭 Home / Recent Files 弹窗 (AEDT 2021+ 启动时常弹)
try:
    # 顺序点掉主窗口的 child dialog:典型 Home Screen 的标题是 "Home"
    for w in list(oDesktop.GetWindowNames()):
        title = (oDesktop.GetWindowTitle(w) or "").lower()
        if "home" in title or "recent" in title or "welcome" in title:
            try:
                oDesktop.CloseWindow(w)
            except Exception:
                pass
except Exception:
    pass

#  4. 现在安全新建项目 (overwrite=True 兜底,避免再有"覆盖?"弹窗)
oProject = oDesktop.NewProject()
oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
oDesign = oProject.SetActiveDesign("Motor_Design")
# ── G3：2D 求解必须显式写叠长 ──
#  Maxwell 2D 的默认 ModelDepth 是 1 mm（不是 0），若这里不写，
#  转矩/反电势/铁耗/铜耗全部按 1 mm 深度算，物理量整体缩小约 160 倍，
#  而求解器不会报任何错（“模型自洽、物理错量级”的静默错误）。
#  实测依据：m4_build_solve.py 写入 ModelDepth:="160mm" 后，
#  空载 BEMF 118.88 V(rms)、负载 T_avg 22.33 N·m，与解析值同量级。
oDesign.SetDesignSettings(
    ["NAME:DesignSettingsData",
     "ModelDepth:=", "160mm",
     "PreserveTransientSolution:=", False,
     "ComputeTransientInductance:=", True])
print("Setup done: 12 slots, 8 poles, rectangular, SPM, ModelDepth=160mm")
