# -*- coding: utf-8 -*-
"""
m3_fix.py — 打开 M2_25Nm.aedt，补齐 M3：
  1) ModelDepth = 160mm（当前是默认 1meter）
  2) 定义并赋给 StatorOuter / RotorOuter 材料 M270_35A
  3) Region 上 VectorPotential = 0
  4) 插入 Transient Setup1
每步保存 checkpoint，便于定位失败点。
"""
import time
import traceback

LOG = r"D:/ANSYS_Run/m3_fix_progress.log"
SRC = r"D:/ANSYS_Run/M2_25Nm.aedt"
DST = r"D:/ANSYS_Run/M3_25Nm.aedt"


def log(msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(line)
    f = open(LOG, "a")
    f.write(line + "\n")
    f.close()


def main():
    open(LOG, "w").close()
    log("start")
    oProject = None
    try:
        oProject = oDesktop.OpenProject(SRC)
        log("opened " + SRC)
        oDesign = oProject.SetActiveDesign("Motor_Design")
        log("design=Motor_Design")

        # 1) ModelDepth
        oDesign.SetDesignSettings(
            ["NAME:DesignSettingsData",
             "ModelDepth:=", "160mm",
             "PreserveTransientSolution:=", False,
             "ComputeTransientInductance:=", True])
        log("ModelDepth=160mm set")
        oProject.SaveAs(r"D:/ANSYS_Run/M3_step1.aedt", True)
        log("checkpoint step1")

        # 2) 核心材料 M270_35A
        oDef = oProject.GetDefinitionManager()
        try:
            oDef.EditMaterial("M270_35A",
                ["NAME:M270_35A", "CoordinateSystemType:=", "Cartesian",
                 "BulkOrSurfaceType:=", 1,
                 ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal", "Structural"]],
                 "permittivity:=", "1", "permeability:=", "1000",
                 "conductivity:=", "2000000", "dielectric_loss_tangent:=", "0",
                 "magnetic_loss_tangent:=", "0", "mass_density:=", "7650",
                 "youngs_modulus:=", "200000000000"])
            log("material M270_35A defined")
        except Exception:
            log("material define warn:\n" + traceback.format_exc())

        oEditor = oDesign.SetActiveEditor("3D Modeler")
        for obj in ("StatorOuter", "RotorOuter"):
            try:
                oEditor.ChangeProperty(
                    ["NAME:AllTabs",
                     ["NAME:Geometry3DAttributeTab",
                      ["NAME:PropServers", obj],
                      ["NAME:ChangedProps", ["NAME:Material", "Value:=", '"M270_35A"']]]])
                log("material assigned: " + obj)
            except Exception:
                log("assign fail " + obj + ":\n" + traceback.format_exc())
        oProject.SaveAs(r"D:/ANSYS_Run/M3_step2.aedt", True)
        log("checkpoint step2")

        # 3) VectorPotential = 0 on Region
        try:
            oBnd = oDesign.GetModule("BoundarySetup")
            # .aedt stores this boundary as Edges(<id>), not by object name.
            edges = [int(e) for e in oEditor.GetEdgeIDsFromObject("Region")]
            log("Region edges: " + str(edges))
            oBnd.AssignVectorPotential(
                ["NAME:VectorPotential1", "Edges:=", edges,
                 "Value:=", "0", "CoordinateSystem:=", ""])
            log("VectorPotential on Region ok")
        except Exception:
            log("VP fail:\n" + traceback.format_exc())

        # 4) Transient setup
        try:
            oAnaly = oDesign.GetModule("AnalysisSetup")
            oAnaly.InsertSetup("Transient",
                ["NAME:Setup1", "StopTime:=", "0.0200s", "TimeStep:=", "0.000050s",
                 "SaveFieldsType:=", "Every N Steps", "N:=", "1",
                 "UseAdaptiveTimeStep:=", False, "NonlinearSolverResidual:=", "0.0001",
                 "SmoothBHCurve:=", False])
            log("Transient Setup1 inserted")
        except Exception:
            log("setup fail:\n" + traceback.format_exc())

        oProject.SaveAs(DST, True)
        log("SAVED " + DST)
        log("DONE")
    except Exception:
        log("FATAL:\n" + traceback.format_exc())
        if oProject is not None:
            try:
                oProject.SaveAs(r"D:/ANSYS_Run/M3_partial.aedt", True)
                log("partial saved")
            except Exception:
                log("partial save failed")


main()
