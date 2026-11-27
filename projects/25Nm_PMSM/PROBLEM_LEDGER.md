# 25 N·m SPMSM — 问题账本（Problem Ledger）

> 每日任务开工先读本文件；收工前更新。**fail 条目不得删除**，关闭必须写证据 + 验收值。
> 严重度：`blocker`（阻塞工程交付/安全）> `major`（性能不达标）> `minor`（一致性/文档）。
> 状态：`open` / `in_progress` / `blocked` / `closed`。
> 判据见 `docs/ENGINEERING_ACCEPTANCE.md`；探索见 `EXPLORATION_LOG.md`。

## 🔄 2026-11-19 阶段切换：SPM 8p12s 账本冻结 / 新项目 IPM 8p48s 启用

> SPM 8p12s 项目（P1–P16/E1–E13/G4b）**整体冻结为 baseline**，open 项（P4/P5/P15/E3–E12/G4b）
> 保留不删，作为后续工程验证的存量清单，**不再由每日任务优先推进**。
> 新项目契约：`projects/IPM_8p48s/PROJECT_SPEC.md`，新问题 ID 从 **I1** 起编，本表下方 SPM 记录存档。
> 交付次序：IPM 8p48s G0–G4 全绿 + 周检确认 → 自动切 36 槽工业机。探索 LOCKED。
>
> **2026-11-19 夜补记**：SPM 的 G4b（磁密三行 FEA 复核）是冻结前**已在飞行中的收尾项**，
> 本次做完并关闭（Bg/B_tooth/B_yoke 三行 PASS）。这不是重开 SPM 优化，也未产出任何
> 设计变更；SPM 冻结状态与"不再由每日任务优先推进"的结论不变。新增 P17/P18 两条为
> 本次暴露的管线/口径问题，其中 P17 已闭，P18 随 IPM 复用同一脚本时一并修。

## 当前基线（2026-11-16 真机，模板路径 M8 梨形槽 + M7 负载 + P12 匝数 84 设计点；**SPM baseline，已冻结**）

| 指标（**80 匝基线**，G4/M8/M7 冻结口径，`--check` 8/8 可复现） | 值 | 判据 | 状态 |
|---|---:|---:|---|
| BEMF 相 RMS | 120.5594 V（模板 M8，+1.41% vs 手写 118.8832） | 118–145 V（±10%） | ✅ |
| 线 BEMF THD | **11.180%**（梨形槽，同口径复算；矩形槽 10.595%） | ≤10%（下限） | ❌ 略超（+0.59 pt） |
| 齿槽峰峰值 | **0.8801 N·m / 3.52%**（模板 M8，401 点） | ≤1.25 N·m / 5% | ✅ |
| 负载 T_avg | **22.6296 N·m（−9.48%）**（模板 M7，401 点） | 25±20% | ✅ |
| 转矩脉动 | **14.688%**（模板 M7，末周期 201 点） | ≤15%（目标 ≤10%） | ✅ 下限 / ⏳ 目标 |
| 双路径一致性 | BEMF +1.41%、齿槽 −87.1%（梨形槽 vs 矩形槽，非等价项）、负载 +1.32% | ±10% | ✅ |
| 功率平衡 | P_mech 3554.6 W vs 3·E·I 3577.0 W = −0.62% | <10% | ✅ |
| 效率（解析） | 93.87% | ≥93.8% | 待 FEA 损耗复核（E8） |
| 报告 | 491,996 B / 13 表 / 7 内嵌图 | — | ✅（数值口径见 P6） |
| 斜槽候选（0.5 槽距，连续多切片） | 齿槽 0.00058 N·m/0.002%、THD 1.9983%、脉动 4.285%、T_avg 21.6056 N·m、BEMF **114.3847 V** | 同左 + BEMF 118–145 V | BEMF ❌（P12，11-16 已闭） |
| **设计点（0.5 槽距 + 84 匝，401 点）** | BEMF **120.1039 V**、THD **1.9983%**、齿槽 **0.00058 N·m/0.0023%**、`T_avg` **22.6857 N·m（−9.26%）**、脉动 **4.285%**；η 仍为解析 93.87%（E8） | 电磁五项 + η ≥93.8% | 电磁 5/5 ✅（6 条判据，齿槽拆绝对+相对）；η 待 FEA 损耗（E8） |
| **网格收敛（E1，11-18，粗/中/细 401 点 ×3）** | 相 BEMF **120.5527 / 120.5594 / 120.5530 V**（三档极差 **0.006%**）；齿槽 **0.945773 / 0.880078 / 0.875432 N·m**（medium→fine **−0.53%**，coarse **+7.46%**）；同模型二次求解复现基线 BEMF +0.0014% / 齿槽 −0.0015% | §3：转矩/BEMF <2% | 基线收敛 ✅；粗档齿槽不可用（E13） |
| **时间步收敛（E2，11-18，50/25 µs）** | 相 BEMF **120.5594 / 120.5891 V（+0.0246%）**；齿槽 **0.880078 / 0.883719 N·m（+0.4137%）**；线 THD **11.1797 / 11.2532%（+0.0735 pt）**；25 µs 磁链隔点降采样 → 120.5594 V / 0.880091 N·m | §3：<2% | PASS ✅（两档均在 E1 分辨力地板同一量级） |
| **磁密 FEA（G4-B，11-19，末时刻快照 t=0.02 s）** | Bg **0.8626 T**（径向@齿中心 15°/45°；\|B\| 峰 0.8947 T 落在槽口倒角 29.0°）/ B_tooth **0.9896 T**（r=54.25 处 0.9247）/ B_yoke **1.1843 T**（轭内缘 r=60.0） | 0.70–0.90 / ≤1.65 / ≤1.50 | 三项 ✅（最紧口径余量 0.6%，边界通过） |

