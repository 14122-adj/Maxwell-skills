# 本周目标（2026-11-14 起）

> 来源：`docs/WEEKLY_AUDIT_2026-11-14.md`（周检判定：**技能可用 / 设计不合格**）
> 上一轮（2026-11-07）的判定是「部分失败 / 条件可用」，G1–G5 已全部关闭，存档见文末。
> 纪律：按 G6 → G7 → G8 顺序推进，做完一条再开下一条；每条完成后在 `DESIGN_PROGRESS.md`
> 记一行「产物路径 + 关键数值」，不得编造数字。

---

**本轮 top 3（按优先级）**

## G6 —【blocker｜M8】梨形槽未开工，齿槽 27.37% 仍是设计不合格的唯一主因

> **状态：⏳ 进行中（规格已冻结 2026-11-14 13:47，代码 0%）**。
> 周检实测：`1af9ddd` 只提交了 `docs/PEAR_SLOT_SPEC.md`，`main.py` 的 `pear` 分支仍是旧
> 7 点浅梨形、`gen_maxwell_model.build_config` 仍是 `RECTANGULAR`、全盘无 `T4_pear*.aedt`
> ⇒ 判 **not started**，不得用解析值顶替 FEA。

| 项 | 内容 |
|---|---|
| 问题 | 定子槽现在是「窄口矩形」（`Bs0=2.5 / Hs2=18.0 / Bs2=9.5`，槽面积 **103.25 mm²**），齿槽峰峰值 **6.84307 N·m = 27.37% 额定**，判据 ≤5% ⇒ 差 **5.47 倍**。用户 2026-11-14 给出表 2 梨形槽尺寸，要求按此改造。 |
| 规格 | `Bs0=0.8 / Hs0=1.5 / Hs1=1.8 / Hs2=12.5 / Bs1=6.0 / Bs2=9.5 / Rs=4.75`；口径 **`Hs2` = 内径→槽底最底端** ⇒ `x1=48.0 / x2=49.8 / x3=54.25 / x4=59.0`，轭 **16.0**，槽面积 **93.02**，线圈 **72.03**（详见 `docs/PEAR_SLOT_SPEC.md`） |
| 做法 | ① `_gen_geometry` 的 `pear` 分支改 11 点 + 10 段，`Arc StartIndex:=4 / NoOfPoints:=3`；② `_slot_pts` 同步 11 点**并给半圆补 ≥8 采样点**；③ `gen_maxwell_model.build_config` 切 `PEAR` + 表 2 尺寸；④ 重生成 → 真机空载 |
| 验收 | ① 槽面积 **93.0±2%**、线圈 **72±5%**、底部 `Arc`、12 槽、无 `intersect`/`Non-manifold`；② 真机 401 点，BEMF 与 **118.8832 V** 偏差 ≤10%；③ 齿槽 **≤6.843 N·m**（目标 **≤1.25 N·m / 5%**）；④ 负载 `T_avg` 仍 25±20%；⑤ `pytest`/`ruff` 全绿、`--check` 无漂移 |
| 已量化的坑 | 若 `_slot_pts` 只给 11 控制点（底部是弦不是弧）：11 边形面积 **80.15**，线圈 **62.07 mm² = −13.8%**，**必撞穿 72±5%**。弧采样不是"优化"，是硬前提 |
| 面积核验口径 | 生成后 `StatorOuter` 应为 **≈9,764 mm²**（10878.55 − 12×92.86，含槽口 0.2 重叠）；±5 mm² 内即算对。不要直接拿 `GetFaceArea` 反算值判 93.0±2% |

---

## G7 —【major｜M8 续】梨形槽若单独压不到 5%，走斜槽 / 极弧 / 槽口扫描

> **状态：⏳ 待 G6 出数后启动**（不预先开工，避免和 G6 抢真机时间）。

| 项 | 内容 |
|---|---|
| 问题 | 齿槽对槽口宽是强非线性（现 `2.5 → 0.8 mm` 是主因），但梨形槽不改变极弧与斜槽，**不能保证单独落到 5%**。解析值 1.815% 曾把齿槽低估 15 倍，不能作为依据。 |
| 做法 | 固定梨形槽，按 `① 极弧系数 0.87→0.82/0.90`、`② 斜槽 1 个槽距（分段叠片或 2D 分段等效）`、`③ 槽口 0.8→0.6 mm` 三个单变量扫描，每个工况真机 401 点 |
| 验收 | 至少给出 3 组 FEA 齿槽值 + 1 组达到 ≤1.25 N·m；达不到则明确写「当前拓扑在 2D 单变量下无解」，并给出下一步（磁极偏斜/不等齿宽） |
| 关联 | P3（齿槽 27.37%）、`PEAR_SLOT_SPEC.md` §5-6 |

