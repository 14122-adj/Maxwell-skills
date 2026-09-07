"""
ANSYS Maxwell 电机自动化建模 - 中心配置文件
支持多槽型/多永磁拓扑切换

使用方法：
    from motor_config import MotorConfig
    cfg = MotorConfig(slot_type="pear", pm_topology="SPM", ...)
"""

import math
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════
#  枚举类型定义
# ═══════════════════════════════════════════════════════════════

class SlotType(Enum):
    """槽型类型"""
    RECTANGULAR = "rectangular"    # 矩形槽
    PEAR = "pear"                  # 梨形槽（上窄下宽+圆角）
    TRAPEZOIDAL = "trapezoidal"    # 梯形槽
    ROUND = "round"                # 圆形槽


class PMTopology(Enum):
    """永磁体拓扑类型"""
    SPM = "SPM"                    # 表贴式
    IPM_FLAT = "IPM_Flat"          # 内置一字型
    IPM_V = "IPM_V"                # 内置V型
    IPM_SPOKE = "IPM_Spoke"        # 内置磁阻型


class MotorType(Enum):
    """电机类型"""
    PMSM = "PMSM"                  # 永磁同步电机
    BLDC = "BLDC"                  # 无刷直流电机
    SRM = "SRM"                    # 开关磁阻电机
    IM = "IM"                      # 感应电机


# ═══════════════════════════════════════════════════════════════
#  默认参数库
# ═══════════════════════════════════════════════════════════════

# 槽型参数默认值
DEFAULT_SLOT_PARAMS = {
    SlotType.RECTANGULAR: {
        "Hs0": 0.8, "Hs2": 12.0,
        "Bs0": 3.0, "Bs2": 8.0,
    },
    SlotType.PEAR: {
        "Hs0": 0.8, "Hs1": 1.5, "Hs2": 11.5,
        "Bs0": 3.5, "Bs1": 6.2, "Bs2": 8.3, "Rs": 4.15,
    },
    SlotType.TRAPEZOIDAL: {
        "Hs0": 0.8, "Hs1": 2.0, "Hs2": 12.0,
        "Bs0": 3.0, "Bs1": 7.0,
    },
    SlotType.ROUND: {
        "diameter": 6.0, "depth": 12.0,
    },
}

# 永磁体参数默认值
DEFAULT_PM_PARAMS = {
    PMTopology.SPM: {
        "pm_thickness": 3.0, "pm_pole_arc": 0.85, "pm_gap": 0.5,
    },
    PMTopology.IPM_FLAT: {
        "pm_thickness": 2.5, "pm_width": 15.0,
        "pm_offset_r": 5.0, "pm_bridge": 1.0,
    },
    PMTopology.IPM_V: {
        "pm_thickness": 2.5, "pm_width": 12.0,
        "v_angle": 120.0, "v_center_offset": 3.0, "pm_bridge": 0.8,
    },
}

# 材料默认值
DEFAULT_MATERIALS = {
    "stator_core": "M270_35A",
    "rotor_core": "M270_35A",
    "pm": "N38UH_20C",
    "conductor": "copper",
    "shaft": "steel_stainless",
    "airgap": "vacuum",
}


# ═══════════════════════════════════════════════════════════════
#  电机配置类
# ═══════════════════════════════════════════════════════════════

