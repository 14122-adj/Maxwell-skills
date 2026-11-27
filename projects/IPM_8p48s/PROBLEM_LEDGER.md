# IPM 8p48s — 问题账本

> 新项目（2026-11-19 立项）。契约见 `PROJECT_SPEC.md`。
> **2026-11-22 用户修订**：磁钢双层 V（32 块）→ **单层 V（16 块）**；绕组槽内径向一远一近 → **切向 y=0 对称并排**；
> **11-22 二次修订**：绕组截面由异形内缩切分 → **矩形 4 点**（最优 9.800 mm²/条 vs 异形 12.301，−20%，边距 0.2023 mm）。
> 下方 I4/I6/I10 与 M1' 验收表已同步；标「旧版，存档」的行是历史证据，不代表当前配置。
> 严重度：`blocker` > `major` > `minor`；状态：`open`/`in_progress`/`blocked`/`closed`。
> 一天只推进一个问题或一个完整实验组。关闭必须写证据 + 验收值，fail 不删。
> SPM 8p12s 的存量 open 项仍留在 `projects/25Nm_PMSM/PROBLEM_LEDGER.md`，不在本表重复。

| ID | 严重度 | 领域 | 问题 | 证据 / 来源要求 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I1** | blocker | 几何 | 48 槽梨形槽 7 尺寸未定；表 2 的 Bs2=9.5 mm > 48 槽槽距 6.087 mm，照抄必 intersect | `projects/IPM_8p48s/ipm_geom.py::derive_slot`（①–⑧ 推导链）、`projects/results/ipm8p48s/i1_slot.json` | 写出定标推导链 + 齿宽/轭厚约束；`.aedt` 中 48 槽无 intersect | **closed**（2026-11-20） | — |
| **I2** | blocker | 绕组 | 8p48s 双层分布绕组展开图未定（集中绕组 `WINDING_LAYOUT` 不适用） | `ipm_winding.py`、`WINDING_TABLE.md`、`projects/results/ipm8p48s/i2_winding_sides.csv`（96 行） | 48 槽×2 层的相属表齐全，96 个线圈边可逐边 `AssignCoil` | **closed**（2026-11-20） | — |
| **I3** | blocker | 绕组 | 每槽导体数 / 每相匝数 / 线径未定；84 匝是 12 槽口径 | `m2_noload_cps10.json`（401 点 BEMF 127.7440 V）；`ipm_geom.slot_fill_factor`；`m1_build_check_cps10.json` | BEMF 落 118–145 V；槽满率 ≤0.78 | **closed（2026-11-24：cps=10=160 匝定源，真机 401 点 BEMF 127.7440 V 落窗，槽满率 0.7387 PASS；见当日记录）** | 已定源，无后续；残余 FAIL 转 I22 齿槽 / G4 Bg |
| **I4** | blocker | 转子 | **单层 V 型**磁钢尺寸 / V 夹角 / 隔磁桥 / 每极块数（2026-11-22 用户由双层 32 块改为单层 16 块） | `ipm_geom.py::derive_rotor`（`v_single=(26,38,13,3)`） | 8 极×1 组×2 块 = **16 块**；每块留桥、无 intersect | **closed（几何部分）**（11-20 双层 / 11-22 改单层重定源：6/6 PASS，OD 桥 8.356 / 轴孔 9.557 / 同组 3.000 / 极间 4.783） | 磁路/漏磁验证转 I8；**M1' 必须重跑**验收 116 sheet |
| **I5** | major | 电磁 | 斜槽是否保留未定（48 槽分布绕组齿槽本就低，0.5 槽距可能过冲） | 依赖 M2' 空载实测齿槽 | 齿槽 ≤5% 且 BEMF 不出窗 | open | M2' 先跑无斜槽基线 |
| **I6** | major | 几何 | 转子内径 / 轴径未定；30 mm 对 16 块单层 V 磁钢 | 11-22 单层 V：到轴孔最小间隙 **9.557 mm** | 两路径 `rotor_id` 同源 | **closed**（11-20 / 11-22 重算） | 30 mm 保留，理由写入 §3.1 |
| **I7** | major | 数值 | 48 槽网格 / 401 点口径与求解时间未标定 | E1/E2 方法可复用，分辨率数值需按新槽距重定 | medium 网格起；50 vs 25 µs <2%；记录 `ANALYZE_OK` 秒数 | open | M4' 阶段做；M1' 已记录建模 84.0 s |

## 2026-11-20 新增（M1' 当天暴露、尚未到处理时机的项）

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 |
|---|---|---|---|---|---|---|
| **I8** | major | 电磁 | V 型聚磁后的气隙工作磁密：**BH 修复后 M2' 实测 Bg=0.6621 T**（旧无 BH 时 0.063→0.182 T 均为 μr=1 假象）；极轴 Br 0.286 T / 峰 0.653 T | `m2_noload_bhfix.json::flux_density.gap`；`i1_slot.json::flux` | 实测 Bg 回填 I1 磁密三行；Bg ≥0.45 T | **closed（11-22 夜：Bg 0.662 T 回填，达 I16 判据 0.45；G4 0.70–0.90 仍边缘 FAIL）** | 回填 I1：Bg 0.85→0.662 T 假设作废；齿身 0.922 / 轭 0.812 T 均 PASS，不需重定槽宽/轭厚 |
| **I9** | minor | 绕组 | 线圈 0.86 内缩在颈部的单边间隙只有 **0.154 mm**（直身段 0.245），低于真实槽绝缘 0.25–0.3 ⇒ 铜面积偏乐观 | `coil_layers()` + `poly_dist` 实测 | M2' BEMF 若高 2–3%，先查此项再改匝数 | open（assumption=待验证） |
| **I10** | minor | 建模 | 16 块磁钢用了 16 个逐块材料（一块一个方向），可维护性差、材料库较长 | `ipm_build.py::magnet_directions` | M2' 稳定后可合并为 per-object 坐标系；不合并也不影响正确性 | open（记账） |

## 2026-11-20 M1' 证据（真机，不求解）

命令：`ansysedt.exe -RunScriptAndExit D:/ANSYS_Run/ipm_m1_build.py`
日志：`D:/ANSYS_Run/ipm_m1.log`（TEMP）；工程：`D:/ANSYS_Run/IPM_8p48s_M1.aedt`（TEMP）
冻结证据：`projects/results/ipm8p48s/m1_build_check.json`（复核脚本 `ipm_m1_check.py`）

| 判据 | 期望 | 实测 | 偏差 | 判定 |
|---|---:|---:|---:|---|
| `SHEETS` 总数（旧双层，存档） | 132（4 主体 + 32 磁钢 + 96 线圈） | 132 | — | PASS（旧版） |
| 前缀计数（旧双层，存档） | Coil 96 / PM 32 / 其余各 1 | 同 | — | PASS（旧版） |
| 定子面积 | 9018.262 mm²（环 10878.55 − 48×38.756） | 9017.825 | −0.0049% | PASS |
| 转子面积 | 4927.068 mm²（环 − Σ磁钢 963.2） | 4927.068 | 0.000% | PASS |
| 96 线圈面积 | 13.884（上）/ 13.881（下） | 13.881–13.884 | ≤0.003% | PASS |
| 16 磁钢面积（11-22 单层 V） | 36.4（13.0×2.8） | 36.4 | 0.000% | PASS（几何自检 + M1' 矩形真机复核） |
| 磁钢中心镜像 | ±y 对称 | 最大不对称 0.000 mm | — | PASS |
| AEDT 设计校验 | 无 intersect | `VALIDATE_OK` | — | PASS |
| 建模耗时 | — | 84.0 s（旧双层 132 sheet）/ **34.5 s（当前单层 V + 矩形 116 sheet）** | — | 记录 |

## 2026-11-22（矩形绕组 M1' 真机重跑）— 当前配置建模已闭环

> 11-22 两次修订（单层 V 16 块 + **矩形绕组 4 点**）后，此前只做过几何自检（6/6 PASS、
> 468 tests），**矩形版从未上真机**。最后一次 M1 真机是 11-22 凌晨的**异形绕组 12.301**
> 版（`ipm_m1_singleV_hetero.log` 存档，SHEETS=116 / COIL_AREA 12.301 / `M1c.aedt`）。
> 本轮用当前 KEEP 代码 `ipm_build.py` 重新生成脚本并真机重跑，证据已刷新。

命令：`ansysedt.exe -RunScriptAndExit D:/ANSYS_Run/IPM_8p48s_M1_rect.py`（不加 -ng，rc=0）
日志：`D:/ANSYS_Run/ipm_m1.log`（TEMP）；工程：`D:/ANSYS_Run/IPM_8p48s_M1_rect.aedt`（TEMP）
冻结复核：`projects/results/ipm8p48s/m1_build_check.json`（脚本 `ipm_m1_check.py`）——**15/15 PASS**

| 判据 | 期望 | 实测 | 判定 |
|---|---:|---:|---|
| SHEETS = 4 + 16 + 96 | 116 | 116 | PASS |
| 前缀 Coil / PM / Region / StatorOuter / RotorOuter / Band | 96/16/1/1/1/1 | 96/16/1/1/1/1 | PASS |
| 定子面积（环 − 48 槽，偏差%） | ≤0.05 | 0.00485 | PASS |
| 转子面积（环 − Σ磁钢，偏差%） | ≤0.05 | 0.000 | PASS |
| 96 线圈面积（矩形 4 点） | 9.800 mm² | 9.800–9.800（偏差 0%） | PASS |
| 16 磁钢面积 = L×t | 36.4 mm² | 36.4（偏差 0%） | PASS |
| 磁钢中心镜像 | ±y 对称 | 不对称 0.000 mm | PASS |
| AEDT 设计校验 / 工程存盘 / .aedt 存在 | OK/true/true | OK/true/true | PASS |
| 建模耗时 | — | 34.5 s | 记录 |

**交叉校验（矩形 vs 异形，同 116 sheet）**：单条线圈 9.800 vs 12.301 mm²，差 −2.501 mm²；
96 条共 −240.096 mm²。Region 面积由异形版 11459.5237 → 矩形版 11699.5892 mm²，
实测 +240.0655 mm²，与理论 +240.096 差 0.013% ⇒ 线圈确实缩为矩形、无伸出槽外偷面积。
转子面积两版同为 5307.8683 mm²（磁钢几何未动）⇒ 本轮只改绕组截面，磁路保持。
新增：`projects/results/ipm8p48s/m1_build_check.json` [KEEP] 当前矩形版建模证据（覆盖旧双层版）。

## 2026-11-22（M2' 空载）新增

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 |
|---|---|---|---|---|---|---|
| **I11** | minor | 数值 | 齿身磁密快照**位形受限**：48 槽/8 极 ⇒ 极轴每 45° 正好落在槽中心（45/7.5=6），末时刻（t=0.02 s，转子 180°）没有「齿正对极轴」的位形，齿磁密快照偏保守 | `ipm_m2_noload.py::probe_geometry` 注释、gap/tooth 探针角度 | M4' 用多快照或「气隙通量积分/齿宽」交叉定峰值 | open（记账） |
| **I12** | minor | 数值 | `Moving1.Torque` 在本工程导出单位是 **[uNewtonMeter]（微牛·米）**，不是 SPM 模板路径的 `mNewtonMeter`；只认 mN·m 会把 195 µN·m 读成 195 N·m（齿槽虚报 780%） | `csv_ipm_m2/tq_noload.csv` 表头；`ipm_m2_check.py::torque_scale` + `tests/test_ipm_m2.py` 两条回归 | 已修，三前缀（N/mN/µN）全测 | **closed**（2026-11-22） |
| **I13** | **blocker** | 材料 | `M270_35A` 无有效 BH：旧 `EditMaterial` 手工塞 BH 被静默丢弃 ⇒ 铁芯按 **μr=1** 求解 ⇒ Bg 塌陷（旧 0.182 T）。真因不是桥饱和/埋深 | `m2_noload_bhfix.json`（Bg 0.662 T vs 旧 0.182，+264%，401 点）；`m2_noload_apex33.json` | Bg ≥0.45 T（I16）；401 点 FEA 实测 | **closed（11-22 夜：CloneMaterial 修复，Bg 0.662 T 达标；见文末闭环节）** | Bg 已回填 I8=0.662 T；残余 BEMF 63.87 V 转 I3 匝数（cps≈10）、齿槽转 I22 |
| **I14** | major | 材料 | BH 写入方式：2021.1 上 `AddMaterial`/`EditMaterial` 的 `Points`/`Coordinates`/`NAME:Coordinate` 4 种写法**全部不落数值**（探针 bh_probe~7 实证） | `D:/ANSYS_Run/bh_probe*.py`（TEMP）；`ipm_build.py` 改用 `CloneMaterial("JFE_Steel_35JN270","M270_35A")` | 找到 2021.1 真正生效写法 | **closed（11-22 夜：CloneMaterial 克隆系统库厂商 BH，`.aedt` 文本 grep 到 `nonlinear` + `Points[66:]`；见文末）** | 材料名保留 M270_35A（契约）；厂商曲线偏软 ~9% 标 assumption=待验证，FEA 已验 Bg |
| **I15** | major | 材料 | BH 曲线本身缺厂商原始数据，现用「M270-35A 级高磁导 0.35 mm 硅钢」公开量级构造（1.5 T@≈400 A/m、膝点 1.85–1.95 T、50 kA/m@2.05 T） | `ipm_build.py::BH_M270_35A` 注释 | 拿到 datasheet 后替换；膝点 ±5% 对 Bg 的敏感性在 M4' 复算 | open（assumption=待验证） |
| **I22** | **blocker** | 电磁/齿槽 | BH 修复（铁芯真导磁）后齿槽从假象 0.0025 N·m 暴露为真实 **3.4729 N·m（13.9% 额定）**，超 ≤1.25 N·m 判据；极轴/峰 Br=0.438 波形顶部塌陷 | `m2_noload_bhfix.json::torque.pp_nm`（3.4729）→ `m2_noload_bs10.json::torque.pp_nm`（**1.1302**，Bs0=1.0 新几何 401 点） | 齿槽 ≤1.25 N·m（5%） | **closed（2026-11-24：Bs0 2.2→1.0 槽口收窄后齿槽 3.4729→1.1302 N·m，降 67.5%，PASS；见文末当日闭环段）** | 已闭环；斜槽仅作负载脉动优化（I26），不是齿槽达标必要条件 |
| **I16** | **blocker** | 转子 | **单层 V 几何把磁钢埋得太深**：mag 外角到转子 OD 的「桥」实测 **8.356 mm**、极间 **4.783 mm**、到轴孔 9.557 mm。桥区磁密只有 **0.085 T**，离饱和（2 T）差一个数量级 ⇒ 聚磁比 0.72 的设计拿不到气隙磁通，实测 Bg 0.0623 T（异形）/ **0.0630 T（矩形）** vs 解析 0.59 T（只有 **11%** 到气隙） | `i4_rotor.json::radial`、`csv_ipm_points_c/points_mag.csv`、`m2_noload_rect.json::flux_density.gap` | 磁钢外角到 OD ≤ **2.0 mm**、极间 ≤ **2.0 mm**（桥要薄到能被 2 T 饱和，否则"桥饱和"机制不存在）；重跑 M1'/M2' 后 Bg ≥ 0.45 T | **open（最高优先级，矩形版 M2' 复核后仍 FAIL，确认为根因）** | 明日：重定源 `v_single` 使磁钢外角到 OD ≤2.0 mm，改 `derive_rotor` + `IPMConfig`，先几何自检再真机 M1'/M2' |

