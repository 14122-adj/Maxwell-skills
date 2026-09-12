---
name: ansys-maxwell-motor
description: ANSYS 多物理场仿真编排器 — 电机电磁设计全流程自动化 + 多学科联合仿真（电磁-结构-热）+ IGBT封装可靠性（热-电-力耦合+疲劳寿命）。参数自动补全、多目标优化、10种电磁仿真+多物理场耦合、疲劳寿命预测、参数化扫描。触发词：电机设计/电机仿真/motor design/Maxwell/多物理场/multiphysics/MDAO/IGBT可靠性/疲劳寿命/焊层/耦合仿真。
agent_created: true
---

# ANSYS 多物理场仿真编排器 Skill (MDAO)

---

## 🚨 绕组位置速查 (AI 必读区) 🚨

> **铁律**：接到"X 极 Y 槽电机"任务时，**先查本节**，再决定下一步。
> 不要靠直觉推断、不要改写 `references/winding_layouts.md` 里的数字、不要用旧 `pmsm_winding_builder.py` 的算法结果直接建 Maxwell。

### 速查命令

```bash
# 单个极槽配合的槽-相-极性映射 (Markdown 格式, 贴答案最快)
python scripts/winding_layout.py <slots> <poles> --list

# 例子: 8 极 12 槽
python scripts/winding_layout.py 12 8 --list

# 生成可直接喂 Maxwell 的 IronPython 脚本
python scripts/winding_layout.py 12 8 --maxwell

# 列出全部 19 种 canonical 组合
python scripts/winding_layout.py --all

# 对比两个组合
python scripts/winding_layout.py --compare 12 8 36 8
```

### 5 个最高频 case (查表后还应交叉验证)

#### 8p/12s 集中绕组 (伺服/小电机最常见)

```
Slot:    1   2   3   4   5   6   7   8   9  10  11  12
Phase:   A+  A-  B+  B-  C+  C-  A+  A-  B+  B-  C+  C-
Coil:    C1  C2  C3  C4  C5  C6  C7  C8  C9  C10 C11 C12
```

- 每相 2+ 2-，k_w = 0.866
- **每相总匝数 N_ph = 2 × N_s × 1/2 = N_s**（双层集中）

#### 10p/12s 集中绕组 (EV 驱动常用)

```
Slot:    1   2   3   4   5   6   7   8   9  10  11  12
Phase:   A+  C-  B+  A-  C+  B-  A+  C-  B+  A-  C+  B-
```

- 每相 2+ 2-，k_w = 0.933

#### 8p/24s 分布绕组 (标准工业电机)

```
Slot:     1    2    3    4    5    6    7    8    9   10   11   12
Phase:    A+   A-   B+   B-   C+   C-   A+   A-   B+  B-   C+   C-
... (12 槽为 1 个周期, 重复 2 次 = 24)
```

- 每相 4+ 4-，k_w = 0.96

#### 8p/36s 分布绕组 (风电/工业大功率)

```
Slot:    1   2   3   4   5   6   7   8   9
Phase:   A+  A-  C-  B+  B-  A-  C+  C-  B-      ← 9 槽 = 1 周期
(× 4 = 36 槽)
```

- 每相 4+ 8-（**q=1.5 固有不平衡, 不是 bug**），k_w = 0.96

#### 4p/24s 分布绕组 (通用工业)

```
Slot:     1    2    3    4    5    6    7    8    9   10   11   12
Phase:    A+   A-   A+   A-   B+   B-   B+   B-   C+  C-   C+   C-
... (× 2 = 24)
```

- 每相 4+ 4-，k_w = 0.933

### 命名与极性约定 (与 Maxwell UI 一致)

| 角色 | 名称 | Maxwell 对象 |
|------|------|-------------|
| 槽 | `Slot_1, Slot_2, ...` | 几何体 |
| 线圈截面 | `Coil_1, Coil_2, ...` | 几何体 |
| 线圈组 | `A+, A-, B+, B-, C+, C-` | Coil Group |
| 绕组 | `WindingA, WindingB, WindingC` | Winding |
| **A+ 极性** | **`PolarityType:="Positive"`** | **← 与 Maxwell UI 一致** |
| **A- 极性** | **`PolarityType:="Negative"`** | |

> ⚠️ 历史 bug: `output_scripts/36slot_industrial/winding.py` 和 `36slot_v2/winding.py` 旧版用了**相反**约定（A+ → Negative, A- → Positive），已在新版中修正。**新代码统一用 standard 约定**。

### 详细参考

- **完整真值表**（19 种极槽配合 + 算法 fallback + 验证清单）: `references/winding_layouts.md`
- **生成器代码**（lookup-first, 集中绕组极性 bug 已修）: `scripts/pmsm_winding_builder.py`
- **查表 CLI**: `scripts/winding_layout.py`
- **自动验证**: `python scripts/test_winding_layouts.py`

### ❌ 错误做法（AI 必避）

1. **不要**按 8p36s 的 AABBCC × 3 模式去套 8p12s（结果错位成 ABCABC，绕组位置全错）
2. **不要**靠"i % 3 == 0/1/2"硬编码相位（36slot_v2 的旧版这样写，对 8p36s 错，对 8p12s 错得更离谱）
3. **不要**把 `A+` 标 `PolarityType:="Negative"`（约定反了，BEMF 整流反向）
4. **不要**跳过查表直接调 `compute_winding()`（v1 算法有 bug，已在 v2 改用 lookup-first）
5. **不要**改 `references/winding_layouts.md` 里的数字（这是真值表，不是参考）

---

## 概述

**双模域能力：**

1. **电机电磁设计（v3.0 原有能力）** — 从最少2个参数出发，自动推导全部设计参数、寻找Pareto最优解、在Maxwell中构建完整FEA模型、运行全部仿真类型、生成含图表的工程报告。支持多槽型（矩形/梨形/梯形/圆形）和多永磁拓扑（SPM/IPM_Flat/IPM_V/IPM_Spoke）一键切换。

2. **多物理场多学科仿真编排（v4.0 新增）** — 电磁-结构-热三场联合仿真、IGBT封装热-电-力耦合可靠性分析、疲劳寿命预测（Coffin-Manson/Darveaux）、参数化扫描（孔洞率/焊层厚度）。基于中车株洲所IGBT和比亚迪轮毂电机获奖论文技术方案。

