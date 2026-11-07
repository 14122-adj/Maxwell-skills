# Maxwell 内部模型逆向记录（AEDT 2021 R1）

> 证据来源：`D:\ANSYS_Run\M1_min.aedt`、`M2_25Nm.aedt`、`M3_25Nm.aedt` 的纯文本工程格式，
> 以及 `m1_probe.log` / `m2_stdout.log` / `m3_fix_progress.log` 的实际运行日志。
> 目的：说明 Maxwell 如何存储几何、材料、绕组、边界与场，以及"创建工程 → 画定子"的真实过程。
> 结论均来自实测文件，未依赖猜测；`REA` 的编译运行时在本机缺失（Node 22.22 < 要求 22.23.4），
> 因此以 `.aedt` 文本格式作为一手证据。

---

## 1. 工程文件语法

AEDT 的 `.aedt` 是 UTF-8 文本，采用 `$begin '块名' ... $end '块名'` 的嵌套块 + `key=value` 行：

```
$begin 'AnsoftProject'
  Created='...'
  Product='ElectronicsDesktop'
  $begin 'Desktop'
    Version(2021, 1)
  $end 'Desktop'
  $begin 'Definitions'
    $begin 'Materials'
      $begin 'vacuum'
        MaterialValue=...
      $end 'vacuum'
    $end 'Materials'
  $end 'Definitions'
  $begin 'M1_Min'            # 设计名
    $begin 'Maxwell2DModel'
      ...
      $begin 'GeometryCore'
        $begin 'ToplevelParts'
          $begin 'GeometryPart'
            $begin 'Attributes'
              Name='StatorOuter'
              MaterialValue='"vacuum"'
            $end 'Attributes'
            $begin 'Operations'
              ... Circle / Polyline / Subtract / DuplicateAroundAxis ...
            $end 'Operations'
          $end 'GeometryPart'
        $end 'ToplevelParts'
        $begin 'allobjects' ...
      $end 'GeometryCore'
      $begin 'BoundarySetup' ...
      $begin 'MeshSetup' ...
      $begin 'AnalysisSetup' ...
    $end 'Maxwell2DModel'
  $end 'M1_Min'
$end 'AnsoftProject'
```

**关键结论**：Maxwell 的"模型"就是这棵块树；脚本 API 的每个调用最终都落到这些块/键上。
`ModelDepth`、`MaterialValue`、`Edges(...)` 都能在文本里直接核对，无需打开 GUI。

---

## 2. 设计对象（Maxwell2DModel）

| 块/键 | 含义 | 实测 |
|---|---|---|
| `$begin 'Maxwell2DModel'` | 一个 Maxwell 2D 设计 | `Motor_Design` |
| `SolutionType='Transient'` | 求解类型 | Transient（M1 为 Magnetostatic） |
| `ModelDepth='160mm'` | **2D 拉伸深度 = 叠长** | 原始 M2 为 `1meter`；M3 修正为 `160mm` |
| `$begin 'GeometryCore'` | 几何容器 | 包含 `ToplevelParts` / `allobjects` / `model` |
| `$begin 'BoundarySetup'` | 边界/激励 | `VectorPotential1`、`WindingA/B/C` |
| `$begin 'MeshSetup'` | 剖分 | `MeshOperations` |
| `$begin 'AnalysisSetup'` | 求解设置 | `Setup1`（Transient） |

**重要**：`ModelDepth` 默认是 **1 meter**（不是 1 mm）。不显式设置时，2D 转矩/铁耗/反电势会按 1 m 深度计算，
与 160 mm 设计相差 **6.25×**（相对 1 m），相对"1 mm"的常见误解则是 1000×。必须显式写 `160mm`。

---

## 3. 几何对象如何表达

`GeometryCore → ToplevelParts → GeometryPart → Attributes`：

| 键 | 示例 | 含义 |
|---|---|---|
| `Name` | `StatorOuter` | 对象名，后续绕组/材料/边界都按名引用 |
| `MaterialValue` | `'"vacuum"'` | 材料名（**带内层引号**） |
| `SolveInside` | `true` | 是否求解内部 |
| `Operations` | `Circle` / `Polyline` / `Subtract` / `DuplicateAroundAxis` | 建模操作链 |

