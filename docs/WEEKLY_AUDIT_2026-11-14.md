# 周检 2026-11-14 — 技能可用（M1–M4 + M6 + 模板路径）/ 设计不合格（齿槽 27.37%）

> 触发：大哥手动触发。基线 HEAD `1af9ddd`（2026-11-14 13:47）。
> **一句话结论**：技能在真机上能画、能解、能复现（M1–M4 全绿，401 点，BEMF 与基线差 −0.02%）；
> **M8 梨形槽只有规格文档、零代码零生成物**，齿槽仍是 **6.84307 N·m / 27.37%**，
> 距 5% 判据差 5.5 倍 —— **设计不合格**。两者不可混为一谈。

---

## 0. 判定（两条口径分开写，禁止互相顶替）

| 判定 | 结论 | 依据 |
|---|---|---|
| **技能可用** | ✅ **可用** | M1 真机 rc=0；M2 24 图元；M3 材料/绕组/边界/Setup 全项；M4 401 点、BEMF 118.86 V（−0.02%）、齿槽 6.84307 N·m、负载 22.3435 N·m（−10.63%）；M6 报告含 §11 交叉校验；模板路径与手写路径等价（+0.04% / −0.365%） |
| **设计合格** | ❌ **不合格** | M8 梨形槽 **not started**（规格已冻结、实现 0%）；齿槽 **27.37% 额定**，判据 ≤5%（目标 ≤1.25 N·m）→ 差 **5.47 倍** |
| **下一步** | M8 梨形槽 → 斜槽 / 极弧 / 槽口 FEA 扫描 | 见 `WEEKLY_GOALS.md` G6–G8 |

---

## 1. 总览表

| 门槛 | 判据 | 实测（2026-11-14 真机/静态） | 结论 |
|---|---|---|---|
| **M1–M4 + M8（核心能力）** | 真机建模 → 求解 → 齿槽优化 | M1–M4 全项通过；**M8 未开工** | **4/5，M8 ❌** |
| M1 Maxwell 启动 | `-RunScriptAndExit` 生成工程 | rc=0；`AEDT_VERSION=2021.1.0`；探针脚本写出 `m1_probe.txt` | ✅ |
| M2 整机几何 | 24 个 2D 图元 + 关键尺寸 | `N_SHEETS=24 / N_SOLIDS=0`，名单 24 项逐一对齐；75.0/46.5/45.825/46.1625 均在几何内 | ✅ |
| M3 材料/绕组/边界/Setup | 160 mm、M270×2、12 Coil、3 Winding、VP、Setup1 | `ModelDepth='160mm'`×1；`M270_35A`×2 + `NdFe35_N/S`×8 + `copper`×12；`BoundType='Coil'`×12、`'Winding Group'`×3；`VectorPotential1` + `Edges(7)`；`Setup1` 0.02 s / 50 µs | ✅ |
| M4 空载 401 点 | BEMF ±10%、齿槽 ≤6.843 N·m | 401 点×4 CSV（两条路径）；BEMF **118.859 V**（独立重算，−0.02%）；齿槽 **6.84307 N·m / 27.372%**；不平衡 0.22%（独立口径） | ✅（但齿槽=设计层不达标） |
| **M8 梨形槽** | 槽面积 93.0±2%、线圈 72±5%、Arc 底、12 槽、齿槽 ≤5% | **无 `.aedt` 生成物**；`main.py` pear 分支仍是旧 7 点浅梨形；`build_config` 仍是 `RECTANGULAR` | ❌ **not started** |
| M5 负载 | `T_avg` 25±20% | **22.3435 N·m = −10.63%**（独立重算） | ✅ |
| M6 报告 | §11 FEA 交叉校验 | 491,996 B / 13 表 / 7 内嵌图 / `figures` 9 张；含 6.84、22.33 | ✅ |
| 模板路径等价 | 与手写 ±10% | BEMF 118.884 V（+0.04%）、齿槽 6.81809 N·m（−0.365%）、401 行×4 | ✅ |

---

## 2. M1 — 真机启动（本次重跑，非引用历史）

```
"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe" -RunScriptAndExit "D:\ANSYS_Run\audit_20261114\m1_probe.py"
→ EXIT=0，耗时 31 s
```

探针输出（`D:\ANSYS_Run\audit_20261114\m1_probe.txt`）：