## 触发条件

**电机电磁设计：**
- 电机设计、电机仿真、motor design、PMSM、BLDC、SRM、IM
- Maxwell自动化、参数化建模、槽型切换、永磁拓扑
- 反电动势分析、转矩仿真、效率优化、NVH

**多物理场仿真：**
- 多物理场、multiphysics、MDAO、多学科、耦合仿真
- IGBT可靠性、焊层疲劳、功率循环、封装热分析
- 热-电-力耦合、电磁-结构-热联合、疲劳寿命预测
- Coffin-Manson、Darveaux、Anand模型、参数化扫描

---

## 核心能力

### 1. 参数自动补全

最少输入2个参数即可自动推导全部电磁和几何参数：

| 提供 | 自动推导 |
|------|---------|
| 功率 + 转速 | 电压、极槽配合、直径、长度、全部电磁参数 |
| 功率 + 电压 | 转速、尺寸、绕组 |
| 外径 + 长度 | 功率范围、最优极槽、电压等级 |

**推导规则：**
- 电压等级：12V(<100W)、24V(100-300W)、48V(300-1000W)、310V(1-10kW)、380V(>10kW)
- 极槽配合：查表 `references/motor_design_guide.md` §6
- 裂比 Dsi/Dso：0.58(2p<8)、0.62(2p≥8)
- 气隙：δ=0.3+Dso/400 mm，截断[0.35, 2.0]
- 电流密度：6 A/mm²(自然)、8(风冷)、12(水冷)
- 转矩密度TRV：8 kN·m/m³(自然冷却500W)，大电机可至20

### 2. 多目标优化

支持4目标Pareto前沿搜索：

```bash
python scripts/motor_optimizer.py \
  --power 500 --speed 3000 \
  --objectives efficiency cost torque_density \
  --constraints "pm_thickness:3:6" "slot_fill:0.3:0.5" "outer_dia:70:90" \
  --algorithm NSGA2 --population 50 --generations 30
```

**算法：** NSGA-II(多目标遗传) | PSO(粒子群) | Grid Search(穷举) | Bayesian(昂贵FEA)

**常用变量：** 磁钢厚度hm、槽口Bs0、极弧系数αp、裂比Dsi/Dso、每相匝数Nph

**常用约束：** 转矩≥目标、效率≥目标、槽满率≤0.50、成本≤预算、Bg≤Bsat

### 3. 完整仿真套件（10种）

按最优顺序执行（先空载验证模型，再负载）：

| # | 仿真类型 | 求解器 | 关键输出 |
|---|---------|--------|---------|
| 1 | 空载反电动势 | Transient | BEMF波形、THD、齿槽转矩 |
| 2 | 额定负载 | Transient | 平均/脉动转矩、效率、功率因数 |
| 3 | 过载(2xI_rated) | Transient | 转矩能力、饱和检查 |
| 4 | 气隙磁密 | Transient/Static | Bg空间波形、FFT谐波、饱和云图 |
| 5 | 电感(Ld/Lq) | Static | 冻结磁导率法 |
| 6 | 铁耗分布 | Transient | 铁耗分布、热点识别 |
| 7 | PM涡流损耗 | Transient | 有/无分段PM损耗 |
| 8 | 热稳态 | Transient+Thermal | 绕组温度、热点裕度 |
| 9 | 退磁 | Transient | 高温短路、PM中B_min |
| 10 | NVH快速扫描 | Transient+FFT | 径向力密度谐波、共振风险 |

### 4. 槽型切换系统

| 槽型 | 适用 | 参数集 |
|------|------|--------|
| `rectangular` | 简单电机/教学 | Bs0, Bs2, Hs0, Hs2 |
| `pear`（梨形） | 高性能PMSM | Bs0, Bs1, Bs2, Hs0, Hs1, Hs2, Rs |
| `trapezoidal` | 大功率电机 | Bs0, Bs1, Hs0, Hs1, Hs2 |
| `round` | 特殊应用 | 直径, 深度 |

参数合法性由 `scripts/param_validator.py` 自动校验（11个尺寸约束）。

### 5. 永磁拓扑切换系统

| 拓扑 | 结构 | 适用 | 特点 |
|------|------|------|------|
| `SPM` | 磁钢贴转子表面 | 伺服/低速 | 结构简单、弱磁弱 |
| `IPM_Flat` | 矩形磁钢埋入 | EV驱动 | 弱磁强、凸极效应 |
| `IPM_V` | V型双磁钢 | 高性能EV | 最强弱磁、高功率密度 |
| `IPM_Spoke` | 辐条状 | 高转矩密度 | 聚磁效应 |

### 6. 仿真收敛保证

每次仿真自动：
1. 验证网格质量（气隙≥3层单元）
2. 检查时间步（≥100步/电周期）
3. 验证收敛（能量误差<0.5%或转矩脉动<1%）
4. 不收敛自动调整：细化网格→减半时间步→重试（最多3次）

### 7. MCP代码质量

内嵌代码审查：
- 每次`run_script()`调用验证ANSYS COM API正确性
- `_safe()`死锁检测与规避
- 材料名称与Maxwell库校验
- 依赖版本兼容性检查

---

## 多物理场仿真能力 (v4.0 新增)

### 8. 多物理场耦合矩阵

| 耦合类型 | 物理场 | 典型应用 | 求解策略 |
|---------|--------|---------|---------|
| 热-电耦合 | 温度+电流 | IGBT结温、母排焦耳热 | 双向弱耦合 |
| 热-力耦合 | 温度+应力 | 焊层疲劳、热膨胀 | 顺序耦合 |
| 热-电-力三耦合 | 温度+电流+应力 | IGBT封装可靠性 | 分步顺序耦合 |
| 电磁-结构耦合 | 电磁+应力 | 转子高速强度 | 单向（电磁→结构） |
| 电磁-热耦合 | 电磁+温度 | 电机损耗发热 | 双向迭代 |
| 电磁-热-结构三耦合 | 电磁+温度+应力 | 电机全耦合分析 | 顺序链式 |

### 9. 电机多学科联合仿真

**三大模块自动化：**

| 模块 | 工具链 | 脚本接口 | 输出 |
|------|--------|---------|------|
| 电磁学 | RMxprt → Maxwell2D/3D | PyAEDT | 转矩、损耗、磁密云图 |
| 结构静力学 | SpaceClaim + Mechanical | ACTPython | 位移、应力、应变云图 |
| 流固耦合热 | Maxwell3D + Fluent | PyFluent | 温度场、流速云图 |