---

## G8 —【minor｜可复现性】工作树脏 + 4 处文档数值漂移

> **状态：⏳ 待办**（不影响 M8，但影响"别人拿到仓库能不能复现"）。

| 项 | 内容 |
|---|---|
| 问题 | ① 工作树 9 改 + 2 未跟踪（`SKILL.md`、`mcp-maxwell/server.py`、3 个 `winding/coils.py` 等）；② `DESIGN_PROGRESS` 记 `T4_tpl_noload.aedt` 767,290 B，实际 **958,509 B**；③ G5 记线圈 **75.24** mm²，实测 **79.9568**；④「9 图」实为 `figures` 9 张、报告内嵌 **7** 张；⑤ `SKILL.md:211` 示例仍写旧梨形尺寸（`Bs0=3.5…Rs=4.15`），与表 2 冲突；⑥ `fea_results.bemf_balance_pct=0.008%` 不可独立复现（独立算 0.220%） |
| 做法 | 数值改成实测值或标注口径；`SKILL.md` 示例换表 2 参数；脏文件择机单独提交（不要 `git add -A`） |
| 验收 | 报告/看板/SKILL 三处数字与 `weekly_audit.json` 一致；`git status` 干净或每项有归属 |

---

## 已关闭目标（G1–G5，2026-11-07 起的上一轮，存档）

## G1 —【blocker｜阶段 S6 前置】建模入口几何不自洽，小机型从零建模必失败

> **状态：✅ 已关闭 2026-11-07**（`scripts/motor_config.py` 几何派生 + `tests/test_motor_config.py` 16 例）。
> 验收②的 `RotorOuter = 46.125 mm` 与本行 δ=0.675 自相矛盾，实取 **45.825 mm**（= 46.5 − 0.675），
> 理由见 `DESIGN_PROGRESS.md` §G1 完成记录。

| 项 | 内容 |
|---|---|
| 问题 | `scripts/motor_config.py:117` 将 `rotor_od` 写死为 135.6（36slot 预设常量），`__post_init__`/`from_dict` 不做 `rotor_od = stator_id − 2·airgap` 派生。凡 `stator_id < 135.6 mm` 的机型经 `scripts/main.py` 从零建模必然 rc=1，报「转子外径必须小于定子内径」，本机 25 N·m 机型（Dsi=93）首跑即失败。 |
| 验收标准 | ① 干净 venv 下 `python scripts/main.py --params "slots=12 poles=8 stator_od=150 stator_id=93"` → rc=0、参数校验通过；② 生成 `geometry.py` 中 `RotorOuter` = **46.125 mm**（= 93/2 − δ，δ 按 `0.3 + Dso/400` = 0.675 mm 推导）、`Region` 半径 ≥ 1.25×Rso；③ 新增 `tests/test_motor_config.py`，覆盖 Dsi<135.6 / Dsi>135.6 / 显式给 rotor_od 三例，`pytest -q` 全绿；④ 显式传 `rotor_od` 时行为不变（不覆盖用户输入）。 |
| 建议对应阶段 | **S6**（FEA 实跑前必须能用 skill 自身重建模型；当前只能靠手写参数绕过） |
| 关联审计项 | P1（`motor_config.py:117`）、P12（缺测试） |

---

## G2 —【blocker｜阶段 S11】报告链路依赖未声明，干净环境装完包仍跑不通

> **状态：✅ 已关闭 2026-11-07**（`pyproject.toml` 依赖提升为 core + `make_report.py` 缺包守卫与 P7 修复
> + `SKILL.md` 安装前置 + `tests/test_report_deps.py` 4 例）。
> 新建 venv `pip install -e .` 后 `make_report.py` **rc=0**，产出 **255,102 B** HTML、内嵌 **6** 图 / **12** 表。

