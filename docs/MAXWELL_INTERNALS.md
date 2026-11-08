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

---

## 9. 2021.1 求解阶段实测坑位（2026-11-08，M4）

上一版（M2/M3）的模型**根本解不动**：`oDesign.Analyze("Setup1")` 立即失败，消息窗口
给出 36 条 `Parts "A" and "B" intersect` + 1 条 `Non-manifold vertices`。
逐条定位如下，全部是几何/参数写法问题，与许可证、沙箱无关。

### 9.1 `M4_25Nm.aedt` 为什么不可解

| # | 现象（AEDT 原文） | 真实原因 | 正确做法 |
|---|---|---|---|
| 1 | `Parts "StatorOuter" and "PM_x" intersect` | 磁钢用**平板弦**从 XStart=45.825 向外 1.95 mm ⇒ 径向跨 45.825…47.775，而定子内径 46.5，插入铁芯 1.275 mm | 磁钢改**环形扇区** 43.875…45.825，按弧离散（24 段/极，弧矢 4.5 µm） |
| 2 | `Parts "StatorOuter" and "Coil_x" intersect`（12 条） | 线圈取 13.2×5.7 矩形，而槽在 r=49.65 只有 3.2 mm 宽 | 线圈 = 槽多边形按 0.88 **缩放**（凸多边形收缩必内含） |
| 3 | `Non-manifold vertices found for "StatorOuter"` | 槽多边形首尾重复点未给闭合段；且槽口与内径**相切** | 顶点 N 个 → 给 N+1 个点（末点复写首点）+ N 段；槽口切入内径 0.2 mm |
| 4 | 全域重叠（无报错但结果不可信） | `Region` 是整圆，从未与定子/带/线圈布尔分离 | `Region −(定子, 转子, 磁钢, 线圈, Band)`，`KeepOriginals=True` |

**校验方法（可复用）**：布尔后按面积反算，并做**面积守恒**——
`Σ(Region+定子+线圈+Band) == π·95²`。本次实测 28352.8737 mm²，误差 0.000%。

### 9.2 `AssignBand` 的正确写法

```python
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData", "Move Type:=", "Rotate", "Coordinate System:=", "Global",
     "Axis:=", "Z", "Is Positive:=", True, "Init Pos:=", "0deg",
     "HasRotateLimit:=", False, "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "1500rpm", "Objects:=", ["Band"]])
```

- 键名是 **`Init Pos:=`**（带空格）；写成 `InitPos:=` 会被忽略但不报错。
- **Band 必须是"包住转子"的整圆**：AEDT 的报错文案是
  `Invalid object selected for band. No objects within the band.`
  —— 把 Band 做成"气隙环、转子在洞内"会被判失败（试过洞内留 25/45 µm 净空、50 µm 均失败）。
  包含式重叠（转子在 Band 内）不触发 intersect 检查，只有**边界穿越**才报。
- 若报 `For 2D XY translation problem, only X or Y axis could be used`，
  说明 Move Type 没被识别/退化成平动，检查上面整串键是否原样传入。
- 旧文档称 M3 已"Band 1500 rpm"，实测 `MotionSetupList` 当时是**空的**——命令失败但被 try 吞掉。
  **判断 band 是否真落地，要读 `.aedt` 里 `$begin 'MotionSetup1'`，不能看脚本是否报错。**

### 9.3 其它 API 修正

| 用途 | 错误写法 | 可用写法 |
|---|---|---|
| 读面积 | `GetFaceArea(name, fid)`（2 参） | `GetFaceArea(fid)`（**1 参**），fid 来自 `GetFaceIDs(name)` |
| 求解 | `oDesign.GetModule("AnalysisSetup").Solve(...)` | **`oDesign.Analyze("Setup1")`**；成功返回 None，不能用返回值判成败 |
| 剖分 | `MeshSetup.AssignSurfApproxOp`（2021.1 无此方法） | 只用 `AssignLengthOp` |
| 重命名 | 同名重命名 | 会报 `Invalid PropServer` 并把对象改成 `Name_8` 之类；**old==new 必须跳过** |
| 单位 | `SetModelUnits("Length:=", "mm")` | `"Units:=", "mm"` |
| 折线闭合 | N 顶点 + N−1 段 | N 顶点 + 1 复写点 + N 段 |