**数据流转：**
```
电磁场仿真 → 损耗（铜耗+铁耗+涡流耗） → 热仿真热源
电磁场仿真 → 径向力密度 → 结构仿真载荷
全部数据 → SQLite 9个专项数据库统一管理
```

```bash
python scripts/mdao_orchestrator.py motor
```

### 10. IGBT 封装可靠性分析

**7层器件结构建模：** Cu主端子 → Pb-Sn焊层 → Al覆层 → AlN绝缘层 → Al覆层 → Pb-Sn焊层 → AlSiC基板

**功率循环工况（GB/T 29332）：** 4载荷步/120s周期

**Anand粘塑性本构模型：** 描述焊层钎料弹性+塑性+蠕变

**疲劳寿命预测：**

| 模型 | 理论基础 | 公式 | 适用 |
|------|---------|------|------|
| Coffin-Manson | 基于应变 | N_f = A(Δε_in)^m | 快速估算 |
| Darveaux | 基于能量 | N_0=C₁(ΔW)^C₂; da/dN=C₃(ΔW)^C₄ | 更准确，反映微观退化 |

**参数化研究：**
- 孔洞率扫描（0%~10%，生死单元技术）
- 焊层厚度扫描（20~120μm，80μm附近最优）

```bash
python scripts/mdao_orchestrator.py igbt
```

### 11. 多学科数据管理

**SQLite 9个专项数据库：**

| 物理场 | 几何库 | 材料库 | 计算库 | 结果库 |
|--------|--------|--------|--------|--------|
| 电磁场 | em_geometry | em_material | em_calc | em_result |
| 应力场 | struct_geometry | struct_material | struct_calc | struct_result |
| 温度场 | thermal_geometry | thermal_material | thermal_calc | thermal_result |

### 12. 多目标优化（OptiSlang）

- **敏感性分析：** 实验样本点设计、取样方法
- **优化变量：** 电机结构参数（定子/转子/绕组/永磁体）
- **优化目标：** 电磁性能、散热性能、机械强度、振动噪声
- **输出：** 响应面、相关性矩阵、Pareto图、最优参数

---

## 工流

### 电机电磁设计工作流

```
Phase 0 — 输入评估
  ├─ 参数完整？→ 跳到 Phase 3
  ├─ 参数部分？→ Phase 1 自动补全
  └─ 仅1-2参数？→ Phase 2 自动补全+优化

Phase 1 — 自动补全缺失参数 → motor_param_calc.py
Phase 2 — 寻找最优设计 → motor_optimizer.py
Phase 3 — 构建Maxwell模型（8阶段几何-求解管线）
Phase 4 — 运行仿真套件（空载→负载→气隙→损耗→退磁→热→NVH）
Phase 5 — 生成工程报告（Markdown→PDF，含全部图表）
```

### 电机多学科联合仿真工作流 (MDAO)

```
Phase 0 — 输入电机参数（功率/转速/电压/极槽/尺寸/冷却）
Phase 1 — 电磁场仿真（Maxwell2D/3D）
  ├─ 几何：定子→绕组→磁钢槽→永磁体→空气槽→转子
  ├─ 输出：电磁转矩、损耗（铜耗+铁耗+涡流）、磁密、力密度
Phase 2 — 结构静力学仿真（Mechanical）
  ├─ 载荷：电磁径向力 + 离心力
  ├─ 输出：位移、等效应力、剪应力、应变、安全系数
Phase 3 — 流固耦合热仿真（Fluent）
  ├─ 热源：电磁损耗（铜耗+铁耗+涡流耗）
  ├─ 输出：绕组温度、磁钢温度、转子温度、流速
Phase 4 — 多学科综合评估（效率/强度/温升 pass/fail判定）
Phase 5 — 多目标优化（OptiSlang，可选）
```

### IGBT 封装可靠性分析工作流

```
Phase 0 — 输入IGBT参数（功率密度/焊层厚度/孔洞率/环境温度）
Phase 1 — 结温分析（温度场）
  ├─ 7层结构建模 + 功率循环载荷（4步/120s）
  ├─ 输出：最高结温、焊层温度、温度波动
Phase 2 — 变形分析（位移场）
  ├─ 输入：温度场
  ├─ 输出：最大位移（~1μm级）
Phase 3 — 应力分析（应力场）
  ├─ 输入：温度场 + 变形
  ├─ 输出：最大应力、非弹性应变、应变能密度
Phase 4 — 疲劳寿命预测
  ├─ Coffin-Manson（基于应变）
  ├─ Darveaux（基于能量，更准确）
Phase 5 — 参数化研究（可选）
  ├─ 孔洞率扫描（0%~10%）
  ├─ 焊层厚度扫描（20~120μm）
  └─ 输出：最优焊层厚度
```

## Maxwell建模管线

### 阶段A — 几何建模
1. 设置单位(mm)
2. 绘制Band圆（气隙中心）
3. 绘制Shaft + OuterRegion
4. 定子铁心（外圆-内圆）
5. 生成单槽→阵列Q个→布尔减法
6. 生成单极磁钢→阵列2p个
7. 转子铁心 + 线圈截面

槽型几何由 `scripts/slot_builder.py` 生成，永磁体由 `scripts/pm_builder.py` 生成。

### 阶段B — 材料
- 12种硅钢牌号（M235至非晶）
- 14种PM牌号（N35至N52SH、SmCo、铁氧体）
- 8种AWG线规（含温变电阻）
- 6种绝缘等级（含热极限）
- **N/S极双磁钢材料**：自动生成N极（磁化径向向外）和S极（磁化径向向内）两种材料定义

### 阶段C — 绕组（自动生成）
- 常用极槽配合预计算绕组表
- 非常用组合用**星形图法**自动生成线圈-相位分配
- **`scripts/pmsm_winding_builder.py`** 自动生成AssignCoilGroup和AddWindingCoils脚本
- 支持**双层分布绕组**，每相12个线圈（6+ / 6-）

#### 关键概念：线组位置（Winding Position）— AI 必须理解

**为什么这很重要**：AI 接进来建模时，最大失败原因是**看不懂输出脚本里的槽-相-极性对应关系**，导致改写/调试时改错相位、极性反转。**必须按本节规则理解 winding.py**。

