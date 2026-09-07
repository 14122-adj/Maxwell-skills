"""
ANSYS Maxwell 电机槽型几何生成器
支持：矩形槽、梨形槽、梯形槽、圆形槽

使用方法：
    from slot_builder import SlotBuilder
    builder = SlotBuilder(config)
    builder.build_single_slot()
    builder.duplicate_slots()
"""

import math
from typing import List


class SlotBuilder:
    """槽型几何生成器"""
    
    def __init__(self, config):
        """
        初始化
        config: MotorConfig对象
        """
        self.config = config
        self.slot_names: List[str] = []
    
    def build_single_slot(self, slot_index: int = 1) -> str:
        """
        根据槽型类型生成单个槽的几何
        
        参数:
            slot_index: 槽编号（用于命名）
        
        返回:
            生成的槽对象名称
        """
        slot_type = self.config.slot_type.value
        
        if slot_type == "rectangular":
            return self._build_rectangular_slot(slot_index)
        elif slot_type == "pear":
            return self._build_pear_slot(slot_index)
        elif slot_type == "trapezoidal":
            return self._build_trapezoidal_slot(slot_index)
        elif slot_type == "round":
            return self._build_round_slot(slot_index)
        else:
            raise ValueError(f"不支持的槽型: {slot_type}")
    
    def build_all_slots(self) -> List[str]:
        """生成全部槽"""
        self.slot_names = []
        for i in range(1, self.config.slots + 1):
            name = self.build_single_slot(i)
            self.slot_names.append(name)
        return self.slot_names
    
    def duplicate_slots(self, slot_name: str = None):
        """
        将单个槽阵列为全部槽
        
        参数:
            slot_name: 要阵列的槽名称（默认第一个）
        """
        if slot_name is None and self.slot_names:
            slot_name = self.slot_names[0]
        
        slot_angle = 360.0 / self.config.slots
        
        # 通过MCP run_script调用IronPython阵列
        script = f"""
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "{slot_name}",
     "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters",
     "CreateNewObjects:=", True,
     "WhichAxis:=", "Z",
     "AngleStr:=", "{slot_angle}deg",
     "Numclones:=", "{self.config.slots}"]
)
"""
        return script
    
    def subtract_slots_from_stator(self, stator_name: str = "Stator"):
        """
        从定子铁心中减去全部槽
        
        参数:
            stator_name: 定子对象名称
        """
        if not self.slot_names:
            self.build_all_slots()
        
        tool_list = ", ".join(self.slot_names)
        script = f"""
oEditor.Subtract(
    ["NAME:Selections",
     "Blank Parts:=", "{stator_name}",
     "Tool Parts:=", "{tool_list}"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False]
)
"""
        return script
    
    # ═══════════════════════════════════════════════════════════════
    #  矩形槽
    # ═══════════════════════════════════════════════════════════════
    
    def _build_rectangular_slot(self, slot_index: int) -> str:
        """
        生成矩形槽
        结构：槽口(小矩形) + 槽体(大矩形)
        
        参数:
            slot_index: 槽编号
        """
        c = self.config
        slot_name = f"Slot_{slot_index}"
        
        # 计算位置
        stator_id_radius = c.stator_id / 2.0
        
        # 槽口段
        # 位置：从定子内径面开始，沿径向向外
        # 矩形：宽度=Bs0，高度=Hs0
        slot_opening_x = stator_id_radius
        slot_opening_y = -c.slot_Bs0 / 2.0
        slot_opening_width = c.slot_Hs0
        slot_opening_height = c.slot_Bs0
        
        # 槽体段
        slot_body_x = stator_id_radius + c.slot_Hs0
        slot_body_y = -c.slot_Bs2 / 2.0
        slot_body_width = c.slot_Hs2 - c.slot_Hs0
        slot_body_height = c.slot_Bs2
        
        # 生成MCP调用脚本
        script = f"""
# 矩形槽 {slot_name} - 槽口
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{slot_opening_x}mm",
     "YStart:=", "{slot_opening_y}mm",
     "ZStart:=", "0mm",
     "Width:=", "{slot_opening_width}mm",
     "Height:=", "{slot_opening_height}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{slot_name}_Open",
     "Flags:=", "",
     "Color:=", "(0 200 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"',
     "SolveInside:=", True]
)

# 矩形槽 {slot_name} - 槽体
oEditor.CreateRectangle(
    ["NAME:RectangleParameters",
     "IsCovered:=", True,
     "XStart:=", "{slot_body_x}mm",
     "YStart:=", "{slot_body_y}mm",
     "ZStart:=", "0mm",
     "Width:=", "{slot_body_width}mm",
     "Height:=", "{slot_body_height}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{slot_name}_Body",
     "Flags:=", "",
     "Color:=", "(0 200 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"',
     "SolveInside:=", True]
)

# 合并槽口和槽体
oEditor.Unite(
    ["NAME:Selections", "Selections:=", "{slot_name}_Open,{slot_name}_Body"],
    ["NAME:UniteParameters", "KeepOriginals:=", False]
)

# 重命名
oEditor.ChangeProperty(
    ["NAME:AllTabs",
     ["NAME:Geometry3DAttributeTab",
      ["NAME:PropServers", "{slot_name}_Open"],
      ["NAME:ChangedProps", ["NAME:Name", "Value:=", "{slot_name}"]]]]
)
"""
        return slot_name
    
    # ═══════════════════════════════════════════════════════════════
    #  梨形槽（本案例使用）
    # ═══════════════════════════════════════════════════════════════
    
    def _build_pear_slot(self, slot_index: int) -> str:
        """
        生成梨形槽
        结构：槽口(窄) → 槽楔(过渡) → 槽体(宽) → 槽底(圆角)
        
        参数:
            slot_index: 槽编号
        """
        c = self.config
        slot_name = f"Slot_{slot_index}"
        
        # 计算关键点坐标（XY平面，从定子内径向外）
        r0 = c.stator_id / 2.0  # 定子内径半径
        
        # 槽口段端点
        x0 = r0
        y0_left = -c.slot_Bs0 / 2.0
        y0_right = c.slot_Bs0 / 2.0
        
        # 槽楔段端点（从Bs0过渡到Bs1）
        x1 = r0 + c.slot_Hs0
        y1_left = -c.slot_Bs1 / 2.0
        y1_right = c.slot_Bs1 / 2.0
        
        # 槽体段端点（从Bs1过渡到Bs2）
        x2 = r0 + c.slot_Hs0 + c.slot_Hs1
        y2_left = -c.slot_Bs2 / 2.0
        y2_right = c.slot_Bs2 / 2.0
        
        # 槽底圆弧中心
        x_arc_center = x2
        y_arc_center = 0
        arc_radius = c.slot_Rs
        
        # 生成MCP调用脚本（通过polyline绘制槽轮廓）
        script = f"""
# 梨形槽 {slot_name} - 使用Polyline绘制
oEditor.CreatePolyline(
    ["NAME:PolylineParameters",
     "IsPolylineCovered:=", True,
     "IsPolylineClosed:=", True],
    ["NAME:PolylinePoints",
     # 槽口左端
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_left}mm", "Z:=", "0mm"],
     # 槽楔左端
     ["NAME:PLPoint", "X:=", "{x1}mm", "Y:=", "{y1_left}mm", "Z:=", "0mm"],
     # 槽体左端
     ["NAME:PLPoint", "X:=", "{x2}mm", "Y:=", "{y2_left}mm", "Z:=", "0mm"],
     # 槽底圆弧（用多个点近似）
     ["NAME:PLPoint", "X:=", "{x2 + arc_radius}mm", "Y:=", "0mm", "Z:=", "0mm"],
     # 槽体右端
     ["NAME:PLPoint", "X:=", "{x2}mm", "Y:=", "{y2_right}mm", "Z:=", "0mm"],
     # 槽楔右端
     ["NAME:PLPoint", "X:=", "{x1}mm", "Y:=", "{y1_right}mm", "Z:=", "0mm"],
     # 槽口右端
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_right}mm", "Z:=", "0mm"],
     # 闭合回起点
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_left}mm", "Z:=", "0mm"]
    ],
    ["NAME:PolylineSegments",
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Arc", "StartIndex:=", 3, "NoOfPoints:=", 3],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 7, "NoOfPoints:=", 2]
    ],
    ["NAME:Attributes",
     "Name:=", "{slot_name}",
     "Flags:=", "",
     "Color:=", "(0 200 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"',
     "SolveInside:=", True]
)
"""
        return slot_name
    
    # ═══════════════════════════════════════════════════════════════
    #  梯形槽
    # ═══════════════════════════════════════════════════════════════
    
    def _build_trapezoidal_slot(self, slot_index: int) -> str:
        """
        生成梯形槽
        结构：槽口(窄) → 槽体(宽，梯形)
        
        参数:
            slot_index: 槽编号
        """
        c = self.config
        slot_name = f"Slot_{slot_index}"
        
        r0 = c.stator_id / 2.0
        
        # 关键点
        x0 = r0
        y0_left = -c.slot_Bs0 / 2.0
        y0_right = c.slot_Bs0 / 2.0
        
        x1 = r0 + c.slot_Hs0 + c.slot_Hs1
        y1_left = -c.slot_Bs1 / 2.0
        y1_right = c.slot_Bs1 / 2.0
        
        script = f"""
# 梯形槽 {slot_name}
oEditor.CreatePolyline(
    ["NAME:PolylineParameters",
     "IsPolylineCovered:=", True,
     "IsPolylineClosed:=", True],
    ["NAME:PolylinePoints",
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_left}mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", "{x1}mm", "Y:=", "{y1_left}mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", "{x1}mm", "Y:=", "{y1_right}mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_right}mm", "Z:=", "0mm"],
     ["NAME:PLPoint", "X:=", "{x0}mm", "Y:=", "{y0_left}mm", "Z:=", "0mm"]
    ],
    ["NAME:PolylineSegments",
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],
     ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 3, "NoOfPoints:=", 2]
    ],
    ["NAME:Attributes",
     "Name:=", "{slot_name}",
     "Flags:=", "",
     "Color:=", "(0 200 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"',
     "SolveInside:=", True]
)
"""
        return slot_name
    
    # ═══════════════════════════════════════════════════════════════
    #  圆形槽
    # ═══════════════════════════════════════════════════════════════
    
    def _build_round_slot(self, slot_index: int) -> str:
        """
        生成圆形槽
        
        参数:
            slot_index: 槽编号
        """
        c = self.config
        slot_name = f"Slot_{slot_index}"
        
        r0 = c.stator_id / 2.0
        center_x = r0 + c.slot_Hs2 / 2.0
        center_y = 0
        radius = c.slot_Bs2 / 2.0  # 使用Bs2作为直径
        
        script = f"""
# 圆形槽 {slot_name}
oEditor.CreateCircle(
    ["NAME:CircleParameters",
     "XPosition:=", "{center_x}mm",
     "YPosition:=", "{center_y}mm",
     "ZPosition:=", "0mm",
     "Radius:=", "{radius}mm",
     "WhichAxis:=", "Z"],
    ["NAME:Attributes",
     "Name:=", "{slot_name}",
     "Flags:=", "",
     "Color:=", "(0 200 0)",
     "Transparency:=", 0,
     "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"',
     "SolveInside:=", True]
)
"""
        return slot_name


