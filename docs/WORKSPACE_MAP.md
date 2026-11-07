# 工作区目录地图与归类规则

> 盘点日期：2026-11-07。目的：把多次迭代产生的一次性脚本按职责归类，减少"同名/同功能脚本散落"。
> 原则：**先建目录与地图，再按组迁移**；每次迁移是一个完整子步骤（含路径/import 修正 + pytest/ruff），不一次性搬空。

## 1. 当前盘点（125 个 `.py`）

| 目录 | `.py` 数 | 性质 | 处理 |
|---|---:|---|---|
| `scripts/` | 16 | skill 核心包（可安装） | **保留**，不动 |
| `projects/` | 33 | 25 N·m 设计 + Maxwell 脚本 | **按 design / maxwell / reports 归类** |
| `output_scripts/` | 47 | 生成的 Maxwell 脚本（多机型） | 保留；按机型子目录已分组 |
| `debug/` | 12 | AEDT/COM 离线检查器 | 保留；后续可并入 `tools/debug/` |
| `tests/` | 8 | 回归测试 | **保留**，不动 |
| `examples/` | 6 | 用法示例 | **保留**，不动 |
| `archive/` | 2 | 历史脚本 | 保留；只进不出 |
| `mcp-maxwell/` | 1 | MCP 服务 | 保留 |

### 重复检测（SHA-256）

- 完全重复仅 **4 组**：
  - `examples/__init__.py` 与 `tests/__init__.py`（均为空文件，正常）；
  - `output_scripts/36slot_industrial/{materials,setup,solver}.py` 与
    `output_scripts/36slot_v2/{materials,setup,solver}.py`（**同一套模板的共享样板**，不是误复制）。
- 结论：**没有需要清理的意外重复**；"杂乱"主要是一次性脚本数量多、职责未分层。

## 2. 目标目录结构

```text
scripts/                         # skill 核心包（pip install -e . 的包）
projects/
  25Nm_PMSM/
    pmsm_config.py               # 共享设计参数（保持在项目根，供各脚本 import）
    DESIGN_PROGRESS.md           # 阶段看板（每日任务维护）
    WEEKLY_GOALS.md              # 本周目标
    design/                      # 【目标】解析设计/热/NVH/敏感性
      sim_analytical.py
      thermal_analysis.py
      nvh_analysis.py
      sensitivity_design.py
      sensitivity_stack_turns.py
    maxwell/                     # 【目标】Maxwell 建模/求解/回填
      gen_maxwell_model.py
      ingest_fea.py
      maxwell_model/             # 现有 7+ 段生成脚本
      m2_*.py / m3_*.py          # 本次突破的实机脚本
    reports/                     # 【目标】报告生成
      make_report.py
      REPORT_25Nm_SPMSM.html
  results/                       # 所有 JSON/CSV/图（脚本统一写入这里）
output_scripts/                  # 生成物（按机型分组；不参与 import）
debug/                           # 离线 COM/AEDT 检查器
examples/ tests/ archive/ mcp-maxwell/
docs/
  MAXWELL_INTERNALS.md           # Maxwell 数据模型逆向记录
  WORKSPACE_MAP.md               # 本文件
```

## 3. 迁移规则（每日任务执行）

1. **一次只迁一组**：`design/` → `maxwell/` → `reports/`，每组迁移是一个完整子步骤（约 80–200 行改动）。
2. **路径修正**：脚本内 `HERE = Path(__file__).resolve().parent` 改为
   `ROOT = Path(__file__).resolve().parents[1]`（项目根），`RES = ROOT.parent / "results"`。
3. **import 修正**：`import pmsm_config` 前插入
   `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))`。
4. **验证**：迁移后必须运行该组脚本 + `pytest -q` + `ruff check`，通过才提交。
5. **不改生成物**：`output_scripts/` 不迁移、不参与 import；`scripts/` 包结构不动。
6. **不删除**：废弃脚本移入 `archive/`，不直接删。

## 4. 当前迁移状态

| 组 | 目标目录 | 状态 | 备注 |
|---|---|---|---|
| design | `projects/25Nm_PMSM/design/` | ⬜ 待迁移 | 5 个脚本；需改 `HERE/RES` 与 `pmsm_config` import |
| maxwell | `projects/25Nm_PMSM/maxwell/` | ⬜ 待迁移 | `gen_maxwell_model.py`、`ingest_fea.py`、`maxwell_model/` |
| reports | `projects/25Nm_PMSM/reports/` | ⬜ 待迁移 | `make_report.py` + HTML |
| debug | `tools/debug/`（可选） | ⬜ 待评估 | 需同步 ruff/mypy exclude |

> 迁移完成的判据：移动后脚本仍能复现既有数值，`pytest`/`ruff` 全绿，且 `DESIGN_PROGRESS.md` 记录新路径。
