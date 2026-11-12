# 25 N·m SPMSM — 设计进度看板

> 本文件由「Maxwell Skill 每日迭代」自动任务维护。每天只推进**一个阶段的一小步**，完成后勾选并记录产物与关键数值。数字必须来自脚本实算，不得臆造。

> 本周目标见 WEEKLY_GOALS.md

## 昨日 / 今日 / 明日（2026-11-12，G3b 模板回灌 + 真机全链路建模通过）

- **昨日（2026-11-11）**：G3 关闭 —— `ModelDepth` 从"手写脚本里有、模板里没有"变成
  "两侧都有且真机可验证"（`G3_depth160/180.aedt` 双值证据）。
- **今日（2026-11-12）**：**G3b 关闭 —— `gen_maxwell_model.py` 从"回退按钮"变成"可信重生成入口"**。
  ① 把 M2 阶段手改出来的 4 处几何 API 修复回灌 `scripts/main.py::_gen_geometry`
  （`Units:=` / `DuplicateAroundAxis` 第 3 参 / `Slot_1_1..` 实名 / `CreatePolyline` 嵌套）；
  ② 真机连跑三轮，**又抓出 4 处同类模板缺陷**并全部修掉：`AssignCoilGroup`（2021.1 批处理
  单数组调用必失败 → 改逐槽边 `AssignCoil`）、`AssignVectorPotential` 只吃 1D 实体
  （→ 运行期取 `GetEdgeIDsFromObject`）、`AssignBand` 键名 `Init Pos`（带空格）+ 可选键给全、
  `AssignSurfApproxOp` 在 2021.1 不存在（→ `AssignLengthOp`）；
  ③ 生成器重构成可测函数（`build_config` / `render_scripts` / `combine` / `check`），
  新增 `--check` 自检（漂移则 rc=1），`--out_dir` 真正生效，表头数值改为随配置走；
  ④ `prepare_batch.py` 新增 `--aedt`（回归验证不再覆盖 `M2_25Nm.aedt` 这类证据工程）。
- **明日（2026-11-13）**：**用模板产出的模型直接求解空载**，与 M5 手写工程逐项对比
  （BEMF 相 RMS 118.8832 V、齿槽 6.84307 N·m、`T_avg` 22.3344 N·m）。
  一致 ⇒ 模板路径与手写路径等价，此后所有几何试验都走生成器；
  不一致 ⇒ 差异就是模板与 `m4_build_solve.py` 的建模口径差（重点查 Region 是否挖件、
  线圈是否内缩 0.88、Band 是薄环还是整圆）。

### 今日关键结论（G3b）

| 项 | 结果 | 说明 |
|---|---|---|
| 模板回灌 | **8 处** API 修复 | 几何 4 + 绕组 1 + 边界 2 + 网格 1，逐条有真机报错原文 |
| 真机轮次 | **3 轮**（19:04 / 19:07 / 19:09） | rc 均为 0；第 1 轮卡 `AssignCoilGroup`、第 2 轮卡 `AssignVectorPotential`、第 3 轮 `BODY_OK` |
| 建模产物 | `G3b_regen3.aedt` **288,557 B** | `Sheets=24`、`Solids=0`、`MotionSetup1`（`Move Type='Rotate'`/1500 rpm） |
| 绕组 | **12 × `AssignCoil`（40 导体/槽边）** | 3 个 `WindingX`（Current 型），A+={1,7} A-={2,8} … kw=0.8660 |
| 边界 | `VectorPotential1`（Edges） | 存盘后 `.aedt` 里 2 处命中 |
| 求解设置 | `Setup1` 20 ms / 5e-5 s | 400 步，`SaveFieldsType=Every N Steps` |
| 叠长 | `ModelDepth='160mm'` × 1 | G3 的注入在模板路径上同样生效 |
| 生成物一致性 | **8/8 逐字一致** | `--check` 输出「无漂移」 |
| 回归 | pytest **276 passed**（+13）、ruff 全通过 | 新增 `tests/test_gen_maxwell_model.py`（13 例） |

**今日两条方法论结论**

1. **"模板改了没重生成"和"重生成把模型改坏"是同一枚硬币的两面**：只测产物测不出前者，
   只测模板测不出后者。可执行的判据是**双向逐字比对**（`--check` + pytest），
   任何一侧漂移都红灯。今天之前，`gen_maxwell_model.py` 一次空白重跑就会毁掉可解模型。
2. **报错原文优先于历史笔记**：今日新抓的 4 处里，`AssignCoilGroup` 与 `Init Pos` 都与
   仓库里既有的"已验证写法"相反（`output_scripts/36slot_industrial/winding.py` 注释写着
   "单数组参数"是 v4 修复，实际真机拒绝；`Init Pos` 空格问题 11-08 笔记记的是"无空格"，
   而 `m4_build_solve_progress.log` 两次都是 `OK AssignBand A Init Pos` 赢）。
   凡两者冲突，以真机日志为准，并回写文档。

**今日最大的坑：日志里的"成功"不等于"跑完"**

`-RunScriptAndExit` 的 rc=0 只表示 AEDT 进程正常退出，脚本里的异常会被驱动脚本
`try/except` 吃掉并写进 `m2_report.txt` 的 `BODY_FAIL`。三轮里前两轮 rc 都是 0，
但模型只建到一半（`BoundarySetup=`、`AnalysisSetup=` 都是空的）。
**判据必须看 `m2_report.txt` 第一行是 `BODY_OK` 还是 `BODY_FAIL`，以及 `BoundarySetup`/
`AnalysisSetup` 是否非空**，不能只看返回码。

**Maxwell 状态（2026-11-12）**：实机运行 ✅ **3 次**（19:04 / 19:07 / 19:09），rc=0 ×3；
日志 `D:\ANSYS_Run\m2_run.log`（第 3 轮报 `BODY_OK`），报告 `D:\ANSYS_Run\m2_report.txt`；
产物 `G3b_regen.aedt`(281,699 B) / `G3b_regen2.aedt` / `G3b_regen3.aedt`(288,557 B)；
对象数 **24 sheets / 0 solids**（Region、StatorOuter、RotorOuter、PM_1..8、Coil_1..12、Band）；
求解**未执行**（本轮只验证建模链路，`.aedtresults` 未生成）；
M4/M5 的 `M5_25Nm.aedt` / `M5_load_25Nm.aedt` 与 401 点解**未触碰**，FEA 数值不变。

## 上一轮：昨日 / 今日 / 明日（2026-11-11，G3 叠长注入闭环）

- **昨日（2026-11-10）**：M6 完成 —— `fea_results.json` 进交付报告（§11 十行对照 + 3 图），
  报告 491,996 B / 9 图 / 13 表。
- **今日（2026-11-11）**：**G3 关闭 —— 2D 叠长（`ModelDepth`）从"手写脚本里有、模板里没有"
  变成"两侧都有且真机可验证"**。
  ① `scripts/main.py::_gen_setup()` 注入 `"ModelDepth:=", "<stack_length>mm"`，
  经新增的 `format_mm()` 归一（160.0 → `160mm`，非整数保留有效位），随 `--params stack_length=` 变；
  ② `MotorConfig.validate()` 新增叠长闸口（非正 → ERROR，L/D>3 → WARNING）；
  ③ `maxwell_model/solve_25Nm_SPMSM.py` 同步 `MODEL_DEPTH = "160mm"`，并删掉头部误导性的
  `-ng -RunScriptAndExit`（两者互斥，是 11-07 之前"启动即失败"的源头）；
  ④ 生成物 `setup.py` / `build_25Nm_SPMSM.py` 同步落地。
  新增 `tests/test_model_depth.py`（27 例，含 4 处真机 API 修复的护栏），
  `pytest 251 passed`、`ruff check scripts tests examples` 全通过。
- **明日（2026-11-12）**：**G3b —— 把 4 处真机 API 修复回灌 `scripts/main.py` 模板**
  （`Units:=` / `DuplicateAroundAxis` 第 3 参 / `Slot_1_1..` 实名 / `CreatePolyline` 嵌套字典）。
  现状是"生成物正确、模板落后"，任何一次重跑生成器都会把模型改回不可解；护栏测试已就位，
  但护栏只能报警、不能自愈。回灌后 `gen_maxwell_model.py` 才是可信的重生成入口。
  若有余力，再进齿槽治理的解析预筛（极弧 0.87→0.80 / 槽口 2.5→1.5 mm）。

### 今日关键结论（G3）

| 项 | 结果 | 说明 |
|---|---|---|
| 模板注入 | `"ModelDepth:=", "160mm"` | 位于 `DesignSettingsData` 内，随 `stack_length` 变（120/160/180/142.5 均验） |
| 真机写读 160 mm | ✅ | `G3_depth160.aedt` **23,905 B**，`ModelDepth='160mm'` |
| 真机写读 180 mm | ✅ | `G3_depth180.aedt` **23,930 B**，`ModelDepth='180mm'` —— 证明该键非硬编码、未被静默忽略 |
| 生成物端到端 | ✅ | 直接执行模板产出的 `setup.py`（仅换掉 3 行 `ScriptEnv` 取桌面），`G3_generated_setup.aedt` **23,906 B**，`ModelDepth='160mm'` |
| 回归 | 251 passed（+27）、ruff 全通过 | `tests/test_model_depth.py` |
| 顺带修复 | `gen_maxwell_model.py` 段序 geometry→**materials** | 旧序会让合并脚本在 `SetMaterial` 处报 Unknown material；`test_materials_before_geometry` 早已是红灯 |

**今日两条方法论结论**

1. **Maxwell 2D 的 design 对象没有深度读取器**：`dir(oDesign)` 90 个成员里只有
   `SetDesignSettings`，`GetDesignSettings` / `GetModelDepth` / `getModelDepth` 全部
   `AttributeError`。所以"写进去再读回来"这条路根本不存在，唯一可信的核对是
   **存盘后解析 `.aedt` 文本**（`$begin 'Maxwell2DModel'` 段内的 `ModelDepth='160mm'`，
   与 `debug/aedt_parser.py` 同法）。别再把"没有读接口"误判成"写失败了"。
2. **不写就是默认值，文件里连键都没有**：`M1_min.aedt`（从未设过深度）里搜不到任何
   `ModelDepth=` 字样 ⇒ 事后从工程文件反查"当时用了多深"是不可行的，只有写进去才留痕。
   这就是 G3 必须先落地的原因 —— 它不是"补一个参数"，而是"让物理量有据可查"。

**今日最值得记的坑：生成器是回退按钮**

