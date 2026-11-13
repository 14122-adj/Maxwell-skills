#!/usr/bin/env python3
"""Step 2: 自定义材料定义（N/S极磁钢 + 铁芯）"""
import ScriptEnv
ScriptEnv.Initialize("Ansoft.ElectronicsDesktop")
oDesktop = ScriptEnv.GetDesktop()
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
            "Magnitude:=", "-890000.0A_per_meter",
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
            "Magnitude:=", "-890000.0A_per_meter",
            "DirComp1:=", "-1",
            "DirComp2:=", "0",
            "DirComp3:=", "0"
        ],
        "mass_density:=", "7400",
        "youngs_modulus:=", "147000000000",
    ])

print("Materials defined: NdFe35_N, NdFe35_S")
# 铁芯材料（G4：模板此前从未定义/绑定，定转子默认是 vacuum）
STEEL_MATS = ['M270_35A']
for _m in STEEL_MATS:
    oDefinitionManager.EditMaterial(
        _m, ["NAME:" + _m, "CoordinateSystemType:=", "Cartesian",
             "BulkOrSurfaceType:=", 1,
             ["NAME:PhysicsTypes", "set:=", ["Electromagnetic", "Thermal",
                                               "Structural"]],
             "permittivity:=", "1", "permeability:=", "1000",
             "conductivity:=", "2000000", "dielectric_loss_tangent:=", "0",
             "magnetic_loss_tangent:=", "0", "mass_density:=", "7650",
             "youngs_modulus:=", "200000000000"])
