# Changelog

All notable changes to **ansys-maxwell-motor** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Docs — 2026-11-24 夜（转矩不稳定排查指导书本地化 + 气隙网格缺陷发现）

用户提交《ANSYS Maxwell 电机仿真转矩不稳定排查指导书》，要求并入每日迭代。逐条甄别后
落地为 `docs/TORQUE_TROUBLESHOOTING.md`，**发现一处真实网格缺陷**。

- 新增 `docs/TORQUE_TROUBLESHOOTING.md`：本地化排查书。含工况分辨（稳态 vs 起动判据不通用）、
  五方向排查（每条标注本项目状态）、波形诊断表（带实测对照）、6 步 SOP、
  **与原文的 3 处出入**（恒速+Load Torque 不能共存 / 不是拍频 / 不是 J 问题）。
- **发现缺陷**：`AirgapRing` 径向只有 ≈1.48 层（`mesh_m4_chirp2.json` 实测 rms_edge 0.2277 mm
  ÷ 气隙 0.3375 mm），且 `ipm_build.py` 的 4 组 `AssignLengthOp` 完全没覆盖它。
  这可能与 h=12（1200 Hz 槽通过频率）主谐波相关——转矩是气隙应力张量的积分，
  1.5 层时高度依赖插值。
- `PROJECT_SPEC.md` §9：新增 4 条契约（AirgapRing 必须有独立 LengthOp、气隙层数 ≥2.0
  计入 §8 判据、起动工况必须导 Speed、读数先看表头单位）。
- 每日任务 prompt 更新：第一优先改为「气隙网格层数单变量复测」，并把 3 处纠正写成禁令，
  防止明天照着原文去"修"一个不存在的 Load Torque 问题。rrule 未动（仍是每日 14:30）。

### Added — 2026-11-24（IPM M4 起动工况：机械瞬态 401 点 / 200 ms）

用户提问「为什么没有转矩从零开始上升的曲线」。根因不是画错，是**口径**：M1'–M3' 全部
`Consider Mechanical Transient=False` + 转速钉死 `1500rpm`，求解器从不积分
`J·dω/dt = T_em − T_load`，所以 t=0 首点就是额定转矩（`tq_load.csv` 首行 26.58 N·m）。
新增独立工况 M4 补上起动曲线，不改动 M1'–M3' 任何一个字符。

- 新增 `projects/IPM_8p48s/ipm_m4_start.py`：M4 驱动（建模 + 求解 + 导出）。时间口径
  `StopTime=0.2s` / `TimeStep=0.0005s` → **400 步 = 401 点**，与稳态工况同规模；
  叠加 `SaveFieldsType="None"`（只取转矩/转速，不存场快照）抵消机械瞬态 remesh 开销。
  实测机械瞬态比稳态慢约 1.5×（401 点 16m09s vs 12m03s）。
- **激励经两次真机证否后定为变频起动**：①固定 100 Hz 开环 → 转速峰 59.3 rpm、
  `position` 停在 358.7° 抖动（PMSM 无阻尼绕组，静止转子追不上 1500 rpm 旋转磁场）；
  ②位置反馈 `sin(p·Moving1.Position+φ)` → 转矩仅 55 µN·m、位置末值 0.00029°
  （`Moving1.Position` 不进 winding 表达式，退化为固定直流）；③变频起动
  `f(t)=f0+k·min(t,T)`、`θ(t)=2π[f0·t+k·min(t,T)²/2]` 可行性验证 40 ms 得 490.6 rpm
  （理论同步 520 rpm）。`--mode {chirp,open,closed}` 三条路径都保留，便于复查。
- 新增 `projects/IPM_8p48s/ipm_m4_plot.py`：起动曲线后处理 + 出图。单位从 CSV 表头读
  （I22 陷阱：`Moving1.Torque` 可能是 µN·m/mN·m），中文字体自动挑选。
- `projects/IPM_8p48s/ipm_build.py`：`build_script()` 新增 `motion` / `stop_time` /
  `time_step` / `save_fields` 四个可选参数。**默认值 = 现有行为**，M1'–M3' 生成物逐字不变
  （已有测试 `test_build_script_default_is_steady_state` 钉住）。