重跑 `gen_maxwell_model.py` 后合并脚本**不会**保持原样，它把 M2 阶段用真机报错逐条修出来的
4 处 API 改回旧写法（`Length:=`、缺 `NAME:Options`、`Slot_2..Slot_12` 实名、`CreatePolyline`
未嵌套），模型立刻变不可解。本次全靠 `pytest`（`TestModelerApiRegressions` 4 红）当场拦住，
才没有把"回退版"提交上去。**结论：生成物与模板已分叉，重生成前必须先回灌**（列 G3b）。

**Maxwell 状态（2026-11-11）**：实机运行 ✅ 3 次（19:04 / 19:05 / 19:06），全部 rc=0；
日志 `D:\ANSYS_Run\g3_depth_check.log`、`g3_run_generated_setup.log`（另有 API 探测轮
`g3_probe_api.log`）；本轮只建设计设置、不建几何 ⇒ **对象数 0**；
产物 `G3_depth160.aedt` / `G3_depth180.aedt` / `G3_generated_setup.aedt` 三个工程；
未触及 M4/M5 的 `M5_25Nm.aedt`（776,049 B）/ `M5_load_25Nm.aedt`（775,532 B）与 401 点解，
故 FEA 数值与 11-09 完全一致（BEMF 118.8832 V、齿槽 6.84307 N·m、`T_avg` 22.3344 N·m）。

## 上一轮：昨日 / 今日 / 明日（2026-11-10，M6 报告链路打通）

- **昨日（2026-11-09）**：M5 负载瞬态跑通 —— 三相 9.89 A(rms) / 20 ms / 400 步，
  `T_avg = 22.33 N·m = −10.66% 额定（±20% ✅）`，电流波形逐点偏差 0.001%，功率平衡 −0.54%。
- **今日（2026-11-10）**：**M6 完成 —— FEA 结果正式进入交付报告**。
  `make_report.py` 新增 §11「Maxwell 2D FEA 实测交叉校验」：10 行解析 vs FEA 逐项对照表
  + 3 张 FEA 图（三相空载 BEMF、负载/齿槽转矩、齿槽频谱）+ 口径说明；
  M4/M5 的 5 个波形 CSV 收进 `projects/results/fea/`（401 行全时长解，59 KB），
  报告不再依赖 `D:\ANSYS_Run` 的外部文件即可复现。
  报告实测 **491,996 B / 9 图 / 13 表**（M6 前 255,102 B / 6 图 / 12 表），
  `pytest 224 passed`（新增 11 例）、`ruff check scripts tests examples` 全通过。
- **明日（2026-11-11）**：二选一，按性价比取 **G3（`ModelDepth` 注入）** —— 这是 M4 之外
  唯一还没关的建模正确性缺口（`scripts/main.py::_gen_setup` 与
  `maxwell_model/solve_25Nm_SPMSM.py` 均无 `ModelDepth`，2D 默认 1 mm）；
  若 G3 顺利，再看齿槽治理的解析预筛（极弧 0.87→0.80 / 槽口 2.5→1.5 mm）。

### 今日关键结论（M6）

| 项 | 数值 | 说明 |
|---|---|---|
| 报告体积 | **491,996 B** | M6 前 255,102 B；增量全是 3 张 FEA 图（base64） |
| 内嵌图 / 表 | **9 / 13** | M6 前 6 / 12 |
| FEA 波形留档 | **5 个 CSV × 401 行** | `results/fea/flux_{a,b,c}`、`tq_noload`、`tq_load` |
| 交叉校验行数 | **10 行** | 相/线 BEMF、不平衡、THD、齿槽、负载 T_avg、脉动、功率平衡、电流、Kt |
| 自检 | pytest **224 passed**（+11）、ruff 全通过 | 新增 `tests/test_report_fea.py` |
| 降级路径 | 有 | 缺 `fea_results.json` → §11 显示降级说明 + 回填命令，不抛栈 |

**M6 的两条方法论结论**

1. **报告只能有一个数据源**：`fea_results.json` 是 §11 的唯一输入，`make_report.py` 不再
   直接解析 `D:\ANSYS_Run\csv`（跨机器不可复现）。波形 CSV 入库后，
   `tests/test_report_fea.py::test_ingest_reproduces_committed_results` 用留档 CSV 重算一遍
   `ingest_fea.compute()`，与 JSON 逐项比对（BEMF 118.8832 V、齿槽 6.84307 N·m、
   `T_avg` 22.3344 N·m 全部严格复现）——**报告里的数字不可再手填**。
2. **`%%` 的作用域陷阱**：报告用 `%` 运算符渲染一个 12 KB 模板，模板里写字面 `%` 必须写 `%%`；
   而新加的 §11 是**普通字符串拼接**，写 `%%` 会原样输出。首次生成就踩到
   （`±25%%`、`折 81 匝 × %.5f` 未替换），靠「渲染后 grep `%%` 与 `%.` 计数」才发现。
   以后凡新增报告段落：生成后必查 `%%` 残留数 = 0、`%.Nf` 残留数 = 0。

**Maxwell 状态（2026-11-10）**：**未运行**（本轮为纯后处理，rc = N/A，无新日志）；
沿用 2026-11-09 的工程 `D:\ANSYS_Run\M5_25Nm.aedt`（776,049 B）/ `M5_load_25Nm.aedt`（775,532 B），
两者均含 401 点全时长解，24 个图元、4 项面积 + 守恒全 PASS、`MotionSetup1` 保留 —— 本轮未改动，
故数值与 11-09 完全一致（BEMF 118.8832 V、齿槽 6.84307 N·m、`T_avg` 22.3344 N·m）。

## 上一轮：昨日 / 今日 / 明日（2026-11-09，M5 负载瞬态打通）

- **昨日（2026-11-08）**：M4 验收完成 —— 401 点全时长解，BEMF 相 RMS 118.88 V
  （折算 81 匝 120.37 V，vs 解析 132.4 V = −9.09% ✅）；齿槽 6.843 N·m ptp = 27.37% 额定 ❌
  （解析只给 1.82%，被低估 15 倍，是真实物理结论而非数值噪声）。
- **今日（2026-11-09）**：**M5 负载瞬态跑通，`T_avg = 22.33 N·m = −10.66% 额定（判据 ±20% ✅）**。
  三相 9.89 A(rms) 正弦电流、20 ms / 400 步，`M5_load_25Nm.aedt` 1.1 MB 含全时长解。
  三项独立自检全部通过：电流波形逐点比对偏差 **0.001%**（幅值+相位都对）、
  功率平衡 `T·ω` vs `3·E·I` 偏差 **−0.54%**、转矩脉动主因是齿槽（32.4%）。
  同时把「改已求解工程绕组电流」这条看似省时的死路彻底查清并写成文档（见下）。
- **明日（2026-11-10）**：M6 —— `fea_results.json` → 报告链路（`make_report.py` 读入 FEA 段）；
  再决定齿槽治理：现有 `sensitivity_design.py` 扫极弧/槽口，或直接上斜槽（0.5 槽距）。

### 今日关键结论（M5）

| 项 | 实测 | 判据 | 结论 |
|---|---|---|---|
| `T_avg` | **22.3344 N·m** | 25 ± 20% | ✅ **−10.66%** |
| `T_min / T_max` | 18.1705 / 25.4044 N·m | — | — |
| 转矩脉动 | 32.39%（末电周期 10 ms，200 点） | — | 主因齿槽 6.84 N·m（30.6%） |
| 指令电流 | 9.89 A rms（峰值 13.9867 A） | — | 原生 TrCrv 逐点偏差 **0.001%** ✅ |
| 功率平衡 | `P_mech 3508.3 W` vs `P_emf 3527.3 W` | ±10% | ✅ **−0.54%** |
| `Kt`（按峰值电流） | 1.5968 N·m/A_pk | — | = 2.258 N·m/A_rms |

−10.66% 的成因与 BEMF 的 −9.09% 同源：解析式用 `Kw=0.933`，而 12S8P 真实绕组因数是 0.866，
单这一项就把解析值高估了 7.7%，其余来自端部漏磁与带载电枢反应。

### 今日最重要的方法论结论：改已完成工程的绕组电流不可行

省 7 min 建模时间的自然想法「打开 M4 工程 → `EditWindingGroup` 改电流 → `Analyze`」是死路：
每个 API 都不报错、求解器真跑 304 s，但设计进入 `Solutions have been invalidated` 状态，
`.aedtresults` 只落试算段 10 步，`CreateReport` 建得出、`ExportToFile` 只写表头。
对照实验（同一份导出代码、未编辑的 `M5_25Nm.aedt`）得 401 行 ⇒ 通道没问题，是工程状态问题。
**结论写进 `docs/MAXWELL_INTERNALS.md` §11：负载工况走全新设计（`MAXWELL_CASE=load`）。**

第二个坑：试算后**不要**导出转矩报表。试算导出会把 `Moving1.Torque` 绑到试算解，
之后全时长再建报表导出的仍是 21 行试算段（而同一解的磁链是 401 行）。
判号改用原生 `WindingX_TrCrv.txt` 的 `Σv·i`（实测 3314 W > 0 ⇒ 电动），零成本且不受报表影响。

**Maxwell 状态（2026-11-09）**：实机运行 ✅ 4 次（19:08 / 19:11 / 19:21 / 19:28），
有效结果取 19:28 那次 rc=0；日志 `D:\ANSYS_Run\m5_load_build_progress.log`（build 9 s /
trial 31 s / **full 377.4 s** / 4×export 401 rows）；工程 `D:\ANSYS_Run\M5_load_25Nm.aedt`
**775,532 B**；对象 24 个（Region/Stator/Rotor/Band/12 Coil/8 PM），面积 4 项 + 守恒全 PASS；
求解 0–20 ms / 50 µs / SaveFields Every 2；运动带 `MotionSetup1`（Rotate / 1500 rpm）保留。

## 上一轮：昨日 / 今日 / 明日（2026-11-08，晚间续推）

> 同一天推进了两轮：白天（下午）把 M4 求解打通，晚间（19:45–20:10）完成 M4 验收。

- **昨日（2026-11-07）**：M0–M3 打通（`M1_min/M2_25Nm/M4_25Nm.aedt`），AEDT 默认工程目录改到
  `D:\ANSYS_Run\projects`，新增 `docs/MAXWELL_INTERNALS.md`、`docs/WORKSPACE_MAP.md`。
- **今日第一轮（2026-11-08 白天）**：**M4 求解跑通**。查实 M2/M3 的 `M4_25Nm.aedt` 根本不可解
  （36 条 intersect + 1 条 non-manifold），新建 `maxwell/m4_build_solve.py` 从零重建自洽几何 →
  `M5_25Nm.aedt` → `Analyze("Setup1")` OK，416.7 s / 400 步；4 项面积 + 面积守恒全 PASS；
  `MotionSetup1` 实落。同时重写 `ingest_fea.py`（零依赖 CSV 解析 + DFT/THD）并补单测。
- **今日第二轮（2026-11-08 晚间）**：**M4 验收完成（BEMF 通过、齿槽不达标）**。三件事：
  1. **导出通道破解**：`CreateReport` 在批处理下是可用的，唯一正确配方是
     `reportType="Standard"` + `NAME:Context/SimValueContext` + `["X Component:=",…]`；
     此前「144 种组合全失败」是三处参数同时踩坑。已固化进
     `maxwell/export_m4_csv.py`（求解/导出解耦，重导出不必重跑 400 s）。
  2. **匝数口径纠错**：`Conductor number` 是**每槽边**导体数，相 A 只有 2 个绕齿线圈 ⇒
     `N_phase = 2 × 40`，旧值 20 导致反电势正好少一半。改 40 后 λ_pp 由 0.25937 → 0.51871 Wb，
     比值 **2.000**，口径确认。
  3. **实机结果**：`full elapsed 377.3 s`、401 点全时长解、`conductor=40 ×12`；
     BEMF 相 RMS **118.88 V**（三相不平衡 0.008%、线 205.91 V、线 THD 10.6%），
     折算 81 匝 **120.37 V** vs 解析 132.4 V = **−9.1%，判据通过**；
     齿槽 **6.84 N·m ptp = 额定 27.4%**，解析只给 1.8% ⇒ **判据不通过，且是真实物理结论**
     （主频 600 Hz = LCM(12,8)×25 Hz，正是理论齿槽基频）。
- **明日（2026-11-09）**：进 M5 负载瞬态（三相 9.89 A，`T_avg` 判 25±20%）；同时把 M6 回填做掉，
  并把「齿槽被解析低估 15 倍」写成设计改进项（极弧/槽口/斜槽三选一，用现成 `sensitivity_*` 链路扫）。

**Maxwell 状态（2026-11-08 晚间）**：实机运行 ✅ 3 次（19:45 / 19:50 / 20:00），有效结果取第 3 次
rc=0；日志 `D:\ANSYS_Run\m4_build_solve_progress.log`（`trial 17.6 s` / `full 377.3 s` /
`4×export … 401 rows`）；工程 `D:\ANSYS_Run\M5_25Nm.aedt` **776,049 B** 已存盘（求解后存 1 次 + 收尾 1 次，
存解前为 583,669 B）；
关键校验全 PASS：12×`Conductor number'='40'`、`MotionSetup1`（`Rotate`/`1500rpm`）、
12×Coil / 3×Winding、`ModelDepth='160mm'`、4 项面积 + 面积守恒（28352.8737 / π·95²）；
工程最终 776,049 B（存解前 583,669 B，增大即全时长解已落盘）。