> **匝数记账口径（P12，全部为 analytic，未替换任何 FEA 值）**：R ∝ N²；同转矩 I ∝ 1/N
> ⇒ P_cu = I²R **近似不变**（138.6 W）；若维持 9.89 A 不变，则 `T_avg` +5%、P_cu ×1.1025
> ⇒ **152.8 W**（≤160 W 下限内，超 ≤140 W 目标）。两条口径不得混用；账本 11-15 版写的
> "同转矩电流 +4.7%"方向错，已改。

## 问题表

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **P1** | blocker | M8 | 梨形槽代码/生成已完成，但无 `.aedt`、无 401 点解、未提交 | `slot_profile.py` / `m8_gen` 21:58 | `T4_pear.aedt`：槽 93.0±2%、线圈 72±5%、Arc、12 槽、无 intersect | **closed** | 11-14 夜 `T4_tpl_noload.aedt` 1,313,661 B；槽 92.866（环带）/`StatorOuter` 9,764.151、线圈 71.863、24 sheets、无 intersect；`fe1de7b` 已提交 |
| **P2** | major | M8 | 11 控制点直接内缩 → 线圈 62.07 mm²（−13.8%） | 周检 §6.3-1 | `_slot_pts` 半圆 ≥8 采样点；线圈 68.4–75.6 | **closed** | `slot_profile.py` 16 段弧，实测 71.863 mm² |
| **P3** | blocker | 电磁 | 齿槽 27.37% ≥ 5%，差 5.47× | `fea_results.json` | FEA 齿槽 ≤1.25 N·m | **closed** | 模板 M8 梨形槽 401 点：**0.8801 N·m / 3.52%**（−87.1%），主频 598.5 Hz≈24×25 Hz；证据 `fea/m8_pear_summary.json`、`fea/m8_pear/tq_noload.csv` |
| **P4** | major | 几何 | 两条路径转子内径不同源：13.24 vs 20.01 mm（面积差 706.86=π·15²） | 周检 §3 | 统一 `rotor_id` 或报告注明“铁芯内部不影响场” | open | 查 `pmsm_config` / 模板 `RotorOuter` 参数 |
| **P5** | minor | 复核 | `fea_results.bemf_balance_pct=0.008%` 与独立重算 0.220% 不一致 | 周检 §5 | 报告脚注写清求导/重采样口径 | open | 模板 M8 三相同窗口 RMS 120.5580/120.5573/120.5629 ⇒ 极差/均值 **0.0046%**；0.220% 来自 M5 手写路径的另一窗口/降采样口径。**明日**在 `make_report.py` §11 加口径脚注并重生成报告（需 g2_venv） |
| **P6** | minor | 文档 | 767,290 vs 958,509 B；线圈 75.24 vs 79.9568；9 图 vs 内嵌 7 | 周检 P6 | 三处数字与 `weekly_audit.json` 一致 | **closed** | ① `767,290` → **958,509 B**（按 `backup_g4/T4_tpl_noload_g4.aedt` 核对，G3b 误记）；② 线圈 75.24 / 79.9568 / 71.863 是 M2 / G4 / M8 三种几何口径，已在看板加脚注；③ 「9 图 / 13 表」经 `grep -c` 复核 **9 / 13 正确**（周检「内嵌 7」不成立） |
| **P7** | minor | 文档 | `SKILL.md:211` 旧梨形尺寸（Bs0=3.5…Rs=4.15） | 周检 P7 | 换成表 2 参数 | **closed** | 该示例是 **210 mm/36 槽教程机**、非 25 N·m 机型 ⇒ 不改数（改数反而错机），已在 `SKILL.md` Step 4 加机型判别注释 + 指向 `PEAR_SLOT_SPEC.md` 表 2 + 共同硬约束 `Rs=Bs2/2` |
| **P8** | minor | 仓库 | 工作树 11 项未提交；M8 文件也未提交 | `git status` | M8 文件单独提交，不扫入已有脏改动 | open | M8 `fe1de7b`；M7 单独提交；11-18 E1 单独提交（`8b14f22`，6 项：`.gitignore`/`gen_maxwell_model.py`/`e1_mesh_check.py`/测试/汇总 JSON/12 个 CSV）；余 **9** 项历史改动仍未归属：`mcp-maxwell/server.py`、`output_scripts/36slot_industrial/{winding.py + 未跟踪 coils.py}`、`output_scripts/36slot_v2/{coils,winding}.py`、`scripts/{maxwell_bridge,motor_param_calc,winding_layout}.py`、`references/motor_design_guide.md` —— 未审不动；`.workbuddy/`（自动化记忆）有意不入库 |
| **P9** | info | 看板 | M7/M8 行缺失 | 周检 P9 | 已补 | **closed** | — |
| **P10** | minor | 管线 | M7 首次跑时应用日志与 AEDT「脚本同名 .log」撞名，日志被截断（CSV 完好） | `D:/ANSYS_Run/aedt_msgwin_m7_collision_20261115.log` | 日志改名 `tpl_app_<case>.log`，重跑无截断 | **closed** | 2026-11-15 改 `tpl_solve_noload.py`/`tpl_run.py` 并加注释；本次靠 401 行 CSV + 原生 TrCrv 反证求解完整 |
| **P11** | major | 电磁 | 线 BEMF THD **11.180% > 10% 下限**；梨形窄槽口把它从 10.595% 推高 0.59 pt（与齿槽改善对冲） | `csv_tpl/flux_*.csv` + `ingest_fea.analyse_signal`（跳首周期、2–15 次）；矩形槽同法复现 10.595% 自证 | 线 THD ≤10%（目标 ≤8%） | **closed** | 设计点（0.5 槽距 + 84 匝）**1.9983%**（≤8% 目标也达标）；频域因子法 1.9969%（差 0.0014 pt）。**未斜槽基线 11.180% 保留为已记录 FAIL**，不改口径、不删数据。证据 `fea/n84_skew_summary.json` |
| **P12** | major | 电磁 | 斜槽 0.5 槽距的基波降额 **k1=0.95493** 使 BEMF 120.5577 → **114.3847 V（−5.12%）< 118 V 下限** | `fea/skew_scan_summary.json` 的 `bemf_phase_rms_v`；k1 由 3 片真机 FEA 复核 **0.95983 vs 0.95980（0.0033%）**（`fea/skew_slice_check.json`） | 配 N=85 后 BEMF 回到 118–145 V，且 T_avg/齿槽/THD 不退化 | **closed** | 11-16 真机：cps 40→42（80→84 匝，+5.00%）两次 401 点（空载 475.9 s / 负载 538.6 s）。BEMF **120.1039 V** ✅；THD 变化 **0.0 pt**、齿槽变化 **−1e-5 N·m**（不退化 ✅）；`T_avg` 22.6857（比 21.6056 升 5%）。负载 FEA 直接平均 22.62961→23.76074（比 1.04998，线性预测 23.76109，差 −0.0015%）。证据 `fea/p12_turns84_summary.json`、`fea/n84/`、`fea/n84_load/`（各 4×401 行） |
| **P15** | minor | 制造/口径 | 槽满率三处口径不一致：`slot_fill_factor=0.40`（config）；φ1.45 mm 单根实算 40 导体 **71.2%**（cps=42 → **74.7%**）；`param_validator.calc_slot_fill_factor` 若按 `num_strands=4` 会得 4 倍面积（**285%**，明显错口径） | `scripts/motor_config.py:167`、`scripts/param_validator.py:116-118` | E9 前统一口径（单根/并绕/含漆膜），再判 ≤0.78 | open | 不阻塞电磁结论；cps=42 的 74.7% 仍在 0.78 内，但需写清是"裸铜/单根"口径 |
| **P13** | minor | 复核 | 3 片真机 FEA 只覆盖**空载**（齿槽/BEMF/THD），负载侧斜槽降额未过真机 | `fea/skew_slice_check.json` 的 `not_covered` | 负载 3 片 FEA（约 3×726 s）或其它独立验证 | open | 现由「时域合成 + k_sk(1)」两法互证（差 1e-3）；若周检要求，再跑 3 个负载切片 |
| **P14** | minor | API | `AssignBand` 的 `Init Pos="7.5deg"` **不旋转几何**：401 点解与基线逐点相同（max 3e-5 N·m、互相关滞后 0），白跑 726 s | `D:/ANSYS_Run/tpl_app_s075.log`（`Init Pos` 版）+ `docs/MAXWELL_INTERNALS.md` §15.1 | 改 `Init Pos` 后转矩波形必须变化 | **closed** | 改用几何旋转磁钢扇区（`_gen_geometry` 的 `_ang_off`）；形心证据 PM_1 = (43.9447, 1.9187) @ 2.5°、(43.6102, 5.7414) @ 7.5° |
| **E1** | major | 数值 | 网格无关性未做 | — | 3 档网格，转矩/BEMF 变化 <2% | **closed** | 11-18 真机三档 401 点（`--mesh-scale` 1.5/1.0/0.6，只差 `mesh.py` 4 行 `MaxLength`）：**BEMF 120.5527/120.5594/120.5530 V（极差 0.0056%，三档全过）**；**齿槽 medium→fine −0.5279%**（0.880078→0.875432 N·m）⇒ 基线误差 ≤0.6%，收敛判据 PASS。**严格三档口径 FAIL 记录在案**：粗档齿槽 +7.4647%（见 E13）。证据 `results/fea/e1_mesh_summary.json`、`results/fea/e1_{m,c,f}/`（12×401 行）、`tpl_app_e1{m,c,f}.log` |
| **E2** | major | 数值 | 时间步无关性未做 | — | 50 µs vs 25 µs，变化 <2% | **closed** | 11-18 夜真机两次 401/801 点（同几何，只改 `TimeStep`）：50 µs 120.5594 V / 0.880078 N·m / THD 11.1797%，25 µs **120.5891 V（+0.0246%）/ 0.883719 N·m（+0.4137%）/ THD 11.2532%（+0.0735 pt）** ⇒ <2% PASS。降采样复核：25 µs 磁链隔点取 1 再求导 = 120.5594 V / 0.880091 N·m（对 50 µs 差 **0.0% / 0.0015%**）。证据 `results/fea/e2_timestep_summary.json`、`fea/e2_t25/`（4×801 行）、`tpl_app_e2t25.log`（`ANALYZE_OK 1321.4s`） |
| **E3** | major | 材料 | `M270_35A` 目前线性 μ=1000；`NdFe35` 未按 100°C 修正 Br | `.aedt` 材料块 | 非线性 B-H；Br(100°C) 与 Hc 修正 | open | 导入 B-H 曲线/温度系数 |
| **E4** | major | 能量 | 能量守恒未闭环 | — | P_in = P_out + ΣP_loss，偏差 <5% | open | 从 FEA 导出损耗/功率（负载功率平衡已 −0.62%，但未含铁耗/铜耗分项） |
| **E5** | major | 热 | 热分析仍是 7 节点解析，未用 FEA 损耗复核 | `thermal_summary.json` | 热点 ≤155°C / 磁钢 ≤120°C | open | 用 FEA 损耗重跑热网络/FEA |
| **E6** | major | 退磁 | 退磁仍是解析，未用 FEA 校核 | `sim_summary.json` | B_min ≥0.2 T，SF ≥2 | **closed (PASS_MIN)** | 11-27 真机 150°C 三相短路 FEA：B_min **0.4222 T**、SF **2.1108**（目标 0.30/2.5，下限 0.20/2.0）⇒ 过下限未达目标；401 点、5 点试算判能解；证据 `projects/results/e8e6/e6_fea.json`、`field/`。温度系数外推标 assumption=待验证；末时刻快照局限在案 |
| **E7** | major | 电磁 | 转矩脉动 32.39% ≥ 15% | `fea_results.json` | ≤15%（目标 ≤10%） | **closed** | 模板 M7 梨形槽 401 点：**14.688%**（≤15% 达标）；主因 600 Hz 齿槽残余（2.04 N·m 基波幅值）；**≤10% 目标未达**，转 G7 |
| **E8** | major | 效率 | 效率 93.87% 为解析，FEA 损耗未复核 | `sim_summary.json` | ≥93.8% | **blocked** | 11-27 铁耗系数定源完成：库内有 M270-35A 牌号但不可导出 ⇒ 等用户提供 Kh/Kc/Ke。详见下方「2026-11-27 11:xx E8 铁耗系数定源」段。gate 未过，未跑 CoreLoss、未填经验值、未改判据 |
| **E9** | major | 制造 | 槽满率/公差链/BOM 未做 | — | 满率 ≤0.78；g_min ≥0.50；BOM ±10% | open | S10 |
| **E10** | minor | NVH | 力波/模态为解析，未用 FEA 校核 | `nvh_summary.json` | 工作区无同阶共振 | open | FEA 模态/力波 |
| **E11** | minor | 标准 | 未对照 IEC 60034-1/2-1、F 级绝缘 | — | 报告列出标准条款/温升限值 | open | 补标准对照表 |
| **E12** | minor | 复核 | 独立重算尚未固化为每日检查 | 周检 §5 | 每日用独立脚本复算 BEMF/转矩 | open | `m7_load_check.py` 已内置双法（梯形 vs `ingest_fea`）；空载侧仍待固化（11-18 的 `e1_mesh_check.py` 已能独立复算空载 BEMF/齿槽并逐位复现 0.880091 N·m，可作固化起点） |
| **E13** | minor | 数值 | 粗档网格（气隙 0.3 mm = 0.675 mm 气隙里 2.25 层单元）把齿槽高估 **+7.46%**，不可用于齿槽/脉动类定量结论 | `results/fea/e1_mesh_summary.json` 的 `checks.c` | 粗档只用于趋势筛查；齿槽类结论必须 medium（0.2 mm）或更细 | **closed** | 11-18 真机 401 点：粗档齿槽 0.945773 vs 中档 0.880078 N·m；BEMF 只差 −0.0056%（不敏感）。反向也成立：medium→fine 仅 −0.53% ⇒ 基线可用。**分辨力地板 ≈0.5%（齿槽）/ 0.006%（BEMF）**，小于此的差异不立结论 |
| **P16** | minor | 复核/代码 | `ingest_fea.analyse_signal` 用 `t[i] >= t0` 浮点比较跳首周期：50 µs 网格被判成 10.05 ms（9.95 ms 窗），25 µs 网格判成 10.000 ms 且**含重复端点**（N+1 点）⇒ 同一物理两个 DFT 窗，E2 首跑 THD 假差 **0.5474 pt**（11.1797% vs 11.7271%） | E2 首跑 `e2_timestep_summary.json` 初版；`analyse_signal` 返回 `n_samples` 200 vs 401 | 跳周期改整数索引 `round(T/dt)`；窗口跨度为整数个电周期时丢弃重复端点 | **closed** | 11-18 修复 + `tests/test_analyse_window.py` 5 例。修复后 50 µs / 25 µs 均落在 10 ms 整周期（200 / 400 点）：THD **11.1797% vs 11.2532%（Δ +0.0735 pt / +0.66%）**；50 µs 历史数值不变（E1 三档复算逐位相同，仅粗档 THD 11.1702→11.1703） |


