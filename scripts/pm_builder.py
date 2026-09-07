"""
ANSYS Maxwell 永磁体几何生成器
支持：表贴式SPM、内置一字型IPM_Flat、内置V型IPM_V

使用方法：
    from pm_builder import PMBuilder
    builder = PMBuilder(config)
    builder.build_single_pm()
    builder.duplicate_pms()
"""

import math
from typing import List


class PMBuilder:
    """永磁体几何生成器"""
    
    def __init__(self, config):
        """
        初始化
        config: MotorConfig对象
        """
        self.config = config
        self.pm_names: List[str] = []
    
    def build_single_pm(self, pm_index: int = 1) -> str:
        """
        根据拓扑类型生成单极磁钢的几何
        
        参数:
            pm_index: 磁钢编号（用于命名）
        
        返回:
            生成的磁钢对象名称
        """
        pm_topology = self.config.pm_topology.value
        
        if pm_topology == "SPM":
            return self._build_spm_magnet(pm_index)
        elif pm_topology == "IPM_Flat":
            return self._build_ipm_flat_magnet(pm_index)
        elif pm_topology == "IPM_V":
            return self._build_ipm_v_magnet(pm_index)
        elif pm_topology == "IPM_Spoke":
            return self._build_ipm_spoke_magnet(pm_index)
        else:
            raise ValueError(f"不支持的永磁拓扑: {pm_topology}")
    
    def build_all_pms(self) -> List[str]:
        """生成全部磁钢"""
        self.pm_names = []
        poles = self.config.poles
        for i in range(1, poles + 1):
            name = self.build_single_pm(i)
            self.pm_names.append(name)
        return self.pm_names
    
    def duplicate_pms(self, pm_name: str = None):
        """
        将单极磁钢阵列为全部磁钢
        
        参数:
            pm_name: 要阵列的磁钢名称（默认第一个）
        """
        if pm_name is None and self.pm_names:
            pm_name = self.pm_names[0]
        
        pole_pitch_angle = 360.0 / self.config.poles
        
        script = f"""
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "{pm_name}",
     "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters",
     "CreateNewObjects:=", True,
     "WhichAxis:=", "Z",
     "AngleStr:=", "{pole_pitch_angle}deg",
     "Numclones:=", "{self.config.poles}"]
)
"""
        return script
    
    def set_magnetization_direction(self):
        """
        根据拓扑类型设置磁化方向
        
        返回:
            IronPython脚本
        """
        pm_topology = self.config.pm_topology.value
        poles = self.config.poles
        pole_pitch = 360.0 / poles
        
        scripts = []
        
        for i in range(1, poles + 1):
            pm_name = f"PM_{i}"
            angle_deg = (i - 1) * pole_pitch
            angle_rad = math.radians(angle_deg)
            
            if pm_topology == "SPM":
                # 径向向外磁化
                dx = math.cos(angle_rad)
                dy = math.sin(angle_rad)
                scripts.append(f"""
# {pm_name} 径向磁化
oEditor.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:MagnetGeometryTab",
      ["NAME:PropServers", "{pm_name}"],
      ["NAME:ChangedProps",
       ["NAME:Magnetization Vector X", "Value:=", "{dx:.6f}"],
       ["NAME:Magnetization Vector Y", "Value:=", "{dy:.6f}"]]]]
)
""")
            
            elif pm_topology == "IPM_Flat":
                # 平行磁化（沿X轴）
                scripts.append(f"""
# {pm_name} 平行磁化
oEditor.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:MagnetGeometryTab",
      ["NAME:PropServers", "{pm_name}"],
      ["NAME:ChangedProps",
       ["NAME:Magnetization Vector X", "Value:=", "1"],
       ["NAME:Magnetization Vector Y", "Value:=", "0"]]]]
)
""")
            
            elif pm_topology == "IPM_V":
                # V型：交替磁化方向形成聚磁
                if i % 2 == 1:
                    # 奇数极：径向向外
                    dx = math.cos(angle_rad)
                    dy = math.sin(angle_rad)
                else:
                    # 偶数极：径向向内
                    dx = -math.cos(angle_rad)
                    dy = -math.sin(angle_rad)
                
                scripts.append(f"""
# {pm_name} V型磁化
oEditor.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:MagnetGeometryTab",
      ["NAME:PropServers", "{pm_name}"],
      ["NAME:ChangedProps",
       ["NAME:Magnetization Vector X", "Value:=", "{dx:.6f}"],
       ["NAME:Magnetization Vector Y", "Value:=", "{dy:.6f}"]]]]
)
""")
        
        return "\n".join(scripts)
    
    # ═══════════════════════════════════════════════════════════════
    #  SPM - 表贴式磁钢（切向贴合转子表面）
    # ═══════════════════════════════════════════════════════════════
    
    def _build_spm_magnet(self, pm_index: int) -> str:
        """
        生成表贴式磁钢
        
        结构：矩形薄片贴在转子表面，与圆周相切
        
        参数:
            pm_index: 磁钢编号
        """
        c = self.config
        pm_name = f"PM_{pm_index}"
        
        # 计算磁钢位置
        rotor_radius = c.rotor_od / 2.0
        
        # 磁钢弧长对应的弦长（近似用矩形）
        pole_pitch_angle = 360.0 / c.poles
        pm_arc_angle = c.pm_pole_arc * pole_pitch_angle
        # 磁钢宽度（沿圆周方向）
        pm_width = 2 * rotor_radius * math.sin(math.radians(pm_arc_angle / 2.0))
        
        # 磁钢厚度（径向）
        pm_thickness = c.pm_thickness
        
        # 磁钢中心位置（在转子表面，X轴正方向）
        pm_center_x = rotor_radius + pm_thickness / 2.0
        pm_center_y = 0
        
        # 创建矩形：宽度沿Y轴（切向），厚度沿X轴（径向）
        script = f"""
# 表贴式磁钢 {pm_name} - 切向贴合转子表面
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{rotor_radius}mm",
     "YStart:=", "{-pm_width/2}mm",
     "ZStart:=", "0mm",
     "Width:=", "{pm_thickness}mm",
     "Height:=", "{pm_width}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{pm_name}",
     "Flags:=", "",
     "Color:=", "(255 0 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.pm_material}"',
     "SolveInside:=", True]
)
"""
        return pm_name
    
    def _build_spm_magnet_rotated(self, pm_index: int) -> str:
        """
        生成表贴式磁钢（带旋转，用于逐个创建模式）
        
        结构：矩形薄片贴在转子表面，旋转到指定角度
        """
        c = self.config
        pm_name = f"PM_{pm_index}"
        
        rotor_radius = c.rotor_od / 2.0
        pole_pitch_angle = 360.0 / c.poles
        pm_arc_angle = c.pm_pole_arc * pole_pitch_angle
        pm_width = 2 * rotor_radius * math.sin(math.radians(pm_arc_angle / 2.0))
        pm_thickness = c.pm_thickness
        
        # 计算旋转角度
        angle_deg = (pm_index - 1) * pole_pitch_angle
        angle_rad = math.radians(angle_deg)
        
        # 旋转后的中心位置
        pm_center_x = (rotor_radius + pm_thickness / 2.0) * math.cos(angle_rad)
        pm_center_y = (rotor_radius + pm_thickness / 2.0) * math.sin(angle_rad)
        
        # 创建矩形并旋转
        script = f"""
# 表贴式磁钢 {pm_name} - 旋转{angle_deg:.1f}度
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{rotor_radius}mm",
     "YStart:=", "{-pm_width/2}mm",
     "ZStart:=", "0mm",
     "Width:=", "{pm_thickness}mm",
     "Height:=", "{pm_width}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{pm_name}",
     "Flags:=", "",
     "Color:=", "(255 0 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.pm_material}"',
     "SolveInside:=", True]
)
oEditor.Rotate(
    ["NAME:Selections", "Selections:=", "{pm_name}"],
    ["NAME:RotateParameters",
     "RotateAxis:=", "Z",
     "RotateAngle:=", "{angle_deg}deg",
     "DuplicateObjects:=", False,
     "DuplicateSurfaceComponents:=", False]
)
"""
        return pm_name
    
    # ═══════════════════════════════════════════════════════════════
    #  IPM_Flat - 内置一字型磁钢
    # ═══════════════════════════════════════════════════════════════
    
    def _build_ipm_flat_magnet(self, pm_index: int) -> str:
        """
        生成内置一字型磁钢
        
        结构：矩形磁钢埋入转子铁心内部
        
        参数:
            pm_index: 磁钢编号
        """
        c = self.config
        pm_name = f"PM_{pm_index}"
        
        # 磁钢中心位置
        rotor_radius = c.rotor_od / 2.0
        pm_center_r = rotor_radius - c.pm_offset_r - c.pm_thickness / 2.0
        
        # 磁钢宽度方向沿X轴
        pm_x_start = pm_center_r - c.pm_thickness / 2.0
        pm_y_start = -c.pm_width / 2.0
        
        script = f"""
# 内置一字型磁钢 {pm_name}
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{pm_x_start}mm",
     "YStart:=", "{pm_y_start}mm",
     "ZStart:=", "0mm",
     "Width:=", "{c.pm_thickness}mm",
     "Height:=", "{c.pm_width}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{pm_name}",
     "Flags:=", "",
     "Color:=", "(255 0 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.pm_material}"',
     "SolveInside:=", True]
)
"""
        return pm_name
    
    # ═══════════════════════════════════════════════════════════════
    #  IPM_V - 内置V型磁钢
    # ═══════════════════════════════════════════════════════════════
    
    def _build_ipm_v_magnet(self, pm_index: int) -> str:
        """
        生成内置V型磁钢
        
        结构：两块矩形磁钢组成V字形
        
        参数:
            pm_index: 磁钢编号
        """
        c = self.config
        pm_name = f"PM_{pm_index}"
        
        # V型参数
        half_v_angle = c.pm_v_angle / 2.0
        rotor_radius = c.rotor_od / 2.0
        
        # V型中心点（转子内部）
        v_center_r = rotor_radius - c.pm_offset_r
        
        # 磁钢基础位置
        pm_x_start = v_center_r - c.pm_thickness / 2.0
        pm_y_start = -c.pm_width / 2.0
        
        script = f"""
# V型磁钢 {pm_name} - 上臂
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{pm_x_start}mm",
     "YStart:=", "{pm_y_start}mm",
     "ZStart:=", "0mm",
     "Width:=", "{c.pm_thickness}mm",
     "Height:=", "{c.pm_width}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{pm_name}_upper",
     "Flags:=", "",
     "Color:=", "(255 0 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.pm_material}"',
     "SolveInside:=", True]
)

# 旋转上臂
oEditor.Rotate(
    ["NAME:Selections", "Selections:=", "{pm_name}_upper"],
    ["NAME:RotateParameters",
     "RotateAxis:=", "Z",
     "RotateAngle:=", "{half_v_angle}deg",
     "DuplicateObjects:=", False,
     "DuplicateSurfaceComponents:=", False]
)

# V型磁钢 {pm_name} - 下臂
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{pm_x_start}mm",
     "YStart:=", "{pm_y_start}mm",
     "ZStart:=", "0mm",
     "Width:=", "{c.pm_thickness}mm",
     "Height:=", "{c.pm_width}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{pm_name}_lower",
     "Flags:=", "",
     "Color:=", "(255 0 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.pm_material}"',
     "SolveInside:=", True]
)

# 旋转下臂
oEditor.Rotate(
    ["NAME:Selections", "Selections:=", "{pm_name}_lower"],
    ["NAME:RotateParameters",
     "RotateAxis:=", "Z",
     "RotateAngle:=", "{-half_v_angle}deg",
     "DuplicateObjects:=", False,
     "DuplicateSurfaceComponents:=", False]
)

# 合并上下臂
oEditor.Unite(
    ["NAME:Selections", "Selections:=", "{pm_name}_upper,{pm_name}_lower"],
    ["NAME:UniteParameters", "KeepOriginals:=", False]
)

# 重命名为统一名称
oEditor.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:Geometry3DAttributeTab",
      ["NAME:PropServers", "{pm_name}_upper"],
      ["NAME:ChangedProps", ["NAME:Name", "Value:=", "{pm_name}"]]]]
)
"""
        return pm_name
    
    # ═══════════════════════════════════════════════════════════════
    #  IPM_Spoke - 磁阻型磁钢
    # ═══════════════════════════════════════════════════════════════
    
    def _build_ipm_spoke_magnet(self, pm_index: int) -> str:
        """
        生成磁阻型磁钢（简化版）
        
        参数:
            pm_index: 磁钢编号
        """
        # 与IPM_Flat类似，但磁钢沿径向排列
        return self._build_ipm_flat_magnet(pm_index)


