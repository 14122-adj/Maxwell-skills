#!/usr/bin/env python3
"""
ANSYS Maxwell MCP Server
=========================
让 Claude AI 通过 MCP 协议控制 ANSYS Maxwell 电磁场仿真软件。

功能覆盖：
  - 项目/设计管理
  - 几何建模（2D/3D）
  - 材料管理
  - 边界条件与激励
  - 网格设置
  - 求解配置与执行
  - 结果提取与场图绘制

依赖：pywin32, mcp
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# ── 日志 ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("maxwell-mcp")


# ══════════════════════════════════════════════════════════════
#  Maxwell COM 客户端
# ══════════════════════════════════════════════════════════════
class MaxwellClient:
    """ANSYS Maxwell COM 自动化客户端"""

    def __init__(self) -> None:
        self.win32com = None
        self.desktop = None
        self.project = None
        self.design = None
        self.editor = None
        self.connected = False

    # ── 连接管理 ──────────────────────────────────────────
    def connect(self, version: Optional[str] = None) -> str:
        """
        连接到正在运行的 ANSYS Electronics Desktop。
        version: 如 "2024.2"，留空自动检测。
        """
        try:
            import win32com.client as _com
            self.win32com = _com
        except ImportError:
            raise RuntimeError(
                "未安装 pywin32，请运行: pip install pywin32"
            )

        try:
            prog_id = (
                f"Ansoft.ElectronicsDesktop.{version}"
                if version
                else "Ansoft.ElectronicsDesktop"
            )
            self.desktop = self.win32com.Dispatch(prog_id)
            # Dispatch 返回的是 AEDT 外壳包装对象，真正可用的桌面接口需经 GetAppDesktop()
            try:
                self.desktop = self.desktop.GetAppDesktop()
            except Exception:
                pass  # 某些版本 Dispatch 即返回桌面接口
            self.connected = True
            ver_info = ""
            try:
                ver_info = f" (v{self.desktop.GetVersion()})"
            except Exception:
                pass
            return f"已连接到 ANSYS Electronics Desktop{ver_info}"
        except Exception as e:
            raise RuntimeError(
                f"连接失败: {e}\n"
                "请确认 ANSYS Electronics Desktop 已启动，且当前用户有 COM 访问权限。"
            )

    def disconnect(self) -> str:
        self.desktop = None
        self.project = None
        self.design = None
        self.editor = None
        self.connected = False
        return "已断开与 ANSYS Maxwell 的连接"

    # ── 对象获取 ──────────────────────────────────────────
    def get_project(self, name: Optional[str] = None):
        if name:
            self.project = self.desktop.SetActiveProject(name)
        else:
            self.project = self.desktop.GetActiveProject()
        if self.project is None:
            raise RuntimeError("没有活动项目")
        return self.project

    def get_design(self, name: Optional[str] = None):
        proj = self.project or self.get_project()
        if name:
            self.design = proj.SetActiveDesign(name)
        else:
            self.design = proj.GetActiveDesign()
        if self.design is None:
            raise RuntimeError("没有活动设计")
        return self.design

    def get_editor(self):
        if self.editor is None:
            design = self.design or self.get_design()
            self.editor = design.SetActiveEditor("3D Modeler")
        return self.editor

    def get_module(self, mod_name: str):
        design = self.design or self.get_design()
        return design.GetModule(mod_name)

    # ── 辅助方法 ──────────────────────────────────────────
    @staticmethod
    def _args(name: str, *nested: Any, **kwargs: Any) -> list:
        """
        构建 ANSYS 风格的参数列表。
        _args("Params", X="0mm", Y="0mm")
        => ["NAME:Params", "X:=", "0mm", "Y:=", "0mm"]
        """
        result = [f"NAME:{name}"]
        for k, v in kwargs.items():
            result.extend([f"{k}:=", v])
        for n in nested:
            result.append(n)
        return result

    def _require_connected(self) -> None:
        if not self.connected:
            raise RuntimeError("未连接到 ANSYS Maxwell，请先调用 connect_to_maxwell")

    def _get_status_dict(self) -> dict[str, Any]:
        """获取当前连接状态信息字典（内部复用）。"""
        info: dict[str, Any] = {"connected": self.connected}
        if not self.connected:
            return info
        try:
            proj = self.desktop.GetActiveProject()
            info["active_project"] = proj.GetName() if proj else None
            if proj:
                design = proj.GetActiveDesign()
                info["active_design"] = design.GetName() if design else None
                if design:
                    info["design_type"] = design.GetDesignType()
                    info["solution_type"] = design.GetSolutionType()
        except Exception:
            pass
        return info


# 全局实例
maxwell = MaxwellClient()


def _safe(fn, *a, **kw) -> str:
    """统一执行并捕获异常（包含连接检查）"""
    try:
        maxwell._require_connected()
        result = fn(*a, **kw)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.exception("工具执行出错")
        return f"❌ 错误: {e}"


# ══════════════════════════════════════════════════════════════
#  MCP Server
# ══════════════════════════════════════════════════════════════
mcp = FastMCP(
    "ansys-maxwell",
    instructions="ANSYS Maxwell 电磁仿真控制 — 由 Claude 通过 MCP 驱动",
)


# ────────────────────────────────────────────────────────────
#  1. 系统 / 连接
# ────────────────────────────────────────────────────────────
@mcp.tool()
def connect_to_maxwell(version: str = "") -> str:
    """
    连接到正在运行的 ANSYS Electronics Desktop。
    version: AEDT 版本号（如 "2024.2"），留空则自动检测。
    """
    # 连接工具不走 _safe()，因为 _safe() 会先检查 connected
    try:
        return maxwell.connect(version or None)
    except Exception as e:
        logger.exception("连接失败")
        return f"❌ 错误: {e}"


@mcp.tool()
def disconnect_from_maxwell() -> str:
    """断开与 ANSYS Maxwell 的连接。"""
    return maxwell.disconnect()


@mcp.tool()
def get_maxwell_status() -> str:
    """获取当前连接状态与活动项目/设计信息。"""
    try:
        info = maxwell._get_status_dict()
        return json.dumps(info, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"❌ {e}"


# ────────────────────────────────────────────────────────────
#  2. 项目管理
# ────────────────────────────────────────────────────────────
@mcp.tool()
def new_project() -> str:
    """在 ANSYS Maxwell 中创建一个新项目。"""
    def _():
        maxwell.project = maxwell.desktop.NewProject()
        maxwell.design = None
        maxwell.editor = None
        return f"已创建新项目: {maxwell.project.GetName()}"
    return _safe(_)


@mcp.tool()
def open_project(file_path: str) -> str:
    """
    打开已有项目文件。
    file_path: .aedt 文件的完整路径。
    """
    def _():
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        maxwell.project = maxwell.desktop.OpenProject(file_path)
        maxwell.design = None
        maxwell.editor = None
        return f"已打开项目: {maxwell.project.GetName()}"
    return _safe(_)


@mcp.tool()
def save_project(file_path: str = "") -> str:
    """
    保存当前项目。
    file_path: 另存为路径（留空则保存到当前位置）。
    """
    def _():
        proj = maxwell.get_project()
        if file_path:
            proj.SaveAs(file_path, True)
            return f"项目已另存为: {file_path}"
        else:
            proj.Save()
            return f"项目已保存: {proj.GetName()}"
    return _safe(_)


@mcp.tool()
def close_project(name: str = "") -> str:
    """
    关闭项目。
    name: 项目名称（留空则关闭当前项目）。
    """
    def _():
        proj = maxwell.get_project(name or None)
        proj_name = proj.GetName()
        proj.Close()
        maxwell.project = None
        maxwell.design = None
        maxwell.editor = None
        return f"已关闭项目: {proj_name}"
    return _safe(_)


@mcp.tool()
def list_projects() -> str:
    """列出所有打开的项目。"""
    def _():
        names = [
            maxwell.desktop.GetProject(i).GetName()
            for i in range(maxwell.desktop.GetProjectCount())
        ]
        return json.dumps(names, ensure_ascii=False)
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  3. 设计管理
# ────────────────────────────────────────────────────────────
@mcp.tool()
def create_design(
    design_type: str = "Maxwell 3D",
    design_name: str = "",
    solution_type: str = "Magnetostatic",
) -> str:
    """
    创建新设计。
    design_type: "Maxwell 2D" 或 "Maxwell 3D"
    design_name: 设计名称（留空自动生成）
    solution_type: "Magnetostatic", "EddyCurrent", "Transient",
                   "ElectricTransient", "DCConduction", "Electrostatic", "ACConduction"
    """
    def _():
        proj = maxwell.get_project()
        dn = design_name or f"{solution_type}Design"
        proj.InsertDesign(design_type, dn, solution_type, "")
        maxwell.design = proj.SetActiveDesign(dn)
        maxwell.editor = None
        return f"已创建设计: {dn} ({design_type} / {solution_type})"
    return _safe(_)


@mcp.tool()
def set_active_design(design_name: str) -> str:
    """设置活动设计。"""
    def _():
        proj = maxwell.get_project()
        maxwell.design = proj.SetActiveDesign(design_name)
        maxwell.editor = None
        return f"活动设计已设为: {design_name}"
    return _safe(_)


@mcp.tool()
def list_designs() -> str:
    """列出当前项目中的所有设计。"""
    def _():
        proj = maxwell.get_project()
        # 使用 GetTopDesignList() 获取设计名称列表（修复原 GetNumber() API 错误）
        names = list(proj.GetTopDesignList())
        return json.dumps(names, ensure_ascii=False)
    return _safe(_)


@mcp.tool()
def delete_design(design_name: str) -> str:
    """从项目中删除指定设计。"""
    def _():
        proj = maxwell.get_project()
        proj.DeleteDesign(design_name)
        if maxwell.design and maxwell.design.GetName() == design_name:
            maxwell.design = None
            maxwell.editor = None
        return f"已删除设计: {design_name}"
    return _safe(_)


@mcp.tool()
def get_design_info() -> str:
    """获取当前设计的详细信息。"""
    def _():
        d = maxwell.get_design()
        info: dict[str, Any] = {
            "name": d.GetName(),
            "design_type": d.GetDesignType(),
            "solution_type": d.GetSolutionType(),
        }
        try:
            editor = maxwell.get_editor()
            info["solids"] = list(editor.GetObjectsInGroup("Solids"))
            info["sheets"] = list(editor.GetObjectsInGroup("Sheets"))
            info["lines"] = list(editor.GetObjectsInGroup("Lines"))
        except Exception:
            pass
        return json.dumps(info, ensure_ascii=False, indent=2)
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  4. 几何建模
# ────────────────────────────────────────────────────────────
@mcp.tool()
def draw_box(
    x: str = "0mm",
    y: str = "0mm",
    z: str = "0mm",
    dx: str = "10mm",
    dy: str = "10mm",
    dz: str = "10mm",
    name: str = "",
    material: str = "vacuum",
    color: str = "(143 175 143)",
) -> str:
    """
    绘制长方体。
    x,y,z: 起点坐标（带单位，如 "0mm"）
    dx,dy,dz: 三方向尺寸
    name: 对象名称（留空自动生成）
    material: 材料名称
    color: RGB 颜色，格式 "(R G B)"
    """
    def _():
        editor = maxwell.get_editor()
        obj_name = name or f"Box_{int(time.time() * 1000) % 100000}"
        editor.CreateBox(
            MaxwellClient._args(
                "BoxParameters",
                XPosition=x, YPosition=y, ZPosition=z,
                XSize=dx, YSize=dy, ZSize=dz,
            ),
            MaxwellClient._args(
                "Attributes",
                Name=obj_name, Flags="",
                Color=color, Transparency=0,
                PartCoordinateSystem="Global",
                MaterialValue=f'"{material}"',
                SolveInside=True,
            ),
        )
        return f"已创建长方体: {obj_name}，材料={material}"
    return _safe(_)


@mcp.tool()
def draw_cylinder(
    x: str = "0mm",
    y: str = "0mm",
    z: str = "0mm",
    radius: str = "5mm",
    height: str = "10mm",
    axis: str = "Z",
    name: str = "",
    material: str = "vacuum",
    color: str = "(143 175 143)",
) -> str:
    """
    绘制圆柱体。
    x,y,z: 底面圆心坐标
    radius: 半径
    height: 高度
    axis: 轴向 ("X", "Y", "Z")
    """
    def _():
        editor = maxwell.get_editor()
        obj_name = name or f"Cyl_{int(time.time() * 1000) % 100000}"
        editor.CreateCylinder(
            MaxwellClient._args(
                "CylinderParameters",
                XPosition=x, YPosition=y, ZPosition=z,
                Radius=radius, Height=height,
                WhichAxis=axis,
            ),
            MaxwellClient._args(
                "Attributes",
                Name=obj_name, Flags="",
                Color=color, Transparency=0,
                PartCoordinateSystem="Global",
                MaterialValue=f'"{material}"',
                SolveInside=True,
            ),
        )
        return f"已创建圆柱体: {obj_name}，轴向={axis}，材料={material}"
    return _safe(_)


@mcp.tool()
def draw_rectangle(
    x: str = "0mm",
    y: str = "0mm",
    z: str = "0mm",
    width: str = "10mm",
    height: str = "10mm",
    axis: str = "Z",
    name: str = "",
    color: str = "(255 0 0)",
) -> str:
    """
    绘制矩形薄片（Sheet）。
    x,y,z: 起始点
    width, height: 宽与高
    axis: 所在平面法向 ("X", "Y", "Z")
    """
    def _():
        editor = maxwell.get_editor()
        obj_name = name or f"Rect_{int(time.time() * 1000) % 100000}"
        editor.CreateRectangle(
            [
                "NAME:RectangleParameters",
                "IsCovered:=", True,
                "XStart:=", x,
                "YStart:=", y,
                "ZStart:=", z,
                "Width:=", width,
                "Height:=", height,
                "WhichAxis:=", axis.upper(),
            ],
            MaxwellClient._args(
                "Attributes",
                Name=obj_name, Flags="",
                Color=color, Transparency=0,
                PartCoordinateSystem="Global",
                MaterialValue='"vacuum"',
                SolveInside=True,
            ),
        )
        return f"已创建矩形: {obj_name}"
    return _safe(_)


@mcp.tool()
def draw_circle(
    x: str = "0mm",
    y: str = "0mm",
    z: str = "0mm",
    radius: str = "5mm",
    axis: str = "Z",
    name: str = "",
    color: str = "(0 0 255)",
) -> str:
    """
    绘制圆形薄片（Sheet）。
    x,y,z: 圆心坐标
    radius: 半径
    axis: 所在平面法向
    """
    def _():
        editor = maxwell.get_editor()
        obj_name = name or f"Circle_{int(time.time() * 1000) % 100000}"
        editor.CreateCircle(
            MaxwellClient._args(
                "CircleParameters",
                XPosition=x, YPosition=y, ZPosition=z,
                Radius=radius, WhichAxis=axis.upper(),
            ),
            MaxwellClient._args(
                "Attributes",
                Name=obj_name, Flags="",
                Color=color, Transparency=0,
                PartCoordinateSystem="Global",
                MaterialValue='"vacuum"',
                SolveInside=True,
            ),
        )
        return f"已创建圆: {obj_name}"
    return _safe(_)


@mcp.tool()
def draw_line(
    start: Optional[list[str]] = None,
    end: Optional[list[str]] = None,
    name: str = "",
    color: str = "(255 255 0)",
) -> str:
    """
    绘制直线段。
    start: 起点坐标 ["0mm", "0mm", "0mm"]
    end: 终点坐标 ["10mm", "0mm", "0mm"]
    """
    def _():
        if not start or not end or len(start) < 3 or len(end) < 3:
            raise ValueError("start 和 end 需要至少三个坐标分量")
        editor = maxwell.get_editor()
        obj_name = name or f"Line_{int(time.time() * 1000) % 100000}"
        editor.CreatePolyline(
            [
                "NAME:PolylineParameters",
                "IsPolylineCovered:=", True,
                "IsPolylineClosed:=", False,
            ],
            [
                "NAME:PolylinePoints",
                ["NAME:PLPoint", "X:=", start[0], "Y:=", start[1], "Z:=", start[2]],
                ["NAME:PLPoint", "X:=", end[0], "Y:=", end[1], "Z:=", end[2]],
            ],
            [
                "NAME:PolylineSegments",
                ["NAME:PLSegment", "SegmentType:=", "Line", "StartIndex:=", 0, "NoOfPoints:=", 2],
            ],
            MaxwellClient._args(
                "Attributes",
                Name=obj_name, Flags="",
                Color=color, Transparency=0,
                PartCoordinateSystem="Global",
                MaterialValue='"vacuum"',
                SolveInside=True,
            ),
        )
        return f"已创建线段: {obj_name}"
    return _safe(_)


# ── 布尔运算与变换 ────────────────────────────────────────
@mcp.tool()
def unite_objects(objects: list[str], keep_originals: bool = False) -> str:
    """
    合并多个几何对象。
    objects: 要合并的对象名称列表
    keep_originals: 是否保留原始对象
    """
    def _():
        editor = maxwell.get_editor()
        editor.Unite(
            ["NAME:Selections", "Selections:=", ",".join(objects)],
            ["NAME:UniteParameters", "KeepOriginals:=", keep_originals],
        )
        return f"已合并: {', '.join(objects)}"
    return _safe(_)


@mcp.tool()
def subtract_objects(
    blank_objects: list[str],
    tool_objects: list[str],
    keep_originals: bool = False,
) -> str:
    """
    布尔减法：从 blank 中减去 tool。
    blank_objects: 被减对象列表
    tool_objects: 工具对象列表
    keep_originals: 是否保留工具对象
    """
    def _():
        editor = maxwell.get_editor()
        editor.Subtract(
            [
                "NAME:Selections",
                "Blank Parts:=", ",".join(blank_objects),
                "Tool Parts:=", ",".join(tool_objects),
            ],
            ["NAME:SubtractParameters", "KeepOriginals:=", keep_originals],
        )
        return f"已执行减法: {', '.join(blank_objects)} - {', '.join(tool_objects)}"
    return _safe(_)


@mcp.tool()
def intersect_objects(objects: list[str], keep_originals: bool = False) -> str:
    """
    布尔交集。
    objects: 要取交集的对象列表
    """
    def _():
        editor = maxwell.get_editor()
        editor.Intersect(
            ["NAME:Selections", "Selections:=", ",".join(objects)],
            ["NAME:IntersectParameters", "KeepOriginals:=", keep_originals],
        )
        return f"已执行交集: {', '.join(objects)}"
    return _safe(_)


@mcp.tool()
def move_object(
    object_name: str,
    dx: str = "0mm",
    dy: str = "0mm",
    dz: str = "0mm",
) -> str:
    """移动几何对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.Move(
            ["NAME:Selections", "Selections:=", object_name],
            [
                "NAME:TranslateParameters",
                "TranslateVectorX:=", dx,
                "TranslateVectorY:=", dy,
                "TranslateVectorZ:=", dz,
            ],
        )
        return f"已移动 {object_name}: ({dx}, {dy}, {dz})"
    return _safe(_)