- 新增 4 条护栏测试：默认稳态口径、`motion` 写出官方 5 键、401 点规模保持、
  J 落在转子本体解析区间内。
- `docs/MAXWELL_INTERNALS.md` §13.11：机械瞬态 5 个键的官方签名（取自本机
  `MaxwellScriptingGuide.pdf` P758–760）+ 4 条踩坑（`DeleteMotionSetup` 要 Structured
  Array、`AssignBand` 同名冲突、`ChangeProperty` PropServer 无效、裸最小工程法不成立）
  + `.aedt` 二进制直搜的验证方法。
- `projects/IPM_8p48s/PROJECT_SPEC.md` §7.6：M4 契约（含 J 推导与"判据互不通用"禁令）。
- `projects/IPM_8p48s/PROBLEM_LEDGER.md` I27：问题定性与参数定源。

### Added — 2026-11-15 夜（G7 斜槽：线 THD 11.180% → 1.998%，齿槽 → 0.002%）

P11（THD 超下限）的单变量实验。结论先行：**斜槽 0.5 槽距把齿槽与 THD 同时打下来，
但基波同比例降额**，BEMF 出窗，必须与匝数重配（P12）一起落地。

- 新增 `projects/25Nm_PMSM/skew_multislice.py`：2D 多切片等效评估。取一个电周期
  （10 ms / 200 点）的 DFT，按 `(1/N)Σ exp(j2πh·Δt_j/T)` 在**谐波域**做平移平均；
  齿槽、BEMF/THD、负载转矩/脉动一次算完，并给「时域平移 vs 频域 `sinc` 因子」双法互校。
- 新增 `projects/25Nm_PMSM/skew_slice_check.py`：真机 N 切片与后处理的独立对照
  （齿槽 / BEMF / THD / 基波降额比 k1 四项），并显式列出**未覆盖**项。
- `scripts/motor_config.py`：新增 `rotor_init_deg` + 三道 validate 闸口（非数值 / 非有限 /
  超一圈告警）。`scripts/main.py::_gen_geometry`：`_ang_off` 把 8 块磁钢绕 Z 转该角度，
  guard 改 `abs(angle) > 1e-9`；默认 0.0 时生成物**逐字不变**（`--check` 仍 8/8）。
- `gen_maxwell_model.py`：新增 `--init-deg`；`maxwell/tpl_run.py`：`--case` 支持任意
  切片名（`maxwell_model_<case>/`）；`maxwell/tpl_solve_noload.py`：新增
  `GetFaceCenter` 形心日志（`.aedt` 几何加密，形心是多切片唯一的几何证据）。
- 结果（连续多切片）：0.25 槽距 → 齿槽 0.537% / THD 7.2741% / BEMF 118.7097 V；
  **0.5 槽距 → 齿槽 0.00058 N·m（0.002%）/ THD 1.9983% / 脉动 4.285% /
  `T_avg` 21.6056 N·m / BEMF 114.3847 V（−5.12%，低于 118 V 下限）**；
  1.0 槽距 → k1=0.827，`T_avg` −25.2%，不划算。证据 `projects/results/fea/skew_scan*`。
- 真机复核（`ANALYZE_OK` 706.5 / 651.7 / 537.0 s，12×401 行入 `fea/skew_slices/`）：
  3 片平均 vs 后处理 —— 齿槽差 **0.0012 N·m**、BEMF 差 **0.0015%**、THD 差 **0.0007 pt**、
  基波降额比差 **0.0033%** ⇒ 多切片等价性成立。
- 回归：新增 `tests/test_skew_multislice.py`（16 例，含 skew=0 逐位复现基线的恒等校验）
  与 `tests/test_rotor_init_deg.py`（12 例，几何偏置只改 2 行）。

### Fixed — 2026-11-15 夜（斜槽实现路上的 4 个静默错误）