| 项 | 内容 |
|---|---|
| 问题 | `pyproject.toml:49-51` 的 `dependencies` 只有 `pyyaml`；`matplotlib`/`numpy` 仅在 `[plot]` extra，`pytest` 仅在 `[dev]`。干净 venv 执行 `pip install -e .` 成功后，`projects/25Nm_PMSM/make_report.py:17` 直接 `ModuleNotFoundError: No module named 'matplotlib'`（rc=1），报告链路断在第一行 import。 |
| 验收标准 | ① 新建 venv → `pip install -e .` → `python projects/25Nm_PMSM/make_report.py` → **rc=0**，产出 `REPORT_25Nm_SPMSM.html` **> 200 KB**，`data:image/png;base64` 计数 **≥ 5**、`<table>` 计数 ≥ 10；② 全程无需手工补装任何包；③ `SKILL.md` 增加一行硬性前置（形如 `pip install -e ".[plot,dev]"`，或在 `dependencies` 中直接声明）；④ `make_report.py` 在 ImportError 时抛出中文可读提示，而非裸栈。 |
| 建议对应阶段 | **S11**（最终评审报告是全链路交付物，其可复现性由本目标保证） |
| 关联审计项 | P2（`pyproject.toml:49`）、P7（`make_report.py:411` 转义告警可一并修） |

---

## G3 —【major｜阶段 S6】2D 叠长丢失，FEA 转矩/损耗将低估约 160×

> **状态：✅ 已关闭 2026-11-11**。验收 ①②③ 全达成，④ 由 M4/M5 既有的 401 点解覆盖
> （`T_avg` 22.3344 N·m = −10.66% 额定，落在 ±20% 内；`m4_build_solve.py` 早已手写
> `MODEL_DEPTH = "160mm"`，本次把它变成模板的默认行为，不再靠人记得）。
> 实机证据：`G3_depth160.aedt` → `ModelDepth='160mm'`、`G3_depth180.aedt` → `'180mm'`
> （证明非硬编码）、`G3_generated_setup.aedt` → `'160mm'`（**模板生成的 setup.py 本体**
> 在 AEDT 里跑出来的工程）。回归 `tests/test_model_depth.py` 27 例，全仓 251 passed。
> 遗留：4 处真机 API 修复仍只存在于生成物、未回灌模板 → 新开 **G3b**（明日）。

| 项 | 内容 |
|---|---|
| 问题 | `stack_length`（25 N·m 机型 = 160 mm）从未被任何生成器消费：`main.py` 生成的 `setup.py` 与 `maxwell_model/solve_25Nm_SPMSM.py` 的 `SetDesignSettings` 都只设 `PreserveTransientSolution`/`ComputeTransientInductance`，**不含 `ModelDepth`**；全仓 121 个 `.py` 中 `ModelDepth` 仅出现在 `debug/` 三个读取器里。Maxwell 2D 默认模型深度 1 mm，实跑转矩、铁耗、反电势幅值将整体低估 ≈160×。 |
| 验收标准 | ① `scripts/main.py` 生成的 `setup.py` 内含 `ModelDepth:="160mm"`（随 `--params stack_length=` 变化，非硬编码）；② `maxwell_model/solve_25Nm_SPMSM.py` 同样设置；③ 回归校验：生成物 `grep -c ModelDepth ≥ 1`，`MotorConfig.validate()` 断言 `stack_length > 0`；④ 桌面会话实跑后，`ingest_fea.py` 回填的 `T_avg` 与解析值 25 N·m 同量级（±20%），否则视为本目标未达成。 |
| 建议对应阶段 | **S6**（FEA 实跑与结果回填；沙箱无法实跑，脚本与校验先落地并标 blocked） |
| 关联审计项 | P3（`main.py:903`、`solve_25Nm_SPMSM.py:65-67`） |

---

## G4 —【blocker｜M0/M1】Maxwell 实机启动与最小工程（最高优先级）

> **状态：✅ 已关闭 2026-11-07**（真机 rc=0，`M1_min.aedt` 17,233 B）。
> 验收①里的命令行**写错了**：`-ng` 不能与 `-RunScriptAndExit` 组合，正确命令为
> `ansysedt.exe -RunScriptAndExit "脚本"`。此前「沙箱 rc=1 = 环境限制」的判断是命令用法错误，
> 详见 `DESIGN_PROGRESS.md` §M0/M1/M2 实测记录。

| 项 | 内容 |
|---|---|
| 问题 | 技能最终产出是 Maxwell 中的电机模型，但周检把 FEA 实跑标为「环境限制、不计入」，导致 G1–G3 都在解析/打包层打转。必须把「Maxwell 能否真正启动并生成 `.aedt`」作为可用性硬门槛。 |
| 验收标准 | ① `ansysedt.exe -ng -RunScriptAndExit` 跑最小脚本，rc=0，生成 `D:\ANSYS_Run\M1_min.aedt`；② 记录 stdout/stderr/日志；③ 若沙箱 rc=1，报告必须标 blocker 并给出桌面一键命令，**不得判「可用」**。 |
| 建议对应阶段 | M0/M1 |
| 关联审计项 | 周检 §1 第 7 项、§4 结论 |

