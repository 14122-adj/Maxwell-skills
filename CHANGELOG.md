# Changelog

All notable changes to **ansys-maxwell-motor** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — 2026-11-15（M7：模板路径负载工况，`T_avg` 22.6296 N·m / 脉动 14.688%）

把「负载工况」从手写路径搬到生成器路径，G6 的最后一条验收（负载 `T_avg`）由此关闭。
关键约束是**空载生成物必须逐字不变** —— 否则 M8 的齿槽证据就不再对应当前仓库模型。

- `scripts/motor_config.py`：新增 `load_case` / `current_phase_deg` / `current_sign`
  三个字段（默认空载）与三条 validate 闸口（符号只能 ±1、三相初相必须 3 个、
  负载时电流/频率必须为正）。
- `scripts/main.py::_gen_winding()`：新增负载分支，把
  `I = sign·√2·I_rms·sin(2πf_e·Time + φ)` 在**宿主侧**算成字面量再写进生成物
  （IronPython 2.7 只吃字符串）；**空载分支保持原文本**，`--check` 仍 8/8 无漂移。
- `projects/25Nm_PMSM/gen_maxwell_model.py`：新增 `--case {noload,load}`；
  `build_config(load=...)`；负载生成到 `maxwell_model_load/`（派生件，已入 `.gitignore`）；
  `--check` 拒绝负载工况（不入库、不参与漂移门禁）。
- `projects/25Nm_PMSM/maxwell/tpl_solve_noload.py`：增 `TPL_CASE` 开关
  （`T4_tpl_load.aedt` / `csv_tpl_load/` / `tq_load.csv` / `flux_load_*.csv`），
  求解与导出逻辑一字不改；应用日志改 `tpl_app_<case>.log`，避开 AEDT「脚本同名 .log」。
- `projects/25Nm_PMSM/maxwell/tpl_run.py`：增 `--case`，并把 `CASE`/`BODY`
  **写死**进驱动副本（环境变量丢失时不会把负载解覆盖到空载基线）。
- 新增 `projects/25Nm_PMSM/m7_load_check.py`：末周期（10 ms / 201 点）梯形积分 +
  `ingest_fea.load_block` 双法互校；电流用原生 `WindingX_TrCrv.txt` 逐点比对并与
  指令表达式对表；输出 `projects/results/fea/m7_load_summary.json`，
  证据波形落 `projects/results/fea/m7_load/`。
- 真机（1 轮 rc=0，19:05:21→19:17:27，**726 s**，`T4_tpl_load.aedt` 1,046,651 B / 24 sheets）：
  **`T_avg` 22.6296 N·m**（手写 M5 22.3344，**+1.32%**；vs 25 N·m **−9.48%**）、
  **脉动 14.688%**（手写 32.389%）、末周期 DFT 600 Hz 分量 2.04 N·m 独占主导、
  电流逐点最大偏差 7e-5 A（0.001%）、Σ(v·i)=+37367.58（电动）、
  功率平衡 `T·ω` vs `3EI` **−0.62%**；导出 4 个 CSV 各 401 行。
- 回归：新增 `tests/test_load_winding.py`（11 例：空载零电流、基线不漂移、
  幅值/相位/符号、负载只改 winding、`--check` 拒绝负载、配置闸口）与
  `tests/test_m7_load_check.py`（8 例：`ms`/`mNewtonMeter` 单位、末周期窗口、
  梯形积分、指令电流对表 M5、原生 TrCrv 解析）。pytest **331 passed**、ruff 全通过。
- **同日 THD 复核（副作用记账）**：用 `ingest_fea.analyse_signal`（跳首周期、2–15 次）
  同口径复算 M8 梨形槽波形 —— 线 BEMF THD **11.180%**，比矩形槽 **10.595%**
  高 **0.59 pt**（矩形槽同法复现 10.595%，方法自证）⇒ **窄槽口压齿槽与压 THD 对冲**，
  G4 的 THD 项仍 FAIL，探索闸门不算"全绿"（`PROBLEM_LEDGER` P11）。

