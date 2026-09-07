#!/usr/bin/env python3
"""
多物理场耦合仿真编排器 (MDAO Orchestrator)
支持：电磁-结构-热三场联合仿真、IGBT热-电-力耦合、疲劳寿命预测

依赖：ansys.aedt.core (PyAEDT), ansys.fluent.core (PyFluent)
      未安装时自动降级为 DryRun 估算模式

用法:
  python mdao_orchestrator.py motor   # 电机多学科仿真
  python mdao_orchestrator.py igbt    # IGBT可靠性分析
"""

import json
import os
import time
import sqlite3
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# ============================================================
# 枚举与数据类
# ============================================================

class PhysicsType(Enum):
    """物理场类型"""
    ELECTROMAGNETIC = "electromagnetic"
    STRUCTURAL = "structural"
    THERMAL = "thermal"
    THERMAL_ELECTRICAL = "thermal_electrical"  # 热电耦合
    COUPLED_TE_MECH = "coupled_te_mech"        # 热电-机械耦合


class CouplingMode(Enum):
    """耦合模式"""
    ONE_WAY = "one_way"
    TWO_WAY = "two_way"
    SEQUENTIAL = "sequential"


class SolverType(Enum):
    """求解器类型"""
    MAXWELL_2D = "maxwell_2d"
    MAXWELL_3D = "maxwell_3d"
    MECHANICAL = "mechanical"
    FLUENT = "fluent"
    STEADY_THERMAL = "steady_thermal"
    TRANSIENT_THERMAL = "transient_thermal"


class FatigueModel(Enum):
    """疲劳寿命模型"""
    COFFIN_MANSON = "coffin_manson"   # 基于应变
    DARVEAUX = "darveaux"             # 基于能量
    BOTH = "both"                     # 双模型对比


@dataclass
class PhysicsConfig:
    """单个物理场配置"""
    physics_type: PhysicsType = PhysicsType.ELECTROMAGNETIC
    solver: SolverType = SolverType.MAXWELL_2D
    input_fields: list = field(default_factory=list)
    output_fields: list = field(default_factory=list)
    mesh_refinement: dict = field(default_factory=dict)
    convergence_target: Optional[float] = None


@dataclass
class CouplingStep:
    """耦合步骤"""
    step_name: str
    source_physics: PhysicsType
    target_physics: PhysicsType
    transfer_variable: str  # 传递变量：loss, temperature, force, displacement
    coupling_mode: CouplingMode = CouplingMode.ONE_WAY


@dataclass
class MDAOConfig:
    """MDAO主配置"""
    project_name: str = "mdao_project"
    work_dir: str = "./mdao_workspace"
    coupling_mode: CouplingMode = CouplingMode.SEQUENTIAL
    physics_configs: list = field(default_factory=list)
    coupling_steps: list = field(default_factory=list)
    max_iterations: int = 3          # 双向耦合最大迭代次数
    convergence_tol: float = 0.01    # 收敛容差（相对变化）
    dry_run: bool = False            # 空运行（不实际调用ANSYS）
    enable_database: bool = True     # 启用SQLite数据管理
    db_path: str = ""                # SQLite数据库路径
    # 集总参数热网络热阻 R_th (单位 K/W)：绕组热点 → 冷却液
    # 典型量级参考（需按机壳/冷却设计通过FEA校准）：
    #   水冷 water ≈ 0.05, 风冷 air ≈ 0.25, 自然冷却 natural ≈ 0.70
    # DryRun 估算公式：ΔT_winding = total_loss[W] × R_th；实际须 Fluent FEA 校核
    thermal_resistance: dict = field(default_factory=lambda: {
        "water": 0.05,
        "air": 0.25,
        "natural": 0.70,
    })
    # ---- ANSYS 实算配置（仅 dry_run=False 时生效）----
    # 本机：Maxwell 在 AnsysEM 21.1（ANSYSEM_ROOT211），Fluent/Mechanical 在 v252（AWP_ROOT252）
    aedt_version: str = "2021.1"      # Electronics Desktop 版本（连 21.1 Maxwell）
    fluent_version: str = "252"       # Fluent 版本（F盘 v252）
    non_graphical: bool = True        # 无图形模式运行（服务器/CI 场景）
    maxwell_project: str = ""         # .aedt 项目路径（电磁实算；空则降级估算）
    maxwell_design: str = ""          # Maxwell 设计名
    maxwell_setup: str = ""           # Maxwell 求解设置名
    mechanical_project: str = ""      # Mechanical 项目（结构/IGBT 实算）
    mechanical_design: str = ""
    mechanical_setup: str = ""
    igbt_thermal_project: str = ""    # IGBT 热-力多物理场项目
    igbt_thermal_setup: str = ""
    fluent_case: str = ""             # Fluent case 文件路径（热实算）


