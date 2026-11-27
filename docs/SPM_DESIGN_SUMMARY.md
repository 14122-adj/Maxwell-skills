# 25 N·m SPM 贴片式永磁同步电机 — 设计参数与设计思路

> 生成：2026-11-27。适用对象：当前冻结基线 `commit 1537b44` + 次日计划 `c8494f2`。
> 所有数值来自实际读取的 FEA 结果 JSON / 建模脚本 / 定源文档，凡解析推算均标 `assumption=待验证`。
> 本文是**设计状态汇总**，不是验收报告；判据与失败记录以 `projects/IPM_8p48s/PROBLEM_LEDGER.md` 为准。

---

## 1. 一句话结论

当前电机是 **8 极 48 槽表贴式（SPM）平行充磁 PMSM**，定子 OD150 / 叠长 160 mm，
以 **t_pm=0.45 mm、极弧 0.90、3 切片斜槽 0.75、Imax 13.856 A** 达成
**T_avg 25.0004 N·m（25.0±0.5 目标）、峰峰 3.6022%、主谐波 1.0432%、跳变 1.6277%，四项全 PASS**（401 点 ×3 片真机，独立重算）。
磁钢厚度偏薄（t/g=0.667）是当前唯一实质遗留风险，已排入 11-28 加厚+重算电流的双验证计划。

---

## 2. 配置定源：两套参数不要混淆

| 源 | 拓扑 | 用途 | 当前状态 |
|---|---|---|---|
| `projects/IPM_8p48s/ipm_geom.py::IPMConfig` + `spm_build.py::SPMConfig` | **8 极 / 48 槽** | **当前 SPM 全部 FEA 的真值来源** | ACTIVE |
| `projects/25Nm_PMSM/pmsm_config.py` | 8 极 / 12 槽 | 早期 IPM 规模设计参考；E6/E8 批次走此目录 | 参考，非当前 SPM 几何 |

下文所有"当前设计"均指前者。两套的极数（8）/气隙（0.675）/定子 OD（150）相同，槽数与绕组不同，**数字不可互换**。

---

## 3. 当前设计参数（实测定源）

### 3.1 整机与工况

| 参数 | 值 | 来源 |
|---|---:|---|
| 极数 / 槽数 | 8 / 48 | `SPMConfig.poles/slots` |
| 定子 OD / ID | 150.0 / 93.0 mm | `IPMConfig` |
| 气隙（径向） | 0.675 mm | `SPMConfig.rotor_od - stator_id` |
| 叠长 L | 160.0 mm | `IPMConfig.stack_length` |
| 转子等效 OD | 91.65 mm | `rotor_od = stator_id - 2×airgap` |
| 轴孔半径 | 15.0 mm | `spm_build.SHAFT_R` |
| 额定转速 / 电频率 | 1500 rpm / 100 Hz | `f = p·n/60 = 4×1500/60` |
| 目标转矩 | 25 N·m（判据 22.5–27.5） | `PROJECT_SPEC.md` §7.4 |
| 额定功率（解析） | 3926.99 W | `ipm_m3_load.P_MECH` |
| 母线电压 | 380 V AC（SVPWM 相 RMS 上限 219.4 V） | `SPM_DESIGN.md` §9.1 |

### 3.2 转子与磁钢（当前基线）

| 参数 | 值 | 来源 |
|---|---:|---|
| 拓扑 | 8 块弧形贴片，平行充磁，NSNSNSNS | `spm_magnets()` |
| 贴片厚 t_pm | **0.45 mm** | `spm_snapshot()` |
| 转子铁芯 OD | **90.75 mm** | `SPMConfig.spm_core_od` |
| 极弧系数 | **0.90**（张角 40.5° / 极距 45°） | `SPMConfig.pm_pole_arc` |
| 贴片内 / 外半径 | 45.375 / 45.825 mm | `spm_snapshot()` |
| 装配胶缝 | 0.02 mm（铁芯 r=45.355） | `SPMConfig.pm_glue_gap` |
| Band 半径 | 46.1625 mm（气隙中线） | `spm_snapshot()` |
| AirgapRing | 46.5–46.1625 mm，厚 0.3375 | 同上，`Mesh_Airgap` 0.15 mm |
| t_pm / 气隙、t_pm / 极距 | 0.667、1.25% | 计算 |
| 单块磁钢面积 / 总体积 | 14.49 mm² / 18.6 cm³ | `spm_magnets()` × L |
| 斜槽 | **0.75 槽距**，3 切片机械角 −2.8125°/0/+2.8125°（电角 γ=22.5°） | `spm_skew_slices.py` |

### 3.3 材料与绕组

