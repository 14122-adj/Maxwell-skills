#!/usr/bin/env python3
"""
ANSYS Maxwell 电机自动化建模 - 主入口
支持多槽型/多永磁拓扑切换的一键建模
支持自定义参数输入

使用方法：
    python main.py --preset 8p36s_tutorial
    python main.py --params "slots=36 poles=8 stator_od=210"
    python main.py --json '{"slots":36,"poles":8,"stator_od":210}'
    python main.py --csv params.csv
"""

import sys
import os
import argparse
import json
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor_config import MotorConfig, SlotType, PMTopology, MotorType, create_motor_from_input
from pmsm_winding_builder import WindingBuilder, LayerType


def format_mm(value: float) -> str:
    """把 mm 尺寸格式化成 AEDT 能吃的字符串（G3）。

    整数值去掉多余的 ``.0``：160.0 → ``"160mm"``（与实机脚本
    ``m4_build_solve.py`` 的 ``MODEL_DEPTH = "160mm"`` 口径一致），
    非整数保留一位小数：142.5 → ``"142.5mm"``。
    """
    value = float(value)
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}mm"
    return f"{value:g}mm"


class MotorModelBuilder:
    """电机模型自动化建模器"""

    def __init__(self, config: MotorConfig):
        self.config = config
        self.scripts = {}

    def validate(self):
        c = self.config
        issues = c.validate()

        errors = [i for i in issues if i.startswith("ERROR")]
        warnings = [i for i in issues if i.startswith("WARNING")]

        if errors:
            for e in errors:
                print(e)
            return False

        for w in warnings:
            print(w)

        print("[OK] 参数校验通过")
        return True

    def generate_all_scripts(self):
        """生成全部Maxwell脚本"""
        c = self.config
        pole_pitch = 360.0 / c.slots
        pm_pitch = 360.0 / c.poles
        freq = c.pole_pairs * c.rated_speed_rpm / 60.0

        self.scripts["setup"] = self._gen_setup()
        self.scripts["materials"] = self._gen_materials()
        self.scripts["geometry"] = self._gen_geometry()
        self.scripts["winding"] = self._gen_winding()
        self.scripts["boundary"] = self._gen_boundary(freq)
        self.scripts["mesh"] = self._gen_mesh()
        self.scripts["solver"] = self._gen_solver(freq)

        return self.scripts

    def _gen_setup(self):
        c = self.config
        if c.stack_length is None or float(c.stack_length) <= 0:
            raise ValueError(
                f"叠片长度必须为正实数才能生成 ModelDepth（当前 {c.stack_length!r}）；"
                "请先修正 stack_length，否则 2D 求解会按默认 1 mm 深度算"
            )
        depth = format_mm(c.stack_length)
        return f'''#!/usr/bin/env python3
"""Step 1: 项目设置 — 修复 NewProject 弹"是否保存"对话框的问题"""
import ScriptEnv
import time

ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()

# ── 修复:避免 AEDT 启动后弹"最近文件/Home"对话框卡死脚本 ──
#  1. 等 AEDT 启动稳定 (load screen/许可/启动画面)
time.sleep(3)

#  2. 主动关掉任何已打开的项目,避免后续 NewProject 触发"是否保存"弹窗
try:
    active = oDesktop.GetActiveProject()
    if active is not None:
        try:
            # ClearSavedFlag 让 AEDT 认为当前项目已保存,丢弃未保存修改
            active.ClearSavedFlag()
        except Exception:
            pass
        try:
            oDesktop.CloseProject(active.GetName())
        except Exception:
            pass
except Exception:
    # 无激活项目/启动尚未就绪 — 忽略,直接 NewProject
    pass

#  3. 关闭 Home / Recent Files 弹窗 (AEDT 2021+ 启动时常弹)
try:
    # 顺序点掉主窗口的 child dialog:典型 Home Screen 的标题是 "Home"
    for w in list(oDesktop.GetWindowNames()):
        title = (oDesktop.GetWindowTitle(w) or "").lower()
        if "home" in title or "recent" in title or "welcome" in title:
            try:
                oDesktop.CloseWindow(w)
            except Exception:
                pass
except Exception:
    pass

#  4. 现在安全新建项目 (overwrite=True 兜底,避免再有"覆盖?"弹窗)
oProject = oDesktop.NewProject()
oProject.InsertDesign("Maxwell 2D", "Motor_Design", "Transient", "")
oDesign = oProject.SetActiveDesign("Motor_Design")
# ── G3：2D 求解必须显式写叠长 ──
#  Maxwell 2D 的默认 ModelDepth 是 1 mm（不是 0），若这里不写，
#  转矩/反电势/铁耗/铜耗全部按 1 mm 深度算，物理量整体缩小约 160 倍，
#  而求解器不会报任何错（“模型自洽、物理错量级”的静默错误）。
#  实测依据：m4_build_solve.py 写入 ModelDepth:="160mm" 后，
#  空载 BEMF 118.88 V(rms)、负载 T_avg 22.33 N·m，与解析值同量级。
oDesign.SetDesignSettings(
    ["NAME:DesignSettingsData",
     "ModelDepth:=", "{depth}",
     "PreserveTransientSolution:=", False,
     "ComputeTransientInductance:=", True])
print("Setup done: {c.slots} slots, {c.poles} poles, {c.slot_type.value}, {c.pm_topology.value}, ModelDepth={depth}")
'''

    def _gen_materials(self):
        c = self.config
        freq = c.pole_pairs * c.rated_speed_rpm / 60.0
        # ── G4 真机修复·材料：铁芯材料（此前模板从未定义、也从未绑定）──
        # 2026-11-13：模板路径此前把 StatorOuter / RotorOuter 建成 `vacuum`，
        # 磁路磁阻全部落在"空气"上，空载 BEMF 只剩解析值的零头，且求解器不报错
        # （又一个"模型自洽、物理错量级"的静默错误）。
        # 口径与 m4_build_solve.py 手写工程一致：线性化 mu_r=1000，sigma=2.0e6 S/m，
        # rho=7650 kg/m³ —— 保证两条路径的差异不来自材料模型。
        steel_names = []
        for nm in (c.stator_material, c.rotor_material):
            if nm not in steel_names:
                steel_names.append(nm)
        steel_block = "\n".join([
            "# 铁芯材料（G4：模板此前从未定义/绑定，定转子默认是 vacuum）",
            f"STEEL_MATS = {steel_names!r}",
            "for _m in STEEL_MATS:",
            "    oDefinitionManager.EditMaterial(",
            '        _m, ["NAME:" + _m, "CoordinateSystemType:=", "Cartesian",',
            '             "BulkOrSurfaceType:=", 1,',
            '             ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal",',
            '                                               "Structural"]],',
            '             "permittivity:=", "1", "permeability:=", "1000",',
            '             "conductivity:=", "2000000", "dielectric_loss_tangent:=", "0",',
            '             "magnetic_loss_tangent:=", "0", "mass_density:=", "7650",',
            '             "youngs_modulus:=", "200000000000"])',
        ])
        return f'''#!/usr/bin/env python3
"""Step 2: 自定义材料定义（N/S极磁钢 + 铁芯）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDefinitionManager = oProject.GetDefinitionManager()

# N极磁钢（磁化方向径向向外）
oDefinitionManager.EditMaterial("{c.pm_material_n}",
    [
        "NAME:{c.pm_material_n}",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "{c.pm_conductivity}",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-{c.pm_hc_kam * 1000}A_per_meter",
            "DirComp1:=", "1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "{c.pm_mass_density}",
        "youngs_modulus:=", "147000000000",
    ])

# S极磁钢（磁化方向径向向内）
oDefinitionManager.EditMaterial("{c.pm_material_s}",
    [
        "NAME:{c.pm_material_s}",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "{c.pm_conductivity}",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-{c.pm_hc_kam * 1000}A_per_meter",
            "DirComp1:=", "-1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "{c.pm_mass_density}",
        "youngs_modulus:=", "147000000000",
    ])

print("Materials defined: {c.pm_material_n}, {c.pm_material_s}")
{steel_block}
'''

    def _gen_geometry(self):
        """生成几何建模脚本"""
        c = self.config
        pole_pitch = 360.0 / c.slots
        pm_pitch = 360.0 / c.poles

        # ── 槽克隆体命名（G3b 真机修复·几何 3）──
        # `DuplicateAroundAxis` 的产物是 `Slot_1_1..Slot_1_{N-1}`（原对象名 + 序号），
        # **不是** `Slot_2..Slot_N`。按后者去 Subtract 会报 Object not found，
        # 槽一个都减不掉，定子齿形根本不存在。生成物里用运行期列表拼名，
        # 与 `maxwell_model/build_25Nm_SPMSM.py` 的 `"Slot_1_" + str(i)` 完全一致。

        # ── 槽型绘制块：按 slot_type 生成槽轮廓 IronPython 代码段 ──
        # fixed: 旧版只有梨形槽模板; 现支持 rectangular / pear / trapezoidal / round,
        # 线圈区域参数随槽型推导, 保证线圈始终位于槽内。
        #
        # ── G4 真机修复·几何 4：槽口必须比定子内径再深 0.2 mm ──
        # 槽口第一边与内孔圆弧**严格相切**时，Acis 会生成退化线段并报
        # `Non-manifold vertices found for "StatorOuter"`（M2/M3 的 36 条 intersect
        # 报错之一）。x0 取 r_bore - 0.2，其余肩部/槽底仍按 r_bore 起算，
        # 因此槽深不变、只有开口多切进气隙 0.2 mm（m4_build_solve.py 同口径）。
        r_bore = c.stator_id / 2.0
        x0 = r_bore - 0.2
        _bs0, _hs0 = c.slot_Bs0, c.slot_Hs0
        _slot_pts = None      # 供线圈内缩复用的槽轮廓（mm）；round 槽为 None
        if c.slot_type.value == "pear":
            x1 = x0 + c.slot_Hs0
            x2 = x0 + c.slot_Hs0 + c.slot_Hs1
            x3 = x0 + c.slot_Hs0 + c.slot_Hs1 + c.slot_Rs
            slot_block = "\n".join([
                f"# Slot creation (pear type)",
                f"r_bore = {r_bore}", f"x0 = r_bore - 0.2",
                f"bs0 = {c.slot_Bs0}", f"bs1 = {c.slot_Bs1}", f"bs2 = {c.slot_Bs2}",
                f"hs0 = {c.slot_Hs0}", f"hs1 = {c.slot_Hs1}", f"hs2 = {c.slot_Hs2}", f"rs = {c.slot_Rs}",
                f"x1 = r_bore + hs0", f"x2 = r_bore + hs0 + hs1",
                f"x3 = r_bore + hs0 + hs1 + rs",
                "oEditor.CreatePolyline(",
                '    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,',
                '     ["NAME:PolylinePoints",',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-bs0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(-bs1/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(-bs2/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x3) + "mm", "Y:=", "0mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(bs2/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(bs1/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(bs0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-bs0/2) + "mm", "Z:=", "0mm"]],',
                '     ["NAME:PolylineSegments",',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Arc", "StartIndex:=", 3, "NoOfPoints:=", 3],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 7, "NoOfPoints:=", 2]]],',
                '    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",',
                '     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '     "MaterialValue:=", \'"vacuum"\', "SolveInside:=", True])',
            ])
            _slot_pts = [(x0, -c.slot_Bs0 / 2.0), (r_bore + c.slot_Hs0, -c.slot_Bs1 / 2.0),
                         (r_bore + c.slot_Hs0 + c.slot_Hs1, -c.slot_Bs2 / 2.0),
                         (r_bore + c.slot_Hs0 + c.slot_Hs1 + c.slot_Rs, 0.0),
                         (r_bore + c.slot_Hs0 + c.slot_Hs1, c.slot_Bs2 / 2.0),
                         (r_bore + c.slot_Hs0, c.slot_Bs1 / 2.0),
                         (x0, c.slot_Bs0 / 2.0)]
        elif c.slot_type.value == "rectangular":
            # 槽口(窄) + 槽体(宽), 直角台阶, 单个 6 点 Polyline 闭合
            slot_block = "\n".join([
                f"# Slot creation (rectangular type)",
                f"r_bore = {r_bore}",
                f"x0 = r_bore - 0.2", f"x1 = r_bore + {c.slot_Hs0}",
                f"x2 = r_bore + {c.slot_Hs2}",
                f"b0 = {_bs0}", f"b2 = {c.slot_Bs2}",
                "oEditor.CreatePolyline(",
                '    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,',
                '     ["NAME:PolylinePoints",',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(-b2/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x2) + "mm", "Y:=", str(b2/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"]],',
                '     ["NAME:PolylineSegments",',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 3, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 4, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 5, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 6, "NoOfPoints:=", 2]]],',
                '    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",',
                '     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '     "MaterialValue:=", \'"vacuum"\', "SolveInside:=", True])',
            ])
            _slot_pts = [(x0, -_bs0 / 2.0), (r_bore + c.slot_Hs0, -_bs0 / 2.0),
                         (r_bore + c.slot_Hs2, -c.slot_Bs2 / 2.0),
                         (r_bore + c.slot_Hs2, c.slot_Bs2 / 2.0),
                         (r_bore + c.slot_Hs0, _bs0 / 2.0), (x0, _bs0 / 2.0)]
        elif c.slot_type.value == "trapezoidal":
            # 开口窄 → 槽底宽, 直线斜坡, 4 点 Polyline
            slot_block = "\n".join([
                f"# Slot creation (trapezoidal type)",
                f"r_bore = {r_bore}", f"x0 = r_bore - 0.2",
                f"x1 = r_bore + {c.slot_Hs0} + {c.slot_Hs1}",
                f"b0 = {_bs0}", f"b1 = {c.slot_Bs1}",
                "oEditor.CreatePolyline(",
                '    ["NAME:PolylineParameters", "IsPolylineCovered:=", True, "IsPolylineClosed:=", True,',
                '     ["NAME:PolylinePoints",',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(-b1/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x1) + "mm", "Y:=", str(b1/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(b0/2) + "mm", "Z:=", "0mm"],',
                f'      ["NAME:PLPoint", "X:=", str(x0) + "mm", "Y:=", str(-b0/2) + "mm", "Z:=", "0mm"]],',
                '     ["NAME:PolylineSegments",',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 1, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 2, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 3, "NoOfPoints:=", 2],',
                '      ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 4, "NoOfPoints:=", 2]]],',
                '    ["NAME:Attributes", "Name:=", "Slot_1", "Flags:=", "", "Color:=", "(0 200 0)",',
                '     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '     "MaterialValue:=", \'"vacuum"\', "SolveInside:=", True])',
            ])
            _slot_pts = [(x0, -_bs0 / 2.0), (r_bore + c.slot_Hs0 + c.slot_Hs1, -c.slot_Bs1 / 2.0),
                         (r_bore + c.slot_Hs0 + c.slot_Hs1, c.slot_Bs1 / 2.0), (x0, _bs0 / 2.0)]
        else:  # round
            # 槽口矩形 + 圆(直径 Bs2), Unite 合并
            slot_block = "\n".join([
                f"# Slot creation (round type)",
                f"r_bore = {r_bore}", f"x0 = r_bore - 0.2",
                f"c_center = r_bore + {c.slot_Hs2} / 2.0",
                f"cr = {c.slot_Bs2} / 2.0",
                f"open_w = max(0.01, c_center - cr - x0)",
                "oEditor.CreateRectangle(",
                f'    ["NAME:RectangleParameters", "IsCovered:=", True,',
                f'     "XStart:=", str(x0) + "mm", "YStart:=", str(-{_bs0}/2) + "mm", "ZStart:=", "0mm",',
                f'     "Width:=", str(open_w) + "mm", "Height:=", "{_bs0}mm", "WhichAxis:=", "Z"],',
                '    ["NAME:Attributes", "Name:=", "Slot_1_open", "Flags:=", "", "Color:=", "(0 200 0)",',
                '     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '     "MaterialValue:=", \'"vacuum"\', "SolveInside:=", True])',
                "oEditor.CreateCircle(",
                f'    ["NAME:CircleParameters", "XCenter:=", str(c_center) + "mm", "YCenter:=", "0mm",',
                f'     "ZCenter:=", "0mm", "Radius:=", str(cr) + "mm", "WhichAxis:=", "Z"],',
                '    ["NAME:Attributes", "Name:=", "Slot_1_circle", "Flags:=", "", "Color:=", "(0 200 0)",',
                '     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '     "MaterialValue:=", \'"vacuum"\', "SolveInside:=", True])',
                'oEditor.Unite(',
                '    ["NAME:Selections", "Selections:=", "Slot_1_open,Slot_1_circle"],',
                '    ["NAME:UniteParameters", "KeepOriginals:=", False])',
                'oEditor.ChangeProperty(',
                '    ["NAME:AllTabs",',
                '     ["NAME:Geometry3DAttributeTab",',
                '      ["NAME:PropServers", "Slot_1_open"],',
                '      ["NAME:ChangedProps", ["NAME:Name", "Value:=", "Slot_1"]]]])',
            ])
            _slot_pts = None   # round 槽由矩形+圆 Unite 得到，无单一多边形轮廓

        # ── 线圈截面（G4 真机修复·几何 5：按槽形内缩，不再用外接矩形）──
        # 2026-11-13：旧版把 `13.2 × 5.7` 的矩形放在槽中线上；本机槽在 r=49.65 处
        # 只有 3.2 mm 宽，矩形两侧直接穿出槽壁 ⇒ `StatorOuter and Coil_x intersect`
        # （M2/M3 阶段 `Analyze` 被 36 条 intersect 判死的主因之一）。
        # 正确做法：取槽轮廓多边形，按 0.88 向形心收缩（凸多边形收缩必内含），
        # 与 m4_build_solve.py 的 COIL_PTS 同一口径。
        _slot_angle = 360.0 / c.slots
        if _slot_pts:
            _pcx = sum(p[0] for p in _slot_pts) / len(_slot_pts)
            _pcy = sum(p[1] for p in _slot_pts) / len(_slot_pts)
            _coil_pts = [(_pcx + 0.88 * (x - _pcx), _pcy + 0.88 * (y - _pcy))
                         for (x, y) in _slot_pts]
            _pts_literal = "["
            _pts_literal += ", ".join("(%.6f, %.6f)" % (x, y) for (x, y) in _coil_pts)
            _pts_literal += "]"
            coil_block = "\n".join([
                "",
                "# ── 线圈截面（铜，槽轮廓 0.88 内缩；命名 Coil_1..Coil_N 与绕组脚本对齐）──",
                "#    矩形截面在高槽满率槽里必然穿出槽壁，线圈必须由槽形收缩得到。",
                f"coil_pts = {_pts_literal}",
                f"coil_slot_angle = {_slot_angle:.6f}",
                f"for k in range({c.slots}):",
                "    angle = k * coil_slot_angle",
                '    cname = "Coil_" + str(k + 1)',
                "    _plpts = []",
                "    for (_x, _y) in coil_pts + [coil_pts[0]]:",
                '        _plpts.append(["NAME:PLPoint", "X:=", str(_x) + "mm",',
                '                       "Y:=", str(_y) + "mm", "Z:=", "0mm"])',
                '    _segs = ["NAME:PolylineSegments"]',
                "    for _i in range(len(coil_pts)):",
                '        _segs.append(["NAME:PLSegment", "SegmentType:=", "Line",',
                '                      "StartIndex:=", _i, "NoOfPoints:=", 2])',
                "    oEditor.CreatePolyline(",
                '        ["NAME:PolylineParameters", "IsPolylineCovered:=", True,',
                '         "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + _plpts, _segs],',
                '        ["NAME:Attributes", "Name:=", cname, "Flags:=", "", "Color:=", "(255 128 0)",',
                '         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '         "MaterialValue:=", \'"copper"\', "SolveInside:=", True])',
                "    if angle > 0:",
                "        oEditor.Rotate(",
                '            ["NAME:Selections", "Selections:=", cname],',
                '            ["NAME:RotateParameters", "RotateAxis:=", "Z",',
                '             "RotateAngle:=", str(angle) + "deg",',
                '             "DuplicateObjects:=", False])',
            ])
        else:  # round：槽体是圆，线圈取同圆心 0.88 倍半径的圆，必在槽内
            coil_block = "\n".join([
                "",
                "# ── 线圈截面（圆槽：同圆心 0.88 倍半径，必在槽内）──",
                f"coil_slot_angle = {_slot_angle:.6f}",
                f"for k in range({c.slots}):",
                "    angle = k * coil_slot_angle",
                '    cname = "Coil_" + str(k + 1)',
                "    oEditor.CreateCircle(",
                '        ["NAME:CircleParameters", "XCenter:=", str(c_center) + "mm",',
                '         "YCenter:=", "0mm", "ZCenter:=", "0mm",',
                '         "Radius:=", str(cr * 0.88) + "mm", "WhichAxis:=", "Z"],',
                '        ["NAME:Attributes", "Name:=", cname, "Flags:=", "", "Color:=", "(255 128 0)",',
                '         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",',
                '         "MaterialValue:=", \'"copper"\', "SolveInside:=", True])',
                "    if angle > 0:",
                "        oEditor.Rotate(",
                '            ["NAME:Selections", "Selections:=", cname],',
                '            ["NAME:RotateParameters", "RotateAxis:=", "Z",',
                '             "RotateAngle:=", str(angle) + "deg",',
                '             "DuplicateObjects:=", False])',
            ])

        # ── G4 几何自洽参数（与 m4_build_solve.py 的冻结口径逐项对齐）──
        r_pm_out = c.rotor_od / 2.0
        r_pm_in = r_pm_out - c.pm_thickness
        r_rotor = r_pm_in + 0.03          # 磁钢内嵌 30 µm
        r_band = (c.rotor_od + c.stator_id) / 4.0
        _nseg_pm = 24
        _half_pm = math.radians(c.pm_pole_arc * pm_pitch) / 2.0
        _pm_pts = []
        for _k in range(_nseg_pm + 1):
            _a = -_half_pm + 2.0 * _half_pm * _k / _nseg_pm
            _pm_pts.append((r_pm_out * math.cos(_a), r_pm_out * math.sin(_a)))
        for _k in range(_nseg_pm, -1, -1):
            _a = -_half_pm + 2.0 * _half_pm * _k / _nseg_pm
            _pm_pts.append((r_pm_in * math.cos(_a), r_pm_in * math.sin(_a)))
        _pm_literal = "[" + ", ".join("(%.6f, %.6f)" % p for p in _pm_pts) + "]"
        _pm_names = ", ".join("PM_%d" % (i + 1) for i in range(c.poles))
        _coil_names = ", ".join("Coil_%d" % (i + 1) for i in range(c.slots))

        s = f'''#!/usr/bin/env python3
"""Step 3: 几何建模"""
import ScriptEnv, math
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
# ── G3b 真机修复·几何 1：单位设置的键名是 Units，不是 Length ──
#   写 "Length:=" 会被 AEDT 判为未知键（rc=1, "Unknown key"），脚本在第一步就死。
oEditor.SetModelUnits(["NAME:UnitsSettings", "Units:=", "mm"])

# Region（外部边界）
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_od/2+20}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Region", "Flags:=", "", "Color:=", "(143 175 143)",
     "Transparency:=", 1, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

# ── G4 真机修复·边界 9：零矢势边界必须在 Region 还是「单条边的整圆」时赋 ──
#   2026-11-13：Region 一旦被 Subtract 切出孔洞（定子/线圈/Band），
#   `GetEdgeIDsFromObject("Region")` 会把外圆**和所有孔边**一起返回，
#   `VectorPotential=0` 就被强行加到材料界面上 ⇒ 磁通被人为短路。
#   求解器不报任何错，BEMF 却掉一大截 —— 又一个静默错误。
#   正确顺序（= m4_build_solve.py 跑出 401 点解的顺序）：先赋边界，再切 Region。
_region_edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]
oDesign.GetModule("BoundarySetup").AssignVectorPotential(
    ["NAME:VectorPotential1", "Edges:=", _region_edges, "Value:=", "0",
     "CoordinateSystem:=", ""])
print("Boundary: VectorPotential=0 on pristine Region (%d edge)" % len(_region_edges))

# Stator outer
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_od/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.stator_material}"', "SolveInside:=", True])

# Stator inner
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.stator_id/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "StatorInner", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter", "Tool Parts:=", "StatorInner"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

{slot_block}

# Duplicate slots
# ── G3b 真机修复·几何 2：DuplicateAroundAxis 必须带第 3 个参数 ──
#   缺 ["NAME:Options", ...] 时报 "expects at least 3 arguments"，克隆不执行。
oEditor.DuplicateAroundAxis(
    ["NAME:Selections", "Selections:=", "Slot_1", "NewPartsModelFlag:=", "Model"],
    ["NAME:DuplicateAroundAxisParameters", "CreateNewObjects:=", True,
     "WhichAxis:=", "Z", "AngleStr:=", "{pole_pitch}deg", "Numclones:=", "{c.slots}"],
    ["NAME:Options", "DuplicateAssignments:=", False])

# Subtract slots from stator
# ── G3b 真机修复·几何 3：克隆体实名 Slot_1_1..Slot_1_{c.slots-1} ──
slot_names = ["Slot_1"] + ["Slot_1_" + str(i) for i in range(1, {c.slots})]
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "StatorOuter",
     "Tool Parts:=", ", ".join(slot_names)],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# Rotor outer
# ── G4 真机修复·几何 6：转子半径 = 磁钢内半径 + 0.03 mm，磁钢"嵌"进转子 ──
#   磁钢改环形扇区后，转子盘必须小于磁钢外弧（否则转子自己就顶到定子内径），
#   但又要与磁钢内弧重叠 30 µm，让布尔开出一个闭合浅坑：界面严格互补、
#   无相切顶点（相切会触发 `Non-manifold vertices`，M2/M3 的死因之一）。
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{r_rotor:.6f}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "RotorOuter", "Flags:=", "", "Color:=", "(132 132 193)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"{c.rotor_material}"', "SolveInside:=", True])

# Shaft
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", "{c.rotor_id/2}mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Shaft", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])

oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "Shaft"],
    ["NAME:SubtractParameters", "KeepOriginals:=", False])

# PMs (N/S alternating)
# ── G4 真机修复·几何 7：磁钢是**环形扇区**，不是平板弦 ──
#   旧版用 `CreateRectangle(XStart=rotor_od/2, Width=pm_thickness)`，即把 1.95 mm 厚的
#   平板放在转子外径**之外** ⇒ 径向跨 45.825..47.775 mm，而定子内径 46.5 mm，
#   磁钢直接插进定子铁芯 1.275 mm（`StatorOuter and PM_x intersect`）。
#   0.675 mm 气隙里平板弦几何上不可行。现在内外弧各离散 {_nseg_pm} 段
#   （弧矢 ~4.5 µm），内弧 {r_pm_in:.4f} / 外弧 {r_pm_out:.4f}，从根上消除相切与穿插。
pm_pitch = {pm_pitch}
pm_pts = {_pm_literal}
for i in range({c.poles}):
    angle = i * pm_pitch
    if i % 2 == 0:
        mat = "{c.pm_material_n}"
        color = "(255 0 0)"
    else:
        mat = "{c.pm_material_s}"
        color = "(0 0 255)"
    pname = "PM_" + str(i + 1)

    _pm_plpts = []
    for (_x, _y) in pm_pts + [pm_pts[0]]:
        _pm_plpts.append(["NAME:PLPoint", "X:=", str(_x) + "mm",
                          "Y:=", str(_y) + "mm", "Z:=", "0mm"])
    _pm_segs = ["NAME:PolylineSegments"]
    for _i in range(len(pm_pts)):
        _pm_segs.append(["NAME:PLSegment", "SegmentType:=", "Line",
                         "StartIndex:=", _i, "NoOfPoints:=", 2])
    oEditor.CreatePolyline(
        ["NAME:PolylineParameters", "IsPolylineCovered:=", True,
         "IsPolylineClosed:=", True, ["NAME:PolylinePoints"] + _pm_plpts, _pm_segs],
        ["NAME:Attributes", "Name:=", pname, "Flags:=", "", "Color:=", color,
         "Transparency:=", 0, "PartCoordinateSystem:=", "Global",
         "MaterialValue:=", '"' + mat + '"', "SolveInside:=", True])

    if angle > 0:
        oEditor.Rotate(
            ["NAME:Selections", "Selections:=", pname],
            ["NAME:RotateParameters", "RotateAxis:=", "Z",
             "RotateAngle:=", str(angle) + "deg",
             "DuplicateObjects:=", False])

# 转子 − 8 磁钢（KeepOriginals=True：磁钢本体保留，只在转子上挖出浅坑）
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "RotorOuter", "Tool Parts:=", "{_pm_names}"],
    ["NAME:SubtractParameters", "KeepOriginals:=", True])

# Band（气隙中心）
#   半径取 (rotor_od + stator_id)/4 = 气隙中点 {r_band:.4f} mm：
#   磁钢外弧 {r_pm_out:.4f} 与其内切，转子盘整个落在带内 ⇒ AEDT 的
#   "objects within the band" 检查能通过（Band 内必须有运动件）。
band_r = ({c.rotor_od} + {c.stator_id}) / 4.0
oEditor.CreateCircle(
    ["NAME:CircleParameters", "XCenter:=", "0mm", "YCenter:=", "0mm",
     "ZCenter:=", "0mm", "Radius:=", str(band_r) + "mm", "WhichAxis:=", "Z"],
    ["NAME:Attributes", "Name:=", "Band", "Flags:=", "", "Color:=", "(0 255 255)",
     "Transparency:=", 0.75, "PartCoordinateSystem:=", "Global",
     "MaterialValue:=", '"vacuum"', "SolveInside:=", True])
{coil_block}

# Region 布尔分离
# ── G4 真机修复·几何 8：Region 必须与所有实体/线圈/运动带布尔分离 ──
#   旧版 Region 是一个从未参与布尔的整圆 sheet ⇒ 与定子、线圈、Band 全域重叠，
#   网格在重叠区被重复计入（M2/M3 的 36 条 intersect 中最隐蔽的一类：
#   求解器不报错，只是场解错）。这里 KeepOriginals=True 只切 Region 本身。
oEditor.Subtract(
    ["NAME:Selections", "Blank Parts:=", "Region",
     "Tool Parts:=", "StatorOuter, RotorOuter, {_pm_names}, {_coil_names}, Band"],
    ["NAME:SubtractParameters", "KeepOriginals:=", True])

print("Geometry done: {c.slots} slots, {c.poles} PMs, Band, {c.slots} coils")
'''
        return s

    def _gen_winding(self):
        """生成绕组脚本 — v4 修复: 与 canonical 真值表对齐
        + standard 极性约定 (A+→Positive, A-→Negative)

        演化史:
          v1 硬编码 A_1..A_12 / B_1..B_12 / C_1..C_12, 与 builder 算法脱节
          v2 模板用 builder.coil_groups 输出, 但 builder 算法对 8p12s 集中绕组有 bug
          v3 头部加"winding guide" + 槽位图 ASCII 示意
          v4 builder 改为 lookup-first, 数据源 = references/winding_layouts.md
             极性约定统一为 standard (A+→Positive, A-→Negative)
        """
        c = self.config
        from pmsm_winding_builder import WindingBuilder
        builder = WindingBuilder(
            slots=c.slots, poles=c.poles, phases=3,
            polarity_convention="standard",   # ★ 新约定: A+→Positive, A-→Negative
        )
        config = builder.compute_winding()

        # ── 按 builder 的 coil_groups 逐槽边渲染 AssignCoil（G3b 真机修复·绕组 4）──
        # 2026-11-12 真机实测：AEDT 2021.1 批处理下
        #   `AssignCoilGroup` 报 "expects at least 2 arguments. 1 arguments provided"
        #   （COM 签名是 (nameArg, dataArg)，单数组调用必失败）
        # ⇒ 绕组不能用「组 + AddWindingCoils」两级结构，必须一个槽边一个 `AssignCoil`，
        #   并用 `Winding:="WindingX"` 直接挂到相绕组上。这是 M4/M5 跑出 401 点解时的写法。
        # 口径：`Conductor number` 是**单个槽边**的导体数（不是线圈匝数）。
        coil_assign_blocks = []
        # 在主进程算好每相 +/- 线圈组数(供 print 报告用)
        n_pos_neg = {p: {"+": 0, "-": 0} for p in ["A", "B", "C"]}
        for group in config.coil_groups:
            if not group.coil_indices:
                continue
            pol_str = builder.polarity_type(group.polarity)   # 走 builder 的标准约定
            for cname in group.coil_names:
                slot_no = cname.rsplit("_", 1)[-1]            # "Coil_7" → "7"
                coil_assign_blocks.append(
                    f'oModule.AssignCoil(\n'
                    f'    ["NAME:{group.phase}_{slot_no}",\n'
                    f'     "Objects:=", ["{cname}"],\n'
                    f'     "Conductor number:=", "{c.conductors_per_slot}",\n'
                    f'     "PolarityType:=", "{pol_str}",\n'
                    f'     "Winding:=", "Winding{group.phase}"])\n'
                )
            n_pos_neg[group.phase][group.polarity] += 1
        coil_groups_py = "\n".join(coil_assign_blocks)
        n_A_pos, n_A_neg = n_pos_neg["A"]["+"], n_pos_neg["A"]["-"]
        n_B_pos, n_B_neg = n_pos_neg["B"]["+"], n_pos_neg["B"]["-"]
        n_C_pos, n_C_neg = n_pos_neg["C"]["+"], n_pos_neg["C"]["-"]

        # ── 相位带表(供人类/AI 阅读校对) ──
        # 输出多行 print, 每槽一行, 一目了然
        phase_belt_prints = []
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append(f'print("  绕组位置分配表 (Phase-Belt Allocation)")')
        phase_belt_prints.append(f'print("  slots={c.slots}  poles={c.poles}  q={c.slots/(c.poles/2)/3:.2f}  layers={builder.layer}")')
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append('print("  槽号  相+/极性  拓扑示意  备注")')
        # 极性星号: A+/B+/C+ → ★ (N 极下), A-/B-/C- → · (S 极下)
        for slot in range(c.slots):
            ph, pl = config.slot_map[slot]
            star = "★" if pl == '+' else "·"
            line_marker = f"[{ph}{pl}]"
            note = "上 N 极下" if pl == '+' else "下 S 极下"
            phase_belt_prints.append(
                f'print(f"  Slot_{slot+1:>2}   {ph}{pl}    {line_marker} {star}   {note}")'
            )
        phase_belt_prints.append('print("=" * 60)')
        phase_belt_prints.append('print("  说明: ★ = 电流方向 + (N 极下); · = 电流方向 - (S 极下)")')
        phase_belt_prints.append('print("  每个槽边 = 一个 Coil 对象 = 一个 AssignCoil（直接挂 Winding:=）")')
        phase_belt_prints.append('print("  同一相 +/- 的槽边共用同一个 WindingX，靠 PolarityType 定方向")')
        phase_belt_py = "\n".join(phase_belt_prints)

        return f'''#!/usr/bin/env python3
"""Step 4: 线圈组与绕组定义 — 修复 v2: 真正用 builder.compute_winding() 的输出"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("BoundarySetup")

# ── 相位带分配表(从 builder 算出, AI 友好: print 出每槽位置 + 拓扑示意) ──
# slots={c.slots}, poles={c.poles}, q={c.slots/(c.poles/2)/3:.2f}, layers={builder.layer}
# 绕组系数 kw = {config.winding_factor:.4f}
#
# 算法 (整数槽分布式 Pyrhonen 公式):
#   相 = (slot_idx * pole_pairs) // (slots // 3)  mod 3
#   极性 = '+' if (slot_idx // q) % 2 == 0 else '-'
# 集中绕组 (q=0.5): 槽电角 120°/槽 → A+B-C+A-B+C- 循环
{phase_belt_py}

# ── Step 1: 定义三相绕组 ──
for phase in ["A", "B", "C"]:
    oModule.AssignWindingGroup(
        ["NAME:Winding" + phase,
         "Type:=", "Current",
         "IsSolid:=", False,
         "Current:=", "0A",
         "Resistance:=", "0.1ohm",
         "Inductance:=", "0.001H",
         "Voltage:=", "0V",
         "ParallelBranchesNum:=", "1"])

# ── Step 2: 逐槽边 AssignCoil（每对象一个，直接挂 Winding:=）──
{coil_groups_py}

print("Winding assignment complete: {c.slots} slots, {c.poles} poles, 3 phases")
print(f"  Winding factor kw = {config.winding_factor:.4f}")
print(f"  Coil groups: A+={n_A_pos} A-={n_A_neg} B+={n_B_pos} B-={n_B_neg} C+={n_C_pos} C-={n_C_neg}")
print(f"  Layout source = {config.source}  ({'真值表 references/winding_layouts.md' if config.source=='canonical' else '⚠ fallback 算法, 请人工核对'})")
print(f"  Polarity convention = {builder.polarity_convention}  (A+→Positive, A-→Negative)")
'''

    def _gen_boundary(self, freq):
        c = self.config
        return f'''#!/usr/bin/env python3
"""Step 5: 边界条件与运动设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oEditor = oDesign.SetActiveEditor("3D Modeler")
oModule = oDesign.GetModule("BoundarySetup")

# 零矢势边界（定子外边界）
# ── G4 迁移：这段边界已移到 geometry.py，紧跟 Region 建圆之后 ──
#   原因（2026-11-13 真机分析）：本脚本在 geometry 之后运行，此时 Region 已被
#   Subtract 切出孔洞，`GetEdgeIDsFromObject("Region")` 会把外圆**和所有孔边**
#   一起返回，`VectorPotential=0` 就落到材料界面上 ⇒ 磁通被短路。
#   写法规矩本身没变（G3b：只吃 1D 实体，必须传 Edges，不能传 Region sheet），
#   只是**时机**必须早于任何布尔运算。见 geometry.py 同位置的注释。

# 运动设置
# ── G3b 真机修复·边界 2：键名是 "Init Pos:="（带空格）──
#   实测（m4_build_solve_progress.log: `OK AssignBand A Init Pos`，两轮均通过）：
#   带空格且**同时给全** Coordinate System / HasRotateLimit / NonCylindrical /
#   Consider Mechanical Transient 这几个可选键，2021.1 才按旋转带处理；
#   缺键或写成 "InitPos:=" 会被判成平动，报
#   `For 2D XY translation problem, only X or Y axis could be used`。
oDesign.GetModule("ModelSetup").AssignBand(
    ["NAME:BandData",
     "Move Type:=", "Rotate",
     "Coordinate System:=", "Global",
     "Axis:=", "Z",
     "Is Positive:=", True,
     "Init Pos:=", "0deg",
     "HasRotateLimit:=", False,
     "NonCylindrical:=", False,
     "Consider Mechanical Transient:=", False,
     "Angular Velocity:=", "{c.rated_speed_rpm}rpm",
     "Objects:=", ["Band"]])

print("Motion band set: {c.rated_speed_rpm}rpm")
'''

    def _gen_mesh(self):
        c = self.config
        pm_list = ', '.join([f'"PM_{i}"' for i in range(1, c.poles + 1)])
        return f'''#!/usr/bin/env python3
"""Step 6: 网格设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("MeshSetup")

# 气隙网格
# ── G3b 真机修复·网格 6：2021.1 没有 AssignSurfApproxOp ──
#   用 AssignLengthOp 控 Band 内最大边长即可（m4_build_solve.py 实机验证的写法）。
oModule.AssignLengthOp(
    ["NAME:Mesh_Band",
     "Objects:=", ["Band"],
     "MaxLength:=", "{c.mesh_airgap}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

# 定转子网格
oModule.AssignLengthOp(
    ["NAME:Mesh_Stator",
     "Objects:=", ["StatorOuter"],
     "MaxLength:=", "{c.mesh_teeth}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_Rotor",
     "Objects:=", ["RotorOuter"],
     "MaxLength:=", "{c.mesh_yoke}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

oModule.AssignLengthOp(
    ["NAME:Mesh_PM",
     "Objects:=", [{pm_list}],
     "MaxLength:=", "{c.mesh_pm}mm",
     "RestrictElem:=", False,
     "RestrictLength:=", True])

print("Mesh configured")
'''

    def _gen_solver(self, freq):
        c = self.config
        stop_time = max(2.0 / freq, 0.02) if freq > 0 else 0.02
        time_step = max(1.0 / (freq * 200), 5e-5) if freq > 0 else 5e-5

        stop_str = f"{stop_time:.4f}"
        step_str = f"{time_step:.6f}"

        return f'''#!/usr/bin/env python3
"""Step 7: 求解器设置"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
oProject = oDesktop.GetActiveProject()
oDesign = oProject.SetActiveDesign("Motor_Design")
oModule = oDesign.GetModule("AnalysisSetup")

oModule.InsertSetup("Transient",
    ["NAME:Setup1",
     "StopTime:=", "{stop_str}s",
     "TimeStep:=", "{step_str}s",
     "SaveFieldsType:=", "Every N Steps",
     # G4：隔步存场（N=2）与 m4_build_solve.py 的全时长口径一致 ——
     # 报表采样点仍由求解步长决定（20 ms / 5e-5 s = 401 点），存场减半只影响
     # 磁盘占用与写盘耗时，不影响转矩/磁链曲线。
     "N:=", "2",
     "UseAdaptiveTimeStep:=", False,
     "NonlinearSolverResidual:=", "0.0001",
     "SmoothBHCurve:=", False])

print("Solver configured: Transient, {stop_str}s / {step_str}s")
'''

    def export_scripts(self, output_dir):
        """导出脚本到文件"""
        os.makedirs(output_dir, exist_ok=True)
        order = ["setup", "materials", "geometry", "winding", "boundary", "mesh", "solver"]
        for name in order:
            if name in self.scripts and self.scripts[name]:
                filepath = os.path.join(output_dir, f"{name}.py")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(self.scripts[name])
                print(f"  Exported: {filepath}")

    def export_winding_report(self, output_dir):
        """导出绕组配置报告"""
        c = self.config
        from pmsm_winding_builder import WindingBuilder
        builder = WindingBuilder(slots=c.slots, poles=c.poles, phases=3)
        config = builder.compute_winding()

        report_path = os.path.join(output_dir, "winding_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("PMSM Winding Configuration Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"  Slots: {config.slots}\n")
            f.write(f"  Poles: {config.poles}\n")
            f.write(f"  q: {config.q:.2f}\n")
            f.write(f"  Winding factor: {config.winding_factor:.4f}\n")
            f.write(f"  Coil span: {config.coil_span}\n")
            f.write("\n  Coil Groups:\n")
            for group in config.coil_groups:
                if group.coil_indices:
                    f.write(f"    {group.phase}{group.polarity}: {len(group.coil_indices)} coils\n")
            f.write("=" * 60 + "\n")
        print(f"  Exported: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="ANSYS Maxwell Motor Auto-Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --preset 8p36s_tutorial
  python main.py --preset 8p12s_servo
  python main.py --params "slots=36 poles=8 stator_od=210 stator_id=136"
  python main.py --params "slots=12 poles=8 stator_od=80 stator_id=52 slot_type=rectangular"
  python main.py --json '{"slots":36,"poles":8,"stator_od":210,"stator_id":136}'
  python main.py --csv "slots,36\\npoles,8\\nstator_od,210"
  python main.py --interactive

槽型 (slot_type): rectangular | pear(默认) | trapezoidal | round
槽参数反推公式: references/motor_design_guide.md §4 "Slot size back-calculation"
电磁参数推导公式: references/motor_design_guide.md §3 (实现见 motor_param_calc.py)
""")
    parser.add_argument("--preset", type=str,
                        choices=["8p12s_servo", "36slot_industrial", "8p12s_ipm_ev", "8p36s_tutorial"],
                        help="使用预设配置")
    parser.add_argument("--params", type=str, help="关键词参数: slots=36 poles=8")
    parser.add_argument("--json", type=str, help="JSON参数: '{\"slots\":36}'")
    parser.add_argument("--csv", type=str, help="CSV参数: slots,36")
    parser.add_argument("--input", type=str, help="从文件读取参数")
    parser.add_argument("--interactive", action="store_true", help="交互式输入模式")
    parser.add_argument("--output_dir", type=str, default="./output_scripts",
                        help="脚本输出目录 (default: ./output_scripts)")
    parser.add_argument("--validate_only", action="store_true",
                        help="仅验证参数，不生成脚本")
    parser.add_argument("--report", action="store_true",
                        help="是否生成绕组报告")

    args = parser.parse_args()

    # 确定配置来源
    config = None

    if args.preset:
        if args.preset == "8p12s_servo":
            from motor_config import create_8p12s_spm_servo
            config = create_8p12s_spm_servo()
        elif args.preset == "36slot_industrial":
            from motor_config import create_36slot_industrial
            config = create_36slot_industrial()
        elif args.preset == "8p12s_ipm_ev":
            from motor_config import create_8p12s_ipm_ev
            config = create_8p12s_ipm_ev()
        elif args.preset == "8p36s_tutorial":
            from motor_config import create_8p36s_tutorial
            config = create_8p36s_tutorial()
            # 8p36s使用教程模式的绕组参数
            config.conductors_per_slot = 45

    elif args.params:
        config = create_motor_from_input(args.params, input_type="keyword")

    elif args.json:
        config = create_motor_from_input(args.json, input_type="json")

    elif args.csv:
        config = create_motor_from_input(args.csv, input_type="csv")

    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            content = f.read()
        config = create_motor_from_input(content, input_type="auto")

    elif args.interactive:
        config = interactive_input()

    else:
        print("请指定参数来源（--preset, --params, --json, --csv, --interactive）")
        print("使用 --help 查看帮助")
        sys.exit(1)

    if config is None:
        print("[ERROR] 无法创建配置")
        sys.exit(1)

    print("=" * 60)
    print("ANSYS Maxwell 电机自动化建模")
    print("=" * 60)
    print(f"  槽型: {config.slot_type.value}")
    print(f"  永磁拓扑: {config.pm_topology.value}")
    print(f"  槽数/极数: {config.slots}/{config.poles}")
    print(f"  定子: {config.stator_od}mm / {config.stator_id}mm")
    print(f"  转子: {config.rotor_od}mm / {config.rotor_id}mm")
    print(f"  磁钢材料(N/S): {config.pm_material_n} / {config.pm_material_s}")
    print()

    builder = MotorModelBuilder(config)
    if not builder.validate():
        sys.exit(1)

    if args.validate_only:
        return

    builder.generate_all_scripts()
    print(f"\n导出到: {args.output_dir}")
    builder.export_scripts(args.output_dir)

    if args.report:
        builder.export_winding_report(args.output_dir)

    print("\n[DONE] 脚本生成成功！")
    print(f"\n可以在ANSYS Electronics Desktop中依次运行:")
    print(f"  1. {args.output_dir}/setup.py     - 项目设置")
    print(f"  2. {args.output_dir}/materials.py  - 材料定义")
    print(f"  3. {args.output_dir}/geometry.py   - 几何建模")
    print(f"  4. {args.output_dir}/winding.py    - 绕组定义")
    print(f"  5. {args.output_dir}/boundary.py   - 边界与运动")
    print(f"  6. {args.output_dir}/mesh.py       - 网格设置")
    print(f"  7. {args.output_dir}/solver.py     - 求解器设置")


def interactive_input():
    """交互式输入模式"""
    print("\n=== 交互式电机参数输入 ===")
    print("（直接回车使用默认值）\n")

    data = {}

    def prompt(msg, default, cast_func=None):
        val = input(f"  {msg} [{default}]: ").strip()
        if not val:
            val = default
        if cast_func:
            val = cast_func(val)
        return val

    data["motor_type"] = "PMSM"
    data["rated_power_kw"] = float(prompt("额定功率 (kW)", "2.2"))
    data["rated_speed_rpm"] = float(prompt("额定转速 (rpm)", "2000"))
    data["dc_bus_voltage_v"] = float(prompt("母线电压 (V)", "310"))
    data["slots"] = int(prompt("槽数", "36"))
    data["poles"] = int(prompt("极数", "8"))
    data["stator_od"] = float(prompt("定子外径 (mm)", "210.0"))
    data["stator_id"] = float(prompt("定子内径 (mm)", "136.0"))
    data["rotor_od"] = float(prompt("转子外径 (mm)", "135.2"))
    data["rotor_id"] = float(prompt("转子内径 (mm)", "48.0"))
    data["airgap"] = float(prompt("气隙 (mm)", "0.4"))
    data["stack_length"] = float(prompt("叠片长度 (mm)", "100"))
    data["pm_thickness"] = float(prompt("磁钢厚度 (mm)", "3.0"))
    data["pm_pole_arc"] = float(prompt("极弧系数", "0.85"))
    data["conductors_per_slot"] = int(prompt("每槽导体数", "45"))
    data["slot_fill_factor"] = float(prompt("槽满率", "0.45"))

    return MotorConfig.from_dict(data)


if __name__ == "__main__":
    main()
