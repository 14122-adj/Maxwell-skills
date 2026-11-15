# 25 N·m SPMSM — 问题账本（Problem Ledger）

> 每日任务开工先读本文件；收工前更新。**fail 条目不得删除**，关闭必须写证据 + 验收值。
> 严重度：`blocker`（阻塞工程交付/安全）> `major`（性能不达标）> `minor`（一致性/文档）。
> 状态：`open` / `in_progress` / `blocked` / `closed`。
> 判据见 `docs/ENGINEERING_ACCEPTANCE.md`；探索见 `EXPLORATION_LOG.md`。

## 当前基线（2026-11-15 真机，模板路径 M8 梨形槽 + M7 负载）

| 指标 | 值 | 判据 | 状态 |
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
| **P8** | minor | 仓库 | 工作树 11 项未提交；M8 文件也未提交 | `git status` | M8 文件单独提交，不扫入已有脏改动 | open | M8 `fe1de7b`；M7 今日单独提交（代码/测试/结果/文档，逐文件 add）；余 **6** 项历史改动未归属：`mcp-maxwell/server.py`、`output_scripts/36slot_industrial/{coils,winding}.py`、`output_scripts/36slot_v2/{coils,winding}.py`、`scripts/{maxwell_bridge,motor_param_calc,winding_layout}.py`、`references/motor_design_guide.md` —— 未审不动 |
| **P9** | info | 看板 | M7/M8 行缺失 | 周检 P9 | 已补 | **closed** | — |
| **P10** | minor | 管线 | M7 首次跑时应用日志与 AEDT「脚本同名 .log」撞名，日志被截断（CSV 完好） | `D:/ANSYS_Run/aedt_msgwin_m7_collision_20261115.log` | 日志改名 `tpl_app_<case>.log`，重跑无截断 | **closed** | 2026-11-15 改 `tpl_solve_noload.py`/`tpl_run.py` 并加注释；本次靠 401 行 CSV + 原生 TrCrv 反证求解完整 |
| **P11** | major | 电磁 | 线 BEMF THD **11.180% > 10% 下限**；梨形窄槽口把它从 10.595% 推高 0.59 pt（与齿槽改善对冲） | `csv_tpl/flux_*.csv` + `ingest_fea.analyse_signal`（跳首周期、2–15 次）；矩形槽同法复现 10.595% 自证 | 线 THD ≤10%（目标 ≤8%） | open | G7 首选 **斜槽 0.5/1.0 槽距**（同时压 600 Hz 齿槽与 5/7 次谐波）；槽口再收窄不作为首选 |
| **E1** | major | 数值 | 网格无关性未做 | — | 3 档网格，转矩/BEMF 变化 <2% | open | 粗/中/细三档，记录 401 点 |
| **E2** | major | 数值 | 时间步无关性未做 | — | 50 µs vs 25 µs，变化 <2% | open | 两档步长对比 |
| **E3** | major | 材料 | `M270_35A` 目前线性 μ=1000；`NdFe35` 未按 100°C 修正 Br | `.aedt` 材料块 | 非线性 B-H；Br(100°C) 与 Hc 修正 | open | 导入 B-H 曲线/温度系数 |
| **E4** | major | 能量 | 能量守恒未闭环 | — | P_in = P_out + ΣP_loss，偏差 <5% | open | 从 FEA 导出损耗/功率（负载功率平衡已 −0.62%，但未含铁耗/铜耗分项） |
| **E5** | major | 热 | 热分析仍是 7 节点解析，未用 FEA 损耗复核 | `thermal_summary.json` | 热点 ≤155°C / 磁钢 ≤120°C | open | 用 FEA 损耗重跑热网络/FEA |
| **E6** | major | 退磁 | 退磁仍是解析，未用 FEA 校核 | `sim_summary.json` | B_min ≥0.2 T，SF ≥2 | open | 150°C 三相短路 FEA |
| **E7** | major | 电磁 | 转矩脉动 32.39% ≥ 15% | `fea_results.json` | ≤15%（目标 ≤10%） | **closed** | 模板 M7 梨形槽 401 点：**14.688%**（≤15% 达标）；主因 600 Hz 齿槽残余（2.04 N·m 基波幅值）；**≤10% 目标未达**，转 G7 |
| **E8** | major | 效率 | 效率 93.87% 为解析，FEA 损耗未复核 | `sim_summary.json` | ≥93.8% | open | 从 FEA 提取 P_cu/P_fe/PM |
| **E9** | major | 制造 | 槽满率/公差链/BOM 未做 | — | 满率 ≤0.78；g_min ≥0.50；BOM ±10% | open | S10 |
| **E10** | minor | NVH | 力波/模态为解析，未用 FEA 校核 | `nvh_summary.json` | 工作区无同阶共振 | open | FEA 模态/力波 |
| **E11** | minor | 标准 | 未对照 IEC 60034-1/2-1、F 级绝缘 | — | 报告列出标准条款/温升限值 | open | 补标准对照表 |
| **E12** | minor | 复核 | 独立重算尚未固化为每日检查 | 周检 §5 | 每日用独立脚本复算 BEMF/转矩 | open | `m7_load_check.py` 已内置双法（梯形 vs `ingest_fea`）；空载侧仍待固化 |


## 优先级规则

1. `blocker` 先于 `major`，`major` 先于 `minor`；同级别按“影响工程交付”排序。
2. 一天只推进**一个**问题（或一个完整实验组）。
3. 关闭条件：验收值达标 + 证据写入本表 + 回归测试通过。
4. 若某问题连续 2 天无进展，标 `blocked` 并写清阻塞点/需要的桌面操作。
