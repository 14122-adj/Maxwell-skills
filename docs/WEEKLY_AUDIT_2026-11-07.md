# 周检报告 — ANSYS Maxwell Skill「从零可用性」验收

**审计日期**：2026-11-07 14:07–14:15（GMT+8）
**审计方式**：手动触发的一次性周检（非自动运行）
**代码基线**：`b2a8c4c`（2026-11-07 13:09，`feat(motor): S9 敏感性第二小步`）**+ 9 个未提交的工作树改动**
**干净环境**：`D:\ANSYS_Run\audit_20261107\`（新建 venv，不复用任何已有生成物）
**Python**：`C:/Users/ASUS/.workbuddy/binaries/python/versions/3.13.12/python.exe`（实际 `Python 3.13.14`）
**FEA 实跑**：环境限制（沙箱无 AEDT 桌面会话），不计入可用性判定，仅做语法/接口/物理设置审查

---

## 1. 总览

| # | 检查项 | 结果 | 严重级别 | 证据（复现命令 → 期望/实测） |
|---|--------|------|----------|------------------------------|
| 1 | 仓库完整性 | ✅ PASS | — | `SKILL.md` 44,300 B / `scripts/main.py` 40,857 B / `scripts/motor_config.py` 19,746 B / `pyproject.toml` 8,517 B / `tests/` 4 文件，全部存在 |
| 2 | 依赖与安装 | ⚠️ PARTIAL | **blocker** | `pip install -e .` rc=0（11.4 s，含 pyyaml）；但 `pytest` / `matplotlib` / `numpy` 均未装，报告链路直接断（见 P2） |
| 3 | 单元测试 | ✅ PASS | — | `python -m pytest -q` → **147 passed, 0 failed**，2.31 s |
| 4 | 从头建模 | ❌ FAIL | **blocker** | 首跑 `main.py --params "…stator_id=93"` → rc=1「转子外径必须小于定子内径」；显式补 `rotor_od` 后 rc=0，7 脚本 `py_compile` 全通过、零硬编码绝对路径 |
| 5 | 从头仿真 | ✅ PASS（1 项存疑） | major | `sim_analytical.py` rc=0，380 ms，生成 `sim_summary.json`；Bg 0.776 T ✓、η 93.87% ✓、B_min 0.627 T ✓、T 25.0 N·m ⚠（回填额定值，见 P6） |
| 6 | 报告链路 | ⚠️ PARTIAL | **blocker** | 裸环境 `make_report.py` → rc=1 `ModuleNotFoundError: matplotlib`；补装后 rc=0，2.6 s，HTML 230,384 B、内嵌 5 图、12 表 |
| 7 | FEA 能力（语法/接口） | ⚠️ FAIL（物理设置） | major | `solve_25Nm_SPMSM.py`、`ingest_fea.py` `py_compile` rc=0；但两脚本 **均未设置 2D `ModelDepth`**，160 mm 叠长丢失（见 P3）；标注「需在桌面会话执行」 |
| 8 | 文档一致性 | ❌ FAIL | major | `SKILL.md` 对 `sim_analytical` / `make_report` / `ingest_fea` / `solve_25Nm` 命中 **0 次**；「2 参数自动补全」承诺在 `main.py` 入口未兑现（P4）；`run_all_simulations.py` 输出指向库外路径（P8） |

**耗时汇总**：安装 55.4 s + 测试 3.3 s + 建模/仿真/报告 ≈ 4.9 s + 静态检查 ≈ 2 s，总 ≈ 66 s。详细秒数见 `weekly_audit.json`。

---

## 2. 详细问题

### P1 —【blocker】`rotor_od` 写死 135.6，小机型从零建模 100% 失败

- **文件/行**：`scripts/motor_config.py:117`（`rotor_od: float = 135.6`）、`scripts/motor_config.py:186-190`（`__post_init__` 只算派生电磁量，不推导几何）
- **复现**：

```bash
cd D:/ANSYS_Run/audit_20261107
venv/Scripts/python.exe "D:/桌面/ANSYS MaxWell_skill/scripts/main.py" \
  --params "slots=12 poles=8 stator_od=150 stator_id=93 slot_type=pear" \
  --output_dir D:/ANSYS_Run/audit_20261107/gen
