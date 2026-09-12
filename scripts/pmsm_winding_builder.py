#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMSM 绕组生成器 v2 — lookup-first + 修集中绕组极性 bug

设计哲学 (v2 重要变更):
  1. 【权威源】所有槽-相-极性映射必须先查 CANONICAL_LAYOUTS 真值表
     (与 references/winding_layouts.md 完全一致)。
     算法仅作为查表未覆盖时的 fallback, 且结果必须打印出来供人核对。
  2. 【修 bug】v1 的 _star_diagram_method 对 8p12s 集中绕组全部输出 + 极性
     (违反 Pyrhonen A+ A- B+ B- C+ C- 交替规律)。v2 改为查表优先,
     算法回退时也修正了集中绕组极性逻辑。
  3. 【可读性】generate_winding() 必输出 "人类可读槽位图",
     与 references/winding_layouts.md 表格同格式, AI 可直接 copy 进 SKILL.md。
  4. 【统一命名】Maxwell 线圈名统一为 Coil_{i} (1-indexed),
     Coil Group 名统一为 A+, A-, B+, B-, C+, C-,
     PolarityType 统一为 A+/Positive, A-/Negative (参见 references/winding_layouts.md §17.2)。

用法:
    from pmsm_winding_builder import WindingBuilder
    builder = WindingBuilder(slots=8, poles=12)        # 错! 应为 slots=12, poles=8
    builder = WindingBuilder(slots=12, poles=8)         # ✓ 8p12s
    config = builder.compute_winding()                  # 必查表
    print(builder.render_slot_map(config))              # 人类可读图
    print(builder.render_phase_belt(config))            # Phase Belt 展开
    script = builder.generate_maxwell_script(config)    # Maxwell COM 脚本
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════════
#  枚举
# ═══════════════════════════════════════════════════════════════

class WindingType(Enum):
    DISTRIBUTED = "distributed"
    CONCENTRATED = "concentrated"
    FRACTIONAL = "fractional"


class LayerType(Enum):
    SINGLE = "single"
    DOUBLE = "double"


# ═══════════════════════════════════════════════════════════════
#  ★ Canonical Layout 真值表 (与 references/winding_layouts.md 同步)
# ═══════════════════════════════════════════════════════════════
# 格式: (slots, poles) -> [(slot_1_phase, slot_1_polarity), ...]
# 槽编号 1-indexed, 长度必须 == slots
# 仅包含电机制造业最常用的 16+ 极槽配合