# ============================================================
# SQLite 多学科数据库管理
# ============================================================

class MultiphysicsDatabase:
    """
    多学科仿真数据库管理器
    9个专项库：电磁/应力/温度 各含 几何/材料/计算/结果
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS {table} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT,
        timestamp TEXT,
        param_name TEXT,
        param_value TEXT,
        unit TEXT,
        category TEXT,
        notes TEXT
    );
    """

    TABLES = [
        "em_geometry", "em_material", "em_calc", "em_result",
        "struct_geometry", "struct_material", "struct_calc", "struct_result",
        "thermal_geometry", "thermal_material", "thermal_calc", "thermal_result",
    ]

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._init_db()

    def _init_db(self):
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        for table in self.TABLES:
            self.conn.execute(self.SCHEMA.format(table=table))
        self.conn.commit()

    def save(self, table: str, project_name: str, param_name: str,
             param_value: str, unit: str = "", category: str = "", notes: str = ""):
        """保存参数到指定表"""
        if table not in self.TABLES:
            raise ValueError(f"Unknown table: {table}. Valid: {self.TABLES}")
        self.conn.execute(
            f"INSERT INTO {table} "
            "(project_name, timestamp, param_name, param_value, unit, category, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_name, time.strftime("%Y-%m-%d %H:%M:%S"),
             param_name, param_value, unit, category, notes)
        )
        self.conn.commit()

    def load(self, table: str, project_name: str):
        """加载指定项目的参数"""
        cursor = self.conn.execute(
            f"SELECT param_name, param_value, unit, category FROM {table} "
            "WHERE project_name = ?",
            (project_name,)
        )
        return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()


# ============================================================
# 疲劳寿命预测
# ============================================================

class FatigueLifePredictor:
    """
    焊层疲劳寿命预测
    支持 Coffin-Manson（应变）和 Darveaux（能量）两种模型
    """

    # Pb-Sn 共晶焊层疲劳参数（问题3溯源）
    # 出处：Pb-Sn 焊料经验疲劳系数，详见 references/multiphysics_guide.md §疲劳寿命模型
    #       其中 Darveaux C1-C4 为经典能量法经验常数（Darveaux 1997 体系）
    # 重要：不同钎料（SAC305/SnAgCu 等）参数差异显著，换材料 MUST 重新标定，否则寿命预测失准
    COFFIN_MANSON_PARAMS = {
        "A": 0.159,   # 疲劳延性相关量（Pb-Sn 共晶，来源：工艺拆解文档）
        "m": -1.98,   # 疲劳延性指数（经典CM指数≈-1.5~-2）
    }

    DARVEAUX_PARAMS = {
        "C1": 22400,    # 起裂常数 (Pb-Sn)
        "C2": -1.52,    # 起裂指数
        "C3": 5.86e-7,  # 裂纹扩展常数
        "C4": 0.98,     # 裂纹扩展指数
    }

    @classmethod
    def coffin_manson(cls, delta_epsilon_in: float) -> int:
        """
        Coffin-Manson 模型（基于应变）
        N_f = A * (Δε_in)^m

        Args:
            delta_epsilon_in: 非弹性应变增量

        Returns:
            循环周次 N_f
        """
        p = cls.COFFIN_MANSON_PARAMS
        if delta_epsilon_in <= 0:
            return float('inf')
        N_f = p["A"] * (delta_epsilon_in ** p["m"])
        return int(N_f)

    @classmethod
    def darveaux(cls, delta_w_avg: float, crack_length: float = 0.0,
                 total_length: float = 1.0) -> dict:
        """
        Darveaux 模型（基于能量）
        N_0 = C1 * (ΔW_avg)^C2          # 起裂周期
        da/dN = C3 * (ΔW_avg)^C4        # 裂纹扩展速率

        Args:
            delta_w_avg: 非弹性应变能密度增量 (MPa)
            crack_length: 当前裂纹长度
            total_length: 总焊层长度

        Returns:
            dict: {N0: 起裂周期, da_dN: 裂纹扩展速率, N_total: 总寿命}
        """
        p = cls.DARVEAUX_PARAMS
        if delta_w_avg <= 0:
            return {"N0": float('inf'), "da_dN": 0, "N_total": float('inf')}

        N0 = p["C1"] * (delta_w_avg ** p["C2"])
        da_dN = p["C3"] * (delta_w_avg ** p["C4"])

        remaining_length = total_length - crack_length
        N_propagation = remaining_length / da_dN if da_dN > 0 else float('inf')
        N_total = N0 + N_propagation

        return {
            "N0": int(N0),
            "da_dN": da_dN,
            "N_total": int(N_total),
            "crack_length": crack_length,
            "remaining_length": remaining_length,
        }

    @classmethod
    def predict(cls, delta_epsilon_in: float = None, delta_w_avg: float = None,
                model: FatigueModel = FatigueModel.BOTH) -> dict:
        """
        疲劳寿命预测

        Args:
            delta_epsilon_in: 非弹性应变增量（Coffin-Manson用）
            delta_w_avg: 非弹性应变能密度增量（Darveaux用）
            model: 使用哪个模型

        Returns:
            预测结果字典
        """
        results = {}
        if model in (FatigueModel.COFFIN_MANSON, FatigueModel.BOTH):
            if delta_epsilon_in is not None:
                results["coffin_manson"] = {
                    "N_f": cls.coffin_manson(delta_epsilon_in),
                    "delta_epsilon_in": delta_epsilon_in,
                }
        if model in (FatigueModel.DARVEAUX, FatigueModel.BOTH):
            if delta_w_avg is not None:
                results["darveaux"] = cls.darveaux(delta_w_avg)
        return results