| **G4b** | major | 复核/场 | Bg / B_tooth / B_yoke 三项 FEA 场探针始终无数据；G4 电磁五项虽全绿，但磁密三行仍只有解析值（且 tooth/yoke 的 1.6514/1.6514 T 是 10.48/7.86=4/3 口径巧合，非物理相等） | `D:/ANSYS_Run/csv_g4b/{bg_gap,b_tooth,b_yoke}.csv` 从 11-19 22:34 至今恒为 2 行（表头+空值）；`g4b_probe.log` TRY_A~F 六种导出变体全部 `no data for export`；`g4b_solve.log` 求解 567.6s 成功、tq/flux 401 行但 `Btry_G has no data`；`g4b_test6.log` 明确 `Solutions have been invalidated` | 三项 FEA 场值 + 磁通连续性偏差 ≤5% | **closed** | 11-19 夜走通路线②：**解后纯 FieldsReporter 后处理、不碰任何几何**。签名 `oF.ExportToFile(out, pts, "Setup1 : Transient", ["Time:=", "0.02s"], 1)`，点文件坐标必须用**米**（mm 全 NaN）。末时刻快照物理充分性：t=0.02 s 转子角 0°，磁钢中心 0/45/90°、槽中心 0/30/60° ⇒ 15°/45° 齿正对极轴 = 齿磁密最大相位。结果：**Bg 0.8626 T（径向@齿中心）/ 0.8947 T（\|B\|峰，槽口倒角 29.0°）、B_tooth 0.9896 T、B_yoke 1.1843 T，三行 PASS**；证据 `fea/g4_flux_summary.json`、`g4_flux_check.py`、`csv_g4b/{calc45,br}/`。磁通连续性 −15.57% 标 `INCONCLUSIVE`（一维控制体经槽开口不闭合 + \|B\| 含切向），**只作诊断不作判据**，未拿它凑验收 |
| **P17** | minor | API/管线 | 生成器 `scripts/main.py::_gen_solver` 写 `"SaveFieldsType:=", "Every N Steps", "N:=", "2"`，但 21.1 落盘真值是 `'N Steps'='0'` —— `"N:="` 是**静默无效键**（不报错、不生效），实际只存末时刻场；旧注释却声称"隔步存场 N=2"，代码在自述一个不存在的行为 | `grep -o "'N Steps'='[0-9]*'" T4_g4b2.aedt` → `'0'`；同工程 `Time:=0.02s` 有数据、`0.0105s` 全部失败；`app_g4b_keytest.log` 6 个变体（含 A 无键、B/C/D `N Steps`、E `SaveFields`、F 旧 `N:`）**全部 raise** | 生成物不得含无效键；存场口径须与注释一致 | **closed** | 11-19 修：删除 `"N:="`、注释改写成实测真值；重生成 `maxwell_model/` 后 `--check` 8/8 无漂移；`tests/test_solver_save_fields.py` 7 例钉死"无效键不得回潮 + 存场开关必须在"。**未能测出正确键名**：已求解的工程上 `InsertSetup` 对所有数组都 raise（含历史上可用的旧数组），故只能在重解前设置；多快照存场留待 E8 铁损时开启，且必须重解确认 Standard 报告仍 401 行（`T4_g4b5` 的 N Steps=5 重解后 tq 只剩 1 行，原因未查清，作废） |
| **P18** | major | 复核/解析 | 轭部解析磁密**偏乐观 21.0%**（解析 0.9351 T vs FEA 1.1843 T），齿部**偏保守 6.6%**（1.0552 vs 0.9896）。解析用 `Φ/2 / (16mm·L)` 的均匀轭模型，未计齿根扩散与轭内缘聚磁，而轭磁密最大值恰在最小半径（r=60.0） | `fea/g4_flux_summary.json` → `analytic.corrected_at_fea_bg` vs `yoke.b_max` | 解析 yoke/tooth 与 FEA 偏差 ≤10%，或解析侧显式标注为"均值口径" | open | 修 `sim_analytical.py` 轭部模型（引入轭部磁密分布系数或改走磁路分段）；在此之前**禁止**用 0.9351 T 报轭磁密。SPM 已冻结为 baseline，随 IPM 复核复用同一脚本时一并修 |