@mcp.tool()
def duplicate_object(
    object_name: str,
    dx: str = "0mm",
    dy: str = "0mm",
    dz: str = "0mm",
    count: int = 1,
) -> str:
    """复制几何对象（沿偏移方向复制 count 份）。"""
    def _():
        editor = maxwell.get_editor()
        editor.DuplicateAlongLine(
            ["NAME:Selections", "Selections:=", object_name],
            [
                "NAME:DuplicateToAlongLineParameters",
                "CreateNewObjects:=", True,
                "XComponent:=", dx,
                "YComponent:=", dy,
                "ZComponent:=", dz,
                "NumClones:=", str(count),
            ],
            ["NAME:Options", "DuplicateAssignments:=", True],
        )
        return f"已复制 {object_name} {count} 次，偏移 ({dx}, {dy}, {dz})"
    return _safe(_)


@mcp.tool()
def scale_object(
    object_name: str,
    sx: float = 1.0,
    sy: float = 1.0,
    sz: float = 1.0,
) -> str:
    """缩放几何对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.Scale(
            ["NAME:Selections", "Selections:=", object_name],
            [
                "NAME:ScaleParameters",
                "ScaleX:=", str(sx),
                "ScaleY:=", str(sy),
                "ScaleZ:=", str(sz),
            ],
        )
        return f"已缩放 {object_name}: ({sx}, {sy}, {sz})"
    return _safe(_)


@mcp.tool()
def rename_object(old_name: str, new_name: str) -> str:
    """重命名几何对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DAttributeTab",
                    ["NAME:PropServers", old_name],
                    ["NAME:ChangedProps", ["NAME:Name", "Value:=", new_name]],
                ],
            ]
        )
        return f"已重命名: {old_name} → {new_name}"
    return _safe(_)