# ============================================================
# 参数化扫描
# ============================================================

class ParametricSweep:
    """
    参数化扫描器
    支持孔洞率扫描、焊层厚度扫描、多参数组合扫描
    """

    @staticmethod
    def sweep_void_ratio(predictor_func, void_ratios=(0.0, 0.025, 0.05, 0.1)):
        """
        孔洞率参数化扫描

        Args:
            predictor_func: 接收void_ratio返回寿命预测的函数
            void_ratios: 孔洞率列表

        Returns:
            扫描结果列表
        """
        results = []
        for vr in void_ratios:
            life = predictor_func(vr)
            results.append({"void_ratio": vr, "life_prediction": life})
        return results

    @staticmethod
    def sweep_solder_thickness(predictor_func, thicknesses=(20, 40, 60, 80, 100, 120)):
        """
        焊层厚度参数化扫描

        Args:
            predictor_func: 接收thickness返回寿命预测的函数
            thicknesses: 厚度列表（μm）

        Returns:
            扫描结果列表
        """
        results = []
        for t in thicknesses:
            life = predictor_func(t)
            results.append({"thickness_um": t, "life_prediction": life})
        return results

    @staticmethod
    def find_optimal_thickness(sweep_results, model_key="darveaux"):
        """
        从扫描结果中找最优焊层厚度

        Args:
            sweep_results: sweep_solder_thickness 的输出
            model_key: 使用哪个模型的结果

        Returns:
            最优厚度和对应寿命
        """
        best = None
        best_life = 0
        for r in sweep_results:
            life = r.get("life_prediction", {}).get(model_key, {}).get("N_total", 0)
            if life > best_life:
                best_life = life
                best = r
        return best


# ============================================================
# MDAO 编排器
# ============================================================