### Added — 2026-11-14（M8：表 2 梨形槽落地，齿槽 27.37% → 3.52%）

把 25 N·m 机型的定子槽从「窄口矩形」换成表 2 梨形槽，并第一次把「几何顶点」与
「线圈轮廓」收敛到**同一个数据源**：

- 新增 `scripts/slot_profile.py`：梨形槽 11 关键点 + 10 段（`Arc` 起点索引 4）+
  底部半圆 16 段离散（`pear_outline`）+ 鞋带面积/形心内缩/环带实切面积。
  几何字面量与线圈 `coil_pts` 都从它派生 —— 旧模板把同一组坐标写了两遍，
  改一处就错位（`StatorOuter and Coil_x intersect` 的来源）。
- `scripts/main.py::_gen_geometry()` 的 `pear` 分支重写：`x1=r_bore+Hs0`、
  `x2=+Hs1`、`x3=r_bore+Hs2−Rs`、`x4=r_bore+Hs2`（旧版全部从 `x0=r_bore−0.2` 起算，
  整槽短 0.2 mm 且只有 7 点、`Arc` 起点错在 3），12 个 `PLPoint`（11 + 闭合）+ 10 段。
- `scripts/motor_config.py::validate()` 增梨形槽三道闸：`Rs` 必须等于 `Bs2/2`
  （否则半圆起点不在圆上，Acis 补隐式连线静默变形）、`Hs2−Hs0−Hs1−Rs ≥ 0`
  （直身段为负即槽形自交）、轭部 <6 mm 告警。
- `projects/25Nm_PMSM/gen_maxwell_model.py`：`build_config` 切 `PEAR` + 表 2 六尺寸；
  `pmsm_config.py` 增 M8 梨形块与派生量（x0..x4 / 轭 16.0 / 面积 93.03 / 线圈 71.9 /
  满率 0.710），旧矩形常量保留供 S7–S9 复现。
- `template_vs_manual.py` 增 `--tag`：M8 证据落 `fea/m8_pear/` 与
  `template_vs_manual_m8_pear.json`，不覆盖 G4 的 `fea/tpl/`。
- 真机（1 轮 rc=0，`ANALYZE_OK 673.6s`，`T4_tpl_noload.aedt` 1,313,661 B / 24 sheets）：
  `StatorOuter` **9,764.151 mm²**（解析预测 9,764.16，偏差 0.001%）、`Coil_1`
  **71.863 mm²**（预测 71.863）；BEMF 相 RMS **120.5594 V**（基线 118.8832，**+1.41%**）；
  齿槽峰峰值 **0.8801 N·m = 3.52% 额定**（基线 6.84307，**−87.1%**），主频 598.5 Hz
  ≈ 24×25 Hz（槽极 LCM 序），两个 10 ms 窗口的峰峰值一致（0.8801/0.8801）。
- 回归：新增 `tests/test_pear_slot.py`（23 例：五条基准线、11 点对称性、10 段覆盖、
  面积三重自洽、弧采样亏损、线圈 72±5% 与不进气隙、满率、validate 闸口）；
  `test_gen_maxwell_model` 的线圈内缩判据改按槽型取多边形；
  `test_model_depth` 不再自抄一份机型配置（M8 换槽型后它才是红的根因）。
  pytest **312 passed**、`ruff` 全通过、`--check` 8/8 无漂移。

### Fixed — 2026-11-13（G4：模板路径 9 处"能建不能解"缺陷，空载解与手写路径等价）

模板产出的模型此前只能"建出来"，不能"解对"。今日把 m4 手写工程跑出 401 点解的全部前提
回灌模板，共 9 处：

- 几何：磁钢由**平板弦**（径向 45.825..47.775，插进定子 1.275 mm）改为**环形扇区**
  （43.875..45.825，弧 39.15°，内外弧各离散 24 段）；转子半径改为
  `磁钢内半径 + 0.03 mm` 并挖出磁钢浅坑（界面互补、无相切顶点）；槽口第一边改为
  `r_bore - 0.2 mm`（消除与内孔圆弧的相切非流形）；线圈由**槽轮廓 0.88 内缩**
  得到（原 13.2×5.7 矩形在 r=49.65 处穿出 3.2 mm 宽的槽壁）；
  `Region` 与定子/转子/磁钢/线圈/Band 布尔分离（`KeepOriginals=True`）。