@mcp.tool()
def list_objects() -> str:
    """列出当前设计中的所有几何对象。"""
    def _():
        editor = maxwell.get_editor()
        result = {
            "solids": list(editor.GetObjectsInGroup("Solids")),
            "sheets": list(editor.GetObjectsInGroup("Sheets")),
            "lines": list(editor.GetObjectsInGroup("Lines")),
            "unclosed_solids": list(editor.GetObjectsInGroup("UnclosedSolids")),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    return _safe(_)


@mcp.tool()
def create_region(
    pad_x: str = "10mm",
    pad_y: str = "10mm",
    pad_z: str = "10mm",
    pad_type: str = "Absolute Offset",
) -> str:
    """
    创建求解域（Region）。
    pad_x/y/z: 各方向的扩展距离
    pad_type: "Absolute Offset" 或 "Percentage Offset"
    """
    def _():
        editor = maxwell.get_editor()
        editor.CreateRegion(
            [
                "NAME:RegionParameters",
                "+X Padding Type:=", pad_type, "+X Padding:=", pad_x,
                "-X Padding Type:=", pad_type, "-X Padding:=", pad_x,
                "+Y Padding Type:=", pad_type, "+Y Padding:=", pad_y,
                "-Y Padding Type:=", pad_type, "-Y Padding:=", pad_y,
                "+Z Padding Type:=", pad_type, "+Z Padding:=", pad_z,
                "-Z Padding Type:=", pad_type, "-Z Padding:=", pad_z,
            ]
        )
        return f"已创建求解域: ({pad_x}, {pad_y}, {pad_z})"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  5. 材料管理
# ────────────────────────────────────────────────────────────
@mcp.tool()
def assign_material(object_name: str, material: str = "vacuum") -> str:
    """
    为几何对象分配材料。
    object_name: 对象名称
    material: 材料名称（如 "steel_1010", "copper", "aluminum", "NdFe35" 等）
    """
    def _():
        editor = maxwell.get_editor()
        editor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DAttributeTab",
                    ["NAME:PropServers", object_name],
                    ["NAME:ChangedProps", ["NAME:Material", "Value:=", f'"{material}"']],
                ],
            ]
        )
        return f"已将 {object_name} 的材料设为: {material}"
    return _safe(_)