```

- **实测**：rc=1，stderr 空，stdout：

```
  定子: 150mm / 93mm
  转子: 135.6mm / 48.0mm      ← 转子外径仍为 36slot 预设值
ERROR: 转子外径必须小于定子内径
```

- **根因**：`MotorConfig` 的 `rotor_od=135.6` / `airgap=0.2` 是 `36slot_industrial` 预设的常量，被当成 dataclass 默认值；`create_motor_from_input()` → `MotorConfig.from_dict()` 只做键过滤，**不做 `rotor_od = stator_id - 2·airgap` 的派生**，也从不按 SKILL.md §1「δ=0.3+Dso/400」推导气隙。凡 `stator_id < 135.6 mm` 的机型（即绝大多数中小型电机）必然失败。
- **影响面**：25 N·m 项目本体（Dsi=93）走 `main.py` 入口必然失败；只有把参数硬写成 210/136 这类"恰好匹配默认值"的例子才通得过——`main.py` docstring 里的示例正是这种巧合。
- **修复建议**：在 `__post_init__` 中做几何自洽：若 `rotor_od` 未显式给出（`None` 哨兵）→ `airgap = clamp(0.3 + stator_od/400, 0.35, 2.0)`，`rotor_od = stator_id - 2*airgap`；`validate()` 保留冲突检查。补 `tests/test_motor_config.py` 覆盖 Dsi<135.6 / Dsi>135.6 / 显式 rotor_od 三种路径。

### P2 —【blocker】报告链路依赖未声明，干净环境装完包仍跑不通

- **文件/行**：`pyproject.toml:49-51`（`dependencies = ["pyyaml>=6.0"]`，`matplotlib` 仅出现在 `[plot]` extra 第 63 行）；`projects/25Nm_PMSM/make_report.py:17-19`（`import matplotlib` / `numpy`）；`projects/25Nm_PMSM/ingest_fea.py:10`（`import numpy as np`）
- **复现**：

```bash
venv/Scripts/python.exe -m pip install -e "D:/桌面/ANSYS MaxWell_skill"
venv/Scripts/python.exe "D:/桌面/ANSYS MaxWell_skill/projects/25Nm_PMSM/make_report.py"
```

- **实测**：rc=1，stderr 摘要：

```
make_report.py:411: SyntaxWarning: invalid escape sequence '\P'
  File "…/make_report.py", line 17, in <module>
    import matplotlib
ModuleNotFoundError: No module named 'matplotlib'
```

  同理 `python -m pytest -q` → `No module named pytest`（pytest 只在 `[dev]` extra 中）。
- **根因**：`matplotlib` / `numpy` 被归入 `[project.optional-dependencies].plot`，但 SKILL.md 与项目 README 均未提示"跑报告需先装 [plot]"；`pytest` 同理。安装成功的 11.4 s 给人"环境已就绪"的错觉。
- **修复建议**（二选一）：① 把 `numpy>=1.26`、`matplotlib>=3.7` 移入 `dependencies`（代价：安装体积 ↑ 约 60 MB）；② 保留 optional，但在 SKILL.md 增加一行硬性前置：`pip install -e ".[plot,dev]"`，并让 `make_report.py` 在 `ImportError` 时抛出中文可读提示而非裸栈。

### P3 —【major】`stack_length` 从未被消费，Maxwell 2D 叠长丢成默认值（FEA 结果差 160×）

- **文件/行**：`scripts/main.py`（无任何一层用 `config.stack_length`；仅 `main.py:903` 交互模式赋值）；生成物 `gen/setup.py:46` 只设 `PreserveTransientSolution` / `ComputeTransientInductance`；`projects/25Nm_PMSM/maxwell_model/solve_25Nm_SPMSM.py:65-67` 同样缺 `ModelDepth`
- **证据**：全仓 121 个 `.py` 中 `ModelDepth` 只出现在 `debug/aedt_parser.py`、`debug/com_extractor.py`、`debug/run_debug.py`（**纯读取器**），零个生成器/求解器设置它；仓库内唯一一份存档工程 `output_scripts/36slot_industrial_motor.aedt:248` 里 `ModelDepth='1meter'`，说明该参数一旦不设就沿用软件默认。
- **实测**：`gen/geometry.py` 全为 XY 平面圆/多段线（2D），无 `ZPosition`、无 `160`；`--params "… stack_length=160"` 被接受但**无任何表现**。
- **后果**：Maxwell 2D 默认模型深度 1 mm，而设计叠长 160 mm —— 一旦在桌面会话实跑，转矩、铁耗、反电势幅值全部低估约 160 倍，S6 回填数据将不可用。这是"脚本合法但物理错"的隐性缺陷，比崩溃更危险。
- **修复建议**：`_gen_setup()` 增加 `oDesign.SetDesignSettings(["NAME:DesignSettingsData", "ModelDepth:=", f"{c.stack_length}mm", …])`；`solve_25Nm_SPMSM.py` 同步；加一条回归校验（生成物 `grep -c ModelDepth >= 1`），并在 `validate()` 中断言 `stack_length > 0`。

### P4 —【major】未知参数静默丢弃，`power`/`speed` 输入产出错误机型且 rc=0

- **文件/行**：`scripts/motor_config.py:from_dict()`（`filtered_data = {k:v for k,v in data.items() if k in valid_fields}`，无告警）
- **复现**：

```bash
venv/Scripts/python.exe "D:/桌面/ANSYS MaxWell_skill/scripts/main.py" \
  --params "power=500 speed=3000" --output_dir D:/ANSYS_Run/audit_20261107/gen_power