- `AssignBand` 的 `Init Pos="7.5deg"` **不旋转几何**：401 点解决与基线逐点相同
  （max 3e-5 N·m、互相关滞后 0），白跑 726 s。改几何旋转磁钢扇区（径向磁化对绕 Z
  旋转不变），并把判据改成"波形必须变化"。
- 斜槽**不能**作用在转矩波形上：`T_load(t)` 的时间依赖含转子角与电流相位，直接平移
  等于重复移相，会得到"`T_avg` 与斜槽无关"的假不变量（首版三水平全为 22.6296 N·m）。
  正解：平均 `e_ph(θ)` 与 `T_cog(θ)`，电流不移相；skew=0 时与 FEA 负载转矩差 −0.02%。
- 2D 后处理的三个数值陷阱（均能被"跑通且结果漂亮"掩盖）：线性插值重采样（齿槽
  600 Hz 仅 33 点/周期）使恒等校验差 **4.67%**；单周期含重复端点使 THD 虚高
  **1.24 pt**（11.180% → 12.422%）；双边谱按 `h/T` 乘相位使基波掉到 **47.6%**。
  详见 `docs/MAXWELL_INTERNALS.md` §15.3。

### Added — 2026-11-15（M7：模板路径负载工况，`T_avg` 22.6296 N·m / 脉动 14.688%）

把「负载工况」从手写路径搬到生成器路径，G6 的最后一条验收（负载 `T_avg`）由此关闭。
关键约束是**空载生成物必须逐字不变** —— 否则 M8 的齿槽证据就不再对应当前仓库模型。

- `scripts/motor_config.py`：新增 `load_case` / `current_phase_deg` / `current_sign`
  三个字段（默认空载）与三条 validate 闸口（符号只能 ±1、三相初相必须 3 个、
  负载时电流/频率必须为正）。
- `scripts/main.py::_gen_winding()`：新增负载分支，把
  `I = sign·√2·I_rms·sin(2πf_e·Time + φ)` 在**宿主侧**算成字面量再写进生成物
  （IronPython 2.7 只吃字符串）；**空载分支保持原文本**，`--check` 仍 8/8 无漂移。
- `projects/25Nm_PMSM/gen_maxwell_model.py`：新增 `--case {noload,load}`；
  `build_config(load=...)`；负载生成到 `maxwell_model_load/`（派生件，已入 `.gitignore`）；
  `--check` 拒绝负载工况（不入库、不参与漂移门禁）。
- `projects/25Nm_PMSM/maxwell/tpl_solve_noload.py`：增 `TPL_CASE` 开关
  （`T4_tpl_load.aedt` / `csv_tpl_load/` / `tq_load.csv` / `flux_load_*.csv`），
  求解与导出逻辑一字不改；应用日志改 `tpl_app_<case>.log`，避开 AEDT「脚本同名 .log」。
- `projects/25Nm_PMSM/maxwell/tpl_run.py`：增 `--case`，并把 `CASE`/`BODY`
  **写死**进驱动副本（环境变量丢失时不会把负载解覆盖到空载基线）。
- 新增 `projects/25Nm_PMSM/m7_load_check.py`：末周期（10 ms / 201 点）梯形积分 +
  `ingest_fea.load_block` 双法互校；电流用原生 `WindingX_TrCrv.txt` 逐点比对并与
  指令表达式对表；输出 `projects/results/fea/m7_load_summary.json`，
  证据波形落 `projects/results/fea/m7_load/`。
- 真机（1 轮 rc=0，19:05:21→19:17:27，**726 s**，`T4_tpl_load.aedt` 1,046,651 B / 24 sheets）：
  **`T_avg` 22.6296 N·m**（手写 M5 22.3344，**+1.32%**；vs 25 N·m **−9.48%**）、
  **脉动 14.688%**（手写 32.389%）、末周期 DFT 600 Hz 分量 2.04 N·m 独占主导、
  电流逐点最大偏差 7e-5 A（0.001%）、Σ(v·i)=+37367.58（电动）、
  功率平衡 `T·ω` vs `3EI` **−0.62%**；导出 4 个 CSV 各 401 行。