| 项 | 值 |
|---|---|
| `oDesktop.GetVersion()` | **2021.1.0** |
| `oDesktop.GetProjectDirectory()` | **`D:\ANSYS_Run\projects`** ✅ 与要求一致 |
| `oDesktop.GetPersonalLibDirectory()` | `D:\ANSYS_Run\projects\PersonalLib` |

> 这条同时关闭了「默认工程目录是否已改」的检查项 —— 不是读 XML 猜的，是**从 AEDT 进程里读回来的**。

---

## 3. M2 — 整机几何（真机枚举 + 面积反算）

`N_SHEETS = 24`、`N_SOLIDS = 0`，名单：
`Region, StatorOuter, RotorOuter, PM_1..PM_8, Band, Coil_1..Coil_12`。

| 对象 | 手写 `M5_25Nm` | 模板 `T4_tpl_noload` | 解析值 | 判读 |
|---|---:|---:|---:|---|
| Region | 11,053.3503（2 faces） | 11,053.3503 | π·95² − 定子 − 12×线圈 − Band = 11,053.35 | ✅ 面积守恒（偏差 <0.01%） |
| StatorOuter | 9,645.3819 | 9,645.3819 | 10,878.55 − 12×103.25 = 9,639.55（+0.06%，差值=槽口 0.2 mm 重叠段） | ✅ |
| RotorOuter | **6,047.9819** | **5,341.1213** | — | ⚠️ 两路径**不同源**，差 706.86 mm² = π·15²（内径 13.24 vs 20.01 mm） |
| Coil_1 | 79.9568 | 79.9568 | 0.7744 × 103.25 = 79.96 | ✅ |
| PM_1 | 59.7507 | 59.7513 | 59.79（−0.07%） | ✅ |
| Band | 6,694.6598 | 6,694.6598 | — | ✅ |

关键尺寸文本核验：`75.0`×15、`46.5`×8、`45.825`×2、`46.1625`×6（`M5_25Nm.aedt`）。
**槽面积实测基准 = 103.25 mm²**（矩形槽：颈 2.5×1.7 + 槽身 16.5×(2.5+9.5)/2）。

---

## 4. M3 — 材料 / 绕组 / 边界 / Setup

| 判据 | 实测 | 结论 |
|---|---|---|
| `ModelDepth='160mm'`（非 1 meter） | ×1（两份工程均 1 处） | ✅ |
| `M270_35A` ×2 | StatorOuter + RotorOuter | ✅ |
| `NdFe35_N/S` | PM_1/3/5/7 = N，PM_2/4/6/8 = S | ✅ |
| `copper` ×12 | Coil_1..Coil_12 | ✅ |
| `BoundType='Coil'` ×12 | 12 | ✅ |
| `BoundType='Winding Group'` ×3 | 3 | ✅ |
| `VectorPotential1` + `Edges(<id>)` | 块位于 L14018，`Edges(7)`（Region 单条外圆边） | ✅ |
| `Setup1`（Transient，0.02 s / 50 µs） | `StopTime='0.02s'`、`TimeStep='5e-05s'` | ✅ |
| 运动带 `MotionSetup1` | ×1 | ✅ |
| 激励枚举（真机） | 12×`Coil` + `WindingA/B/C Winding Group` | ✅ |

> 真机 `GetExcitations()` 顺序在两条路径上不同（`A_1,A_2,B_3,B_4…` vs `A_1,A_7,A_2,A_8…`），
> 属命名/枚举顺序差异，不影响数值（BEMF 差 0.02% 已证）。

---

## 5. M4 — 空载 401 点（**独立重算，不走工作区代码**）

方法与基线完全解耦：直接读 4 个 401 行原生 CSV，用中值差分 `V = −dλ/dt` 重算，
不调用 `ingest_fea.py`。脚本：`D:\ANSYS_Run\audit_20261114\verify_fea.py`。