## 目标机型

| 项 | 值 |
|---|---|
| 类型 | 表贴式永磁同步电机（SPMSM） |
| 规格 | 25 N·m / 1500 rpm / 3.93 kW |
| 母线 | 537 V（380 V AC × √2） |
| 极槽 | 8 极 12 槽 |
| 定子 | 外径 150 mm / 内径 93 mm / 叠长 160 mm |
| 气隙 | 0.675 mm |
| 磁钢 | N35 NdFeB，厚 1.95 mm，极弧 0.87 |
| 铁芯 | M270-35A（0.35 mm） |
| 绕组 | 集中式，81 匝/相，kw=0.933 |

## 阶段看板

| 阶段 | 内容 | 状态 | 关键产物 |
|---|---|---|---|
| S0 | 需求与规格冻结 | ✅ 完成 | `pmsm_config.py` |
| S1 | 电磁 sizing / 主要尺寸 | ✅ 完成 | `pmsm_config.py` |
| S2 | 槽极配合与绕组排布 | ✅ 完成 | `maxwell_model/winding.py` |
| S3 | 材料与损耗模型 | ✅ 完成 | `pmsm_config.py`、`sim_analytical.py` |
| S4 | 解析电磁仿真（磁场/反电势/转矩/损耗/退磁） | ✅ 完成 | `sim_analytical.py`、`projects/results/sim_summary.json` |
| S5 | Maxwell 2D 建模脚本（几何+材料+绕组+剖分） | ✅ 完成 | `maxwell_model/build_25Nm_SPMSM.py` |
| S6 | Maxwell FEA 实跑与结果回填 | ✅ **完成 2026-11-10**（经 M4/M5 实机求解 + M6 回填；`main.py` 代码生成路径的 `ModelDepth` 仍待 G3） | `maxwell/m4_build_solve.py`、`export_m4_csv.py`、`ingest_fea.py`、`results/fea_results.json` |
| S7 | 热分析（损耗→绕组/磁钢温升） | ✅ 完成 | `thermal_analysis.py`、`projects/results/thermal_summary.json` |
| S8 | NVH / 结构模态与力波避振 | ✅ 完成 | `nvh_analysis.py`、`projects/results/nvh_summary.json` |
| S9 | 参数敏感性 / 多目标优化 | ✅ 完成（斜槽×极弧 → 叠长×匝数） | `sensitivity_design.py`、`sensitivity_stack_turns.py`、`projects/results/sensitivity_summary.json`、`sensitivity_stack_turns.json` |
| S10 | 制造公差、BOM 与图纸 | ⬜ 未开始 | — |
| S11 | 最终设计评审报告（汇总全链路） | ⬜ 未开始（前置已全部具备：G2 报告链路 + M6 FEA 段；报告现 491,996 B / 9 图 / 13 表） | `make_report.py`、`REPORT_25Nm_SPMSM.html` |

## Maxwell 实机执行轨（M0–M6，最高优先级）

> 技能的意义是**在 ANSYS Maxwell 中把电机画出来**。解析仿真（S4/S7/S8/S9）只是前置校验，**不能替代** Maxwell 实机验证。每日任务优先推进本轨；只有 M4（Maxwell 求解）通过后，才考虑 S10/S11。

| 阶段 | 内容 | 状态 | 产物 / 判据 |
|---|---|---|---|
| M0 | 环境探测：`ansysedt.exe`、许可证、`-ng` 可启动性 | ✅ **完成 2026-11-07** | 可启动，命令**不带 `-ng`**：`ansysedt.exe -RunScriptAndExit <脚本>` |
| M1 | 最小 Maxwell 工程：NewProject + Maxwell 2D + SaveAs `.aedt` | ✅ **完成 2026-11-07** | `D:\ANSYS_Run\M1_min.aedt`（17,233 B，`Factory='Maxwell 2D'`） |
| M2 | 25 N·m 几何在 Maxwell 中生成（定子/12 槽/转子/8 磁钢/气隙/band） | ✅ **完成 2026-11-07** | `D:\ANSYS_Run\M2_25Nm.aedt`（281,687 B，24 个 2D 图元，面积全项校验通过） |
| M3 | 材料/绕组/边界/运动带/剖分落地 | ✅ 完成 2026-11-07（**Band 实际未落地**，2026-11-08 修正） | 12×Coil、3×Winding、`ModelDepth='160mm'`、`M270_35A`×2、`VP`；但 `MotionSetupList` 当时为空 |
| M4 | 空载瞬态求解（BEMF/齿槽） | 🟡 **BEMF 通过 / 齿槽不达标（2026-11-08）** | 401 点全时长解（0–20 ms，50 µs）。BEMF 相 RMS **118.88 V**、三相不平衡 0.008%、线 205.91 V、线 THD 10.60%；折算 81 匝 **120.37 V** vs 解析 132.4 V = **−9.09% ✅**。齿槽 **6.84 N·m ptp = 27.37% 额定 ❌**（解析 1.82%，被低估 15 倍） |
| M5 | 负载瞬态求解（转矩/电流） | ✅ **完成 2026-11-09** | `T_avg = 22.3344 N·m = −10.66% 额定（±20% ✅）`；三相 9.89 A(rms)，电流波形偏差 0.001%；脉动 32.4%；功率平衡 −0.54% |
| M6 | 结果回填报告 | ✅ **完成 2026-11-10** | `fea_results.json` + `results/fea/*.csv` → 报告 §11（10 行交叉校验 + 3 图），报告 491,996 B / 9 图 / 13 表 |

**M0/M1/M2 实测记录（2026-11-07 22:16–22:26，本 agent 会话，真机执行）**

> 结论先行：此前连续多日记录的「M0 blocked（沙箱环境）」是**误判**。真实原因是命令行用法错误，
> 与沙箱/许可证无关。Maxwell 21.1 在本机可被 agent 正常驱动。

| 项 | 实测 |
|---|---|
| 失败根因 1 | `-ng` 必须与 `-batchsolve/-batchsave/-batchextract` 组合；脚本模式应**去掉 `-ng`** |
| 失败根因 2 | `-RunScriptAndExit` 模式由 AEDT **预注入 `oDesktop`**，脚本内 `ScriptEnv.GetDesktop()` 直接 AttributeError |
| 失败根因 3 | 内嵌 IronPython 为 **2.7**，f-string 是语法错误 |
| 正确命令 | `ansysedt.exe -RunScriptAndExit "D:\ANSYS_Run\m2_run.py"` |
| M1 结果 | rc=0、`M1_min.aedt` 17,233 B、`DesignName='M1_Min'`、`Factory='Maxwell 2D'` |
| M2 结果 | rc=0、`M2_25Nm.aedt` 281,687 B、`n_sheets=24`、`units=mm`、重开工程成功 |
| M2 对象 | Region、StatorOuter（12 槽）、RotorOuter（含 φ15 轴孔）、PM_1…PM_8、Band、Coil_1…Coil_12 |

M2 尺寸校验（`m2_verify.py` 重开工程，用 `GetFaceIDs`+`GetFaceArea` 取面积，与解析值比对）：

| 对象 | 期望（mm²） | 实测（mm²） | 判据 |
|---|---|---|---|
| Region | π·95² = 28352.874 | 28352.87370 | ✅ 外边界 R=95 |
| StatorOuter | π(75²−46.5²) − 12×102.75 = 9645.5 | 9645.54996 | ✅ 12 槽已挖除、槽型面积正确 |
| RotorOuter | π(45.825²−15²) = 5890.27 | 5890.26828 | ✅ 转子 OD 45.825、轴孔 φ15 |
| Band | π·46.1625² = 6694.66 | 6694.65982 | ✅ 气隙中心带 |
| PM_1…8 | 1.95×30.707 = 59.88 | 59.87760 | ✅ 厚 1.95、极弧 0.87 |
| Coil_1…12 | 13.2×5.7 = 75.24 | 75.24000 | ✅ 槽内居中 |

