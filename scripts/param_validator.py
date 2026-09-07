"""
ANSYS Maxwell 电机参数校验器
包含：参数合法性检查、拓扑组合校验、工程约束验证、尺寸约束公式

使用方法：
    from param_validator import MotorValidator
    validator = MotorValidator(config)
    results = validator.validate_all()
"""

import math
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """校验结果"""
    level: str      # "ERROR" | "WARNING" | "INFO"
    category: str   # 校验类别
    message: str    # 描述信息
    suggestion: str = ""  # 修正建议


class MotorValidator:
    """电机参数校验器"""
    
    # ═══════════════════════════════════════════════════════════════
    #  工程约束常量（来自行业经验）
    # ═══════════════════════════════════════════════════════════════
    
    # 气隙磁密范围 (T)
    BG_MIN = 0.6
    BG_MAX = 0.95
    
    # 齿部磁密限值 (T) - D23_50硅钢
    BT_SAT = 1.7
    # 轭部磁密限值 (T)
    BY_SAT = 1.5
    
    # 电流密度范围 (A/mm²)
    J_MIN = 3.0
    J_MAX = 10.0
    
    # 电负荷限值 (A/m)
    A_MAX_NATURAL = 40000
    A_MAX_FORCED = 60000
    
    # 槽满率限值
    KF_HAND = 0.45
    KF_MACHINE = 0.65
    
    # 气隙长度范围 (mm)
    AIRGAP_MIN = 0.15
    AIRGAP_MAX = 2.0
    
    # 磁钢厚度范围 (mm)
    PM_THICK_MIN = 1.0
    PM_THICK_MAX = 10.0
    
    # 极弧系数范围
    POLE_ARC_MIN = 0.6
    POLE_ARC_MAX = 0.95
    
    # V型夹角范围 (deg)
    V_ANGLE_MIN = 80
    V_ANGLE_MAX = 150
    
    # 分裂比范围 (Dsi/Dso)
    SPLIT_RATIO_MIN = 0.45
    SPLIT_RATIO_MAX = 0.75
    
    # ═══════════════════════════════════════════════════════════════
    #  尺寸约束公式（来自指导书）
    # ═══════════════════════════════════════════════════════════════
    
    @staticmethod
    def calc_airgap(stator_id, rotor_od):
        """计算气隙长度"""
        return (stator_id - rotor_od) / 2.0
    
    @staticmethod
    def calc_pole_pitch(stator_id, pole_pairs):
        """计算极距 (mm)"""
        return math.pi * stator_id / (2 * pole_pairs)
    
    @staticmethod
    def calc_slot_pitch(stator_id, slots):
        """计算槽距 (mm)"""
        return math.pi * stator_id / slots
    
    @staticmethod
    def calc_tooth_width(stator_id, slots, bt_target=1.5):
        """计算齿宽 (mm) - 基于磁密目标"""
        tau_s = math.pi * stator_id / slots
        # 齿宽约等于槽距的一半（等磁通面积原则）
        return tau_s * 0.45
    
    @staticmethod
    def calc_yoke_thickness(stator_od, stator_id, pole_pairs, by_target=1.3):
        """计算轭部厚度 (mm) - 基于磁密目标"""
        tau_p = math.pi * stator_id / (2 * pole_pairs)
        # 轭部厚度 = 极距 * Bg / (2 * By)
        # 简化公式：约等于极距的0.3~0.4倍
        return tau_p * 0.35
    
    @staticmethod
    def calc_slot_area(stator_id, stator_od, slots):
        """估算槽面积 (mm²)"""
        # 槽深 ≈ (外径-内径)/2 - 轭部厚度
        slot_depth = (stator_od - stator_id) / 2.0 * 0.6
        slot_width = math.pi * stator_id / slots * 0.5
        return slot_depth * slot_width
    
    @staticmethod
    def calc_slot_fill_factor(conductors_per_slot, wire_area, slot_area, num_strands=1):
        """计算槽满率"""
        total_wire_area = conductors_per_slot * wire_area * num_strands
        return total_wire_area / slot_area if slot_area > 0 else 0
    
    @staticmethod
    def calc_current_density(current_rms, wire_area):
        """计算电流密度 (A/mm²)"""
        return current_rms / wire_area if wire_area > 0 else 0
    
    @staticmethod
    def calc_electric_loading(current_rms, turns_per_phase, phases, stator_id):
        """计算电负荷 (A/m)"""
        # A = m * Nph * I / (pi * Dsi)
        return phases * turns_per_phase * current_rms / (math.pi * stator_id)
    
    @staticmethod
    def calc_pm_thickness_min(airgap, bg_target=0.8, br=1.17):
        """计算最小磁钢厚度 (mm)"""
        # hm ≥ 3 * δ (经验值)
        # 更精确：hm = (Bg * δ * μ0) / (Br * μr * Kf)
        return 3.0 * airgap
    
    @staticmethod
    def calc_torque(power_kw, speed_rpm):
        """计算额定转矩 (N·m)"""
        return power_kw * 1000 / (speed_rpm * 2 * math.pi / 60)
    
    def __init__(self, config):
        """
        初始化校验器
        config: MotorConfig对象
        """
        self.config = config
        self.results: List[ValidationResult] = []
    
    def validate_all(self) -> List[ValidationResult]:
        """执行全部校验"""
        self.results = []
        
        self._validate_geometry()
        self._validate_slot_params()
        self._validate_pm_params()
        self._validate_winding()
        self._validate_electrical()
        self._validate_topology_combination()
        self._validate_materials()
        self._validate_simulation()
        self._validate_design_rules()
        
        return self.results
    
    def _add(self, level, category, message, suggestion=""):
        self.results.append(ValidationResult(level, category, message, suggestion))
    
    # ═══════════════════════════════════════════════════════════════
    #  几何尺寸校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_geometry(self):
        """校验基础几何尺寸"""
        c = self.config
        
        # 定子外径 > 内径
        if c.stator_od <= c.stator_id:
            self._add("ERROR", "几何", "定子外径必须大于内径",
                      f"Dso={c.stator_od}, Dsi={c.stator_id}")
        
        # 转子外径 < 定子内径
        if c.rotor_od >= c.stator_id:
            self._add("ERROR", "几何", "转子外径必须小于定子内径",
                      f"Dro={c.rotor_od}, Dsi={c.stator_id}")
        
        # 轴径 < 转子内径
        if c.rotor_id >= c.rotor_od:
            self._add("ERROR", "几何", "轴径必须小于转子外径",
                      f"轴径={c.rotor_id}, Dro={c.rotor_od}")
        
        # 气隙一致性
        airgap_calc = self.calc_airgap(c.stator_id, c.rotor_od)
        if abs(airgap_calc - c.airgap) > 0.01:
            self._add("WARNING", "几何",
                      f"气隙={c.airgap}mm 与几何计算值={airgap_calc:.3f}mm 不一致",
                      "调整stator_id或rotor_od使气隙一致")
        
        # 气隙范围
        if c.airgap < self.AIRGAP_MIN:
            self._add("WARNING", "几何", f"气隙={c.airgap}mm过小，可能引起机械干涉",
                      f"建议>={self.AIRGAP_MIN}mm")
        if c.airgap > self.AIRGAP_MAX:
            self._add("WARNING", "几何", f"气隙={c.airgap}mm过大，降低功率密度",
                      f"建议<={self.AIRGAP_MAX}mm")
        
        # 分裂比
        split_ratio = c.stator_id / c.stator_od
        if split_ratio < self.SPLIT_RATIO_MIN or split_ratio > self.SPLIT_RATIO_MAX:
            self._add("WARNING", "几何",
                      f"分裂比={split_ratio:.2f}不在推荐范围{self.SPLIT_RATIO_MIN}~{self.SPLIT_RATIO_MAX}",
                      "PM电机典型分裂比0.55~0.65")
        
        # 叠片长度
        if c.stack_length <= 0:
            self._add("ERROR", "几何", "叠片长度必须>0")
        
        # 径向尺寸链检查
        total_radial = c.airgap + c.pm_thickness + (c.stator_id - c.rotor_od) / 2.0
        if abs(total_radial - (c.stator_id - c.rotor_od) / 2.0) > 0.1:
            self._add("WARNING", "几何", "径向尺寸链不闭合",
                      "检查airgap + pm_thickness是否等于(stator_id - rotor_od)/2")
    
    # ═══════════════════════════════════════════════════════════════
    #  槽型参数校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_slot_params(self):
        """校验槽型参数"""
        c = self.config
        
        if c.slot_type.value == "rectangular":
            # 矩形槽：Bs0 ≈ Bs2
            if abs(c.slot_Bs0 - c.slot_Bs2) / c.slot_Bs2 > 0.15:
                self._add("WARNING", "槽型", "矩形槽Bs0应约等于Bs2",
                          f"Bs0={c.slot_Bs0}, Bs2={c.slot_Bs2}")
            if c.slot_Hs2 <= c.slot_Hs0:
                self._add("ERROR", "槽型", "槽深必须大于槽口高度")
        
        elif c.slot_type.value == "pear":
            # 梨形槽：Bs0 < Bs1 < Bs2
            if not (c.slot_Bs0 < c.slot_Bs1 < c.slot_Bs2):
                self._add("ERROR", "槽型", "梨形槽宽度应递增：Bs0<Bs1<Bs2",
                          f"Bs0={c.slot_Bs0}, Bs1={c.slot_Bs1}, Bs2={c.slot_Bs2}")
            if c.slot_Rs <= 0:
                self._add("ERROR", "槽型", "梨形槽需要正的圆角Rs")
            if c.slot_Rs > c.slot_Bs2 / 2:
                self._add("WARNING", "槽型", "圆角半径过大",
                          f"Rs={c.slot_Rs}, Bs2/2={c.slot_Bs2/2}")
        
        elif c.slot_type.value == "trapezoidal":
            # 梯形槽：Bs0 < Bs1
            if c.slot_Bs0 >= c.slot_Bs1:
                self._add("ERROR", "槽型", "梯形槽Bs0应<Bs1",
                          f"Bs0={c.slot_Bs0}, Bs1={c.slot_Bs1}")
        
        # 通用槽型约束
        if c.slot_Hs0 <= 0:
            self._add("ERROR", "槽型", "槽口高度Hs0必须>0")
        if c.slot_Hs2 <= c.slot_Hs1:
            self._add("ERROR", "槽型", "槽深Hs2应大于槽楔高度Hs1")
        
        # 槽口宽度与气隙关系
        if c.slot_Bs0 > 5 * c.airgap:
            self._add("WARNING", "槽型", "槽口过宽，增加齿槽转矩",
                      f"推荐bs0<=5*d={5*c.airgap}mm")
        
        # 槽距检查
        tau_s = self.calc_slot_pitch(c.stator_id, c.slots)
        if c.slot_Bs2 > tau_s * 0.7:
            self._add("WARNING", "槽型", "槽宽过大，齿部过窄",
                      f"Bs2={c.slot_Bs2}, tau_s={tau_s:.2f}")
    
    # ═══════════════════════════════════════════════════════════════
    #  永磁体参数校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_pm_params(self):
        """校验永磁体参数"""
        c = self.config
        
        # 磁钢厚度范围
        if c.pm_thickness < self.PM_THICK_MIN:
            self._add("WARNING", "磁钢", f"磁钢厚度={c.pm_thickness}mm过小",
                      f"建议>={self.PM_THICK_MIN}mm")
        if c.pm_thickness > self.PM_THICK_MAX:
            self._add("WARNING", "磁钢", f"磁钢厚度={c.pm_thickness}mm过大",
                      f"建议<={self.PM_THICK_MAX}mm")
        
        # SPM特殊约束
        if c.pm_topology.value == "SPM":
            min_thickness = self.calc_pm_thickness_min(c.airgap)
            if c.pm_thickness < min_thickness:
                self._add("WARNING", "磁钢", 
                          f"SPM磁钢厚度={c.pm_thickness}mm应>=3倍气隙={min_thickness:.1f}mm",
                          "增加磁钢厚度或减小气隙")
        
        # IPM_V特殊约束
        if c.pm_topology.value == "IPM_V":
            if c.pm_v_angle < self.V_ANGLE_MIN or c.pm_v_angle > self.V_ANGLE_MAX:
                self._add("WARNING", "磁钢", f"V型夹角={c.pm_v_angle}度不在推荐范围",
                          f"建议{self.V_ANGLE_MIN}~{self.V_ANGLE_MAX}度")
            if c.pm_bridge <= 0:
                self._add("ERROR", "磁钢", "IPM需要正的隔磁桥厚度")
            if c.pm_bridge > 2.0:
                self._add("WARNING", "磁钢", "隔磁桥过厚，漏磁增加",
                          f"pm_bridge={c.pm_bridge}mm，建议<1.5mm")
        
        # 极弧系数
        if c.pm_pole_arc < self.POLE_ARC_MIN or c.pm_pole_arc > self.POLE_ARC_MAX:
            self._add("WARNING", "磁钢", f"极弧系数={c.pm_pole_arc}不在推荐范围",
                      f"建议{self.POLE_ARC_MIN}~{self.POLE_ARC_MAX}")
        
        # 磁钢宽度检查（IPM）
        if c.pm_topology.value in ["IPM_Flat", "IPM_V"]:
            tau_p = self.calc_pole_pitch(c.stator_id, c.pole_pairs)
            if c.pm_width > tau_p * 0.8:
                self._add("WARNING", "磁钢", "磁钢宽度过大",
                          f"pm_width={c.pm_width}, tau_p={tau_p:.2f}")
    
    # ═══════════════════════════════════════════════════════════════
    #  绕组参数校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_winding(self):
        """校验绕组参数"""
        c = self.config
        
        # 槽满率
        if c.slot_fill_factor > self.KF_MACHINE:
            self._add("WARNING", "绕组", f"槽满率={c.slot_fill_factor:.0%}过高",
                      f"机绕极限{self.KF_MACHINE:.0%}")
        
        # 每槽导体数检查
        if c.conductors_per_slot <= 0:
            self._add("ERROR", "绕组", "每槽导体数必须>0")
        
        # 线圈节距检查
        if c.coil_pitch < 1 or c.coil_pitch > c.slots:
            self._add("ERROR", "绕组", f"线圈节距={c.coil_pitch}不合理",
                      f"应在1~{c.slots}之间")
    
    # ═══════════════════════════════════════════════════════════════
    #  电气参数校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_electrical(self):
        """校验电气参数"""
        c = self.config
        
        # 电频率与转速关系
        freq_calc = c.pole_pairs * c.rated_speed_rpm / 60.0
        if abs(freq_calc - c.frequency_hz) > 1.0:
            self._add("WARNING", "电气",
                      f"电频率={c.frequency_hz}Hz与计算值={freq_calc:.1f}Hz不一致",
                      "f = p * n / 60")
    
    # ═══════════════════════════════════════════════════════════════
    #  拓扑组合校验
    # ═══════════════════════════════════════════════════════════════
    
    def _validate_topology_combination(self):
        """校验槽型-极数-磁钢拓扑组合"""
        c = self.config
        
        # 矩形槽不适合高极数
        if c.slot_type.value == "rectangular" and c.poles > 8:
            self._add("WARNING", "拓扑", "矩形槽高极数时齿部过窄",
                      "考虑使用梨形槽或梯形槽")
        
        # V型IPM至少12槽
        if c.pm_topology.value == "IPM_V" and c.slots < 12:
            self._add("ERROR", "拓扑", "V型IPM至少需要12槽")
        
        # 极槽配合
        lcm_val = self._lcm(c.slots, c.poles)
        if lcm_val < 12:
            self._add("WARNING", "拓扑",
                      f"LCM(槽,极)={lcm_val}过小，齿槽转矩可能较大",
                      "建议LCM>=24")
        
        # 感应电机检查
        if c.motor_type.value == "IM":
            if c.pm_topology.value != "SPM":
                self._add("WARNING", "拓扑", "感应电机通常不使用永磁体",
                          "考虑移除永磁体或改用PMSM")
    
    def _validate_materials(self):
        """校验材料选择"""
        pass  # 材料校验在分配时进行
    
    def _validate_simulation(self):
        """校验仿真参数"""
        c = self.config
        
        # 时间步与频率关系
        min_step = 1.0 / (c.frequency_hz * 200)  # 至少200步/周期
        if c.sim_time_step > min_step:
            self._add("WARNING", "仿真", f"时间步={c.sim_time_step}s可能过大",
                      f"建议<={min_step:.2e}s（200步/周期）")
    
    def _validate_design_rules(self):
        """校验设计规则"""
        c = self.config
        
        # 计算关键设计参数
        tau_p = self.calc_pole_pitch(c.stator_id, c.pole_pairs)
        tau_s = self.calc_slot_pitch(c.stator_id, c.slots)
        
        # 极距与槽距比例
        ratio = tau_p / tau_s if tau_s > 0 else 0
        if ratio < 0.8 or ratio > 1.2:
            self._add("INFO", "设计规则",
                      f"极距/槽距={ratio:.2f}，建议在0.8~1.2之间")
        
        # 轭部厚度检查
        hy_calc = self.calc_yoke_thickness(c.stator_od, c.stator_id, c.pole_pairs)
        hy_actual = (c.stator_od - c.stator_id) / 2.0 - c.slot_Hs0 - c.slot_Hs1 - c.slot_Hs2
        if hy_actual < 0:
            self._add("ERROR", "设计规则", "槽深过大，超出定子径向空间",
                      f"槽深={c.slot_Hs0+c.slot_Hs1+c.slot_Hs2}, 径向空间={(c.stator_od-c.stator_id)/2:.1f}")
        elif hy_actual < hy_calc * 0.5:
            self._add("WARNING", "设计规则", "轭部过薄，可能饱和",
                      f"实际轭部厚度={hy_calc:.1f}mm")
    
    @staticmethod
    def _lcm(a, b):
        return abs(a * b) // math.gcd(a, b)
    
    def get_summary(self) -> str:
        """获取校验结果摘要"""
        errors = [r for r in self.results if r.level == "ERROR"]
        warnings = [r for r in self.results if r.level == "WARNING"]
        
        lines = [f"校验完成: {len(errors)}个错误, {len(warnings)}个警告"]
        
        if errors:
            lines.append("\n[ERROR] 错误:")
            for r in errors:
                lines.append(f"  [{r.category}] {r.message}")
                if r.suggestion:
                    lines.append(f"    -> {r.suggestion}")
        
        if warnings:
            lines.append("\n[WARNING] 警告:")
            for r in warnings:
                lines.append(f"  [{r.category}] {r.message}")
                if r.suggestion:
                    lines.append(f"    -> {r.suggestion}")
        
        if not errors and not warnings:
            lines.append("\n[OK] 全部参数校验通过")
        
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  独立校验函数（可直接调用）
# ═══════════════════════════════════════════════════════════════