- 回归：新增 `tests/test_load_winding.py`（11 例：空载零电流、基线不漂移、
  幅值/相位/符号、负载只改 winding、`--check` 拒绝负载、配置闸口）与
  `tests/test_m7_load_check.py`（8 例：`ms`/`mNewtonMeter` 单位、末周期窗口、
  梯形积分、指令电流对表 M5、原生 TrCrv 解析）。pytest **331 passed**、ruff 全通过。
- **同日 THD 复核（副作用记账）**：用 `ingest_fea.analyse_signal`（跳首周期、2–15 次）
  同口径复算 M8 梨形槽波形 —— 线 BEMF THD **11.180%**，比矩形槽 **10.595%**
  高 **0.59 pt**（矩形槽同法复现 10.595%，方法自证）⇒ **窄槽口压齿槽与压 THD 对冲**，
  G4 的 THD 项仍 FAIL，探索闸门不算"全绿"（`PROBLEM_LEDGER` P11）。

### Added — 2026-11-14（M8：表 2 梨形槽落地，齿槽 27.37% → 3.52%）

把 25 N·m 机型的定子槽从「窄口矩形」换成表 2 梨形槽，并第一次把「几何顶点」与
「线圈轮廓」收敛到**同一个数据源**：

- 新增 `scripts/slot_profile.py`：梨形槽 11 关键点 + 10 段（`Arc` 起点索引 4）+
  底部半圆 16 段离散（`pear_outline`）+ 鞋带面积/形心内缩/环带实切面积。
  几何字面量与线圈 `coil_pts` 都从它派生 —— 旧模板把同一组坐标写了两遍，
  改一处就错位（`StatorOuter and Coil_x intersect` 的来源）。
- `scripts/main.py::_gen_geometry()` 的 `pear` 分支重写：`x1=r_bore+Hs0`、
  `x2=+Hs1`、`x3=r_bore+Hs2−Rs`、`x4=r_bore+Hs2`（旧版全部从 `x0=r_bore−0.2` 起算，
  整槽短 0.2 mm 且只有 7 点、`Arc` 起点错在 3），12 个 `PLPoint`（11 + 闭合）+ 10 段。
- `scripts/motor_config.py::validate()` 增梨形槽三道闸：`Rs` 必须等于 `Bs2/2`
  （否则半圆起点不在圆上，Acis 补隐式连线静默变形）、`Hs2−Hs0−Hs1−Rs ≥ 0`
  （直身段为负即槽形自交）、轭部 <6 mm 告警。
- `projects/25Nm_PMSM/gen_maxwell_model.py`：`build_config` 切 `PEAR` + 表 2 六尺寸；
  `pmsm_config.py` 增 M8 梨形块与派生量（x0..x4 / 轭 16.0 / 面积 93.03 / 线圈 71.9 /
  满率 0.710），旧矩形常量保留供 S7–S9 复现。
- `template_vs_manual.py` 增 `--tag`：M8 证据落 `fea/m8_pear/` 与
  `template_vs_manual_m8_pear.json`，不覆盖 G4 的 `fea/tpl/`。
- 真机（1 轮 rc=0，`ANALYZE_OK 673.6s`，`T4_tpl_noload.aedt` 1,313,661 B / 24 sheets）：
  `StatorOuter` **9,764.151 mm²**（解析预测 9,764.16，偏差 0.001%）、`Coil_1`
  **71.863 mm²**（预测 71.863）；BEMF 相 RMS **120.5594 V**（基线 118.8832，**+1.41%**）；
  齿槽峰峰值 **0.8801 N·m = 3.52% 额定**（基线 6.84307，**−87.1%**），主频 598.5 Hz
  ≈ 24×25 Hz（槽极 LCM 序），两个 10 ms 窗口的峰峰值一致（0.8801/0.8801）。