| 量 | 基线（2026-11-13） | 独立重算（手写） | 偏差 | 独立重算（模板） | 偏差 |
|---|---:|---:|---:|---:|---:|
| 相 RMS 均值 | 118.8832 V | **118.8594 V** | −0.02% | **118.8840 V** | +0.0007% |
| 相 A / B / C | 118.8793 / 118.8887 / 118.8815 | 118.7687 / 118.7791 / **119.0303** | −0.09% / −0.09% / +0.13% | 118.7953 / 118.7988 / 119.0578 | 同左 |
| 齿槽峰峰值 | 6.84307 N·m | **6.84307 N·m** | 0.000% | **6.81809 N·m** | −0.365% |
| 齿槽 / 额定 | 27.372% | **27.372%** | — | 27.272% | — |
| 负载 `T_avg` | 22.3344 N·m | **22.3435 N·m** | +0.04% | — | — |
| 负载脉动 | 32.39% | 32.376% | −0.01 pp | — | — |
| 采样点 | 401 | 401（`flux_*.csv` 402 行=表头+401） | — | 401 | — |
| 三相不平衡 | 0.008% | **0.220%** | +0.21 pp | 0.221% | — |

**结论**：BEMF / 齿槽 / 负载三项全部落在 ±10%（实际 <0.4%）内，M4 可复现 ✅。
`.aedtresults` 侧有实解（`M5_25Nm` 23 MB、`T4_tpl_noload` 29 MB，`DV42_SOL41_V0.Data` / `DV72_SOL71_V0.Data`），
`WindingX_TrCrv.txt` 是 10 步环形缓冲（22 行），**401 点只能从导出 CSV 判**，这点别再拿 TrCrv 行数当证据。

---

## 6. M8 梨形槽 — ❌ **not started**（本次重点，结论明确）

### 6.1 五条独立证据

| # | 证据 | 事实 |
|---|---|---|
| 1 | 提交内容 | `1af9ddd` 只改 3 个文件：`docs/PEAR_SLOT_SPEC.md`(+104)、`DESIGN_PROGRESS.md`、`WEEKLY_GOALS.md`。**零代码** |
| 2 | 模板几何 | `scripts/main.py:261-300` 的 `pear` 分支仍是**旧 7 点浅梨形**：`x1 = x0+Hs0`、`x2 = x0+Hs0+Hs1`、`x3 = x0+Hs0+Hs1+Rs`，**无 `x4`、无肩部台阶（Bs0→Bs1）、`Arc StartIndex:=3`**，与表 2 的 11 点 / `Arc StartIndex:=4` 完全不符 |
| 3 | 机型配置 | `projects/25Nm_PMSM/gen_maxwell_model.py:52` 仍是 `SlotType.RECTANGULAR`，`slot_Bs0=2.5 / slot_Hs2=18.0 / slot_Bs2=9.5`；`scripts/motor_config.py` 梨形预设仍是 `Bs0=3.5 / Bs1=6.2 / Bs2=8.3 / Rs=4.15` |
| 4 | 生成物 | 全盘（含 `D:\ANSYS_Run`）**无任何 `T4_pear*.aedt` / `pear*.aedt`**；`find . -iname "*pear*"` 只命中规格文档 |
| 5 | `--check` | 8 个生成物 `[OK] 无漂移`（逐字一致）—— 这只证明"模板=生成物"，**不证明模板被改过**。别拿它当 M8 进展 |

### 6.2 规格自洽性复核（表 2 尺寸是对的）

| 项 | 公式 | 值 | 与规格 |
|---|---|---:|---|
| 颈 | 0.8×(48.0−46.3) | 1.36 | ✅ |
| 斜肩 | (6.0+9.5)/2×1.8 | 13.95 | ✅ |
| 直身 | 9.5×(54.25−49.8) | 42.275 | ✅ |
| 半圆底 | π·4.75²/2 | 35.437 | ✅ |
| **槽面积** | 合计 | **93.02 mm²** | ✅ 落 93.0±2% |
| 轭部 | 75−59.0 | 16.0 | ✅ |
| 线圈（0.88² 等比） | 0.7744×93.02 | **72.03** | ✅ 落 72±5% |

口径按「`Hs2` = 内径→槽底**最底端**」：`x3=54.25`、`x4=59.0`、总深 12.5、轭 16.0。
若改口「内径→圆心」，则 `x3=59.0`、`x4=63.75`、总深 17.25、轭 11.25 —— 本报告采用**前者**。

### 6.3 实施预警（本次新增，量化）

1. **弧段不采样会把线圈面积打穿判据**。现有线圈内缩是「绕形心 ×0.88 等比」
   （`main.py:401-405`），而 `_slot_pts` 给的是**11 个控制点**、底部是**直线弦**：
   该 11 边形面积 = **80.15 mm²**（半圆 35.437 被三角 22.5625 取代），
   ⇒ 线圈 = 0.7744×80.15 = **62.07 mm² = −13.8%**，直接撞穿 72±5%（68.4–75.6）。
   **必须在 `_slot_pts` 里给半圆补 ≥8 个采样点**（规格 §4 已写，但没写"不补会差多少"——差 13.8%）。