@mcp.tool()
def set_object_color(object_name: str, color: str = "(255 0 0)") -> str:
    """设置对象显示颜色。color 格式: "(R G B)"，值 0-255。"""
    def _():
        editor = maxwell.get_editor()
        editor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DAttributeTab",
                    ["NAME:PropServers", object_name],
                    ["NAME:ChangedProps", ["NAME:Color", "Value:=", color]],
                ],
            ]
        )
        return f"已设置 {object_name} 颜色为 {color}"
    return _safe(_)


@mcp.tool()
def set_object_solve_inside(object_name: str, solve_inside: bool = True) -> str:
    """设置对象是否在内部求解（适用于导体等）。"""
    def _():
        editor = maxwell.get_editor()
        editor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DAttributeTab",
                    ["NAME:PropServers", object_name],
                    ["NAME:ChangedProps", ["NAME:Solve Inside", "Value:=", solve_inside]],
                ],
            ]
        )
        tag = "启用" if solve_inside else "禁用"
        return f"已{tag} {object_name} 的内部求解"
    return _safe(_)


@mcp.tool()
def add_custom_material(
    material_name: str,
    properties: Optional[dict[str, str]] = None,
) -> str:
    """
    添加自定义材料。
    properties: 材料属性字典，如：
    {
        "permeability": "1",
        "conductivity": "5.8e7",
        "magnetic_coercivity": "0"
    }
    """
    def _():
        if not properties:
            raise ValueError("需要提供材料属性")
        proj = maxwell.get_project()
        lib = proj.GetDefinitionManager()
        # 构建完整的材料属性数组（修复原格式错误）
        mat_args = [f"NAME:{material_name}"]
        for k, v in properties.items():
            mat_args.extend([f"{k}:=", v])
        lib.AddMaterial(mat_args)
        return f"已添加材料: {material_name}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  6. 边界条件与激励
# ────────────────────────────────────────────────────────────
@mcp.tool()
def assign_vector_potential(
    object_name: str,
    boundary_name: str = "",
    value: str = "0",
    coordinate_system: str = "Cartesian",
) -> str:
    """
    分配矢量磁位边界条件。
    object_name: 需要分配边界的对象（通常是 Region 表面或边界对象）
    value: 矢量磁位值（如 "0" 表示磁力线平行边界）
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        bn = boundary_name or f"VectorPot_{int(time.time() * 1000) % 100000}"
        module.AssignVectorPotential(
            [
                f"NAME:{bn}",
                "Objects:=", [object_name],
                "Value:=", value,
                "CoordinateSystem:=", coordinate_system,
            ]
        )
        return f"已分配矢量磁位: {bn} = {value}"
    return _safe(_)


@mcp.tool()
def assign_balloon_boundary(
    objects: list[str],
    boundary_name: str = "",
) -> str:
    """
    分配 Balloon（气球）边界条件，模拟无限远。
    objects: 边界对象列表
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        bn = boundary_name or f"Balloon_{int(time.time() * 1000) % 100000}"
        module.AssignBalloon(
            [f"NAME:{bn}", "Objects:=", objects]
        )
        return f"已分配 Balloon 边界: {bn}"
    return _safe(_)