class MDAOOrchestrator:
    """
    多物理场多学科仿真编排器

    支持的仿真流程：
    1. 电机多学科联合仿真（电磁→结构→热）
    2. IGBT封装可靠性分析（热→位移→应力→疲劳）
    3. 自定义耦合流程
    """

    def __init__(self, config: MDAOConfig):
        self.config = config
        self.db = None
        self.results = {}
        self.iteration = 0
        self.fea_backend = None
        if config.enable_database and config.db_path:
            self.db = MultiphysicsDatabase(config.db_path)
        os.makedirs(os.path.abspath(config.work_dir), exist_ok=True)
        # 实算后端加载（仅 dry_run=False 时尝试 PyAEDT；失败安全降级 DryRun）
        if not config.dry_run:
            try:
                from solver_backends import PyAEDTBackend
                self.fea_backend = PyAEDTBackend(config)
                print("[Backend] PyAEDT 真实 FEA 后端已加载")
            except Exception as e:
                print(f"[Backend] PyAEDT 不可用，降级 DryRun 估算: {e}")

    # ------------------------------------------------------------
    # 电机多学科联合仿真
    # ------------------------------------------------------------

    def run_motor_mdao(self, motor_params: dict) -> dict:
        """
        电机多学科联合仿真（电磁→结构→热）

        流程：
        1. 电磁场仿真 → 电磁转矩、损耗、磁密
        2. 结构静力学仿真 → 应力、应变（载荷=电磁力+离心力）
        3. 流固耦合热仿真 → 温度场（热源=电磁损耗）
        4. 多目标优化评估

        Args:
            motor_params: 电机参数字典
                - power: 功率 (W)
                - speed: 转速 (rpm)
                - voltage: 电压 (V)
                - poles: 极数
                - slots: 槽数
                - outer_dia: 外径
                - length: 长度 (mm)
                - cooling: 冷却方式

        Returns:
            多物理场仿真结果
        """
        print("\n" + "=" * 60)
        print("电机多学科联合仿真 MDAO")
        print("项目:", self.config.project_name)
        print("参数:", json.dumps(motor_params, indent=2, ensure_ascii=False))
        print("=" * 60 + "\n")

        results = {
            "project": self.config.project_name,
            "motor_params": motor_params,
            "physics_results": {},
            "coupling_log": [],
        }

        # Phase 1: 电磁场仿真
        print("[Phase 1] 电磁场仿真 (Maxwell2D/3D)")
        em_result = self._run_electromagnetic(motor_params)
        results["physics_results"]["electromagnetic"] = em_result
        results["coupling_log"].append({
            "step": "electromagnetic",
            "status": "completed",
            "outputs": ("torque", "losses", "flux_density"),
        })

        # Phase 2: 结构静力学仿真（载荷=电磁力+离心力）
        print("[Phase 2] 结构静力学仿真 (Mechanical)")
        struct_input = {
            "electromagnetic_force": em_result.get("radial_force_density"),
            "speed": motor_params.get("speed", 3000),
            "rotor_radius": motor_params.get("outer_dia", 80) / 2,
        }
        struct_result = self._run_structural(struct_input)
        results["physics_results"]["structural"] = struct_result
        results["coupling_log"].append({
            "step": "structural",
            "source": "electromagnetic",
            "transfer": "electromagnetic_force",
            "status": "completed",
            "outputs": ("displacement", "stress", "strain"),
        })

        # Phase 3: 流固耦合热仿真（热源=电磁损耗）
        print("[Phase 3] 流固耦合热仿真 (Fluent)")
        thermal_input = {
            "copper_loss": em_result.get("copper_loss"),
            "iron_loss": em_result.get("iron_loss"),
            "pm_eddy_loss": em_result.get("pm_eddy_loss"),
            "cooling": motor_params.get("cooling", "water"),
        }
        thermal_result = self._run_thermal(thermal_input)
        results["physics_results"]["thermal"] = thermal_result
        results["coupling_log"].append({
            "step": "thermal",
            "source": "electromagnetic",
            "transfer": "losses",
            "status": "completed",
            "outputs": ("temperature_field", "flow_field"),
        })

        # Phase 4: 多学科综合评估
        print("[Phase 4] 多学科综合评估")
        assessment = self._assess_motor(results["physics_results"], motor_params)
        results["assessment"] = assessment

        # 打印电机评估结果
        pf = assessment["pass_fail"]
        print(f"\n[电机评估] 效率={pf.get('efficiency')} | 结构安全={pf.get('stress')} "
              f"| 温升达标={pf.get('thermal')} | 总评={assessment['overall']}")

        # 保存到数据库
        if self.db:
            self._save_to_db("em_result", results["physics_results"]["electromagnetic"])
            self._save_to_db("struct_result", results["physics_results"]["structural"])
            self._save_to_db("thermal_result", results["physics_results"]["thermal"])

        # 保存结果
        result_path = os.path.join(self.config.work_dir, f"{self.config.project_name}_mdao.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存: {result_path}")

        return results

    # ------------------------------------------------------------
    # IGBT 封装可靠性分析
    # ------------------------------------------------------------

    def run_igbt_reliability(self, igbt_params: dict) -> dict:
        """
        IGBT 封装可靠性分析（热-电-力耦合 + 疲劳寿命）

        流程：
        1. 几何建模（7层结构）
        2. 材料参数定义（含Anand模型）
        3. 功率循环载荷施加
        4. 多物理场求解（温度→位移→应力）
        5. 疲劳寿命预测（Coffin-Manson + Darveaux）
        6. 参数化研究（可选）

        Args:
            igbt_params: IGBT参数字典
                - cycle_period: 功率循环周期
                - power_density_igbt: IGBT芯片发热功率密度 (W/m³)
                - power_density_frd: FRD芯片发热功率密度 (W/m³)
                - solder_thickness: 焊层厚度 (μm)
                - void_ratio: 孔洞率 (0-1)
                - env_temp: 环境温度 (℃)
                - num_cycles: 仿真循环次数

        Returns:
            可靠性分析结果
        """
        print(f"\n{'='*60}")
        print(f"IGBT 封装可靠性分析 (热-电-力耦合)")
        print(f"项目: {self.config.project_name}")
        print(f"参数: {json.dumps(igbt_params, indent=2, ensure_ascii=False)}")
        print(f"{'='*60}\n")

        results = {
            "project": self.config.project_name,
            "igbt_params": igbt_params,
            "physics_results": {},
            "fatigue_life": {},
        }

        # Phase 1: 结温分析
        print("[Phase 1] 结温分析 (温度场)")
        temp_result = self._run_igbt_thermal(igbt_params)
        results["physics_results"]["temperature"] = temp_result

        # Phase 2: 变形分析
        print("[Phase 2] 变形分析 (位移场)")
        deform_input = {
            "temp_field": temp_result.get("max_junction_temp"),
            "solder_temp": temp_result.get("max_solder_temp"),
            "solder_thickness": igbt_params.get("solder_thickness", 80),
        }
        deform_result = self._run_igbt_deformation(deform_input)
        results["physics_results"]["deformation"] = deform_result

        # Phase 3: 应力分析
        print("[Phase 3] 应力分析 (应力场)")
        stress_input = {
            "temp_field": temp_result.get("max_junction_temp"),
            "deformation": deform_result.get("max_displacement"),
            "solder_thickness": igbt_params.get("solder_thickness", 80),
        }
        stress_result = self._run_igbt_stress(stress_input)
        results["physics_results"]["stress"] = stress_result

        # Phase 4: 疲劳寿命预测
        print("[Phase 4] 疲劳寿命预测")
        delta_epsilon = stress_result.get("inelastic_strain", 0.01)
        delta_w = stress_result.get("inelastic_strain_energy", 0.5)

        fatigue = FatigueLifePredictor.predict(
            delta_epsilon_in=delta_epsilon,
            delta_w_avg=delta_w,
        )
        results["fatigue_life"] = fatigue
        print(f"  Coffin-Manson: {fatigue.get('coffin_manson', {}).get('N_f', 'N/A')} 次")
        print(f"  Darveaux: {fatigue.get('darveaux', {}).get('N_total', 'N/A')} 次")

        # Phase 5: 参数化研究（可选，基准锚定主流程实际应变/能量）
        if igbt_params.get("enable_sweep", False):
            print("[Phase 5] 参数化研究")
            sweep_result = self._run_parametric_sweep(igbt_params, baseline=stress_result)
            results["parametric_sweep"] = sweep_result

        # 可靠性判定（最小可验证 pass/fail）
        target_cycles = igbt_params.get("target_cycles", 1e5)  # 行业典型功率循环门槛
        cm_life = fatigue.get("coffin_manson", {}).get("N_f", 0) or 0
        dv_life = fatigue.get("darveaux", {}).get("N_total", 0) or 0
        solder_stress = stress_result.get("max_stress_solder", 0)
        # 核心判据：疲劳寿命 > 目标循环数
        # 注：焊层在功率循环中进入塑性为预期机理，应力超屈服不单独判 FAIL
        life_ok = (max(cm_life, dv_life) > target_cycles)
        results["assessment"] = {
            "target_cycles": target_cycles,
            "coffin_manson_life": cm_life,
            "darveaux_life": dv_life,
            "solder_stress_MPa": solder_stress,
            "plastic_regime": solder_stress > 30,  # 是否进入塑性（预期）
            "pass_fail": {"fatigue_life": life_ok},
            "overall": "PASS" if life_ok else "FAIL",
        }
        print(f"\n[可靠性判定] 目标循环={target_cycles:.0f} | CM={cm_life} | Darveaux={dv_life} | {results['assessment']['overall']}")

        # 保存结果
        result_path = os.path.join(self.config.work_dir, f"{self.config.project_name}_igbt.json")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存: {result_path}")

        return results

    # ============================================================
    # 内部方法 - 电磁场仿真
    # ============================================================

    def _run_electromagnetic(self, params: dict) -> dict:
        """电磁场仿真（Maxwell2D/3D）"""
        # 实算后端优先：已加载 PyAEDT 则委托真实 Maxwell 求解
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_electromagnetic(params)
            except Exception as e:
                print(f"  [Warning] PyAEDT 电磁求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 Maxwell 求解，使用集总估算")
            else:
                print("  [Note] 未加载实算后端（PyAEDT 不可用），使用 DryRun 估算")

        # 返回结构化结果（实际或估算）
        # P1 陷阱防护：power 单位必须为瓦特(W)；若为 kW 须先 ×1000，否则损耗全错
        power = params.get("power", 500)  # W
        speed = params.get("speed", 3000)
        return {
            "torque": power / (speed * 2 * 3.14159 / 60) * 1000,  # N·m
            "torque_ripple": 0.03,
            "copper_loss": power * 0.05,
            "iron_loss": power * 0.03,
            "pm_eddy_loss": power * 0.01,
            "efficiency": 0.91,
            "radial_force_density": 50000,  # N/m²
            "flux_density": 1.2,  # T
        }

    # ============================================================
    # 内部方法 - 结构静力学仿真
    # ============================================================

    def _run_structural(self, params: dict) -> dict:
        """
        结构静力学仿真（Mechanical）
        载荷 = 离心力（来自转速） + 电磁径向力（来自电磁仿真）
        """
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_structural(params)
            except Exception as e:
                print(f"  [Warning] PyAEDT 结构求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 Mechanical 求解，使用集总估算")
            else:
                print("  [Note] 未加载实算后端（PyAEDT 不可用），使用 DryRun 估算")

        speed = params.get("speed", 3000)
        rotor_radius = params.get("rotor_radius", 40) / 1000  # m
        omega = speed * 2 * 3.14159 / 60  # rad/s
        centrifugal_acc = omega**2 * rotor_radius

        # 离心应力 σ = ρ·ω²·r²（Pa），×1e-6 转 MPa
        rho_steel = 7850  # kg/m³
        centrifugal_stress = rho_steel * omega**2 * rotor_radius**2 * 1e-06  # MPa

        # 电磁径向力贡献应力（N/m² → MPa，量级换算 ×1e-6）
        em_force_density = params.get("electromagnetic_force", 1.0)  # N/m²
        em_stress_contribution = em_force_density * 1e-06  # MPa

        # 总应力
        total_stress = centrifugal_stress + em_stress_contribution

        return {
            "max_displacement": 0.02,  # mm
            "max_von_mises_stress": total_stress,  # MPa
            "max_shear_stress": total_stress * 0.5,  # MPa
            "max_strain": total_stress / 200000,  # ε = σ/E，E=200000 MPa
            "safety_factor": 200 / total_stress if total_stress > 0 else float('inf'),
            "centrifugal_acceleration": centrifugal_acc,
            "em_force_density": em_force_density,
            "centrifugal_stress": centrifugal_stress,
            "em_stress_contribution": em_stress_contribution,
        }

    # ============================================================
    # 内部方法 - 热仿真
    # ============================================================

    def _run_thermal(self, params: dict) -> dict:
        """流固耦合热仿真（Fluent）"""
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_thermal(params)
            except Exception as e:
                print(f"  [Warning] PyFluent 热求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 Fluent 求解，使用集总热网络估算")
            else:
                print("  [Note] 未加载实算后端（PyFluent 不可用），使用 DryRun 估算")

        # P1 陷阱防护：copper_loss/iron_loss/pm_eddy_loss 必须为瓦特(W)
        # 上游电磁仿真若输出 kW 须先 ×1000，否则热源量级错误
        total_loss = (params.get("copper_loss", 25) +
                      params.get("iron_loss", 15) +
                      params.get("pm_eddy_loss", 5))
        cooling = params.get("cooling", "water")

        # 集总参数热网络：绕组热点温升 ΔT = P_total[W] × R_th[K/W]
        # R_th 取自 config.thermal_resistance（默认水冷0.05，须按实际FEA校准）
        r_th = self.config.thermal_resistance.get(
            cooling, self.config.thermal_resistance.get("water", 0.05))
        temp_rise = total_loss * r_th  # [K] = [°C]，即温升

        # 各部件热点温度：基准为部件基础工作温度，磁钢/转子按热阻比回落
        # 注意：以下为 DryRun 集总估算，真实分布须 Fluent 三维流固耦合求解
        return {
            "max_winding_temp": 80 + temp_rise,
            "max_magnet_temp": 70 + temp_rise * 0.8,
            "max_rotor_temp": 60 + temp_rise * 0.6,
            "coolant_flow_rate": 5.0 if cooling == "water" else 0,
            "thermal_resistance": r_th,
            "temp_rise": temp_rise,
        }

    # ============================================================
    # 内部方法 - IGBT 热分析
    # ============================================================

    def _run_igbt_thermal(self, params: dict) -> dict:
        """IGBT 结温分析"""
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_igbt_thermal(params)
            except Exception as e:
                print(f"  [Warning] PyAEDT IGBT 热求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 IGBT 热求解，使用估算值")
            else:
                print("  [Note] 未加载实算后端，使用 DryRun 估算")

        power_density = params.get("power_density_igbt", 1.69e9)
        env_temp = params.get("env_temp", 40)
        solder_thickness = params.get("solder_thickness", 80)

        # 简化估算（实际需要FEA求解）
        temp_rise = 89  # 参考值：结温波动约80℃
        max_junction_temp = env_temp + temp_rise
        max_solder_temp = max_junction_temp - 24  # 焊层温度约105℃

        return {
            "max_junction_temp": max_junction_temp,
            "max_solder_temp": max_solder_temp,
            "temp_fluctuation": 65,
            "solder_temp_fluctuation": 65,
            "power_density": power_density,
        }

    def _run_igbt_deformation(self, params: dict) -> dict:
        """
        IGBT 变形分析（热膨胀）
        输入：温度场（结温/焊层温度）+ 焊层厚度
        计算：CTE失配导致的热变形
        """
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_igbt_deformation(params)
            except Exception as e:
                print(f"  [Warning] PyAEDT IGBT 变形求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 IGBT 变形求解，使用估算值")
            else:
                print("  [Note] 未加载实算后端，使用 DryRun 估算")

        temp_field = params.get("temp_field", 125)  # ℃ 结温
        solder_temp = params.get("solder_temp", 105)  # ℃ 焊层温度
        solder_thickness = params.get("solder_thickness", 80)  # μm

        cte_solder = 17.6e-6      # 焊料 CTE
        cte_substrate = 7.5e-6    # 基板 CTE
        env_temp = 40  # ℃

        # 焊层温升驱动 CTE 失配应变（由上游温度场决定，保证数据链连通）
        delta_T = solder_temp - env_temp
        mismatch_strain = (cte_solder - cte_substrate) * delta_T
        displacement = mismatch_strain * solder_thickness  # μm

        return {
            "max_displacement": displacement,
            "displacement_ratio": displacement / solder_thickness if solder_thickness else 0,
            "mismatch_strain": mismatch_strain,
            "cte_mismatch": cte_solder - cte_substrate,
            "delta_T": delta_T,
            "max_location": "R1_R7",
        }

    def _run_igbt_stress(self, params: dict) -> dict:
        """
        IGBT 应力分析（热应力 + 机械应力）
        输入：温度场（结温）+ 变形量 + 焊层厚度
        计算：CTE失配热应力 + 变形引起的机械应力
        """
        if self.fea_backend is not None:
            try:
                return self.fea_backend.run_igbt_stress(params)
            except Exception as e:
                print(f"  [Warning] PyAEDT IGBT 应力求解失败，降级 DryRun 估算: {e}")
        else:
            if self.config.dry_run:
                print("  [DryRun] 跳过实际 IGBT 应力求解，使用估算值")
            else:
                print("  [Note] 未加载实算后端，使用 DryRun 估算")

        temp_field = params.get("temp_field", 125)  # ℃ 结温
        deformation = params.get("deformation", 1.0)  # μm
        solder_thickness = params.get("solder_thickness", 80)  # μm

        # 热应力 σ = E·α·ΔT (焊层 E ≈ 45 GPa)
        E_solder = 45e3  # MPa
        cte_solder = 17.6e-6
        cte_substrate = 7.5e-6
        env_temp = 40  # ℃
        delta_T = temp_field - env_temp
        thermal_stress = E_solder * (cte_solder - cte_substrate) * delta_T  # MPa

        # 变形引起的机械应力
        mech_stress = E_solder * (deformation / solder_thickness) if solder_thickness else 0

        # 总应力（绝对值叠加）
        total_stress = abs(thermal_stress) + abs(mech_stress)

        # 非弹性应变增量 Δε_in ≈ CTE失配 × ΔT（全塑性近似，DryRun估算）
        # 真实值应从 FEA 塑性应变张量提取；此处由上游温升驱动，保证数据链连通
        inelastic_strain = (cte_solder - cte_substrate) * delta_T
        # 非弹性应变能密度 ΔW_avg ≈ 0.5 × σ_solder × Δε_in（DryRun估算）
        inelastic_strain_energy = 0.5 * total_stress * inelastic_strain

        return {
            "max_stress_device": total_stress * 3,  # 器件侧应力集中更高
            "max_stress_solder": total_stress,  # MPa
            "thermal_stress": thermal_stress,  # MPa
            "mech_stress": mech_stress,  # MPa
            "inelastic_strain": inelastic_strain,  # Δε_in
            "inelastic_strain_energy": inelastic_strain_energy,  # ΔW_avg (MPa)
            "max_location": "solder_edge",
        }

    def _run_parametric_sweep(self, params: dict, baseline: dict = None) -> dict:
        """参数化研究"""
        # 基准非弹性应变/能量锚定主流程实际值，保证扫描与主流程量级一致
        base_strain = (baseline or {}).get("inelastic_strain", 0.0008989)
        base_energy = (baseline or {}).get("inelastic_strain_energy", 0.03146)

        results = {"void_ratio_sweep": [], "thickness_sweep": []}

        # 孔洞率扫描：孔洞率升高 → 局部应变集中，寿命下降
        def void_predictor(void_ratio=0):
            strain = base_strain * (1 + void_ratio * 0.5)
            energy = base_energy * (1 + void_ratio * 0.3)
            return FatigueLifePredictor.predict(
                delta_epsilon_in=strain,
                delta_w_avg=energy,
            )

        results["void_ratio_sweep"] = ParametricSweep.sweep_void_ratio(void_predictor)

        # 焊层厚度扫描：偏离80μm → 应力重新分布，寿命变化
        def thickness_predictor(thickness=80):
            if thickness <= 80:
                factor = thickness / 80
            else:
                factor = 80 / thickness * 0.9
            strain = base_strain / factor
            energy = base_energy / factor
            return FatigueLifePredictor.predict(
                delta_epsilon_in=strain,
                delta_w_avg=energy,
            )

        results["thickness_sweep"] = ParametricSweep.sweep_solder_thickness(thickness_predictor)
        results["optimal_thickness"] = ParametricSweep.find_optimal_thickness(
            results["thickness_sweep"], "darveaux"
        )

        return results

    # ============================================================
    # 综合评估
    # ============================================================

    def _assess_motor(self, physics_results: dict, motor_params: dict) -> dict:
        """多学科综合评估"""
        em = physics_results.get("electromagnetic", {})
        struct = physics_results.get("structural", {})
        thermal = physics_results.get("thermal", {})

        assessment = {
            "efficiency": em.get("efficiency", 0),
            "torque": em.get("torque", 0),
            "max_stress": struct.get("max_von_mises_stress", 0),
            "safety_factor": struct.get("safety_factor", 0),
            "max_winding_temp": thermal.get("max_winding_temp", 0),
            "max_magnet_temp": thermal.get("max_magnet_temp", 0),
            "pass_fail": {},
        }

        # 判定标准
        assessment["pass_fail"]["efficiency"] = em.get("efficiency", 0) > 0.85
        assessment["pass_fail"]["stress"] = struct.get("safety_factor", 0) > 1.5
        assessment["pass_fail"]["thermal"] = thermal.get("max_winding_temp", 200) < 150

        all_pass = all(assessment["pass_fail"].values())
        assessment["overall"] = "PASS" if all_pass else "FAIL"

        return assessment

    def _save_to_db(self, table: str, data: dict):
        """保存结果到数据库"""
        if not self.db:
            return
        for key, value in data.items():
            self.db.save(
                table=table,
                project_name=self.config.project_name,
                param_name=key,
                param_value=str(value),
            )

    def close(self):
        """清理资源"""
        if self.db:
            self.db.close()


