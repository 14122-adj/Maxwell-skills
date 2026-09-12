#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winding_layout.py — 独立绕组位置速查工具

用途: AI 或用户接到"X 极 Y 槽电机"任务时, 第一动作是跑这个工具,
     把输出直接贴进回答, 而非靠直觉或算法推断。

用法:
    python winding_layout.py 12 8              # 8 极 12 槽 (8p12s)
    python winding_layout.py 36 8 --list       # 列表模式 (槽-相表)
    python winding_layout.py 36 8 --maxwell     # 输出 Maxwell 脚本
    python winding_layout.py 36 8 --md          # 输出 Markdown 格式 (适合贴 SKILL.md)
    python winding_layout.py --all             # 列出所有 canonical 组合
    python winding_layout.py --compare 8 12 8 36   # 对比两个极槽配合

与 pmsm_winding_builder.py 共享 CANONICAL_LAYOUTS 真值表, 数据源唯一。
"""
import sys
import io

# Support both invocation styles:
#   1. `python scripts/winding_layout.py 12 8 --list`    (script mode)
#   2. `python -m scripts.winding_layout 12 8 --list`   (package mode, after `pip install -e .`)
try:
    from pmsm_winding_builder import WindingBuilder, CANONICAL_LAYOUTS   # type: ignore
except ImportError:
    from scripts.pmsm_winding_builder import WindingBuilder, CANONICAL_LAYOUTS


def render_md(slots, poles, layer="double", pattern="AABBCC"):
    """Markdown 格式 (适合贴入 SKILL.md / 报告)"""
    b = WindingBuilder(slots=slots, poles=poles, pattern=pattern)
    c = b.compute_winding()
    out = []
    out.append(f"## {poles}p/{slots}s {b.winding_type.value} (q={b.q:.3f}, k_w={c.winding_factor:.3f})")
    out.append("")
    out.append("```")
    out.append(b.render_slot_map(c))
    out.append("```")
    out.append("")
    out.append("```")
    out.append(b.render_phase_belt(c))
    out.append("```")
    out.append("")
    out.append("```")
    out.append(b.render_summary(c))
    out.append("```")
    return "\n".join(out)


def render_list(slots, poles, pattern="AABBCC"):
    """简洁列表 (AI 贴答案最快)"""
    b = WindingBuilder(slots=slots, poles=poles, pattern=pattern)
    c = b.compute_winding()
    out = []
    out.append(f"# {poles}p/{slots}s — source={c.source}")
    out.append("")
    # 表格形式: slot | phase | coil
    out.append("| Slot | Phase+Pol | Coil |")
    out.append("|------|-----------|------|")
    for i, (p, pol) in enumerate(c.slot_map, 1):
        out.append(f"| {i} | {p}{pol} | Coil_{i} |")
    return "\n".join(out)


def render_maxwell(slots, poles, conductors=40, pattern="AABBCC", convention="standard"):
    """Maxwell 脚本片段"""
    b = WindingBuilder(slots=slots, poles=poles, pattern=pattern, polarity_convention=convention)
    c = b.compute_winding()
    return b.generate_maxwell_script(c, conductor_number=conductors)


def render_all():
    """列出所有 canonical 组合"""
    out = ["# Available Canonical Winding Layouts", ""]
    out.append(f"共 {len(CANONICAL_LAYOUTS)} 种, 按槽数排序:")
    out.append("")
    out.append("| Poles | Slots | q | Type |")
    out.append("|-------|-------|---|------|")
    for slots, poles in sorted(CANONICAL_LAYOUTS.keys(), key=lambda x: (x[0], x[1])):
        q = slots / (3 * poles)
        if q < 1:
            t = "concentrated"
        elif q == int(q):
            t = "distributed"
        else:
            t = "fractional"
        out.append(f"| {poles}p | {slots} | {q:.3f} | {t} |")
    out.append("")
    out.append(f"使用: python {sys.argv[0]} <slots> <poles>")
    return "\n".join(out)


def render_compare(s1, p1, s2, p2):
    """对比两个极槽配合"""
    out = ["# Winding Layout Comparison", ""]
    for tag, slots, poles in [("Layout A", s1, p1), ("Layout B", s2, p2)]:
        b = WindingBuilder(slots=slots, poles=poles)
        c = b.compute_winding()
        out.append(f"## {tag}: {poles}p/{slots}s")
        out.append("```")
        out.append(b.render_slot_map(c))
        out.append("```")
        out.append("")
    return "\n".join(out)


def main():
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--all" in args:
        print(render_all())
        return

    if "--compare" in args:
        idx = args.index("--compare")
        s1, p1, s2, p2 = int(args[idx+1]), int(args[idx+2]), int(args[idx+3]), int(args[idx+4])
        print(render_compare(s1, p1, s2, p2))
        return

    # 默认: slots poles
    slots = int(args[0])
    poles = int(args[1])
    pattern = "AABBCC"
    convention = "standard"
    mode = "list"
    conductors = 40

    for i, a in enumerate(args):
        if a == "--pattern" and i+1 < len(args):
            pattern = args[i+1]
        if a == "--convention" and i+1 < len(args):
            convention = args[i+1]
        if a == "--list": mode = "list"
        if a == "--md": mode = "md"
        if a == "--maxwell": mode = "maxwell"
        if a == "--conductors" and i+1 < len(args):
            conductors = int(args[i+1])

    if mode == "list":
        print(render_list(slots, poles, pattern))
    elif mode == "md":
        print(render_md(slots, poles, pattern=pattern))
    elif mode == "maxwell":
        print(render_maxwell(slots, poles, conductors, pattern, convention))


if __name__ == "__main__":
    main()