def validate_slot_type(slot_type: str) -> bool:
    """验证槽型名称"""
    valid = ["rectangular", "pear", "trapezoidal", "round"]
    return slot_type in valid


def validate_pm_topology(pm_topology: str) -> bool:
    """验证永磁拓扑名称"""
    valid = ["SPM", "IPM_Flat", "IPM_V", "IPM_Spoke"]
    return pm_topology in valid


def check_design_rules(stator_od, stator_id, rotor_od, airgap, slots, poles):
    """快速设计规则检查"""
    issues = []
    
    split_ratio = stator_id / stator_od
    if split_ratio < 0.45 or split_ratio > 0.75:
        issues.append(f"分裂比{split_ratio:.2f}不在合理范围0.45~0.75")
    
    airgap_calc = (stator_id - rotor_od) / 2.0
    if abs(airgap_calc - airgap) > 0.01:
        issues.append(f"气隙不一致: 设定{airgap}mm, 几何{airgap_calc:.3f}mm")
    
    lcm_val = (slots * poles) // math.gcd(slots, poles)
    if lcm_val < 12:
        issues.append(f"LCM(槽,极)={lcm_val}过小")
    
    return issues


if __name__ == "__main__":
    # 测试校验器
    from motor_config import MotorConfig, SlotType, PMTopology
    
    cfg = MotorConfig(
        slot_type=SlotType.PEAR,
        pm_topology=PMTopology.SPM,
        stator_od=210, stator_id=136,
        rotor_od=135.6, airgap=0.2,
        slots=36, pole_pairs=2,
    )
    
    validator = MotorValidator(cfg)
    results = validator.validate_all()
    print(validator.get_summary())