| 参数 | 值 | 备注 |
|---|---:|---|
| 铁芯 | M270-35A（0.35 mm 硅钢） | BH 从 `JFE_Steel_35JN270` 克隆 66 点（I13 根因修复） |
| 磁钢 | N35 / NdFe35，Br≈1.23 T、Hc≈890 kA/m、μr=1.05 | Br/Hc 标 `assumption=待验证`，需 BOM/datasheet |
| 绕组 | 梨形槽、每槽导体数 cps=10、短距 5 | `ipm_geom.py` I3 定源 |
| 每相匝数 | N_ph=160 | SPM 用双层绕组模型 |
| 槽满率 | Ø1.35 时 ≈0.76（≤0.78） | `wind_wire_mm`，FEA 不依赖此字段 |
| 电流激励 | Imax 13.856 A（峰值）、φ_abs=90°、sign=−1、f=100 Hz | 11-28 起允许重算，见 §7 |

### 3.4 网格与求解

| 项 | 值 |
|---|---|
| 求解器 | Transient / 2D，401 点 / 电周期，步长 50 µs |
| 单元总数 | 56584（`mesh_m2_spm_g03.json`） |
| LengthOp | Band 0.25 / Stator 0.9 / Rotor 1.2 / Mesh_Airgap 0.15 mm |
| 气隙层数 | ≥2（`Mesh_Airgap` 0.15 mm ⇒ 2.58 层，I28） |
| 判据 | T_avg 22.5–27.5 N·m、峰峰 ≤10%、主谐波 ≤5%、跳变 ≤15% |

---

## 4. 设计思路（Observe → Diagnose → Optimize）

### 4.1 为什么从 IPM 换到 SPM

IPM 8p48s 已完成 25 N·m 目标（斜槽 0.75：T_avg 27.0286 / 峰峰 3.2855%），
但隔磁桥漏磁使气隙磁密只有 0.6189 T（G4 要求 0.70–0.90）。用户要求做贴片式平行充磁版本，
同 25 N·m、其他参数不变。SPM 取消隔磁桥，Bg 实测升到 1.0114 T（+63%），
但转矩随之升到 50.28 N·m（×2），于是进入"用磁钢厚度当转矩调节旋钮"的精调链。

### 4.2 厚度单变量扫描（Imax 全程固定，未改电流凑数）

| t_pm | T_avg (N·m) | 峰峰 | 主谐波 | 结果 / 证据 |
|---:|---:|---:|---:|---|
| 2.38 | 50.2821 | 8.531% | 3.606% | FAIL 超转矩，`spm_m3_t238_check.json` |
| 1.30 | 42.0246 | 9.110% | 3.798% | FAIL 超转矩，`spm_m3_t130_check.json` |
| 0.65 | 30.6432 | 10.328% | 4.259% | FAIL 超转矩+峰峰，`spm_m3_t065r_check.json` |
| 0.50（极弧 0.85） | 26.3363 | 10.965% | 4.50% | 峰峰 FAIL，`spm_m3_t050_check.json` |
| 0.50（极弧 0.90） | 26.6968 | 9.963% | 3.037% | 四项 PASS 但偏 25 达 +6.8%，`spm_m3_t050a90_check.json` |
| 0.45（极弧 0.90） | 24.9991 | **10.130% FAIL** | 3.128% | 幅值精确命中，峰峰破 10%，`spm_m3_t045a90_check.json` |

结论：减薄 45% 只降 16% 转矩（非线性），线性外推失效；FFT 定主导为 h=24 槽谐波族。

### 4.3 极弧与斜槽：把峰峰压下来的两支

| 步骤 | 结果 | 判定 |
|---|---|---|
| 极弧 0.80 | 峰峰 14.88% | FAIL，弃 |
| 极弧 0.92 | 峰峰 **10.860%**（比 0.90 恶化 0.73 pt） | FAIL，确认 0.90 为最优点 |
| **斜槽 0.75（3 切片）** | 峰峰 **3.6022%**，h=24 降到 1.0432%，T_avg 保持 25.0004 | **PASS，定为新基线** |

机理：单片峰峰各约 10.12–10.13%，三片按 Δ_elec=Δ_mech×极对数 4 补偿电流相位后逐点平均，
槽谐波相位互补抵消，**直流转矩不降（+0.005%）**。该口径已在 IPM D5 验证（14.08%→3.29%）。

### 4.4 拓扑经验（踩过的坑，勿重踩）

1. 贴片与铁芯严格共面时 Maxwell `Analyze` 报 `PM_x and RotorOuter intersect`（`ValidateDesign` 不报）——
   必须 `Subtract(PM, KeepOriginals=True)` + 0.02 mm 装配胶缝。