# ============================================================
# 命令行入口
# ============================================================

def demo_motor_mdao():
    """电机多学科仿真演示"""
    import tempfile
    tmp_dir = os.path.join(tempfile.gettempdir(), "mdao_workspace")
    os.makedirs(tmp_dir, exist_ok=True)

    config = MDAOConfig(
        project_name="demo_motor",
        work_dir=tmp_dir,
        dry_run=True,
        enable_database=True,
        db_path=os.path.join(tmp_dir, "mdao.db"),
    )
    orchestrator = MDAOOrchestrator(config)

    motor_params = {
        "power": 10000,
        "speed": 6000,
        "voltage": 310,
        "poles": 8,
        "slots": 48,
        "outer_dia": 180,
        "length": 120,
        "cooling": "water",
    }

    results = orchestrator.run_motor_mdao(motor_params)
    orchestrator.close()


def demo_igbt_reliability():
    """IGBT 可靠性分析演示"""
    import tempfile
    tmp_dir = os.path.join(tempfile.gettempdir(), "mdao_workspace")
    os.makedirs(tmp_dir, exist_ok=True)

    config = MDAOConfig(
        project_name="demo_igbt",
        work_dir=tmp_dir,
        dry_run=True,
        enable_database=True,
        db_path=os.path.join(tmp_dir, "mdao.db"),
    )
    orchestrator = MDAOOrchestrator(config)

    igbt_params = {
        "cycle_period": 120,
        "power_density_igbt": 1.69e9,
        "power_density_frd": 1.14e9,
        "solder_thickness": 80,
        "void_ratio": 0.0,
        "env_temp": 40,
        "num_cycles": 3,
        "enable_sweep": True,
    }

    results = orchestrator.run_igbt_reliability(igbt_params)
    orchestrator.close()