### 3.1 定子
- `StatorOuter`：`Circle(Radius='75mm')`
- `StatorInner`：`Circle(Radius='46.5mm')`
- `Subtract(StatorOuter - StatorInner)` → 定子环
- `Slot_1`：`Polyline`，7 个点、**6 段**（`StartIndex 0..5`）
- `DuplicateAroundAxis(30deg × 12)` → `Slot_1_1` … `Slot_1_11`（共 12 个）
- `Subtract(StatorOuter - 12 slots)` → 带槽定子

### 3.2 转子
- `RotorOuter`：`Circle(45.825mm)`
- `Shaft`：`Circle(15mm)`
- `Subtract(RotorOuter - Shaft)` → 转子环
- `PM_1..PM_8`：`Rectangle(1.95mm × pm_h)`，按 45° 旋转，N/S 交替
- `Band`：`Circle(46.1625mm)`，气隙中心的运动带
- `Region`：`Circle(95mm)`，外部求解域

### 3.3 绕组
- `Coil_1..Coil_12`：槽内矩形，`MaterialValue='"copper"'`
- `WindingA/B/C`：`BoundType='Winding Group'`
- `AssignCoilGroup` 在 `.aedt` 中体现为线圈组 + 极性（`Positive/Negative`）
- 空间关系：槽 → 线圈 → 相带（A+/A−/B+/B−/C+/C−）→ 三相绕组；极性决定电流方向

---

## 4. 材料、边界、场的表达

### 4.1 材料
- 材料定义在 `Definitions → Materials`（`NdFe35_N`、`NdFe35_S`、`M270_35A`、`copper`）。
- 对象上的赋值是 `Attributes.MaterialValue='"材料名"'`。
- 用 `ChangeProperty` 修改时，`Value` 必须带内层引号：`'"M270_35A"'`。
- 实测：M2 的定/转子仍是 `vacuum`；M3 已改为 `M270_35A`（2 处）。

### 4.2 边界
- `BoundarySetup → Boundaries → VectorPotential1`：
  ```text
  $begin 'VectorPotential1'
    ID=3
    BoundType='Vector Potential'
    Edges(7)
    Value='0'
  $end 'VectorPotential1'
  ```
- **按边 ID 存储**，不是按对象名。脚本必须 `GetEdgeIDsFromObject("Region")` 取整数 ID，
  再 `AssignVectorPotential(["NAME:...", "Edges:=", [7], "Value:=", "0", ...])`。

### 4.3 求解设置
- `AnalysisSetup → SolveSetups → Setup1`：
  `StopTime=0.02s`、`TimeStep=50us`、`SaveFieldsType='Every N Steps'`。
- 场结果在 `Solutions` / `FieldsReporter` / `FieldsCalculator`；`.aedt` 只存设置，场数据在 `.aedtresults`。

---

## 5. 空间关系（Maxwell 怎么"理解"电机）

1. **2D 平面 = XY**：所有几何都是 XY 平面上的圆/多段线/矩形；Z 方向由 `ModelDepth` 拉伸。
2. **单位 = mm**：`SetModelUnits(["NAME:UnitsSettings", "Length:=", "mm"])`；
   注意不是 `Units:=`（错误键会导致单位不生效）。
3. **径向/切向**：定子/转子/磁钢/线圈都以原点为中心，按角度 `k·30°`（槽）或 `k·45°`（磁钢）旋转。
4. **气隙**：`Band` 位于定子内径 46.5 与转子外径 45.825 之间（半径 46.1625 mm），是运动带。
5. **槽 → 线圈 → 绕组**：槽是定子上的减法区域；线圈是槽内的铜矩形；线圈组按极性连成三相。
6. **场**：材料属性（μ、σ、Br/Hc）决定场分布；边界（VectorPotential=0）限定求解域；
   网格（MeshOperations）决定离散精度；`Setup1` 决定时间步与总时长。
7. **"电子"**：Maxwell 2D 不显式建"电子"粒子；电流以绕组激励（Current/Voltage）或外部电路体现，
   场是宏观连续介质解（A-formulation），电子只是电流的微观载体。

---

## 6. 创建过程（实测可用顺序）

