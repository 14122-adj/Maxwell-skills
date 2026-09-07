#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 2: 自定义材料定义（N/S极磁钢）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = __import__("sys").modules["__main__"].oDesktop
oProject = oDesktop.GetActiveProject()
oDefinitionManager = oProject.GetDefinitionManager()

# N极磁钢（磁化方向径向向外）
oDefinitionManager.EditMaterial("NdFe35_N",
    [
        "NAME:NdFe35_N",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "625000",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-890000A_per_meter",
            "DirComp1:=", "1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "7400",
        "youngs_modulus:=", "147000000000",
    ])

# S极磁钢（磁化方向径向向内）
oDefinitionManager.EditMaterial("NdFe35_S",
    [
        "NAME:NdFe35_S",
        "CoordinateSystemType:=", "Cylindrical",
        "BulkOrSurfaceType:=", 1,
        ["NAME:PhysicsTypes", "set:=", ["Electromagnetic","Thermal","Structural"]],
        "permittivity:=", "1",
        "permeability:=", "1.0997785406",
        "conductivity:=", "625000",
        "dielectric_loss_tangent:=", "0",
        "magnetic_loss_tangent:=", "0",
        [
            "NAME:magnetic_coercivity",
            "property_type:=", "VectorProperty",
            "Magnitude:=", "-890000A_per_meter",
            "DirComp1:=", "-1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "7400",
        "youngs_modulus:=", "147000000000",
    ])

print("Materials defined: NdFe35_N, NdFe35_S")
