# ANSYS MaxWell_skill 设计流程完整性审计报告

> 审计日期：2026-07-29
> 审计对象：`D:\桌面\ANSYS MaxWell_skill`（SKILL.md v4.0）
> 审计方法：静态结构核对 + 运行时 DryRun 验证 + MCP 接口契约比对

---

## 一、总体结论

**完整性评分：约 72/100**

- ✅ **文档层 + MDAO 多物理场层：完整且已验证可运行**
- ❌ **驱动 ANSYS Maxwell 的电磁建模/仿真执行层：与 MCP Server 存在系统性接口断裂，端到端无法真实跑通**

---

## 二、已验证完整的部分（✅）

| 项目 | 证据 | 结论 |
|------|------|------|
| 文档体系 | SKILL.md 648行 + 6份reference共3077行 | 完整 |
| 脚本语法 | `py_compile` 全部 13个核心py + 11个项目脚本 | 无残缺、无语法错误 |
| MDAO 链路 | `test_mdao_chain.py` → Motor/IGBT key chain 全 **PASS** | 真实连通 |
| MDAO 运行 | `mdao_orchestrator.py motor/igbt` DryRun 跑通，结果落盘 JSON | 端到端可跑 |
| 自检命令 | `check` 优雅识别本机 Maxwell@21.1 / Fluent-Mechanical@v252，缺失依赖不崩溃 | 健壮 |
| 参数补全 | `motor_param_calc.py --power 500 --speed 3000 --json` 输出完整 JSON（10项校验全PASS） | 真实可用 |
| MCP 工具集 | server.py 含 **71个 @mcp.tool**，覆盖建模/材料/边界/激励/网格/求解/后处理 | 丰富 |
| 项目脚本 | 25Nm 项目 01~11 仿真脚本 + run_all 齐全 | 数量完整 |

---

## 三、发现的缺陷（❌）

### 缺陷1：几何建模 Phase 3 接口断裂（阻断性）

`projects/25Nm_PMSM/01_build_geometry.py` 直接裸调用以下函数（脚本仅 `from motor_config import *`，无本地定义）：

| 脚本调用 | server.py 现状 | 状态 |
|---------|--------------|------|
| `set_model_units("mm")` (L18) | **不存在** | 🔴 真缺口 |
| `duplicate_around_axis(...)` (L64, L90) | 仅有 `duplicate_object` | 🔴 真缺口（阵列槽/磁钢核心操作） |
| `subtract(...)` (L23,32,101,117,126) | 实为 `subtract_objects` | 🟡 命名不符 |

**后果**：Phase 3 构建 Maxwell 模型在真实 MCP 环境下会直接抛 NameError。

### 缺陷2：仿真脚本（02~11）MCP 接口系统性未对齐

约 15 个被项目脚本调用的工具名，在 server.py 的 71 个工具中**均不存在本地定义、也无对应**：

```
add_transient_setup      add_magnetostatic_setup   analyze_setup
assign_band             assign_mesh_skin_depth     create_winding_setup
draw_region_pad         duplicate_around_axis      export_data
get_field_data          get_induced_voltage       get_loss_data
set_magnet_orientation  set_model_units           subtract
```

- 其中部分为**命名不符**（server 有等价功能，名字不同）：
  - `subtract` ↔ `subtract_objects`
  - `assign_mesh_skin_depth` ↔ `assign_skin_depth_mesh`
  - `draw_region_pad` ↔ `create_region`
  - `add_transient_setup`/`add_magnetostatic_setup` ↔ `create_analysis_setup`
  - `analyze_setup` ↔ `analyze`/`analyze_all`
  - `assign_band` ↔ `assign_motion_setup`
- 部分为**功能确缺失**：`set_model_units`、`set_magnet_orientation`、`duplicate_around_axis`、`get_field_data`、`get_loss_data`、`get_induced_voltage`、`export_data`

### 缺陷3：SKILL.md 文档与实现不一致

- SKILL 工作流 Phase 1 写：`python scripts/motor_param_calc.py --power 500 --speed 3000 --auto --json`
- 实际脚本**不支持 `--auto` 参数**（报错 `unrecognized arguments: --auto`）。参数补全为默认行为，该 flag 冗余。

### 缺陷4：执行模式架构模糊（根因）

项目脚本同时混用两种调用范式，文档未澄清：
- **MCP 封装函数**：`draw_circle` / `draw_rectangle` / `assign_material` / `save_project`（非 Maxwell 原生 API）
- **Maxwell 原生 COM 方法**：`set_model_units` / `duplicate_around_axis` / `subtract`（IronPython 原生）

这导致：若脚本经 `run_script` 注入 Maxwell IronPython 执行，则 `set_model_units` 等原生方法合法，但 `draw_circle` 等 MCP 封装函数反而非法；若走逐 MCP 工具调用，则反之。两种模式都没有被完整满足。

---

## 四、修复建议

### 方案A：补齐 MCP Server（推荐，改动集中在 server.py）
1. 在 server.py 新增工具：`set_model_units`、`duplicate_around_axis`、`set_magnet_orientation`、`get_field_data`、`get_loss_data`、`get_induced_voltage`、`export_data`
2. 为兼容保留别名：`subtract`（→`subtract_objects`）、`assign_skin_depth_mesh`（→`assign_mesh_skin_depth`）等
3. 修正 SKILL.md 去掉 `--auto`

### 方案B：改写项目脚本（改动分散在 01~11）
将脚本调用的所有接口对齐到 server.py 已暴露的 71 个工具名（如 `create_analysis_setup` 替代 `add_transient_setup`、`create_region` 替代 `draw_region_pad`）。

### 方案C：明确执行模式（文档+轻量改造）
在 SKILL.md 明确：项目脚本统一走 `run_script` 注入 Maxwell IronPython，则 `set_model_units`/`duplicate_around_axis`/`subtract` 改为原生 API 调用，同时移除对 `draw_circle` 等 MCP 封装的依赖（改用 `oEditor.CreateCircle` 等）。

---

## 五、完整性矩阵

| 工作流阶段 | 状态 | 说明 |
|-----------|------|------|
| Phase0 输入评估 | ✅ | 逻辑清晰 |
| Phase1 参数自动补全 | ✅ | 实测可跑 |
| Phase2 多目标优化 | ✅ | motor_optimizer.py 存在 |
| Phase3 构建 Maxwell 模型 | ❌ | 3个接口断裂（缺陷1） |
| Phase4 运行仿真套件 | ❌ | 15个接口未对齐（缺陷2） |
| Phase5 生成报告 | ⚠️ | 依赖 Phase3/4 产出 |
| MDAO 多物理场链路 | ✅ | DryRun 实测 PASS |
| IGBT 可靠性链路 | ✅ | DryRun 实测 PASS |

---

*审计由 Torry 执行，所有"可跑"结论均基于本机 Python 3.13.14 DryRun 实测，未实际连接 ANSYS（需 Python 3.12 + PyAEDT/PyFluent 实算环境）。*