- 回归：新增 `tests/test_pear_slot.py`（23 例：五条基准线、11 点对称性、10 段覆盖、
  面积三重自洽、弧采样亏损、线圈 72±5% 与不进气隙、满率、validate 闸口）；
  `test_gen_maxwell_model` 的线圈内缩判据改按槽型取多边形；
  `test_model_depth` 不再自抄一份机型配置（M8 换槽型后它才是红的根因）。
  pytest **312 passed**、`ruff` 全通过、`--check` 8/8 无漂移。

### Fixed — 2026-11-13（G4：模板路径 9 处"能建不能解"缺陷，空载解与手写路径等价）

模板产出的模型此前只能"建出来"，不能"解对"。今日把 m4 手写工程跑出 401 点解的全部前提
回灌模板，共 9 处：

- 几何：磁钢由**平板弦**（径向 45.825..47.775，插进定子 1.275 mm）改为**环形扇区**
  （43.875..45.825，弧 39.15°，内外弧各离散 24 段）；转子半径改为
  `磁钢内半径 + 0.03 mm` 并挖出磁钢浅坑（界面互补、无相切顶点）；槽口第一边改为
  `r_bore - 0.2 mm`（消除与内孔圆弧的相切非流形）；线圈由**槽轮廓 0.88 内缩**
  得到（原 13.2×5.7 矩形在 r=49.65 处穿出 3.2 mm 宽的槽壁）；
  `Region` 与定子/转子/磁钢/线圈/Band 布尔分离（`KeepOriginals=True`）。
- 材料：`_gen_materials()` 新增铁芯材料定义（`STEEL_MATS`，线性化 µr=1000 / σ=2.0e6 /
  ρ=7650），`StatorOuter`/`RotorOuter` 绑定 `stator_material`/`rotor_material`
  —— 此前定转子建的是 `vacuum`，磁路整个落在空气上且不报错。
- 边界：`AssignVectorPotential` 从 `_gen_boundary()` **前置进 `_gen_geometry()`**，
  紧跟 Region 建圆之后。Region 一旦切孔，`GetEdgeIDsFromObject("Region")` 会把外圆
  与所有孔边一起返回，`AZ=0` 落到材料界面 ⇒ 磁通被短路（求解器不报错）。
- 求解：存场改 `N=2`（与 m4 全时长口径一致，401 个采样点不变）。
- 新增 `projects/25Nm_PMSM/maxwell/tpl_solve_noload.py`（同进程 execfile 生成物 →
  `SaveAs` → `Analyze("Setup1")` → 导出 `FluxLinkage`/`Moving1.Torque` 全时长解，
  含面积自检与 `data_rows` 非空校验）与 `maxwell/tpl_run.py`（宿主侧清洗脚本、
  起 `ansysedt -RunScriptAndExit`、抓日志）。
- 新增 `projects/25Nm_PMSM/template_vs_manual.py`：两条路径逐项对比，含单位换算
  （`Time [us]` / `Torque [mNewtonMeter]` —— 403 N·m 的来源）与 `e = -dλ/dt` 口径。
- 真机结果（1 轮 rc=0，`ANALYZE_OK 437.1s`）：`T4_tpl_noload.aedt`（767,290 B，
  24 sheets，Region 2 faces 面积守恒 11,053.35 mm²）；BEMF 相 RMS **118.9077 V**
  vs 手写 118.8832 V（**+0.02%**）；齿槽峰峰值 **6.8181 N·m** vs 6.84307（**−0.37%**）；
  三相磁链峰峰 0.518813/0.518829/0.518833 Wb（不平衡 0.004%）。
- 回归：新增 `tests/test_gen_maxwell_model.py::TestG4GeometrySelfConsistency`（7 例：
  磁钢扇区半径、转子内嵌、线圈顶点落在槽内（射线法，槽肩是凹角）、Region 布尔、
  铁芯材料绑定与边界先于布尔）与 `tests/test_template_vs_manual.py`（6 例单位/求导口径）；
  pytest **289 passed**、`ruff check scripts tests examples` 全通过。

### Fixed — 2026-11-12（G3b：建模模板 8 处 API 回灌，真机全链路建模通过）

