#!/usr/bin/env python3
"""
PMSM绕组生成器 - 自动线圈-相位分配
支持任意槽极配合，自动生成Maxwell COM API绕组脚本

基于星形图法（Star Diagram）计算线圈连接
支持双层分布绕组和集中绕组

用法：
    from pmsm_winding_builder import WindingBuilder
    builder = WindingBuilder(slots=36, poles=8, phases=3)
    winding_config = builder.compute_winding()
    script = builder.generate_maxwell_script(winding_config)
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from enum import Enum


class WindingType(Enum):
    """绕组类型"""
    DISTRIBUTED = "distributed"      # 分布绕组
    CONCENTRATED = "concentrated"    # 集中绕组
    FRACTIONAL = "fractional"        # 分数槽绕组


class LayerType(Enum):
    """绕组层数"""
    SINGLE = "single"                # 单层绕组
    DOUBLE = "double"                # 双层绕组


@dataclass
class CoilGroup:
    """线圈组"""
    phase: str                       # 相位：A, B, C
    polarity: str                    # 极性：+ 或 -
    coil_indices: List[int]          # 线圈索引列表
    coil_names: List[str] = field(default_factory=list)  # 线圈名称列表


@dataclass
class WindingConfig:
    """绕组配置"""
    slots: int                       # 槽数
    poles: int                       # 极数
    phases: int                      # 相数
    q: float                         # 每极每相槽数
    slot_angle: float                # 槽距角（度）
    pole_pitch: float                # 极距（度）
    winding_factor: float            # 绕组系数
    coil_groups: List[CoilGroup]     # 线圈组列表
    coil_to_phase: Dict[int, str]    # 线圈到相位映射
    coil_to_polarity: Dict[int, str] # 线圈到极性映射
    coil_span: int                   # 线圈节距（槽数）
    coils_per_phase: int             # 每相线圈数
    coils_per_group: int             # 每组线圈数


class WindingBuilder:
    """
    PMSM绕组生成器
    
    使用星形图法计算线圈连接，自动生成Maxwell COM API脚本
    """
    
    # 常用槽极配合的绕组系数表
    WINDING_FACTOR_TABLE = {
        (12, 8): 0.933,    # 8p12s
        (12, 10): 0.933,   # 10p12s
        (9, 8): 0.945,     # 8p9s
        (9, 10): 0.945,    # 10p9s
        (12, 4): 0.933,    # 4p12s
        (6, 4): 0.866,     # 4p6s
        (6, 8): 0.866,     # 8p6s
        (24, 4): 0.966,    # 4p24s
        (18, 16): 0.945,   # 16p18s
        (36, 8): 0.960,    # 8p36s
        (27, 24): 0.945,   # 24p27s
        (36, 4): 0.960,    # 4p36s
        (48, 8): 0.960,    # 8p48s
        (48, 16): 0.958,   # 16p48s
        (54, 6): 0.955,    # 6p54s
        (72, 6): 0.957,    # 6p72s
    }
    
    def __init__(self, slots: int, poles: int, phases: int = 3,
                 layer: LayerType = LayerType.DOUBLE,
                 winding_type: Optional[WindingType] = None):
        """
        初始化绕组生成器
        
        Args:
            slots: 槽数
            poles: 极数
            phases: 相数（默认3相）
            layer: 绕组层数（默认双层）
            winding_type: 绕组类型（自动检测）
        """
        self.slots = slots
        self.poles = poles
        self.phases = phases
        self.layer = layer
        self.phase_names = ['A', 'B', 'C'][:phases]
        
        # 计算基本参数
        self.q = slots / (phases * poles) if poles > 0 else 0  # 每极每相槽数
        self.slot_angle = 360.0 / slots if slots > 0 else 0    # 槽距角
        self.pole_pitch = 360.0 / poles if poles > 0 else 0    # 极距

        # 自动检测绕组类型
        if winding_type is None:
            self.winding_type = self._detect_winding_type()
        else:
            self.winding_type = winding_type
    
    def _detect_winding_type(self) -> WindingType:
        """自动检测绕组类型"""
        if self.q >= 1:
            if self.q == int(self.q):
                return WindingType.DISTRIBUTED
            else:
                return WindingType.FRACTIONAL
        else:
            return WindingType.CONCENTRATED
    
    def _gcd(self, a: int, b: int) -> int:
        """最大公约数"""
        while b:
            a, b = b, a % b
        return a
    
    def _lcm(self, a: int, b: int) -> int:
        """最小公倍数"""
        return abs(a * b) // self._gcd(a, b)
    
    def compute_winding_factor(self) -> float:
        """
        计算绕组系数
        
        对于分布绕组：Kw = Kd × Kp
        Kd = 分布系数，Kp = 节距系数
        """
        # 查表
        key = (self.slots, self.poles)
        if key in self.WINDING_FACTOR_TABLE:
            return self.WINDING_FACTOR_TABLE[key]
        
        # 通用计算
        if self.q >= 1:
            # 分布绕组
            alpha = math.pi * self.poles / self.slots
            q_floor = int(self.q)
            
            # 分布系数
            if self.q == q_floor:
                # 整数槽
                kd = math.sin(q_floor * alpha / 2) / (q_floor * math.sin(alpha / 2))
            else:
                # 分数槽，近似处理
                kd = math.sin(self.q * alpha / 2) / (self.q * math.sin(alpha / 2))
            
            # 节距系数（假设全节距）
            kp = 1.0
            return kd * kp
        else:
            # 集中绕组
            return 0.933  # 保守默认值
    
    def compute_winding(self) -> WindingConfig:
        """
        计算绕组配置

        使用星形图法确定线圈-相位分配

        Returns:
            WindingConfig: 绕组配置
        """
        # 计算线圈节距
        if self.winding_type == WindingType.CONCENTRATED:
            coil_span = 1
        else:
            coil_span = max(1, round(self.pole_pitch / self.slot_angle))

        # 计算绕组系数
        winding_factor = self.compute_winding_factor()

        # 每相线圈数
        if self.layer == LayerType.DOUBLE:
            coils_per_phase = self.slots  # 双层：每槽一个线圈
        else:
            coils_per_phase = self.slots // self.phases

        # 星形图法计算线圈-相位分配
        coil_to_phase, coil_to_polarity = self._star_diagram_method()

        # 组织成线圈组
        coil_groups = self._organize_coil_groups(coil_to_phase, coil_to_polarity)

        # 每组线圈数（= 每相线圈数 / 2）
        coils_per_group = coils_per_phase // 2 if coils_per_phase > 0 else 0

        return WindingConfig(
            slots=self.slots,
            poles=self.poles,
            phases=self.phases,
            q=self.q,
            slot_angle=self.slot_angle,
            pole_pitch=self.pole_pitch,
            winding_factor=winding_factor,
            coil_groups=coil_groups,
            coil_to_phase=coil_to_phase,
            coil_to_polarity=coil_to_polarity,
            coil_span=coil_span,
            coils_per_phase=coils_per_phase,
            coils_per_group=coils_per_group,
        )
    
    def _star_diagram_method(self) -> Tuple[Dict[int, str], Dict[int, str]]:
        """
        星形图法计算线圈-相位分配

        原理：
        1. 计算每个线圈的电角度位置
        2. 将线圈分配到对应的相位（A:0-120°, B:120-240°, C:240-360°）
        3. 每相内按电角度排序，前半部分为+，后半部分为-

        Returns:
            coil_to_phase: 线圈到相位映射
            coil_to_polarity: 线圈到极性映射
        """
        coil_to_phase = {}
        coil_to_polarity = {}

        # 计算每个槽的电角度
        slot_angles = {}
        for slot in range(self.slots):
            # 电角度 = 机械角度 × 极对数
            mech_angle = slot * self.slot_angle
            elec_angle = (mech_angle * self.poles / 2) % 360
            slot_angles[slot] = elec_angle

        # 分配到相位
        for slot, angle in slot_angles.items():
            if angle < 120:
                phase = 'A'
            elif angle < 240:
                phase = 'B'
            else:
                phase = 'C'
            coil_to_phase[slot] = phase

        # 极性分配：每相内按电角度排序，前一半为+，后一半为-
        for phase in self.phase_names:
            # 找出该相的所有线圈
            phase_slots = [(s, slot_angles[s]) for s in range(self.slots) if coil_to_phase[s] == phase]
            # 按电角度排序
            phase_slots.sort(key=lambda x: x[1])

            n = len(phase_slots)
            half = n // 2

            for i, (slot, _) in enumerate(phase_slots):
                coil_to_polarity[slot] = '+' if i < half else '-'

        return coil_to_phase, coil_to_polarity
    
    def _organize_coil_groups(self, coil_to_phase: Dict[int, str],
                              coil_to_polarity: Dict[int, str]) -> List[CoilGroup]:
        """
        组织线圈组
        
        将线圈按相位和极性分组
        """
        groups = []
        
        for phase in self.phase_names:
            for polarity in ['+', '-']:
                # 找出该相位和极性的所有线圈
                coil_indices = []
                for slot, (p, pol) in enumerate(zip(coil_to_phase.values(), coil_to_polarity.values())):
                    if p == phase and pol == polarity:
                        coil_indices.append(slot)
                
                # 生成线圈名称
                coil_names = [f"Coil_{i+1}" for i in coil_indices]
                
                groups.append(CoilGroup(
                    phase=phase,
                    polarity=polarity,
                    coil_indices=coil_indices,
                    coil_names=coil_names,
                ))
        
        return groups
    
    def generate_maxwell_script(self, config: WindingConfig,
                                 conductor_number: int = 50,
                                 winding_type: str = "Current") -> str:
        """
        生成Maxwell COM API绕组脚本
        
        Args:
            config: 绕组配置
            conductor_number: 每槽导体数
            winding_type: 绕组激励类型（Current/Voltage）
        
        Returns:
            生成的Python脚本
        """
        lines = []
        lines.append('# ============================================================')
        lines.append('# PMSM Winding Assignment Script')
        lines.append('# Auto-generated by pmsm_winding_builder.py')
        lines.append('# ============================================================')
        lines.append('')
        lines.append('import ScriptEnv')
        lines.append('ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")')
        lines.append('oDesktop = ScriptEnv.GetDesktop()')
        lines.append('oProject = oDesktop.GetActiveProject()')
        lines.append('oDesign = oProject.SetActiveDesign("Motor_Design")')
        lines.append('oModule = oDesign.GetModule("BoundarySetup")')
        lines.append('')
        
        # 生成绕组定义
        lines.append('# ============================================================')
        lines.append('# Step 1: 定义三相绕组')
        lines.append('# ============================================================')
        
        for phase in self.phase_names:
            lines.append(f'oModule.AssignWindingGroup(')
            lines.append(f'    [')
            lines.append(f'        "NAME:Winding{phase}",')
            lines.append(f'        "Type:=", "{winding_type}",')
            lines.append(f'        "IsSolid:=", False,')
            lines.append(f'        "Current:=", "0A",')
            lines.append(f'        "Resistance:=", "0.1ohm",')
            lines.append(f'        "Inductance:=", "0.001H",')
            lines.append(f'        "Voltage:=", "0V",')
            lines.append(f'        "ParallelBranchesNum:=", "1"')
            lines.append(f'    ]')
            lines.append(f')')
            lines.append('')
        
        # 生成线圈组赋值
        lines.append('# ============================================================')
        lines.append('# Step 2: 定义线圈组')
        lines.append('# ============================================================')
        
        for group in config.coil_groups:
            if not group.coil_indices:
                continue
            
            # 生成线圈名称列表
            coil_list = ', '.join([f'"{name}"' for name in group.coil_names])
            
            # 确定极性
            polarity = "Positive" if group.polarity == '+' else "Negative"
            
            lines.append(f'oModule.AssignCoilGroup(')
            lines.append(f'    [')
            lines.append(f'        "NAME:{group.phase}{group.polarity}_1",')
            lines.append(f'        "Objects:=", [{coil_list}],')
            lines.append(f'        "Conductor number:=", "{conductor_number}",')
            lines.append(f'        "PolarityType:=", "{polarity}"')
            lines.append(f'    ]')
            lines.append(f')')
            lines.append('')
        
        # 生成绕组-线圈连接
        lines.append('# ============================================================')
        lines.append('# Step 3: 连接线圈到绕组')
        lines.append('# ============================================================')
        
        for phase in self.phase_names:
            # 找出该相的所有线圈组
            phase_groups = [g for g in config.coil_groups if g.phase == phase]
            group_names = [f'"{g.phase}{g.polarity}_1"' for g in phase_groups if g.coil_indices]
            
            if group_names:
                groups_str = ', '.join(group_names)
                lines.append(f'oModule.AddWindingCoils("Winding{phase}", [{groups_str}])')
        
        lines.append('')
        lines.append('print("Winding assignment complete")')
        lines.append(f'print("  Phases: {self.phases}")')
        lines.append(f'print("  Slots: {self.slots}")')
        lines.append(f'print("  Poles: {self.poles}")')
        lines.append(f'print("  Coils per phase: {config.coils_per_phase}")')
        lines.append(f'print("  Winding factor: {config.winding_factor:.4f}")')
        
        return '\n'.join(lines)
    
    def generate_coil_renaming_script(self, config: WindingConfig) -> str:
        """
        生成线圈重命名脚本
        
        将默认的线圈名称重命名为更有意义的名称
        """
        lines = []
        lines.append('# ============================================================')
        lines.append('# Coil Renaming Script')
        lines.append('# ============================================================')
        lines.append('')
        lines.append('import ScriptEnv')
        lines.append('ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")')
        lines.append('oDesktop = ScriptEnv.GetDesktop()')
        lines.append('oProject = oDesktop.GetActiveProject()')
        lines.append('oDesign = oProject.SetActiveDesign("Motor_Design")')
        lines.append('oEditor = oDesign.SetActiveEditor("3D Modeler")')
        lines.append('')
        
        # 重命名线圈
        lines.append('# ============================================================')
        lines.append('# Rename coils based on phase and polarity')
        lines.append('# ============================================================')
        
        for group in config.coil_groups:
            if not group.coil_indices:
                continue
            
            # 生成旧名称和新名称
            old_names = ', '.join([f'"{name}"' for name in group.coil_names])
            new_name = f'{group.phase}{group.polarity}'
            
            lines.append(f'oEditor.ChangeProperty(')
            lines.append(f'    [')
            lines.append(f'        "NAME:AllTabs",')
            lines.append(f'        [')
            lines.append(f'            "NAME:Geometry3DAttributeTab",')
            lines.append(f'            [')
            lines.append(f'                "NAME:PropServers",')
            lines.append(f'                {old_names}')
            lines.append(f'            ],')
            lines.append(f'            [')
            lines.append(f'                "NAME:ChangedProps",')
            lines.append(f'                [')
            lines.append(f'                    "NAME:Name",')
            lines.append(f'                    "Value:=", "{new_name}"')
            lines.append(f'                ]')
            lines.append(f'            ]')
            lines.append(f'        ]')
            lines.append(f'    ]')
            lines.append(f')')
            lines.append('')
        
        lines.append('print("Coil renaming complete")')
        
        return '\n'.join(lines)
    
    def print_summary(self, config: WindingConfig):
        """打印绕组配置摘要"""
        print("\n" + "=" * 60)
        print("PMSM Winding Configuration Summary")
        print("=" * 60)
        print(f"  Slots: {config.slots}")
        print(f"  Poles: {config.poles}")
        print(f"  Phases: {config.phases}")
        print(f"  q (slots/pole/phase): {config.q:.2f}")
        print(f"  Slot angle: {config.slot_angle:.2f}°")
        print(f"  Pole pitch: {config.pole_pitch:.2f}°")
        print(f"  Coil span: {config.coil_span} slots")
        print(f"  Winding factor: {config.winding_factor:.4f}")
        print(f"  Coils per phase: {config.coils_per_phase}")
        print(f"  Coils per group: {config.coils_per_group}")
        print("\nCoil Groups:")
        for group in config.coil_groups:
            if group.coil_indices:
                print(f"  {group.phase}{group.polarity}: {len(group.coil_indices)} coils - {group.coil_names}")
        print("=" * 60)


# ============================================================
# 常用槽极配合预设
# ============================================================

def create_8p36s_winding():
    """8极36槽绕组（教程模式）"""
    builder = WindingBuilder(slots=36, poles=8, phases=3)
    return builder.compute_winding()


def create_8p12s_winding():
    """8极12槽绕组（伺服电机）"""
    builder = WindingBuilder(slots=12, poles=8, phases=3)
    return builder.compute_winding()


def create_10p12s_winding():
    """10极12槽绕组（低齿槽转矩）"""
    builder = WindingBuilder(slots=12, poles=10, phases=3)
    return builder.compute_winding()


# ============================================================
# 测试函数
# ============================================================

def test_winding_builder():
    """测试绕组生成器"""
    print("\n" + "=" * 60)
    print("Testing PMSM Winding Builder")
    print("=" * 60)
    
    # 测试8p36s
    print("\n--- 8p36s (Tutorial Pattern) ---")
    builder = WindingBuilder(slots=36, poles=8, phases=3)
    config = builder.compute_winding()
    builder.print_summary(config)
    
    # 生成脚本
    script = builder.generate_maxwell_script(config)
    print("\nGenerated script preview (first 50 lines):")
    print('\n'.join(script.split('\n')[:50]))
    
    # 测试8p12s
    print("\n--- 8p12s (Servo Motor) ---")
    builder2 = WindingBuilder(slots=12, poles=8, phases=3)
    config2 = builder2.compute_winding()
    builder2.print_summary(config2)
    
    # 测试10p12s
    print("\n--- 10p12s (Low Cogging) ---")
    builder3 = WindingBuilder(slots=12, poles=10, phases=3)
    config3 = builder3.compute_winding()
    builder3.print_summary(config3)


if __name__ == "__main__":
    test_winding_builder()