##### 1. 两种绕组拓扑的关键差异

| 拓扑 | 槽极对 | q = slots/(3×极对) | 相位带规律 | 极性 |
|------|--------|---------------------|------------|------|
| **整数槽分布式** | 36s/4p, 48s/8p, 24s/4p | q=2,3,4 整数 | A+/A-/B+/B-/C+/C- 每相带 q 槽 | 每相带前 q 槽=+，后 q 槽=− |
| **集中绕组** | 8p12s, 12p18s, 6p9s | q=0.5 | A+/A-/B+/B-/C+/C- 每相对极 1 槽 | Maxwell 双层 y=1 内部反转 bot |

##### 2. winding.py 输出长这样（AI 必须会解读）

```python
# 头部有自动 print 出的完整相位带表 (★=N 极下电流方向+, ·=S 极下-)
# Slot_ 1   A+    [A+] ★   上 N 极下
# Slot_ 2   A-    [A-] ·   下 S 极下
# Slot_ 3   B+    [B+] ★   上 N 极下
# ...

# AssignCoilGroup 把"同相+同极性"的所有 Coil_xxx 槽位归一组
oModule.AssignCoilGroup(["NAME:A+", "Objects:=", ["Coil_1", "Coil_3", "Coil_5", ...], ...])
oModule.AssignCoilGroup(["NAME:A-", "Objects:=", ["Coil_2", "Coil_4", "Coil_6", ...], ...])
# ...
# AddWindingCoils 把 + / - 线圈组连到对应相绕组
oModule.AddWindingCoils("WindingA", ["A+", "A-"])
```

##### 3. AI 调 winding builder 的标准算法（v3 工业标准 Pyrhonen 公式）

```python
# 整数槽分布式公式 (q≥1 整数):
相索引 = (s * pole_pairs) // (slots // 3)  mod 3
极性   = '+' if (s // q) % 2 == 0 else '-'
其中 s = 0-indexed 槽号, q = slots / (3 * pole_pairs)
```

##### 4. 改/调试规则（AI 改相位前必读）

- **加新槽位**：用 builder 输出 `WindingConfig.slot_map[s] = (phase, polarity)`，**不要**手动算电角
- **改极性**：直接调 `WindingConfig.slot_map`，不要碰 `coil_to_phase` / `coil_to_polarity`（内部已废弃字段）
- **验证方法**：跑 `pmsm_winding_builder.WindingBuilder(slots, poles, phases=3).compute_winding()` 检查 `slot_map`、`coil_groups`、`winding_factor`，kw 应接近 0.866 (q=1) / 0.933 (q=0.5) / 0.96 (q=3) / 0.95 (q=4)
- **失败信号**：`winding_factor < 0.5` 或 +/- 不均（>30% 不平衡）= 算法走兜底分支，应检查槽极配合
- **保留 Token**：实际 Maxwell 调用只跑 builder 一次，把结果嵌进脚本（`output_scripts/winding.py`），不要在 AEDT 里再算

### 阶段D — 仿真配置
每种仿真预置配置见 `references/simulation_configs.md`

### 阶段E — 结果提取与绘图
1. `get_solution_data()` → 原始时间序列
2. Python处理 → 均值、脉动、FFT、THD
3. `create_report()` → Maxwell原生图
4. `export_data()` → CSV自定义绘图

---

## Prompt模板

### 最小输入

```
设计一台电机。我只知道：
- 功率：500W
- 转速：3000rpm
自动计算其余参数，优化最高效率，建模，跑空载+额定负载+气隙磁密仿真，生成报告。
```

### 完整规格

```
设计SPMSM：
功率500W，3000rpm，48V DC母线，8极12槽，外径80mm，长度50mm。
优化磁钢厚度追求最高效率，成本≤¥180。
运行：空载、额定负载、2x过载、气隙BFFT、150°C退磁。
生成完整报告含全部图表。
```

### 带拓扑选择

```
设计IPM_V电机：
功率10kW，6000rpm，310V，8极48槽，外径180mm，长度120mm。
槽型：梨形槽
永磁拓扑：内置V型(IPM_V)
运行全部10种仿真，生成NVH报告。
```

### 自定义参数输入

支持多种参数输入方式：

```bash
# 关键词输入
python main.py --params "slots=36 poles=8 stator_od=210 stator_id=136"

# JSON输入
python main.py --json '{"slots":36,"poles":8,"stator_od":210}'

# CSV输入
python main.py --csv "slots,36\npoles,8\nstator_od,210"

# 文件输入
python main.py --input params.txt

# 交互式输入
python main.py --interactive

# 使用预设
python main.py --preset 8p36s_tutorial    # 教程模式（N/S极磁钢+自动绕组）
python main.py --preset 8p12s_servo       # 8极12槽伺服电机
python main.py --preset 36slot_industrial  # 36槽工业电机
python main.py --preset 8p12s_ipm_ev      # 8极12槽IPM_V电机
```

### Codex System Prompt

```
SYSTEM: 你是Maxwell电机设计和FEA自动化智能体。
可调用 references/mcp_tools_reference.md 中全部MCP工具。

设计原则：
1. 自动补全缺失参数——不要让用户自己算
2. 保守首版→验证→仅在不达标时优化
3. 仿真按序执行：先空载验证模型，再负载，最后专项
4. 每一步仿真前验证、后检查
5. 所有结果标注与设计目标的通过/不通过
```

### 多物理场联合仿真

```
对这台电机做多学科联合仿真：
功率10kW，6000rpm，310V，8极48槽，外径180mm，长度120mm，水冷。
1. 电磁场：转矩、损耗、磁密
2. 结构：转子应力（电磁力+离心力）
3. 热：绕组温度、磁钢温度
输出各物理场pass/fail判定。
```

### IGBT 可靠性分析

```
分析IGBT封装可靠性：
- IGBT芯片发热功率密度：1.69e9 W/m³
- FRD芯片发热功率密度：1.14e9 W/m³
- 焊层材料：Pb-Sn
- 焊层厚度：80μm
- 功率循环：GB/T 29332，120s周期
运行热-电-力耦合仿真，预测焊层疲劳寿命（Coffin-Manson + Darveaux），
并扫描焊层厚度20~120μm找最优值。
```

---

## 参考资源

