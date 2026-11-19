# 文件生命周期规范 —— 临时测试 vs 长期保存

> 建立日期：2026-11-19。来源：用户要求「每日迭代写明哪些是临时测试、哪些是长期保存，周检做一次文件清理」。
> 本文件是**唯一分类权威**；每日任务创建文件时必须按 §2 打标记，周检按 §4 清理。
> 归类地图见 `docs/WORKSPACE_MAP.md`（讲"放哪"），本文件讲"留多久、谁清理"。

## 1. 三类文件（KEEP / TEMP / ARCHIVE）

| 类 | 定义 | 判定口诀 | 生命周期 |
|---|---|---|---|
| **KEEP 长期保存** | 设计契约、判据、验收证据、可复现脚本、测试、报告 | **删了就无法复现结论或重建模型** | 永久入库；改动需提交 + 理由 |
| **TEMP 临时测试** | 试算脚本、求解中间工程、日志、空/失败 CSV、模板派生目录 | **由模板 + 一个旋钮一键再生，或只用于诊断** | 用完即弃；周检清理；**不入库** |
| **ARCHIVE 归档** | 冻结的旧项目产物、历史周检、旧报告 | **有审计价值但不参与当前迭代** | 入库但只读；只进不出 |

## 2. 分类清单（按真实路径，非抽象规则）

### 2.1 KEEP —— 长期保存（绝不清理）

| 路径 | 内容 | 为什么必须留 |
|---|---|---|
| `projects/IPM_8p48s/PROJECT_SPEC.md` | 新项目唯一设计契约（D1–D7 定源） | 删了设计依据断链 |
| `projects/IPM_8p48s/PROBLEM_LEDGER.md` | I1–I7 问题账本（含 fail 记录） | 反自演证据链 |
| `projects/25Nm_PMSM/{DESIGN_PROGRESS,WEEKLY_GOALS,PROBLEM_LEDGER,EXPLORATION_LOG}.md` | SPM baseline 看板/账本（已冻结） | 阶段切换与对比基线 |
| `docs/{DAILY_LOOP,ENGINEERING_ACCEPTANCE,MAXWELL_INTERNALS,PEAR_SLOT_SPEC,FILE_LIFECYCLE,WORKSPACE_MAP}.md` | 方法/判据/API 坑/槽型规格 | skill 的核心知识 |
| `docs/WEEKLY_AUDIT_*.md` + `docs/weekly_audit.json` | 历次周检判定 | 监督审计轨迹 |
| `scripts/`（17 py）、`tests/`（23 py） | skill 核心包与回归测试 | 模板与门禁，删了不可复现 |
| `projects/*/maxwell/` | 模板路径求解脚本（`tpl_solve_noload.py` 等）与手写路径脚本 | 真机链路代码 |
| `projects/25Nm_PMSM/{gen_maxwell_model,pmsm_config,ingest_fea,make_report}.py` | 配置/生成/解析/报告主链 | 一条不能少 |
| `projects/results/fea/**/*.csv`、`projects/results/*.json` | **验收数据**：401/801 行 CSV、汇总 JSON | 每个性能数字的证据；**任何情况下不清理** |
| `projects/results/figures/` | 报告内嵌图 | 报告完整性 |
| `SKILL.md`、`README.md`、`pyproject.toml`、`.github/` | skill 入口与 CI | — |

### 2.2 TEMP —— 临时测试（周检清理对象）

| 路径 / 模式 | 内容 | 清理条件 |
|---|---|---|
| `D:/ANSYS_Run/*_test*.py`、`g4b_*.py`、`tpl_body_*.py`、`try_*.py`、`*_probe.py`、`*_check.py` | 一次性诊断/试算脚本 | 对应诊断已结案；**若结论被账本引用则先把证据迁到 KEEP 再删** |
| `D:/ANSYS_Run/*.log` | AEDT 应用日志（98 个） | 保留被引用的关键日志行到账本后清理；`ANALYZE_OK` 行必须先抄进证据 |
| `D:/ANSYS_Run/*.aedt`、`.aedtresults/`、`*.batchinfo/` | Maxwell 求解工程与缓存（30 + 67 目录） | 求解已完成且 CSV 已归档；`.lock` 文件需先确认无 Maxwell 进程 |
| `D:/ANSYS_Run/csv_*/*.csv` | 试算导出（含只有表头的空 CSV） | 空/失败 CSV 直接清；有效 401 行先归档到 `projects/results/fea/` 再清 |
| `projects/*/maxwell_model_*`（除 `maxwell_model/`） | 模板 + 旋钮的派生脚本目录（已 gitignore） | 可一键再生；对应 CSV 已归档 |
| 工作区 `debug/`、`.pytest_cache/`、`.ruff_cache/`、`__pycache__/` | 调试器与缓存 | 随时可清 |
| `projects/IPM_8p48s/TEMP/` | 新项目专用临时区（**新建**） | D1–D7 未定源前的临时参数脚本只能放这里 |