2. `AssignBand` 的 `Init Pos` **不旋转几何**——转子初始角只能改几何（现用 `cfg.rotor_init_deg`）。
3. 未求解工程 `ExportMeshStats` 导出空表头，只对已求解工程导。
4. CSV 表头单位随导出路径变（`uN·m`/`mN·m`/`N·m`），`torque_scale()` 按表头自适应。
5. 会话中断留孤儿锁（`.aedt.lock` / `.asol.semaphore`），先清再重跑；日志止于 `MOTION_NAMES` 是中断，不是崩溃。
6. GUI 演示用 `-RunScript` **不带** `AndExit` 且**无管道**（带 `| head -5` 会让 GUI 退出），禁 `AddMessage`。

---

## 5. 当前实测性能（全部 401 点 FEA）

### 5.1 负载转矩（新基线，斜槽 3 片平均）

| 量 | 实测 | 判据 | 状态 | 证据 |
|---|---:|---:|---|---|
| T_avg | **25.0004 N·m** | 22.5–27.5 | PASS | `spm_m3_skew_spm_t045_skew075.json` |
| 峰峰值 | 0.9006 N·m = **3.6022%** | ≤10% | PASS | 同上 |
| 主谐波 h=24 | 0.2609 N·m = **1.0432%** | ≤5% | PASS | 同上 |
| 单点跳变 | **1.6277%** | ≤15% | PASS | 同上 |
| 电流 | 13.856 A（真施加），φ_abs 90° | 固定 | — | 同上 |

### 5.2 空载（旧 t=2.38 点，已过时，仅作参考）

| 量 | 实测 | 判据 | 状态 |
|---|---:|---:|---|
| 相 BEMF RMS | 273.4005 V | 118–145 V | **FAIL（超窗）** |
| 线 BEMF THD | 7.3508% | ≤10% | PASS |
| 齿槽峰峰 | 1.1764 N·m | ≤1.25 | PASS |
| 气隙 \|B\| 峰 | 1.0114 T | 0.70–0.90 T | **FAIL（超上限）** |
| 齿身 / 轭 B 峰 | 1.5890 / 1.2824 T | ≤1.65 / ≤1.50 | PASS |

> 当前 t=0.45 点的空载 BEMF/Bg **未测**（11-28 计划补测）。解析外推 BEMF≈137.8 V，
> 标 `assumption=待验证`，不得当结论。

### 5.3 从零起动曲线（t=0.45 单片，稳态+软启动口径）

| 量 | 实测 | 证据 |
|---|---:|---|
| t=0 转矩 | −0.0003 N·m（≈0） | `m4_start_summary_spm_t045_steady.json` |
| 进入 95% 稳态带 | 19.5 ms | 同上 |
| 峰值 | 25.798 N·m @ 43 ms | 同上 |
| 末段稳态 | 25.094 N·m | 同上 |
| 转速 | 恒定 1500 rpm | 同上 |

口径：`i(t)=−13.856·min(t/0.02,1)·sin(628.3185·t+90°)`；软启动是变频器标准功能，只改建立过程不改稳态。
**未含斜槽**（3 切片 M4 未做）。图：`projects/results/ipm8p48s/spm_m4_start_curve_t045.png`。

### 5.4 E6 退磁 / E8 效率

| 项 | 状态 | 数值 / 说明 |
|---|---|---|
| E6（150°C 三相短路） | **PASS_MIN** | B_min 0.4222 T、SF 2.11（下限 2.0，目标 2.5 未达）；Br −0.12%/K、Hc −0.6%/K 标 `assumption=待验证`；IPM V 型磁钢口径，**不能外推到 0.45 mm 贴片** |
| E8（效率） | **BLOCKED** | M270-35A 的 Kh/Kc/Ke 无明文可导出值；未跑 CoreLoss、未填经验值、`ENGINEERING_ACCEPTANCE.md` η 行未改 |

---

## 6. 文件与证据索引

| 类别 | 路径 |
|---|---|
| 设计定源 | `projects/IPM_8p48s/SPM_DESIGN.md`（§1–§8 实测 + §9 缩小版 + §7.5 新基线） |
| 契约 / 判据 | `projects/IPM_8p48s/PROJECT_SPEC.md` §7/§8/§9 |
| 账本 | `projects/IPM_8p48s/PROBLEM_LEDGER.md`（I31–I35）、`projects/25Nm_PMSM/PROBLEM_LEDGER.md`（E8） |
| 建模 / 校核 | `spm_build.py`、`spm_check.py`、`spm_m3_load.py`、`spm_skew_slices.py`、`spm_sizing_calc.py` |
| 判据重算 | `ipm_m3_check.py`（T_avg/峰峰/主谐波/跳变）、`ipm_mesh_check.py` |
| 结果证据 | `projects/results/ipm8p48s/spm_m3_*_check.json`、`spm_m3_skew_spm_t045_skew075.json`、`mesh_m2_spm_g03.json`、`m4_start_summary_spm_t045_steady.json` |
| 曲线 | `spm_torque_scan.png`、`spm_m4_start_curve_t045.png` |
| 演示方法论 | `docs/DEMO_CASE_M4_TORQUE.md`、`docs/TORQUE_TROUBLESHOOTING.md` |
| 次日计划 | `projects/IPM_8p48s/DAILY_PLAN_2026_11_28.md` |