### 9.4 报告导出（2026-11-09 解决：唯一可用配方）

先说结论：`ReportSetup.CreateReport` 在批处理下**能用**，但只有下面这一种写法。
此前「144 种组合全失败」是因为三处参数都踩在坑上，缺一即 `call failed`：

```python
rep.CreateReport(
    "Tq",                                   # 报告名
    "Standard",                             # ← 坑1：必须是 "Standard"，不是 "Transient"
    "Rectangular Plot",
    "Setup1 : Transient",                   # 求解名 + " : " + 求解类型
    ["NAME:Context", "SimValueContext:=",    # ← 坑2：必须 NAME:Context 包一层
     [1, 0, 2, 0, False, False, -1, 1, 0, 1, 1, "", 0, 0]],
    ["Time:=", ["All"]],
    ["X Component:=", "Time",             # ← 坑3：X/Y 写在同一参，且不再有 expr:=" 前缀
     "Y Component:=", ["Moving1.Torque"]],
    [])                                     # 第 8 参给空 list

rep.ExportToFile("Tq", r"D:/ANSYS_Run/csv/tq_noload.csv")   # 失败时再试三参 (..., True)
```

| 参数 | 错误写法（必失败） | 正确写法 |
|---|---|---|
| reportTypeArg | `"Transient"` | `"Standard"` |
| simValueCtxtArg | `["Domain:=", "Sweep"]` | `["NAME:Context", "SimValueContext:=", [1,0,2,0,False,False,-1,1,0,1,1,"",0,0]]` |
| expressionsOfTracesArg | `[expr + ":=", ["None","None","None"]]` | `["X Component:=", "Time", "Y Component:=", [expr]]` |
| pointSetArg | `["Time:=", "0.02s"]` | `["Time:=", ["All"]]` |

配套两个坑：

1. **`CreateReport` 抛异常 ≠ 报告没建成。** 报告已存在时重复 Create 会抛，但同名报告可用，
   直接 `ExportToFile` 即可；因此代码里要「忽略 Create 异常、照常尝试导出」。
2. **`ExportToFile` 可能在数据缺失时只给警告不报错**，返回的 CSV 是空的。
   消息窗口出现 `Report BemfA has no data for export` 即属此类 ⇒ 导出后必须数行数校验
   （见 `maxwell_model/export_m4_csv.py::data_rows`）。

**电流型绕组没有 `*.Voltage` 观测**：`AssignWindingGroup(Type="Current")` 下不存在
`WindingA.Voltage`，导它必然得到 "no data"。空载反电势的正确取法是导磁链再求导：

```
FluxLinkage(WindingA) [Wb]  →  e(t) = − dλ(t)/dt
```

求解与导出已解耦：重导出用 `maxwell_model/export_m4_csv.py`，不必重跑 400+ s 的求解。

### 9.5 求解耗时基线

| 项 | 实测 |
|---|---|
| 4 步试算（0.2 ms） | 16.2 s |
| 全时长（0.02 s / 50 µs = 400 步） | **416.7 s** |
| 并行进程 | `solver2d.exe` 独立进程，CPU 累计 975 s；`ansysedt.exe` 此时近乎空闲 |
| 结果体积 | `.aedtresults` 约 23 MB（SaveFields = Every 2 Steps） |

### 9.6 匝数口径：`Conductor number` 不是线圈匝数（2026-11-09 查实）

这是 M4 首轮反电势只有解析值一半的**唯一**原因，磁路本身是准的。

`BoundarySetup.AssignCoil` 的 `"Conductor number:="` 是**单个槽边**的导体数。
一匝必然「进一个槽、出另一个槽」，所以：