- 材料：`_gen_materials()` 新增铁芯材料定义（`STEEL_MATS`，线性化 µr=1000 / σ=2.0e6 /
  ρ=7650），`StatorOuter`/`RotorOuter` 绑定 `stator_material`/`rotor_material`
  —— 此前定转子建的是 `vacuum`，磁路整个落在空气上且不报错。
- 边界：`AssignVectorPotential` 从 `_gen_boundary()` **前置进 `_gen_geometry()`**，
  紧跟 Region 建圆之后。Region 一旦切孔，`GetEdgeIDsFromObject("Region")` 会把外圆
  与所有孔边一起返回，`AZ=0` 落到材料界面 ⇒ 磁通被短路（求解器不报错）。
- 求解：存场改 `N=2`（与 m4 全时长口径一致，401 个采样点不变）。
- 新增 `projects/25Nm_PMSM/maxwell/tpl_solve_noload.py`（同进程 execfile 生成物 →
  `SaveAs` → `Analyze("Setup1")` → 导出 `FluxLinkage`/`Moving1.Torque` 全时长解，
  含面积自检与 `data_rows` 非空校验）与 `maxwell/tpl_run.py`（宿主侧清洗脚本、
  起 `ansysedt -RunScriptAndExit`、抓日志）。
- 新增 `projects/25Nm_PMSM/template_vs_manual.py`：两条路径逐项对比，含单位换算
  （`Time [us]` / `Torque [mNewtonMeter]` —— 403 N·m 的来源）与 `e = -dλ/dt` 口径。
- 真机结果（1 轮 rc=0，`ANALYZE_OK 437.1s`）：`T4_tpl_noload.aedt`（767,290 B，
  24 sheets，Region 2 faces 面积守恒 11,053.35 mm²）；BEMF 相 RMS **118.9077 V**
  vs 手写 118.8832 V（**+0.02%**）；齿槽峰峰值 **6.8181 N·m** vs 6.84307（**−0.37%**）；
  三相磁链峰峰 0.518813/0.518829/0.518833 Wb（不平衡 0.004%）。
- 回归：新增 `tests/test_gen_maxwell_model.py::TestG4GeometrySelfConsistency`（7 例：
  磁钢扇区半径、转子内嵌、线圈顶点落在槽内（射线法，槽肩是凹角）、Region 布尔、
  铁芯材料绑定与边界先于布尔）与 `tests/test_template_vs_manual.py`（6 例单位/求导口径）；
  pytest **289 passed**、`ruff check scripts tests examples` 全通过。

### Fixed — 2026-11-12（G3b：建模模板 8 处 API 回灌，真机全链路建模通过）

- `scripts/main.py::_gen_geometry()` 回灌 M2 阶段手改出来的 4 处真机修复：
  `SetModelUnits` 用 `"Units:="`（非 `"Length:="`）、`DuplicateAroundAxis` 补第 3 参
  `["NAME:Options", ...]`、槽克隆体按 `Slot_1_1..` 实名相减、`CreatePolyline` 的点/段
  嵌进 `PolylineParameters`（pear / rectangular / trapezoidal 三种槽型同步）。
- 真机连跑三轮又抓出 4 处同类缺陷并修复：
  `_gen_winding()` 改用逐槽边 `AssignCoil`（2021.1 的 `AssignCoilGroup` 是 2 参签名，
  单数组调用报 `expects at least 2 arguments`）；`_gen_boundary()` 的
  `AssignVectorPotential` 改用运行期 `GetEdgeIDsFromObject`（`can only be assigned on
  1D entities`），`AssignBand` 键名改 `"Init Pos:="`（带空格）；`_gen_mesh()` 用
  `AssignLengthOp` 替代 2021.1 不存在的 `AssignSurfApproxOp`。