**G3 实证**：`GetModelBoundingBox()` 返回 `['-95','-95','0','95','95','0']` —— Z 向厚度为 **0**，
2D 模型确实没有叠长，`ModelDepth` 缺失会使 FEA 转矩/损耗整体低估，G3 仍是 M4 的硬前置。

**M3 完成记录（2026-11-07 22:46，`M4_25Nm.aedt` 285,766 B）**

| 项 | 实测 |
|---|---|
| `ModelDepth` | `'160mm'`（原默认 `1meter`，已修） |
| 铁芯材料 | `MaterialValue='"M270_35A"'` ×2（StatorOuter / RotorOuter） |
| 线圈 | `BoundType='Coil'` **×12**，`Winding=` **×12** |
| 绕组组 | `BoundType='Winding Group'` ×3（WindingA/B/C） |
| 边界 | `VectorPotential1` + `Edges(7)` |
| 求解 | `Setup1`（Transient，0.02 s / 50 µs） |
| 几何 | 12 槽 + 8 磁钢 + 12 线圈 + Band + Region（面积校验全通过） |

**关键坑（2021.1 实测）**：`AssignCoilGroup` 在 AEDT 2021.1 的 COM 签名对参数类型极挑
（字符串/单数组/双数组均报 `Output data type conversion error`）。**可用写法是逐个线圈 `AssignCoil`**：

```python
oBnd.AssignCoil(["NAME:A_1", "Objects:=", ["Coil_1"],
                 "Conductor number:=", "40", "PolarityType:=", "Positive",
                 "Winding:=", "WindingA"])
```

12 个线圈逐个挂接后，`.aedt` 中自然形成 12 个 `BoundType='Coil'` 边界与 `Winding` 关联。

**M4 完成记录（2026-11-08，`M5_25Nm.aedt` 776,049 B（含全时长解），真机执行）**

三次真机运行才拿下这一格，每次都是不同的坑，全部留痕：

| 运行 | 起止 | 配置 | 结果 |
|---|---|---|---|
| ① 19:45 | trial 14.1 s | 20 导体/槽边 | `Analyze full` 被下一次启动打断，无数据 |
| ② 19:50 | full **401.6 s** | 20 导体 + **删了 Band 再重挂** | 求解 OK，但导出只得到 **5 点试算段**（0–200 µs） |
| ③ 20:00 | trial 17.6 s / full **377.3 s** | **40 导体/槽边**、不动 Band | ✅ 401 点全时长解 + 4 个 CSV 全部 401 行 |

**为什么②只拿到 5 点**：`EditSetup` 之后 `DeleteMotionSetup()` 把运动设置清掉再重挂，
求解列表被重建，`CreateReport(... "Time:=",["All"])` 绑到了残留的试算解。
日志里 `motion setups before full solve: ['MotionSetup1']` 直接给出反证——
**`EditSetup` 本身不会丢运动带**，是那句多余的 Delete 制造的问题。
现脚本改成 `ensure_band()`：有就保留、没有才补挂（`BAND_VARIANTS` 变体链）。

**匝数口径**：`Conductor number` 是**每槽边**导体数。相 A = 槽{1+,2−}绕齿1 + 槽{7+,8−}绕齿7
= 2 个线圈 ⇒ `N_phase = 2 × 40 = 80` 匝（设计 81，−1.2%）。旧值 20 使反电势正好少一半。
硬证据：λ_pp 由 0.25937 → **0.51871 Wb，比值 2.000**（严格线性，说明只是匝数变化）。

**空载反电势（e = −dλ/dt，电流型绕组无 `*.Voltage` 观测）**

| 项 | 实测 | 解析 | 判据 |
|---|---|---|---|
| 相 RMS（80 匝） | 118.88 V | — | — |
| 相 RMS（折 81 匝） | **120.37 V** | 132.4 V | **−9.09% ✅（±25%）** |
| 线 RMS（A−B 实测） | 205.91 V | — | 与 √3×相 = 205.91 一致 |
| 三相不平衡 | **0.008%** | 0 | ✅ |
| 相 THD | 10.59% | — | 线 THD 10.60%（解析 15.75%） |
| λ_pp | 0.51871 Wb | — | — |

−9.1% 的差额可完整解释：解析式用了 `Kw=0.933`，而 12S8P 的真实绕组因数是 **0.866**
（kp=sin60°=0.866、kd=1），单这一项就带来 +7.7% 的高估，其余 ~1.4% 来自磁钢端部/漏磁。

**齿槽转矩：解析严重低估（本条为设计问题，不是脚本问题）**

| 项 | 实测 | 解析 | 判据 |
|---|---|---|---|
| ptp | **6.843 N·m** | 0.454 N·m | ❌ 差 15 倍 |
| 占额定 | **27.37%** | 1.82% | ❌（≤5%） |
| 均值 | 0.00003 N·m | 0 | ✅ 无直流偏置，纯齿槽 |
| 主频 | **600 Hz** = LCM(12,8)×f_mech = 24×25 | — | ✅ 正是理论齿槽基频 |

不是数值噪声的三条依据：① 均值 0.00003 N·m，若为伪迹通常带偏置；
② 主频精确落在 600 Hz，且 `t=0.45 ms` 与 `t=10.45 ms` 数值完全重复（3.4219），周期性干净；
③ 频谱上 100 次（0.0001 N·m）几乎为零，全部能量在 600 / 1200 / 2400 Hz 齿槽族上。

根因按可能性排序：**槽口 2.5 mm / 气隙 0.675 mm = 3.7** 过大、无斜槽、极弧 0.87 未针对 12S8P 优化。
下一步不是改脚本，而是先做网格敏感性排除离散化（Band `MaxLength` 0.3 → 0.15 mm 复算一次），
再用现成 `sensitivity_design.py` 扫极弧×槽口。

**产物**：`projects/25Nm_PMSM/results/fea_results.json`（`bemf_pass: true`、`cogging.pass_5pct: false`）。
复现命令：

```bash
# 全流程（约 7 min）
"C:/Program Files/AnsysEM/AnsysEM21.1/Win64/ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/m4_build_solve.py"
# 只补导出（不重求解）
"…/ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/export_m4_csv.py"
# 回填
ci_venv/Scripts/python.exe projects/25Nm_PMSM/ingest_fea.py --csvdir D:/ANSYS_Run/csv --turns-model 80
```

**口径警示（避免再次误读）**：导出文件必须核行数。521 B / 5 行的 csv 是**试算段**
（0–200 µs），满篇 401 行才是全时长解；`0.404 N·m`「齿槽」正是把试算段末点
（t=0.2 ms，tq=0.4036）当成峰值的产物，不可引用。

**纪律**：M5–M6 未完成前不得标完成；解析结果只能写在「交叉校验」栏，不能替代 Maxwell 实机证据。

## M5 完成记录（负载瞬态，2026-11-09 真机执行，`M5_load_25Nm.aedt`）

四轮真机运行才拿下，每轮都留下一条可复用结论（前三轮全部失败在「工程状态」而非物理）：

| 运行 | 起止 | 配置 | 结果 |
|---|---|---|---|
| ① 19:08 | 打开 M4 工程改绕组电流 | `EditWindingGroup` + 试算 | 编辑成功、试算 22.6 s，但导出只有表头 |
| ② 19:11 | 同上，全时长 | 20 ms / 400 步 | 求解 304.1 s「Normal completion」，**解不落盘**（Data 只有 10 步） |
| ③ 19:21 | 从头重建（负载） | 试算后导出转矩判号 | 全时长 282.6 s；磁链 401 行，**转矩仍 21 行（试算段）** |
| ④ 19:28 | 从头重建（负载）+ 原生判号 | 试算不导报表 | ✅ 试算 31 s、全时长 **377.4 s**、4 个 CSV 全 401 行 |

**根因一（运行①②）**：对已求解工程 `EditWindingGroup` 会令设计进入 `Solutions have been
invalidated`，`Analyze` 照跑但新解不登记为该设计的当前解 ⇒ 后处理拿不到时间轴。
对照实验：同一导出代码对未编辑的 `M5_25Nm.aedt` 得 401 行。
**根因二（运行③）**：试算后若导出转矩报表，`Moving1.Torque` 会绑定在试算解上；全时长后
再建同名族报表仍导试算段（21 行），而同解磁链是 401 行。故判号改用原生 `Σv·i`。

**电学口径（已逐点验证）**：`Current:="−13.9866*sin(2*pi*100*Time+2.094395)"`（A 相），
`Time` 大写、秒；三相对称 B=+4.188790（240°）、C=无相位（0°）。原生 TrCrv 逐点比对
最大偏差 **0.0001 A = 峰值的 0.001%**，即幅值与相位同时对上。

**负载结果**

| 项 | 实测 | 判据 | 结论 |
|---|---|---|---|
| `T_avg` | **22.3344 N·m** | 25 ± 20% | ✅ −10.66% |
| `T_min / T_max` | 18.1705 / 25.4044 | — | 脉动 32.39% |
| 空载齿槽（M4） | 6.843 N·m ptp = 27.37% | ≤5% | ❌ 脉动主因 |
| `P_mech = T·ω` | 3508.3 W | vs `3·E·I`=3527.3 W | ✅ −0.54% |
| `Kt` | 1.5968 N·m/A_pk（2.258 N·m/A_rms） | — | — |

`P_mech` 与 `3·E_rms·I_rms` 相差 0.54%，说明**转矩与反电势两条独立通道互相印证**，
−10.66% 不是数值误差，而是解析 `Kw=0.933`（真实 0.866）带来的系统性高估。

**产物**：`projects/results/fea_results.json`（新增 `load` 段：`pass_20pct: true`、
`current_ok: true`、`power_balance.pass_10pct: true`）。

复现命令：

```bash
# 负载全流程（约 7.5 min：build 9 s + trial 31 s + full 377 s）
MAXWELL_CASE=load MAXWELL_SIGN=-1 \
  "D:/Program Files/AnsysEM/AnsysEM21.1/Win64/ansysedt.exe" -RunScriptAndExit "D:/ANSYS_Run/m4_build_solve.py"
# 回填（电流走原生 TrCrv，报表导不出也不影响）
ci_venv/Scripts/python.exe projects/25Nm_PMSM/ingest_fea.py --csvdir D:/ANSYS_Run/csv \
  --native-dir D:/ANSYS_Run/M5_load_25Nm.aedtresults/Motor_Design.results/DV42_SOL41_V0.Data \
  --turns-model 80
```


## M6 完成记录（报告链路，2026-11-10）

目标：把 `fea_results.json` 接进交付报告，让 FEA 成为可引用的证据而不是散落在 `D:\ANSYS_Run` 的中间产物。

