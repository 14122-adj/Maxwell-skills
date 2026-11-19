# 每日闭环（Daily Loop）— 从“能跑”到“工程可用”

> 目标：每天不是“改一点代码”，而是让模型在**真实工程判据**下前进一步；
> 标准流程 green 后自动进入探索，而不是永远在同一个模型上自编自演。
> 判据：`docs/ENGINEERING_ACCEPTANCE.md`；问题：`projects/25Nm_PMSM/PROBLEM_LEDGER.md`；
> 探索：`projects/25Nm_PMSM/EXPLORATION_LOG.md`。

## 闭环七步

```
0 Observe → 1 Standard → 2 Diagnose → 3 Optimize → 4 Explore → 5 Deliver → 6 Commit/Push
                  ↑                         │
                  └──── 未 green 回修管线 ←──┘
```

## 阶段闸门（2026-11-14）

- 当前只做 **M8 验证 + P3–P8**；**不启动自动探索**。
- 探索解锁条件：G0–G4 全绿 **且周检书面批准**（在 `EXPLORATION_LOG.md` 写批准日期/范围）。
- 周检负责监督/矫正；越权探索、拿解析填 FEA、只报好案例等，按**流程违规**处理。

### 0. Observe（开工先读）
- `PROBLEM_LEDGER.md`：当前 blocker/major、上次未闭环项。
- `DESIGN_PROGRESS.md`：昨日/今日/明日、阶段状态。
- `WEEKLY_GOALS.md` / 最近周检：本周目标与判定。
- `projects/results/fea_results.json`：基线数值。
- `git log --oneline -10`：避免重复。

### 1. Standard（标准流程，必须先 green）
```
gen_maxwell_model.py 重生成 → tpl_solve_noload.py 建模 → Analyze 401 点
→ 导出 flux/torque CSV → 独立重算 BEMF/齿槽/负载 → 对照基线
```
- 门槛：G0–G3（可复现/几何/材料/求解设置）+ G4 的 BEMF/转矩/齿槽有数。
- **任何一步失败：只修管线，不做优化**；不得在坏模型上做参数扫描。
- 401 点才算数；试算/5 点只能判“能解”，不能判性能。

### 2. Diagnose（独立诊断，不是自证）
按 `ENGINEERING_ACCEPTANCE.md` §3 做检查：
- 解析 vs FEA、模板 vs 手写、独立脚本 vs 工作区脚本。
- 网格/时间步无关性、能量守恒、磁通连续性、三相平衡、边界/单位。
- 每个异常写入 `PROBLEM_LEDGER.md`（ID/严重度/证据/验收/状态）。
- 结论必须分 `PASS` / `FAIL` / `BLOCKED`；不许把 FAIL 写成“基本通过”。

### 3. Optimize（一天一个完整实验）
- 从账本取**最高优先级**的一个问题（blocker > major > minor）。
- 设计一个 FEA 实验：单变量为主；写清假设、判据、对照基线。
- 跑 401 点 → 记录 → 判定：
  - 达标：关闭账本项（写证据/验收值），回归测试。
  - 未达标：保留失败记录，更新假设，明日继续或转 G7。
- 不允许“改判据/改口径/删失败案例”。

### 4. Explore（标准流程 green 后自动进入）
- 触发：G0–G4 全绿 **且周检书面批准**（`EXPLORATION_LOG.md` 里写批准日期/范围）。
- **当前阶段（2026-11-14）：M8 验证未完成，探索 LOCKED；不要跑探索案例。**
- 每次 1 个探索案例（OFAT）或 1 组 DOE（≤3 变量）。
- 记录到 `EXPLORATION_LOG.md`：参数、401 点结果、失败原因、证据。
- 目标：齿槽 ≤5%、脉动 ≤10%、THD ≤10%、η ≥93.8%、T_avg 25±10%。
- 若物理不可达：给“最接近 + 代价”，不改判据。

### 5. Deliver（交付物）
- 更新 `DESIGN_PROGRESS.md`（昨日/今日/明日、M 阶段、产物）。
- 更新 `PROBLEM_LEDGER.md`（关闭/新增/阻塞）。
- 更新 `EXPLORATION_LOG.md`（如探索）。
- 更新报告/测试/文档；`pytest` + `ruff` 通过。
- 报告里分列 analytic / FEA，写清假设与局限。

### 6. Commit / Push（每天必做）
- 只 `git add` 本阶段文件；**不要 `git add -A`**；不提交 `.aedt`/`.asol`/`__pycache__`/大图。
- 提交信息：`feat(motor): Mx ...` / `fix(motor): ...` / `docs(motor): ...`。
- CI 红：修根因，不放宽规则/删测试。
- 推送成功后在日志写 commit hash；失败保留本地提交并说明。

## 决策树