```

- **实测**：rc=0，「脚本生成成功」，耗时 494 ms；生成物 `geometry.py` 的定子外半径 **105.0 mm**（210/2，即 dataclass 默认机），槽极 12s/8p —— 与输入的 500 W / 3000 rpm 毫无关系，且**无一行警告**。
- **根因**：SKILL.md §1 承诺「最少输入 2 个参数（功率+转速）即可自动推导全部参数」，其实现位于**另一个**入口 `scripts/motor_param_calc.py`；`main.py` 从不调用它，也不校验键名。
- **修复建议**：`from_dict()` 对未识别键抛 `ValueError`（列出可用键）；或 `main.py` 检测到 `power`/`speed` 时先转 `motor_param_calc` 派生再建模。文档上把"自动补全"明确标注为 `motor_param_calc.py` 的能力，不要把 `main.py` 写成两参数入口。

### P5 —【major】`WINDING_KW=0.933` 与真值表 0.866 冲突，齿磁密被低估 7.7%

- **文件/行**：`projects/25Nm_PMSM/pmsm_config.py:66`（`WINDING_KW = 0.933`）
- **冲突对象**：`scripts/winding_layout.py 12 8 --list` 输出 `source=canonical (k_w=0.866)`；`references/winding_layouts.md §3` 亦为 0.866（0.933 是 **10p/12s** 的值，疑似串行复制）
- **量化**（同一 E=132.4 V、N=81、f=100 Hz）：

| k_w | 每极磁通 φ | Bg | 齿磁密 | T_calc |
|---|---|---|---|---|
| 0.933（现状） | 3.946 mWb | 0.776 T | 1.651 T | 22.53 N·m |
| 0.866（真值表） | 4.251 mWb | **0.836 T** | **1.779 T** | 22.53 N·m |

- **后果**：Bg 仍在 0.7–0.9 带内（迷惑性强），但齿磁密由"刚好压在 Bsat 1.65 T"变为"超 Bsat 8%"，即设计实际饱和而报告显示未饱和；`DESIGN_PROGRESS.md`、`REPORT.md` 的 S4 基线随之系统性偏乐观。转矩不受影响（φ 与 k_w 在 `lam_pm` 中相消）。
- **修复建议**：改为 0.866 并按 P5 表格重跑 S4，同步更新 DESIGN_PROGRESS 基准表；`validate()` 增加断言 `abs(kw - canonical_kw(12,8)) < 1e-3`。

### P6 —【major】额定转矩自检循环：`T_avg` 直接回填输入

- **文件/行**：`projects/25Nm_PMSM/sim_analytical.py:130`（`T_avg=T_rated`）
- **实测**：`sim_summary.json` → `T_avg=25.0`（= 输入），`T_calc=22.53`（真实算出来的，偏低 **9.9%**）。验收清单里「转矩≈25 N·m」这一项因此是恒真的，不具备鉴别力。
- **修复建议**：`T_avg` 改为 `T_calc`（或 `0.95·T_calc` 计入端部/谐波折减）并保留 `T_rated` 作为目标值；把 22.5 vs 25 的 10% 缺口转成设计动作（匝数 81→88 或叠长 160→176），而不是用回填掩盖。报告里 `T_avg` 与 `T_calc` 需分列并标注口径。

### P7 —【minor】`make_report.py:411` 非法转义，未来 Python 版本将报 SyntaxError

- **文件/行**：`projects/25Nm_PMSM/make_report.py:411` — 普通字符串内含 `D:\Program Files\AnsysEM\...`，`\P` 触发 `SyntaxWarning: invalid escape sequence '\P'`。
- **修复**：该行加 `r` 前缀或 `\\`。同时该行文案硬编码「Maxwell 2021 R1 已安装…许可证 localhost:1055」，与运行机实际状态无关，建议改为动态探测结果。

### P8 —【minor】编排脚本日志输出指向库外不存在的路径；dry_run 13 步「全 PASS」无产物

- **文件/行**：`projects/25Nm_PMSM/run_all_simulations.py:113,121`（`log(f"Output: {EXPORT_DIR}")`）
- **实测**（沙箱内 `MAXWELL_DRY_RUN=1`，rc=0，498 ms）：末行 `Output: D:/桌面/maxwell-motor-25Nm/results/` —— 该目录**不存在**，是历史遗留的库外路径；13 个 Step 全部 `PASS`，但耗时 0.1 s、无任何文件落盘。
- **修复建议**：`EXPORT_DIR` 改为相对 `projects/results` 解析；dry_run 时把 `PASS` 改标 `MOCK`，避免"全绿"误读。

### P9 —【minor】生成物头部注释 `q=1.00` 与实际 0.50 不符

- **文件/行**：`scripts/main.py` 的 `_gen_winding()` 模板（生成物 `gen/winding.py:12` 打印 `slots=12 poles=8 q=1.00`，同文件 `winding_report.txt` 为 `q: 0.50`）。
- **修复**：改用 `{c.q:.2f}` 插值，并把「整数槽分布式 Pyrhonen 公式」的注释在集中绕组分支改为对应算法说明（当前注释与代码路径不匹配，易误导后人改相位）。

### P10 —【minor】报告图表缺 CJK 字形，个别字符渲染为空框

- **实测**：`make_report.py:48/52` 抛 `UserWarning: Glyph 38408 (█) / 20540 (值) missing from font(s) DejaVu Sans`；抽查 `cross_section.png`、`torque.png` 正文为英文/ASCII 正常，含中文或方块符号的标注会出现豆腐块。
- **修复**：`matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei"]` + `axes.unicode_minus=False`。