| 项 | 改动 / 实测 |
|---|---|
| 数据入库 | 新增 `projects/results/fea/`：`flux_a|b|c.csv`、`tq_noload.csv`、`tq_load.csv`，各 401 行（0–20 ms / 50 µs），合计 59 KB |
| 报告 | `make_report.py` 新增 `load_fea()` / `_fea_series()` / `chart_fea_bemf()` / `chart_fea_torque()` / `chart_fea_cogging_spectrum()` / `build_fea_section()` / `fea_kpi()` / `fea_bullet()`；新增 §11 章节，首屏 KPI 加「FEA 平均转矩」 |
| 降级 | `fea_results.json` 缺失或 `status != OK` → §11 输出降级说明并给出回填命令，其余章节照常 |
| 图表 | BEMF 三相（e = −dλ/dt）、负载转矩 + 齿槽转矩、齿槽频谱（标注 600 Hz = LCM(12,8)×25 Hz） |
| 报告实测 | **491,996 B / 9 图 / 13 表**（M6 前 255,102 B / 6 / 12），`<!--…-->` 占位符残留 0、`%%` 残留 0 |
| 测试 | 新增 `tests/test_report_fea.py`（11 例）：JSON 结构、判据口径、物理自洽、CSV 必须 401 行、**用留档 CSV 重算复现 JSON**、源码级降级契约 |
| CI | `pytest` **224 passed**（213+11）、`ruff check scripts tests examples` 全通过 |

**口径（报告已写明，勿再误用）**：FEA 模型 80 匝/相（40 导体/槽边 × 2 绕齿线圈），
折 81 匝 × 1.0125；电流型绕组无 `WindingA.Voltage`，反电势由 `FluxLinkage` 求导；
导出单位随解变化（`Time [us]`/`[ms]`、`Torque [mNewtonMeter]`），换算由
`ingest_fea.load_maxwell_csv` 按单位行自动完成；只有 401 行才是全时长解。

**同时修正的过期表述**：原报告首页写「FEA 须桌面执行（待执行）」、附录写「agent 沙箱无法初始化
AEDT 运行时」——均与 11-08/11-09 的实机事实相反，已改为记录真实工程路径、求解耗时与 401 点解。

## M4 结果与「报错即退出」诊断（2026-11-08）

> **⚠️ 本节是当晚第一轮的诊断记录，其中 3 条已被晚间复算推翻**（`CreateReport` 其实可用、
> `EditSetup` 不丢运动、齿槽 0.404 N·m 是试算段末点）。**以本文档上方的「M4 完成记录」为准**，
> 本节仅保留排查过程与「`-RunScriptAndExit` 跑完即退出属正常语义」这一条有效结论。

### 现象
运行 `m4_build_solve.py` 后，Maxwell 完成建模/求解，随后报错并退出。**不是 Maxwell 崩溃，也不是建模失败。**

### 根因
1. `-RunScriptAndExit` 跑完脚本即退出，属正常语义。
2. 报错来自**求解后的导出/回读**：`CreateReport`/`ExportToFile` 在 2021.1 批处理参数不兼容；
   `verify turns` 的 `GetChildObject` 读回失败（非致命）。
3. 导出 CSV 取的是**试算解**（0–200 µs，5 行），不是全时长解；单位是 `Time [us]` / `Torque [mNewtonMeter]`，
   误当 ms/N·m 会算出 403 N·m 的错值。
4. 全时长 `EditSetup` 会丢掉 band 运动；已在 `EditSetup` 后 `DeleteMotionSetup` + 重新 `AssignBand`
   修复（全时长磁链重新随转子变化，A: -0.0595→-0.1297 Wb）。

### 已验证的正确做法

> 以下三条在晚间复算中被推翻/修正，以本节为准；原判断保留在行内以便追溯。

- Band **取整圆包住转子**（`R=46.1625 mm`，面积 π·46.1625² = 6694.66 mm²，实测 6694.6598 ✅）。
  「必须是三不沾的薄环」是误判：整圆 Band 不参与 intersect 检查，且 `AssignBand` 找的是
  band **内部**对象，做成气隙环（洞内放转子）反而报 `No objects within the band`。
  原先「整圆盘会让 BEMF 掉到 45%」的说法也不成立 —— 那 45% 的真因是匝数少了一半（见下）。
- `AssignBand` 键名 `"InitPos:="` 与 `"Init Pos:="` 在删干净 motion 后**都能成功**；
  稳妥做法仍是按变体链逐个试（`BAND_VARIANTS`），不要押单一写法。
- **`EditSetup` 不会丢 band 运动**（日志 `motion setups before full solve: ['MotionSetup1']`）。
  多余地 `DeleteMotionSetup()` + 重挂会重建求解列表，让报告绑到残留试算解 ⇒ 400 步跑完只导出 5 行。
  正确做法是 `ensure_band()`：读回有就保留、没有才补挂。
- BEMF 用 `FluxLinkage(WindingA)`；`WindingA.Voltage` 对电流型绕组为空。
- `CreateReport` 用 `Standard` + 14 元素 `SimValueContext` + `X Component`/`Y Component`；
  `ExportToFile` 后必须**数数据行**（401 行才是全时长解，5 行是试算段）。
- 单位换算必须做：试算段导出会给 `Time [us]` / `Torque [mNewtonMeter]`，
  误当 ms/N·m 会算出 403 N·m 的错值。

### 结果（`M5_25Nm.aedt`，401 点全时长解，2026-11-08 实测）

| 指标 | 解析 | FEA（80 匝/相） | 差异 |
|---|---|---|---|
| 相 BEMF 峰值 | 187.2 V | **156.97 V** | — |
| 相 BEMF RMS | 132.4 V | **118.88 V** | 折算 81 匝为 120.37 V ⇒ **−9.09%** |
| 齿槽 ptp | 0.454 N·m（1.8%） | **6.843 N·m（27.37%）** | **+15 倍，解析失效** |
| 空载平均转矩 | ~0 | 0.00003 N·m | ✅ |

> **纠正两处早前误读**（数据源混用所致，务必以本表为准）：
> ① 「相 RMS ≈111 V」是 `156.97/√2` 的估算，没做真实 RMS（波形含 10.6% 谐波，
> 真值 118.88 V）；② 「齿槽 0.404 N·m」取自**试算段 200 µs 末点**（tq=0.4036），
> 不是全时长齿槽峰值。
>
> 结论：**BEMF 与解析同量级（−9.1%，可由 Kw 口径 0.933 vs 0.866 解释）；齿槽转矩被解析
> 低估 15 倍，是真实设计问题**（槽口/气隙 = 3.7、无斜槽、极弧未优化），需在 M6 作为改进项
> 处理。下一步不是改脚本，而是先做 Band 网格敏感性（0.3 → 0.15 mm）排除离散化影响。

## 本周目标（2026-11-07 起，G1–G3）进度

| 目标 | 内容 | 状态 | 产物 |
|---|---|---|---|
| G1 | 建模入口几何不自洽（`rotor_od` 写死 135.6） | ✅ 完成 2026-11-07 | `scripts/motor_config.py`、`tests/test_motor_config.py` |
| G2 | 报告链路依赖未声明（matplotlib/numpy/pytest） | ✅ 完成 2026-11-07 | `pyproject.toml`、`SKILL.md`、`make_report.py`、`tests/test_report_deps.py` |
| G3 | 2D 叠长丢失（无 `ModelDepth`） | ⬜ 待做（下一步） | `scripts/main.py::_gen_setup`、`maxwell_model/solve_25Nm_SPMSM.py` |
| G6 | **`compute_winding_factor` 表把 12S8P 记成 0.933** | ⬜ 待修（2026-11-08 由 FEA 反查发现） | `scripts/motor_param_calc.py:364` |

**G6 说明（新发现，暂不动手）**：`scripts/motor_param_calc.py` 的查表里
`(12, 8): 0.933` 与 `(12, 10): 0.933` 取了同一个值，但 12S8P 的真实绕组因数应为
**0.866**（kp = sin(2π/3 / 2) = sin60° = 0.866，kd = 1）。该错值经
`E_ph_rms = √2·π·f·Nph·Kw·φ` 使 BEMF 高估 7.7%，正是 FEA 与解析 −9.1% 差额的主因。
修它会连带改变 `E_ph_rms_V` → `Nph` → 铜耗/转矩/热/NVH 全链路，不属于「Maxwell 建模」
范畴，**本轮只登记不改**，留到 M6 回填时一次性重算并更新 S4/S7/S8/S9 结果。

## G1 完成记录（几何派生，2026-11-07）

缺陷：`MotorConfig.rotor_od` / `airgap` 为 36 槽机型的硬编码默认值（135.6 / 0.2 mm），
`__post_init__` 不做几何派生 ⇒ 凡 `stator_id < 135.6 mm` 的机型经 `scripts/main.py` 从零建模必 rc=1。

修复：两字段改 `Optional[float] = None` 哨兵 + `_resolve_geometry()` 四分支（优先级：
显式两者 > 只给 rotor_od > 只给 airgap > 都缺省），气隙按 `δ = clamp(0.3 + Dso/400, 0.35, 2.0)` 推导。

| 校核项 | 判据 | 实测 |
|---|---|---|
| 干净 venv 建模 `slots=12 poles=8 stator_od=150 stator_id=93` | rc=0、校验通过 | ✅ rc=0（`pip install -e .` 后无需任何补装） |
| 派生气隙 | δ=0.3+150/400 | ✅ 0.675 mm（与 S3–S9 冻结值一致） |
| 派生转子外径 | Dro = 93 − 2δ | ✅ 91.65 mm |
| 生成物 `RotorOuter` | 46.5 − δ | ✅ **45.825 mm**（气隙闭合 0.675 mm） |
| `Region` 半径 | ≥1.25×Rso(=75) | ✅ 95.0 mm = 1.267× |
| 四预设行为不变 | rotor_od 不被覆盖 | ✅ 135.6 / 50.8 / 118.4 / 135.2，气隙自洽 |
| 单测 | 新增三例 + 全量回归 | ✅ 163 passed（147+16），ruff 全通过 |

**口径偏差（须留痕）**：WEEKLY_GOALS 验收写 `RotorOuter = 46.125 mm`，该数 = 46.5 − 0.375，
隐含 δ=Dso/400（丢了 0.3 mm 偏置），与同一条目内「δ=0.3+Dso/400=0.675」自相矛盾。
本步取 **45.825 mm**（δ=0.675）：S4 解析、S7 热、S8 NVH、S9 敏感性全部以 0.675 mm 气隙为基准
（g_eff=2.532 mm），若按 0.375 mm 建模则与既有设计链路脱钩；周检报告 §3 证据段亦记录 45.825 ✓。

## G2 完成记录（报告链路依赖声明，2026-11-07）