## 2026-11-26 15:35 — E6/E8 路线变更：Motor-CAD 弃用，改 Maxwell 原生 + 分批时段

Motor-CAD 2025.2.1 的 `motorcad` feature checkout 报 FlexNet -8,544（license 文件为第三方 Team SolidSQUAD-SSQ 签发，非 ANSYS 官方），P0 连接验证 BLOCKED（IPM 账本 I30）。**不修破解 license，不碰任何 license 文件**。E6/E8/热网络改走 Maxwell 原生链路。

| 项 | 决策 | 证据 |
|---|---|---|
| 能力层 | `projects/e8e6/e8e6_bridge.py`（KEEP）+ `tests/test_e8e6_bridge.py`（12 例） | 12/12 PASS；全量 504 passed |
| E8 gate | `core_loss_coefficients("M270_35A")` 返回 `MISSING` —— 材料只有 permeability/conductivity，无 Kh/Kc/Ke | `maxwell_model/materials.py:59-69`；测试 `test_real_mode_core_loss_gate_on_this_machine` 钉死 |
| E8 批次 | 定时任务 `c280d576`（11-27 08:00）：先做铁耗系数定源，gate=PRESENT 才跑真机 FEA，否则记 BLOCKED 等厂家数据 | automation list |
| E6 批次 | 定时任务 `af283519`（11-27 11:00）：150°C 三相短路 FEA；温度系数外推标 `assumption=待验证` | automation list |
| Motor-CAD 任务 | `92f05bc4` 改为 PAUSED，不再触发 | automation list |
| 判据 | 未改：η ≥93.8%/93.0%、B_min ≥0.30/0.20 T、SF ≥2.5/2.0、绕组 ≤155°C、磁钢 ≤120°C | `e8e6_bridge.py` 常量 + 测试 `test_criteria_match_acceptance_doc` 钉死 |