@mcp.tool()
def assign_master_slave_boundary(
    master_objects: list[str],
    slave_objects: list[str],
    boundary_name: str = "",
    angle: str = "0deg",
) -> str:
    """
    分配主从边界条件（用于周期性边界）。
    master_objects: 主边界对象
    slave_objects: 从边界对象
    angle: 周期角度
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        bn = boundary_name or f"MasterSlave_{int(time.time() * 1000) % 100000}"
        master_bn = bn + "_Master"
        slave_bn = bn + "_Slave"
        module.AssignIndependent(
            [f"NAME:{master_bn}", "Objects:=", master_objects, "CoordSystem:=", "Global"]
        )
        module.AssignDependent(
            [
                f"NAME:{slave_bn}",
                "Objects:=", slave_objects,
                "Independent:=", master_bn,
                "SameAsMaster:=", True,
                "AngleOfDirection:=", angle,
            ]
        )
        return f"已分配主从边界: {master_bn} / {slave_bn}"
    return _safe(_)


@mcp.tool()
def assign_current_excitation(
    objects: list[str],
    current: str = "1A",
    excitation_name: str = "",
    is_solid: bool = True,
    is_positive: bool = True,
) -> str:
    """
    分配电流激励。
    objects: 导体截面对象列表
    current: 电流值（如 "10A", "1.5mA"）
    is_solid: 是否为实体导体
    is_positive: 电流方向
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        en = excitation_name or f"Current_{int(time.time() * 1000) % 100000}"
        module.AssignCurrent(
            [
                f"NAME:{en}",
                "Objects:=", objects,
                "Current:=", current,
                "IsSolid:=", is_solid,
                "IsPositive:=", is_positive,
            ]
        )
        return f"已分配电流激励: {en} = {current}"
    return _safe(_)


@mcp.tool()
def assign_voltage_excitation(
    objects: list[str],
    voltage: str = "1V",
    excitation_name: str = "",
) -> str:
    """分配电压激励。"""
    def _():
        module = maxwell.get_module("BoundarySetup")
        en = excitation_name or f"Voltage_{int(time.time() * 1000) % 100000}"
        module.AssignVoltage(
            [f"NAME:{en}", "Objects:=", objects, "Value:=", voltage]
        )
        return f"已分配电压激励: {en} = {voltage}"
    return _safe(_)