2. **等比内缩不会穿出槽壁**（规格担心的"切进半圆底"在此实现下不成立）：等比缩放对星形域必内含，
   且槽满率 = 40×π×1.45²/4 / 93.02 = 66.0/93.02 = **0.709 ≤ 0.78** ✅ —— 线径不必改。
3. **M8 验收要按解析槽面积判，不能按 `GetFaceArea` 反算**：槽口 0.2 mm 重叠在环带外，
   反算值会比解析值小 0.16/12 ≈ 0.013 mm²/槽（−0.17%），当前矩形槽同样差 0.49 mm²/槽（−0.5%）。
   预期 M8 生成后：`StatorOuter ≈ 9,764 mm²`（10878.55 − 12×92.86），±5 mm² 内即算对。
4. **齿槽主因是槽口，不是槽底形状**：现槽口 `Bs0=2.5 mm`，表 2 要 `0.8 mm`（缩到 32%）。
   齿槽峰峰值对槽口宽是强非线性（经验上 ∝ Bs0^1.5~2），**预期能压到个位数%，但不敢承诺 5%**
   —— 必须 FEA 说话。若梨形单独不够，按 G7 走斜槽/极弧。

### 6.4 Blocker 与桌面一键命令

| 项 | 内容 |
|---|---|
| Blocker | M8 梨形槽实现未启动 → 齿槽 27.37% ≥ 5%，**设计不合格** |
| 阻塞点 | ① `main.py` pear 分支需按 11 点 + `Arc(4,3)` 重写；② `_slot_pts` 需弧采样；③ `gen_maxwell_model.build_config` 需切 `PEAR` + 表 2 尺寸 |
| 桌面命令（改完代码后） | `"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe" -RunScriptAndExit "D:\ANSYS_Run\tpl_solve_noload.py"`（先跑 `python projects/25Nm_PMSM/gen_maxwell_model.py` 重生成） |
| 判定时点 | 生成 `.aedt` 后按 §6.3 第 3 条核面积，再解 401 点核齿槽 |

---

## 7. 次要检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 仓库完整性 | ✅ | `git fsck` rc=0（1 个 dangling blob，无损坏）；`main...origin/main` 同步；HEAD `1af9ddd` |
| 工作树 | ⚠️ 脏 | 9 改 + 2 未跟踪（`SKILL.md`、`mcp-maxwell/server.py`、3 个 `winding/coils.py`、`references/motor_design_guide.md`、`maxwell_bridge.py`、`motor_param_calc.py`、`winding_layout.py`；`?? .workbuddy/`、`?? 36slot_industrial/coils.py`） |
| 依赖安装 | ✅ | 复用 `D:\ANSYS_Run\audit_20261107\venv`（3.13.14，editable 装到工作区）；`pip install ruff` 后齐备 |
| `pytest` | ✅ | **289 passed / 2.67 s**（+142 vs 11-07 的 147，G1–G4 的护栏都进来了） |
| `ruff` | ✅ | ruff 0.17.5：`All checks passed!` |
| 生成物漂移 | ✅ | `gen_maxwell_model.py --check` → `[OK] 无漂移：8 个生成物与模板逐字一致` |
| 解析 + 报告链路 | ✅ 交叉校验 | `REPORT_25Nm_SPMSM.html` 491,996 B / 13 表 / 7 内嵌 PNG（`results/figures` 9 张）；含齿槽 6.84、`T_avg` 22.33、§11 十行对照 |
| 默认工程目录 | ✅ | 真机读出 `D:\ANSYS_Run\projects`（§2） |
| 文档一致性 | ⚠️ 4 处漂移 | 见 P6/P7 |

---

## 8. 问题清单

