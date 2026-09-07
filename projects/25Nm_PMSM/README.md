# 快速启动指南 — 25N·m PMSM Maxwell 自动化仿真

## 前置条件

1. **ANSYS Electronics Desktop (Maxwell)** 已安装并可启动
2. **MCP Server** 已配置并运行（通过 Windows COM 接口连接 Maxwell）
3. **Python 3.8+** 已安装（用于参数计算器）

## 一键运行全部仿真

```bash
cd "D:\桌面\maxwell-motor-25Nm\scripts"
python run_all_simulations.py
```

## 分步运行

```bash
# 仅构建几何模型
python run_all_simulations.py --step 1

# 仅分配材料和激励
python run_all_simulations.py --step 2

# 从第3步开始运行（无负载反电动势）
python run_all_simulations.py --from 3

# 仅运行额定负载仿真
python run_all_simulations.py --step 4

# 检查项目状态
python run_all_simulations.py --status
```

## 仿真执行顺序

```
步骤1: 构建几何 → 步骤2: 材料/激励/网格
   │
   ├→ 步骤3: 无负载反电动势（验证绕组）
   │
   └→ 步骤4: 额定负载（核心性能数据）
         │
         ├→ 步骤5: 气隙磁密分析
         ├→ 步骤6: 过载（2倍电流）
         ├→ 步骤7: 铁耗分析
         ├→ 步骤8: 永磁体涡流损耗
         ├→ 步骤9: 电感计算（Ld/Lq）
         ├→ 步骤10: 退磁分析
         └→ 步骤11: NVH快速扫描
```

## 输出文件

所有结果导出到 `D:\桌面\maxwell-motor-25Nm\results\` 目录：

| 文件 | 内容 |
|------|------|
| `no_load_bemf.csv` | 反电动势波形、齿槽力矩 |
| `rated_load.csv` | 力矩、电流波形 |
| `airgap_flux_density.csv` | 气隙磁密空间分布 |
| `overload.csv` | 过载力矩 |
| `iron_loss.csv` | 铁耗分布 |
| `pm_eddy_loss.csv` | 永磁体涡流损耗 |
| `inductance_ld.csv` | 电感数据 |
| `demag_pm_*.csv` | 各磁钢退磁B场 |
| `nvh_radial_force.csv` | 径向力密度谐波 |

## 设计参数速查

| 参数 | 值 |
|------|-----|
| 外径 | 150 mm |
| 叠长 | 160 mm |
| 气隙 | 0.675 mm |
| 极数/槽数 | 8/12 |
| 每相匝数 | 81 |
| 额定电流 | 9.89 A (RMS) |
| 额定力矩 | 25.0 N·m |
| 效率 | 94.0% |

## 常见问题

### Q: Maxwell 连接失败？
A: 确保 ANSYS Electronics Desktop 已启动，且 MCP Server 配置了正确的 COM 接口路径。

### Q: 仿真不收敛？
A: 检查网格质量（气隙至少3层单元），减小时间步长，确认材料属性正确。

### Q: 力矩脉动过大？
A: 检查绕组布局是否正确，考虑增加斜槽或调整磁钢极弧系数。

### Q: 退磁风险？
A: 如果B_min < 0.2T，增加磁钢厚度或升级磁钢等级（N35 → N42SH）。