@mcp.tool()
def assign_winding(
    winding_name: str = "Winding1",
    excitation_type: str = "Current",
    current: str = "1A",
    resistance: str = "0",
    inductance: str = "0",
    voltage: str = "0",
    is_solid: bool = True,
    parallel_branches: int = 1,
    phase: int = 0,
) -> str:
    """
    分配绕组激励（用于电机仿真）。
    excitation_type: "Current" 或 "Voltage"
    current: 电流幅值
    parallel_branches: 并联支路数
    phase: 相位角（电角度）
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        module.AssignWinding(
            MaxwellClient._args(
                "Winding",
                Name=winding_name,
                Type=excitation_type,
                IsSolid=is_solid,
                Current=current,
                Resistance=resistance,
                Inductance=inductance,
                Voltage=voltage,
                ParallelBranchesNum=parallel_branches,
                Phase=phase,
                WindingType="Stranded",
            )
        )
        return f"已创建绕组: {winding_name}, {excitation_type}={current}"
    return _safe(_)


@mcp.tool()
def add_turns_to_winding(
    winding_name: str,
    objects: list[str],
    turns: int = 1,
) -> str:
    """
    将线圈截面添加到绕组。
    winding_name: 绕组名称
    objects: 线圈截面对象列表
    turns: 匝数
    """
    def _():
        module = maxwell.get_module("BoundarySetup")
        module.AddWindingNode(
            winding_name,
            ["NAME:WindingNode", "Objects:=", objects, "Turns:=", turns],
        )
        return f"已将 {', '.join(objects)} 添加到 {winding_name}，匝数={turns}"
    return _safe(_)


@mcp.tool()
def assign_force_parameter(
    objects: list[str],
    param_name: str = "",
) -> str:
    """
    分配力参数（用于力计算）。
    objects: 需要计算力的对象列表
    """
    def _():
        module = maxwell.get_module("Parameters")
        pn = param_name or f"Force_{int(time.time() * 1000) % 100000}"
        module.AssignForce(
            [
                f"NAME:{pn}",
                "Objects:=", objects,
                "ReferenceCS:=", "Global",
                "IsVirtual:=", True,
            ]
        )
        return f"已分配力参数: {pn}"
    return _safe(_)


@mcp.tool()
def assign_torque_parameter(
    objects: list[str],
    param_name: str = "",
    axis: str = "Z",
) -> str:
    """
    分配转矩参数（用于电机仿真）。
    objects: 需要计算转矩的对象列表
    axis: 旋转轴 ("X", "Y", "Z")
    """
    def _():
        module = maxwell.get_module("Parameters")
        pn = param_name or f"Torque_{int(time.time() * 1000) % 100000}"
        module.AssignTorque(
            [
                f"NAME:{pn}",
                "Objects:=", objects,
                "Axis:=", axis,
                "IsVirtual:=", True,
            ]
        )
        return f"已分配转矩参数: {pn}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  7. 运动设置（用于 Transient）
# ────────────────────────────────────────────────────────────
@mcp.tool()
def assign_motion_setup(
    objects: list[str],
    motion_type: str = "Rotation",
    axis: str = "Z",
    positive: bool = True,
    angular_velocity: str = "1000rpm",
) -> str:
    """
    分配运动设置（瞬态仿真）。
    objects: 运动部件对象列表
    motion_type: "Rotation" 或 "Translation"
    axis: 运动轴
    angular_velocity: 角速度（旋转）或速度（平移）
    """
    def _():
        module = maxwell.get_module("ModelSetup")
        module.AssignMotion(
            MaxwellClient._args(
                "MotionSetup",
                MotionType=motion_type,
                CoordinateSystem="Global",
                AxisOfRotation=axis,
                PositiveDirection=positive,
                AngularVelocity=angular_velocity,
                **{"Objects": objects},
            )
        )
        return f"已设置运动: {motion_type} {angular_velocity} (轴={axis})"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  8. 网格操作
# ────────────────────────────────────────────────────────────
@mcp.tool()
def assign_mesh_operation(
    objects: list[str],
    mesh_type: str = "InsideSelection",
    element_size: str = "1mm",
    op_name: str = "",
) -> str:
    """
    分配网格操作。
    objects: 目标对象列表
    mesh_type: "InsideSelection" (内部) 或 "SurfaceApproximation" (表面近似)
    element_size: 最大单元尺寸
    """
    def _():
        module = maxwell.get_module("MeshSetup")
        on = op_name or f"MeshOp_{int(time.time() * 1000) % 100000}"
        module.AssignLengthOp(
            [
                f"NAME:{on}",
                "Objects:=", objects,
                "ElementSize:=", element_size,
                "RestrictElem:=", True,
            ]
        )
        return f"已设置网格操作: {on}, 单元尺寸={element_size}"
    return _safe(_)


@mcp.tool()
def assign_skin_depth_mesh(
    objects: list[str],
    skin_depth: str = "0.5mm",
    num_layers: int = 2,
    op_name: str = "",
) -> str:
    """
    分配趋肤深度网格（用于涡流分析）。
    objects: 导体对象列表
    skin_depth: 趋肤深度
    num_layers: 趋肤层层数
    """
    def _():
        module = maxwell.get_module("MeshSetup")
        on = op_name or f"SkinDepth_{int(time.time() * 1000) % 100000}"
        module.AssignSkinDepthOp(
            [
                f"NAME:{on}",
                "Objects:=", objects,
                "SkinDepth:=", skin_depth,
                "NumLayersOfElements:=", num_layers,
            ]
        )
        return f"已设置趋肤深度网格: {on}, 深度={skin_depth}, 层数={num_layers}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  9. 求解设置
# ────────────────────────────────────────────────────────────
@mcp.tool()
def create_analysis_setup(
    setup_name: str = "Setup1",
    solution_type: str = "Magnetostatic",
    max_passes: int = 10,
    percent_error: float = 1.0,
    percent_refinement: int = 30,
    frequency: str = "0Hz",
    max_delta_energy: float = 0.1,
) -> str:
    """
    创建分析设置。
    setup_name: 设置名称
    solution_type: 求解类型（应与设计类型匹配）
    max_passes: 最大迭代次数
    percent_error: 百分比误差目标
    percent_refinement: 每次迭代网格加密比例
    frequency: 频率（EddyCurrent 需要）
    max_delta_energy: 最大能量变化（%）
    """
    def _():
        module = maxwell.get_module("AnalysisSetup")
        setup_args = MaxwellClient._args(
            setup_name,
            MaximumPasses=max_passes,
            PercentError=percent_error,
            PercentRefinement=percent_refinement,
            MinConvergedPasses=1,
            MinPasses=1,
            MaxRefinementPerPass=100,
            MaxDeltaEnergy=max_delta_energy,
            Frequency=frequency,
        )
        module.InsertSetup(solution_type, setup_args)
        return f"已创建分析设置: {setup_name} ({solution_type})"
    return _safe(_)


@mcp.tool()
def create_parametric_sweep(
    setup_name: str = "Setup1",
    sweep_name: str = "Sweep1",
    variable: str = "RotorAngle",
    start: str = "0deg",
    end: str = "90deg",
    step: str = "1deg",
    sweep_type: str = "LinearStep",
) -> str:
    """
    创建参数化扫描。
    setup_name: 关联的分析设置
    sweep_name: 扫描名称
    variable: 扫描变量名称
    start, end, step: 起始值、终止值、步长
    sweep_type: "LinearStep" (等步长) 或 "LinearCount" (等数量) 或 "SinglePoint"
    """
    def _():
        module = maxwell.get_module("Optimetrics")
        module.InsertSetup(
            "Parametric",
            [
                f"NAME:{sweep_name}",
                [
                    "NAME:ProdOptiSetupData",
                    ["NAME:StartingPoint"],
                    "UseNominal:=", False,
                    [
                        "NAME:Sweeps",
                        [
                            "NAME:SweepDefinition",
                            "Variable:=", variable,
                            "StartValue:=", start,
                            "StopValue:=", end,
                            "StepValue:=", step,
                            "SweepType:=", sweep_type,
                        ],
                    ],
                    ["NAME:SweepOperations"],
                    ["NAME:Goals"],
                ],
            ],
        )
        return f"已创建参数化扫描: {sweep_name}, 变量={variable} [{start}:{step}:{end}]"
    return _safe(_)


@mcp.tool()
def create_optimization(
    setup_name: str = "Setup1",
    opt_name: str = "Optimization1",
    goals: Optional[list[dict]] = None,
    variables: Optional[list[str]] = None,
) -> str:
    """
    创建优化设置。
    goals: 目标列表，如 [{"expression": "Force(Force1)", "target": "10"}]
    variables: 优化变量名列表
    """
    def _():
        module = maxwell.get_module("Optimetrics")
        opt_setup = [f"NAME:{opt_name}", "SetupName:=", setup_name, "SetupStart:=", False]
        if goals:
            goals_list = ["NAME:Goals"]
            for g in goals:
                goals_list.append(
                    [
                        "NAME:Goal",
                        "ReportType:=", "Fields",
                        "Solution:=", f"{setup_name} : LastAdaptive",
                        "Expression:=", g.get("expression", ""),
                        "GoalValue:=", g.get("target", "0"),
                    ]
                )
            opt_setup.append(goals_list)
        module.InsertSetup("Optimization", opt_setup)
        return f"已创建优化: {opt_name}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  10. 求解执行
# ────────────────────────────────────────────────────────────
@mcp.tool()
def validate_design() -> str:
    """验证设计设置是否完整，列出可能的问题。"""
    def _():
        design = maxwell.get_design()
        try:
            design.ValidateDesign()
            return "✅ 设计验证通过"
        except Exception as e:
            return f"⚠️ 设计验证发现问题: {e}"
    return _safe(_)


@mcp.tool()
def analyze(setup_name: str = "Setup1") -> str:
    """
    执行分析求解。
    setup_name: 要运行的分析设置名称
    """
    def _():
        design = maxwell.get_design()
        logger.info("开始求解: %s", setup_name)
        design.Analyze(setup_name)
        return f"✅ 求解完成: {setup_name}"
    return _safe(_)


@mcp.tool()
def analyze_all() -> str:
    """执行所有分析设置。"""
    def _():
        design = maxwell.get_design()
        design.AnalyzeAll()
        return "✅ 所有分析已完成"
    return _safe(_)


@mcp.tool()
def analyze_parametric_sweep(sweep_name: str = "Sweep1") -> str:
    """执行参数化扫描分析。"""
    def _():
        module = maxwell.get_module("Optimetrics")
        module.SolveSetup(sweep_name)
        return f"✅ 参数化扫描完成: {sweep_name}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  11. 结果提取
# ────────────────────────────────────────────────────────────
@mcp.tool()
def get_force(
    force_name: str = "Force1",
    setup_name: str = "Setup1",
) -> str:
    """
    获取力的计算结果。
    force_name: 力参数名称
    setup_name: 分析设置名称
    """
    def _():
        module = maxwell.get_module("Solutions")
        data = module.GetSolutionData(
            f"{setup_name} : LastAdaptive",
            ["NAME:Context", "SimValueContext:=", "1"],
            f"Force({force_name})",
            False,
        )
        if data:
            values = list(data.GetRealDataValuesOf("Force"))
            return json.dumps(
                {
                    "force_name": force_name,
                    "setup": setup_name,
                    "fx": f"{values[0]} N" if len(values) > 0 else "N/A",
                    "fy": f"{values[1]} N" if len(values) > 1 else "N/A",
                    "fz": f"{values[2]} N" if len(values) > 2 else "N/A",
                },
                ensure_ascii=False,
            )
        return "未找到力数据"
    return _safe(_)


@mcp.tool()
def get_torque(
    torque_name: str = "Torque1",
    setup_name: str = "Setup1",
) -> str:
    """
    获取转矩的计算结果。
    torque_name: 转矩参数名称
    """
    def _():
        module = maxwell.get_module("Solutions")
        data = module.GetSolutionData(
            f"{setup_name} : LastAdaptive",
            ["NAME:Context", "SimValueContext:=", "1"],
            f"Torque({torque_name})",
            False,
        )
        if data:
            values = list(data.GetRealDataValuesOf("Torque"))
            return json.dumps(
                {
                    "torque_name": torque_name,
                    "setup": setup_name,
                    "torque_nm": values[0] if values else None,
                },
                ensure_ascii=False,
            )
        return "未找到转矩数据"
    return _safe(_)


@mcp.tool()
def get_flux_linkage(
    winding_name: str = "Winding1",
    setup_name: str = "Setup1",
) -> str:
    """获取磁链。"""
    def _():
        module = maxwell.get_module("Solutions")
        data = module.GetSolutionData(
            f"{setup_name} : LastAdaptive",
            ["NAME:Context", "SimValueContext:=", "1"],
            f"FluxLinkage({winding_name})",
            False,
        )
        if data:
            values = list(data.GetRealDataValuesOf("FluxLinkage"))
            return json.dumps(
                {"winding": winding_name, "flux_linkage": values[0] if values else None},
                ensure_ascii=False,
            )
        return "未找到磁链数据"
    return _safe(_)


@mcp.tool()
def get_inductance(
    winding_name: str = "Winding1",
    setup_name: str = "Setup1",
) -> str:
    """获取电感。"""
    def _():
        module = maxwell.get_module("Solutions")
        data = module.GetSolutionData(
            f"{setup_name} : LastAdaptive",
            ["NAME:Context", "SimValueContext:=", "1"],
            f"Inductance({winding_name})",
            False,
        )
        if data:
            values = list(data.GetRealDataValuesOf("Inductance"))
            return json.dumps(
                {"winding": winding_name, "inductance_h": values[0] if values else None},
                ensure_ascii=False,
            )
        return "未找到电感数据"
    return _safe(_)


@mcp.tool()
def get_solution_info(setup_name: str = "Setup1") -> str:
    """获取求解信息（收敛情况等）。"""
    def _():
        design = maxwell.get_design()
        info = design.GetSolutionInfo()
        return json.dumps(
            {"solution_info": str(info) if info else None},
            ensure_ascii=False,
            indent=2,
        )
    return _safe(_)


@mcp.tool()
def get_convergence_data(setup_name: str = "Setup1") -> str:
    """获取收敛数据。"""
    def _():
        module = maxwell.get_module("Solutions")
        data = module.GetConvergence(setup_name)
        if data:
            passes = [
                {
                    "pass": i + 1,
                    "delta_energy": data.GetDeltaEnergy(i),
                    "max_delta_s": data.GetMaxDeltaS(i),
                }
                for i in range(data.GetNumber())
            ]
            return json.dumps(passes, ensure_ascii=False, indent=2)
        return "无收敛数据"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  12. 场图与报告
# ────────────────────────────────────────────────────────────
@mcp.tool()
def create_field_plot(
    quantity_name: str = "Mag_B",
    plot_name: str = "",
    objects: Optional[list[str]] = None,
    setup_name: str = "Setup1",
) -> str:
    """
    创建场图。
    quantity_name: 场量名称（如 "Mag_B", "Mag_J", "Mag_H", "Vector_B" 等）
    objects: 绘图对象列表（留空则绘制所有实体）
    """
    def _():
        module = maxwell.get_module("FieldsReporter")
        pn = plot_name or f"Plot_{int(time.time() * 1000) % 100000}"
        plot_args = [
            f"NAME:{pn}",
            "QuantityName:=", quantity_name,
            "Solution:=", f"{setup_name} : LastAdaptive",
            "PlotFolder:=", "Field Plots",
        ]
        if objects:
            plot_args.extend(["SurfacesList:=", objects])
        module.CreateFieldPlot(plot_args)
        return f"已创建场图: {pn} ({quantity_name})"
    return _safe(_)


@mcp.tool()
def export_field_plot(
    file_path: str,
    plot_name: str = "",
    file_format: str = "jpg",
) -> str:
    """
    导出场图到文件。
    file_path: 导出路径
    file_format: "jpg", "png", "bmp", "emf"
    """
    def _():
        editor = maxwell.get_editor()
        if plot_name:
            editor.ExportFieldPlot(plot_name, file_path, False)
        else:
            editor.ExportModelImageToFile(
                file_path,
                [
                    "NAME:ImageParameters",
                    "ShowAxis:=", True,
                    "ShowGrid:=", True,
                    "ShowRuler:=", True,
                ],
            )
        return f"已导出: {file_path}"
    return _safe(_)


@mcp.tool()
def export_mesh(
    file_path: str,
    setup_name: str = "Setup1",
) -> str:
    """导出网格到文件。"""
    def _():
        module = maxwell.get_module("Solutions")
        module.ExportMesh(f"{setup_name} : LastAdaptive", file_path)
        return f"已导出网格: {file_path}"
    return _safe(_)


@mcp.tool()
def create_report(
    report_type: str = "Rectangular Plot",
    solution: str = "",
    category: str = "Force",
    quantity: str = "Force1",
    report_name: str = "",
    sweep_variable: str = "",
) -> str:
    """
    创建报告。
    report_type: "Rectangular Plot", "Data Table", "Polar Plot"
    category: "Force", "Torque", "FluxLinkage", "Inductance", "Current", "Voltage"
    quantity: 具体的量名称
    sweep_variable: X 轴扫描变量（留空使用默认）
    """
    def _():
        design = maxwell.get_design()
        setup_module = maxwell.get_module("AnalysisSetup")
        setups = setup_module.GetSetups()
        default_setup = f"{setups[0]} : LastAdaptive" if setups else "Setup1 : LastAdaptive"
        setup = solution or default_setup
        rn = report_name or f"Report_{int(time.time() * 1000) % 100000}"

        module = design.GetModule("ReportSetup")
        module.CreateReport(
            rn,
            report_type,
            "Rectangular Plot",
            setup,
            ["NAME:Context", "SimValueContext:=", "1"],
            [f"{category}({quantity})"],
            [],
            [],
        )
        return f"已创建报告: {rn}"
    return _safe(_)


@mcp.tool()
def export_report_data(
    report_name: str,
    file_path: str,
    file_format: str = "csv",
) -> str:
    """
    导出报告数据。
    file_format: "csv", "tab", "dat"
    """
    def _():
        module = maxwell.get_module("ReportSetup")
        module.ExportToFile(report_name, file_path)
        return f"已导出报告数据: {file_path}"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  13. 视图控制
# ────────────────────────────────────────────────────────────
@mcp.tool()
def fit_view() -> str:
    """自动适配视图。"""
    def _():
        editor = maxwell.get_editor()
        editor.FitAll()
        return "已适配视图"
    return _safe(_)


@mcp.tool()
def set_view(view_name: str = "iso") -> str:
    """
    设置视图方向。
    view_name: "iso", "top", "bottom", "left", "right", "front", "back"
    """
    def _():
        editor = maxwell.get_editor()
        editor.SetView(
            ["NAME:ViewParameters", "ViewDirection:=", view_name, "AutoFit:=", True]
        )
        return f"已设置视图: {view_name}"
    return _safe(_)


@mcp.tool()
def hide_object(object_name: str) -> str:
    """隐藏对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.HideSelection(
            ["NAME:SelectionParameters", "Selections:=", object_name]
        )
        return f"已隐藏: {object_name}"
    return _safe(_)


