#!/usr/bin/env python3
"""
Mock Maxwell COM 层
===================
在被测服务端进程里注入一个假的 `win32com` 包，使 `D:\\mcp-maxwell\\server.py`
的 `connect_to_maxwell()` 无需真实 ANSYS Maxwell 即可"连接成功"，并且后续工具
(new_project / draw_circle / assign_material / analyze / get_force ...) 走通
完整的 COM 调用链，返回带状态的结果。

用途：本地测试 MCP 连接器的实际调用效果（connector → server → COM → 响应）。

注入方式：在 import 真实 server 之前，把本模块导入一次，它会用假的 win32com
覆盖 `sys.modules['win32com']` 与 `sys.modules['win32com.client']`。
"""
from __future__ import annotations

import sys
import types
from typing import Any


# ══════════════════════════════════════════════════════════════
#  共享状态：所有 mock COM 对象读写同一个 State 单例
# ══════════════════════════════════════════════════════════════
class _State:
    def __init__(self) -> None:
        self.calls: list[tuple] = []          # 调用日志：(role, method, args, kwargs)
        self.version = "2024.2"
        self.projects: list["MockProject"] = []
        self.active_project: "MockProject | None" = None
        self.active_design: "MockDesign | None" = None
        self.objects: dict[str, list[str]] = {
            "Solids": [], "Sheets": [], "Lines": [], "UnclosedSolids": []}
        self.variables: dict[str, str] = {}
        self.materials: dict[str, dict] = {}
        self.excitations: list[str] = []
        self.windings: list[str] = []
        self.setups: list[str] = []
        self.analyzed: list[str] = []
        self.reports: list[str] = []
        self.field_plots: list[str] = []
        self.design_type = "Maxwell 2D"
        self.solution_type = "Transient"
        self.units = "mm"

    def reset(self) -> None:
        self.__init__()


STATE = _State()


def _log(role: str, method: str, args: tuple, kwargs: dict) -> None:
    STATE.calls.append((role, method, args, kwargs))


def _extract_name(attrs: Any) -> str | None:
    """从 ANSYS Attributes 列表里抽出 'Name:=' 后的值。

    兼容两种形态：
      - Attributes 块：['NAME:Attributes','Name:=',name,...]
      - Material 块：['NAME:<material_name>', 'k:=', v, ...]  → 取首元素去前缀
    """
    try:
        lst = list(attrs)
    except TypeError:
        return None
    # 形态1：'Name:=' 键
    for i, v in enumerate(lst):
        if v == "Name:=" and i + 1 < len(lst):
            return str(lst[i + 1])
    # 形态2：首元素 'NAME:xxx'
    if lst and isinstance(lst[0], str) and lst[0].startswith("NAME:"):
        return lst[0][len("NAME:"):]
    return None


def _extract_kv(args: Any, key: str) -> Any:
    """从 ['NAME:...','key:=',val,...] 里取 key 后的值。"""
    try:
        lst = list(args)
    except TypeError:
        return None
    for i, v in enumerate(lst):
        if v == f"{key}:=" and i + 1 < len(lst):
            return lst[i + 1]
    return None


# ══════════════════════════════════════════════════════════════
#  Mock COM 对象图
# ══════════════════════════════════════════════════════════════
class _Recorder:
    """未知方法的兜底：记录调用，返回 None（不抛）。"""

    def __init__(self, role: str, name: str):
        self._role = role
        self._name = name

    def __call__(self, *args, **kwargs):
        _log(self._role, self._name, args, kwargs)
        return None


class MockSolutionData:
    """get_force/get_torque 等返回的解数据。"""

    def __init__(self, values: list[float]):
        self._values = values

    def GetRealDataValuesOf(self, name: str) -> list[float]:
        _log("SolutionData", "GetRealDataValuesOf", (name,), {})
        return list(self._values)


class MockConvergence:
    def __init__(self, passes: int = 5):
        self._n = passes

    def GetNumber(self) -> int:
        return self._n

    def GetDeltaEnergy(self, i: int) -> float:
        return 0.1 / (10 ** i)

    def GetMaxDeltaS(self, i: int) -> float:
        return 0.2 / (10 ** i)


class MockModule:
    """BoundarySetup / MeshSetup / Solutions / FieldsReporter 等模块。"""

    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, method: str):  # 注意：仅对未定义方法触发
        def _fn(*args, **kwargs):
            _log(f"Module:{self._name}", method, args, kwargs)
            # 几个需要返回值的特殊方法
            if method == "GetSolutionData":
                return MockSolutionData([1.23, 4.56, 7.89])
            if method == "GetConvergence":
                return MockConvergence(5)
            return None
        return _fn