| ID | 严重度 | 问题 | 证据 | 验收 |
|---|---|---|---|---|
| **P1** | **blocker** | M8 梨形槽未实现，齿槽 27.37% 未动 | §6.1 五条 | 生成 `T4_pear.aedt`：槽面积 93.0±2%、线圈 72±5%、`Arc` 底、12 槽、无 intersect |
| **P2** | **major** | 照 11 控制点直接内缩 → 线圈 62.07 mm²（−13.8%），实测必撞 72±5% | §6.3-1（80.15 多边形面积） | `_slot_pts` 半圆 ≥8 采样点；生成物线圈面积 68.4–75.6 |
| **P3** | **major** | 齿槽 27.37% vs 判据 5%，差 5.47 倍（设计层） | `fea_results.json` `cogging.pass_5pct=false` | FEA 齿槽 ptp ≤1.25 N·m |
| P4 | minor | 两条路径转子内径不同源（13.24 vs 20.01 mm，面积差 706.86 = π·15²） | §3 面积表 | 统一 `rotor_id` 口径，或写明"铁芯内部不影响场" |
| P5 | minor | `fea_results.bemf_balance_pct=0.008%` 不可独立复现（同一 CSV 独立算得 0.220%，C 相偏高 0.13%） | §5 | 在报告脚注写清求导/重采样口径 |
| P6 | minor | 文档数值漂移：`DESIGN_PROGRESS` 记 `T4_tpl_noload` 767,290 B（实际 **958,509 B**）；G5 记线圈 75.24 mm²（实测 **79.9568**）；「9 图」vs 报告内嵌 **7** 张 | 文件系统 / 报告 | 改数或改口径 |
| P7 | minor | `SKILL.md:211` 示例仍写旧梨形尺寸（`Bs0=3.5 … Rs=4.15`），与表 2 冲突 | 文本 | 示例换成表 2 参数 |
| P8 | minor | 工作树 11 项未提交（含 `SKILL.md`、`mcp-maxwell/server.py`） | `git status` | 择机独立提交或丢弃 |
| P9 | info | 阶段看板 M0–M6 表缺 M7/M8 行 | `DESIGN_PROGRESS.md:352-360` | 本次已补 |

---

## 9. 历史误判复核（防止再被当事实）

| 旧结论 | 现状 |
|---|---|
| 「Band 必须薄环」 | ❌ 不成立（`6fca72c` 已推翻）；Band 6,694.66 mm² 正常 |
| 「`EditSetup` 丢运动」 | ❌ 不成立；`MotionSetup1` 在两条路径上都在 |
| 「齿槽 1.6%」 | ❌ 不成立；真值 **6.84307 N·m / 27.37%**，本次独立重算确认到小数点后 5 位 |
| 「沙箱无法启动 Maxwell = 环境限制」 | ❌ 不成立；本次真机 rc=0 / 31 s，M1–M4 全程可跑 |

---

## 附录 A — 复现命令（本报告全部数字）

```bat
:: 1) 真机探针（M1/M2/M3 + ProjectDirectory）
"D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe" -RunScriptAndExit "D:\ANSYS_Run\audit_20261114\m1_probe.py"

:: 2) 独立重算 M4/M5（不依赖工作区代码）
C:\Users\ASUS\.workbuddy\binaries\python\versions\3.13.12\python.exe D:\ANSYS_Run\audit_20261114\verify_fea.py D:\ANSYS_Run\csv
C:\Users\ASUS\.workbuddy\binaries\python\versions\3.13.12\python.exe D:\ANSYS_Run\audit_20261114\verify_fea.py D:\ANSYS_Run\csv_tpl

:: 3) 回归
python -m pytest -q                       :: 289 passed
python -m ruff check .                    :: All checks passed
python projects\25Nm_PMSM\gen_maxwell_model.py --check   :: 8 个生成物无漂移

:: 4) .aedt 静态键值
C:\Users\ASUS\.workbuddy\binaries\python\versions\3.13.12\python.exe D:\ANSYS_Run\audit_20261114\aedt_scan.py D:\ANSYS_Run\M5_25Nm.aedt
```

## 附录 B — 审计产物

| 文件 | 说明 |
|---|---|
| `docs/WEEKLY_AUDIT_2026-11-14.md` | 本报告 |
| `docs/weekly_audit.json` | 机读版（门槛/偏差/问题清单） |
| `projects/25Nm_PMSM/WEEKLY_GOALS.md` | 本轮 top 3（G6 齿槽 blocker / G7 齿槽二次手段 / G8 一致性） |
| `projects/25Nm_PMSM/DESIGN_PROGRESS.md` | M0–M8 状态 + 昨日/今日/明日 |
| `D:\ANSYS_Run\audit_20261114\` | `m1_probe.py`、`m1_probe.txt`、`verify_fea.py`、`aedt_scan.py`（审计脚手架，不入库） |