- `projects/25Nm_PMSM/gen_maxwell_model.py` 重构为可测函数
  （`build_config` / `render_scripts` / `combine` / `artifacts` / `write_all` / `check`），
  新增 `--check`（漂移列出文件并 rc=1）与 `--out_dir`（此前参数被静默忽略）；
  合并脚本表头数值改为随配置走，不再硬编码 150/93/160/0.675。
- `projects/25Nm_PMSM/maxwell_model/prepare_batch.py` 新增 `--aedt`，回归验证不再覆盖
  `M2_25Nm.aedt`。
- 新增 `tests/test_gen_maxwell_model.py`（13 例）：生成物与模板逐字比对（双向防漂移）、
  8 处 API 修复的模板级护栏、四种槽型几何脚本可编译、`--check` 反向验证。
- 真机证据（rc=0 ×3）：第 3 轮 `G3b_regen3.aedt`（288,557 B）`BODY_OK`，`Sheets=24`、
  `Solids=0`、`Conductor number'='40'` ×12、`VectorPotential1`、`MotionSetup1`
  （`Move Type='Rotate'`/1500 rpm）、`Setup1`（20 ms/5e-5 s）、`ModelDepth='160mm'`。
- 文档：`docs/MAXWELL_INTERNALS.md` 新增 §13（8 处陷阱 + 报错原文 + 三轮证据）。

### Added — 2026-11-11（G3：2D 叠长 `ModelDepth` 注入闭环）

- `scripts/main.py`：`_gen_setup()` 在 `SetDesignSettings(DesignSettingsData)` 里注入
  `"ModelDepth:=", "<stack_length>mm"`；新增 `format_mm()` 归一尺寸字符串
  （160.0 → `160mm`，非整数保留有效位）。非正叠长直接在生成期抛 `ValueError`，
  不让 `Nonemm` 流到 AEDT。
- `scripts/motor_config.py`：`validate()` 增叠长闸口（缺失/非正 → `ERROR`，L/D>3 → `WARNING`）。
- `projects/25Nm_PMSM/maxwell_model/solve_25Nm_SPMSM.py`：`MODEL_DEPTH = "160mm"`
  进 `SetDesignSettings`，并删除文件头误导性的 `-ng -RunScriptAndExit`（与
  `-RunScriptAndExit` 互斥，是 2026-11-07 之前"启动即失败"的源头）。
- 生成物 `maxwell_model/setup.py` / `build_25Nm_SPMSM.py` 同步落地 `ModelDepth`。
- `tests/test_model_depth.py`（27 例）：模板注入 + 随叠长变化 + 生成文本可编译 +
  `validate()` 闸口 + 生成物与模板不漂移 + **4 处真机 API 修复护栏**。
- 真机验证（rc=0 ×3）：`G3_depth160.aedt`（23,905 B → `ModelDepth='160mm'`）、
  `G3_depth180.aedt`（23,930 B → `'180mm'`）、`G3_generated_setup.aedt`
  （23,906 B → `'160mm'`，由模板产出的 `setup.py` 本体执行）。

### Fixed — 2026-11-11（生成器段序与 API 说明）

- `projects/25Nm_PMSM/gen_maxwell_model.py`：合并顺序改为 `setup → materials → geometry`。
  旧序让合并脚本先建几何再定义材料，Maxwell 在 `SetMaterial` 处报 Unknown material，
  也是 `tests/test_prepare_batch.py::test_materials_before_geometry` 长期红灯的根因。
- 同文件增「⚠ 重跑前必读」：4 处真机 API 修复尚未回灌 `scripts/main.py` 模板，
  空白重跑会把模型改回不可解；护栏为 `TestModelerApiRegressions` 与
  `TestCombinedScriptApiFixes`。

### Added — 2026-11-10（M6：FEA 结果进入交付报告）

- `projects/25Nm_PMSM/make_report.py` 新增 §11「Maxwell 2D FEA 实测交叉校验」：
  `load_fea()` 读 `results/fea_results.json`，生成 10 行「解析 vs FEA」逐项对照表
  （相/线 BEMF、三相不平衡、THD、齿槽 ptp、`T_avg`、脉动、功率平衡、指令电流、`Kt`）
  与 3 张图（三相空载 BEMF、负载+齿槽转矩、齿槽频谱标注 600 Hz）。
  首屏 KPI 增「FEA 平均转矩」，结论区首条改为以 FEA 为准。