---

## 7. 遗留风险与 11-28 计划

### 7.1 遗留风险（当前基线达成，不阻塞交付）

1. **磁钢过薄**：t_pm=0.45 mm，t/g=0.667、t/τ=1.25%；机械强度与抗退磁裕度未验证。
2. **空载 BEMF/Bg 超窗**：旧 t=2.38 点实测 273.4 V / 1.0114 T；新 t=0.45 点空载未测。
3. **E8 效率未复核**：铁耗系数 MISSING，效率 93.87% 仍是解析值。
4. **胶缝敏感性**：0.02 mm 胶缝对 Bg 的贡献未做扫描（I32）。
5. **OD120 × L200 / 380V 缩小版**：用户 11-26 追加需求，尚未建模；旧缩放表基于 t=2.38 已作废。
6. **斜槽版 M4**：现有 M4 曲线为单片 t=0.45，未含斜槽。

### 7.2 11-28 13:30 自动化任务（已写入 rrule，未改时间）

用户 11-27 16:32 指令：**增加磁钢厚度、允许改电流、空载与负载双验证、重算电流和厚度**。
解析定源 `spm_sizing_calc.py` 给出（`assumption=待验证`）：

| t_pm | core_OD | I@25Nm | BEMF 推算 | 380V 余量 | 判定 |
|---:|---:|---:|---:|---:|---|
| 0.45（现值） | 90.75 | 13.755 A | 137.79 V | 1.592 | 太薄，弃 |
| **0.65（首选）** | **90.35** | **11.182 A** | **169.74 V** | **1.293** | 厚度 +44%，电流 −19.3% |
| 0.90（备选） | 89.85 | 9.594 A | 198.50 V | 1.105 | BEMF 紧 |
| 1.20 | 89.25 | 8.524 A | 223.07 V | 0.984 | 超 380V 上限，不测 |

执行顺序：开工 gate → 空载 401 点（验 BEMF ≤219.4 V）→ 负载斜槽 3×401 点（验四项判据）→
T_avg 出窗则按 `I_new=11.182×25/T_avg` 微调一次（不改厚度）→ 回写 SPM_DESIGN §7.5 / 账本 I35 /
M4 曲线重出 → commit/push。判据不动、FAIL 不删；118–145 V 原窗若破线只报数，380V 口径由周检裁定。

---

## 8. 复现命令（完整可运行）

```bash
cd "D:/桌面/ANSYS MaxWell_skill"
PY="C:/Users/ASUS/.workbuddy/binaries/python/versions/3.13.12/python.exe"

# 0. 解析定源（只读）
"$PY" projects/IPM_8p48s/spm_sizing_calc.py

# 1. 负载斜槽 3 片（当前基线复现）
"$PY" projects/IPM_8p48s/spm_skew_slices.py \
  --core-od 90.75 --pole-arc 0.90 --imax 13.856 \
  --skew 0.75 --case spm_t045_skew075 --run

# 2. 单片独立重算（逐片）
"$PY" projects/IPM_8p48s/ipm_m3_check.py \
  --csvdir "D:/ANSYS_Run/csv_spm_m3_spm_t045_skew075_s1" \
  --json projects/results/ipm8p48s/spm_m3_load_spm_t045_skew075_s1.json \
  --out projects/results/ipm8p48s/spm_m3_t045_skew_s1_check.json

# 3. 从零起动曲线
"$PY" projects/IPM_8p48s/spm_m4_start.py \
  --core-od 90.75 --pole-arc 0.90 --imax 13.856 \
  --case spm_t045_steady --run
"$PY" projects/IPM_8p48s/ipm_m4_plot.py --case spm_t045_steady \
  --csvdir "D:/ANSYS_Run/csv_spm_m4_spm_t045_steady" \
  --topology "SPM 8p48s 贴片平行充磁 t=0.45 斜槽0.75" \
  --png projects/results/ipm8p48s/spm_m4_start_curve_t045.png

# 4. 回归
"$PY" -m pytest tests/ -q
```

> 求解约 16–18 分钟/401 点、斜槽 3 片约 47 分钟；AEDT 单实例禁止并发，
> 开工先 `tasklist | grep -i ansysedt`，完成看 CSV + `ANALYZE_OK`。