if __name__ == "__main__":
    import sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    print("=" * 60)
    print("MDAO 多物理场仿真编排器")
    print("=" * 60)

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "motor":
            print("\n--- 电机多学科仿真 ---")
            demo_motor_mdao()
        elif cmd == "igbt":
            print("\n--- IGBT 可靠性分析 ---")
            demo_igbt_reliability()
        elif cmd == "check":
            # 环境自检：探测本机 ANSYS 安装 / PyAEDT / PyFluent 可用性
            try:
                from solver_backends import detect_ansys_env, format_report
                print(format_report(detect_ansys_env()))
            except Exception as e:
                print(f"[check] 环境探测失败: {e}")
        else:
            print(f"\n用法:")
            print("  python mdao_orchestrator.py motor   # 电机多学科仿真")
            print("  python mdao_orchestrator.py igbt    # IGBT可靠性分析")
            print("  python mdao_orchestrator.py check   # ANSYS 环境自检(DryRun/实算切换诊断)")
    else:
        print("\n用法:")
        print("  python mdao_orchestrator.py motor   # 电机多学科仿真")
        print("  python mdao_orchestrator.py igbt    # IGBT可靠性分析")
        print("  python mdao_orchestrator.py check   # ANSYS 环境自检(DryRun/实算切换诊断)")
        print("\n运行演示...")
        print("\n--- 电机多学科仿真 ---")
        demo_motor_mdao()
        print("\n--- IGBT 可靠性分析 ---")
        demo_igbt_reliability()