- `projects/results/fea/`：M4/M5 波形留档（`flux_a|b|c.csv`、`tq_noload.csv`、`tq_load.csv`，
  各 401 行全时长解），报告不再依赖 `D:\ANSYS_Run` 的外部文件即可复现。
- `tests/test_report_fea.py`（11 例）：JSON 结构/判据口径/物理自洽、CSV 必须 401 行、
  用留档 CSV 重算 `ingest_fea.compute()` 复现 JSON、源码级降级契约。

### Fixed — 2026-11-10（报告过期表述与渲染陷阱）

- 报告首页「FEA 待桌面执行」与附录「agent 沙箱无法初始化 AEDT 运行时」两句已与实机事实
  （2026-11-08 / 11-09 两次真机求解）相反，改为记录真实工程路径、求解耗时与 401 点解。
- §11 为普通字符串拼接，`%%` 会被原样输出（首版渲染出 `±25%%`、`折 81 匝 × %.5f`）。
  现以「生成后 grep `%%` 与 `%.Nf` 残留数均为 0」作为验收项。

### Added — 2026-11-09（M5 负载瞬态：三相 9.89 A，`T_avg` 判据通过）

- `maxwell/m4_build_solve.py` 增加 `MAXWELL_CASE=load` 负载工况（与空载共用同一条建模
  代码路径，几何零改动）：三相电流型绕组注入 `−13.9866*sin(2*pi*100*Time+φ)`，
  φ = 120°/240°/0°（由 M4 空载磁链最小二乘拟合得到），相电阻 0.47227 Ω；
  试算判号改用原生 `WindingX_TrCrv.txt` 的 `Σv·i`，**不导报表**。
- `ingest_fea.py`：新增 `load_block()`（`T_avg`/脉动/`Kt`/功率平衡）与
  `read_native_trcrv()`（原生 TrCrv 解析），新增 `--native-dir`；
  电流校核支持「报表 CSV 整周期 RMS」与「原生环形缓冲逐点波形比对」两种口径。
- `tests/test_ingest_fea.py` +7 例（`TestLoadBlock` 8 例、`TestNativeTrCrv` 3 例）。
- `docs/MAXWELL_INTERNALS.md` §11：负载工况四个新坑（改已求解工程绕组电流 → 解不落盘、
  `Analyze()` 返回 None、试算后导报表会绑死试算解、TrCrv 列含义与环形缓冲）。

### Fixed — 2026-11-09（M5 真机四轮排查）

- **改已完成工程的绕组电流不可行**：`EditWindingGroup` 成功后设计进入
  `Solutions have been invalidated`，`Analyze` 跑完 304 s 但 `.aedtresults` 只落试算 10 步，
  `CreateReport` 建得出、`ExportToFile` 只写表头。对照实验（未编辑工程）得 401 行
  ⇒ 是工程状态问题，负载工况必须重建。
- **试算后导出转矩报表会污染全时长导出**：`Moving1.Torque` 绑到试算解，
  全时长后再导仍是 21 行（0–1 ms），而同解 `FluxLinkage` 为 401 行。
- `m5_load_solve.py` 作废（其「打开 M4 工程改电流」路线被证伪），改由
  `m4_build_solve.py` 的 `MAXWELL_CASE=load` 承担；`m5_load_export.py` 保留为独立
  导出通道诊断脚本。

### Added — 2026-11-07（Maxwell 批跑通道）

- `projects/25Nm_PMSM/maxwell_model/prepare_batch.py`：把「控制台粘贴式」建模脚本转换为
  `ansysedt.exe -RunScriptAndExit` 可直接执行的脚本（剥离 `ScriptEnv` 依赖、f-string 降级为
  IronPython 2.7 写法），并生成带 `SaveAs` + 对象清单的驱动脚本。
  一条命令即可复现 M2 几何：`python prepare_batch.py --workdir D:\ANSYS_Run`。