## G5 —【blocker｜M2/M3】25 N·m 几何/材料/绕组在 Maxwell 中落地

> **状态：✅ 已关闭 2026-11-07**。`M4_25Nm.aedt` 实测：
> ① 24 个 2D 图元（Region + 定子 1 + 转子 1 + 磁钢 8 + 线圈 12 + Band 1）；
> ② 面积反算尺寸全部吻合（定子 9645.55 / 转子 5890.27 / Band 6694.66 / 磁钢 59.878 / 线圈 75.24 mm²）；
> ③ `M270_35A`×2、`NdFe35_N/S`、`copper` 已绑定；
> ④ `BoundType='Coil'`×12 + `Winding Group`×3 + Band + Mesh 操作存在；
> ⑤ `ModelDepth='160mm'`。
> 关键修正：AEDT 2021.1 的 `AssignCoilGroup` 参数类型极挑，改用逐个
> `AssignCoil(["NAME:...", "Objects:=", ["Coil_x"], "Conductor number:=", "40",
> "PolarityType:=", "...", "Winding:=", "WindingA"])` 一次成功。

| 项 | 内容 |
|---|---|
| 问题 | 现有 `solve_25Nm_SPMSM.py` 只做了 `py_compile`，未在 Maxwell 中实际生成过工程；`ModelDepth` 未设置（G3），几何/材料/绕组/band 是否被 Maxwell 接受均未验证。 |
| 验收标准 | ① 在 Maxwell 中生成 `.aedt`，对象数 = 定子 1 + 转子 1 + 轴 1 + 磁钢 8 + 线圈 12 + band 1 + region 1；② 关键尺寸 75.0 / 46.5 / 45.825 / 46.1625 mm；③ 材料 `M270_35A` / `NdFe35_N` / `NdFe35_S` / `copper` 存在；④ 6 个线圈组 + Band 1500 rpm + Mesh 操作存在；⑤ `ModelDepth = 160 mm`（G3 前置）。 |
| 建议对应阶段 | M2/M3 |
| 关联审计项 | P3（ModelDepth）、周检 §1 第 7 项 |

## 排期建议（本轮）

| 日 | 动作 | 完成判据 |
|---|---|---|
| D1 | G3 代码层：`_gen_setup()` 注入 `ModelDepth` + `validate()` 断言 | ✅ 完成 2026-11-11（`G3_depth160/180` + `G3_generated_setup.aedt`） |
| D2 | G4/M1：`ansysedt -RunScriptAndExit` 最小脚本 | ✅ 完成（`M1_min.aedt`） |
| D3 | G5/M2：25 N·m 几何在 Maxwell 中生成 | ✅ 完成（`M2_25Nm.aedt`，24 图元） |
| D4 | M3：材料/绕组/Band/边界/Setup | ✅ 完成（`M4_25Nm.aedt`：12×Coil、3×Winding、160mm、M270、VP、Setup1） |
| D5 | **M4：空载瞬态** | ✅ 完成（401 点全时长解，BEMF 118.8832 V，齿槽 6.84307 N·m） |
| D6 | M5：负载瞬态 | ✅ 完成（`T_avg` 22.3344 N·m，−10.66%） |
| D7 | M6 + 周检复跑 | ✅ 完成（`fea_results.json` 进报告 §11） |
| D8 | G3b/G4：模板回灌 + 模板路径空载求解 | ✅ 完成 2026-11-13（`T4_tpl_noload.aedt`，与手写 +0.02%/−0.37%） |
| **D9** | **G6：梨形槽 11 点 + 弧采样 → 重生成 → 真机空载** | 槽面积 93.0±2%、线圈 72±5%、齿槽 ≤6.843（目标 ≤1.25）N·m |
| **D10** | **G7：极弧 / 斜槽 / 槽口单变量扫描** | 至少 3 组 FEA 齿槽值，其中 1 组 ≤1.25 N·m |
| D11 | G8：工作树 + 文档数值对齐 | `git status` 干净、三处数字与 `weekly_audit.json` 一致 |

## 明确不在本轮范围

- 旧审计的 P4（未知参数静默丢弃）、P5（`WINDING_KW=0.933` vs 0.866）、P6（`T_avg` 回填额定值）—— 仍挂在 `docs/WEEKLY_AUDIT_2026-11-07.md`，优先级低于齿槽。
- 任何 S10（BOM/图纸）与 S11（评审报告重生成）新阶段推进 —— 齿槽不收敛，报告重生成没有意义。
- **判定纪律**：M8 未完成前，报告只能写「技能可用、设计不合格」，不得写「全部通过」。
