# 文件清理报告 2026-11-23（每周清理，只清 TEMP）

> 触发：每周验收自动化（手动触发）。依据 `docs/FILE_LIFECYCLE.md` §4。
> 基线：HEAD `ae93bde`，工作树 1 改（`m2_noload_rect.json` 浮点尾数差异）+ `.workbuddy/` 未跟踪。
> 安全约束：无 `ansysedt.exe` 进程（仅 `ansyslmd.exe` license manager，PID 12492）；不碰 KEEP / ARCHIVE / git 跟踪文件 / `projects/results/**`；全部移到 `D:/ANSYS_Run/_trash_2026-11-23/` 留 7 天；每批 ≤20。

## 1. 判定口径

| 类 | 处置 | 本次命中 |
|---|---|---|
| KEEP（`projects/results/**`、账本/契约/报告/测试/脚本） | 绝不清理 | 全部跳过 |
| ARCHIVE（`archive/`、冻结 SPM 产物） | 只读不清理 | 全部跳过 |
| TEMP 空/失败产物、无引用试算脚本、孤立 `.lock` | 移 `_trash` 留 7 天 | 见 §2 |
| TEMP 但结论已迁 KEEP（bh_probe~7） | 移 `_trash`（证据已在 IPM 账本 I14 + 自动化 memory） | 见 §2 批 3 |
| TEMP 但被文档/任务引用 | **保留标 REVIEW** | 见 §3 |

## 2. 清理清单（移 `_trash_2026-11-23/`，4 批，每批 ≤20）

### 批 1 — 0 字节空日志（14 个）
`ansys_h.log`、`batchC.log`、`ipm_m1_stdout.log`、`m4_api_stdout.log`、`m4_band_stdout.log`、`m4_build_stdout.log`、`m4_export2_stdout.log`、`m4_export3_stdout.log`、`m4_export4_stdout.log`、`m4_export_stdout.log`、`m4_export_stdout2.log`、`m4_probe_stdout.log`、`runScript.log`、`variantA.log`
判定：无内容、无引用，空文件直接清。

### 批 2 — 无引用 BH/材料试算脚本与 ring 诊断（20 个）
`bh_keytest.log/.py`、`bh_keytest2.log/.py`、`bh_readback.log/.py`、`bh_ring.log`、`bh_ring_test.log/.py`、`clone_sig.log/.py`、`dirprobe.log/.py`、`matnames.log/.py`、`ring_A_edit.csv`、`ring_B_add.csv`、`ring_C_addnoperm.csv`、`ring_D_lin.csv`、`ring_pts.txt`
判定：grep 仓库 md/py/json 零引用，结论（ CloneMaterial 唯一可行）已入 IPM 账本 I14，可清。

### 批 3 — bh_probe~7 试算（19 个）
`bh_probe.py/.log/.aedt`、`bh_probe2.py/.log/.aedt`、`bh_probe3.py/.log/.aedt`、`bh_probe4.py/.log`、`bh_probe5.py/.log/.aedt`、`bh_probe6.py/.log`、`bh_probe7.py/.log/.aedt`
判定：被 I14 引用但**证据已迁移**（4 种 BH 写法静默丢弃 + `nonlinear` + `Points[66:]` 结论已写账本/自动化 memory），符合"先迁证据后清"。

### 批 4 — 早期 G3/dbg 诊断与孤立 lock（13 个）
`dbg_period.py`、`dbg_periodic.py`、`dbg_thd2.py`、`dbg_torque.py`、`diag_thd.py`、`g3_main.patch`、`g3_probe_api.log/.py`、`g3_run_generated_setup.log/.py`、`g3_stage_main.py`、`IPM_8p48s_M2_rect.aedt.lock`、`T4_g4b3.aedt.lock`
判定：早期数值调试脚本 + 无进程的残留 lock（无 ansysedt 进程，确认无占用），可清。

## 3. 保留（REVIEW / KEEP 前提，不清理）

| 路径 | 保留理由 |
|---|---|
| `projects/IPM_8p48s/TEMP/probe_mesh_api.py` | **本周新要求的关键前提**：网格 API 尚未真机探测（`D:/ANSYS_Run/probe_mesh_api.log` 不存在，MAXWELL_INTERNALS 无网格 API 结论）。任务约定"用完可清，但 log 的 API 结论须先写进 MAXWELL_INTERNALS 再清"，现探测未执行 ⇒ 必须保留供每日任务执行 |
| `D:/ANSYS_Run/before_*.py`（7 个） | 引用命中测试用例 `test_materials_before_geometry` 及 SPM 文档；保守标 REVIEW |
| `D:/ANSYS_Run/m1_probe.py/.log` | 被 `docs/MAXWELL_INTERNALS.md` / 周检报告引用（审计脚手架同源名）；保守标 REVIEW |
| `D:/ANSYS_Run/probe.py`、`probe_out.txt` | 早期报告探针，引用不确定 ⇒ REVIEW |
| 所有 `*.aedt`（除 bh_probe 系列）/`.aedtresults/`/`csv_*` | 求解工程与导出，CSV 证据未全部确认归档 ⇒ 本轮不动，仅清 `.lock` |
| `projects/results/**`（含全部 JSON/CSV） | KEEP 验收数据，任何情况不清理 |

## 4. 执行结果

- 实际移动 **66 个文件**（批 1=14 / 批 2=20 / 批 3=19 / 批 4=13），每批 ≤20。
- 目标：`D:/ANSYS_Run/_trash_2026-11-23/`（占用 636 KB），写入 `_README_KEEP_UNTIL.txt`：保留至 **2026-11-30** 后彻底删除。
- 核验：`projects/IPM_8p48s/TEMP/probe_mesh_api.py` 完好（网格探测前提）；`git status` 仅原有 1 改 + `.workbuddy/` + 本报告 3 项，无 git 跟踪文件被移动；`projects/results/**` 文件数 103 不变；无 ansysedt 进程存活。
- 释放：运行区根目录减少 66 个 TEMP（含 5 个 `bh_probe*.aedt` ≈ 160 KB 与 2 个孤立 `.lock`）。

## 5. fail 只增不减声明

本清理**不删除、不修改任何判据、账本 fail 行、报告或 `projects/results/**`**；仅移动 §2 列出的 TEMP 文件。`m2_noload_rect.json` 工作树浮点尾数差异（3e-6 V 量级）**未触碰、未提交**，留待下轮每日任务决定是否纳入。