- `scripts/main.py::_gen_geometry()` 回灌 M2 阶段手改出来的 4 处真机修复：
  `SetModelUnits` 用 `"Units:="`（非 `"Length:="`）、`DuplicateAroundAxis` 补第 3 参
  `["NAME:Options", ...]`、槽克隆体按 `Slot_1_1..` 实名相减、`CreatePolyline` 的点/段
  嵌进 `PolylineParameters`（pear / rectangular / trapezoidal 三种槽型同步）。
- 真机连跑三轮又抓出 4 处同类缺陷并修复：
  `_gen_winding()` 改用逐槽边 `AssignCoil`（2021.1 的 `AssignCoilGroup` 是 2 参签名，
  单数组调用报 `expects at least 2 arguments`）；`_gen_boundary()` 的
  `AssignVectorPotential` 改用运行期 `GetEdgeIDsFromObject`（`can only be assigned on
  1D entities`），`AssignBand` 键名改 `"Init Pos:="`（带空格）；`_gen_mesh()` 用
  `AssignLengthOp` 替代 2021.1 不存在的 `AssignSurfApproxOp`。
- `projects/25Nm_PMSM/gen_maxwell_model.py` 重构为可测函数
  （`build_config` / `render_scripts` / `combine` / `artifacts` / `write_all` / `check`），
  新增 `--check`（漂移列出文件并 rc=1）与 `--out_dir`（此前参数被静默忽略）；
  合并脚本表头数值改为随配置走，不再硬编码 150/93/160/0.675。
- `projects/25Nm_PMSM/maxwell_model/prepare_batch.py` 新增 `--aedt`，回归验证不再覆盖
  `M2_25Nm.aedt`。
- 新增 `tests/test_gen_maxwell_model.py`（13 例）：生成物与模板逐字比对（双向防漂移）、
  8 处 API 修复的模板级护栏、四种槽型几何脚本可编译、`--check` 反向验证。
- 真机证据（rc=0 ×3）：第 3 轮 `G3b_regen3.aedt`（288,557 B）`BODY_OK`，`Sheets=24`、
  `Solids=0`、`Conductor number'='40'` ×12、`VectorPotential1`、`MotionSetup1`
  （`Move Type='Rotate'`/1500 rpm）、`Setup1`（20 ms/5e-5 s）、`ModelDepth='160mm'`。
- 文档：`docs/MAXWELL_INTERNALS.md` 新增 §13（8 处陷阱 + 报错原文 + 三轮证据）。

### Added — 2026-11-11（G3：2D 叠长 `ModelDepth` 注入闭环）

- `scripts/main.py`：`_gen_setup()` 在 `SetDesignSettings(DesignSettingsData)` 里注入
  `"ModelDepth:=", "<stack_length>mm"`；新增 `format_mm()` 归一尺寸字符串
  （160.0 → `160mm`，非整数保留有效位）。非正叠长直接在生成期抛 `ValueError`，
  不让 `Nonemm` 流到 AEDT。
- `scripts/motor_config.py`：`validate()` 增叠长闸口（缺失/非正 → `ERROR`，L/D>3 → `WARNING`）。
- `projects/25Nm_PMSM/maxwell_model/solve_25Nm_SPMSM.py`：`MODEL_DEPTH = "160mm"`
  进 `SetDesignSettings`，并删除文件头误导性的 `-ng -RunScriptAndExit`（与
  `-RunScriptAndExit` 互斥，是 2026-11-07 之前"启动即失败"的源头）。
- 生成物 `maxwell_model/setup.py` / `build_25Nm_SPMSM.py` 同步落地 `ModelDepth`。
- `tests/test_model_depth.py`（27 例）：模板注入 + 随叠长变化 + 生成文本可编译 +
  `validate()` 闸口 + 生成物与模板不漂移 + **4 处真机 API 修复护栏**。
- 真机验证（rc=0 ×3）：`G3_depth160.aedt`（23,905 B → `ModelDepth='160mm'`）、
  `G3_depth180.aedt`（23,930 B → `'180mm'`）、`G3_generated_setup.aedt`
  （23,906 B → `'160mm'`，由模板产出的 `setup.py` 本体执行）。