两个批次与每日 14:30 迭代错峰，均带 `tasklist | grep -i ansysedt` 并发检查；**只有真机 FEA 数据才允许改 `ENGINEERING_ACCEPTANCE.md` 的 E6/E8 状态**。

## 2026-11-27 11:xx — E8 铁耗系数定源（定时任务 c280d576；结论 BLOCKED）

开工 gate：`E8E6Bridge(dry_run=False).core_loss_coefficients()` → `{'status': 'MISSING', 'coefficients': {'Kh': False, 'Kc': False, 'Ke': False}, 'source': 'projects/25Nm_PMSM/maxwell_model/materials.py'}`，三系数全缺。按账本约束「补系数前不许用经验值跑 CoreLoss」，本批次只做定源。并发检查：`tasklist | grep -i ansysedt` = NO_ANSYSDT（无占用）。

定源检索（只读，未碰 Motor-CAD / 破解 license / 任何 license 文件）：

| 检索对象 | 结果 | 证据 |
|---|---|---|
| `projects/25Nm_PMSM/maxwell_model/materials.py:59-69` | M270_35A 只有 `permeability=1000` / `conductivity=2e6`，Kh/Kc/Ke 无 | 文件直接读取 |
| Maxwell 主材料库 `D:/Program Files/AnsysEM/AnsysEM21.1/Win64/syslib/Materials.amat` | 无 M270 / M270-35A 命中（`grep -i M270` 无结果） | 全库检索 |
| GRANTA 扩展库 `syslib/GRANTA Producers Materials Data for Simulation.amat` | **有** `Cogent Power - M270-35A, 50Hz`，`$begin` 行 94813、`$end` 行 95446；条目 `IsEncrypted=true`，整段为 `CypherText` 密文 | `grep -in M270` 行 94813/95446；`sed` 读条目 |
| 该 GRANTA 库加密性质 | 1937 条材料全部 `IsEncrypted=true`；全文件 `core_loss\|Kh\|Kc\|Ke` 明文命中 **0** | `grep -c IsEncrypted=true` = 1937；`grep -ic core_loss...` = 0 |
| Maxwell 原生 API 读系统库材料属性 | 探测脚本 2 版（`D:/ANSYS_Run/probe_m270_coreloss*.py`，TEMP）：v1 API 签名错；v2 枚举加密库卡死 12 min → 主动终止。未取得系数 | 探测无结果文件；`GetPropertyValue` 需 3 参数 `(tab,material,prop)` |
| 非 GRANTA 目录 / 用户材料库 `C:/Users/ASUS/AnsysEM` | 无 M270-35A 命中；无用户 `.amat` | 全盘 `grep -ril`、`.amat` 检索 |