缺陷：`pyproject.toml` 的 `dependencies` 只声明 `pyyaml`，`matplotlib`/`numpy` 仅存在于 `[plot]` extra。
干净 venv `pip install -e .` 成功后，`projects/25Nm_PMSM/make_report.py:17` 直接
`ModuleNotFoundError: No module named 'matplotlib'`（rc=1），S11 交付链断在第一条 import；
同文件 line 411 的 `D:\Program` 构成无效转义序列 `\P`（P7，`-W error::SyntaxWarning` 即报 SyntaxError）。

修复（6 处，均为声明/入口层，不触碰电磁模型）：
1. `pyproject.toml`：`numpy>=1.24`、`matplotlib>=3.7` 提升为**核心依赖**，`[plot]` 保留为向后兼容别名；
2. `make_report.py`：绘图 import 包进 `try/except ModuleNotFoundError`，打印中文安装提示并 `sys.exit(2)`；
3. `make_report.py`：line 411 路径改 `D:\\Program ...`，**P7 关闭**；
4. `make_report.py`：第 9 节补入「已算但未内嵌」的退磁柱状图（内嵌图 5→6），`阈值 0.2T` 改 ASCII，消除 DejaVu CJK 缺字形告警；
5. `SKILL.md`：新增「📦 安装（报告链路前置）」小节（`pip install -e .` / `-e ".[dev]"` / 只装绘图栈）；
6. 新增 `tests/test_report_deps.py`（4 例）：numpy/matplotlib 必须在核心 deps、`make_report.py` 的第三方 import 必须已声明、缺包必须 rc=2。

| 校核项 | 判据 | 实测 |
|---|---|---|
| 新建 venv（py3.13）→ `pip install -e .` | 无需手工补装 | ✅ 单条命令即装到 numpy 2.5.4 / matplotlib 3.11.2 |
| `python projects/25Nm_PMSM/make_report.py` | rc=0 | ✅ rc=0 |
| HTML 体积 | >200 KB | ✅ **255,102 B**（255.1 KB，原 230,384 B） |
| `data:image/png;base64` 计数 | ≥5 | ✅ **6**（截面/反电势/气隙/转矩/损耗/退磁） |
| `<table>` 计数 | ≥10 | ✅ **12** |
| 缺包路径 | 中文提示、不抛裸栈 | ✅ rc=2（用无 numpy 的 ci_venv 复现） |
| `-W error::SyntaxWarning` 编译 | 无告警 | ✅ 通过（P7） |
| 自检回归 | pytest / ruff | ✅ **167 passed**（163+4）、ruff 全通过 |

结论：报告链路由「依赖本机残留环境」改为「声明式依赖 + 装完即跑」，`pip install -e .` 是唯一前置；
S11 最终评审报告的可复现性有了硬保证。附带效果：`make_report.py` 的失败模式从「裸栈 rc=1」变为
「可读诊断 rc=2」，CI/脚本可据退出码区分「环境未装」与「代码错误」。

## 当前基准数值（S4 解析结果）

| 指标 | 数值 |
|---|---|
| 气隙磁密 Bg | 0.776 T |
| 齿/轭磁密 | 1.651 T（≈Bsat 1.65 T，临界） |
| 空载反电势 | 132.4 V RMS |
| 齿槽转矩 | 0.454 N·m（1.82% 额定） |
| 额定转矩 / 脉动 | 25.0 N·m / 8.0% |
| 过载能力 | 47.5 N·m（1.90×），过载齿部 1.90 T 饱和 |
| 铜耗 / 铁耗 | 138.6 W / 39.0 W |
| PM 涡流 | 6.44 W（无分段）→ 0.40 W（4 段） |
| 效率 | 93.87% |
| Ld = Lq | 2.52 mH |
| 退磁 B_min（150°C 三相短路） | 0.627 / 0.749 T，SF 3.1–3.7 |
| 最低力波阶次 | 4 阶（S8 按 \|μ·2p±ν·Q\| 推导；主导 8 阶） |

## S7 热分析结果（7 节点 LPTN，`thermal_analysis.py`）

热源取自 S4：铜 138.6 W（端部 42.9% / 槽内 57.1%）、铁 39.0 W（齿 15.0 / 轭 21.3 / 转子 2.7）、
PM 涡流 0.40 W、机械 58.9 W（70% 机壳 / 30% 转子）、杂散 19.6 W（齿轭各半）＝ **256.5 W**。
边界：T_amb=40°C，机壳 OD 170 mm，筋化面积系数 3.0 → A_eff=0.288 m²。

| 节点 | 强迫风冷 h=30 | 自然对流 h=10 |
|---|---|---|
| 端部绕组 EW | 88.4°C | 147.7°C |
| 槽内绕组 WS | 80.9°C | 140.3°C |
| 齿 TOOTH | 72.9°C | 132.3°C |
| 轭 YOKE | 70.6°C | 129.9°C |
| 机壳 HOUSE | 69.7°C | 129.0°C |
| 转子 ROTOR | 76.1°C | 135.4°C |
| 磁钢 MAGNET | 76.1°C | 135.4°C |
| **绕组热点** | **89.5°C**（+49.5 K） | 148.8°C（+108.8 K） |

| 校核项 | 判据 | 强迫风冷 | 自然对流 |
|---|---|---|---|
| 绕组热点 | ≤155°C（F 级） | ✅ 89.5°C，裕度 65.5 K | ⚠️ 148.8°C，裕度 6.2 K |
| 磁钢温度 | ≤120°C（N35） | ✅ 76.1°C，裕度 43.9 K | ❌ 135.4°C |

结论：
1. 强迫风冷（TEFC 轴流风扇）下热设计**通过**，且裕度充足；**自然对流不可行**（磁钢超 120°C），
   机壳必须带散热筋 + 风扇，此为设计约束而非可选项。
2. 热点在**端部绕组**（88.4°C）而非槽内（80.9°C）：端部损耗占 42.9% 而散热仅靠端腔空气，
   R_eh=0.606 K/W 是最大内部热阻。改善顺序：端部灌封/环氧 → 端盖导热桥。
3. 磁钢温度由定子侧热阻主导，PM 不分段（6.44 W）仅使磁钢 +1.9 K，**分段对热校核非决定性**，
   其价值在效率（6.04 W）与退磁裕度。
4. 磁钢实际约 76°C，而 S4 退磁按 150°C 校核（SF 3.1–3.7），属超保守工况，退磁风险进一步降低。
5. 热容 10.23 kJ/K，τ=1184 s（19.7 min），t95=3610 s（60 min）——短时 1.9× 过载不会立即触发热极限。
6. 复算自检：注入/排出功率偏差 0.000%（三工况），瞬态末端与稳态差 ≤0.35 K。

产物：`projects/results/thermal_summary.json`（含假设/热阻/热容/三工况）、`thermal_nodes.csv`、`thermal_transient.csv`。

## S8 NVH 结果（薄环模态 + Maxwell 应力力波，`nvh_analysis.py`）

结构：轭 R=71.07 mm、t=7.86 mm（t/R=0.111），E_eff=185 GPa，ρ=7650；质量加载系数 0.758
（铁芯 6.95 + 机壳 3.15 + 铜 2.01 kg）。齿 h=20.64 mm、w=10.48 mm、端部附加质量 0.166 kg。

| 阶次 m | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|
| 铁芯模态 Hz | 943 | 2668 | 5116 | 8274 | 12138 | 16707 | 21979 |
| 加载后 Hz | 715 | 2021 | 3876 | 6268 | 9195 | 12656 | 16650 |

齿一阶弯曲 f1=10.37 kHz（k=969 MN/m，m_eq=0.228 kg）；Carter k_C=1.0457，ε_1=0.0437 → B_slot1=0.0339 T。

力波：全部同步力波频率为 **2f_e=200 Hz**（转子谐波与齿槽调制波均以 f_e 旋转，交叉项取非零和频）。

| 阶次 | 来源 | 幅值 kPa | 占比 |
|---|---|---|---|
| 8 | B₁² 自乘 | 119.85 | 67.2% |
| 4 | B₁×Λ₁₂⁻ | 10.47 | 5.9% |
| 20 | B₁×Λ₁₂⁺ | 10.47 | 5.9% |
| 24 | B₃² 自乘 | 9.30 | 5.2% |
| 16 / 32 | B₁×Λ₂₄∓ | 5.24 | 2.9% |
| 12 / 36 | B₃×Λ₁₂∓ | 2.92 | 1.6% |

| 校核项 | 判据 | 结果 |
|---|---|---|
| 同阶避振（2–8 阶） | 偏差 ≥15% | ✅ 最小 2458%（4 阶：200 Hz vs 5116 Hz） |
| 主导 8 阶 | 偏差 ≥15% | ✅ 109× （200 Hz vs 21.98 kHz） |
| 临界转速（包络 0–3000 rpm） | ≥1.0× | ✅ 最小 38373 rpm = 12.8× |
| 2 阶不平衡磁拉力（偏心，f_e） | 偏差 ≥15% | ✅ 843%（100 Hz vs 943 Hz），n_crit=14151 rpm |
| 自检 6 项 | 全通过 | ✅ 6/6 |

结论：
1. **结构侧无共振风险**：8p12s 最低力波阶次为 4 阶而非 S4 估计的 6 阶，但其频率仅 200 Hz，
   而同阶模态 5.1 kHz，裕度两个数量级；工作区 0–3000 rpm 内无任何同阶穿越。
2. **S4 力波口径需纠正**：① 6/10 阶在 8p12s 上不可能出现（|μ·8±ν·12| 无解）；
   ② 20 阶频率应为 2f_e=200 Hz 而非 500 Hz（「阶次×转频」口径对 4/20 阶偏低一半）；
   ③ 主导阶次为 8 阶（2p，B₁² 自乘），幅值 119.9 kPa，占力波能量 67.2%。
3. **噪声治理方向应为降幅值而非加强结构**：结构裕度 12.8×，而 8 阶力波 120 kPa 属大机器量级。
   斜槽可压制齿槽交叉项（4/20 阶，合计 11.8%）并使 8 阶沿轴向错相位，是最直接手段；
   极弧优化则直接影响 B₁ 与低次谐波（B₃=0.278 pu 贡献 24 阶 9.3 kPa）。
4. 局限：薄环模型仅对 m≤8 定量有效（t/R=0.111 略超 0.1，误差 ±15%）；m≥10 阶（20/24/32 阶
   合计 16% 能量）未做定量判据，需 S6 FEA 模态提取复核。齿模态 10.4 kHz 远高于力波频率，
   不构成共振路径；机壳未单独建模（保守取下限）。

产物：`projects/results/nvh_summary.json`（假设/模态/力波/自检/偏心）、`nvh_modes.csv`、`nvh_force_orders.csv`。