### Fixed — 2026-11-11（生成器段序与 API 说明）

- `projects/25Nm_PMSM/gen_maxwell_model.py`：合并顺序改为 `setup → materials → geometry`。
  旧序让合并脚本先建几何再定义材料，Maxwell 在 `SetMaterial` 处报 Unknown material，
  也是 `tests/test_prepare_batch.py::test_materials_before_geometry` 长期红灯的根因。
- 同文件增「⚠ 重跑前必读」：4 处真机 API 修复尚未回灌 `scripts/main.py` 模板，
  空白重跑会把模型改回不可解；护栏为 `TestModelerApiRegressions` 与
  `TestCombinedScriptApiFixes`。

### Added — 2026-11-10（M6：FEA 结果进入交付报告）

- `projects/25Nm_PMSM/make_report.py` 新增 §11「Maxwell 2D FEA 实测交叉校验」：
  `load_fea()` 读 `results/fea_results.json`，生成 10 行「解析 vs FEA」逐项对照表
  （相/线 BEMF、三相不平衡、THD、齿槽 ptp、`T_avg`、脉动、功率平衡、指令电流、`Kt`）
  与 3 张图（三相空载 BEMF、负载+齿槽转矩、齿槽频谱标注 600 Hz）。
  首屏 KPI 增「FEA 平均转矩」，结论区首条改为以 FEA 为准。
- `projects/results/fea/`：M4/M5 波形留档（`flux_a|b|c.csv`、`tq_noload.csv`、`tq_load.csv`，
  各 401 行全时长解），报告不再依赖 `D:\ANSYS_Run` 的外部文件即可复现。
- `tests/test_report_fea.py`（11 例）：JSON 结构/判据口径/物理自洽、CSV 必须 401 行、
  用留档 CSV 重算 `ingest_fea.compute()` 复现 JSON、源码级降级契约。

### Fixed — 2026-11-10（报告过期表述与渲染陷阱）

- 报告首页「FEA 待桌面执行」与附录「agent 沙箱无法初始化 AEDT 运行时」两句已与实机事实
  （2026-11-08 / 11-09 两次真机求解）相反，改为记录真实工程路径、求解耗时与 401 点解。
- §11 为普通字符串拼接，`%%` 会被原样输出（首版渲染出 `±25%%`、`折 81 匝 × %.5f`）。
  现以「生成后 grep `%%` 与 `%.Nf` 残留数均为 0」作为验收项。

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

## [4.5.0] — 2026-11-23 — "IPM 8p48s + load cases + FEA provenance"

本版把 skill 从「25 N·m 8p12s 表贴电机」扩展到「8p48s 内嵌 V 型永磁 + 负载仿真 +
真机证据链」。不改变既有 API，但新增了 3 个建模/后处理脚本与 2 份验收规范。

### Added — IPM 8p48s 项目（commits 4fc5c92 / 97da23f / d71f489 / a2f0ef4）

- 新项目目录 `projects/IPM_8p48s/`：设计契约 `PROJECT_SPEC.md`、问题账本
  `PROBLEM_LEDGER.md`（I1–I22）、绕组表 `WINDING_TABLE.md`。
- 几何定源 `ipm_geom.py`：48 槽梨形槽 7 尺寸按槽距 6.0868 mm 约束推导
  （`Rs=Bs2/2` 相切恒等式）、q=2 双层分布绕组（y=5 短距、`k_w1=0.9330`）、
  单层 V 磁钢 16 块（`v_single=(33,38,13,3)`、OD 桥 1.549 mm）、
  气隙独立环 `AirgapRing`（外 R46.5 / 内 R46.1625 / 厚 0.3375 mm vacuum）。
- 绕组截面按用户要求改为**槽内切向 y=0 对称的矩形 4 点**
  （x[48.4,58.2] / y[±0.2,±1.2]、9.800 mm²/条、槽壁边距 0.2023 mm），
  不是径向「一远一近」、也不是异形内缩切分。