判定：库内**仅有加密牌号名**，无明文 core loss 曲线、无 Kh/Kc/Ke 可导出值。按任务规则「库里也没有（可导出系数）→ 写 BLOCKED + 需要的厂商标定数据」，E8 置 **blocked**。本批次未跑 CoreLoss、未跑真机 FEA、未填经验值、未改判据、未改 `ENGINEERING_ACCEPTANCE.md` 的 η 行。

解锁所需厂商标定数据（缺一不可）：
1. **M270-35A（Cogent Power / Thyssenkrupp 或实际采购钢厂）的 Steinmetz 三系数 Kh / Kc / Ke**，须注明单位口径（W/kg @ B[T]、f[Hz]）与拟合频率/磁密区间；或
2. **同等效力原始标定**：B–P 损耗曲线族（P[W/kg] vs B[T]，至少 3 个频率点，如 50/100/200/400 Hz），由我方用 Steinmetz 回归拟合 Kh/Kc/Ke 并留拟合脚本与残差；曲线必须来自钢厂 datasheet / 第三方实测报告，不得用 ANSYS 通用经验值。
3. 数据文件名、厂商、牌号批次、测试标准（IEC 60404-2 或等效）需一并给出，以便写 `materials.py` 时标注来源。

> 注：GRANTA 条目名为 `Cogent Power - M270-35A, 50Hz`（50 Hz 数据），而本项目 `RATED_FREQUENCY_HZ` 为 100 Hz（`projects/25Nm_PMSM/pmsm_config.py:13`，8 极 1500 rpm，f=4×1500/60）；即便密文可解，50 Hz 单点也不足以定 Ke，仍需多频点曲线。此点作为附加证据，不改变 BLOCKED 结论。