class MockEditor:
    role = "Editor"

    def GetObjectsInGroup(self, group: str) -> list[str]:
        _log(self.role, "GetObjectsInGroup", (group,), {})
        return list(STATE.objects.get(group, []))

    def _create(self, method: str, params, attrs, group: str):
        _log(self.role, method, (params, attrs), {})
        name = _extract_name(attrs) or f"{method}_{len(STATE.calls)}"
        STATE.objects.setdefault(group, []).append(name)
        return name

    def CreateBox(self, params, attrs):       return self._create("CreateBox", params, attrs, "Solids")
    def CreateCylinder(self, params, attrs):  return self._create("CreateCylinder", params, attrs, "Solids")
    def CreateRectangle(self, params, attrs): return self._create("CreateRectangle", params, attrs, "Sheets")
    def CreateCircle(self, params, attrs):    return self._create("CreateCircle", params, attrs, "Sheets")
    def CreatePolyline(self, *a, **k):
        # CreatePolyline 签名多变，兜底
        _log(self.role, "CreatePolyline", a, k)
        name = "Polyline_0"
        STATE.objects.setdefault("Lines", []).append(name)
        return name
    def CreateRegion(self, params):
        _log(self.role, "CreateRegion", (params,), {})
        STATE.objects.setdefault("Solids", []).append("Region")
        return "Region"

    def Unite(self, sel, params):      _log(self.role, "Unite", (sel, params), {}); return None
    def Subtract(self, sel, params):   _log(self.role, "Subtract", (sel, params), {}); return None
    def Intersect(self, sel, params):  _log(self.role, "Intersect", (sel, params), {}); return None
    def Move(self, *a, **k):           _log(self.role, "Move", a, k); return None
    def DuplicateAlongLine(self, *a, **k):
        _log(self.role, "DuplicateAlongLine", a, k)
        return [0]  # 返回克隆索引列表
    def Scale(self, *a, **k):          _log(self.role, "Scale", a, k); return None
    def ChangeProperty(self, *a, **k): _log(self.role, "ChangeProperty", a, k); return None
    def FitAll(self):                  _log(self.role, "FitAll", (), {}); return None
    def SetView(self, *a, **k):        _log(self.role, "SetView", a, k); return None
    def HideSelection(self, *a, **k):  _log(self.role, "HideSelection", a, k); return None
    def ShowSelection(self, *a, **k):  _log(self.role, "ShowSelection", a, k); return None
    def ShowAll(self):                 _log(self.role, "ShowAll", (), {}); return None
    def ExportFieldPlot(self, *a, **k): _log(self.role, "ExportFieldPlot", a, k); return None
    def ExportModelImageToFile(self, *a, **k):
        _log(self.role, "ExportModelImageToFile", a, k); return None

    def __getattr__(self, method: str):
        return _Recorder(self.role, method)


class MockDefinitionManager:
    role = "DefinitionManager"

    def AddMaterial(self, args):
        _log(self.role, "AddMaterial", (args,), {})
        name = _extract_name(args) or f"Mat_{len(STATE.materials)}"
        STATE.materials[name] = args
        return None

    def EditMaterial(self, name, args):
        _log(self.role, "EditMaterial", (name, args), {})
        STATE.materials[name] = args
        return None

    def __getattr__(self, method: str):
        return _Recorder(self.role, method)


class MockDesign:
    role = "Design"

    def __init__(self, name: str, design_type: str, solution_type: str):
        self._name = name
        STATE.design_type = design_type
        STATE.solution_type = solution_type

    def GetName(self) -> str:
        return self._name

    def GetDesignType(self) -> str:
        return STATE.design_type

    def GetSolutionType(self) -> str:
        return STATE.solution_type

    def SetActiveEditor(self, name: str) -> MockEditor:
        _log(self.role, "SetActiveEditor", (name,), {})
        return MockEditor()

    def GetModule(self, name: str) -> MockModule:
        _log(self.role, "GetModule", (name,), {})
        return MockModule(name)

    def ValidateDesign(self):
        _log(self.role, "ValidateDesign", (), {})
        return True

    def Analyze(self, setup_name: str):
        _log(self.role, "Analyze", (setup_name,), {})
        STATE.analyzed.append(setup_name)
        return None

    def AnalyzeAll(self):
        _log(self.role, "AnalyzeAll", (), {})
        STATE.analyzed.extend(STATE.setups)
        return None

    def GetSolutionInfo(self):
        _log(self.role, "GetSolutionInfo", (), {})
        return {"converged": True, "passes": 5}

    def ChangeProperty(self, *a, **k):
        _log(self.role, "ChangeProperty", a, k)
        # set_variable 走 ChangeProperty，解析变量名/值
        try:
            tabs = a[0]
            for tab in tabs[1:] if isinstance(tabs, list) else []:
                if isinstance(tab, list) and tab and tab[0] == "NAME:LocalVariableTab":
                    for blk in tab[1:]:
                        if isinstance(blk, list) and blk and blk[0] == "NAME:ChangedProps":
                            for prop in blk[1:]:
                                if isinstance(prop, list) and len(prop) >= 3:
                                    vn = prop[0].replace("NAME:", "")
                                    STATE.variables[vn] = str(prop[2])
        except Exception:
            pass
        return None

    def GetVariables(self) -> list[str]:
        _log(self.role, "GetVariables", (), {})
        return list(STATE.variables.keys())

    def GetVariableValue(self, name: str) -> str:
        _log(self.role, "GetVariableValue", (name,), {})
        return STATE.variables.get(name, "0")

    def ExportDesignData(self, *a, **k):
        _log(self.role, "ExportDesignData", a, k); return None

    def EditScript(self, *a, **k):
        _log(self.role, "EditScript", a, k); return None

    def __getattr__(self, method: str):
        return _Recorder(self.role, method)