@dataclass
class MotorConfig:
    """电机设计完整配置"""
    
    # --- 基本规格 ---
    motor_type: MotorType = MotorType.PMSM
    rated_power_kw: float = 0.5           # 额定功率 (kW)
    rated_speed_rpm: float = 3000.0       # 额定转速 (rpm)
    dc_bus_voltage_v: float = 48.0        # 母线电压 (V)
    phases: int = 3                       # 相数
    
    # --- 拓扑选择 ---
    slot_type: SlotType = SlotType.PEAR
    pm_topology: PMTopology = PMTopology.SPM
    pole_pairs: int = 4                   # 极对数
    slots: int = 12                       # 槽数
    
    # --- 几何尺寸 (mm) ---
    stator_od: float = 210.0              # 定子外径
    stator_id: float = 136.0              # 定子内径（气隙面）
    rotor_od: float = 135.6               # 转子外径
    rotor_id: float = 48.0                # 转子内径（轴径）
    airgap: float = 0.2                   # 气隙长度
    stack_length: float = 143.0           # 叠片长度（轴向）
    
    # --- 槽型参数 (mm) ---
    slot_Hs0: float = 0.8                 # 槽口高度
    slot_Hs1: float = 1.5                 # 槽楔高度
    slot_Hs2: float = 11.5                # 槽深
    slot_Bs0: float = 3.5                 # 槽口宽度
    slot_Bs1: float = 6.2                 # 槽宽上部
    slot_Bs2: float = 8.3                 # 槽宽下部
    slot_Rs: float = 4.15                 # 槽底圆角
    
    # --- 永磁体参数 (mm) ---
    pm_thickness: float = 3.0             # 磁钢厚度
    pm_pole_arc: float = 0.85             # 极弧系数
    pm_width: float = 15.0                # 磁钢宽度（IPM用）
    pm_offset_r: float = 5.0              # 径向偏移（IPM用）
    pm_v_angle: float = 120.0             # V型夹角（IPM_V用）
    pm_bridge: float = 1.0                # 隔磁桥厚度（IPM用）
    
    # --- 绕组参数 ---
    turns_per_phase: int = 81             # 每相匝数
    conductors_per_slot: int = 35         # 每槽导体数
    wire_diameter_mm: float = 0.95        # 线径
    num_strands: int = 4                  # 并绕根数
    coil_pitch: int = 7                   # 线圈节距
    slot_fill_factor: float = 0.40        # 槽满率
    parallel_branches: int = 1            # 并联支路数
    
    # --- 电气参数 ---
    rated_current_rms: float = 10.0       # 额定电流RMS (A)
    frequency_hz: float = 100.0           # 电频率 (Hz)
    phase_resistance: float = 0.957       # 相电阻 (Ω)
    phase_inductance: float = 0.0038      # 相电感 (H)
    
    # --- 材料 ---
    stator_material: str = "M270_35A"
    rotor_material: str = "M270_35A"
    pm_material: str = "N38UH_20C"
    pm_material_n: str = "NdFe35_N"           # N极磁钢材料（磁化方向：径向向外）
    pm_material_s: str = "NdFe35_S"           # S极磁钢材料（磁化方向：径向向内）
    pm_br_20c: float = 1.37                   # 剩磁Br@20°C (T)
    pm_hc_kam: float = 890                    # 矫顽力Hc (kA/m)
    pm_mur: float = 1.05                      # 相对磁导率
    pm_conductivity: float = 625000            # 电导率 (S/m)
    pm_mass_density: float = 7400              # 质量密度 (kg/m³)
    conductor_material: str = "copper"
    shaft_material: str = "steel_stainless"
    
    # --- 自定义数据输入 ---
    custom_params: dict = field(default_factory=dict)  # 自定义参数字典
    
    # --- 仿真参数 ---
    sim_stop_time: float = 0.02           # 停止时间 (s)
    sim_time_step: float = 5e-5           # 时间步长 (s)
    fractions: int = 4                    # 周期分数
    
    # --- 网格参数 (mm) ---
    mesh_airgap: float = 0.2              # 气隙网格尺寸
    mesh_teeth: float = 1.5               # 齿部网格尺寸
    mesh_pm: float = 0.5                  # 磁钢网格尺寸
    mesh_yoke: float = 3.0                # 轭部网格尺寸
    
    def __post_init__(self):
        """初始化后自动计算派生参数"""
        self.poles = self.pole_pairs * 2
        self.rated_frequency_hz = self.pole_pairs * self.rated_speed_rpm / 60.0
        self.tau_pole = math.pi * self.stator_id / self.poles  # 极距
        self.tau_slot = math.pi * self.stator_id / self.slots  # 槽距
        self.band_radius = (self.rotor_od + self.stator_id) / 2.0
    
    def validate(self) -> list:
        """验证参数合理性，返回警告/错误列表"""
        issues = []
        
        # 基本尺寸检查
        if self.stator_od <= self.stator_id:
            issues.append("ERROR: 定子外径必须大于内径")
        if self.rotor_od >= self.stator_id:
            issues.append("ERROR: 转子外径必须小于定子内径")
        
        # 气隙检查
        airgap_actual = (self.stator_id - self.rotor_od) / 2.0
        if abs(airgap_actual - self.airgap) > 0.01:
            issues.append(f"WARNING: 气隙={self.airgap}mm, 但Dsi-Dro计算值={airgap_actual:.3f}mm")
        
        # 槽型参数检查
        if self.slot_type == SlotType.PEAR:
            if not (self.slot_Bs0 < self.slot_Bs1 < self.slot_Bs2):
                issues.append("WARNING: 梨形槽Bs0应<Bs1<Bs2")
            if self.slot_Rs <= 0:
                issues.append("ERROR: 梨形槽需要正的圆角Rs")
        
        # 永磁体检查
        if self.pm_topology == PMTopology.SPM:
            if self.pm_thickness < 3 * self.airgap:
                issues.append("WARNING: SPM磁钢厚度应≥3倍气隙")
        
        if self.pm_topology == PMTopology.IPM_V:
            if self.pm_v_angle > 150 or self.pm_v_angle < 80:
                issues.append("WARNING: V型夹角建议在80°~150°之间")
        
        # 绕组检查
        if self.slot_fill_factor > 0.65:
            issues.append("WARNING: 槽满率>0.65可能无法嵌线")
        
        # 极槽配合检查
        lcm_val = self._lcm(self.slots, self.poles)
        if lcm_val < 12:
            issues.append(f"WARNING: LCM(槽,极)={lcm_val}过小，齿槽转矩可能较大")
        
        return issues
    
    @staticmethod
    def _gcd(a, b):
        """最大公约数"""
        while b:
            a, b = b, a % b
        return a

    @staticmethod
    def _lcm(a, b):
        """最小公倍数"""
        return abs(a * b) // MotorConfig._gcd(a, b)
    
    def get_slot_angle(self) -> float:
        """获取单槽角度 (deg)"""
        return 360.0 / self.slots
    
    def get_pole_pitch_angle(self) -> float:
        """获取极距角度 (deg)"""
        return 360.0 / self.poles
    
    def get_pm_arc_angle(self) -> float:
        """获取磁钢弧度角 (deg)"""
        return self.pm_pole_arc * self.get_pole_pitch_angle()
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {k: v.value if isinstance(v, (SlotType, PMTopology, MotorType)) else v
                for k, v in self.__dict__.items()}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MotorConfig':
        """
        从字典创建配置（支持自定义数据输入）
        
        Args:
            data: 参数字典，键名与MotorConfig字段名一致
        
        Returns:
            MotorConfig实例
        """
        # 处理枚举类型转换
        if 'slot_type' in data and isinstance(data['slot_type'], str):
            data['slot_type'] = SlotType(data['slot_type'])
        if 'pm_topology' in data and isinstance(data['pm_topology'], str):
            data['pm_topology'] = PMTopology(data['pm_topology'])
        if 'motor_type' in data and isinstance(data['motor_type'], str):
            data['motor_type'] = MotorType(data['motor_type'])
        
        # 处理别名：poles -> pole_pairs
        if 'poles' in data and 'pole_pairs' not in data:
            data['pole_pairs'] = data.pop('poles') // 2
        
        # 过滤掉不在MotorConfig中的键
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        return cls(**filtered_data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MotorConfig':
        """
        从JSON字符串创建配置
        
        Args:
            json_str: JSON格式的参数字符串
        
        Returns:
            MotorConfig实例
        """
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_csv(cls, csv_content: str) -> 'MotorConfig':
        """
        从CSV内容创建配置
        
        CSV格式：参数名,参数值
        例如：
            slots,36
            poles,8
            stator_od,210
        
        Args:
            csv_content: CSV格式的参数内容
        
        Returns:
            MotorConfig实例
        """
        data = {}
        for line in csv_content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) >= 2:
                key = parts[0].strip()
                value = parts[1].strip()
                # 尝试转换为数字
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                data[key] = value
        
        return cls.from_dict(data)
    
    def update(self, **kwargs):
        """
        更新配置参数
        
        Args:
            **kwargs: 要更新的参数
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.custom_params[key] = value
        
        # 重新计算派生参数
        self.__post_init__()


# ═══════════════════════════════════════════════════════════════
#  快捷创建函数
# ═══════════════════════════════════════════════════════════════

def create_8p12s_spm_servo():
    """8极12槽表贴式伺服电机"""
    return MotorConfig(
        motor_type=MotorType.PMSM,
        rated_power_kw=0.5,
        rated_speed_rpm=3000,
        dc_bus_voltage_v=48,
        slot_type=SlotType.RECTANGULAR,
        pm_topology=PMTopology.SPM,
        pole_pairs=4,
        slots=12,
        stator_od=80,
        stator_id=52,
        rotor_od=50.8,
        rotor_id=20,
        airgap=0.6,
        stack_length=50,
        pm_thickness=4.0,
        pm_pole_arc=0.87,
    )


def create_36slot_industrial():
    """36槽工业电机（仿书本案例）"""
    return MotorConfig(
        motor_type=MotorType.PMSM,
        rated_power_kw=7.5,
        rated_speed_rpm=1500,
        dc_bus_voltage_v=380,
        slot_type=SlotType.PEAR,
        pm_topology=PMTopology.SPM,
        pole_pairs=2,
        slots=36,
        stator_od=210,
        stator_id=136,
        rotor_od=135.6,
        rotor_id=48,
        airgap=0.2,
        stack_length=143,
        slot_Hs0=0.8, slot_Hs1=1.5, slot_Hs2=11.5,
        slot_Bs0=3.5, slot_Bs1=6.2, slot_Bs2=8.3, slot_Rs=4.15,
        pm_thickness=3.0,
        pm_pole_arc=0.85,
    )


def create_8p12s_ipm_ev():
    """8极12槽内置V型EV驱动电机"""
    return MotorConfig(
        motor_type=MotorType.PMSM,
        rated_power_kw=50,
        rated_speed_rpm=3000,
        dc_bus_voltage_v=350,
        slot_type=SlotType.TRAPEZOIDAL,
        pm_topology=PMTopology.IPM_V,
        pole_pairs=4,
        slots=12,
        stator_od=200,
        stator_id=120,
        rotor_od=118.4,
        rotor_id=40,
        airgap=0.8,
        stack_length=150,
        pm_thickness=2.5,
    pm_v_angle=120,
    pm_bridge=0.8,
)


def create_8p36s_tutorial():
    """8极36槽PMSM（匹配教程模式）"""
    return MotorConfig(
        motor_type=MotorType.PMSM,
        rated_power_kw=2.2,
        rated_speed_rpm=2000,
        dc_bus_voltage_v=310,
        slot_type=SlotType.PEAR,
        pm_topology=PMTopology.SPM,
        pole_pairs=4,
        slots=36,
        stator_od=210.0,
        stator_id=136.0,
        rotor_od=135.2,
        rotor_id=48.0,
        airgap=0.4,
        stack_length=100.0,
        slot_Hs0=0.8, slot_Hs1=1.5, slot_Hs2=11.5,
        slot_Bs0=3.5, slot_Bs1=6.2, slot_Bs2=8.3, slot_Rs=4.15,
        pm_thickness=3.0,
        pm_pole_arc=0.85,
        conductors_per_slot=45,
        slot_fill_factor=0.45,
        pm_material_n="NdFe35_N",
        pm_material_s="NdFe35_S",
        pm_br_20c=1.37,
        pm_hc_kam=890,
        pm_conductivity=625000,
        pm_mass_density=7400,
    )


def create_8p12s_pmsm_from_params(**params):
    """从参数字典创建8极12槽PMSM配置"""
    defaults = dict(
        motor_type=MotorType.PMSM,
        rated_power_kw=0.5,
        rated_speed_rpm=3000,
        dc_bus_voltage_v=48,
        slot_type=SlotType.RECTANGULAR,
        pm_topology=PMTopology.SPM,
        pole_pairs=4,
        slots=12,
        stator_od=80,
        stator_id=52,
        rotor_od=50.8,
        rotor_id=20,
        airgap=0.6,
        stack_length=50,
        pm_thickness=4.0,
        pm_pole_arc=0.87,
    )
    defaults.update(params)
    return MotorConfig(**defaults)


def create_motor_from_input(input_str: str, input_type: str = "auto"):
    """
    从用户输入创建电机配置 - 自定义数据入口
    
    Args:
        input_str: 输入字符串（JSON、CSV或关键词）
        input_type: 输入类型（json/csv/keyword/auto）
    
    Returns:
        MotorConfig实例
    """
    import json
    
    if input_type == "auto":
        if input_str.lstrip().startswith('{'):
            input_type = "json"
        elif ',' in input_str and ':' not in input_str:
            input_type = "csv"
        else:
            input_type = "keyword"
    
    if input_type == "json":
        data = json.loads(input_str)
        return MotorConfig.from_dict(data)
    
    elif input_type == "csv":
        return MotorConfig.from_csv(input_str)
    
    elif input_type == "keyword":
        data = {}
        # 处理关键词格式: "slots=36 poles=8 stator_od=210"
        for pair in input_str.replace(',', ' ').split():
            if '=' in pair:
                key, value = pair.split('=', 1)
                key = key.strip().lstrip('-')
                value = value.strip()
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        else:
                            # 尝试枚举
                            enum_map = {
                                'slot_type': SlotType, 'pm_topology': PMTopology, 'motor_type': MotorType,
                            }
                            if key in enum_map:
                                for e in enum_map[key]:
                                    if e.value == value:
                                        value = e
                                        break
                data[key] = value
        return MotorConfig.from_dict(data)
    
    else:
        raise ValueError(f"不支持的输入类型: {input_type}")


if __name__ == "__main__":
    # 测试配置创建
    cfg = create_36slot_industrial()
    issues = cfg.validate()
    
    print("=" * 50)
    print("电机配置参数：")
    print("=" * 50)
    for k, v in cfg.to_dict().items():
        if not k.startswith('_'):
            print(f"  {k}: {v}")
    
    print("\n参数校验结果:")
    if issues:
        for issue in issues:
            print(f"  [{issue.split(':')[0]}] {issue.split(':')[1]}")
    else:
        print("  全部通过")