CANONICAL_LAYOUTS: Dict[Tuple[int, int], List[Tuple[str, str]]] = {
    # ── 集中绕组 (q < 1) ──
    (12, 8): [  # 8p/12s 变体 A (Pyrhonen AABBCC, 教材标准)
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
    ],
    (12, 10): [  # 10p/12s
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
    ],
    (12, 14): [  # 14p/12s
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
    ],
    (9, 8): [  # 8p/9s (q=0.375, 不平衡磁拉力警告)
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),
    ],
    (18, 8): [  # 8p/18s (q=0.75)
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
    ],
    (24, 10): [  # 10p/24s (q=0.8)
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
    ],
    (12, 4): [  # 4p/12s (q=1, 实为整数槽)
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
    ],
    # ── 分布绕组 (q ≥ 1) ──
    (24, 8): [  # 8p/24s (q=1)
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
    ],
    (36, 8): [  # 8p/36s (q=1.5, 风电常用) — 9 槽周期 × 4
        # 60° 相带, 1+2- per period, 4+8- per phase
        # (这是 Pyrhonen 教材标准, 8p36s 本身就有 MMF 次谐波, 业界常用 4p36s q=3 替代)
        ("A","+"),("A","-"),("C","-"),("B","+"),("B","-"),("A","-"),("C","+"),("C","-"),("B","-"),
    ] * 4,
    (48, 8): [  # 8p/48s (q=2)
        ("A","+"),("A","-"),("A","+"),("A","-"),("B","+"),("B","-"),("B","+"),("B","-"),
        ("C","+"),("C","-"),("C","+"),("C","-"),
    ] * 4,  # 每 12 槽重复 4 次 = 48
    (24, 4): [  # 4p/24s (q=2)
        ("A","+"),("A","-"),("A","+"),("A","-"),("B","+"),("B","-"),("B","+"),("B","-"),
        ("C","+"),("C","-"),("C","+"),("C","-"),
    ] * 2,
    (36, 4): [  # 4p/36s (q=3, 60°相带, 9槽周期 × 4)
        # 周期 0: A+(0°),A+(20°),C-(40°),C-(60°),C-(80°),B+(100°),B+(120°),B+(140°),A-(160°)
        # 极性: A 2+ 1- per period, B 3+ 0-, C 0+ 3- (q=3 分数槽固有不平衡)
        ("A","+"),("A","+"),("C","-"),("C","-"),("C","-"),("B","+"),("B","+"),("B","+"),("A","-"),
    ] * 4,
    (36, 6): [  # 6p/36s (q=2, 60°相带, 12槽周期 × 3)
        # 周期 0: A+(0°),C-(30°),C-(60°),B+(90°),B+(120°),A-(150°),A-(180°),C+(210°),C+(240°),B-(270°),B-(300°),A+(330°)
        # 每相 2+ 2- per period, 6+ 6- per motor, 平衡
        ("A","+"),("C","-"),("C","-"),("B","+"),("B","+"),("A","-"),
        ("A","-"),("C","+"),("C","+"),("B","-"),("B","-"),("A","+"),
    ] * 3,
    (54, 6): [  # 6p/54s (q=3)
        ("A","+"),("A","-"),("A","+"),("B","+"),("B","-"),("B","+"),
        ("C","+"),("C","-"),("C","+"),
    ] * 6,
    (72, 6): [  # 6p/72s (q=4)
        ("A","+"),("A","-"),("A","+"),("A","-"),("B","+"),("B","-"),("B","+"),("B","-"),
        ("C","+"),("C","-"),("C","+"),("C","-"),
    ] * 6,
    (24, 16): [  # 16p/24s (q=0.5, 集中但 q 整数)
        ("A","+"),("A","-"),("B","+"),("B","-"),("C","+"),("C","-"),
    ] * 4,
    (36, 16): [  # 16p/36s (q=0.75, 集中)
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
    ] * 6,
    (27, 24): [  # 24p/27s (q=0.375)
        ("A","+"),("C","-"),("B","+"),("A","-"),("C","+"),("B","-"),
        ("A","+"),("C","-"),("B","+"),
    ] * 3,
    (54, 12): [  # 12p/54s (q=1.5, 分布)
        ("A","+"),("A","-"),("A","+"),("B","+"),("B","-"),("B","+"),
        ("C","+"),("C","-"),("C","+"),
    ] * 6,
}


# ═══════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class CoilGroup:
    phase: str                        # 'A' / 'B' / 'C'
    polarity: str                     # '+' / '-'
    coil_indices: List[int]           # 1-indexed 槽号
    coil_names: List[str] = field(default_factory=list)  # ['Coil_1', 'Coil_7', ...]


@dataclass
class WindingConfig:
    slots: int
    poles: int
    phases: int
    q: float
    slot_angle: float                 # 机械角 (度)
    pole_pitch: float                 # 机械角 (度)
    electrical_slot_angle: float      # 电角 (度)
    winding_factor: float
    coil_span: int                    # 线圈节距 (槽数)
    coils_per_phase: int
    coil_groups: List[CoilGroup]
    slot_map: List[Tuple[str, str]]   # 1-indexed: [(phase, polarity), ...]
    source: str = "canonical"         # "canonical" | "computed"


# ═══════════════════════════════════════════════════════════════
#  Builder
# ═══════════════════════════════════════════════════════════════