| 文档 | 内容 |
|------|------|
| `references/motor_design_guide.md` | 设计理论、公式、材料库、绕组拓扑、冷却限制、BOM成本模型 |
| `references/mcp_tools_reference.md` | Maxwell MCP工具完整目录（全部工具）含参数签名和用法 |
| `references/troubleshooting.md` | 调试指南：连接、几何、求解器、多物理场故障 |
| `references/optimization_guide.md` | 优化算法（NSGA-II/PSO/Grid/Bayesian）、目标函数、约束处理 |
| `references/simulation_configs.md` | 10种仿真类型预置配置含求解器设置、网格方案、期望输出 |
| `references/multiphysics_guide.md` | **多物理场耦合仿真指南：耦合矩阵、IGBT 7层结构、Anand模型、疲劳寿命、参数化研究** |
| `MCP_Server.md` | MCP Server完整文档和源代码 |
| `AutoFlow.md` | 全流程操作手册 |

## 脚本

| 脚本 | 功能 |
|------|------|
| `scripts/maxwell_bridge.py` | **统一 MCP 抽象层（唯一接口边界）**：封装 71 个 MCP 工具 + 15 个缺口补救方法；项目脚本只经此层访问 Maxwell，`dry_run` 免软件即可跑通。**v4.3 起 `backend="mcp"` 真正经 `mcp_connector` 调用 `D:\mcp-maxwell\server.py` 的 71 个工具**（含 71 个参数适配器收敛签名差异/单位转换），服务端或 Maxwell 不可用时自动降级 text/dry_run |
| `scripts/mcp_connector.py` | **★v4.3 新增 MCP 链接工具★**：以子进程启动 `D:\mcp-maxwell\server.py`，经 stdio 建立 `mcp.ClientSession`，把工具调用真正路由到 ANSYS Maxwell COM 层。同步 API（后台 asyncio 线程 + 请求队列），Windows ProactorEventLoop 兼容，服务端路径自动发现（`MAXWELL_MCP_SERVER` 环境变量 → `D:\mcp-maxwell\server.py` → skill 内 `mcp-maxwell/server.py`） |
| `scripts/motor_param_calc.py` | 解析参数计算器+自动补全 |
| `scripts/motor_optimizer.py` | 多目标设计优化器（NSGA-II/PSO/Grid/Bayesian） |
| `scripts/motor_config.py` | 中心配置类（MotorConfig dataclass、N/S极材料、自定义输入） |
| `scripts/param_validator.py` | 参数合法性校验（11个尺寸约束） |
| `scripts/slot_builder.py` | 槽型几何生成器（矩形/梨形/梯形/圆形） |
| `scripts/pm_builder.py` | 永磁体几何生成器（SPM/IPM_Flat/IPM_V/IPM_Spoke） |
| `scripts/pmsm_winding_builder.py` | **PMSM绕组生成器（星形图法自动分配线圈-相位，支持任意槽极配合）** |
| `scripts/main.py` | 主入口（MotorModelBuilder一键建模，支持预设/JSON/CSV/关键词/交互式输入） |
| `scripts/mdao_orchestrator.py` | **多物理场仿真编排器：电机MDAO + IGBT可靠性 + 疲劳寿命 + 参数化扫描 + SQLite数据库** |
| `archive/maxwell2d.py`, `archive/maxwell2d_25nm.py` | 遗留异步电机建模器（已归档，与本项目 PMSM+MCP 架构无关） |

### 25Nm PMSM 项目（`projects/25Nm_PMSM/`）

统一经 `scripts/maxwell_bridge.py` 访问 Maxwell，13 步管线由 `run_all_simulations.py` 编排：

| 步 | 脚本 | 分析 |
|----|------|------|
| 1 | `01_build_geometry.py` | 几何建模 |
| 2 | `02_materials_and_excitation.py` | 材料与激励 |
| 3 | `03_no_load_bemf.py` | 空载反电动势 |
| 4 | `04_rated_load.py` | 额定负载 |
| 5 | `05_airgap_flux_density.py` | 气隙磁密 |
| 6 | `06_overload_capacity.py` | 过载能力 + 退磁 |
| 7 | `07_loss_separation.py` | 铁损分离 |
| 8 | `08_mtpa_sweep.py` | MTPA 扫描 |
| 9 | `09_thermal_analysis.py` | 瞬态热分析 |
| 10 | `10_structural_analysis.py` | 结构强度 |
| 11 | `11_nvh_scan.py` | NVH 扫描 |
| 12 | `12_pm_eddy_loss.py` | PM 涡流损耗 |
| 13 | `13_inductance.py` | 电感 Ld/Lq |

> 配置：`projects/25Nm_PMSM/pmsm_config.py`（项目扁平配置，与 `scripts/motor_config.py` 中心配置类命名空间隔离，避免同名冲突）。
> 运行：`cd projects/25Nm_PMSM && MAXWELL_DRY_RUN=1 python run_all_simulations.py`（dry_run 免 Maxwell 即可跑通全链路）。

---

## MCP 链接工具（v4.3 新增）

**背景**：此前 `maxwell_bridge.py` 自称"唯一 MCP 抽象层"，但实为 mock/脚本生成器——`dry_run=True` 返回假值，`dry_run=False` 仅生成 IronPython 脚本文本而**从不真正连接** `D:\mcp-maxwell\server.py`。v4.3 补齐这一缺口：新增 `scripts/mcp_connector.py` 作为真正的 MCP 客户端，并给 bridge 增加 `backend="mcp"` 实算路径。

### 三种后端

| 后端 | 构造方式 | 行为 | 适用 |
|------|---------|------|------|
| `dry_run` | `MaxwellBridge(dry_run=True)`（默认） | 返回 mock 值，免 Maxwell 免服务端 | CI、逻辑链路验证、教学 |
| `text` | `MaxwellBridge(dry_run=False, backend="text")` | 生成 IronPython 脚本文本供外部打包执行 | 离线脚本生成、审计 |
| `mcp` ★ | `MaxwellBridge(dry_run=False, backend="mcp")` | **真正子进程启动 `D:\mcp-maxwell\server.py`，经 stdio MCP 协议调用 71 个工具，实算结果回传** | 接真实 ANSYS Maxwell 实算 |

### 用法