# ═══════════════════════════════════════════════════════════════
#  快捷函数
# ═══════════════════════════════════════════════════════════════

def build_slot_by_type(slot_type: str, params: dict, slot_index: int = 1) -> str:
    """
    根据槽型类型快速生成槽几何脚本
    
    参数:
        slot_type: 槽型名称
        params: 槽型参数字典
        slot_index: 槽编号
    """
    from motor_config import MotorConfig, SlotType
    
    # 创建临时配置
    type_map = {
        "rectangular": SlotType.RECTANGULAR,
        "pear": SlotType.PEAR,
        "trapezoidal": SlotType.TRAPEZOIDAL,
        "round": SlotType.ROUND,
    }
    
    cfg = MotorConfig(
        slot_type=type_map.get(slot_type, SlotType.PEAR),
        stator_id=params.get("stator_id", 136),
        slot_Hs0=params.get("Hs0", 0.8),
        slot_Hs1=params.get("Hs1", 1.5),
        slot_Hs2=params.get("Hs2", 11.5),
        slot_Bs0=params.get("Bs0", 3.5),
        slot_Bs1=params.get("Bs1", 6.2),
        slot_Bs2=params.get("Bs2", 8.3),
        slot_Rs=params.get("Rs", 4.15),
    )
    
    builder = SlotBuilder(cfg)
    return builder.build_single_slot(slot_index)


if __name__ == "__main__":
    # 测试梨形槽生成
    from motor_config import MotorConfig, SlotType, PMTopology
    
    cfg = MotorConfig(
        slot_type=SlotType.PEAR,
        pm_topology=PMTopology.SPM,
        stator_od=210, stator_id=136,
        rotor_od=135.6,
        slots=36,
        slot_Hs0=0.8, slot_Hs1=1.5, slot_Hs2=11.5,
        slot_Bs0=3.5, slot_Bs1=6.2, slot_Bs2=8.3, slot_Rs=4.15,
    )
    
    builder = SlotBuilder(cfg)
    
    # 生成单个梨形槽
    slot_script = builder.build_single_slot(1)
    print("生成的槽名称:", slot_script)
    print("\n槽轮廓脚本:")
    print(builder._build_pear_slot(1)[:500], "...")