### 2.3 ARCHIVE —— 归档（只读，不清理）

| 路径 | 内容 |
|---|---|
| `archive/` | 历史脚本 |
| `projects/25Nm_PMSM/REPORT*.html`、`output_scripts/36slot_*/`（旧机型生成物） | 有审计/复用价值 |
| 冻结的 SPM `.aedt`（若日后为审计需要保留） | 阶段证据 |

## 3. 每日任务的文件纪律（创建即打标）

1. **先判类再落盘**：新建任何文件前，先按 §2 判断属于 KEEP / TEMP / ARCHIVE。
2. **临时脚本只能进 TEMP 区**：
   - 工作区内 → `projects/<项目>/TEMP/`（新项目已有）；
   - Maxwell 运行区 → `D:/ANSYS_Run/`（本身即临时区，不入库）。
   - **绝不**把试算脚本写进 `scripts/`、`projects/<项目>/maxwell/` 或项目根目录。
3. **临时值隔离**：D1–D7 未定源的参数只能出现在 `TEMP/` 脚本里，不得进 baseline 配置（与 `PROJECT_SPEC.md` §5 一致）。
4. **证据先迁后清**：任何临时产物里被账本/报告引用的数字，必须先把证据（CSV 行 / 日志行 / JSON 键 + 文件路径）迁到 KEEP 区，才允许标为可清理。
5. **每日交付写明**：当天在 `DESIGN_PROGRESS.md` 或 IPM 账本里记一行「新增文件 → 分类」，格式：
   `新增：<路径> [KEEP|TEMP|ARCHIVE] <一句话理由>`。

## 4. 周检清理流程（每周一次，只清 TEMP）

> 安全约束：**先列清单 → 人工/日志确认 → 再清理**；不碰 KEEP / ARCHIVE，不碰 git 跟踪文件，不删任何 `projects/results/**`。

1. **盘点**：扫描 §2.2 的 TEMP 路径，生成 `docs/CLEANUP_REPORT_YYYY-MM-DD.md`，逐条列出：路径、大小、创建/修改时间、最后引用位置（grep 账本/看板/报告）、建议动作（保留/删除/归档）。
2. **判定**：
   - 被账本/报告/契约引用 → **保留**（或迁移证据后归档）；
   - 空 CSV、失败试算、`__pycache__`、缓存 → **删除**；
   - 已归档 CSV 的 `.aedt`/`.aedtresults` → **删除**；
   - 拿不准 → **保留并标 `REVIEW`**，不擅自删。
3. **执行**：
   - 只删 §2.2 明确列出的 TEMP 路径；**禁止递归删除工作区根目录、`D:/ANSYS_Run` 根目录本身**；
   - Maxwell 进程存活时（检查 `tasklist | grep ansysedt`）**不删任何 `.aedt`/`.lock`**；
   - 优先用回收站/移到 `D:/ANSYS_Run/_trash_YYYY-MM-DD/`，保留 7 天再彻底删；
   - 每批 ≤ 20 个文件，删后核验。
4. **记账**：把清理结果（删了多少、释放多少、保留了什么及原因）写进 `docs/CLEANUP_REPORT_YYYY-MM-DD.md` 和周检报告的 G9 段。
5. **入库**：只提交 `docs/CLEANUP_REPORT_*.md`；**不**把 TEMP 文件 add 进 git。

## 5. 反自演条款（继承）

- 清理**不得**删除 fail 记录或被否定的试算结论——它们必须已在账本里留痕；清理的是文件，不是历史。
- 不得以"清理"为名隐藏未达标数据；周检核对账本 fail 条目数量只增不减。
- 清理后必须能重跑 `docs/DAILY_LOOP.md` 的标准流程（模板可再生成、CSV 未被删）。