## 2026-11-27 11:xx — E6 退磁真机 FEA（定时任务 af283519；结论 PASS_MIN）

并发闸口：`tasklist | grep -i ansysedt` = NO_ANSYSEDT_RUNNING（08:00 E8 批次已结束且
BLOCKED，未跑真机），与 14:30 迭代错峰，单实例无并发。全程未碰 Motor-CAD / license 文件。

| 项 | 结果 | 证据 |
|---|---|---|
| 温度外推（assumption=待验证） | ΔT=130K；Br(150)=Br20·[1+(−0.0012)·130]=**1.0381 T**；Hc(150)=890k·[1+(−0.006)·130]=**195800 A/m**；μr(150)=Br/(μ0·Hc)=**4.21915** | `e6_fea.json::temperature_extrapolation`；系数是 N35 常见值外推，**非本项目厂家数据**，需 datasheet 或 150°C 实测退磁曲线确认 |
| 短路拓扑 | 三相 `Type="Voltage"` / `Voltage="0V"` + R=0.48Ω / L=0.0038H，电流由感应电压驱动 | `.aedt` 绕组块；原生 TrCrv 回路残差 max\|Ldi/dt+Ri+e\| ≤0.02 V（试算+全解均验证） |
| 试算（5 点） | `ANALYZE_OK 16.4s`，三相 TrCrv 各 5 行，电流由 0 升至 ±0.375 A ⇒ 能解 | `D:/ANSYS_Run/app_e6_demag_trial.log`（TEMP） |
| 全解（401 点） | `ANALYZE_OK 458.8s`，10 ms / 25 µs，motion setup 保留；三相隔 401 点电流 CSV | `app_e6_demag_full.log`；`projects/results/e8e6/field/current_{a,b,c}.csv` |
| 短路电流峰值 | 11.24 A（C 相；8p12s 集中绕组三相不对称属正常）；H_demag=28.23 kA/m | `e6_fea.json::short_circuit` |
| **B_min** | **0.4222 T** @ t=10 ms / θ=27° / r=46.1625 mm，121 点 | `field/gap_bx_010000us.csv` + `gap_by_...csv`；口径 min_t[max_θ\|Br\|] |
| **SF** | **2.1108**（B_min/0.2T，与账本解析 SF=B_min/0.2 同源）；交叉 SF_Hc=6.94 | `e6_fea.json::safety_factor` |
| 判据 | B_min ≥0.30/0.20 T，SF ≥2.5/2.0 ⇒ **PASS_MIN**（过下限、未达目标） | `E8E6Bridge(dry_run=False).check_demag(...,temperature_c=150,source="FEA")`；阈值未改 |
| 热网络 G5 对照 | bridge.thermal_nodes()：绕组 89.47°C ≤155、磁钢 76.06°C ≤120 ⇒ PASS，source=ANALYTIC_LPTN_S4_LOSS | `e6_fea.json::thermal_crosscheck`；**未改** `thermal_summary.json` |