```python
from maxwell_bridge import MaxwellBridge

# 实算：接真实 Maxwell（需 Maxwell 已启动 + pywin32）
bridge = MaxwellBridge(dry_run=False, backend="mcp")
bridge.set_model_units("mm")
bridge.draw_circle("Stator_Outer", x=0, y=0, radius=40)   # 真正调 server.draw_circle
bridge.assign_material("Stator_Outer", "M235_35A")
bridge.analyze("Setup1")
bridge.close()  # 关闭子进程

# 也可直接用连接器（绕过 bridge，直调 71 个工具）
from mcp_connector import MCPConnector
conn = MCPConnector()
conn.connect()
print(conn.list_tools())                       # 71 个工具名
print(conn.call_tool("get_maxwell_status", {}))
conn.run_script('oEditor.SetModelUnits(...)')  # 直接执行 IronPython
conn.close()
```

### 配置

- **服务端路径发现优先级**：环境变量 `MAXWELL_MCP_SERVER` → `D:\mcp-maxwell\server.py` → skill 内 `mcp-maxwell/server.py`
- **依赖**：`pip install "mcp>=1.0.0,<2.0.0"`（本机已装）；服务端另需 `pywin32>=306` + ANSYS Electronics Desktop 已启动
- **降级**：`mcp` 包未装 / 服务端起不来 / Maxwell 未连接 → bridge 自动降级为 `text`/`dry_run` 并打印 `[Bridge] ...` 提示，流程不中断
- **适配器**：`MCP_ADAPTERS`（71 个）把 bridge 调用签名收敛到 server 工具签名（如 `subtract(blank_parts=...)` → `subtract_objects(blank_objects=...)`、数值 `40` → `"40mm"`、`create_design` 补默认 `design_type="Maxwell 2D"`）；少数 bridge 缺服务端必需参数的工具（如 `add_turns_to_winding` 缺 `objects`）自动回退 `run_script` 兜底

### 自检命令

```bash
python scripts/mcp_connector.py          # 连接器自检（无需 Maxwell）
python debug/test_bridge_mcp.py          # bridge 三后端集成测试
```

---

## 拓扑参数速查

### SPM
```python
{"pm_thickness": 3.0, "pm_pole_arc": 0.85, "pm_gap": 0.5}
```

### IPM_Flat
```python
{"pm_thickness": 2.5, "pm_width": 15.0, "pm_offset_r": 5.0, "pm_bridge": 1.0}
```

### IPM_V
```python
{"pm_thickness": 2.5, "pm_width": 12.0, "v_angle": 120.0, "v_center_offset": 3.0, "pm_bridge": 0.8}
```

## 设计规则速查

| 规则 | 公式 | 适用 |
|------|------|------|
| 气隙长度 | δ = 0.2 + Dro/1000 mm | 所有电机 |
| 磁钢厚度 | hm ≥ 3δ (SPM) | 防过度漏磁 |
| 槽口宽度 | bs0 = 3~5δ | 齿槽转矩权衡 |
| 齿宽 | wt ≈ 槽距/2 | 等磁通面积 |
| 轭部厚度 | hy = τp×Bg/(2×Bsat) | 防饱和 |
| 电负荷 | A = m×Nph×I/(π×Dsi) | <40000A/m自然冷却 |
| 电流密度 | J = 4~8 A/mm² | 取决于冷却 |

## 绕组拓扑推荐

| 极/槽 | Kw | LCM | 齿槽转矩 | 推荐 |
|-------|-----|-----|---------|------|
| 8p12s | 0.933 | 24 | 中 | 伺服电机 |
| 10p12s | 0.933 | 60 | 低 | 低齿槽应用 |
| 8p9s | 0.945 | 72 | 极低 | 高精度 |
| 4p12s | 0.933 | 12 | 高 | 简单应用 |

---

## 关键数据流陷阱 (Critical Data Flow Pitfalls)

> ⚠️ 以下是在实际使用中已发现的坑位，使用前务必检查。

### P1. 电磁损耗 → 热仿真的单位一致性

`_run_electromagnetic()` 输出 `copper_loss` / `iron_loss` / `pm_eddy_loss`，在 `run_motor_mdao()` 中直接求和传给 `_run_thermal()` 作为热源。

**陷阱：** 三个损耗项的单位必须统一（W 或 kW），且必须确认它们来自同一求解器的同一物理量基准。实际 Maxwell FEA 输出常以 W 为单位，但部分场景（如每周期能量）可能以 J/cycle 输出。

**强制要求：**
- 在 `_run_electromagnetic()` 返回值中显式标注单位：`# 单位: W (瓦特)`
- 在 `_run_thermal()` 输入处加断言：`assert all(v > 0 for v in [copper_loss, iron_loss, pm_eddy_loss])`
- 不同损耗对温度场的影响权重不同（铜耗集中在绕组，铁耗分布在铁芯），如需精确分配应引入位置权重因子

### P2. IGBT 三阶段函数的可见性

`_run_igbt_thermal()` → `_run_igbt_deformation()` → `_run_igbt_stress()` 三个方法均定义在 `scripts/mdao_orchestrator.py` 的 `MDAOOrchestrator` 类内部（约第595行起）。

**陷阱：** 部分 agent/编辑器在读取大文件时可能发生截断或跳过，导致误判"函数不存在"。

**确认方法：** 直接搜索 `def _run_igbt_` 确认三个方法都在同一文件中。

### P3. 疲劳寿命模型参数溯源

`FatigueLifePredictor` 中 Coffin-Manson (A=0.159, m=-1.98) 和 Darveaux (C1=22400, C2=-1.52, C3=5.86e-7, C4=0.98) 的参数**仅适用于 Pb-Sn 共晶焊料**。

**陷阱：** 不同钎料（如 SAC305 无铅焊料、Au-Sn）的参数完全不同。换材料必须同步更新 `COFFIN_MANSON_PARAMS` 和 `DARVEAUX_PARAMS`。

**参数来源：** 基于中车株洲所 IGBT 多物理场仿真论文（Ansys 2025 全球仿真大会获奖论文）中的 Pb-Sn 焊层疲劳试验数据。

### P4. 多物理场耦合求解策略选择

| 场景 | 推荐策略 | 原因 |
|------|---------|------|
| 电机电磁→结构 | 单向（电磁力作为结构载荷） | 结构变形对电磁场影响可忽略 |
| 电机电磁→热 | 双向迭代 | 温度升高改变电阻率，影响损耗 |
| IGBT 热→电→力 | 顺序链式 | 温度→变形→应力逐级传递，无强回耦 |

