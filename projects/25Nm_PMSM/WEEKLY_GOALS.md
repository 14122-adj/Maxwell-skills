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

| 项 | 内容 |
|---|---|
| 问题 | `stack_length`（25 N·m 机型 = 160 mm）从未被任何生成器消费：`main.py` 生成的 `setup.py` 与 `maxwell_model/solve_25Nm_SPMSM.py` 的 `SetDesignSettings` 都只设 `PreserveTransientSolution`/`ComputeTransientInductance`，**不含 `ModelDepth`**；全仓 121 个 `.py` 中 `ModelDepth` 仅出现在 `debug/` 三个读取器里。Maxwell 2D 默认模型深度 1 mm，实跑转矩、铁耗、反电势幅值将整体低估 ≈160×。 |
| 验收标准 | ① `scripts/main.py` 生成的 `setup.py` 内含 `ModelDepth:="160mm"`（随 `--params stack_length=` 变化，非硬编码）；② `maxwell_model/solve_25Nm_SPMSM.py` 同样设置；③ 回归校验：生成物 `grep -c ModelDepth ≥ 1`，`MotorConfig.validate()` 断言 `stack_length > 0`；④ 桌面会话实跑后，`ingest_fea.py` 回填的 `T_avg` 与解析值 25 N·m 同量级（±20%），否则视为本目标未达成。 |
| 建议对应阶段 | **S6**（FEA 实跑与结果回填；沙箱无法实跑，脚本与校验先落地并标 blocked） |
| 关联审计项 | P3（`main.py:903`、`solve_25Nm_SPMSM.py:65-67`） |

---

## 排期建议（明天起，每天一小步）

| 日 | 动作 | 完成判据 |
|---|---|---|
| D1 | G1：`motor_config.py` 加几何派生 + 哨兵默认值 | `main.py --params "…stator_id=93"` rc=0，RotorOuter=46.125 |
| D2 | G1：补 `tests/test_motor_config.py` 三例 + 跑 pytest/ruff | 147+3 全绿，ruff 无新增告警 |
| D3 | G2：依赖声明 + SKILL.md 前置说明 | 干净 venv 一路 rc=0 出 HTML |
| D4 | G2：`make_report.py` ImportError 中文提示 + P7 转义修复 | 缺包时报错可读，`-W error::SyntaxWarning` 无告警 |
| D5 | G3：`_gen_setup()` 注入 `ModelDepth` | 生成物 grep 命中，`stack_length` 可配 |
| D6 | G3：`solve_25Nm_SPMSM.py` 同步 + 校验脚本 | 两处 `ModelDepth` 落地，标注待桌面执行 |
| D7 | 周检复跑（下周），确认 G1–G3 关闭 | 判定由「部分失败」升为「可用」 |

## 明确不在本周范围

- P4（未知参数静默丢弃）、P5（`WINDING_KW=0.933` vs 真值表 0.866）、P6（`T_avg` 回填额定值）—— 已记录在审计报告，排 G1–G3 之后。
- 任何 S10（BOM/图纸）新阶段推进。
