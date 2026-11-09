# Changelog

All notable changes to **ansys-maxwell-motor** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