class MockProject:
    role = "Project"

    def __init__(self, name: str):
        self._name = name
        self._designs: list[MockDesign] = []

    def GetName(self) -> str:
        return self._name

    def Save(self):
        _log(self.role, "Save", (), {}); return None

    def SaveAs(self, path, flag):
        _log(self.role, "SaveAs", (path, flag), {}); return None

    def Close(self):
        _log(self.role, "Close", (), {}); return None

    def SetActiveDesign(self, name: str) -> MockDesign:
        _log(self.role, "SetActiveDesign", (name,), {})
        for d in self._designs:
            if d._name == name:
                STATE.active_design = d
                return d
        # 不存在则建一个（宽容）
        d = MockDesign(name, STATE.design_type, STATE.solution_type)
        self._designs.append(d)
        STATE.active_design = d
        return d

    def GetActiveDesign(self) -> "MockDesign | None":
        _log(self.role, "GetActiveDesign", (), {})
        return STATE.active_design

    def InsertDesign(self, design_type: str, name: str, solution_type: str, _):
        _log(self.role, "InsertDesign", (design_type, name, solution_type), {})
        d = MockDesign(name, design_type, solution_type)
        self._designs.append(d)
        STATE.active_design = d
        return d

    def GetTopDesignList(self) -> list[str]:
        _log(self.role, "GetTopDesignList", (), {})
        return [d._name for d in self._designs]

    def DeleteDesign(self, name: str):
        _log(self.role, "DeleteDesign", (name,), {})
        self._designs = [d for d in self._designs if d._name != name]
        return None

    def GetDefinitionManager(self) -> MockDefinitionManager:
        _log(self.role, "GetDefinitionManager", (), {})
        return MockDefinitionManager()

    def ExportToArchive(self, *a, **k):
        _log(self.role, "ExportToArchive", a, k); return None

    def __getattr__(self, method: str):
        return _Recorder(self.role, method)


class MockDesktop:
    role = "Desktop"

    def GetVersion(self) -> str:
        return STATE.version

    def GetAppDesktop(self) -> "MockDesktop":
        _log(self.role, "GetAppDesktop", (), {})
        return self

    def NewProject(self) -> MockProject:
        _log(self.role, "NewProject", (), {})
        p = MockProject(f"Project{len(STATE.projects) + 1}")
        STATE.projects.append(p)
        STATE.active_project = p
        return p

    def OpenProject(self, path: str) -> MockProject:
        _log(self.role, "OpenProject", (path,), {})
        p = MockProject(path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].replace(".aedt", ""))
        STATE.projects.append(p)
        STATE.active_project = p
        return p

    def GetActiveProject(self) -> "MockProject | None":
        _log(self.role, "GetActiveProject", (), {})
        return STATE.active_project

    def GetProject(self, i: int) -> MockProject:
        _log(self.role, "GetProject", (i,), {})
        return STATE.projects[i]

    def GetProjectCount(self) -> int:
        _log(self.role, "GetProjectCount", (), {})
        return len(STATE.projects)

    def SetActiveProject(self, name: str) -> MockProject:
        _log(self.role, "SetActiveProject", (name,), {})
        for p in STATE.projects:
            if p._name == name:
                STATE.active_project = p
                return p
        return STATE.active_project

    def RunScriptString(self, command: str):
        _log(self.role, "RunScriptString", (command,), {})
        return None

    def __getattr__(self, method: str):
        return _Recorder(self.role, method)


# ══════════════════════════════════════════════════════════════
#  注入假 win32com 包
# ══════════════════════════════════════════════════════════════
def install() -> None:
    """把假的 win32com / win32com.client 注入 sys.modules。"""
    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")

    def _dispatch(prog_id: str = "") -> MockDesktop:
        _log("win32com.client", "Dispatch", (prog_id,), {})
        return MockDesktop()

    client.Dispatch = _dispatch
    win32com.client = client
    # 标记为已安装，便于诊断
    win32com.__mock__ = True
    sys.modules["win32com"] = win32com
    sys.modules["win32com.client"] = client


# 自动安装：import 本模块即生效
install()