遗留限制（如实留痕，不掩盖）：
1. **末时刻快照**：21.1 `EditSetup` 的 `"N Steps"="10"` 被静默忽略（P17 同类），多时刻场 66 次导出
   全失败，只有 t=0.010 s（1 个电周期末、转子机械角回 0°）场可查。B_min 严格性弱于全时程场扫描，
   无法确认最恶劣去磁相位；与 G4-B 磁密三行同口径（末时刻快照），不在本次冒充全时程最小值。
2. **温度系数待验证**：Br −0.12%/K、Hc −0.6%/K 为常见值外推，不是厂家数据；SF 对 Hc 敏感
   （解析 0.4%/K 给 SF≈1.1，本次 0.6%/K 给真机 SF_Hc=6.94），牌号 datasheet 到位后须重跑。
3. **端部电感口径**：2D 场已含槽内电感，0.0038 H 全额计入是 assumption=待验证；
   实测端部电感若小于此值，短路电流与退磁裕度会变化。
4. E6 由 `open` 直接置 `closed (PASS_MIN)`：达标下限但未达工程目标（SF 2.5），是否接受 PASS_MIN
   作为最终关闭由周检裁定；本次不改判据、不删数据。

新增文件 → 分类：`projects/e8e6/e6_demag_check.py`、`e6_demag_solver.py` [KEEP] 可复现链路；
`projects/results/e8e6/e6_fea.json` + `field/*.csv` [KEEP] 验收证据；`D:/ANSYS_Run/e6_*` [TEMP] 不入库。

## 优先级规则

1. `blocker` 先于 `major`，`major` 先于 `minor`；同级别按“影响工程交付”排序。
2. 一天只推进**一个**问题（或一个完整实验组）。
3. 关闭条件：验收值达标 + 证据写入本表 + 回归测试通过。
4. 若某问题连续 2 天无进展，标 `blocked` 并写清阻塞点/需要的桌面操作。