---

## 调试与系统限制 (Debugging & System Limitations)

### L1. 沙箱路径限制

`MDAOOrchestrator` 默认 `work_dir` 和 `db_path` 使用绝对路径，避免沙箱环境相对路径报错。Demo 输出目录使用 `tempfile.gettempdir()` 避免写入被拦截。

### L2. 无 ANSYS 环境时验证

所有仿真方法支持 `dry_run=True` 模式：跳过实际 Maxwell/Mechanical/Fluent 调用，使用工程估算值验证逻辑链路。适用于：
- CI/CD 流程验证
- 参数接口检查
- 工作流连通性测试

### L3. PyAEDT / PyFluent 依赖与版本兼容

实际运行（dry_run=False）需要安装：
```bash
# 必须在 Python 3.10~3.12 环境安装（ansys-aedt-core 0.10+ 无 3.13 wheel）
pip install ansys-aedt-core ansys-fluent-core
```
- **Python 版本**：当前 managed 运行时为 3.13.x，无对应 wheel，import 会失败。PyAEDTBackend 构造即抛 RuntimeError，由 orchestrator 捕获并降级 DryRun（不影响流程跑通）。
- **本机环境**：Maxwell/Electronics Desktop 在 `D:\Program Files\AnsysEM\AnsysEM21.1`（对应 `aedt_version="2021.1"`）；Fluent/Mechanical/Icepak 在 `F:\Program Files\ANSYS Inc\v252`（对应 `fluent_version="252"`）。注意 v252 未装 Electronics Desktop，电磁实算必须连 21.1。
- **未安装/版本不符时**：自动降级为估算模式并打印 `[Note]` / `[Warning]`，整条 MDAO 链不会因单个 solver 不可用而中断。
- **自检**：`python mdao_orchestrator.py check` 打印本机 ANSYS 安装、PyAEDT/PyFluent 可用性、Python 兼容性及建议。

### L4. 大文件读取限制

部分 AI agent 在读取超过 400 行的 Python 文件时可能截断。建议：
- 按类/方法拆分检查任务
- 用 `grep "def method_name"` 确认方法存在
- 关键参数集中在 `MDAOConfig` 和 `FatigueLifePredictor` 两个类中

---

## DryRun → 实算切换 (v4.2 新增)

编排器通过**后端抽象（Strategy 模式）**在估算与真实 FEA 之间无缝切换，调用方代码无需改动。

### 切换机制

`MDAOOrchestrator(config)` 在构造时按 `config.dry_run` 决定后端：

| `dry_run` | 行为 | 后端 |
|---|---|---|
| `True` | 走内联集总参数估算，不触碰 ANSYS | `self.fea_backend = None` |
| `False` | 尝试 `from solver_backends import PyAEDTBackend` 加载真实 FEA 后端 | `self.fea_backend = PyAEDTBackend(config)` |

加载失败（PyAEDT 未装 / Python 版本不兼容 / ANSYS 未授权）时**捕获异常并降级 DryRun**，打印 `[Backend] PyAEDT 不可用，降级 DryRun 估算: ...`，流程不中断。

### 调用路由（`_run_*` 方法）

六个物理场方法统一先问询后端：
```python
def _run_electromagnetic(self, params):
    if self.fea_backend is not None:          # 实算后端已加载
        try:
            return self.fea_backend.run_electromagnetic(params)
        except Exception as e:
            print(f"  [Warning] PyAEDT 电磁求解失败，降级 DryRun 估算: {e}")
    else:
        # 无后端：dry_run 明确估算，否则提示未加载后退回估算
        print("  [DryRun] 跳过实际 Maxwell 求解，使用集总估算")
    # ... 内联 DryRun 估算逻辑（降级兜底）...
```
其余 `_run_structural / _run_thermal / _run_igbt_thermal / _run_igbt_deformation / _run_igbt_stress` 同构。

### 后端接口约定（`solver_backends.py`）

`SolverBackend` 抽象基类定义 6 个 `run_*` 方法；所有返回 dict 的 **key 必须与 DryRun 估算完全一致**（见 `solver_backends.py` 头注释），否则下游物理链路会断。当前实现 `PyAEDTBackend`：

- **`Maxwell2d`**（电磁）/ **`Mechanical`**（结构、IGBT 热-力）/ **`pyfluent.launch_fluent`**（热流固耦合）
- **懒加载**：首次用到对应物理场才启动 solver 进程（`_connect_maxwell/_connect_mechanical/_connect_fluent`）
- **两种用法**：
  - A. 驱动已有项目（推荐）：`config.maxwell_project` / `fluent_case` 指向现成 `.aedt` / Fluent case，后端改设计变量→求解→提取结果
  - B. 从零建模：需给出完整几何/材料/网格/边界定义，工作量大，须逐字段校准
- **结果提取辅助**：`_extract_loss/_extract_force/_extract_flux/_extract_scalar/_extract_max_temp` 按 PyAEDT/PyFluent API 校准，失败时返回工程默认值而非崩溃

### 环境自检命令

```bash
python mdao_orchestrator.py check
```
输出：Python 版本、PyAEDT/PyFluent 可用性、版本兼容性（需 3.10~3.12）、Maxwell/Electronics Desktop 与 Fluent/Mechanical 安装路径、以及针对性建议。

### 实算配置要点

实算前须在 `MDAOConfig` 填妥：
- `aedt_version="2021.1"`、`fluent_version="252"`、`non_graphical=True`
- `maxwell_project / maxwell_design / maxwell_setup`（电磁）
- `mechanical_project / mechanical_design / mechanical_setup`（结构、IGBT）
- `igbt_thermal_project / igbt_thermal_setup`（IGBT 热-力）
- `fluent_case`（热流固耦合）

任一项目未配置时 `PyAEDTBackend.run_*` 抛 RuntimeError，由 orchestrator 捕获降级估算（不中断）。

---

## 变更日志

### v4.1 (2026-07-06) — 数据流连通与参数物理化
基于参数体系检查与最小可验证流程搭建，修复以下数据流断裂与参数缺陷：