## S9 参数敏感性（第一小步：斜槽 × 极弧二维扫描，`sensitivity_design.py`）

方法：以 S4 解析结果（α_p=0.87、无斜槽）为**归一化基准点**，按「磁通比例 × 斜槽系数」缩放：
Φ1 ∝ sin(α_p·π/2)；k_sk(m)=sinc(m·γ/2)，γ=s·2π/Q；基波 m=p=4、齿槽 m=LCM(2p,Q)=24、
8 阶力波按基波平方 k_sk(4)²；维持 25 N·m 则 I ∝ 1/(Φ1·k_sk1)、铜耗 ∝ I²；
铁耗/PM 涡流 ∝ Φ1²；热点按 S7 线性叠加 Δθ=R_hot·ΔP（R_hot=0.1930 K/W）。
几何（Dso/Dsi/叠长/匝数）全部冻结，仅动斜槽与极弧。

15 工况（斜槽 0–2.0 槽距 × 极弧 0.80/0.87/0.93）：

| 斜槽 | 极弧 | k_t | I (A) | Tcog | THD_线 | η | P_cu (W) | 热点 (°C) | σ8 (kPa) | B_齿 (T) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.80 | 0.9712 | 10.18 | 1.76% | 14.97% | 93.74% | 146.9 | 90.7 | 113.1 | 1.604 |
| 0 | 0.87 | 1.0000 | 9.89 | 1.82% | 15.75% | 93.87% | 138.6 | 89.5 | 119.8 | 1.651 |
| 0 | 0.93 | 1.0151 | 9.74 | 1.84% | 20.55% | 93.94% | 134.5 | 88.9 | 123.5 | 1.676 |
| 0.5 | 0.80 | 0.9275 | 10.66 | ≈0 | 1.59% | 93.42% | 161.1 | 93.4 | 103.1 | 1.604 |
| 0.5 | 0.87 | 0.9549 | 10.36 | ≈0 | 2.32% | 93.57% | 152.0 | 92.1 | 109.3 | 1.651 |
| 0.5 | 0.93 | 0.9693 | 10.20 | ≈0 | 3.75% | 93.65% | 147.5 | 91.5 | 112.6 | 1.676 |
| 1.0 | 0.80 | 0.8032 | 12.31 | ≈0 | 1.59% | 92.24% | 214.8 | 103.8 | 77.3 | 1.604 |
| 1.0 | 0.87 | 0.8270 | 11.96 | ≈0 | 2.32% | 92.46% | 202.6 | 101.9 | 82.0 | 1.651 |
| 1.0 | 0.93 | 0.8394 | 11.78 | ≈0 | 3.75% | 92.56% | 196.7 | 100.9 | 84.5 | 1.676 |
| 1.5 | 0.87 | 0.6366 | 15.54 | ≈0 | 2.32% | 89.52% | 341.9 | 128.7 | 48.6 | 1.651 |
| 2.0 | 0.87 | 0.4135 | 23.92 | ≈0 | 2.32% | 80.89% | 810.5 | 219.2 | 20.5 | 1.651 |

（完整 15 行见 `sensitivity_sweep.csv`；1.5/2.0 槽距的 0.80/0.93 列同理，从略）

| 校核项 | 判据 | 最优组合 | 结论 |
|---|---|---|---|
| BEMF 线 THD | ≤8% | 1.59%（0.5 槽距/0.80） | ✅ 15.75% → 1.59%，降 89.9% |
| 齿槽转矩 | ≤1% 额定 | ≈0（模型零点） | ✅ 0.5 槽距即达零点 |
| 效率 | ≥94%（参考） | 93.42%（-0.45 pt vs 基线） | ⚠️ 判据本身在基线即未达成 |
| 退磁 SF（150°C 三相短路） | ≥2.0 | 3.27（基线 3.14） | ✅ 斜槽降低短路电流，SF 反升 |
| 绕组热点 | ≤155°C | 93.4°C | ✅ 裕度 61.6 K |
| 齿部磁密 | ≤1.65 T | 1.604 T | ✅（0.93 极弧 1.676 T 越限） |
| 自检 | 13 项 | 13/13 | ✅ PASS |

**推荐：斜槽 0.5 槽距 + 极弧 0.80**（η 93.42%、THD 1.59%、Tcog≈0、B_齿 1.604 T、σ8 103.1 kPa、SF 3.27）。

结论：
1. **斜槽存在明确最优值 0.5 槽距，而非越斜越好**。0.5 槽距即可把线反电势 THD 压到 2% 量级、
   齿槽转矩压到理论零点，代价仅 4.5% 基波（电流 9.89→10.36 A）；加密到 1.0 槽距，THD 几无改善
   （模型给出与 0.5 槽距完全相同值），但基波再损 17% → 电流 +21%、铜耗 +46%、效率掉 1.4 pt。
   1.5 槽距以上电流 >15 A、热点 >128°C，**工程不可行**（2.0 槽距效率跌至 80.9%、热点 219°C）。
2. **THD 与效率此消彼长，且 94% 效率判据在基线（93.87%）就未达成**，说明「8p12s 集中绕组 + 81 匝冻结」
   这一组合本身不是高效率构型。若要兼顾 THD≤8% 与 η≥94%，必须放开匝数/叠长（S9 第二小步）或改绕组型式，
   单靠斜槽/极弧无解——这是本次扫描最有价值的负面结论。
3. **极弧 0.80 优于 0.87**：5 次谐波 sin(5·0.80·π/2)=0 被解析消掉（THD 15.75%→14.97%，配斜槽后 2.32%→1.59%），
   且齿部磁密由 1.651 T 降到 1.604 T、脱离饱和临界，代价是基波 -2.9%、效率 -0.45 pt。
   极弧 0.93 虽效率最高（+0.07 pt），但 5 次谐波升至 0.172 pu（THD 20.55%）、齿部 1.676 T 入饱和，
   **不推荐**（该效率增益在磁路线性假设失效后不可信）。
4. **斜槽不解决 8 阶力波**：8 阶（2p）力波仅按基波平方衰减，0.5 槽距 119.8→109.3 kPa（-8.8%），
   1.0 槽距 82.0 kPa（-31.6%），代价却是效率 -1.4 pt。S8 提出「斜槽压 4/20 阶」的判断成立，
   但主导的 8 阶能量（67.2%）**只能靠降 B1 或改极槽配合**，斜槽性价比低。
5. 退磁 SF 随斜槽单调上升（3.14→3.27 @0.5 斜槽），因短路电流 ∝ 反电势 ∝ k_t；斜槽在退磁维度是正收益。
6. 局限（须 S6 FEA 复核）：① 斜槽仅轴向相位错位近似，未计端部漏磁与轴向力；② 齿槽「零点」是理想 sinc 结果，
   实机因饱和/工艺偏差残留 10–30%，故**只用于相对比较，绝对值不作判据**；③ 铁耗未随斜槽变化（谐波铁耗未单列）；
   ④ 未校核 537 V 母线电压裕度（斜槽后 E 降至 122.8 V、J 升至 7.35 A/mm²，均在允许范围）。

产物：`projects/results/sensitivity_summary.json`（模型假设/判据/15 工况/Pareto/自检/推荐）、`sensitivity_sweep.csv`。

## S9-2 参数敏感性（第二小步：叠长 × 匝数二维扫描，`sensitivity_stack_turns.py`）

动机：S9-1 证明几何冻结下 THD≤8% 与 η≥94% 不可兼得，故放开仅剩的两个自由度——叠长与匝数。
锚点＝S9-1 推荐点（skew=0.5 槽距、α_p=0.80，L=160 mm、N=81）：η 93.42%、P_cu 161.106 W、
P_fe 36.824 W、I 10.6635 A、E 122.796 V、R 0.47227 Ω。

模型（比值式，以锚点归一化）：
① 转矩守恒 I = I₀(N₀L₀)/(NL)；
② 每匝平均长度 L_turn = 2(L+0.12) m，端部长度 0.12 m 由 R₀ 反标定（ρ=1.72e-8 Ω·m、A_w0=1.652 mm²）；
③ 等槽满率换线 A_w = A_w0·N₀/N ⇒ P_cu ∝ (L+0.12)/L²；
④ 铁耗/PM/杂散 ∝ L（齿轭磁密不变），机械耗 58.9 W 固定；
⑤ 质量：铁+铜+PM ∝ L，机壳 3.15 kg 固定；热点沿用 S7 的 R_hot=0.19297 K/W。

主表（N=81 中间列；同一叠长下 72/81/90 匝的 P_cu、η、ΣP、SF 完全相同，仅 I/E/槽满率不同）：

| 叠长 | I (A) | J (A/mm²) | P_cu (W) | P_fe (W) | ΣP (W) | η | Δη vs S9-1 | E (V) | V_ph (V) | 槽满率 | 质量 (kg) | 转矩密度 (N·m/kg) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 140 | 12.19 | 7.38 | 195.4 | 32.2 | 304.0 | 92.82% | −0.60 pt | 107.4 | 113.8 | 0.391 | 17.51 | 1.428 |
| 160 | 10.66 | 6.45 | 161.1 | 36.8 | 276.8 | 93.42% | ±0.00 | 122.8 | 128.7 | 0.391 | 19.56 | 1.278 |
| 180 | 9.48 | 5.74 | 136.4 | 41.4 | 259.2 | 93.81% | +0.39 pt | 138.1 | 143.7 | 0.391 | 21.61 | 1.157 |

匝数支表（L=160 mm）：72 匝 I=12.00 A / E=109.2 V / 满率 0.348；90 匝 I=9.60 A / E=136.4 V / 满率 0.435。

| 校核项 | 判据 | 结果 |
|---|---|---|
| 槽满率（维持 AWG15） | ≤0.45 | ✅ 0.348–0.435（90 匝 0.435 为上限，仅余 3.3%） |
| 相电压（含 R/X 压降） | ≤197.3 V（0.9·V_dc/√6） | ✅ 最大 159.7 V（180/90），裕度 19% |
| 电流密度 | ≤7.0 A/mm² | ⚠️ 140 mm 为 7.38 越限；160/180 mm 5.74–6.45 通过 |
| 退磁 SF | ≥2.0 | ✅ 全网格 3.27（短路安匝 E/Xs·N 与 N 无关） |
| 绕组热点 | ≤155°C | ✅ 最大 40+0.1930×304.0=98.7°C |
| 自检 | 14 项 | ✅ 14/14 PASS |

**推荐：维持 L=160 mm / N=81 匝（效率不变、无重绕成本）；若要提效率，取 L=180 mm（η 93.81%，代价 −9.5% 转矩密度）。**