@mcp.tool()
def show_object(object_name: str) -> str:
    """显示对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.ShowSelection(
            ["NAME:SelectionParameters", "Selections:=", object_name]
        )
        return f"已显示: {object_name}"
    return _safe(_)


@mcp.tool()
def show_all_objects() -> str:
    """显示所有对象。"""
    def _():
        editor = maxwell.get_editor()
        editor.ShowAll()
        return "已显示所有对象"
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  14. 变量/参数管理
# ────────────────────────────────────────────────────────────
@mcp.tool()
def set_variable(name: str, value: str) -> str:
    """
    设置设计变量。
    name: 变量名（如 "RotorAngle", "AirGap"）
    value: 变量值（带单位，如 "30deg", "1mm"）
    """
    def _():
        design = maxwell.get_design()
        design.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:LocalVariableTab",
                    ["NAME:PropServers", "DesignParameters"],
                    ["NAME:ChangedProps", [f"NAME:{name}", "Value:=", value]],
                ],
            ]
        )
        return f"已设置变量: {name} = {value}"
    return _safe(_)


@mcp.tool()
def get_variables() -> str:
    """获取所有设计变量。"""
    def _():
        design = maxwell.get_design()
        variables = design.GetVariables()
        result = {var: design.GetVariableValue(var) for var in (variables or [])}
        return json.dumps(result, ensure_ascii=False, indent=2)
    return _safe(_)


# ────────────────────────────────────────────────────────────
#  15. 批量操作
# ────────────────────────────────────────────────────────────
@mcp.tool()
def run_script(script_content: str, save_before: bool = True) -> str:
    """
    直接执行 ANSYS IronPython 脚本。
    脚本中可使用 oDesktop, oProject, oDesign, oEditor 等对象。
    script_content: 脚本内容
    save_before: 执行前是否先保存项目（默认 True，避免意外丢失数据）
    """
    def _():
        if save_before:
            try:
                proj = maxwell.get_project()
                proj.Save()
                logger.info("脚本执行前已保存项目")
            except Exception as e:
                logger.warning("执行前保存失败: %s", e)
        design = maxwell.get_design()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script_content)
            temp_path = f.name
        try:
            design.EditScript(
                ["NAME:ScriptParameter", "ScriptFile:=", temp_path]
            )
            return "✅ 脚本执行完成"
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return _safe(_)


@mcp.tool()
def execute_console_command(command: str) -> str:
    """
    通过 ANSYS 脚本控制台执行命令。
    command: 单条命令字符串
    """
    def _():
        maxwell.desktop.RunScriptString(command)
        return f"已执行: {command}"
    return _safe(_)


@mcp.tool()
def export_project_archive(
    file_path: str,
    include_results: bool = True,
    include_mesh: bool = True,
) -> str:
    """
    导出项目存档（.aedtz）。
    file_path: 存档路径（应以 .aedtz 结尾）
    """
    def _():
        proj = maxwell.get_project()
        proj.ExportToArchive(
            file_path,
            include_results,
            include_mesh,
            True,  # include geometric data
        )
        return f"已导出存档: {file_path}"
    return _safe(_)


# ══════════════════════════════════════════════════════════════
#  Resources - 可读取的项目信息
# ══════════════════════════════════════════════════════════════
@mcp.resource("maxwell://status")
def get_status_resource() -> str:
    """获取当前 ANSYS Maxwell 连接状态。"""
    try:
        info = maxwell._get_status_dict()
        if not info["connected"]:
            return "未连接"
        pname = info.get("active_project", "N/A")
        dname = info.get("active_design", "N/A")
        return f"已连接 | 项目: {pname} | 设计: {dname}"
    except Exception:
        return "状态未知"


@mcp.resource("maxwell://projects")
def get_projects_resource() -> str:
    """列出所有打开的项目。"""
    try:
        if not maxwell.connected:
            return "未连接"
        names = [
            maxwell.desktop.GetProject(i).GetName()
            for i in range(maxwell.desktop.GetProjectCount())
        ]
        return json.dumps(names, ensure_ascii=False)
    except Exception as e:
        return f"错误: {e}"


# ══════════════════════════════════════════════════════════════
#  入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mcp.run(transport="stdio")
