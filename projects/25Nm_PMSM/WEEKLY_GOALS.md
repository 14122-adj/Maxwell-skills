# 本周目标（2026-11-07 起）

> 来源：`docs/WEEKLY_AUDIT_2026-11-07.md`（周检判定：**部分失败 / 条件可用**）
> 取 top 3，按优先级执行：做完 G1 再做 G2，依此类推。每日迭代任务每次仍只推进一小步。
> 纪律：每条完成后在 `DESIGN_PROGRESS.md` 记一行「产物路径 + 关键数值」，不得编造数字。

---

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

## G6 —【高优先｜M8】梨形槽与齿槽抑制（2026-11-14 用户指定）

| 项 | 内容 |
|---|---|
| 问题 | 当前定子槽是「窄口 + 梯形/矩形」的近似，齿槽峰峰值 **6.843 N·m（27.37%）** 远超 5% 判据；用户给出表 2 梨形槽尺寸，要求按此改造。 |
| 尺寸 | `Bs0=0.8`、`Hs0=1.5`、`Hs1=1.8`、`Hs2=12.5`、`Bs1=6.0`、`Bs2=9.5`（`Rs=4.75`）；`Hs2` 按「内径→槽底最底端」总深。 |
| 验收标准 | ① 模板 `_gen_geometry` 的 `pear` 分支按本尺寸生成，槽面积 **93.0±2%**、线圈 **72±5%**、无 `intersect`；② 真机空载 401 点，BEMF 与基线 **118.8832 V** 偏差 ≤10%；③ 齿槽峰峰值 ≤6.843 N·m（目标 **≤1.25 N·m / 5%**）；④ 负载 `T_avg` 仍 ±20%；⑤ pytest/ruff 全绿、模板/生成物 `--check` 无漂移。 |
| 对应阶段 | **M8**（齿槽优化第一刀）；M7 模板负载顺延 |
| 关联 | 表 2、图 1-1；`docs/PEAR_SLOT_SPEC.md`；FEA 基线 6.84307 N·m |

## 排期建议（Maxwell 优先，明天起）

| 日 | 动作 | 完成判据 |
|---|---|---|
| D1 | G3 代码层：`_gen_setup()` 注入 `ModelDepth` + `validate()` 断言 | ✅ 完成 2026-11-11（`G3_depth160/180` + `G3_generated_setup.aedt`） |
| D2 | G4/M1：`ansysedt -RunScriptAndExit` 最小脚本 | ✅ 完成（`M1_min.aedt`） |
| D3 | G5/M2：25 N·m 几何在 Maxwell 中生成 | ✅ 完成（`M2_25Nm.aedt`，24 图元） |
| D4 | M3：材料/绕组/Band/边界/Setup | ✅ 完成（`M4_25Nm.aedt`：12×Coil、3×Winding、160mm、M270、VP、Setup1） |
| D5 | **M4：空载瞬态** | ✅ 完成（401 点全时长解，BEMF 118.8832 V，齿槽 6.84307 N·m） |
| D6 | M5：负载瞬态 | ✅ 完成（`T_avg` 22.3344 N·m，−10.66%） |
| D7 | M6 + 周检复跑 | ✅ 完成（`fea_results.json` 进报告 §11） |
| D8 | **G3b：4 处真机 API 修复回灌模板** | 重跑 `gen_maxwell_model.py` 后 `TestModelerApiRegressions` 仍全绿（下一步） |

## 明确不在本周范围

- P4（未知参数静默丢弃）、P5（`WINDING_KW=0.933` vs 真值表 0.866）、P6（`T_avg` 回填额定值）—— 已记录在审计报告，排 G1–G3 之后。
- 任何 S10（BOM/图纸）新阶段推进。
