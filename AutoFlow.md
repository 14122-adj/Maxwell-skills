# ANSYS Maxwell 电机设计全流程自动化操作手册
> **适用工具：** Claude（通过 MCP）/ Codex（通过 API）  
> **仿真软件：** ANSYS Maxwell 2024 R1+  
> **文档版本：** v1.0 | 2026-06-17  
> **作者：** 基于 Maxwell MCP Server 生成

---

## 目录

1. [流程总览](#1-流程总览)
2. [阶段一：参数需求定义](#2-阶段一参数需求定义)
3. [阶段二：参数自动计算与验证](#3-阶段二参数自动计算与验证)
4. [阶段三：几何建模](#4-阶段三几何建模)
5. [阶段四：材料定义与分配](#5-阶段四材料定义与分配)
6. [阶段五：绕组与激励设置](#6-阶段五绕组与激励设置)
7. [阶段六：边界条件与网格设置](#7-阶段六边界条件与网格设置)
8. [阶段七：求解配置与仿真运行](#8-阶段七求解配置与仿真运行)
9. [阶段八：结果提取与报告生成](#9-阶段八结果提取与报告生成)
10. [完整 Prompt 模板（Claude / Codex）](#10-完整-prompt-模板)
11. [MCP 工具调用速查表](#11-mcp-工具调用速查表)
12. [常见问题排查](#12-常见问题排查)

---

## 1. 流程总览

```
用户输入参数需求
      │
      ▼
[阶段一] 参数需求定义
  - 电机类型选择（PMSM / BLDC / SRM / 感应电机）
  - 额定功率、转速、电压、效率目标
  - 外形约束（外径、轴向长度、质量）
      │
      ▼
[阶段二] 参数自动计算
  - 气隙磁密、线圈匝数、槽满率等初始设计值
  - Claude/Codex 生成完整参数表
      │
      ▼
[阶段三] 几何建模 ──→ Maxwell MCP: draw_rectangle / draw_circle / draw_line
  - 定子槽、转子铁心、永磁体、气隙
      │
      ▼
[阶段四] 材料定义 ──→ Maxwell MCP: assign_material / add_custom_material
  - 铁心硅钢片（M270-35A）
  - 永磁体（N35 / N48SH）
  - 绕组铜导线
      │
      ▼
[阶段五] 激励设置 ──→ Maxwell MCP: assign_coil / assign_winding / assign_current_source
  - 三相绕组拓扑
  - 电流幅值/相位
      │
      ▼
[阶段六] 边界与网格 ──→ Maxwell MCP: assign_vector_potential / assign_master_slave
  - 对称边界
  - 气隙细化网格
      │
      ▼
[阶段七] 求解运行 ──→ Maxwell MCP: add_solution_setup / run_simulation / run_script
  - 瞬态/静磁场/涡流分析
      │
      ▼
[阶段八] 结果提取 ──→ Maxwell MCP: create_report / get_solution_data
  - 转矩、磁通密度、铁损、铜损报告
      │
      ▼
输出：仿真报告 + 参数对比表
```

---

## 2. 阶段一：参数需求定义

### 2.1 用户需求输入模板

在与 Claude / Codex 对话时，建议按以下结构化格式描述需求：

```
电机类型：    [PMSM / BLDC / SRM / 感应电机]
额定功率：    [W / kW]
额定转速：    [rpm]
直流母线电压：[V]
相数：        [3]
极对数 p：    [整数]
槽数 Q：      [整数]
效率目标：    [%]（可选）
功率因数：    [0.0–1.0]（可选）
外径限制：    [mm]
内径（气隙）：[mm]（可选，若未知让 AI 计算）
轴向长度：    [mm]
工作温度：    [°C]
冷却方式：    [自然冷却 / 水冷 / 强制风冷]
```

### 2.2 示例需求

```
电机类型：    表贴式永磁同步电机（SPMSM）
额定功率：    500 W
额定转速：    3000 rpm
直流母线电压：48 V（三相桥逆变器供电）
相数：        3
极对数 p：    4（8 极）
槽数 Q：      12（8 极 12 槽集中绕组）
效率目标：    ≥ 88%
功率因数：    ≥ 0.90
外径限制：    80 mm
轴向长度：    50 mm
工作温度：    80 °C 连续
冷却方式：    自然冷却
```

---

## 3. 阶段二：参数自动计算与验证

### 3.1 发送给 Claude / Codex 的计算 Prompt

```
你是一位电机设计专家，请根据以下需求参数，计算出完整的 SPMSM 电机设计参数表。
要求：
1. 计算气隙磁密 Bg（目标 0.7~0.85 T）
2. 计算每相匝数 N、每槽导体数 Ns
3. 计算槽满率 Kf（目标 < 0.45）
4. 计算磁极弧度角 αp（目标 0.85~0.92）
5. 计算永磁体厚度 hm
6. 输出完整参数表（含单位），并指出任何超出合理范围的参数

需求：
- 额定功率 500 W，转速 3000 rpm，48 V 母线
- 外径 80 mm，轴向长度 50 mm
- 8 极 12 槽，绕组因数约 0.933
- 硅钢片 M270-35A，永磁体 N35（Br=1.17 T，Hc=880 kA/m）
```

### 3.2 期望输出的参数表格（Claude 应生成如下格式）

| 参数 | 符号 | 数值 | 单位 | 备注 |
|------|------|------|------|------|
| 定子外径 | Dso | 80 | mm | 约束值 |
| 定子内径（气隙处） | Dsi | 52 | mm | 计算值 |
| 转子外径 | Dro | 50.8 | mm | 留 0.6 mm 气隙 |
| 气隙长度 | δ | 0.6 | mm | 经验值 |
| 轴向长度 | La | 50 | mm | 约束值 |
| 极弧系数 | αp | 0.87 | — | 0.85~0.92 推荐 |
| 永磁体厚度 | hm | 4.0 | mm | 计算值 |
| 定子槽数 | Q | 12 | — | 设计值 |
| 极对数 | p | 4 | — | 设计值 |
| 每相匝数 | N | 60 | 匝 | 计算值 |
| 每槽导体数 | Ns | 40 | 导体 | 计算值 |
| 导线规格 | — | φ0.8 mm | mm | AWG21 |
| 槽满率 | Kf | 0.42 | — | < 0.45 ✓ |
| 气隙磁密 | Bg | 0.78 | T | 0.7~0.85 T ✓ |
| 额定电流（有效值）| Irms | 12.5 | A | 计算值 |
| 绕组因数 | Kw | 0.933 | — | 8p12s 集中绕组 |
| 额定转矩 | Tn | 1.59 | N·m | P/ω |
| 预估效率 | η | 89.2 | % | 满足目标 |

---

## 4. 阶段三：几何建模

### 4.1 建模流程（Claude 调用 MCP 的完整步骤）

**Step 1：连接 Maxwell 并新建项目**

```python
# MCP 调用序列（Claude 发出）
connect_to_maxwell()
new_project()
new_design(design_name="SPMSM_8p12s", solution_type="Transient")
```

**Step 2：绘制定子铁心外轮廓**

```python
# 定子外圆
draw_circle(
    name="Stator_Outer",
    x_center=0, y_center=0,
    radius=40  # 外径 80mm 半径 40mm
)

# 定子内圆（气隙面）
draw_circle(
    name="Stator_Inner",
    x_center=0, y_center=0,
    radius=26  # 内径 52mm 半径 26mm
)
```

**Step 3：绘制定子槽（单槽后阵列）**

```python
# 绘制单个定子槽矩形近似（简化模型）
draw_rectangle(
    name="Slot_1",
    x_start=-2.5, y_start=26,
    width=5, height=12  # 槽宽 5mm，槽深 12mm
)

# 通过 run_script 执行阵列操作（12 槽均布）
run_script(script="""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.GetActiveDesign()
oEditor = oDesign.SetActiveEditor("3D Modeler")
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", 
     "CreateNewObjects:=", True, "WhichAxis:=", "Z",
     "AngleStr:=", "30deg", "Numclones:=", "12"]
)
""")
```

**Step 4：绘制转子铁心**

```python
draw_circle(
    name="Rotor_Core",
    x_center=0, y_center=0,
    radius=25.4  # 转子外径 50.8mm
)

draw_circle(
    name="Shaft",
    x_center=0, y_center=0,
    radius=10   # 轴径 20mm
)
```

**Step 5：绘制永磁体（表贴，8 块均布）**

```python
# 单块永磁体（弧形近似用矩形，后期可改弧形）
draw_rectangle(
    name="PM_1",
    x_start=-5.5, y_start=21.4,
    width=11, height=4  # 宽约 11mm，厚 4mm
)

# 阵列 8 块（45° 间隔）
run_script(script="...极弧阵列脚本...")
```

### 4.2 建模注意事项

| 注意点 | 说明 |
|--------|------|
| 坐标系 | Maxwell 默认 XY 平面，Z 为轴向，2D 模型在 XY 截面建立 |
| 单位 | 默认 mm，提前用 `SetModelUnits("mm")` 确认 |
| 气隙建模 | 气隙区域必须单独建一个 Band 对象，用于旋转边界 |
| 命名规范 | 各部件命名统一：`Stator_Core`, `Rotor_Core`, `PM_[1-8]`, `Winding_A/B/C`, `Band`, `Air_Gap` |

---

## 5. 阶段四：材料定义与分配

### 5.1 标准材料分配（调用 MCP）

```python
# 定子铁心 → 硅钢片
assign_material(objects=["Stator_Core"], material="M270_35A")

# 转子铁心 → 硅钢片
assign_material(objects=["Rotor_Core"], material="M270_35A")

# 永磁体 → NdFeB N35
assign_material(objects=["PM_1","PM_2","PM_3","PM_4",
                          "PM_5","PM_6","PM_7","PM_8"],
                material="NdFe30")

# 绕组 → 铜
assign_material(objects=["Winding_A","Winding_B","Winding_C"], material="copper")

# 轴 → 不导磁钢
assign_material(objects=["Shaft"], material="steel_1008")
```

### 5.2 自定义材料（N48SH 示例）

```python
add_custom_material(
    name="NdFeB_N48SH",
    properties={
        "permeability": 1.05,        # 相对磁导率
        "conductivity": 625000,       # 电导率 S/m
        "Hc": 950000,                 # 矫顽力 A/m（N48SH）
        "Br": 1.38                    # 剩磁 T
    }
)

assign_material(objects=["PM_1","PM_2","PM_3","PM_4",
                          "PM_5","PM_6","PM_7","PM_8"],
                material="NdFeB_N48SH")
```

### 5.3 材料选择速查

| 部件 | 推荐材料 | Maxwell 内置名称 |
|------|---------|----------------|
| 定/转子铁心 | M270-35A 硅钢 | `M270_35A` |
| 永磁体（标准） | NdFeB N35 | `NdFe30` |
| 永磁体（高性能）| NdFeB N48SH | 需自定义 |
| 绕组 | 无氧铜 | `copper` |
| 机壳 | 铝合金 | `aluminum` |
| 轴 | 不导磁不锈钢 | `steel_stainless` |
| 气隙/Band | 真空（空气） | `vacuum` |

---

## 6. 阶段五：绕组与激励设置

### 6.1 集中绕组拓扑（8 极 12 槽）

```
槽号：  1   2   3   4   5   6   7   8   9  10  11  12
相位：  A  -C   B  -A   C  -B   A  -C   B  -A   C  -B
```

### 6.2 绕组分配（MCP 调用）

```python
# 分配线圈截面（每槽 40 导体，即 20 匝双层）
assign_coil(
    objects=["Slot_1", "Slot_7"],
    conductor_number=40,
    polarity="Positive",
    name="Coil_A_pos"
)
assign_coil(
    objects=["Slot_4", "Slot_10"],
    conductor_number=40,
    polarity="Negative",
    name="Coil_A_neg"
)

# A 相绕组（含正负线圈）
assign_winding(
    coil_terminals=["Coil_A_pos", "Coil_A_neg"],
    winding_type="Current",
    is_solid=False,
    current=17.68,    # 峰值 = 12.5A × √2
    resistance=0.52,  # 相电阻 Ω
    inductance=0.0,
    voltage=0.0,
    name="Phase_A"
)
# B 相、C 相类似，相位分别滞后 120°、240°
```

### 6.3 激励电流设置

```python
# 三相正弦电流激励
assign_current_source(
    objects=["Phase_A"],
    amplitude=17.68,   # A（峰值）
    phase=0.0,         # A 相参考 0°
    frequency=200.0,   # Hz（3000rpm × 4极对数 / 60）
    name="Current_A"
)

assign_current_source(
    objects=["Phase_B"],
    amplitude=17.68,
    phase=-120.0,
    frequency=200.0,
    name="Current_B"
)

assign_current_source(
    objects=["Phase_C"],
    amplitude=17.68,
    phase=-240.0,
    frequency=200.0,
    name="Current_C"
)
```

---

## 7. 阶段六：边界条件与网格设置

### 7.1 旋转运动边界（Band）

```python
# Band 对象需在建模阶段已创建（覆盖气隙的圆形区域）
run_script(script="""
oDesign.AssignBand(
    ["NAME:Band",
     "Objects:=", ["Band"],
     "AngularVelocity:=", "3000rpm",
     "WhichAxis:=", "Z",
     "InitialPositionIsZero:=", True]
)
""")
```

### 7.2 向量磁位边界（外边界）

```python
assign_vector_potential(
    objects=["Stator_Outer"],
    value=0.0,
    name="VectorPot_Zero"
)
```

### 7.3 网格精化策略

```python
# 气隙区域精化
run_script(script="""
oMeshModule = oDesign.GetModule("MeshSetup")
oMeshModule.AddLengthBased(
    ["NAME:AirGap_Mesh",
     "RefineInside:=", True,
     "Objects:=", ["Air_Gap"],
     "RestrictElem:=", False,
     "MaxLength:=", "0.2mm",
     "RestrictLength:=", True]
)

# 永磁体精化
oMeshModule.AddLengthBased(
    ["NAME:PM_Mesh",
     "RefineInside:=", True,
     "Objects:=", ["PM_1","PM_2","PM_3","PM_4",
                   "PM_5","PM_6","PM_7","PM_8"],
     "MaxLength:=", "0.5mm",
     "RestrictLength:=", True]
)
""")
```

### 7.4 网格建议设置

| 区域 | 最大单元尺寸 | 说明 |
|------|------------|------|
| 气隙 Band | 0.2 mm | 旋转精度关键区域 |
| 永磁体 | 0.5 mm | 磁场分布精度 |
| 定子铁心 | 1.5 mm | 铁损计算 |
| 转子铁心 | 1.5 mm | 一般精度 |
| 绕组区域 | 2.0 mm | 导体截面较小 |

---

## 8. 阶段七：求解配置与仿真运行

### 8.1 瞬态求解设置

```python
add_solution_setup(
    setup_name="Transient_Setup",
    stop_time="0.02s",       # 仿真 20 ms（约 1 个电周期）
    time_step="0.0001s",     # 时间步 0.1 ms
    save_fields_flag=True
)
```

### 8.2 参数化扫描（可选）

```python
# 扫描永磁体厚度 hm = 3, 4, 5 mm
run_script(script="""
oDesign.AddParametricSetup(
    ["NAME:Parametric_PM_Thickness",
     "Sim. Setups:=", ["Transient_Setup"],
     ["NAME:Sweeps",
      ["NAME:SweepDefinition",
       "Variable:=", "hm",
       "Data:=", "LIN 3mm 5mm 1mm",
       "OffsetF1:=", False, "Synchronize:=", 0]
     ],
     "CopyMesh:=", False,
     "SolveWithCopiedMeshOnly:=", True]
)
""")
```

### 8.3 运行仿真

```python
run_simulation(setup_name="Transient_Setup")
# 等待完成后（可轮询状态）
get_maxwell_status()
```

---

## 9. 阶段八：结果提取与报告生成

### 9.1 创建转矩报告

```python
create_report(
    report_name="Torque_vs_Time",
    report_type="Transient",
    x_quantity="Time",
    y_quantities=["Moving1.Torque"],
    display_type="Rectangular Plot"
)
```

### 9.2 创建磁通密度云图

```python
create_report(
    report_name="B_Field_Distribution",
    report_type="Fields",
    x_quantity="",
    y_quantities=["Mag_B"],
    display_type="Field Plot"
)
```

### 9.3 获取关键数据

```python
# 获取平均转矩（最后一个周期均值）
data = get_solution_data(
    expressions=["Moving1.Torque"],
    setup_name="Transient_Setup"
)
# data 中计算均值 → 与目标 1.59 N·m 对比

# 铜损数据
get_solution_data(
    expressions=["Winding_Loss"],
    setup_name="Transient_Setup"
)

# 铁损数据
get_solution_data(
    expressions=["CoreLoss"],
    setup_name="Transient_Setup"
)
```

### 9.4 结果目标值对比表

| 性能指标 | 设计目标 | 仿真结果 | 是否满足 |
|---------|---------|---------|---------|
| 额定转矩 | 1.59 N·m | [填入] | — |
| 转矩脉动 | < 10% | [填入] | — |
| 气隙磁密峰值 | 0.7–0.85 T | [填入] | — |
| 铁损 | < 15 W | [填入] | — |
| 铜损 | < 40 W | [填入] | — |
| 效率 | ≥ 88% | [填入] | — |

---

## 10. 完整 Prompt 模板

### 10.1 一键启动 Prompt（发送给 Claude）

```
你是一位 ANSYS Maxwell 电机仿真专家，请通过 MCP Server 工具完成以下任务：

【电机设计需求】
- 类型：表贴式永磁同步电机（SPMSM）
- 额定功率：500 W，转速：3000 rpm，母线电压：48 V
- 极数/槽数：8 极 12 槽
- 外径：80 mm，轴向长度：50 mm
- 效率目标：≥ 88%

【请按以下顺序执行】
1. 调用 connect_to_maxwell() 连接软件
2. 调用 new_project() 和 new_design() 新建瞬态仿真项目
3. 完成定子、转子、永磁体、气隙 Band 的几何建模
4. 完成材料分配（铁心 M270_35A，永磁体 NdFe30，绕组铜）
5. 完成 8 极 12 槽集中绕组的激励设置，三相正弦电流
6. 添加旋转边界 Band 和向量磁位外边界
7. 配置瞬态求解：0~20ms，步长 0.1ms
8. 运行仿真并等待完成
9. 创建转矩-时间曲线报告和磁密云图
10. 提取平均转矩、铁损、铜损数据，计算效率，生成结果摘要

每一步执行后请报告状态。如遇错误，请先检查连接状态和参数合理性再重试。
```

### 10.2 分步调试 Prompt（适用于 Codex）

```python
# Codex 系统提示（System Prompt）
SYSTEM = """
你是一位 ANSYS Maxwell 仿真自动化助手。
你可以调用以下 MCP 工具：
- connect_to_maxwell, new_project, new_design
- draw_rectangle, draw_circle, draw_line, draw_arc
- assign_material, add_custom_material
- assign_coil, assign_winding, assign_current_source
- assign_vector_potential, assign_master_slave
- add_solution_setup, run_simulation, get_solution_data
- create_report, run_script, get_maxwell_status

每次只执行一步，执行后返回结果，等待用户确认后再进行下一步。
如果遇到 COM 接口错误，先调用 get_maxwell_status() 检查连接。
"""

# 用户首次输入
USER = "开始建立一个 500W 3000rpm 8p12s SPMSM 的 Maxwell 仿真模型"
```

### 10.3 错误处理 Prompt 片段

```
如果上一步工具调用失败，请：
1. 调用 get_maxwell_status() 检查 Maxwell 是否仍在运行
2. 检查错误信息中的参数名是否正确
3. 如果是 COM 接口超时，重试一次
4. 如果连续失败 3 次，停止并报告具体错误信息
5. 不要跳过失败的步骤继续执行后续步骤
```

---

## 11. MCP 工具调用速查表

| 工具名称 | 阶段 | 主要参数 | 说明 |
|---------|------|---------|------|
| `connect_to_maxwell` | 初始化 | — | 连接 Maxwell COM |
| `new_project` | 初始化 | — | 新建项目 |
| `new_design` | 初始化 | `design_name`, `solution_type` | 瞬态/静磁/涡流 |
| `draw_circle` | 建模 | `name`, `x_center`, `y_center`, `radius` | 绘制圆 |
| `draw_rectangle` | 建模 | `name`, `x_start`, `y_start`, `width`, `height` | 绘制矩形 |
| `draw_line` | 建模 | `name`, `start`, `end` | 绘制线段 |
| `draw_arc` | 建模 | `name`, `x_center`, `y_center`, `radius`, `start_angle`, `end_angle` | 绘制弧 |
| `assign_material` | 材料 | `objects`, `material` | 分配已有材料 |
| `add_custom_material` | 材料 | `name`, `properties` | 添加自定义材料 |
| `assign_coil` | 激励 | `objects`, `conductor_number`, `polarity`, `name` | 线圈截面 |
| `assign_winding` | 激励 | `coil_terminals`, `winding_type`, `current`, `name` | 绕组定义 |
| `assign_current_source` | 激励 | `objects`, `amplitude`, `phase`, `frequency`, `name` | 正弦电流 |
| `assign_vector_potential` | 边界 | `objects`, `value`, `name` | 磁位边界 |
| `assign_master_slave` | 边界 | `master_objects`, `slave_objects`, `angle` | 周期对称边界 |
| `add_solution_setup` | 求解 | `setup_name`, `stop_time`, `time_step` | 求解配置 |
| `run_simulation` | 求解 | `setup_name` | 运行仿真 |
| `get_solution_data` | 后处理 | `expressions`, `setup_name` | 提取数值 |
| `create_report` | 后处理 | `report_name`, `report_type`, `x_quantity`, `y_quantities` | 创建图表 |
| `run_script` | 通用 | `script`, `save_before` | 执行 IronPython |
| `get_maxwell_status` | 调试 | — | 检查连接状态 |
| `list_designs` | 管理 | — | 列出所有设计 |
| `save_project` | 管理 | `file_path` | 保存项目 |

---

## 12. 常见问题排查

### Q1：`connect_to_maxwell()` 失败
```
原因：Maxwell 未打开，或 COM 注册表缺失
解决：
  1. 手动启动 ANSYS Maxwell 软件
  2. 确认 Maxwell 版本 ≥ 2022 R1
  3. 以管理员身份运行 Claude/Codex 客户端
  4. 检查防火墙是否阻止了 COM 通信
```

### Q2：`assign_material` 报错 "Material not found"
```
原因：材料库名称大小写或下划线不一致
解决：
  1. 先调用 list_materials() 查看库中实际名称
  2. 常见易错：M270-35A → M270_35A，NdFe30 → NdFe30（注意大小写）
  3. 或使用 add_custom_material() 手动添加
```

### Q3：仿真收敛慢或不收敛
```
原因：时间步太大，或网格质量差
解决：
  1. 减小时间步（从 0.1ms → 0.05ms）
  2. 增大气隙网格密度
  3. 检查 Band 对象是否覆盖整个气隙区域
  4. 确认旋转速度单位（rpm 而非 rad/s）
```

### Q4：转矩结果为零或异常
```
原因：激励未正确连接，或绕组极性错误
解决：
  1. 检查 assign_coil 的 polarity（正负线圈方向）
  2. 检查 assign_winding 中 coil_terminals 列表是否完整
  3. 确认 Band 旋转方向与转矩方向一致
  4. 用 create_report 观察 "Moving1.Torque" 而非 "Core.Torque"
```

### Q5：COM 接口调用偶发超时
```
原因：Maxwell 大型网格计算时 COM 响应慢
解决：
  1. 在 run_simulation 后不要立即查询，等待 5~10 秒
  2. 轮询 get_maxwell_status() 直到状态变为 "Completed"
  3. 增大 MCP Server 的超时参数（在 pyproject.toml 中配置）
```

---

## 附录 A：8 极 12 槽绕组接线图

```
定子槽号：  1   2   3   4   5   6   7   8   9  10  11  12
          ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
相位标记：  A+ C-  B+  A-  C+  B-  A+  C-  B+  A-  C+  B-
          └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘

A 相：槽 1(+), 槽 4(-), 槽 7(+), 槽 10(-)
B 相：槽 3(+), 槽 6(-), 槽 9(+), 槽  12(-)
C 相：槽 2(-), 槽 5(+), 槽 8(-), 槽  11(+)
```

## 附录 B：常用电频率与转速对应关系

| 极对数 p | 转速 (rpm) | 电频率 (Hz) |
|---------|-----------|------------|
| 4 | 3000 | 200 |
| 4 | 1500 | 100 |
| 3 | 3000 | 150 |
| 5 | 3000 | 250 |
| 2 | 3000 | 100 |

计算公式：`f = p × n / 60`

## 附录 C：推荐参考标准

- **GB/T 755** — 旋转电机定额和性能（等效 IEC 60034-1）
- **IEC 60034-30** — 电机能效分级（IE1~IE5）
- **ANSYS Maxwell 官方文档** — Maxwell 2024 R1 Technical Reference
- **JSOL JMAG** — 对比验证可用 JMAG-Designer

---

*文档生成时间：2026-06-17 | 版本 v1.0*  
*本文档基于 ANSYS Maxwell MCP Server v1.x 编写，如 API 有更新请对照最新工具调用手册修改*