**数据流连通修复**
- 电机 MDAO：结构仿真 `_run_structural` 接入电磁径向力载荷 `radial_force_density`（电磁→结构耦合原断链）
- IGBT 三阶段：`_run_igbt_deformation` 由 ΔT 计算变形，`_run_igbt_stress` 接入温度+变形输入并计算非弹性应变 `Δε_in`、`ΔW_avg`（原三阶段各自写死、互不相通）
- 疲劳寿命 `FatigueLifePredictor` 现用上游真实 `Δε_in`/`ΔW_avg`，CM≈1.7×10⁵ 次 / Darveaux≈5.5×10⁷ 次（原写死值导致量级失真）

**参数物理化与防护**
- 热仿真 `_run_thermal` 改用集总参数热网络 `ΔT = P_total × R_th`，R_th 按冷却方式可配置（水冷0.05/风冷0.25/自然0.7 K/W），绕组热点从误算 530°C 修正为 125°C
- 电磁/热损耗单位防护（P1）：power、copper_loss 等明确标注单位 W，避免 kW 误用
- 疲劳参数 `COFFIN_MANSON_PARAMS`/`DARVEAUX_PARAMS` 补 Pb-Sn 出处注释，标注换材料须重标定
- 参数化扫描 `_run_parametric_sweep` 基准应变/能量锚定主流程实际值，扫描结果与主流程量级一致

**验证**
- `scripts/test_mdao_chain.py` 全链路 key 传递连通 [PASS]
- `python mdao_orchestrator.py motor|igbt` DryRun 端到端跑通，IGBT 可靠性判定 PASS

---

### v4.2 (2026-07-06) — DryRun → 真实 ANSYS FEA 切换

基于用户需求"接真实 ANSYS FEA（PyAEDT/PyFluent）做 DryRun→实算切换"，落地后端抽象与切换机制：

**新增 `solver_backends.py`（后端层）**
- `SolverBackend` 抽象基类 + `PyAEDTBackend` 真实 FEA 后端（Maxwell2d/Mechanical/PyFluent）
- 懒加载连接（`_connect_maxwell/_connect_mechanical/_connect_fluent`），含结果提取辅助与失败默认值
- `detect_ansys_env()` / `format_report()` 供 `check` 命令做环境自检
- 明确接口约定：所有 `run_*` 返回 dict 的 key 与 DryRun 估算一致

**编排器切换改造（`mdao_orchestrator.py`）**
- `MDAOConfig` 新增 ANSYS 配置字段：`aedt_version/fluent_version/non_graphical` 与各物理场 `project/design/setup`、`fluent_case`
- `__init__` 按 `dry_run` 加载 `PyAEDTBackend`；失败安全降级 DryRun
- 六个 `_run_*` 方法统一路由：后端可用→委托实算，失败/未装→降级估算
- 新增 `check` CLI 子命令（环境自检）
- 电机 demo 新增评估结果打印（`[电机评估] ... 总评=PASS`）

**验证**
- `python mdao_orchestrator.py check` → 正确识别 Python 3.13.12（无 PyAEDT wheel）、Maxwell@21.1、Fluent/Mechanical@v252，给出降级/安装建议 [PASS]
- `motor`/`igbt` DryRun 端到端跑通，电机评估 PASS、IGBT 可靠性 PASS
- `scripts/test_mdao_chain.py` 全链路 key 传递连通 [PASS]
- 降级路径确认：无 PyAEDT 时不抛错、不中断，退回集总估算

---

### v4.3 (2026-08-08) — 补齐 MCP 链接工具（bridge 真正接入 MCP 服务端）

**问题诊断**：经核查，skill 此前**没有真正的 MCP 链接工具**。`maxwell_bridge.py` 名义上是"唯一 MCP 抽象层"，但 `_inject_ironpython()` 仅生成 IronPython 脚本文本并返回（`dry_run=False` 时返回 `# MCP:tool(args,kwargs)` 注释串），从不 spawn 服务端、从不建立 `mcp.ClientSession`、从不调用任何 MCP 工具——全 skill 无任何 `mcp.client` 代码。`D:\mcp-maxwell\server.py` 是一个可用的 FastMCP 服务端（71 工具，stdio），但 bridge 没有客户端去连它。

**新增 `scripts/mcp_connector.py`（MCP 客户端连接器）**
- 以子进程启动 `D:\mcp-maxwell\server.py`，经 stdio 建立 `mcp.ClientSession`，把工具调用真正路由到 ANSYS Maxwell COM 层
- 同步 API（后台 asyncio 线程 + 请求队列，orchestrator 协程持有 stdio/session 上下文），Windows ProactorEventLoop 兼容
- 服务端路径自动发现：`MAXWELL_MCP_SERVER` 环境变量 → `D:\mcp-maxwell\server.py` → skill 内 `mcp-maxwell/server.py`
- `connect/list_tools/call_tool/run_script/close/diagnose`，进程级单例 `get_connector()`

**bridge 改造（`maxwell_bridge.py`）**
- `MaxwellBridge(dry_run=False, backend="mcp")` 新增实算路径：`_mock` 与 `_inject_ironpython` 在 mcp 模式下经连接器真实调用
- `MCP_ADAPTERS`：71 个参数适配器，收敛 bridge↔server 签名差异（命名漂移、位置重排、数值→带单位字符串、补默认 `design_type="Maxwell 2D"`）
- `set_model_units` 同步维护 `_mcp_unit` 供适配器单位转换
- 优雅降级：`mcp` 包未装 / 服务端起不来 / Maxwell 未连接 → 自动回退 `text`/`dry_run`，打印 `[Bridge] ...`，流程不中断
- `dry_run`/`text` 后端 100% 向后兼容

**验证**
- `python scripts/mcp_connector.py` 自检：连 `D:\mcp-maxwell\server.py`，71 工具，`get_maxwell_status` 返回 `未连接到 ANSYS Maxwell` [PASS]
- `python debug/test_bridge_mcp.py`：dry_run 回归 / 适配器覆盖 71/71 / mcp 实调 `get_maxwell_status`+`draw_circle` / 不可用降级 text，4 项全过 [PASS]
- `python scripts/maxwell_bridge.py` 自检：17 项 dry_run 验证通过 [PASS]
- `python scripts/test_mdao_chain.py`：电机 MDAO + IGBT 三阶段全链路无回归 [PASS]

---

*Skill版本：v4.3 | 电机电磁设计v3.0 + 多物理场MDAO | DryRun→真实FEA切换 | **MCP链接工具接入** | 2026-08-08*