- 脚本 `ipm_build.py`（真机建模）、`ipm_m1_check.py`（116→117 sheet 自检）、
  `ipm_m2_check.py` / `ipm_m2_noload.py`（401 点空载）、
  `ipm_m3_load.py` / `ipm_m3_check.py`（401 点负载 + 转矩平直 FFT/逐点差分）。
- 负载电流按用户截图公式：`Ia=Imax·sin(2πf·t+φ)`、`f=p·n/60=100 Hz`、
  `ω=628.3185 rad/s`；`--phi` 默认 0 = 相对 BEMF 反相点，`--phi-abs` 兼容历史。
- 测试 `tests/test_ipm_8p48s.py` / `test_ipm_m2.py`（全量 468 passed）。

### Fixed — 磁路与材料真因（commits e32ad2e / 128d45f / 25316ba / ae93bde）

- **Bg 塌陷真因翻转**：不是磁钢埋深或隔磁桥不饱和，而是 AEDT 2021.1 的
  `EditMaterial` 塞 `BHCoordinates` 4 种写法全被静默丢弃，铁芯按 μr=1 求解
  （旧 `.aedt` grep `nonlinear`=0）。改用 `CloneMaterial("JFE_Steel_35JN270",
  "M270_35A")`，66 点厂商 BH 真机落盘（`nonlinear`=2），Bg **0.182 → 0.662 T**。
- 删除静默无效键 `"N:="`（`SaveFieldsType`）；存场口径与注释一致。
- I20 电流相位参考系：`φ=0` 在本机与 BEMF 正交导致 `T_avg≈0`，改为相对
  BEMF 反相点起算，`φ=90°` 真机 `T_avg` 转正且与理论差 0.017%。
- 空载/负载口径按用户明确纠正：**空载 = winding 0A 无电流**，负载 = 三相正弦电流。
  禁止在空载工况注入电流凑 25 N·m（判自演）。

### Added — 验收与流程（commits 30c8d40 / da1fb68 / c33bdcc / f9ef41e / f9b0402 / 25316ba / a997bd7 / 5933160）

- SPM 项目 G4-B 场探针收口：解后纯 `FieldsReporter` 后处理（不碰几何），
  Bg 0.8626 / B_tooth 0.9896 / B_yoke 1.1843 T 三行 FEA PASS。
- 契约 §7：气隙环几何、磁钢外移、两工况激励、转矩平直判据、I21 负载 BEMF
  幅值优化顺序（禁止坏磁路上调参掩盖）。
- 契约 §8：**每次建模后剖分网格 + 质量报告**（`mesh_<case>.json`：单元/节点数、
  min/max 单元、质量指标或 `unavailable`、耗时、MaxLength），流程改为
  「建模 → 剖分+统计 → 401 点求解」。
- 周检 G10 监督几何位置/两工况/网格剖分；周检 2026-11-23 判定
  「技能可用 / 设计不合格 / 流程不合规」，M4' 网格全缺为 P0。
- 文件生命周期规范 `docs/FILE_LIFECYCLE.md`（KEEP / TEMP / ARCHIVE），
  每日打标、周检清理 TEMP。
- 中文主版 `SKILL_zh.md` 与英文/原版 `SKILL.md` 内容同步。

### Changed — 工程卫生（commit 902f49f）

- 清理 9 个历史未提交改动：MCP 幂等建项目、36 槽绕组 v4 修复
  （`AssignCoilGroup` 调用形式 + 线圈居中）、公式溯源注释。
- 全量测试 437 → 468 passed。

### Known issues（本版未解决，非回归）

- IPM 8p48s 设计仍未达标：BEMF 63.87 V < 118、齿槽 13.89% > 5%、
  `T_avg` 1.56 N·m < 22.5、E8 效率 FEA 与 E6 退磁 FEA 仍缺。
- M4' 网格剖分链路全缺（无 `mesh_<case>.json`、API 未真机探测），契约 §8 未执行。
- I16「极间 ≤2.0」判据经解析扫描与单层 V 几何不可兼得，周检已裁定改为
  「OD 桥 ≤2.0 且桥内 B≥1.8 T」，桥内 B 实测尚未完成。

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