**I16 定源预研（11-22 解析扫描，assumption=待验证）**：用 `ipm_geom.derive_rotor` 扫
`apex_r∈[26,35] / L∈[11,18] / tilt∈[25,45]°`（thick=2.8、gap_in=3 固定），几何自检 PASS
且 OD 桥 ≤2.5 mm 的候选 53 组。最优几组：(apex,L,tilt)=(33,13,38) OD桥1.549/极间10.141；
(31,14,25) OD桥1.512/极间14.139；(30,17,45) OD桥1.682/**极间2.004**。
**关键矛盾**：OD 桥压到 ≤2.0 后极间桥仍在 2–15 mm，与 I16 验收"极间 ≤2.0"几乎不可兼得
（8 极 V 张角 + 3 mm 内端间距的几何下限）。明日路径须二选一并写理由：①放宽极间判据为
"极间桥饱和即可"（用非线性 BH 实测桥内 B≥1.8 T 替代几何阈值）；②改 gap_in/apex 同时压两者。
当前极间 4.783 mm 时实测桥内仅 0.085 T，说明**厚度不是唯一变量、磁钢埋深更关键**；
优先做①配合 I13 的 BH 生效验证。以上纯解析、未经 FEA，**禁止当设计结论**。

### M2' 矩形绕组版证据（2026-11-22 真机 401 点空载，cps=5）— 当前配置

命令：`ipm_m2_noload.py` 生成 rect 求解脚本 → `ansysedt.exe -RunScriptAndExit`；CSV
`D:/ANSYS_Run/csv_ipm_m2rect/`（TEMP），判定 `projects/results/ipm8p48s/m2_noload_rect.json`。
输入工程 `IPM_8p48s_M1_rect.aedt`（116 sheet，与 M1' 自检同源）；`ANALYZE_OK 470.5 s`，
flux/tq 各 402 行（表头+401），探针 181/46/91 点齐全。独立重算脚本 `ipm_m2_check.py`。

| 量 | 矩形版实测 | 异形版实测（11-22 旧） | 判据 | 判定 |
|---|---:|---:|---|---|
| 相 BEMF RMS | **4.2552 V** | 4.2885 V | 118–145 V | **FAIL** |
| 线 BEMF THD | 0.0375% | 0.0408% | ≤10% | PASS（幅度失真，不作数） |
| 齿槽峰峰 | 3.9e-5 N·m（0.0002%） | 4.75e-5 N·m | ≤5% | PASS（同上） |
| 三相不平衡 | 0.0001% | 0.00013% | ≤2% | PASS |
| 气隙 \|B\| 峰 | **0.0630 T** @21.75° | 0.0623 T | 0.70–0.90 T | **FAIL** |
| 气隙 \|Br\| 峰 / 极轴 | 0.0542 / 0.0542 T | 0.0543 / 0.0543 T | — | 记录 |
| 齿身 B 峰 | 0.0468 T | 0.0468 T | ≤1.65 T | PASS（同上） |
| 轭部 B 峰 | 0.0167 T | 0.0167 T | ≤1.50 T | PASS（同上） |
| 解析交叉 E | 6.6923 V（差 −36.4%） | 6.6934 V（差 −35.9%） | — | 记录 |

**关键诊断（反自演，两版对照）**：绕组截面 12.301 → 9.800 mm²（−20%），BEMF 仅
4.2885 → 4.2552 V（**−0.78%**）、Bg 0.0623 → 0.0630 T（+1.1%）、磁密三行逐位近似。
⇒ ①矩形修订对电磁性能影响 <1%，几何代价可接受；②**BEMF/Bg 塌陷与绕组截面无关**，
根因锁定 I13/I16 磁路（隔磁桥不饱 + 磁钢埋深 8.356 mm），不是 I9 线圈间隙或 I3 匝数。
③匝数反推 cps=139（118 V）/147（125 V）在 9.8 mm² 矩形内**物理放不下**（Ø1.5 线、
单层最多 ~5 根），当属 BEMF 失真下的废数，**禁止当设计结论写进 I3**（与旧版 0.0536
V/匝/相 同源）。结论：I3 保持 open，等 I13/I16 修复、Bg 回到 ≥0.45 T 后再反推。

### M2' 异形绕组版证据（2026-11-22 旧配置，存档，勿作当前性能）

命令：`ipm_m2_noload.py --run` → `ansysedt.exe -RunScriptAndExit`；证据 CSV
`D:/ANSYS_Run/csv_ipm_m2*/`（TEMP），判定 `projects/results/ipm8p48s/m2_noload.json`

| 量 | 实测 | 判据 | 判定 |
|---|---:|---|---|
| 相 BEMF RMS | 2.8848 V | 118–145 V | **FAIL** |
| 线 BEMF THD | 0.4421% | ≤10% | PASS（幅度已失真，不作数） |
| 齿槽峰峰 | 1.95e-4 N·m（0.0008%） | ≤5% | PASS（同上） |
| 三相不平衡 | 0.0098% | ≤2% | PASS |
| 气隙 \|B\| 峰 | 0.0296 T | 0.70–0.90 T | **FAIL** |
| 齿身 B 峰 | 0.0405 T @ r=52.0 mm | ≤1.65 T | PASS（同上） |
| 轭部 B 峰 | 0.0281 T | ≤1.50 T | PASS（同上） |
| `ANALYZE_OK` | 615.2 s（线性 32 块）/ 898.0 s（+BH 32 块）/ 928.3 s（单层 16 块 + BH） | — | 记录（I7） |

**第二次：单层 V 16 块（当前配置）+ BH 去 permeability，401 点 928.3 s**

| 量 | 实测 | 解析/目标 | 判定 |
|---|---:|---|---|
| 相 BEMF RMS | 4.2885 V | 118–145 V | FAIL |
| 气隙 \|B\| 峰 | 0.0623 T | ≈0.59 T（聚磁比 0.72×漏磁 0.7） | FAIL（只有 11% 到气隙） |
| 磁钢上方铁 r=41 / 44 mm | **0.085 / 0.067 T** | 应接近 1.8–2.0 T（饱和） | 说明桥**根本没饱和** |
| 磁钢内部 r=31.6, θ=10° | 0.134 T | ≈1.1–1.2 T | 严重短路 |

⇒ 单层 V 的问题不是 BH，是**几何**：8.356 mm 的铁不是「桥」，是磁短路块。判据「桥要薄到
能被 2 T 饱和」不成立时，任何非线性模型都救不回来（I16）。

**根因（定量，非推断）**：

1. 磁钢正常：磁钢内部 |B| **0.925 T**（定点探针 r=37.4 mm、θ=±5.7°，两侧对称）。
2. 气隙是空的：r=46.30 mm 弧 0→45° 全周 |B| 峰 0.0296 T，极轴只有 0.0130 T。
3. 磁通改走桥：r=44.0 mm 弧在 **12.0° / 32.5°** 出现 **2.67 T** 峰（关于极间轴 22.5°
   对称），极轴处仅 0.197 T ⇒ 磁通从极间隔磁桥短路回相邻极。
4. 磁路估算吻合：桥 3.19 mm / μr 1000 的磁阻 ≈ 气隙 0.675 mm 的 **1/30**；理想磁路
   Bg≈1.08 T 应被压到 1/31 ≈ **0.035 T**，实测 0.0296 T（差 15%，同量级）。
5. SPM 为什么没暴露：8p12s 是表贴、无隔磁桥，线性 μr=1000 只轻微偏乐观（G4b 已 PASS）。
   这是**新项目专属**的建模缺陷，也是 G2「B-H 非线性」的真实代价。

**修复尝试（当天未成功，留证据）**：`EditMaterial` 加 24 点
`[NAME:BHCoordinates]`（`Coordinates:=` 只接受纯数值平铺数组；嵌套 list 会被拒——
"A block func can only have primitives"）。两版：①BH 与 `permeability:=1000` 并存；
②BH 移到数组末位并删掉 `permeability`。两版整机结果与纯线性**逐位相同**
（Bg 0.0296 T、BEMF 2.8848 V）⇒ BH 块被静默丢弃。2021.1 的 `oDefinitionManager`
没有 `GetMaterial` / `GetMaterialNames` / `ExportMaterialsToFile`，材质无法事后读回；
`.aedt` 是二进制，`strings` 查不到 ⇒ 只能靠「重解后 Bg 是否变化」判定。

## 2026-11-22 午后用户要求 — 新增 I17/I18/I19（气隙圆环 + 负载电流激励）

> 事项见 `PROJECT_SPEC.md` §7（精确几何/位置/工况/验证项）。用户决策：圆环=新增独立
> vacuum 环；**15:04 用户明确纠正**：空载=winding 0 无电流，负载=有电流，
> 上一版"额定励磁空载"作废，只有两工况。
> 排期：I16（磁钢外移）是高优先级根因修复，**I17 圆环改 Region/Band 拓扑须与 I16 在同一次
> M1' 里一起做**，避免为同一几何连跑两次 401 点；I18 两工况（空载 0A / 负载有电流）随后。

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I17** | blocker | 几何 | 气隙区缺独立空气圆环：外圈直径=定子内径 93.000（R=46.5）、内圈直径=转子直径+气隙 92.325（R=46.1625）、厚 0.3375。与现有 Band（运动环）位置重叠 | `PROJECT_SPEC.md` §7.1；`ipm_build.py:328-352` Band/Region 布尔 | 用户决策=新增独立 vacuum 环 `AirgapRing`；Band 须收进转子内（R≤45.80）或绑转子对象，**无 intersect** | open | 与 I16 的 apex=33 一起改 `ipm_build.py`，M1' 真机验收 sheet 数=117（原 116 + 环 1） |
| **I18** | blocker | 工况 | winding 激励写死 `Current="0A"`（`ipm_build.py:360`），且**没有负载脚本**；用户 15:04 明确：空载=winding 0 无电流，负载=有电流 | `ipm_build.py:358-360`；仅 `ipm_m2_noload.py`，无 load 版 | **两工况分立**（旧的"额定励磁空载"作废）：①空载 0A 验齿槽≤1.25+BEMF+Bg，**不得有 25 N·m**；②负载三相正弦电流 **T_avg 25±10%**；每份 JSON 写 `excitation` | open | 新建 `ipm_m3_load.py`；公式 `Imax·sin(2πf·t+φ)`，f=100Hz/ω=628.3185；P=3927W，E=125V⇒I_rms=10.472A/Imax=14.810A（**须待 apex33 修复后实测 E 再定 Imax**）；φ 由 MTPA 扫描定 |
| **I19** | major | 转矩 | 转矩曲线平直度无量化判据；用户要求无明显周期性大幅波动 | `PROJECT_SPEC.md` §7.4 已给判据草案 | 峰峰值 ≤10% T_avg；主谐波 ≤5% T_avg；单点跳变 ≤15% | open（判据待周检确认） | 工况②③ 401 点 CSV 做 FFT + 逐点差分；I16 磁钢外移是主要手段 |

## 2026-11-22（夜，M5' 每日推进）— I16+I17 几何闭环 / I18 负载脚本落地

> 本轮按 PROJECT_SPEC §7 唯一权威执行。用户最高准则：全程自主、未定参数选最合理路径
> 立即执行 + 账本标 `assumption=待验证` + FEA/独立复算验证。

### I16 磁钢外移 apex 26→33 + I17 独立气隙环 —— DONE（真机 17/17 PASS）

- 改动：`ipm_geom.py` `v_single=(33,38,13,3)`；`ipm_build.py` 新增 `AirgapRing` 整环
  （外 R46.5 / 内 R46.1625 / 厚 0.3375 / vacuum / 独立实体），并入 Region 布尔工具与盘点；
  `ipm_m1_check.py` sheet 判据 116→117、前缀加 AirgapRing、新增环面积复核项。
- **Band 拓扑决策（assumption=待验证，真机已证无 intersect）**：契约 §7.1 字面要求
  "Band 收进转子内 R≤45.80"，但 `docs/MAXWELL_INTERNALS.md` §9.2 实测硬约束——Band
  做成气隙环/收进转子会触发 `No objects within the band`（运动带失效）。注意到现有 Band
  半径 46.1625 **恰等于**契约给的环内半径，二者是**共面贴边（零体积重叠）**，Maxwell 的
  intersect 只报"边界穿越"。故保留 Band 整圆包住转子 + 外壁贴独立 AirgapRing，是同时
  满足"独立气隙环"与"运动带包住转子"的唯一可行拓扑。判据以真机 Validate_OK + 无
  intersect + 117 sheet 为准（本轮全部达标）；周检复核该偏离是否需改契约 §7.1 文字。
- 真机证据：`D:/ANSYS_Run/ipm_m1_build.py` → `IPM_8p48s_M1_apex33.aedt`，ansysedt rc=0，
  38.5 s。日志 `ipm_m1.log`：**SHEETS=117**、前缀 AirgapRing=1/Band=1/Coil=96/PM=16、
  `AREA AirgapRing 98.2489`（解析 π(46.5²−46.1625²)=98.248892，偏差 1e-5%）、
  线圈 9.8 mm²、`VALIDATE_OK`、无 intersect/error。
  `ipm_m1_check.py` 独立复核 **17/17 PASS**（`m1_build_check.json`，含 v_single=[33,38,13,3]）。
  解析扫描交叉校验：apex33 OD 桥 1.549 / 极间 10.141 / 轴孔 16.495 / 6/6 PASS；
  apex32 OD 2.525 不够、33.5 OD 1.060 < 机械下限 FAIL。
- I16 极间桥仍 10 mm+（8 极 V 张角几何下限），与 I16"极间≤2.0"判据不可兼得；按契约 §7.2
  本阶段只按 OD 桥≤2.0 推进，**未改判据**，交周检裁定。

### I18 负载电流脚本 —— DONE（脚本层；真机待 M2' 实测 E 定 Imax 后跑）

- `ipm_build.py::build_script` 参数化 `currents`（None=三相 0A 空载，dict=三相字面量），
  默认行为逐字等价（回归 `CURRENTS={"A":"0A",...}` 已验证）。
- 新增 `ipm_m3_load.py` [KEEP]：`f=100Hz / ω=628.3185`，Imax 表按实测 BEMF 插值
  （118→15.688 / 125→14.810 / 132→14.024 / 145→12.767 A），φ/sign 参数化，
  三相表达式 `Imax*sin(ω*Time+φ)` B=φ−120°/C=φ+120°，电动取负号（§11.3 反相）。
  遵守 §11.1：不打开已求解工程改电流，而是**从头建含电流的新设计**（两段式：建模→求解）。
  工程/CSV/JSON 与空载严格分立（`IPM_8p48s_M3_<case>.aedt` / `csv_ipm_m3_<case>/` /
  `m3_load_<case>.json`），JSON 写 `excitation`（current_A/phase/frequency/source）。
- 新增 `ipm_m3_check.py` [KEEP]：独立重算 T_avg/峰峰值/FFT 主谐波/逐点跳变（I19 判据），
  合成 25±0.5 N·m 冒烟测试 5/5 PASS。

### M2' 空载（apex33）401 点实测 —— 几何方向对，但电磁仍 FAIL（留档，不改判据）

- 命令：`ipm_m2_noload.py --aedt-in .../IPM_8p48s_M1_apex33.aedt` → 求解脚本 →
  `ansysedt -RunScriptAndExit`；`ANALYZE_OK 457.5 s`、rc=0。CSV `csv_ipm_m2_apex33/`
  （flux/tq 各 402 行、探针 181/46/91），独立重算 `ipm_m2_check.py` →
  证据 `m2_noload_apex33.json`（KEEP）。**注意本轮 tq 表头 `[mNewtonMeter]`**（上次是 µN·m），
  torque_scale 按表头自动换算。
- 实测（apex33 vs 旧 apex26）：
  - 相 BEMF RMS **7.3844 V**（旧 4.2552，+73.5%）｜判据 118–145 → **FAIL**
  - 气隙 |B| 峰 **0.1823 T**（旧 0.0630，+189.4%）｜判据 ≥0.45（及 G4 0.70–0.90）→ **FAIL**
  - 极轴 |Br| 0.0853 T / |Br| 峰 0.1320 T（极轴/峰=0.646，波形仍畸变）
  - 线 THD 1.2887%（PASS）、齿槽 0.0025 N·m=0.0099%（PASS）、三相不平衡 0.0002%（PASS）
  - 解析交叉 E=16.28 V（差 −54.65%）；匝数反推 118V→cps=80 / 125V→cps=85
  - **空载转矩 ~0，未出现 25 N·m**（符合 15:04 口径）
- 诊断（诚实，反自演）：apex33 让磁通从 0.063→0.182 T，**方向验证 I16 外移有效**，但仍只到
  0.45 T 判据的 40%、BEMF 只到 118 V 的 6.3%。按契约 §7.3，**禁止用 E=7.3844 V 反推 Imax**
  （会得 Imax≈250.7 A，槽满率爆表）。残余瓶颈：①磁路仍欠 2.47×（I13 的 BH 是否真正生效
  未在真机验证——上次 memory 记 BH 标量覆盖已修，但本轮 Bg 0.182 提示桥仍未饱和到设计值）；
  ②匝数 cps=5 是 I3 未定源 TEMP 值，118V 需 cps≈80（16×），但契约要求 Bg 先回 ≥0.45 再反推匝数。
  两者耦合，不能单独靠加匝数掩盖磁路问题。**I16 标记"几何闭环 DONE、电磁目标未达"**，
  根因转 I13/I8（磁路饱和 + 聚磁比），留档 FAIL 不改判据，交周检裁定路径。
- 新增洞察：极轴/峰 Br=0.646 说明气隙磁密波形顶部塌陷（极间漏磁仍显著），单纯外移 apex 解决
  了"埋深"但未解决"桥饱和/极间短路"——与 I13 线性铁假设一致。

### M3' 负载管线验证 —— DONE（I18/I20 green；幅值 FAIL 留档）

- 两次 401 点真机（表下限 Imax=15.688 A，非从 7.38V 反推）：φ_abs=0（正交）T_avg≈0 →
  诊断 I20 → φ_abs=90（反相）T_avg=+1.5635 N·m。两段式脚本（建模→求解）均 rc=0，
  遵守 §11.1（不打开已求解工程改电流）。证据 `m3_load_floor_e118.json` / `m3_load_phi90.json`
  + 各自 `csv_ipm_m3_<case>/`（flux/tq 402 行）。
- **I18 验收：两工况分立 green** —— 空载 0A（`m2_noload_apex33.json`，无 25 N·m）、
  负载有电流（`excitation.current_A=15.688`，JSON 字段齐全，周检 G10 可核）。
- **I19 平直判据 green**（φ=90 case）：峰峰值 2.75% / 主谐波 1.33% / 跳变 0.35%，均 PASS。
- **T_avg=1.56 N·m FAIL（22.5–27.5）** —— 非管线问题（理论 1.5632 逐位吻合），是磁路/匝数
  未达（I13/I8/I3）。留档不改判据。

### 明日单一焦点

- **I13/I8 磁路**：BH 在 2021.1 真机是否真正生效 + 隔磁桥饱和判定。apex33 后 Bg 只到 0.182 T
  （判据 0.45，差 2.47×），极轴/峰 Br=0.646 波形顶部塌陷 → 桥仍半饱和/极间漏磁。这是 Bg、
  BEMF、T_avg 上不去的**共同卡点**；在此之前 φ MTPA 扫描、加匝数掩盖都无意义（禁止在坏磁路
  上调参，契约 §7.3"Bg 先回 ≥0.45 再反推匝数"）。周检裁定：I16"极间≤2.0"判据与单层 V
  几何不可兼得是否已改，以及是否放宽为"桥内 B≥1.8 T 饱和"实测口径。

## 2026-11-22（夜）新增 I20 —— 电流相位参考系未对齐（T_avg≈0 根因）

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 |
|---|---|---|---|---|---|---|
| **I20** | **blocker** | 工况/相位 | 用户公式 φ=0 的电流在本机与 BEMF 恰好**正交 90°**，导致负载 T_avg≈0（不是幅值/磁路问题）。空载拟合 `e_A=10.4348·sin(ωt+90°)`；φ=0、sign=−1 时 `i_A=−15.688·sin(ωt)=15.688·sin(ωt+180°)`，相位差 90° ⇒ 平均转矩 ∝ E·I·cos90°=0。M3' φ=0 真机实测 `T_avg=−0.0000 N·m`、主谐波 h=6（纯齿槽特征）印证 | `m3_load_floor_e118.json` + `csv_ipm_m3_floor_e118/tq_load.csv`（401 点）；BEMF 相位拟合脚本（读 `csv_ipm_m2_apex33/flux_a.csv` 差分）；§11.3 `T·ω=−avg(i·e)` | φ 设为 **+90°** 使 i 与 e 反相（i_A 相位 −90°/270°），T_avg 转正；再按相对反相点做 φ 扫描 | **closed（2026-11-22 夜：φ=+90° 真机 T_avg 转正 +1.5635 N·m，误差 0.017%）** |

- 推导：`e_A=E·sin(ωt+90°)`；`i_A=−Imax·sin(ωt+φ)=Imax·sin(ωt+φ+180°)`；反相要求
  `φ+180° ≡ 90°+180° (mod 360)` ⇒ **φ=+90°**。SPM 默认 `current_phase_deg=(120,240,0)`
  之所以不同，是它相对绕组 A 轴 0° 另起了参考系。用户截图的 φ=0 参考系与本机绕组相带
  （`ipm_winding.PHASE_PATTERN` A 相在槽 1/2，电角 0°）不对齐。
- 修正后预期：`P=3·E_rms·I_rms·1=245.6 W ⇒ T≈1.56 N·m`（cps=5、E=7.38 V 下）。仍远低于
  25 N·m 是磁路/匝数问题（I13/I8/I3），不是相位问题。**先把相位管线修 green，再谈优化。**
- CURRENTS 探针 API 失败（`BoundarySetup` 无 `GetPropertyValue`）：无法直接回读电流，改用
  "负载 flux/tq CSV 与空载逐点差异 + T_avg 符号"反证电流真施加（本轮 t=0.05ms 转矩
  −5.47 mN·m vs 空载 −0.94 mN·m，差 5.8×，证明电流确实改变了场）。

**I20 验证闭环（φ=+90° 真机，2026-11-22 夜）**：`ipm_m3_load.py --imax 15.688 --phi-abs 90`
→ 建模 rc=0 + 401 点 `ANALYZE_OK 475.5s` rc=0 → `m3_load_phi90.json` + 独立重算：
- **T_avg=+1.5635 N·m**（φ=0 时 −0.0000），理论 `3·E_rms·I_rms=3·(10.4348/√2)·(15.688/√2)=1.5632`，
  **误差 0.017%** —— 相位诊断"电流与 BEMF 反相"被真机逐位证实。
- I19 平直三项全 PASS：峰峰值 2.75%（≤10%）、主谐波 h=6 幅值 1.33%（≤5%）、
  单点跳变 0.35%（≤15%）；仅 T_avg 幅值 FAIL（1.56 < 22.5，因磁路/匝数未修复，非相位）。
- **状态：I20 closed**（相位管线 green）。`ipm_m3_load.py` 已按契约语义修订：`--phi` 现在
  表示"相对 BEMF 反相点的偏移"（默认 0 = 最大转矩点，内部 φ_abs=90+φ）；`--phi-abs` 显式
  绝对角兼容历史；JSON `excitation` 增 `phase_abs_deg`/`bemf_offset_deg`。默认 φ=0 生成脚本
  与 phi90 验证 case 逐字一致（已核对），`--phi-abs 0` 精确复现旧 φ=0 case。
- 下一步（磁路修好后）：φ=0/−15/−30 相对偏移扫描取 T_avg 最大且脉动最小（MTPA）。

## 2026-11-22（22:26 用户反馈）新增 I21 —— 负载后感应电势幅值对不上（优化项）

用户原话："添加负载之后连感应电势的幅值都对不上了，这一点需要优化。"

**现场实测（本轮从 flux CSV 独立重算，第二电周期 10–20 ms、dλ/dt 基波 DFT，n=199）**：

| 工况 | A 相 BEMF 基波幅值 | RMS | 相对空载 | 相位 |
|---|---:|---:|---:|---:|
| 空载 apex33（0A） | 10.3798 V | 7.3396 V | 基准 | 90.00° |
| 负载 φ=0（15.688A） | **12.5572 V** | 8.8792 V | **+21.0%** | 90.00°（不变） |
| 负载 φ=90（15.688A） | 10.6103 V | 7.5026 V | +2.2% | **101.96°（偏 +11.96°）** |

B/C 相同量级（空载 10.4635 V）。CSV：`csv_ipm_m2_apex33/`、`csv_ipm_m3_floor_e118/`、
`csv_ipm_m3_phi90/`。

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I21** | major | 工况/复核 | 负载后 BEMF 幅值与空载不一致：φ=0 +21.0%、φ=90 +2.2% 且相位偏 11.96°。**根因不是脚本 bug**：φ=0 的 +21% 是电枢反应增磁（真实物理），φ=90 的相位偏是电流改变弱磁/增磁工作点。但两者都被 I8/I13 坏磁路放大（Bg 0.182 T 判据 0.45、BEMF 7.38 V 判据 118–145），**在坏磁路上调参掩盖属于自演** | 上表（flux CSV 独立重算）；`m2_noload_apex33.json`、`m3_load_*.json`；账本 I8/I13 的 Bg 0.182 T | ①负载工况的 BEMF 必须在各自 JSON 里有独立字段（`bemf_load`），与空载分列；②Bg 回 ≥0.45 T 后重测，负载/空载 BEMF 幅值比应落在物理合理区间（电枢反应 ≤15%）；③相位偏差须在 `excitation` 里记录实测 BEMF 相位 | **open（优化项，依赖 I8/I13 磁路修复）** | 先修 I8/I13 磁路（禁止在坏磁路调参）；`ipm_m3_check.py` 增负载 BEMF 计算并写 `bemf_load`；磁路 green 后做 φ 扫描复核幅值/相位；不为了"对上"而改电流幅值或判据 |

**优化顺序（写进每日/周检任务）**：I8/I13 磁路 → BEMF 回 118–145 V → 负载 BEMF 独立入 JSON → φ MTPA 扫描复核幅值/相位。**禁止**用改 Imax/φ 或换相位参考系来"凑"空载幅值。

## 优先级规则

1. `blocker` 先于 `major`；I1→I2→I3→I4 有依赖关系（I3 依赖 I1+I2，I6 依赖 I4）。
2. 每天只推进**一个**问题；D1–D7 定源前禁止把临时参数写进 baseline 配置（只能放显式 `TEMP/` 试验脚本）。
3. 关闭条件：验收值达标 + 证据写入本表 + 脚本自检通过。
4. 连续 2 天无进展标 `blocked` 并写清需要的桌面操作或用户决策。

## 2026-11-22 22:35 根因翻转 —— Bg 0.182 T 的真因是 BH 没进材料（不是桥饱和/埋深）

**用户"继续修复"要求触发的核查结论（覆盖 I16/I13 此前的一部分猜测）**：

| 旧判断 | 真机证据 | 结论 |
|---|---|---|
| I16：磁钢埋深 8.356 mm、桥区 0.085 T ⇒ 磁通极间短路 | apex 33 后 OD 桥压到 1.549 mm，Bg 只从 0.063 → **0.182 T**（仍远低于 0.45） | 外移有效但**不是主因** |
| I13/I14：EditMaterial 手工塞 BHCoordinates 生效 | 4 种写法（顶层/BValue/平铺数组/挪末位+删 permeability）在 2021.1 **全部静默丢弃**；旧 `.aedt` grep `nonlinear` = **0** | 铁芯一直按 **μr=1** 求解 ⇒ Bg 塌陷真因 |
| — | `ipm_m1_bhfix.py` 改用 `CloneMaterial("JFE_Steel_35JN270","M270_35A")`，新 `.aedt` grep `nonlinear` = **2**、BHCoordinates 有真实点 | **真机已落盘，待 M2' 401 点验证 Bg** |

- **来源**：JFE_35JN270 是 0.35 mm、牌号 270 同 M270 量级的厂商实测 BH（66 点，10 A/m@0.02 T → 80 kA/m@2.094 T）；膝点比自造 M270 曲线偏软约 9%，**assumption=待验证**，Bg 由 FEA 判定，不靠解析。
- **待验证**：后台 M2'（`ipm_m2_bhfix_solve.py`）正在跑 401 点，出结果后回填 Bg/BEMF；若 Bg 仍 <0.45，再回到几何（I16 极间桥判据）而非继续改 BH 写法。
- **对 I16 判据的影响**：此前"极间≤2.0 不可兼得"的裁定仍有效，但桥饱和假设的前提（铁芯有 BH）此前根本不成立，周检复核时应把这条一并更正。

## 2026-11-22 夜（本轮续）— BH 修复 401 点验证闭环：Bg 0.182→0.662 T（I13/I8 根因坐实）

> 上一节"待验证"项的实测回填。真机 401 点（`ipm_m2_bhfix_solve.py`，输入 `IPM_8p48s_M1_bhfix.aedt`），
> `ANALYZE_OK 694.6 s` rc=0，flux/tq 各 402 行、探针 181/46/91；独立重算
> `ipm_m2_check.py` → 证据 `projects/results/ipm8p48s/m2_noload_bhfix.json`（KEEP）。
> **非线性求解 694.6 s vs 旧线性 457.5 s（+52%），求解器真在做 BH 迭代**（旁证 BH 生效）。

| 量 | 旧（无 BH，μr=1） | 新（CloneMaterial BH） | 变化 | 判据 | 判定 |
|---|---:|---:|---:|---|---|
| 气隙 \|B\| 峰 Bg | 0.1823 T | **0.6621 T** | +264% | ≥0.45（I16）/ 0.70–0.90（G4） | **I16 PASS / G4 边缘 FAIL** |
| 气隙 \|Br\| 峰 | 0.1320 T | 0.6530 T | +395% | — | 记录 |
| 极轴 \|Br\| | 0.0853 T | 0.2858 T | +235% | — | 波形仍畸变（轴/峰=0.438） |
| 相 BEMF RMS (cps=5) | 7.3844 V | **63.8721 V** | +765% | 118–145 V | FAIL（**匝数不足**，非磁路） |
| 相 BEMF 基波 THD | 4.00% | 14.76% | — | ≤10%（相） | FAIL（线 THD 4.50% PASS） |
| 线 BEMF THD | 1.29% | 4.50% | — | ≤10% | PASS |
| 齿槽峰峰 | 0.0025 N·m | **3.4729 N·m** | 放大 | ≤1.25 N·m（5%） | **FAIL（新暴露，见 I22）** |
| 齿身 / 轭部 B 峰 | 0.082 / 0.028 T | 0.922 / 0.812 T | — | ≤1.65 / ≤1.50 | PASS |
| 解析交叉 E | 16.28 V | 80.55 V | — | vs FEA 63.87（差 −20.7%） | 记录（解析偏乐观） |

- **I13 / I8 状态更新**：BH 缺失是 Bg 塌陷主因，已由 CloneMaterial 修复并经 401 点证实
  （Bg +264% 越过 I16 的 0.45 T 判据）。I16"几何外移 apex33"仍有效（-8.356→1.549 mm OD 桥），
  但单独不足以修复磁路；I13 从"最高优先级 blocker"降为 **closed（BH 生效路径已闭环）**。
  I8（Bg 回填 I1 磁密三行）现在可回填实测 0.662 T，旧 0.85 T 假设作废。
- **匝数反推（此时才有效）**：cps=5 时 0.7984 V/匝/相；118 V→cps=9（144 匝，114.97 V）、
  125 V→cps=10（160 匝，127.74 V）、145 V→cps=11（176 匝，140.52 V）。
  **这是 Bg 正常后第一次可信反推**（对比 apex26 时代的 cps=139 废数）。cps=10 在 9.8 mm²
  矩形内是否放得下需按 I3 槽满率复核（Ø1.5 线 10 根≈17.7 mm²，fill 0.45，可行）。
- **新暴露 I22（齿槽随导磁显现）**：旧齿槽 0.0025 N·m 是"铁芯不导磁"的假象；BH 修复后
  齿槽真实值 3.4729 N·m（13.9% 额定）超 ≤1.25 N·m 判据。这是真实物理，不是管线 bug。
  修法候选：①48 槽分布绕组本应齿槽低，先查极轴/峰 Br=0.438 的波形塌陷（磁钢外移 apex33
  后极间漏磁仍大）；②斜槽（D5，0.5 槽距，SPM 历史把 0.88→0.00058 N·m）；③齿形/槽口微调。
  **本轮不动**（一天一个 I 号），留作明日单一焦点。
- **I21 本轮进展（③ 已实现）**：`ipm_m3_check.py` 新增 `bemf_load_block()` + `fundamental()`，
  load JSON 写独立 `bemf_load` 字段（A/B/C 基波幅值/RMS/相位/相对空载%），`--noload-json`
  可选接空载 JSON 算相对%。用 phi90 CSV 复现：A 相基波 **10.6889 V @ 102.68°**、RMS 7.5639 V、
  相对空载 +2.16%，与旧账本 I21 的 10.6103 V@101.96°/+2.2% 逐位接近（DFT 窗 n=200 vs 199），
  独立实现交叉校验通过。新字段不破坏 I19 转矩判据，pytest 468 passed。
- **遗留**：BEMF 63.87 V（需 cps≈10 才达标）、齿槽 3.47 N·m（I22）、Bg 0.662 略低于 G4 0.70
  下限。按优化顺序，下一步先 I22（齿槽）与匝数 cps=10 定源，再跑负载 T_avg 与 φ 扫描。
- 新增：`projects/results/ipm8p48s/m2_noload_bhfix.json` [KEEP] BH 修复 401 点独立重算证据。
  临时探针 `D:/ANSYS_Run/bh_probe{,2,3,4,5,6,7}.py` / `bh_probe*.aedt` [TEMP] 不入库。

## 2026-11-23 周检书面裁定（docs/WEEKLY_AUDIT_2026-11-23.md）

> 基线 HEAD `ae93bde` == origin/main；技能可用 ✅ / 设计不合格 ❌ / 流程不合规 ❌。
> M1' PASS / M2' PASS / M3' PASS / **M4' FAIL（网格全缺）**。本节只裁定与记账，不删任何 fail 行、不改判据数值（I16 例外见下，为书面裁定明示修订）。

### I16 判据书面裁定（周检授权）
**裁定：修订为「OD 桥 ≤2.0 mm 且桥内磁密 B≥1.8 T（FEA 实测饱和）」；极间桥厚度不再作独立硬阈值。**
- 依据①：极间桥恒 10.141 mm 是 8 极 V 张角 + 3 mm 内端间距的几何硬下限，与「极间≤2.0」不可兼得——原判据定错，非设计失败（I16 定源预研已证）。
- 依据②：I16 原始意图是「桥薄到能被 2 T 饱和，磁通不短路」；BH 已生效（Bg 0.662 T），应回归物理意图，用桥内 FEA 实测 B≥1.8 T 判饱和。此前「桥饱和前提不成立」的旧说法一并更正为「BH 未进材料导致 μr=1，非桥几何问题」。
- 依据③：新增桥内 B≥1.8 T 比原几何阈值更严格、更贴物理，**不是放宽判据掩盖 FAIL**。
- 执行约束：桥内 B FEA 实测未完成（I22 诊断候选），该子项记 **`unverified`，不得标 PASS**；下轮单一变量补测后再闭环 I16。

### 本周 top3（P0/P1/P2）
1. **P0 — M4' 网格剖分链路（G10⑤ blocker）**：全库无 `mesh_<case>.json`、`probe_mesh_api.log` 不存在、流程跳过剖分直接求解。先真机跑 `TEMP/probe_mesh_api.py`→把 2021.1 网格 API 结论写进 `docs/MAXWELL_INTERNALS.md`→每 case 出 `mesh_<case>.json`（单元/节点数按对象、min/max、质量指标或 unavailable、耗时、4 组 MaxLength）→校验 Band≤0.25 + 4 组 Enabled。**未 green 前禁止新 401 点求解**。
2. **P1 — I3 匝数定源 + I22 齿槽**：Bg 0.662 T 已可信，按反推表 cps=5→**cps=10（160 匝，预测 127.74 V）**定源并复核槽满率；重算 Imax、φ 相对反相点扫描，T_avg 1.56→22.5–27.5 N·m；同步处理齿槽 3.4729 N·m（13.89%）。
3. **P2 — I21/excitation 字段合规**：`bemf_load` 从 `D:/ANSYS_Run/m3_load_phi90_check_i21.json`（TEMP）写回 KEEP 的 `m3_load_*.json`；空载 5 份 JSON 补 `excitation.current_A=0`；负载补 `phase_abs_deg`/`bemf_offset_deg`；BEMF 回窗后做幅值比≤15% 复核。

### 新暴露 minor（周检记账，不改判据）
| ID | 严重度 | 领域 | 问题 | 验收 | 状态 |
|---|---|---|---|---|---|
| **I23** | minor | 流程/证据 | G10③：空载 5 份 JSON 完全无 `excitation` 字段（契约 §7.3 要求记 0A）；负载 3 份缺 `phase_abs_deg`/`bemf_offset_deg`（账本 I20 声称已增，实测未落盘） | 每份 JSON excitation 字段齐全，空载 current_A=0，负载含相位字段 | open（P2 一并处理） |
| **I24** | major | 流程/证据 | G10⑤：每次建模后剖分+统计未执行，全库无 `mesh_<case>.json`；网格 API 未真机探测 | 契约 §8 流程与 mesh JSON 判据全过 | **closed（2026-11-23 P0 闭环，4 case 全 PASS，见下）** |

### I24 / M4' 闭环（2026-11-23，P0）

- **API 探测（真机三轮）**：`probe_mesh_api{,2,3}.log` 实测 2021.1 的网格生成统计在 **`oDesign` 层**
  （`GenerateMesh`/`ExportMeshStats`/`ApplyMeshOps`），`oMesh`（MeshSetup module）层**没有**这些方法。
  `GenerateMesh("Setup1")->0`、`ExportMeshStats(setup,keys,path,[overwrite])` 导出 8 列单元统计。
  结论写入 `docs/MAXWELL_INTERNALS.md §18`（含签名、单位推断、坑位）。
- **落盘脚本（KEEP）**：`ipm_mesh_check.py`（`--gen` 生成 IronPython 剖分脚本 / `--parse` 解析统计+
  独立判定）；每 case 的 `mesh_<case>.json`（KEEP）。宿主侧 CPython 解析，不碰 AEDT 求解。
- **四 case 全 PASS**（`mesh_<case>.json::verdict.overall_pass=true`，真机 GenerateMesh r=0）：

| case | 工程 | 总单元 | 剖分耗时 s | Band | Stator | Rotor | PM(16) | AirgapRing | Coil(96) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| m1_bhfix | IPM_8p48s_M1_bhfix | 42684 | 11.491 | 4170 | 9543 | 10150 | 4508 | 4466 | 1574 |
| m2_bhfix | IPM_8p48s_M2_bhfix | 42748 | 6.219 | — | — | — | — | — | — |
| m3_phi90 | IPM_8p48s_M3_phi90 | 42858 | 7.350 | — | — | — | — | — | — |
| m3_floor_e118 | IPM_8p48s_M3_floor_e118 | 42840 | 7.186 | — | — | — | — | — | — |

- **判据逐项**：4 组 LengthOp 全 Enabled 且 MaxLength 一致（0.25/0.9/1.2/0.5 mm）、Band≤0.25 ✓、
  六类对象单元数全非 0 ✓。质量指标（skewness）/节点数 2021.1 ExportMeshStats 不导出 →
  JSON 写 `unavailable`+原因（§18.3），**未编数**。
- **单位**：统计长度按 SI(m) 推断 ×1000→mm（Band RMS 0.656 mm ≈ 气隙 0.675 mm 交叉验证），
  JSON 标 `assumption=待验证`+验证方法，未当已证（§18.4）。
- **踩坑（高价值）**：①API 挂在 oDesign 不在 oMesh，问错对象全 AttributeError；②`--aedt` 传带扩展名
  会在 gen 里拼成 `.aedt.aedt`，已加去扩展名保护；③异常退出残留 `.aedt.lock`+`*.asol.semaphore`
  会让下次 OpenProject 报"used by another application"且脚本主体不执行，确认无 ansysedt 进程后清 TEMP 锁可恢复。
- **未做（禁越界）**：未启动新 401 点求解（P0 只补剖分链路）、未碰 P1 匝数/齿槽、未碰 P2 字段。
  下一步按 top3 顺序转 P1。

## 2026-11-24（P1 主项）— I3 匝数定源 cps=10：401 点 BEMF 首次回窗（127.7440 V）

> 开工 HEAD==origin/main==`386a806`（P0 已闭环），工作树干净。按 top3 的 P1 单项推进；
> 一次一个变量（只改 cps=10 + 配套制造绕线线径 Ø1.35，几何/材料/BH/边界一律不动）。
> 全程自主未提问。

### 定源决策（assumption=待验证部分已就地标注）
- **匝数**：cps 5→**10**（`N_ph=16·cps=160`）。依据：BH 修复后 cps=5 实测 BEMF 63.8721 V
  （Bg 0.6621 T 可信）⇒ 0.7984 V/匝/相 ⇒ 125 V 需 cps=10（预测 127.7442 V，落 118–145 窗）。
  119 V 下限需 cps=9（114.97 V 出窗），145 V 上限需 cps=11（140.52 V 在窗但槽满率爆表，
  见下）⇒ **cps=10 是唯一同时满足 BEMF 窗与槽满率的整数匝数**。
- **绕线线径**：cps=10 每槽 2 边×10 根 = 20 根。Ø1.5 铜 35.34 mm²/槽实切 38.756 mm²
  ⇒ fill **0.9119 FAIL**（>0.78）；Ø1.35 铜 28.63 mm² ⇒ fill **0.7387 PASS**。
  故 `wind_wire_mm=1.35`（新字段，仅槽满率口径；**不进 FEA、不改几何**）。
  几何定标 `wire_diameter_mm=1.50` 不动（Bs0/Bs2 由它推，改它要推翻已 green 的 M1'）。
  `assumption=待验证`：Ø1.35 需物料 BOM/真实漆包线规格确认；铜耗预算 28.63 < 38.756×0.78=30.23 ✓。

### 代码改动（KEEP）
- `projects/IPM_8p48s/ipm_geom.py`：`IPMConfig.conductors_per_slot` 5→10（定源，非 TEMP）；
  新增 `wind_wire_mm=1.35` + `slot_fill_factor()` 独立复算函数。
- `projects/IPM_8p48s/ipm_build.py`：`CPS = ` 生成行注释更新（TEMP→I3 定源）。
- `projects/IPM_8p48s/ipm_m2_check.py`：`CPS_MODEL` 5→10。
- `projects/IPM_8p48s/ipm_m1_check.py`：新增 `--json` 全路径参数（支持多 case 不覆盖旧证据）。
- `tests/test_ipm_8p48s.py`：+3 例（cps=10 定源 / 槽满率 Ø1.35 PASS+Ø1.5 FAIL / 生成物 CPS=10）；
  `tests/test_ipm_m2.py`：CPS_MODEL 断言 5→10 + 反推恒等校验改活。
- `projects/IPM_8p48s/PROJECT_SPEC.md` §3.1 D3：open→closed，写明定源依据与 assumption。

### 真机链路（全部 rc=0，401 点 + 每次剖分，契约 §8）
| 动作 | 工程/产物 | 关键数 |
|---|---|---|
| M1' 建模 | `IPM_8p48s_M1_cps10.aedt` + `m1_build_check_cps10.json` | 117 sheet、CPS=10、96 Conductor number、BH `nonlinear`=2、`VALIDATE_OK`、35.8 s、**17/17 PASS** |
| M1' 剖分 | `mesh_m1_cps10.json` | 42872 单元、17.278 s、4 组 LengthOp 合规、Band≤0.25、六类对象非 0、**overall PASS** |
| M2' 空载 401 点 | `IPM_8p48s_M2_cps10.aedt` + `csv_ipm_m2_cps10/` + `m2_noload_cps10.json` | `ANALYZE_OK 710.3 s`、flux/tq 各 402 行、探针 181/46/91、SHEETS=117 |
| M2' 剖分 | `mesh_m2_cps10.json` | 42758 单元、5.728 s、**overall PASS** |

### 独立重算结果（`m2_noload_cps10.json`）
| 量 | cps=5（旧） | cps=10（本轮） | 判据 | 判定 |
|---|---:|---:|---|---|
| 相 BEMF RMS | 63.8721 V | **127.7440 V**（预测 127.7442，误差 0.0002%） | 118–145 V | **PASS（首次回窗）** |
| 线 BEMF THD | 4.4988% | 4.4988% | ≤10% | PASS |
| 气隙 \|B\|峰 Bg | 0.6621 T | 0.6621 T（逐位不变，磁路未动） | 0.70–0.90 | FAIL（I3 无关，G4 遗留） |
| 齿槽峰峰 | 3.4729 N·m | 3.4729 N·m（逐位不变） | ≤1.25 N·m | FAIL（I22 遗留） |
| 三相不平衡 | 0.0003% | 0.0003% | ≤2% | PASS |
| 齿身/轭部 B | 0.922/0.812 T | 0.922/0.812 T | ≤1.65/≤1.50 | PASS |

- **关键交叉校验**：只改 cps（Conductor number）⇒ BEMF 严格线性 ×2（63.8721→127.7440，
  比 2.00000），Bg/齿槽/THD 逐位不变 ⇒ 证明匝数旋钮与磁路解耦，I13/I16 的 BH 修复未被回退。
- **未做（禁越界）**：未碰 I22 齿槽、未碰 I21/P2 字段、未碰 φ 扫描/T_avg（那是 P1 后半，
  需负载 401 点；本轮只做匝数定源单项，Imax 表 E=125→14.810 A 现成可用，明日转负载）。
  探索仍 LOCKED；SPM baseline 只读。
- **遗留风险**：①Ø1.35 线径需 BOM 验证（assumption=待验证，不影响 FEA）；②齿槽 3.4729
  与 Bg 0.6621 仍 FAIL，是本设计最终能否工程可用的真正卡点（I22/G4），非匝数问题。
- 新增文件：`m1_build_check_cps10.json` [KEEP]、`mesh_m1_cps10.json` [KEEP]、
  `mesh_m2_cps10.json` [KEEP]、`m2_noload_cps10.json` [KEEP]（首次 BEMF 回窗证据）。
  TEMP 脚本/CSV/日志全在 `D:/ANSYS_Run/`，不入库。
- 明日单一焦点：负载 T_avg 回窗——按实测 E=127.744 V 取 Imax（表 E=125→14.810 / 132→14.024
  插值 ≈14.52 A），φ=0 相对反相点跑 401 点负载，看 T_avg 是否回 22.5–27.5；FAIL 留档后转 I22 齿槽。

## 2026-11-24 用户要求 — Bs0 收窄 + 槽满率提高 + 转矩平直（I25/I26）

用户三要求：①Bs0 小一点；②槽满率提高一点；③今天内完成稳定转矩曲线。用户确认方案：Bs0=1.0+槽深重定标；脉动先 FFT 诊断。用户参考案例 `D:/桌面/Maxwell电机仿真/书本仿制.aedt`（Bs0=1.0/Hs0=0.5/Hs1=1.7/Hs2=18.8/Bs1=6.9/Bs2=6.9，稳定 48 N·m）。

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I25** | blocker | 几何 | Bs0 2.2→**1.0**、Hs0 1.2→**0.5**（书本案例，用户 16:56 要求 Hs0 跟着小一点、Hs2 加长、绕组正好放进去）；联动 Bs1 2.7→1.5、Hs1 5.3→6.0、Hs2 12.5→13.5、yoke 16→15 | `ipm_geom.py` derive_slot 系数 0.36→0.164、Hs0=0.5 案例定制、不再被 d_wire+0.4 拉宽；槽面积 **38.886**（铜耗需 37.776）、满率 **0.7400**（原 0.7387，仍≤0.78）、矩形线圈 6.795→**7.172 mm²/条**（+5.5%，往槽口延伸）、B_yoke 1.089、8/8 自检 PASS、473 tests | 真机重跑 M1'（117 sheet/无 intersect/槽口1.0）+ M2'（Bg≥0.45/BEMF 118–145/齿槽≤1.25），旧 cps=10 数据（127.744 V/25.7367 N·m）是 Bs0=2.2 的，**不得引用为新几何性能** | **closed（几何定源）/ open（真机）** | 今日按 prompt 顺序重跑；制造口径 Ø1.35 + Bs0<线径属半闭口槽，待 BOM 复核 |
| **I26** | blocker | 转矩 | cps=10 负载 T_avg 25.7367 N·m 达标但**峰峰值 5.1299 N·m = 19.93% FAIL**；FFT 主谐波 h=12/1200 Hz/2.208 N·m(8.58%)=48槽×25rps 槽通过频率，h=24 0.752、h=6 0.393 | `m3_load_check_cps10.json`（旧几何）+ `m3_load_check_bs10.json`（Bs0=1.0，pp 14.08%）+ `m3_skew_skew_bs10.json`（斜槽 3 切片，pp **3.29%**）；各片 CSV 401 行、s1 identity 校验逐位一致 | 峰峰值 ≤10% T_avg、主谐波 ≤5%、跳变 ≤15%；先 FFT 诊断再对症，不调参掩盖 | **closed（2026-11-24：Bs0 收窄 + 3 切片斜槽 0.75 槽距，四项全 PASS：T_avg 27.0286 / pp 3.29% / h12 0.81% / 跳变 0.91%）** | 残余：T_avg 距上限 27.5 仅 1.7% 余量；见文末当日闭环段 |

**图1/图3 口径澄清**：图1（±500 N·m）是 Maxwell 原始 `Moving1.Torque`，IPM 导出单位 **µN·m**，按 N·m 读放大 1000×，叠加零电流/正交相位⇒绕 0 大幅振荡；图3（稳定 48 N·m）是书本案例的稳态有效电动工况。两者不是同一物理量口径，禁止直接对比数值。

## 2026-11-24（第二段）— I26 转矩平稳闭环：Bs0 收窄 + 3 切片斜槽 0.75 槽距

> **并发会话说明**：本轮运行期间另一会话把 Bs0 2.2→1.0（commit 5535c9e/3474545/e058cba）。
> 本轮先跑完旧几何斜槽证明方法有效，**随即在新几何（Bs0=1.0）上重跑全链路**，以下数据均为新几何。

### 诊断（不调参，先定根因）
- 旧几何无斜槽负载：pp 19.93%、主谐波 h=12 2.2077 N·m（8.58%）。h=12 = 48槽/4极对 = 1200 Hz 槽通过频率。
- 空载齿槽 3.4729 N·m 本身就 > 2.5 N·m 判据 ⇒ **齿槽是根因**，φ 扫描（不改变齿槽）无解。
- 频域预研（`TEMP/ipm_skew_predict.py`，纯后处理）：0.5 槽距仅降到 12.82% 不够；0.75 槽距预测 7.29%；1.0 槽距 1.95% 但基波降额更大。**选 0.75 槽距（γ=22.5° 电角）**。

### 实现（KEEP）
- `ipm_geom.IPMConfig.rotor_init_deg` 新字段 + `derive_rotor(cfg, rotor_init_deg)`：转子 V 槽/磁钢绕 Z 转该机械角。
- `ipm_build.magnet_directions(cfg, rotor_init_deg)`：磁化方向**同步旋转**（否则几何转了磁极没转 = 假斜槽）。
- 新增 `ipm_skew_slices.py`（KEEP）：3 切片驱动（Δ_mech=±2.8125°,0）+ 逐点平均 + 同判据重算。
- `tests/test_ipm_8p48s.py` +2 例：0° identity 逐位一致、旋转后 16 块面积/6 项自检不变。

### 关键踩坑（写进代码注释）
1. **电流相位必须按切片补偿**：`--phi` 是相对 BEMF 反相点的偏移，`compute_currents` 要 φ_abs=90+φ_rel；
   且每片转子转 Δ_mech ⇒ BEMF 反相点转 Δ_elec=Δ_mech×4，电流相位必须同步补，否则各片工作点不同
   （首跑未补 ⇒ 三片 T_avg 分别 +1.40/0.00/−1.40，平均≈0，`KeyError:101` 二次崩在 DFT 索引）。
2. **3 切片是离散实现，不是对单波形做频域平移**：每片独立真机求解后逐点平均。s1（0°）与无斜槽
   baseline 逐位一致（T_avg 27.0306、pp 3.8047 vs 3.8048）即 identity 校验。

### 新几何真机结果（全部 rc=0、401 点、每 case 剖分）
| 阶段 | 工程/证据 | 关键数 |
|---|---|---|
| M1' | `IPM_8p48s_M1_bs10.aedt` + `m1_build_check_bs10.json` | 117 sheet、线圈 7.172 mm²、VALIDATE_OK、39.2 s、17/17 PASS |
| M1' 剖分 | `mesh_m1_bs10.json` | 45576 单元、PASS |
| M3' 无斜槽 | `IPM_8p48s_M3_bs10.aedt` + `m3_load_check_bs10.json` | ANALYZE_OK 718.8 s、T_avg 27.0306、pp **14.08%**、h12 5.94% FAIL |
| M3' 剖分 | `mesh_m3_bs10.json` | 45540 单元、PASS |
| 斜槽 s0/s1/s2 | `IPM_8p48s_M3_skew_bs10_s{0,1,2}.aedt` | ANALYZE_OK 804.1/991.1/976.0 s、各 401 行、单片 pp 14.69/14.08/14.71% |
| 斜槽平均 | **`m3_skew_skew_bs10.json`** | **T_avg 27.0286 / pp 3.29% / h12 0.81% / 跳变 0.91% — 四项全 PASS** |
| 斜槽剖分 | `mesh_m3_skew_bs10_s{0,1,2}.json` | 45170/45566/45216 单元、全 PASS |

### 对比（同判据）
| 工况 | T_avg | pp | h12 | 判定 |
|---|---:|---:|---:|---|
| 旧几何 Bs0=2.2 无斜槽 | 25.7367 | 19.93% | 8.58% | FAIL |
| 旧几何 + 斜槽 0.75 | 27.0085 | 3.32% | 0.83% | PASS（方法验证） |
| 新几何 Bs0=1.0 无斜槽 | 27.0306 | 14.08% | 5.94% | FAIL（收窄有效但不够） |
| **新几何 + 斜槽 0.75** | **27.0286** | **3.29%** | **0.81%** | **PASS（今日目标达成）** |

### 新几何空载 M2' 401 点（同日补跑，闭环 BEMF/齿槽判据）
`IPM_8p48s_M2_bs10.aedt`，`ANALYZE_OK 665.0 s`，flux/tq 各 402 行，探针 181/46/91。
`m2_noload_bs10.json` + `mesh_m2_bs10.json`（45284 单元 PASS）：

| 量 | 旧几何 Bs0=2.2 | 新几何 Bs0=1.0 | 判据 | 判定 |
|---|---:|---:|---|---|
| 相 BEMF RMS | 127.7440 V | **133.7364 V** | 118–145 V | **PASS** |
| 齿槽峰峰 | 3.4729 N·m | **1.1302 N·m（4.52%）** | ≤1.25 N·m | **PASS（I22 闭环）** |
| 线 BEMF THD | 4.4988% | 4.2550% | ≤10% | PASS |
| 三相不平衡 | 0.0003% | 0.0002% | ≤2% | PASS |
| 气隙 \|B\|峰 Bg | 0.6621 T | 0.6189 T | 0.70–0.90（G4） | FAIL（I16 的 ≥0.45 仍 PASS） |
| 齿身 / 轭部 B | 0.922 / 0.812 T | 0.948 / 0.873 T | ≤1.65 / ≤1.50 | PASS |

**齿槽下降机理（不靠斜槽）**：Bs0 2.2→1.0 收窄槽口，槽口磁导调制减弱 ⇒ 齿槽 3.4729→1.1302
（−67.5%），同时槽口窄使气隙磁通略降（Bg 0.6621→0.6189）但 BEMF 反升（127.74→133.74，
因齿身/轭部磁阻重新分配）。斜槽只用于压负载段残余脉动（I26），不是齿槽达标的必要条件。

- **未做（禁越界）**：未改判据、未改 Imax 凑幅值、未碰探索（LOCKED）、未动 SPM baseline。
- **遗留风险**：①T_avg 27.03 距上限 27.5 仅 1.7%，若后续调参需留余量；②3 离散切片忽略
  轴向场/斜槽漏抗，属近似上限口径（SPM G7 同款局限）；③Bs0=1.0 < Ø1.35 线径属半闭口槽，
  制造工艺待 BOM 复核；④Bg 0.6189 T 低于 G4 下限 0.70 T（G4 仍 FAIL，属磁钢/聚磁设计问题，
  与转矩曲线目标无关）。
- 新增 KEEP：`m1_build_check_bs10.json`、`mesh_m1_bs10.json`、`m3_load_bs10.json`、
  `m3_load_check_bs10.json`、`mesh_m3_bs10.json`、`m3_skew_skew_bs10.json`、
  `mesh_m3_skew_bs10_s{0,1,2}.json`、`m2_noload_bs10.json`、`mesh_m2_bs10.json`、
  `ipm_skew_slices.py`。
  TEMP：`TEMP/ipm_skew_predict.py`（斜槽频域预研）。

---

### I27 「为什么没有转矩从零上升的曲线」—— M4 起动工况设立（2026-11-24，DONE-script / 真机进行中）

**用户提问**（20:42）："好奇怪，为什么，没有转矩从零开始上升的转矩曲线？"

**这不是 bug，是口径。** 三条代码事实（不是推断）：

| 环节 | M1'–M3' 实际设置 | 后果 |
|---|---|---|
| 转子运动 `ipm_build.py:419` | `Consider Mechanical Transient:=False` + `Angular Velocity:="1500rpm"` | 求解器**从不积分** `J·dω/dt = T_em − T_load`，ω 是给定的常数 |
| 绕组激励 `:398` | `Type:="Current"`，`Imax·sin(ωt+φ)` | 电流源直接灌入，t=0 即为 `Imax·sin(φ)`；无电压源 L/R 建立过程 |
| 永磁体 | 剩磁预置于材料 | t=0 气隙已是 0.662 T，无"充磁"过渡 |
| 求解窗口 `:437` | `StopTime=0.02s`（2 个电周期） | 401 点全部落在稳态区间 |

**硬证据**：`D:/ANSYS_Run/csv_ipm_m3_cps10/tq_load.csv` 首行 `0, 26.5808397855413` ——
仿真第一个采样点就是 26.58 N·m。不存在"上升慢"，是根本没有上升段。

**处置**：新建独立工况 M4（契约见 `PROJECT_SPEC.md` §7.6），不复用、不覆盖 M1'–M3'。
参数签名取自本机 `MaxwellScriptingGuide.pdf` P758–760（见 `docs/MAXWELL_INTERNALS.md` §13.11）。

**参数定源**：

| 键 | 值 | 来源 |
|---|---|---|
| `Consider Mechanical Transient` | `True` | 官方 P760 示例 |
| `Angular Velocity` | `"0deg_per_sec"` | 机械瞬态下=初速（非恒转速） |
| `Moment of Inertia` | `"0.0092"` | 转子本体解析：硅钢 ½·7.43·0.0461625²=7.92e-3 + 磁钢 0.749·0.0415²=1.29e-3；不含轴 |
| `Damping` | `"0"` | 无额外阻尼 |
| `Load Torque` | `"0NewtonMeter"` | 空载起动 |
| `StopTime` / `TimeStep` | `0.2s` / `0.0005s` = 400 步 401 点 | 与 M1'–M3' 同规模（用户要求） |
| `SaveFieldsType` | `"None"` | 只取转矩/转速，抵消 remesh 开销 |

**文件级验证**（`IPM_8p48s_M4_start.aedt` 二进制直搜，2026-11-24 建模后）：
`'Consider Mechanical Transient'=true` ×1、`'Angular Velocity'='0deg_per_sec'` ×1、
`'Moment of Inertia'='0.0092'` ×1、`Damping='0'`、`'Load Torque'='0NewtonMeter'` —— 全部命中。

**踩坑（完整清单见 `docs/MAXWELL_INTERNALS.md` §13.11）**：
① `DeleteMotionSetup` 要 Structured Array，传字符串失败；② `AssignBand` 对同一 band 重复调用
报 `Already has motion setup with same band assignment`；③ `ChangeProperty` 的
`PropServers` 用 `MotionSetup1`/`BandData` 都是 `Invalid PropServer`；
④ **裸最小工程上连已验证写法都失败**（band 需完整建模上下文），最小工程法不成立。

**遗留**：M4 首跑用 `--bemf 127.744`（旧几何 Bs0=2.2 实测值）插得 Imax=14.502 A；
新几何实测相 BEMF 为 **133.7364 V**，若按新值应为 Imax≈13.84 A（−4.8%）。
M4 只用于看起动曲线形状，不参与 25 N·m 判据，故首跑数据有效但需在报告中标注该口径差；
若要 M4 稳态段精确落在 25 N·m，需用 `--bemf 133.7364` 补跑一次。

---

#### I27 续：机械瞬态跑通 ≠ 转子能起动（同日 21:00–21:30 两次真机证否）

M4 首跑（21:09，`ANALYZE_OK`，16m09s）参数全部生效、工程能解，但**转子根本没转起来**：

| 量 | 实测 | 应有 |
|---|---:|---|
| 转速峰值 | 59.3 rpm @122.5 ms | → 1500 |
| 转速末段 | −8.1 rpm | 1500 |
| 转矩峰 / 谷 | +33.84 / −33.88 N·m | 单边正 |
| 转矩末段均值 | 0.381 N·m | ≈0（空载稳态） |
| `position.csv` 末值 | 358.72° | 单调增 |

**根因（①）**：`Consider Mechanical Transient=true` 只解决"转速从哪来"，不解决"转子能否被
驱动"。PMSM **没有阻尼绕组**，固定 100 Hz 定子磁场以 1500 rpm 旋转，静止转子被正负交替的
转矩原地拉扯，平均转矩≈0。异步机能自起动靠鼠笼；PMSM 必须 ①阻尼笼 ②变频器爬坡
③编码器闭环。首跑等于"直接投额定频率 + 转子静止"这一最恶劣工况。

**证否（②）**：改位置反馈 `i=−Imax·sin(4·Moving1.Position·pi/180+φ)`（极对数 4，★现场
先误写成极数 8，靠 grep 表达式才抓到）。结果转矩仅 **55 µN·m**（单位自动降到 µN·m）、
`position.csv` 末值 **0.00029°** ⇒ **`Moving1.Position` 在 winding 电流表达式里未被实时
求值**（当常量 0），三相退化成固定直流、合成磁动势静止。该路线在本机 2021.1 不可用。

**采纳（③）变频起动**：`f(t)=f0+k·min(t,T)`、`θ(t)=2π[f0·t+k·min(t,T)²/2]`，
f0=2 Hz → f1=100 Hz、T=0.12 s（余 0.08 s 恒频稳态）。纯时间函数，不依赖任何反馈变量；
`min()` 在表达式引擎可用，用来"爬到目标频率后封顶"。
40 ms 快速验证：转速 0 → **490.6 rpm**，理论同步速 (2+816.67×0.04)×60/4 = 520 rpm → **PASS**。

**判据教训（写进 §7.6）**：只导 `Moving1.Torque` 看不出这两种失败——转矩在 ±33 N·m 之间摆
也能画得像"起动曲线"。**必须同导 `Moving1.Speed`**，它是"转子到底动没动"的唯一硬证据。

---

## 2026-11-25 — I28 气隙网格层数单变量复测（指导书唯一命中的真缺陷）

**来源**：用户 2026-11-24 21:54《ANSYS Maxwell 电机仿真转矩不稳定排查指导书》；
本地化 `docs/TORQUE_TROUBLESHOOTING.md` §3.4/§6 逐条甄别后，整份指导书只有
「气隙网格 2–3 层」这一条在本项目真没做到。其余 3 条（恒速+Load Torque、拍频、
J 过大）是原文错误，已纠正，不照抄。

**缺陷定量（改前）**：`mesh_m4_chirp2.json::per_object` 实测 `AirgapRing`
n=4534、rms_edge=0.2277 mm、max_edge=0.4588 mm；气隙环厚 0.3375 mm
（`PROJECT_SPEC` §7.1：airgap/2 = 0.675/2）⇒ 层数 0.3375/0.2277 ≈ **1.48 < 2.0**。
`ipm_build.py` 原 4 组 `AssignLengthOp` 只覆盖 Band/StatorOuter/RotorOuter/PM，
AirgapRing 不在任何一组 ⇒ 0.2277 mm 是全局网格被动传播值，非设计值。

**处置（严格单变量）**：`ipm_build.py` 新增第 5 组
`NAME:Mesh_Airgap / Objects:["AirgapRing"] / MaxLength:="0.15mm"`
（⇒ 2.25 层名义）。其余 4 组 MaxLength、几何、材料、BH、边界、绕组、相位、
求解窗口逐字未动；`test_build_script_default_is_steady_state` 护栏保持稳态口径。
`ipm_mesh_check.py` 同步把 `EXPECTED_LENGTH_OPS` 扩为 5 组，并新增
`airgap_ring_min_layers ≥ 2.0` 判据（契约 §9.2）。
新增测试 `test_airgap_length_op_is_5th_group` 钉住 5 组/0.15 mm/稳态不变。

**二选一决策（未试第三档）**：任务书允许 0.15 mm（2.25 层）或 0.11 mm（3 层），
二选一不试第三档。实测 0.15 mm 已使 rms_edge 降到 0.1306 mm ⇒ **2.58 层 PASS**，
目标达成；0.11 mm 只会进一步增加单元数（与"单元超预期则收紧"的缓解方向相反），
故**不切换到 0.11 mm**。总单元增幅超指导书预估（见下遗留），但不改档。

**真机证据链**（全部 rc=0）：

| 环节 | 结果 | evidence |
|---|---|---|
| M1' 建模 | 117 sheet / VALIDATE_OK / 无 intersect / 槽口 Bs0=1.0 / 线圈 7.1725 mm² | `m1_build_check_airgap.json` 17/17 PASS |
| .aedt 5 组 | LengthBased=5，MaxLength 0.15/0.25/0.5/0.9/1.2 各一组 | `IPM_8p48s_M1_airgap.aedt` grep 实测 |
| M1' 剖分 | 总 68068 单元 / AirgapRing 13690 / rms 0.1306 / 2.58 层 | `mesh_m1_airgap.json` all PASS |
| M3' 401 点 | ANALYZE_OK 1123.0 s / tq 402 行 / 表头 [NewtonMeter] | `m3_load_check_airgap.json` |
| M3' 剖分 | 总 67680 单元 / AirgapRing 13690 / rms 0.1306 / 2.58 层 | `mesh_m3_airgap.json` all PASS |

**与基线逐项对比**（基线 `m3_load_check_bs10.json`，14.08% 那条 FAIL **保留不删**）：

| 量 | 基线（Imax 14.5019） | 本轮（Imax 13.8561） | 差 | 归因 |
|---|---:|---:|---:|---|
| AirgapRing 单元 | 4534 | 13690 | ×3.02 | 网格加密（设计变更） |
| AirgapRing rms_edge | 0.2277 mm | 0.1306 mm | −42.7% | 网格加密 |
| 气隙层数 | 1.48 | **2.58** | +74% | 已达 §9.2 ≥2.0 |
| 总单元 | 45540 | 67680 | +48.6% | AirgapRing + 共面 Band 连锁加密 |
| T_avg | 27.0306 | 25.8068 | −4.53% | **Imax −4.45% 口径差**，非网格 |
| **峰峰值** | **14.0757%** | **14.0075%** | **−0.068 pt** | **几乎不变 ⇒ 网格不是主因** |
| 主谐波 h=12 | 5.9393% | 5.8872% | −0.052 pt | 几乎不变 |
| 跳变 | 3.9178% | 3.9339% | +0.016 pt | 不变 |

**判据裁定**（按 §9.3 的二分支）：峰峰仅降 0.068 pt（相对 −0.5%），远达不到
"显著下降"，落在**"几乎不变"分支** ⇒ 网格不是 14.08% 的主因，
**斜槽 0.75 槽距的 3.2855% 收益结论成立**（`m3_skew_skew_bs10.json`，
四项全 PASS，稳态 25 N·m 平直目标仍为 PASS，本轮不推翻）。

**口径诚实标注（反自演）**：基线用 Imax=14.5019 A（旧几何 BEMF 反推），
本轮按任务书用当前几何实测 BEMF 133.7364 V 插值 Imax=13.8561 A
（`imax_from_bemf`，解析直算 √2·P/3E=13.8422 A，差 0.10%）。
⇒ 严格说本轮是 **网格 + 电流口径双变量**，不是纯净单变量。
处理方式：T_avg 变化按电流口径差解释，不归因网格；**峰峰值 % 与主谐波 % 是
对 T_avg 归一化的量**，电流降 4.45% 会使其分母变小、数值略升，而实测反而略降，
故"几乎不变"的结论是**保守的**（若电流相同，降幅只会更小）。
φ_abs=90°、f=100 Hz、sign=−1 均未动。

**遗留风险**：
1. 总单元 +48.6%（指导书预估 +6% 严重低估）：AirgapRing ×3.02 之外，
   共面贴边的 Band 从 4778→11980（×2.5）被迫加密。401 点求解 1123 s
   （基线 718.8 s，+56%），在可接受范围，但后续每次 M3 复测预算需按 ~19 min 计。
2. rms_edge 作径向层厚代理是保守口径（周向长边抬高 rms ⇒ 低估层数），
   真机 2021.1 ExportMeshStats 无径向专用列，`assumption=待验证`，
   验证方法：改用 max_edge 0.2383 mm 时层数 0.3375/0.2383=1.42（更保守），
   但 max_edge 是周向+径向混合，两者都不精确；层数达标结论以"加密前后数值变化
   不影响平直判据"为准，不依赖单一层数口径。
3. 本轮不覆盖 14.08% FAIL 记录，不改任何判据；Bg 0.6189 T（G4 FAIL）、
   E8 效率 / E6 退磁 FEA、I16 判据周检裁定仍是遗留。

**新增 KEEP**：`m1_build_check_airgap.json`、`mesh_m1_airgap.json`、
`m3_load_airgap.json`、`m3_load_check_airgap.json`、`mesh_m3_airgap.json`；
代码改动 `ipm_build.py`（第 5 组）、`ipm_mesh_check.py`（判据+5 组）、
`tests/test_ipm_8p48s.py`（+1 例）。TEMP：`D:/ANSYS_Run/ipm_*_airgap*` 全部留在运行目录。
**未做**：未碰 SPM baseline、未改 J/阻尼、未动判据、未删除任何失败记录、
未跑 M4 0.5 s 窗口（属第二优先，见当日自动化输出）。

---

### I28 续：M4 起动 0.5 s 窗口延长尝试 —— FAIL 留档（2026-11-25，第二优先）

**动机**：`m4_start_chirp2.json`（0.2 s/401 点）转速 0→1687 rpm 峰、末段 1588.4 rpm，
115 ms 后仍有 ±33 N·m 同步振荡。任务书要求：第一优先完成后有余量则把窗口延到
0.5 s（1000 点，额外工况不占 401 点口径），看振荡是否自然衰减到 1500 rpm；
**禁止**改 `Moment of Inertia`（0.0092 解析值）。

**执行**：`ipm_m4_start.py --bemf 133.7364 --mode chirp --ramp 0.18
--stop 0.5s --dt 0.0005s --case chirp2_05s` 生成两个脚本；核验
`ipm_m4_solve_chirp2_05s.py` 同时导 `Moving1.Torque/Speed/Position`（三量齐）、
`Moment of Inertia:="0.0092"` 未动。建模 `BUILD_RC=0`（工程
`IPM_8p48s_M4_chirp2_05s.aedt` 落盘 2.12 MB）。

**失败证据（两次真机，rc=127）**：
- 首次：Analyze 运行 ~26 min 后进程无日志退出，`ipm_m4_solve_chirp2_05s.log`
  止于 `MOTION_NAMES=['MotionSetup1']`，无 `ANALYZE_OK`/`ANALYZE_FAIL`，
  CSV 目录空（0 文件）。
- 清理孤儿锁（PID 26264 已死）后**原参数原脚本重试**：38 s 即同样 rc=127、
  日志同样止于 `MOTION_NAMES`，CSV 仍空 ⇒ **可复现失败，非偶发/非锁残留**。
- 系统内存 14.0 GB 可用 / 32.4 GB 总，`wmic/tasklist` 无残留 ansysedt 进程 ⇒
  不是 OOM 或实例冲突。
- 再次清理第二次的孤儿锁（PID 10612）。

**根因（判断，非编数）**：崩溃发生在 `oDesign.Analyze("Setup1")` 调用本身
（Python 层 try/except 未捕获 ⇒ 进程级退出，rc=127 是批处理壳返回码，
不是脚本异常）。0.2 s/401 点同参数同求解器曾 `ANALYZE_OK` 通过
（`m4_start_chirp2.json`），0.5 s/1001 点 + 加密网格（M4 工程沿用当前
`ipm_build.py`，AirgapRing 已含第 5 组 0.15 mm ⇒ 单元数 ~2 倍）后不可复现成功。
区分不了是"瞬态机械积分在长窗口发散"还是"大网格长窗口求解器内部错误"——
**未做定位实验，不猜结论**。

**处置**：不删失败、不改判据、不改 J/阻尼/电流/网格去"凑"成功。
`m4_start_chirp2_05s.json` 保留 `generated=true / solved=false` 作 KEEP 证据。
M4 第二优先对"振荡是否自然衰减"这个问题**未获得答案**，
0.2 s 基线的 1588 rpm 末段 + 同步振荡仍是唯一有效 M4 数据。

**遗留 / 明日一步**：若继续 M4，先做定位实验而非再跑长窗口——
在 0.2 s 基线上只延到 0.3 s/601 点（不加密网格，用冻结版工程），
看是否存在"窗口长度阈值"；若 0.3 s 也崩，则是机械瞬态长窗口求解器问题，
转用外部后处理外推或直接接受 0.2 s 基线。此项**不阻塞**第一优先的
25 N·m 平直目标（斜槽 0.75 已 PASS，与 M4 无关）。

---

## 2026-11-26 — Motor-CAD MCP P0 连接验证：I30 BLOCKED（工具链，非电机设计）

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I30** | **blocker** | 工具链 / Motor-CAD MCP | P0 最小连接验证失败：exe 路径可由 `set_motorcad_exe()` 绕过，但 `get_variable("Version")` 被 FlexNet 拦截（error -8,544，license key 与数据不一致），拿不到版本号，无法判定 E8/E6/热网络链路可用 | `projects/motorcad_mcp/probe_connection.py`（KEEP，退出码 1）；`projects/motorcad_mcp/TEMP/probe_fail.log`（TEMP，56 行完整原文）；`F:\ANSYS Motor CAD\AnsysMotorCAD\Shared Files\ActiveX.bat` 第 1 行 | `MotorCAD()` + `set_variable` + `get_variable("Version")` 全 PASS 且打印 `PROBE_OK` | **BLOCKED**（2026-11-26，P0 30 分钟上限内穷尽 4 条路径） | 需授权修复本机 ANSYS License（key 与 license server 不一致）。修复后重跑探针，PASS 才进 P1/P2。**本轮按协议停止，未写 MCP server、未跑真机、未改 E6/E8 状态** |

### I30 诊断链（全部为实测，非推断）

**环境事实**：
- PyMotorCAD `0.8.8` 已装入项目级 venv（`projects/motorcad_mcp/.venv`），未装全局依赖；venv Python 实测 `3.13.14`（指定路径 3.13.12 目录下）。
- 8 个目标 API 方法经 introspect 全部存在：`get_variable` / `set_variable` / `load_template` / `save_to_file` / `do_magnetic_calculation` / `do_steady_state_analysis` / `get_magnetic_graph_point` / `get_node_temperature`。
- `MOTORCAD_ACTIVEX` 环境变量指向 `F:\ANSYS Motor CAD\AnsysMotorCAD\Shared Files\ActiveX.bat`，其第 1 行为 `call "C:\Program Files\AnsysMotorCAD\v252\Motor-CAD_2025_2_1.exe" /SCRIPTING` —— **安装残留旧路径，本机不存在**，这是 PyMotorCAD 默认 `MotorCAD()` 的首个失败点。
- 真实 exe 从用户指定快捷方式 `D:\桌面\Ansys Motor-CAD 2025.2.1.lnk` 的 Shell Link `LocalBasePath` 字段解出：`F:\ANSYS Motor CAD\AnsysMotorCAD\v252\Motor-CAD_2025_2_1.exe`（33,639,424 B，实测存在）。**未扫描安装包目录**。

**已尝试路径（4 条，均 FAIL）**：

| # | 路径 | 结果 |
|---|---|---|
| 1 | `pymotorcad.MotorCAD()` 默认（batch 文件路径） | `MotorCADError: File does not exist: C:\Program Files\AnsysMotorCAD\v252\...` |
| 2 | `set_motorcad_exe(真实路径)` + `MotorCAD()` | 实例启动、`set_variable("MessageDisplayState", 2)` 成功；`get_variable("Version")` 抛 FlexNet -8,544 |
| 3 | `MotorCAD(use_blackbox_licence=True)` | `feature: motorcad_blackbox` 同样 -8,544 |
| 4 | `MotorCAD(use_blackbox_licence=False)` | `feature: motorcad` 同样 -8,544 |

**完整报错原文（`TEMP/probe_fail.log`，核心段）**：

```
ansys.motorcad.core.rpc_client_core.MotorCADError: Unable to check out feature: motorcad
ANSYS LICENSE MANAGER ERROR
Invalid (inconsistent) license key.
 The license key and data for the feature do not match.
 This usually happens when a license file has been altered.