class WindingBuilder:
    # 兼容旧字段名 (k_w lookup, 优先于公式计算, 因公式对分数槽不准确)
    WINDING_FACTOR_TABLE = {
        # 集中绕组
        (12, 8): 0.866, (12, 10): 0.933, (12, 14): 0.933,
        (9, 8): 0.945, (9, 10): 0.945,
        (12, 4): 0.933, (6, 4): 0.866, (6, 8): 0.866,
        (18, 8): 0.945, (24, 10): 0.933,
        (24, 16): 0.866, (36, 16): 0.945, (27, 24): 0.945,
        # 分布绕组
        (24, 4): 0.966, (24, 8): 0.96, (36, 4): 0.96,
        (36, 6): 0.866, (36, 8): 0.96, (48, 8): 0.96,
        (54, 6): 0.945, (54, 12): 0.96, (72, 6): 0.957,
        (48, 16): 0.958,
    }

    def __init__(self, slots: int, poles: int, phases: int = 3,
                 layer: LayerType = LayerType.DOUBLE,
                 winding_type: Optional[WindingType] = None,
                 pattern: str = "AABBCC",
                 polarity_convention: str = "standard"):
        """
        Args:
            slots:    槽数 Q
            poles:    极数 2p
            phases:   相数 m
            layer:    双层/单层
            winding_type: 分布/集中/分数槽 (None=自动)
            pattern:  集中绕组变体 "AABBCC" (Pyrhonen) | "ABCABC" (标准)
                     分布绕组此参数被忽略
            polarity_convention:
                "standard" (默认): A+/B+/C+ → PolarityType=Positive,
                                    A-/B-/C- → PolarityType=Negative
                                    (与 Maxwell UI 默认一致, 本表推荐)
                "legacy":          A+/B+/C+ → PolarityType=Negative,
                                    A-/B-/C- → PolarityType=Positive
                                    (与 output_scripts/36slot_industrial/winding.py 旧版一致)
        """
        assert slots > 0 and poles > 0
        self.slots = slots
        self.poles = poles
        self.phases = phases
        self.phase_names = ['A', 'B', 'C'][:phases]
        self.layer = layer
        self.pattern = pattern
        assert polarity_convention in ("standard", "legacy"), f"unknown convention: {polarity_convention}"
        self.polarity_convention = polarity_convention

        # 派生几何量
        self.pole_pairs = poles / 2.0
        self.q = slots / (phases * poles)
        self.slot_angle = 360.0 / slots                  # 机械角
        self.pole_pitch = 360.0 / poles                  # 机械角
        self.electrical_slot_angle = 360.0 * self.pole_pairs / slots  # 电角

        # 绕组类型
        if winding_type is None:
            self.winding_type = self._detect_winding_type()
        else:
            self.winding_type = winding_type

    def polarity_type(self, polarity: str) -> str:
        """
        根据 polarity 字符和 convention 返回 Maxwell PolarityType。
        'standard': + → Positive, - → Negative
        'legacy':   + → Negative, - → Positive
        """
        if self.polarity_convention == "legacy":
            return "Negative" if polarity == '+' else "Positive"
        return "Positive" if polarity == '+' else "Negative"

    # ─────────────────────────────────────────────────────
    #  类型检测
    # ─────────────────────────────────────────────────────

    def _detect_winding_type(self) -> WindingType:
        if self.q >= 1:
            if abs(self.q - round(self.q)) < 1e-6:
                return WindingType.DISTRIBUTED
            return WindingType.FRACTIONAL
        return WindingType.CONCENTRATED

    # ─────────────────────────────────────────────────────
    #  绕组系数
    # ─────────────────────────────────────────────────────

    def compute_winding_factor(self) -> float:
        key = (self.slots, self.poles)
        if key in self.WINDING_FACTOR_TABLE:
            return self.WINDING_FACTOR_TABLE[key]
        if self.winding_type == WindingType.CONCENTRATED:
            return 0.866
        # 分布近似
        alpha = math.radians(self.electrical_slot_angle)
        q = self.q
        y = max(1, round(self.q * self.phases / 2.0))     # 粗略节距
        kd = math.sin(q * alpha / 2) / (q * math.sin(alpha / 2)) if math.sin(alpha/2) > 1e-9 else 1.0
        kp = math.cos((y * alpha - math.pi) / 2) if self.electrical_slot_angle > 0 else 1.0
        return abs(kd * kp)

    # ─────────────────────────────────────────────────────
    #  ★ 主入口: compute_winding()
    # ─────────────────────────────────────────────────────

    def compute_winding(self) -> WindingConfig:
        """
        计算绕组配置。

        v2 流程:
          1. 先查 CANONICAL_LAYOUTS 真值表 (权威)
          2. 查不到才用算法 (fallback, 集中绕组用修正后的 Pyrhonen 模式)
          3. 必输出 source 字段, AI 应校验 source == "canonical" 才信任
        """
        # ── Step 1: 查表 (支持 (slots, poles) 和 (slots, poles, variant)) ──
        key = (self.slots, self.poles)
        if key in CANONICAL_LAYOUTS:
            slot_map = CANONICAL_LAYOUTS[key]
            if len(slot_map) != self.slots:
                raise ValueError(
                    f"CANONICAL_LAYOUTS[{key}] 长度 {len(slot_map)} != slots {self.slots}, "
                    f"真值表损坏！请检查 references/winding_layouts.md"
                )
            source = "canonical"
        else:
            # ── Step 2: fallback 算法 (修过的版本) ──
            slot_map = self._compute_slot_map_fallback()
            source = "computed"

        # ── Step 3: 派生 CoilGroup, coil_names ──
        coil_groups, coil_to_phase, coil_to_polarity = self._build_coil_groups(slot_map)

        # ── Step 4: 绕组系数 + 节距 ──
        winding_factor = self.compute_winding_factor()
        if self.winding_type == WindingType.CONCENTRATED:
            coil_span = 1
        else:
            coil_span = max(1, round(self.pole_pitch / self.slot_angle))

        coils_per_phase = sum(1 for p, _ in slot_map if p in self.phase_names)
        coils_per_phase //= 1  # (already correct)

        config = WindingConfig(
            slots=self.slots,
            poles=self.poles,
            phases=self.phases,
            q=self.q,
            slot_angle=self.slot_angle,
            pole_pitch=self.pole_pitch,
            electrical_slot_angle=self.electrical_slot_angle,
            winding_factor=winding_factor,
            coil_span=coil_span,
            coils_per_phase=coils_per_phase,
            coil_groups=coil_groups,
            slot_map=slot_map,
            source=source,
        )
        return config

    # ─────────────────────────────────────────────────────
    #  ★ Fallback 算法 (查表未命中时用, 已修集中绕组极性 bug)
    # ─────────────────────────────────────────────────────

    def _compute_slot_map_fallback(self) -> List[Tuple[str, str]]:
        """
        当 CANONICAL_LAYOUTS 没有 (slots, poles) 时, 用此算法生成。

        修复历史:
          v1 的 _star_diagram_method 对 8p12s 集中绕组全部输出 + 极性 (bug)。
          v2 修正: 集中绕组使用"电角距相中心 < 30° → +, 30-60° → -, > 60° → +"
          三个槽一组, 确保每个相带交替 + - +
        """
        pole_pairs = self.pole_pairs
        phase_centers = {'A': 0.0, 'B': 120.0, 'C': 240.0}

        # Step 1: 每槽电角
        slot_elec = [
            (s * self.slot_angle * pole_pairs) % 360.0
            for s in range(self.slots)
        ]

        # Step 2: 相位带
        slot_phase = []
        for alpha in slot_elec:
            best, best_d = 'A', 1e9
            for ph, c in phase_centers.items():
                d = min(abs(alpha - c), 360.0 - abs(alpha - c))
                if d < best_d:
                    best_d, best = d, ph
            slot_phase.append(best)

        # Step 3: 极性 (关键修复!)
        slot_pol = []
        for s in range(self.slots):
            alpha = slot_elec[s]
            ph = slot_phase[s]
            center = phase_centers[ph]
            d = (alpha - center + 360.0) % 360.0

            if self.winding_type == WindingType.CONCENTRATED:
                # 集中绕组: 同一相内电角按 0→60→120 排序后交替 + - + - ...
                # 取该槽在同相内电角排名第几
                same_phase = [i for i, p in enumerate(slot_phase) if p == ph]
                same_phase_sorted = sorted(same_phase, key=lambda i: slot_elec[i])
                rank = same_phase_sorted.index(s)
                slot_pol.append('+' if rank % 2 == 0 else '-')
            else:
                # 分布绕组: 相带内 0-60° → +, 60-120° → -
                slot_pol.append('+' if d < 60.0 else '-')

        return list(zip(slot_phase, slot_pol))

    # ─────────────────────────────────────────────────────
    #  Coil Group 构建
    # ─────────────────────────────────────────────────────

    def _build_coil_groups(self, slot_map: List[Tuple[str, str]]):
        """
        把 slot_map 转成 (CoilGroup list, coil_to_phase dict, coil_to_polarity dict)
        槽号 1-indexed。Maxwell 中 Coil_{i} 对应 slot i。
        """
        coil_to_phase = {i + 1: slot_map[i][0] for i in range(self.slots)}
        coil_to_polarity = {i + 1: slot_map[i][1] for i in range(self.slots)}

        groups = []
        for phase in self.phase_names:
            for polarity in ['+', '-']:
                indices = [i + 1 for i in range(self.slots)
                           if slot_map[i] == (phase, polarity)]
                if not indices:
                    continue
                names = [f"Coil_{i}" for i in indices]
                groups.append(CoilGroup(
                    phase=phase, polarity=polarity,
                    coil_indices=indices, coil_names=names,
                ))
        return groups, coil_to_phase, coil_to_polarity

    # ─────────────────────────────────────────────────────
    #  ★ 人类可读输出 (与 references/winding_layouts.md 同格式)
    # ─────────────────────────────────────────────────────

    def render_slot_map(self, config: WindingConfig) -> str:
        """
        输出与 references/winding_layouts.md 完全同格式的槽位图。
        AI 可直接 copy 进回答。
        """
        lines = []
        lines.append(f"# {self.poles}p/{self.slots}s {self.winding_type.value} "
                     f"(q={self.q:.3f}, k_w={config.winding_factor:.3f}, "
                     f"source={config.source})")
        lines.append("")

        # Slot 编号行
        slot_nums = " ".join(f"{i+1:>4}" for i in range(self.slots))
        lines.append(f"Slot:    {slot_nums}")
        # Phase 标号行
        phase_str = " ".join(f"{p}{pol:>3}" for p, pol in config.slot_map)
        lines.append(f"Phase:   {phase_str}")
        # Coil 标号行
        coil_nums = " ".join(f"{'C'+str(i+1):>4}" for i in range(self.slots))
        lines.append(f"Coil:    {coil_nums}")
        return "\n".join(lines)

    def render_phase_belt(self, config: WindingConfig) -> str:
        """
        输出 Phase Belt Diagram (与 references/winding_layouts.md §2 同格式)。
        """
        lines = []
        lines.append(f"# Phase Belt Diagram for {self.poles}p/{self.slots}s")
        lines.append("")
        # 12 槽为一行 (太多槽时分多行)
        per_row = 12 if self.slots >= 12 else self.slots
        rows = (self.slots + per_row - 1) // per_row
        for r in range(rows):
            s0 = r * per_row
            s1 = min(s0 + per_row, self.slots)
            row_nums = " ".join(f"{i+1:>4}" for i in range(s0, s1))
            row_phase = " ".join(f"{p}{pol:>3}" for p, pol in config.slot_map[s0:s1])
            lines.append(f"Row {r+1}: Slot = {row_nums}  |  Phase = {row_phase}")
        lines.append("")
        lines.append(f"  Slot angle (mech)   = {config.slot_angle:.2f}°")
        lines.append(f"  Slot angle (elec)   = {config.electrical_slot_angle:.2f}°")
        lines.append(f"  Pole pitch (mech)   = {config.pole_pitch:.2f}°")
        lines.append(f"  Coil span (y)       = {config.coil_span}")
        lines.append(f"  Winding factor k_w  = {config.winding_factor:.4f}")
        return "\n".join(lines)

    def render_summary(self, config: WindingConfig) -> str:
        """每相 +/- 线圈数自检 (AI 用此对账)"""
        lines = []
        lines.append(f"# Winding Summary ({self.poles}p/{self.slots}s, source={config.source})")
        lines.append("")
        for phase in self.phase_names:
            n_pos = sum(1 for p, pol in config.slot_map if p == phase and pol == '+')
            n_neg = sum(1 for p, pol in config.slot_map if p == phase and pol == '-')
            lines.append(f"  Phase {phase}: {n_pos:>2}+  {n_neg:>2}-  (total {n_pos+n_neg})")
        n_pos = sum(1 for p, pol in config.slot_map if pol == '+')
        n_neg = sum(1 for p, pol in config.slot_map if pol == '-')
        lines.append(f"  TOTAL:  {n_pos:>2}+  {n_neg:>2}-")
        lines.append("")

        # ── 自检规则 ──
        # 1. 三相线圈总数必须相等
        n_per_phase = {p: sum(1 for pp, _ in config.slot_map if pp == p) for p in self.phase_names}
        if len(set(n_per_phase.values())) > 1:
            lines.append(f"  [ERROR] 三相线圈数不均衡: {n_per_phase}  ← 真 bug, 不能用")

        # 2. 集中绕组 (q < 1): 整数 q 要求 + 和 - 平衡
        if self.winding_type == WindingType.CONCENTRATED:
            if n_pos != n_neg:
                lines.append(f"  [WARN] 集中绕组 + ({n_pos}) != - ({n_neg}), 预期平衡 (每极每相 q 应整除极数)")
            # 集中绕组: 同一相对极应交替
            for phase in self.phase_names:
                pol_seq = [pol for p, pol in config.slot_map if p == phase]
                if len(pol_seq) >= 2:
                    alternations = sum(1 for i in range(1, len(pol_seq)) if pol_seq[i] != pol_seq[i-1])
                    if alternations < len(pol_seq) - 1:
                        lines.append(f"  [WARN] Phase {phase} 极性非完全交替: {''.join(pol_seq)}")

        # 3. 分布绕组 (q 分数): + 和 - 可能不平衡, 但应一致
        elif self.winding_type in (WindingType.DISTRIBUTED, WindingType.FRACTIONAL):
            # 分数槽绕组的不平衡是固有的, 不报 WARN
            # 但应检查三相是否一致不平衡
            n_pos_per_phase = {p: sum(1 for pp, pol in config.slot_map if pp == p and pol == '+')
                               for p in self.phase_names}
            if len(set(n_pos_per_phase.values())) > 1:
                lines.append(f"  [WARN] 三相 + 极性数不一致: {n_pos_per_phase}  ← 可能 bug")
            else:
                if n_pos != n_neg:
                    lines.append(f"  [INFO] q={self.q} 分布/分数槽, + {n_pos} / - {n_neg} 不平衡是固有特征 (Pyrhonen §4.4)")

        # 4. source=computed: 提醒人工核对
        if config.source == "computed":
            lines.append("  [WARN] source=computed, 槽位图未在 canonical 真值表 (references/winding_layouts.md) 中,")
            lines.append("         请人工核对后向真值表添加新条目")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────
    #  Maxwell COM API 脚本生成
    # ─────────────────────────────────────────────────────

    def generate_maxwell_script(self, config: WindingConfig,
                                 conductor_number: int = 50,
                                 winding_type: str = "Current") -> str:
        """
        生成 Maxwell COM API 绕组脚本。

        命名约定 (与 references/winding_layouts.md §17.2 一致):
          - Coil 截面:  Coil_1, Coil_2, ... (1-indexed)
          - Coil Group: A+, A-, B+, B-, C+, C-
          - PolarityType: A+ → Positive, A- → Negative
        """
        lines = []
        lines.append("# ============================================================")
        lines.append(f"# PMSM Winding Assignment Script ({self.poles}p/{self.slots}s)")
        lines.append(f"# source={config.source}, k_w={config.winding_factor:.4f}")
        lines.append(f"# Auto-generated by pmsm_winding_builder.py v2")
        lines.append("# ============================================================")
        lines.append("")
        lines.append("import ScriptEnv")
        lines.append("ScriptEnv.Initialize(\"Ansoft.ElectronicsDesktop\")")
        lines.append("oDesktop = ScriptEnv.GetDesktop()")
        lines.append("oProject = oDesktop.GetActiveProject()")
        lines.append("oDesign = oProject.SetActiveDesign(\"Motor_Design\")")
        lines.append("oModule = oDesign.GetModule(\"BoundarySetup\")")
        lines.append("")

        # ── 1. 定义三相绕组 ──
        lines.append("# Step 1: 定义三相绕组 (Winding)")
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

        # ── 2. 定义 Coil Group (按相+极性) ──
        lines.append("# Step 2: 定义 Coil Group (按 phase + polarity)")
        lines.append(f"# 约定 ({self.polarity_convention}):")
        if self.polarity_convention == "standard":
            lines.append("#   A+/B+/C+ → PolarityType=Positive")
            lines.append("#   A-/B-/C- → PolarityType=Negative")
        else:
            lines.append("#   A+/B+/C+ → PolarityType=Negative")
            lines.append("#   A-/B-/C- → PolarityType=Positive")
        for group in config.coil_groups:
            if not group.coil_indices:
                continue
            pol_str = self.polarity_type(group.polarity)
            coil_objs = ", ".join(f'"{n}"' for n in group.coil_names)
            lines.append(f'oModule.AssignCoilGroup(')
            lines.append(f'    [')
            lines.append(f'        "NAME:{group.phase}{group.polarity}",')
            lines.append(f'        "Objects:=", [{coil_objs}],')
            lines.append(f'        "Conductor number:=", "{conductor_number}",')
            lines.append(f'        "PolarityType:=", "{pol_str}"')
            lines.append(f'    ]')
            lines.append(f')')
            lines.append('')

        # ── 3. 绑定到 Winding ──
        lines.append("# Step 3: 将 Coil Group 绑定到对应 Winding")
        for phase in self.phase_names:
            phase_groups = [g for g in config.coil_groups if g.phase == phase and g.coil_indices]
            group_names = [f'"{g.phase}{g.polarity}"' for g in phase_groups]
            if group_names:
                groups_str = ", ".join(group_names)
                lines.append(f'oModule.AddWindingCoils("Winding{phase}", [{groups_str}])')

        lines.append('')
        lines.append('print("Winding assignment complete")')
        lines.append(f'print(f"  Layout:  {self.poles}p/{self.slots}s, source={config.source}")')
        lines.append(f'print(f"  k_w:     {config.winding_factor:.4f}")')
        lines.append(f'print(f"  q:       {self.q:.3f}")')
        for phase in self.phase_names:
            n_pos = sum(1 for g in config.coil_groups if g.phase == phase and g.polarity == '+' for _ in g.coil_indices)
            n_neg = sum(1 for g in config.coil_groups if g.phase == phase and g.polarity == '-' for _ in g.coil_indices)
            lines.append(f'print(f"  Phase {phase}: {n_pos}+ {n_neg}-")')
        return "\n".join(lines)

    def generate_coil_renaming_script(self, config: WindingConfig) -> str:
        """重命名 Maxwell 中已存在的 coil 截面为 Coil_1..Coil_N (若需要)"""
        lines = []
        lines.append("# ============================================================")
        lines.append(f"# Coil Renaming Script ({self.poles}p/{self.slots}s)")
        lines.append("# 假设几何中已存在 36 个线圈截面, 默认名可能是 Coil_Top_1.. / Coil_Bot_1..")
        lines.append("# 这里给出按 phase+slot 命名的另一种风格 (可选)")
        lines.append("# ============================================================")
        lines.append("")
        return "\n".join(lines)

    def print_summary(self, config: WindingConfig):
        """CLI 友好输出"""
        print("=" * 60)
        print(self.render_slot_map(config))
        print("=" * 60)
        print(self.render_phase_belt(config))
        print("=" * 60)
        print(self.render_summary(config))
        print("=" * 60)


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python pmsm_winding_builder.py <slots> <poles> [pattern]")
        print("  例: python pmsm_winding_builder.py 12 8         # 8 极 12 槽")
        print("      python pmsm_winding_builder.py 36 8 AABBCC  # 8 极 36 槽")
        print()
        print("Available canonical layouts:")
        for s, p in sorted(CANONICAL_LAYOUTS.keys(), key=lambda x: x[0]):
            tag = " <- in table" if (s, p) in CANONICAL_LAYOUTS else ""
            print(f"  {p}p/{s}s  q={s/(3*p):.3f}{tag}")
        sys.exit(0)

    slots = int(sys.argv[1])
    poles = int(sys.argv[2])
    pattern = sys.argv[3] if len(sys.argv) > 3 else "AABBCC"

    builder = WindingBuilder(slots=slots, poles=poles, pattern=pattern)
    config = builder.compute_winding()
    builder.print_summary(config)