- `tests/test_prepare_batch.py`（12 例）：锁定「ScriptEnv 必须剥离」「f-string 必须降级」
  以及三处 Modeler API 误用的回归（`Units:="mm"`、`DuplicateAroundAxis` 三参、槽名 `Slot_1_i`）。

### Fixed — 2026-11-07（Maxwell M0–M2 打通）

- **M0 误判纠正**：`ansysedt.exe -ng` 不能单独用于脚本模式，`-ng` 仅与
  `-batchsolve/-batchsave/-batchextract` 组合。脚本模式正确命令为
  `ansysedt.exe -RunScriptAndExit <脚本>`。此前连续多日记录的「沙箱环境 blocked」作废，
  真机实测 rc=0，`M1_min.aedt` 与 `M2_25Nm.aedt` 均已生成。
- `build_25Nm_SPMSM.py` 四处真机暴露的 API 缺陷：
  1. `SetModelUnits` 键名 `Length:=` → `Units:=`；
  2. `CreatePolyline` 误传 4 参 → 点/段嵌入 `PolylineParameters` 字典（2 参）；
  3. `DuplicateAroundAxis` 缺第 3 个 `NAME:Options` 参数；
  4. 槽克隆实名为 `Slot_1_1..Slot_1_11`，`Subtract` 却写死 `Slot_2..Slot_12` → 改按实际名生成。
- 段落顺序：`MATERIALS` 提前到 `GEOMETRY` 之前，否则 PM 引用未定义材料导致 `CreateRectangle` 失败。

### Planned

- More canonical pole-slot combinations (currently 19; target 30+)
- PyVista / Matplotlib 3D winding visualization
- Direct PyAEDT integration (no manual IronPython paste step)

### Fixed — 2026-11-07（审计 G2 / P2 / P7）

- **报告链路开箱可用**：`numpy>=1.24`、`matplotlib>=3.7` 由 `[plot]` extra 提升为
  `[project].dependencies` 核心依赖；干净 venv 只需 `pip install -e .` 即可让
  `projects/25Nm_PMSM/make_report.py` 跑通（rc=0、HTML 255 KB、内嵌 6 图）。
  `[plot]` 保留为向后兼容别名。
- `make_report.py` 捕获 `ModuleNotFoundError`，打印中文安装提示并以 **rc=2** 退出，不再抛裸栈。
- `make_report.py` 附录路径中的无效转义 `\P` 修复（P7，`-W error::SyntaxWarning` 通过）；
  退磁柱状图改为真正内嵌（5 → 6 张图），`阈值 0.2T` 改 ASCII 消除 DejaVu 缺字形告警。
- 新增 `tests/test_report_deps.py`（4 例）锁定「核心依赖必须声明」「缺包必须 rc=2」两条契约。

---

## [4.4.0] — 2026-09-12 — "GitHub-ready release"

### Added

- **Canonical pole-slot winding table** (`references/winding_layouts.md`,
  19 entries) — single source of truth for slot → phase + polarity mapping
- **Lookup-first WindingBuilder** (`scripts/pmsm_winding_builder.py` v2) —
  consults the canonical table before computing
- **Standalone winding CLI** (`scripts/winding_layout.py`) — one-line slot
  map lookup for any pole-slot combination
- **Pytest test suite** (147 tests across 3 modules in `tests/`)
- **Examples directory** (4 runnable scripts in `examples/`)
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — lint + test on
  Linux/macOS/Windows × Python 3.10-3.13
- **Issue + PR templates** (`.github/ISSUE_TEMPLATE/`,
  `.github/PULL_REQUEST_TEMPLATE.md`)
- **`pyproject.toml`** — modern Python packaging with entry points
  (`maxwell-winding`, `maxwell-build`, `maxwell-test`), ruff + pytest
  + mypy configuration
- **CHANGELOG.md, CONTRIBUTING.md, Makefile** — full GitHub-submittable
  project structure

### Fixed