Feature:       motorcad
License path:  1055@localhost;
FlexNet Licensing error:-8,544
```

**根因判断（assumption=待验证）**：FlexNet -8,544 的官方语义是 license key 与 license 数据不一致（文件被改动/与 server 不匹配）。本机能打开 GUI 与本错误不矛盾——GUI 可能走缓存或另一 license 口径，未经本轮验证。验证方法：在本机运行 ANSYS License Manager 的 `lmstat -a -c 1055@localhost` 检查 `motorcad` feature 状态，再由管理员重新获取/替换 license 文件。**本轮不修改任何 license 文件、注册表或环境变量**（破坏性操作需明确授权）。

**交付边界**：只落 `probe_connection.py` [KEEP] 与本条账本；`TEMP/diag_license.py`、`TEMP/probe_fail.log` [TEMP] 不入库；`.venv` 由 `.gitignore` 排除。P1（8 工具 MCP + dry_run + 进程锁）、P2（IPM .mot 真机 + E6/E8）**未执行**，`docs/ENGINEERING_ACCEPTANCE.md` 的 E6/E8 状态一字未改。

---

## 2026-11-26（SPM 第一优先）— I31/I32/I33：贴片平行充磁几何定源 + 拓扑消歧

| ID | 严重度 | 领域 | 问题 | 证据 | 验收 | 状态 | 下一步 |
|---|---|---|---|---|---|---|---|
| **I31** | major | SPM 几何口径 | `SPM_DESIGN.md` §2 写"Band=43.7825 / AirgapRing 厚 2.7175"，把贴片占据的 2.38mm 重复扣成气隙；若采用则 Band 切过磁钢 (43.445–45.825)，几何不成立 | `spm_build.py` `SPMConfig.spm_iron_r` / `spm_snapshot`；`m1_spm_g03_build_check.json` 实测气隙 0.675、Band 46.1625、环 98.2489 | 磁钢外表面 r=45.825（=原 IPM 转子 OD 半径），气隙 0.675、Band 46.1625 与 IPM 逐字相同 | **已处置（assumption=待验证）**：采用物理自洽值，SPM_DESIGN.md 待回填；FEA 气隙探针 gap_mag.csv 复核 Bg | 周检复核 SPM_DESIGN.md §2 的 43.7825 口径，改为 46.1625 |
| **I32** | blocker（已解） | SPM 拓扑 | 贴片内表面与铁芯外表面相邻时，Maxwell `Analyze` 报 `Parts "PM_01..08" and "RotorOuter" intersect`（`ValidateDesign` 不报）；M1/M1_clean/M1_g02 三次 401 点入口均 4s 快速 FAIL | `spm_diag_analyze.log` / `spm_diag_g02.log` 完整 message；`spm_diag_g03.log` 显示 `Normal completion` | 短窗口 4 步 Analyze `Normal completion`、无 intersect | **已修复**：对铁芯做 `Subtract(PM, KeepOriginals=True)` 显式建拓扑（沿用 IPM baseline 做法），并留 0.02mm 装配胶缝（铁芯 r=43.425、磁钢内 r=43.445）。胶缝 assumption=待验证 | 401 点实测后回填 I32 验收；胶缝对 Bg 影响待敏感性复核 |
| **I33** | minor | 工具链 / 网格统计 | 未求解的全新 SPM 工程上 `GenerateMesh("Setup1")->0` 但 `ExportMeshStats` 只导表头（无单元行）；IPM 历史成功案例均是已求解工程导出 | `meshstats_m1_spm.txt`（2 次）、`meshstats_spm_retry.txt`（双 GenerateMesh+Save 仍空）；`mesh_m1_spm.json` TOTAL_ELEMENTS=0、OVERALL_PASS=False | 求解完成后对 `SPM_8p48s_M2_g03.aedt` 补导真实统计 | **记录为 unavailable + 原因，不编数**；空 JSON 保留作证据，判据未改 | M2 401 点成功后补剖分统计 JSON；周检确认 §8.4 顺序对未求解工程的例外 |

### I32 诊断链（关键，避免重复踩坑）

- 现象：`ipm_build` 同构脚本建出的 SPM M1，`ValidateDesign` 返回 `VALIDATE_OK`，但 M2 求解 `Analyze("Setup1")` 4.2–4.3s 抛 `call failed`，CSV 空、`.asol` 仅 1729 B。
- 排查顺序：① 疑 mesh 缓存污染 → 干净重建 `M1_clean.aedt`，同样 FAIL ⇒ 排除；② 疑材料/矫顽力未落盘 → `grep .aedt` 确认 8 块 NdFe35 均含 `Magnitude='-890000A_per_meter'`、BH 66 点落盘 ⇒ 排除；③ 抓 `oDesktop.GetMessages` → **8 条 `Parts "PM_0x" and "RotorOuter" intersect`**，根因确定。
- 修复：0.02mm 装配胶缝（验证无效，仍报）+ 对铁芯 `Subtract(PM, KeepOriginals=True)`（有效）。`spm_diag_g03.log`：`Normal completion of simulation on server`。
- 教训：`ValidateDesign OK` **不等于**求解器无 intersect；新拓扑必须做一次短窗口 Analyze 判"能解"，不能只看建模日志。已写入护栏测试 `test_spm_build.py`。



### I31 续：SPM M1/M2 401 点实测（2026-11-26，第一优先 S2）

- **M2 空载 401 点**（`SPM_8p48s_M1_g03.aedt` → `SPM_8p48s_M2_g03.aedt`）：
  `ANALYZE_OK 1277.0s`、CSV 402 行、`m2_noload_spm_g03.json`。
  - 相 BEMF **273.4005 V**（判据 118–145，**FAIL**，×1.88 上限）；
  - Bg **1.0114 T**（判据 0.70–0.90，**FAIL 超上限**）；极轴 Br 0.6699 T；
  - 齿槽 **1.1764 N·m PASS**、线 THD **7.3508% PASS**、三相不平衡 0.0009% PASS、
    齿身 1.5890 / 轭 1.2824 T PASS。
  - 解析交叉 E=248.405 V 与实测差 +10.06%（Bg 高、饱和Starts），标 assumption=待验证。
- **根因判断（FEA 证据，非编数）**：SPM 贴片无 IPM 隔磁桥漏磁通道，Bg 1.0114 比 IPM
  实测 0.6189 高 63%，与分析预估 0.95 T 同向。BEMF 超窗是拓扑本质，不是管线错误：
  gap/flux CSV 完整、三相平衡、THD 合规、齿槽合规。
- **处置**：FAIL 留档，判据未改、数据未删。Imax=13.856 A 固定不变（任务书硬约束），
  不按 BEMF 反推电流凑数。M3 负载 401 点测 T_avg 后，按任务书单变量扫
  t_pm=2.0/2.38/2.8（实际需据 T_avg 决定扫描区间）；若减薄仍不能同时满足
  BEMF≤145 与 T_avg≥22.5，则该拓扑在本绕组/电流口径下不可达，如实记 FAIL 交周检，
  **不改判据**。



### I31 续：SPM M3 负载 401 点实测 + S4 厚度单变量决策（2026-11-26）

- **M3 负载（t_pm=2.38, Imax=13.856A, φ_abs=90°）401 点**：
  `ANALYZE_OK 1296.1s`、`Normal completion`、CSV 402 行、`spm_m3_t238_check.json`。
  - **T_avg=50.2821 N·m**（判据 22.5–27.5，**FAIL**，×2.01）；
  - 峰峰 **8.531% PASS**、主谐波 h=12 **3.606% PASS**、跳变 **1.621% PASS**、
    负载 BEMF 基波 394.38 V（相对空载 +2.73%）。
  - 平直三项全 PASS，说明**贴片拓扑的平直性成立，唯幅值超 2×**。
- **S4 决策（assumption=待验证，自主选档）**：任务书预案扫 t_pm=2.0/2.38/2.8，
  但实测 T_avg 50.28 表明需减薄约一半才能落窗。线性外推
  `T∝t_pm`（SPM 无桥、Bg 随 t 近线性）：50.28 × 1.30/2.38 ≈ **27.46 N·m**，
  取 **t_pm=1.30 mm**（core_od=89.05）作为首个单变量点，落窗上沿留余量。
  **不改电流**（Imax 仍 13.856 A，判据可比性）。若仍 >27.5 则下一步 1.15mm；
  若 <22.5 则退 1.45mm。每步 401 点，FAIL 留档。
  风险：1.30mm 贴片偏薄，退磁/机械强度留 E6 待验证；Bg/BEMF 会同步下降（利好 BEMF 超窗）。



### I31 续：S4 厚度单变量第 1 点 t_pm=1.30（2026-11-26）

- **M3（t_pm=1.30, core_od=89.05, Imax=13.856A）401 点**：`ANALYZE_OK 1134.1s`、
  `Normal completion`、CSV 402 行、`spm_m3_t130_check.json`。
  - **T_avg=42.0246 N·m**（判据 22.5–27.5，**FAIL**，较 t=2.38 的 50.2821 降 16.4%）；
  - 峰峰 **9.110% PASS**、主谐波 **3.798% PASS**、跳变 **1.705% PASS**；
  - 负载 BEMF 基波 348.42 V（相对 t=2.38 空栽 394.38 降 11.6%，方向正确）。
- **外推失效诊断**：t 减 45%（2.38→1.30）T_avg 只降 16%，线性外推预测 27.46 落空。
  物理解释：SPM 无隔磁桥，气隙磁密 Bg≈Br·t/(t+μr·g)，当 t≫μr·g≈0.709mm 时
  1.30mm 已近饱和区，继续减薄到气隙同量级才有显著下降。
  处置：再测极端点 t=0.65mm（core_od=90.35，与气隙 0.675 同量级）确认下限，
  仍 FAIL 则判"本电流/气隙口径下拓扑不可达"，留档交周检，不改判据/电流。


### I31 补记：SPM_DESIGN.md §9.2（11-26 15:28 用户追加 OD120 需求）沿用错误气隙口径

`SPM_DESIGN.md` §9.2 网格预算行写"气隙厚从 2.7175 → 2.174 mm"（并发会话写入），
仍是 I31 已证伪的口径——贴片占据空间被重复扣成气隙。真实气隙环厚 **0.3375 mm**
（Band 46.1625 = 气隙中线，AirgapRing 46.5/46.1625），OD120 按比例应为
**0.54 mm 气隙 → 环厚 0.27 mm**，Mesh 0.12mm ⇒ 2.25 层（与 §9.2 的"≈18 层"不同）。
本轮不改他人章节（明日 OD120 任务第一优先）；此处留档，供 11-27 建 OD120 模型时修正，
避免 43.7825/2.7175 错误口径被带进新几何导致 Band 切过贴片。


### I33 补记：会话中断导致求解工程孤儿锁（2026-11-26 16:01）

t_pm=0.65 的 M3 求解在会话中断时被杀，留下 `SPM_8p48s_M3_t065.aedt.lock` +
`.Motor_Design.asol.semaphore` + `.Motor_Design.asol_priv.semaphore`（时间戳 16:01）。
20:17 恢复任务后直接重跑，`OpenProject` 抛 `call failed`、日志止于 `OPEN_FAIL`，
空耗 698.3s。确认无 ansysedt 进程后清理上述 3 个孤儿锁（未动无关 M4_soft 锁），
重跑恢复正常。**教训**：会话中断后重跑求解前，先查 `.aedt.lock` / `*.semaphore`
并确认无残留进程；这是 2026-11-23 已记录过的坑，本轮复发。


### I33 补记 2：t=0.65 首次求解中断后结果目录污染（2026-11-26 20:30）

t065 工程（16:01 被会话中断）清锁后重跑，`OpenProject` 成功但 `Analyze` 8.8s 报
`Maxwell2d solver ... Internal Solver Error: 'Missing data to continue solution process!'`。
判断为中断时写入的半截 `.aedtresults`（`.asol` 1643 B + `.asol_priv` 3336 B +
`Motor_Design.results/`）被求解器读到，非几何问题（t=2.38/1.30 同拓扑成功）。
处置：**不删失败、不改判据**；换工程名 `t065r` 干净重建再求解。
原 `spm_m3_solve_t065.log` 保留 FAIL 证据。


### I31 续：S4 厚度单变量三点曲线 + 第 4 点决策（2026-11-26 20:47）

| t_pm (mm) | core_od | T_avg (N·m) | 峰峰 | 主谐波 | 判定 | 证据 |
|---:|---:|---:|---:|---:|---|---|
| 2.38 | 86.89 | 50.2821 | 8.531% | 3.606% | FAIL 超转矩 | `spm_m3_t238_check.json` |
| 1.30 | 89.05 | 42.0246 | 9.110% | 3.798% | FAIL 超转矩 | `spm_m3_t130_check.json` |
| 0.65 | 90.35 | **30.6432** | **10.328%** | 4.259% | FAIL 超转矩+峰峰 | `spm_m3_t065r_check.json` |

- t=0.65 由干净工程 `t065r` 求解（`ANALYZE_OK 881.4s`，Normal completion）；原 t065
  因会话中断污染 `.aedtresults`，清锁重跑仍报 solver internal error，失败留档（I33 补记 2）。
- **趋势**：t 每减半，T_avg 降幅递减（50.28→42.02→30.64）；t=0.65 距上沿 27.5 仅 11%，
  但峰峰首次破 10%（10.33%）。说明薄贴片区转矩与脉动同时恶化，存在可达窗口边界。
- **第 4 点决策（assumption=待验证）**：t=0.50（core_od=90.65），线性外推 T≈27–28，
  检验能否同时满足 T_avg∈[22.5,27.5] 与峰峰≤10%。若 FAIL 且峰峰继续恶化，
  判"本电流/气隙口径下 SPM 贴片拓扑不可同时达标"，留档交周检，不改判据/电流。


### I31 续：S4 第 4 点 t=0.50 落窗 + S5 FFT 诊断（2026-11-26 21:05）

- **M3（t_pm=0.50, core_od=90.65, Imax=13.856A）401 点**：`ANALYZE_OK 962.3s`、
  Normal completion、CSV 402 行、`spm_m3_t050_check.json`。
  - **T_avg=26.3363 N·m ∈ [22.5,27.5] —— PASS（首次落窗）**；
  - 主谐波 h=12 **4.500% PASS**、跳变 **2.637% PASS**、电流施加 PASS；
  - **峰峰 10.965% > 10% FAIL**（唯一剩余失败项）。
- **S5 FFT 诊断（先行，不直接调参）**：末周期 200 点 DFT，最强分量：
  h=12 **1.1852 N·m (4.50%)**、h=24 0.3224 (1.22%)、h=36 0.1648 (0.63%)、
  h=6 0.1449 (0.55%)、h=48 0.0343 (0.13%)。⇒ 峰峰由 **h=12 槽谐波族**主导
  （48 槽 × 4 对极 → 槽通过频率 12 阶），与 IPM 无斜槽的 14% 同源。
- **下一单变量决策（assumption=待验证）**：先试极弧 0.85→0.80（任务书 S5 候选、
  改动最小、只动贴片张角），Imax 仍 13.856 A；若峰峰仍 >10% 再上 IPM 已验证的
  斜槽 0.75 槽距（需新写 SPM 斜槽几何+磁化旋转，成本 3×401 点）。
  无论哪条，T_avg 落窗的 t=0.50 是后续固定基线。


### I31 续：S5 极弧单变量第 1 点 0.80 —— FAIL（2026-11-26 21:22）

- **M3（t=0.50, 极弧 0.80, Imax=13.856A）401 点**：`ANALYZE_OK 863.9s`、Normal completion、
  CSV 402 行、`spm_m3_t050a80_check.json`。
  - T_avg **25.8114 PASS**（仍在窗）；但峰峰 **14.8767% FAIL**（极弧 0.85 时 10.965%）、
    主谐波 h=12 **7.155% FAIL**（0.85 时 4.500%）、跳变 4.45% PASS。
- **结论**：减小极弧使 h=12 槽谐波族**恶化**，方向错误。FAIL 留档、判据未改。
- **下一步**：反向单变量极弧 **0.90**（增大极弧），若仍 FAIL 则极弧路线证否，
  转 IPM 已验证的斜槽 0.75 槽距（需新写 SPM 斜槽几何+磁化方向旋转）。


### I31 CLOSED：SPM 25 N·m 贴片平行充磁达成（2026-11-26 21:36）

- **最终设计点**：t_pm=**0.50 mm**（core_od=90.65）、极弧 **0.90**、Imax 13.856 A 固定。
- **M3 401 点**（`ANALYZE_OK 816.3s`、Normal completion、CSV 402 行）：
  `spm_m3_t050a90_check.json` — **status=PASS**：
  T_avg **26.6968 N·m**（窗内）、峰峰 **9.963% PASS**、主谐波 h=24 **3.037% PASS**、
  跳变 **4.061% PASS**、电流施加 PASS。**25 N·m 目标达成**（偏差 +6.8%，在 ±10% 内）。
- **极弧扫描**：0.85 → 峰峰 10.965% FAIL；0.80 → 14.876% FAIL（h=12 恶化）；
  **0.90 → 9.963% PASS**。三者 T_avg 均在窗，唯极弧 0.90 压住 h=12 族。
- **网格闭环**：`mesh_m2_spm_g03.json` TOTAL 56584、OVERALL_PASS True
  （5 组 LengthOp 合规、Band ≤0.25、各对象组非零、气隙层数 ≥2）。I33 已闭环
  （未求解工程导空表头，已求解工程正常；空 JSON `mesh_m1_spm.json` 保留 FAIL 证据）。
- **验收**：492→504 pytest passed（含并发新增 12 例）、ruff 全绿、M1 几何自检全 PASS、
  8 块极性与平行充磁矢量护栏 5 例通过。
- **I31/I32/I33 状态**：I31 转矩目标 **CLOSED**；I32 拓扑 intersect **CLOSED**；
  I33 网格统计 **CLOSED**。遗留非阻塞项见 SPM_DESIGN §7.3（空载 BEMF/Bg 超窗、
  0.50mm 贴片退磁 E6、胶缝敏感性、OD120 口径修正）——不推翻本次达标结论。
- **曲线证据**：`projects/results/ipm8p48s/spm_torque_scan.png`（3 档 t + 最终点）。


### SPM M4 从零起动曲线（2026-11-26 21:55）— 演示图达成

- 用户要求"完成转矩目标后继续做从零开始的图像（之前做过的）" ⇒ 复用
  `docs/DEMO_CASE_M4_TORQUE.md` §3 正解：稳态口径 + 电流软启动
  `i=−13.856·min(t/0.02,1)·sin(628.3185·t+90°)`，转速钉死 1500 rpm。
- 新建 `spm_m4_start.py` [KEEP]：唯一替换是建模用 `spm_build.build_script`、
  几何取 SPM 最终设计点（core_od=90.65 / 极弧 0.90 / t_pm=0.50）；三条已证否
  机械瞬态路线不提供。段2 求解脚本完全复用 IPM（已真机验证三量齐导）。
- **M4 401 点实测**（`ANALYZE_OK 848.8s`、Normal completion、CSV 402 行）：
  t=0 **−0.00356 N·m（≈0）**、19.5 ms 进入 95% 稳态带、峰值 27.569 N·m、
  末段稳态 **26.797 N·m**（与 M3 T_avg 26.6968 差 0.4%）、转速恒定 1500 rpm。
  证据：`spm_m4_start_spm_steady.json`、`m4_start_summary_spm_steady.json`、
  `spm_m4_start_curve.png`。
- 坑：`ipm_m4_plot.py` 原把摘要写到默认 `m4_start_summary_start.json`，
  覆盖了 IPM 历史证据 —— 已 `git checkout` 恢复原文件，改用 `--case spm_steady`
  写专属摘要。另给 plot 加 `--topology` 参数（默认 IPM 不变）修正图标题口径，
  标题现为"SPM 8p48s 贴片平行充磁 — 恒转速稳态 + 电流软启动（401 点）"。
- 504 pytest passed / ruff 绿。未改判据、未删任何 FAIL 记录。


### I35（优化项，2026-11-27 16:32 用户指令）— 增加磁钢厚度 + 重算电流（空载/负载双验证）

- **用户指令**：「下一步增加厚度，0.45mm 太薄了，可以更改电流，空载和负载验证一下，重新计算合适的电流和厚度，写进每日任务计划书，明天按时执行」。
- **动机**：当前 t/g=0.667、t/τ_pole=1.25%，贴片过薄；机械强度与抗退磁裕度未验证（E6 的 SF=2.11 是 IPM V 型磁钢，不能外推到 0.45mm 贴片）。
- **授权变更**：用户明确解除 Imax=13.856 A 冻结，允许改电流；但判据 22.5–27.5 / 峰峰≤10% / 主谐波≤5% / 跳变≤15% 不动，FAIL 不删。必须单变量：先定厚度，再按计算值改电流。
- **解析定源（assumption=待验证）**：新建 `spm_sizing_calc.py`。5 个 FEA 点拟合 T(t,13.856)≈37.7646+15.7561·ln(t)（残差 −1.65%~+0.90%），Bg 用 t=2.38 实测 1.0114 T 校准（系数 1.0671），BEMF 外推自 273.4 V。
  | t_pm | core_OD | I@25Nm | BEMF_est | 380V 余量 |
  |---:|---:|---:|---:|---:|
  | 0.45 | 90.75 | 13.755 | 137.79 | 1.592 |
  | **0.65（首选）** | **90.35** | **11.182** | **169.74** | **1.293** |
  | 0.90（备选） | 89.85 | 9.594 | 198.50 | 1.105 |
  | 1.20（不测） | 89.25 | 8.524 | 223.07 | 0.984 |
- **执行计划**：`projects/IPM_8p48s/DAILY_PLAN_2026_11_28.md`（KEEP）。首选 t=0.65/极弧0.90/I=11.182 A，空载 401 点验 BEMF≤219.4V（380V 上限）+ 负载斜槽 3×401 点验四项判据；T_avg 出窗按 `I_new=11.182×25/T_avg` 微调一次（不改厚度）。BEMF 118–145V 原窗按判据记 FAIL 留档，380V 口径是否替代由周检裁定。
- **自动化**：任务 `74244a4a` 已更新 prompt，rrule 每日 13:30 原样保留（用户设定严禁改）。
- **状态**：OPEN，待 11-28 13:30 执行。本轮只做解析计算与计划，**未跑真机、未改判据、未删任何 FAIL**。


#### 2026-11-27 19:xx — I35 思路一实测（今晚加跑）：t=0.65 / cps=8 / I=13.978 A 单片四项 PASS

- 用户 19:07 授权「思路一降匝数」今晚试一次；19:09 确认。改 `spm_m3_load.py` /
  `spm_skew_slices.py` 加 `--cps`、`spm_sizing_calc.py` 加 cps 维度（BEMF∝N_ph、I∝1/N_ph），
  +1 护栏测试（cps 单变量：除 CPS 行外生成脚本逐字一致）→ SPM 护栏 8 passed / ruff 绿。
- 解析定源 `--cps 8`：t=0.65/core_OD 90.35 → I=**13.978 A**、BEMF_est **135.79 V**
  （PASS 118–145 V 原窗）、380V 余量 1.616。`assumption=待验证`。
- **单片 401 点真机**（`ANALYZE_OK`/`Normal completion`，BUILD/SOLVE rc=0，22 min）：
  T_avg **25.1711 N·m PASS**、峰峰 **9.9325% PASS**（比 t=0.45 单片 10.1304% 更低）、
  主谐波 h=24 2.9688% PASS、跳变 3.9194% PASS、电流 13.978 A 真施加。
  证据 `spm_m3_t065c8_check.json`、`spm_m3_load_t065c8.json`。
- 负载 BEMF（I21 口径）：A 相基波 **227.0949 V @124.67°**、RMS **161.8591 V**——
  这是**负载**含电枢反应口径，不等于解析空载 135.79 V；空载 BEMF 待补测。
- 判定：比原 t=0.45/cps=10 基线**有进步**（厚度 +44%、电流回到 13.978 A、峰峰单片已过线、
  T_avg 仍落 25±0.5）。斜槽 3 片验证已发起，完成后决定是否更新明日计划首选。


#### 2026-11-27 20:xx — I35 思路一闭环：t=0.65/cps=8/I=13.978 A 空载+负载双验证全 PASS

- **斜槽 0.75 三片 401 点**（`ANALYZE_OK`/`Normal completion` rc=0，总 63 min，单片 s0 1222.7 s）：
  单片 T_avg 25.1734/25.1711/25.1687、单片峰峰 9.9057/9.9325/9.9252%（各过线），
  逐点平均后 **T_avg 25.1711 N·m PASS、峰峰 0.8128 N·m=3.2292% PASS、
  主谐波 h=24 0.9894% PASS、跳变 1.4692% PASS** —— 四项全过。
  证据 `spm_m3_skew_spm_t065c8_skew075.json`（KEEP）。
- **空载 401 点**（`ANALYZE_OK 1011.0 s`，零电流 cps=8）：相 BEMF RMS
  **135.1203/135.1229/135.1223 V**（A/B/C），均值 **135.1218 V** ⇒
  **118–145 V 原窗 PASS、380V 上限 219.4 V PASS**；解析预测 135.79 V，误差 **0.49%**。
  证据 `m2_noload_spm_t065c8.json`（KEEP）。**Bg/齿槽未重算**（求解脚本未导 gap_mag.csv/
  tq_noload.csv，管线缺口如实留痕，未改 FEA 数据凑数）。
- **对比旧基线（t=0.45/cps=10/I=13.856）**：厚度 0.45→0.65（+44%）、t/g 0.667→0.963、
  电流 13.856→13.978（回到基线量级）、空载 BEMF 从外推 137.79→实测 135.12 V、
  峰峰 3.6022%→3.2292%、主谐波 1.0432%→0.9894%、T_avg 25.0004→25.1711。
  **结论：有进步**，降匝数思路一成立。
- 管线改动：`spm_m3_load.py`/`spm_skew_slices.py` 加 `--cps`（默认 10，向后兼容）、
  `spm_sizing_calc.py` 加 cps 维度、+1 护栏测试（cps 单变量逐字一致）。
  全量 **507 passed** / ruff 绿。**判据未改、FAIL 未删、未碰 OD120/E8**。
- 判据未改、FAIL 未删；新基线是否替换 t=0.45 由明日（11-28 13:30）正式执行后裁定，
  本轮为今晚加跑的探索验证，已先行写账本留痕。

### I34（**CLOSED**，2026-11-26 23:47 用户反馈）— 转矩幅值精调到 25.0±0.5 N·m ✅ 2026-11-27 斜槽 0.75 达成

- **用户反馈**：「转矩上还有点小瑕疵，不是很接近 25 N·m，这一点明天的任务里优化一下」。
- **现状**：SPM 最终设计点 t_pm=0.50 / 极弧 0.90 / Imax 13.856 A 实测 T_avg=**26.6968 N·m**，
  在判据 22.5–27.5 内（PASS），但距 25 偏 **+6.8%**。用户希望更接近 25。
- **定性**：这是**优化目标收紧**，不是判据变更。判据 22.5–27.5 保持不动，
  FAIL 记录不删；新增"精调目标 25.0±0.5"作为 Optimize 方向，达不到仍按原判据判定。
- **明日路线（assumption=待验证，单变量）**：在极弧 0.90 固定下，t_pm 从 0.50 往下扫
  **0.45 / 0.40 mm**（两点线性外推 0.50→0.435 落 25.0，取 0.45 先测）；每点 401 点、
  Imax 仍 13.856 A 不改电流。**关键约束**：当前峰峰 9.963% 距 10% 仅 0.037 pt，
  减薄可能恶化峰峰（t=0.65 时 10.33%）；每点须同时看 T_avg 与峰峰，若峰峰破 10%
  则先 FFT 定阶次，配合极弧 0.92 或斜槽 0.75，不得直接调参。
- **OD120 联动**：明日第一优先已是 OD120×L200/380V 缩放。Kt∝N·D·L，D×0.8 与 L×1.25
  抵消，转矩仍是 26.7 量级 ⇒ **OD120 也需同一精调**（t_pm 按比例 0.40→0.36 附近），
  不能照抄旧缩放表 1.904mm（那是 t_pm=2.38 旧几何，会重复今天的厚度扫描）。
- **自动化 prompt 已同步**：保留 rrule 每日 14:30，只改任务正文。

**新增 KEEP**：`spm_build.py`、`spm_check.py`、`spm_m3_load.py`、`tests/test_spm_build.py`（5 例）、`m1_spm_build_check.json` / `m1_spm_g03_build_check.json` / `mesh_m1_spm.json`（FAIL 证据）。TEMP：`D:/ANSYS_Run/spm_*` 诊断脚本与日志不入库。**未做**：未改 IPM baseline、未改判据、未删任何 FAIL 记录、未改电流凑数。


#### 2026-11-27 每日 13:30 — I34 精调第 1 点：t_pm=0.45 / 极弧 0.90（FAIL 峰峰，留档）

- 单变量：core_od=90.75（t_pm=0.450），极弧 0.90、Imax 13.856 A、φ_abs=90°、f=100Hz 全固定。
  401 点 `ANALYZE_OK`/`Normal completion`，求解 981.0 s，BUILD/SOLVE rc=0。
  CSV `tq_load.csv` 402 行、表头 `[NewtonMeter]`（scale=1）。
- **独立重算 `ipm_m3_check.py` → `spm_m3_t045a90_check.json`（status=FAIL）**：
  T_avg **24.9991 N·m**（精确命中 25.0±0.5，PASS）、峰峰 **2.5325 N·m = 10.1304%**
  **>10% FAIL（超 0.1304 pt）**、主谐波 h=24 0.7819 N·m=3.128% PASS、
  跳变 1.0438 N·m=4.175% PASS、电流 13.856 A 真施加 PASS。负载 BEMF 基波 291.0078 V@140.36°。
- **FFT 定阶次（末周期 200 点，t 单位 ms 校正后）**：h=24 3.128%（主导）、h=12 1.788%、
  h=36 0.977%、h=6 0.461%、h=48 0.174% ⇒ 48 槽/8 极槽谐波族，与 11-26 t=0.50 诊断同族。
- **处置**：T_avg 已达标，禁止改电流或 t_pm 凑峰峰。按 I34 约束走极弧单变量补救
  （极弧 0.90→0.92），已发起 t045a92 401 点。**t045a90 的 FAIL 记录不删、判据未改**。
- 证据：`spm_m3_load_t045a90.json`、`spm_m3_t045a90_check.json`、
  `D:/ANSYS_Run/csv_spm_m3_t045a90/`（TEMP）、`spm_m3_solve_t045a90.log`（TEMP）。


#### 2026-11-27 — I34 CLOSED：斜槽 0.75 达成 25.0004 N·m / 峰峰 3.6022%（四项 PASS）

第 2 点（极弧 0.92，t=0.45）：T_avg 25.1007、峰峰 **10.8601% FAIL（比 0.90 恶化 0.73 pt）**
⇒ 极弧 0.90 确认为最优点，弃极弧路线（证据 `spm_m3_t045a92_check.json`，FAIL 留档）。

第 3 点（斜槽 0.75，t=0.45/极弧 0.90）：新建 `spm_skew_slices.py`（KEEP），
`spm_build.spm_magnets` 加 `cfg.rotor_init_deg` 使贴片几何与平行充磁矢量同步转
（+2 护栏测试，0° 恒等逐位复现）。3 片机械角 −2.8125/0/+2.8125°（γ=0.75×7.5°=5.625°），
每片电流 φ_abs 补 Δ_elec=Δ_mech×4（IPM D5 已验证口径），各 401 点
`ANALYZE_OK`/`Normal completion` rc=0，单片 T_avg 25.0091/24.9991/24.9930、
单片峰峰 10.1249/10.1304/10.1225%（均未单独过线），逐点平均后：
**T_avg 25.0004 N·m PASS、峰峰 0.9006 N·m=3.6022% PASS、
主谐波 h=24 1.0432% PASS、跳变 1.6277% PASS** —— 四项全过，
`assumption=待验证` 项（3 切片近似上限口径）沿用 IPM D5 同口径。
直流转矩不降（25.0004 vs 24.9991，+0.005%），h=24 槽谐波被相位互补从 3.128% 压到 1.0432%。

**新基线**：t_pm=0.45（core_od 90.75）/ 极弧 0.90 / 斜槽 0.75 / Imax 13.856 A 固定。
判据 22.5–27.5 / ≤10% / ≤5% 全程未改；t045a90、t045a92 的 FAIL 原样保留。
证据 `spm_m3_skew_spm_t045_skew075.json`（KEEP）；`D:/ANSYS_Run/csv_spm_m3_spm_t045_skew075_s*/`
与求解日志为 TEMP。全量 pytest **506 passed**（504→506，+2 护栏）。
**遗留**：起动曲线 `spm_m4_start_curve.png` 仍是旧 t=0.50 口径，待按新基线重出；
OD120 缩放版需从 t=0.45×0.8=0.36 起步走同一精调，不照抄旧 1.904mm 表。