### P11 —【minor】审计基线含 9 个未提交改动

- `git status --short`：`M SKILL.md`、`M mcp-maxwell/server.py`、`M output_scripts/36slot_industrial/winding.py`、`M output_scripts/36slot_v2/coils.py`、`M output_scripts/36slot_v2/winding.py`、`M references/motor_design_guide.md`、`M scripts/main.py`、`M scripts/maxwell_bridge.py`、`M scripts/motor_param_calc.py`、`M scripts/winding_layout.py`、`?? output_scripts/36slot_industrial/coils.py`。
- 本次结论对**工作树**有效，不能仅凭 `b2a8c4c` 复现。建议周检前先清理或提交工作树，否则"基线"漂移。

### P12 —【minor】测试只覆盖绕组，建模/配置链路零回归防护

- 147 个用例全部落在 `tests/test_winding_layouts.py` / `test_pmsm_winding_builder.py` / `test_winding_layout_cli.py`；`MotorConfig` 派生、`main.py` 几何输出、`make_report.py` 均无用例 —— P1 / P4 / P3 这类缺陷因此可以长期存活。

---

## 3. 通过项的硬证据

| 项 | 证据 |
|---|---|
| 包安装与入口 | `pip install -e .` rc=0；`maxwell-build.exe / maxwell-winding.exe / maxwell-test.exe` 三个 console script 生成；`maxwell-build --help` rc=0（579 ms，异地 cwd 可用） |
| 测试 | `147 passed in 2.31s`，rc=0，无 xfail/skip |
| 建模脚本合法性 | 7 个生成脚本 `py_compile` 全 rc=0；`re` 扫描 `[A-Za-z]:\` 绝对路径 → **0 命中** |
| 几何与输入一致 | 显式给参后：`StatorOuter 75.0`（150/2 ✓）、`StatorInner 46.5`（93/2 ✓）、`RotorOuter 45.825`（91.65/2 ✓）、`Shaft 24.0`（48/2 ✓）、PM 环 `range(8)` ✓、线圈 `range(12)` ✓、槽阵列 `DuplicateAroundAxis` ✓；**唯叠长 160 未体现**（P3） |
| 解析仿真可复现 | 沙箱空 results 目录 → 380 ms 生成 `sim_summary.json` / `airgap_flux_density.csv` / `no_load_bemf.csv`；数值与 `DESIGN_PROGRESS.md` 既有基线**逐项一致**（0.776 T / 25.0 N·m / 93.87% / 2.52 mH / 0.454 N·m 齿槽） |
| 报告链路（补依赖后） | rc=0，2.65 s，`REPORT_25Nm_SPMSM.html` 230,384 B，`data:image/png;base64` ×5、`<img src=` ×5、`<table>` ×12 |
| FEA 脚本语法/接口 | `solve_25Nm_SPMSM.py`、`ingest_fea.py`、`gen_maxwell_model.py`、`run_all_simulations.py` 全部 `py_compile` rc=0；`ansysedt.exe` 存在于 `D:\Program Files\AnsysEM\AnsysEM21.1\Win64\`；实跑需桌面会话（本沙箱 rc=1，环境限制，不计缺陷） |

---

## 4. 结论

**判定：部分失败（条件可用）—— 不满足「零配置从零建模 + 仿真 + 报告」的完整口径。**

- **可用部分**：包安装、147 项单测、解析仿真链路（可复现既有基线）、HTML 报告生成、生成脚本语法与路径卫生。仅"给全参数（含 `rotor_od`）+ 手工补装 matplotlib"时，全链路能从零跑通并产出 230 KB 自带图表的报告。
- **不可用部分**：① 小机型（`stator_id < 135.6`）走标准入口必然失败，`main.py` 的"2 参数自动补全"实为隐式默认机；② 干净环境装包后报告链路直接断在 `import matplotlib`；③ 生成模型与 FEA 脚本都不设 2D `ModelDepth`，叠长 160 mm 丢失，S6 一旦实跑将得到低 160 倍的结果。
- **对「从零建模 + 仿真」的直接回答**：**当前不可用**，需先修 P1、P2 两个 blocker；P3 决定 FEA 数据能否采信。

**本周目标（top 3）已写入 `projects/25Nm_PMSM/WEEKLY_GOALS.md`**：G1=P1（blocker）、G2=P2（blocker）、G3=P3（major，S6 前置）。

---

## 5. 复现脚本（整包重跑）

```bash
PY=C:/Users/ASUS/.workbuddy/binaries/python/versions/3.13.12/python.exe
ROOT="D:/桌面/ANSYS MaxWell_skill"
AUDIT=D:/ANSYS_Run/audit_20261107

"$PY" -m venv "$AUDIT/venv"
"$AUDIT/venv/Scripts/python.exe" -m pip install -e "$ROOT"          # rc=0, 11.4s
"$AUDIT/venv/Scripts/python.exe" -m pip install pytest matplotlib numpy
cd "$ROOT" && "$AUDIT/venv/Scripts/python.exe" -m pytest -q          # 147 passed

# 从零建模（P1 复现 → rc=1）
"$AUDIT/venv/Scripts/python.exe" "$ROOT/scripts/main.py" \
  --params "slots=12 poles=8 stator_od=150 stator_id=93" --output_dir "$AUDIT/gen"

# 从零仿真（需先复制 projects/25Nm_PMSM + scripts 到空目录，或接受写入 projects/results）
"$AUDIT/venv/Scripts/python.exe" "$ROOT/projects/25Nm_PMSM/sim_analytical.py"
"$AUDIT/venv/Scripts/python.exe" "$ROOT/projects/25Nm_PMSM/make_report.py"
```