结论：
1. **待验证假设成立且是严格结论：定转矩下 P_cu 与匝数无关**（3 组叠长下 72/81/90 匝铜耗差 <1e-6 W）。
   机理：I ∝ 1/N 与 A_w ∝ 1/N 相消，电流密度只由叠长决定（J ∝ 1/L），铜体积固定 ⇒ P_cu = ρJ²V_cu。
   **匝数是电压旋钮，不是效率旋钮**——这一点纠正了 S9-1 结尾「效率瓶颈在匝数/叠长」的表述，实为「只在叠长」。
2. **叠长是唯一效率杠杆，但收益递减且与转矩密度对冲**：160→180 mm，P_cu −15.3%（161.1→136.4 W），
   而铁耗+杂散 +12.4%（36.8→41.4 W），净 ΣP −6.4%，η +0.39 pt；代价质量 +10.5%、转矩密度 −9.5%。
   反向 140 mm：η 92.82%（−0.60 pt）且 J=7.38 A/mm² 越 7.0 上限，**不可取**。
3. **三种效率判据口径所需叠长（本步最硬的结论）**：S9-1 设计点 +0.5 pt（93.92%）→ **187.3 mm**；
   原绝对 94% → **193.6 mm**；S4 解析基线 +0.5 pt（94.37%）→ **255.4 mm**。
   扫描上界 180 mm 内**无一点满足 +0.5 pt 判据**（最好 93.81%，差 0.11 pt）。
4. **口径澄清**：若判据取「S4 基线 93.87% + 0.5 pt」，则该目标在 150 mm 机座内物理上不可达
   （需 255 mm 叠长，L/D=1.70、质量约 29 kg）。故 94% 级目标应重新谈判为 **93.8%（L=180）**，
   或改分布式绕组/放大机座——继续在集中绕组上优化斜槽/极弧/匝数已无空间。
5. **匝数选择建议 81 匝（不改工装）**：效率不变；E=122.8 V 对 537 V 母线余量 34%；
   SF 恒 3.27。90 匝唯一系统级收益是相电流降至 9.60 A（逆变器通态损耗↓，本步未量化），
   但槽满率只剩 3.3% 余量；72 匝把槽满率浪费到 0.348，无收益。
6. 局限：解析比值模型，逆变器损耗/端部漏磁/铁耗谐波未计；端部长度 0.12 m 为反标定值；
   叠长 >180 mm 会突破现机座长径比（L/D 由 1.07 升至 1.25–1.29），须同步改机壳与轴系，本步未建模。

产物：`projects/results/sensitivity_stack_turns.json`（锚点/假设/判据/9 工况/最优/所需叠长/自检）、
`sensitivity_stack_turns.csv`。

## 下一次应推进（Maxwell 优先）

### 优先级 1 — M4 空载瞬态求解（下一步，桌面会话）

1. 打开 `D:\ANSYS_Run\M4_25Nm.aedt`，先确认：`ModelDepth='160mm'`、`M270_35A`×2、
   `BoundType='Coil'`×12 + `Winding Group`×3、`VectorPotential1 Edges(7)`、`Setup1`。
2. `Setup1` 设为空载（绕组 `Current=0A`），Transient 运行 0.02 s / 50 µs。
3. 导出 `Moving1.Torque`（齿槽）与 `WindingA/B/C.Voltage`（BEMF）到 `D:\ANSYS_Run\csv\`。
4. `ingest_fea.py` 计算 BEMF RMS/THD、齿槽峰值 → `fea_results.json`。
5. 验收：BEMF RMS 与解析 132.4 V 同量级；齿槽 ≤5% 额定；CSV 非空。

### 已关闭：M3（2026-11-07）

- `M4_25Nm.aedt`：`M270_35A`×2、`BoundType='Coil'`×12、`Winding Group`×3、
  `VectorPotential1 Edges(7)`、`Setup1` 全部落地。
- 关键坑：AEDT 2021.1 的 `AssignCoilGroup` 参数类型极挑；改用逐个
  `AssignCoil(["NAME:...", "Objects:=", ["Coil_x"], "Conductor number:=", "40",
  "PolarityType:=", "...", "Winding:=", "WindingA"])` 一次成功。

### G3 状态（数据层已修，代码层待补）

- **数据层**：`M4_25Nm.aedt` 的 `ModelDepth='160mm'`，不再是默认 `1meter`，M4 求解可直接用。
- **代码层（代码债，不阻塞 M4）**：`scripts/main.py::_gen_setup` 与
  `maxwell_model/solve_25Nm_SPMSM.py` 仍需注入 `ModelDepth`，避免下次重建又丢；
  `MotorConfig.validate()` 断言 `stack_length > 0`。

### 优先级 3 — M4/M5/M6（求解与回填）

- M4 空载瞬态：BEMF + 齿槽，导出 `bemf.csv` / `tq_noload.csv`。
- M5 负载瞬态：三相电流，导出 `tq_load.csv` / `ia_load.csv`。
- M6：`ingest_fea.py` → `fea_results.json`，回填报告。
- 判据：M5 的 `T_avg` 与解析 25 N·m 同量级（±20%），否则先修模型，不要改报告口径。

### 已关闭：M0/M1/M2（2026-11-07）

- 复现命令（本机可直接跑，约 25 s/轮）：
  ```bat
  python projects\25Nm_PMSM\maxwell_model\prepare_batch.py --workdir D:\ANSYS_Run
  "D:\Program Files\AnsysEM\AnsysEM21.1\Win64\ansysedt.exe" -RunScriptAndExit "D:\ANSYS_Run\m2_run.py"
  ```
  产物：`D:\ANSYS_Run\M2_25Nm.aedt` + `m2_report.txt`（对象清单）+ `m2_run.log`（AEDT 日志）。

## 历史「下一次应推进」计划（G2，已关闭 2026-11-07）

G1 已关闭（建模入口可从零重建 25 N·m 机型）。下一步转 G2：
- 现象：干净 venv `pip install -e .` 后 `python projects/25Nm_PMSM/make_report.py` → `ModuleNotFoundError: matplotlib`
  （`numpy` 同理，`pytest` 缺）
- 验收：新建 venv → `pip install -e .` → `make_report.py` rc=0，产出 >200 KB HTML 且 `data:image/png;base64` ≥5；
  无需手工补装；`SKILL.md` 写明安装前置
- 可选同类修复：`pyproject.toml` 依赖声明（`numpy`/`matplotlib` 进 `dependencies` 或 `[plot,dev]` 前置说明）、
  `make_report.py` ImportError 中文提示 + P7 转义告警
- 注意：只改 `pyproject.toml` / `SKILL.md` / `make_report.py`，不要碰工作区里已存在的其他未提交改动

## 历史「下一次应推进」计划（S10，未启动）

**S10 制造公差、BOM 与图纸**（本周不主动开新阶段，排 G1–G3 之后）
- 脚本 `projects/25Nm_PMSM/manufacturing_bom.py`，输出
  `projects/results/bom.csv` + `manufacturing_summary.json`
- ① **BOM**：定子铁芯（M270-35A，冲片+叠压）、转子铁芯、N35 磁钢（8 块，含 4 段分段）、
  漆包线（AWG15，按 L_turn=2(L+0.12)、a=2 折算总长与净重）、机壳（带散热筋）、端盖×2、
  轴、轴承×2、绝缘件/槽楔/灌封、旋变——数量、单重、材料牌号全部由 `pmsm_config.py` 与
  `sim_summary.json` 的质量派生，**禁止手填数字**；单价列用区间并标注来源（估算/询价）
- ② **公差链（RSS + Monte-Carlo 双算，互校）**：气隙 g=0.675 mm 的公差预算
  - 贡献项：定子内径 ±0.02、转子外径 ±0.02、同轴度 ±0.03、轴承游隙 ±0.01、端盖止口 ±0.02
  - 传递函数：∂Bg/∂g 用 S4 的 Carter 有效气隙模型（g_eff=2.532 mm）解析求导，
    再按 Bg→Tcog(∝Bg²)、Bg→σ8 力波、Bg→UMP（2 阶，S8 已有公式）三路放大
  - 判据：g_min ≥0.50 mm（防扫膛）、Tcog ≤1% 额定、UMP 引起的轴承当量载荷增量 ≤10%
- ③ **磁钢 Br 公差 ±3%**（N35 批次离散）：对 E_rms、T、退磁 SF 的影响（沿用 S9 的 kt 缩放）
- 自检项：RSS 与 MC（≥10⁴ 抽样，固定随机种子）标准差偏差 <10%；公差贡献排序稳定；
  气隙名义值复现 0.675 mm；BOM 总重与 S9-2 的 19.56 kg ±10% 一致

## 每日任务约定

1. 先读本文件 + `git log --oneline -10`，确认进度，避免重复。
2. 只推进「下一次应推进」所指阶段的一小步（建议 ≤120 行代码）；**优先 M0–M6（Maxwell 实机）**，其次 G3，最后 S10/S11。
3. 所有数值由脚本计算并落盘到 `projects/results/`，禁止编造。
4. 完成后更新本文件的阶段状态、产物路径、关键结论与新的「下一次应推进」。
5. 验证：运行本阶段脚本 + `python -m pytest -q`（原有失败不算本次引入）。
6. 只 `git add` 本阶段相关文件；**不要 `git add -A`**；不提交 `.aedt`/`.asol`/`__pycache__`/大图。
7. 验证通过后 `git push origin main`；失败或冲突则保留本地提交，禁止 `--force`。
8. **Maxwell 优先**：每天至少尝试一次 Maxwell 实机启动/建模（M0–M6），记录 rc、日志、`.aedt` 是否生成；沙箱无法启动时标注 blocked 并给出桌面一键命令，**不得用解析仿真替代 Maxwell 验证**。
9. 只有 M4（Maxwell 求解）通过后，才推进 S10/S11 等非 Maxwell 阶段。

## 备注

- **Maxwell 可由 agent 直接驱动（2026-11-07 更正）**：此前「沙箱无法启动 Maxwell」的结论**作废**。
  真机实测 rc=0，限制只来自命令行用法：脚本模式**不能带 `-ng`**，且 `oDesktop` 由 AEDT 预注入、
  IronPython 为 2.7。仓库内脚本为权威源，`D:\ANSYS_Run\` 下为 ASCII 路径的批跑副本（由
  `prepare_batch.py` 自动生成）。
- 8p12s 集中绕组、非斜槽，谐波（BEMF 线 THD 15.8%、THD_Bg 32.8%）偏高；S9 已确认
  斜槽 0.5 槽距 + 极弧 0.80 可把线 THD 降到 1.59%，代价 0.45 pt 效率——**效率瓶颈只在叠长，
  与匝数严格无关**（S9-2 已验证）；达 94% 需 L≈194 mm，超出 150 mm 机座常规长径比。