```
一个绕齿线圈的匝数 = 槽边导体数
相 A = 槽{1+,2−} 绕齿 1  +  槽{7+,8−} 绕齿 7   ⇒ 2 个线圈串联
N_phase = 2 × Conductor number
```

12S8P 单层集中绕组的分配（槽距电角 = 360°×4/12 = 120°）：

| 相 | 槽（极性） | 线圈数 | 槽边导体 20 时 | 槽边导体 40 时 |
|---|---|---|---|---|
| A | 1+, 2−, 7+, 8− | 2 | 40 匝 | **80 匝** |
| B | 3+, 4−, 9+, 10− | 2 | 40 匝 | **80 匝** |
| C | 5+, 6−, 11+, 12− | 2 | 40 匝 | **80 匝** |

旧注释「4 线圈/相 ⇒ 80 匝/相」把**槽边数**当成了线圈数，实际 4 个槽 = 2 个线圈。
取 40 导体/槽边 ⇒ 80 匝/相，与设计 81 匝差 −1.2%。

**反推校验（判断磁路对不对的关键手法）**：用 FEA 的每匝磁链除以真实绕组因数，
再与解析 φ_pm 比，就能把「绕组口径错」和「磁路错」分开：

| 量 | 首轮 FEA（20 导体/槽边） | 解析 | 比 |
|---|---|---|---|
| λ_pp（相） | 0.2594 Wb | — | — |
| 每匝 λ_peak = 0.2594/2/40 | 3.24 mWb | — | — |
| 反推 φ_pole = 3.24 / 0.866 | **3.74 mWb** | 3.946 mWb | **0.95** ✅ |
| E_ph_rms = ωλ_peak/√2 | 59.3 V | 132.4 V | 0.45 ❌ |

磁路只差 5%，反电势差 55% ⇒ 差异全部来自匝数（40 vs 81 ≈ 0.49），
而不是磁钢、气隙或饱和。**先做这个比值，再决定要不要动几何。**

12S8P 的真实绕组因数 **kw = 0.866**（= kp 0.866 × kd 1.0），
而 `pmsm_config.py` 里用的是 **0.933**（那是 12S10P 的值）——这是解析链路的独立问题，
会在 M6 回填时一并标注，不影响 M4 的 Maxwell 结论。


## 9. 空载求解与导出实测（2026-11-08）

- **Band 必须是与转子/磁钢不重叠的薄环**：`R_in=45.85`、`R_out=46.1625 mm`。整圆盘会覆盖转子/PM，
  等效削弱永磁磁通，BEMF 掉到解析的 ~45%；挖掉转子/PM 的带孔环会被 Maxwell 拒绝。
- **`AssignBand`**：键名 `"InitPos:="`（无空格）；写成 `"Init Pos:="` 会被当成平动，
  报 `For 2D XY translation problem, only X or Y axis could be used`。
- **`EditSetup` 会丢掉 band 运动**：全时长求解前先 `DeleteMotionSetup` 再重新 `AssignBand`，
  否则全时长磁链恒定、EMF≈0。
- **BEMF 提取**：电流型绕组的 `WindingA.Voltage` 为空；用 `FluxLinkage(WindingA)`，
  或直接读原生 `.aedtresults/*.Data/WindingA_TrCrv.txt`（第 4 列磁链 Wb、第 5 列电压 V）。
- **`CreateReport`**：`(name, "Standard", "Rectangular Plot", solution,
  ["NAME:Context","SimValueContext:=",[1,0,2,0,false,false,-1,1,0,1,1,"",0,0]],
  ["Time:=",["All"]], ["X Component:=","Time","Y Component:=",[expr]], [])`。
  `ExportToFile` 可能静默不写，必须检查文件存在与大小。
- **单位陷阱**：`Time [us]`、`Torque [mNewtonMeter]`；换算成 s / N·m。
- **结果**：相 BEMF 峰值 ≈157 V（相 RMS ≈111 V，解析 132.4 V，−16%）；齿槽峰值 0.404 N·m
  = 1.6% 额定（解析 0.454 N·m / 1.8%，吻合）。
