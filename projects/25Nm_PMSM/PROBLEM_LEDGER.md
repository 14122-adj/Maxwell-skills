# 25 N·m SPMSM — 问题账本（Problem Ledger）

> 每日任务开工先读本文件；收工前更新。**fail 条目不得删除**，关闭必须写证据 + 验收值。
> 严重度：`blocker`（阻塞工程交付/安全）> `major`（性能不达标）> `minor`（一致性/文档）。
> 状态：`open` / `in_progress` / `blocked` / `closed`。
> 判据见 `docs/ENGINEERING_ACCEPTANCE.md`；探索见 `EXPLORATION_LOG.md`。

## 当前基线（2026-11-13/14 真机）

| 指标 | 值 | 判据 | 状态 |
|---|---:|---:|---|
| BEMF 相 RMS | 118.8832 V | 118–145 V（±10%） | ✅ 下限附近 |
| 线 BEMF THD | 10.59% | ≤10% | ⚠️ 略超 |
| 齿槽峰峰值 | 6.84307 N·m / 27.37% | ≤1.25 N·m / 5% | ❌ |
| 负载 T_avg | 22.3344 N·m（−10.66%） | 25±20% | ✅ |
| 转矩脉动 | 32.39% | ≤15% | ❌ |
| 效率（解析） | 93.87% | ≥93.8% | 待 FEA 复核 |
| 报告 | 491,996 B / 13 表 / 7 内嵌图 | — | ✅ |

## 问题表

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **P1** | blocker | M8 | 梨形槽代码/生成已完成，但无 `.aedt`、无 401 点解、未提交 | `slot_profile.py` / `m8_gen` 21:58 | `T4_pear.aedt`：槽 93.0±2%、线圈 72±5%、Arc、12 槽、无 intersect | in_progress | 跑 `tpl_solve_noload.py` → 401 点 → 提交 |
| **P2** | major | M8 | 11 控制点直接内缩 → 线圈 62.07 mm²（−13.8%） | 周检 §6.3-1 | `_slot_pts` 半圆 ≥8 采样点；线圈 68.4–75.6 | **closed** | `slot_profile.py` 16 段弧，实测 71.863 mm² |
| **P3** | blocker | 电磁 | 齿槽 27.37% ≥ 5%，差 5.47× | `fea_results.json` | FEA 齿槽 ≤1.25 N·m | open | 梨形槽 FEA；不足则 G7 斜槽/极弧/槽口扫描 |
| **P4** | major | 几何 | 两条路径转子内径不同源：13.24 vs 20.01 mm（面积差 706.86=π·15²） | 周检 §3 | 统一 `rotor_id` 或报告注明“铁芯内部不影响场” | open | 查 `pmsm_config` / 模板 `RotorOuter` 参数 |
| **P5** | minor | 复核 | `fea_results.bemf_balance_pct=0.008%` 与独立重算 0.220% 不一致 | 周检 §5 | 报告脚注写清求导/重采样口径 | open | 统一 BEMF 重算脚本/口径 |
| **P6** | minor | 文档 | 767,290 vs 958,509 B；线圈 75.24 vs 79.9568；9 图 vs 内嵌 7 | 周检 P6 | 三处数字与 `weekly_audit.json` 一致 | open | 改数或改口径 |
| **P7** | minor | 文档 | `SKILL.md:211` 旧梨形尺寸（Bs0=3.5…Rs=4.15） | 周检 P7 | 换成表 2 参数 | open | 更新示例 |
| **P8** | minor | 仓库 | 工作树 11 项未提交；M8 文件也未提交 | `git status` | M8 文件单独提交，不扫入已有脏改动 | open | 按文件清单提交 |
| **P9** | info | 看板 | M7/M8 行缺失 | 周检 P9 | 已补 | **closed** | — |
| **E1** | major | 数值 | 网格无关性未做 | — | 3 档网格，转矩/BEMF 变化 <2% | open | 粗/中/细三档，记录 401 点 |
| **E2** | major | 数值 | 时间步无关性未做 | — | 50 µs vs 25 µs，变化 <2% | open | 两档步长对比 |
| **E3** | major | 材料 | `M270_35A` 目前线性 μ=1000；`NdFe35` 未按 100°C 修正 Br | `.aedt` 材料块 | 非线性 B-H；Br(100°C) 与 Hc 修正 | open | 导入 B-H 曲线/温度系数 |
| **E4** | major | 能量 | 能量守恒未闭环 | — | P_in = P_out + ΣP_loss，偏差 <5% | open | 从 FEA 导出损耗/功率 |
| **E5** | major | 热 | 热分析仍是 7 节点解析，未用 FEA 损耗复核 | `thermal_summary.json` | 热点 ≤155°C / 磁钢 ≤120°C | open | 用 FEA 损耗重跑热网络/FEA |
| **E6** | major | 退磁 | 退磁仍是解析，未用 FEA 校核 | `sim_summary.json` | B_min ≥0.2 T，SF ≥2 | open | 150°C 三相短路 FEA |
| **E7** | major | 电磁 | 转矩脉动 32.39% ≥ 15% | `fea_results.json` | ≤15%（目标 ≤10%） | open | 与齿槽同源，先压齿槽 |
| **E8** | major | 效率 | 效率 93.87% 为解析，FEA 损耗未复核 | `sim_summary.json` | ≥93.8% | open | 从 FEA 提取 P_cu/P_fe/PM |
| **E9** | major | 制造 | 槽满率/公差链/BOM 未做 | — | 满率 ≤0.78；g_min ≥0.50；BOM ±10% | open | S10 |
| **E10** | minor | NVH | 力波/模态为解析，未用 FEA 校核 | `nvh_summary.json` | 工作区无同阶共振 | open | FEA 模态/力波 |
| **E11** | minor | 标准 | 未对照 IEC 60034-1/2-1、F 级绝缘 | — | 报告列出标准条款/温升限值 | open | 补标准对照表 |
| **E12** | minor | 复核 | 独立重算尚未固化为每日检查 | 周检 §5 | 每日用独立脚本复算 BEMF/转矩 | open | 把 `verify_fea.py` 纳入流程 |

## 优先级规则

1. `blocker` 先于 `major`，`major` 先于 `minor`；同级别按“影响工程交付”排序。
2. 一天只推进**一个**问题（或一个完整实验组）。
3. 关闭条件：验收值达标 + 证据写入本表 + 回归测试通过。
4. 若某问题连续 2 天无进展，标 `blocked` 并写清阻塞点/需要的桌面操作。