```
Standard 失败?
├─ 是 → 修管线（API/几何/材料/边界/导出），不探索
└─ 否 → Diagnose
        ├─ 有 blocker/major → Optimize（选最高优先级，一个实验）
        └─ 全绿 → Explore（一个案例/DOE）
                  └─ 找到更优 → 更新基线 → 重跑 Standard
```

## 每日报告格式（必须）

```
【昨日】完成了什么（commit + 文件 + 验收）
【今日】标准流程结果（401 点 / BEMF / 齿槽 / 负载）
        诊断结论（PASS/FAIL，证据）
        优化/探索实验（参数、结果、判定）
【Maxwell 状态】运行次数、rc、日志、.aedt、对象/尺寸、Analyze
【账本】关闭 X，新增 Y，阻塞 Z
【明日】一个最高优先级目标 + 判据
```

## 周检监督（每周任务）

周检不只看数字，还要**监督每日任务是否按闭环执行、是否在自演**：

1. **流程合规**：每日是否从账本选一个最高优先级问题？标准流程是否 401 点？是否先 green 再优化？
2. **证据质量**：每个数字是否有 CSV/JSON/日志/键值证据？是否拿解析填 FEA 空缺？是否拿试算/5 点当性能？
3. **失败记录**：`PROBLEM_LEDGER` 的 fail 是否保留？`EXPLORATION_LOG` 是否只报好案例？
4. **提交纪律**：是否每天 commit/push？是否 `git add -A` 扫入脏文件？
5. **探索闸门**：G0–G4 未绿 / 未批准就探索 → **流程违规**，暂停探索并纠正 daily prompt。
6. **文件分类与清理**：是否按 `docs/FILE_LIFECYCLE.md` 给新增文件打 KEEP/TEMP/ARCHIVE 标记？临时脚本是否只进 `projects/IPM_8p48s/TEMP/` 或 `D:/ANSYS_Run/`？周检是否每周清理一次 TEMP 并出 `docs/CLEANUP_REPORT_YYYY-MM-DD.md`（清理前后账本 fail 条目只增不减）？
7. **纠偏输出**：用 `automation_update` 更新每日任务 prompt（**保留 22:30，用户设定，勿改**），写入 top 3 + 下周**单一焦点**；连续 2 天无进展的问题标 `blocked` 并换路径。

周检 scorecard（写入报告）：

| 维度 | 分值 | 判据 |
|---|---|---|
| 流程合规 | 0–2 | 闭环七步、先 green 后优化、401 点 |
| 证据质量 | 0–2 | 可追溯、独立复核、解析/FEA 分列 |
| 进度 | 0–2 | 账本关闭/推进、无连续卡死 |
| 探索就绪 | 0–1 | G0–G4 green + 批准；未就绪必须写 LOCKED |

## 文件生命周期（2026-11-19 新增）

每日**创建即打标**，周检**每周清一次 TEMP**，权威分类见 `docs/FILE_LIFECYCLE.md`：

| 类 | 例子 | 处理 |
|---|---|---|
| **KEEP 长期保存** | 契约/账本/判据/方法文档、`scripts/`+`tests/`、`projects/results/fea/**/*.csv` 与汇总 JSON、报告 | 入库，绝不清理 |
| **TEMP 临时测试** | `D:/ANSYS_Run/*.log`、试算脚本（`g4b_test*.py`/`tpl_body_*.py`/`try_*.py`）、`.aedt`/`.aedtresults`、空 CSV、`maxwell_model_*` 派生目录、`debug/`、缓存 | 不入库，周检清理；临时脚本只进 `projects/IPM_8p48s/TEMP/` 或 `D:/ANSYS_Run/` |
| **ARCHIVE 归档** | `archive/`、冻结的 SPM 旧产物 | 入库，只读，只进不出 |

- **证据先迁后清**：临时产物里被账本/报告引用的数字，先把证据迁到 KEEP 区才允许标"可清理"。
- **每日交付记一行**：`新增：<路径> [KEEP|TEMP|ARCHIVE] <理由>`。
- **周检清理安全**：先列 `docs/CLEANUP_REPORT_YYYY-MM-DD.md` → 判定 → 只清 TEMP；有 Maxwell 进程时不删 `.aedt`/`.lock`；优先移 `_trash_` 留 7 天；fail 条目只增不减。

## 硬约束
- **时间不改**：每日 **22:30**（用户设定，实际 rrule），不要调整 rrule；周检周日 22:00。
- **不上传假数据**：无证据的数字不写；不用解析填 FEA 空缺；不用试算/单点下结论。
- **不重复误判**：Band 薄环 / `EditSetup` 丢运动 / 齿槽 1.6% / `Init Pos` 能斜槽 已被推翻。
- **不跳过验收**：技能可用 ≠ 设计合格；G4b 场探针 blocked，G4 未全绿，**不得用解析填 FEA**。
- **项目状态**：SPM 8p12s 冻结为 baseline；当前项目 IPM 8p48s（双层 V 型 + 双层三相绕组），探索 LOCKED。