# ═══════════════════════════════════════════════════════════════
#  快捷函数
# ═══════════════════════════════════════════════════════════════

def build_pm_by_topology(pm_topology: str, params: dict, pm_index: int = 1) -> str:
    """
    根据拓扑类型快速生成磁钢几何脚本
    
    参数:
        pm_topology: 拓扑类型名称
        params: 磁钢参数字典
        pm_index: 磁钢编号
    """
    from motor_config import MotorConfig, PMTopology, SlotType
    
    type_map = {
        "SPM": PMTopology.SPM,
        "IPM_Flat": PMTopology.IPM_FLAT,
        "IPM_V": PMTopology.IPM_V,
        "IPM_Spoke": PMTopology.IPM_SPOKE,
    }
    
    cfg = MotorConfig(
        pm_topology=type_map.get(pm_topology, PMTopology.SPM),
        rotor_od=params.get("rotor_od", 135.6),
        pole_pairs=params.get("poles", 4) // 2,
        pm_thickness=params.get("pm_thickness", 3.0),
        pm_pole_arc=params.get("pm_pole_arc", 0.85),
        pm_offset_r=params.get("pm_offset_r", 5.0),
        pm_width=params.get("pm_width", 15.0),
        pm_v_angle=params.get("v_angle", 120.0),
        pm_material=params.get("pm_material", "N38UH_20C"),
    )
    
    builder = PMBuilder(cfg)
    return builder.build_single_pm(pm_index)


if __name__ == "__main__":
    # 测试SPM磁钢生成
    from motor_config import MotorConfig, SlotType, PMTopology
    
    cfg = MotorConfig(
        slot_type=SlotType.PEAR,
        pm_topology=PMTopology.SPM,
        stator_od=210, stator_id=136,
        rotor_od=135.6, pole_pairs=2,
        pm_thickness=3.0, pm_pole_arc=0.85,
        pm_material="N38UH_20C",
    )
    
    builder = PMBuilder(cfg)
    
    # 生成单极SPM磁钢
    pm_script = builder.build_single_pm(1)
    print("生成的磁钢名称:", pm_script)
    
    # 测试IPM_V
    cfg_v = MotorConfig(
        pm_topology=PMTopology.IPM_V,
        rotor_od=135.6, pole_pairs=2,
        pm_thickness=2.5,
        pm_offset_r=5.0, pm_v_angle=120.0,
        pm_bridge=0.8,
    )
    
    builder_v = PMBuilder(cfg_v)
    pm_v_script = builder_v.build_single_pm(1)
    print("\nIPM_V磁钢名称:", pm_v_script)