```text
1. oDesktop.NewProject()
2. oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
3. oDesign.SetDesignSettings(["NAME:DesignSettingsData",
       "ModelDepth:=", "160mm",
       "PreserveTransientSolution:=", False,
       "ComputeTransientInductance:=", True])
4. oEditor = oDesign.SetActiveEditor("3D Modeler")
5. oEditor.SetModelUnits(["NAME:UnitsSettings", "Length:=", "mm"])
6. CreateCircle(Region/StatorOuter/StatorInner/RotorOuter/Shaft/Band)
7. CreatePolyline(Slot_1, 7 points / 6 segments)
8. DuplicateAroundAxis(30deg × 12) → Slot_1_1..11
9. Subtract(StatorOuter - StatorInner) / Subtract(StatorOuter - 12 slots)
10. CreateRectangle(PM_1..8, Coil_1..12) + Rotate
11. EditMaterial(NdFe35_N/S, M270_35A) + ChangeProperty(MaterialValue)
12. BoundarySetup.AssignVectorPotential(Edges=[7], Value="0")
13. MeshSetup.AssignLengthOp(...)
14. AnalysisSetup.InsertSetup("Transient", Setup1)
15. oProject.SaveAs("D:/ANSYS_Run/M3_25Nm.aedt", True)
```

### 实测坑位（必须记住）
| 坑 | 正确做法 |
|---|---|
| `SetModelUnits` 用 `Units:=` | 用 `Length:=` |
| `CreatePolyline` 写 7 段 | 7 个点只能 6 段（`StartIndex 0..5`） |
| `AddMessage(0,0,0,msg)` | 签名是 `AddMessage(project, design, severity, msg)`；可省略 |
| `ChangeProperty` 材料值不带引号 | `Value:='"M270_35A"'`（内层引号） |
| `AssignVectorPotential(Objects=["Region"])` | `Edges:=[int(id)]`，用 `GetEdgeIDsFromObject` |
| 默认 `ModelDepth=1meter` | 显式 `ModelDepth:="160mm"` |
| `-ng -RunScriptAndExit` | 需配 `-batchsave/-batchsolve` 且文件名在最后；或直接用 `-RunScriptAndExit`（实测可用） |

---

## 7. 与"电子/槽/线/绕组/磁场"的对应

| 概念 | Maxwell 中的对象 | 存储位置 |
|---|---|---|
| 电子/电流 | 不建粒子；绕组激励/外部电路 | `BoundarySetup → Winding Group` |
| 定子槽 | `Slot_1..Slot_1_11`（减法区域） | `GeometryCore → ToplevelParts` |
| 线/导体 | `Coil_1..Coil_12`（铜矩形） | `GeometryCore → ToplevelParts` |
| 绕组 | `WindingA/B/C` + 线圈组极性 | `BoundarySetup → Boundaries` |
| 磁场 | 材料 μ/σ + 边界 + 网格 → 解 | `Solutions` / `.aedtresults` |
| 空间 | XY 平面 + `ModelDepth` 拉伸 | `Maxwell2DModel → ModelDepth` |

---

## 8. 当前状态与下一步

| 阶段 | 状态 | 证据 |
|---|---|---|
| M1 打开 Maxwell + 新建工程 | ✅ | `M1_min.aedt`（Maxwell 2D / Magnetostatic） |
| M2 整机几何 | ✅ | `M2_25Nm.aedt` 281 KB：12 槽 + 8 磁钢 + 12 线圈 + Band + Region |
| M3 材料/边界/求解设置 | ✅ | `M3_25Nm.aedt`：`ModelDepth='160mm'`、`M270_35A`×2、`VectorPotential1 Edges(7)`、`Setup1` |
| M4 空载求解 | ⬜ 下一步 | 需在桌面会话跑 Transient，导出 BEMF/齿槽 |
| M5 负载求解 | ⬜ | 9.89 A 三相电流，导出转矩 |
| M6 结果回填 | ⬜ | `ingest_fea.py` → `fea_results.json` |

**结论**：技能已经能驱动 Maxwell 完成"新建工程 → 整机几何 → 材料 → 边界 → 求解设置"；
下一步是把 `Setup1` 真正跑起来（M4），而不是继续在解析层打转。