- **8p/12s concentrated winding polarity bug** — v1 algorithm produced all
  `+` polarity, violating Pyrhonen AABBCC alternating pattern. v2 fixes
  this via canonical lookup; fallback algorithm also corrected.
- **Three conflicting winding conventions in the codebase** — unified to
  the "standard" convention (`A+/B+/C+ → PolarityType=Positive`,
  `A-/B-/C- → PolarityType=Negative`), with `polarity_convention="legacy"`
  opt-in for old projects.
- **6p/36s and 8p/36s canonical table entries** — old "12-slot segment"
  layout was not a real 3-phase winding; replaced with proper 60° phase
  belt pattern.
- **4p/36s canonical table** — was missing phase C entirely; corrected.
- **36slot_industrial/winding.py and 36slot_v2/winding.py** — polarity
  values were reversed, causing BEMF phase sequence to be inverted.

### Changed

- **Maxwell coil naming standardized to `Coil_1, Coil_2, …`** in the
  builder (legacy `A_1, A_2, …` retained in old `output_scripts/` for
  backwards compat).
- **Concentrated winding detection** in `pmsm_winding_builder.py` — now
  `q < 1` (catches q=0.4, q=0.375 etc., not just q=0.5).

### Migration guide

- Code using `pmsm_winding_builder.WindingBuilder(slots, poles)` is
  unchanged.
- Code using `coil_groups` is unchanged (same fields).
- Code using `generate_maxwell_script()` is unchanged in API, but
  the output is now `standard` polarity by default. To restore old
  behavior, pass `polarity_convention="legacy"` to the constructor.
- Custom (slots, poles) not in `CANONICAL_LAYOUTS` will now use the
  fallback algorithm and be marked `source="computed"`. This may
  produce different output from the buggy v1 algorithm.

---

## [4.3.0] — 2026-07 — "MCP connector"

### Added

- **Real MCP client** (`scripts/mcp_connector.py`) — stdio JSON-RPC client
  to `D:\mcp-maxwell\server.py` (71 tools).
- **Three backends** in `maxwell_bridge.py`: `dry_run` (mock), `text`
  (IronPython script gen), `mcp` (real Maxwell).

### Known limitations (carried over)

- Many MCP tool names in `server.py` do not match what `projects/25Nm_PMSM/`
  scripts call. The `set_model_units`, `duplicate_around_axis`,
  `get_field_data`, `get_loss_data`, etc. tools are missing or have
  signature drift. See `AUDIT_REPORT.md`.

---

## [4.0.0] — 2026-04 — "Multiphysics MDAO"

### Added

- **MDAO orchestrator** (`scripts/mdao_orchestrator.py`) — electromechanical
  + thermal + IGBT reliability chain
- **IGBT 7-layer structure** + Coffin-Manson / Darveaux fatigue models
- **9 SQLite databases** for multiphysics data management
- **3 multiphysics workflows**: motor (electromagnetic-structural-thermal),
  IGBT reliability, fatigue life

---

## [3.x] — earlier

- 3.0 — Parameter auto-completion (just 2 inputs → full motor spec)
- 3.1 — Multi-objective optimization (NSGA-II / PSO)
- 3.2 — 10 simulation types
- 3.3 — Slot / PM topology switching

See git log for full history.

---

## Versioning policy

- **Major** (X.0.0): breaking API change, drop Python support
- **Minor** (4.X.0): new feature, new pole-slot combination, non-breaking
- **Patch** (4.4.X): bug fix, documentation, non-breaking

## Release cadence

- Major: as needed (rare — maybe yearly)
- Minor: monthly if features land
- Patch: as needed for bug fixes

[Unreleased]: https://github.com/Torry/ansys-maxwell-motor-skill/compare/v4.4.0...HEAD
[4.4.0]: https://github.com/Torry/ansys-maxwell-motor-skill/releases/tag/v4.4.0
[4.3.0]: https://github.com/Torry/ansys-maxwell-motor-skill/releases/tag/v4.3.0
[4.0.0]: https://github.com/Torry/ansys-maxwell-motor-skill/releases/tag/v4.0.0
