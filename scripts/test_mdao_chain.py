#!/usr/bin/env python3
"""
MDAO 最小可验证流程测试
验证两个全流程（电机MDAO + IGBT可靠性）的 key 传递链路是否真正连通

注意：该脚本依赖于 mdao_orchestrator.py 同级目录实现。
"""

import os
import tempfile
import json
from mdao_orchestrator import MDAOConfig, MDAOOrchestrator


def check_key_chain(label, source_dict, source_keys, target_dict, target_keys):
    """检查 key 传递链路"""
    issues = []
    for sk in source_keys:
        if sk not in source_dict:
            issues.append("  [MISSING] source missing output key: %s" % sk)
        else:
            val = source_dict[sk]
            if val is None:
                issues.append("  [NONE] source output key is None: %s" % sk)
    for tk in target_keys:
        if tk not in target_dict:
            issues.append("  [MISSING] target missing input key: %s" % tk)

    if issues:
        print("[%s] [FAIL] issues found:" % label)
        for i in issues:
            print(i)
        return False
    else:
        print("[%s] [OK] key chain complete" % label)
        return True


def test_motor_mdao_chain():
    """测试电机MDAO key传递"""
    print("\n" + "=" * 60)
    print("Test 1: Motor MDAO key chain")
    print("=" * 60)

    # 使用临时目录模拟工作空间，确保文件路径正确性
    temp_dir = tempfile.mkdtemp(prefix="mdao_test_")
    config = MDAOConfig(
        project_name="test_motor",
        work_dir=os.path.join(temp_dir, "workspace"), # 设定内部工作目录
        dry_run=True,
        enable_database=False,
    )
    # 确保MDAOOrchestrator使用新的上下文，这是关键步骤。
    orch = MDAOOrchestrator(config)

    motor_params = {
        "power": 10000, "speed": 6000, "voltage": 310,
        "poles": 8, "slots": 48, "outer_dia": 180, "length": 120,
        "cooling": "water",
    }

    em = orch._run_electromagnetic(motor_params)
    print("  EM output keys: %s" % list(em.keys()))


    struct_input = {
        "electromagnetic_force": em.get("radial_force_density"),
        "speed": motor_params.get("speed", 3000),
        "rotor_radius": motor_params.get("outer_dia", 80) / 2,
    }
    struct = orch._run_structural(struct_input)
    print("  Structural output keys: %s" % list(struct.keys()))
    em_used = struct.get("em_force_density", 0) > 0
    print("  Structural uses EM force: %s" % em_used)


    thermal_input = {
        "copper_loss": em.get("copper_loss"),
        "iron_loss": em.get("iron_loss"),
        "pm_eddy_loss": em.get("pm_eddy_loss"),
        "cooling": motor_params.get("cooling", "water"),
    }
    thermal = orch._run_thermal(thermal_input)
    print("  Thermal output keys: %s" % list(thermal.keys()))

    ok1 = check_key_chain("EM->Structural", em, ["radial_force_density"], struct_input, ["electromagnetic_force"])
    ok2 = check_key_chain("EM->Thermal", em, ["copper_loss", "iron_loss", "pm_eddy_loss"], thermal_input, ["copper_loss", "iron_loss", "pm_eddy_loss"])

    if not em_used:
        print("  [BROKEN] Structural sim does NOT use EM force! EM->Structural coupling broken")
        ok1 = False


    orch.close()
    return ok1 and ok2


def test_igbt_chain():
    """测试IGBT三阶段key传递"""
    print("\n" + "=" * 60)
    print("Test 2: IGBT 3-phase key chain")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp(prefix="mdao_test_")
    config = MDAOConfig(
        project_name="test_igbt",
        work_dir=os.path.join(temp_dir, "workspace"), # 设定内部工作目录
        dry_run=True,
        enable_database=False,
    )
    orch = MDAOOrchestrator(config)

    igbt_params = {
        "cycle_period": 120, "power_density_igbt": 1.69e9, "power_density_frd": 1.14e9,
        "solder_thickness": 80, "void_ratio": 0.0, "env_temp": 40,
        "num_cycles": 3,
    }

    temp = orch._run_igbt_thermal(igbt_params)
    print("  Thermal output keys: %s" % list(temp.keys()))


    deform_input = {
        "temp_field": temp.get("max_junction_temp"),
        "solder_temp": temp.get("max_solder_temp"),
        "solder_thickness": igbt_params.get("solder_thickness", 80),
    }
    deform = orch._run_igbt_deformation(deform_input)
    print("  Deformation output keys: %s" % list(deform.keys()))
    print("  Deformation uses temp: " + str("mismatch_strain" in deform and abs(deform["mismatch_strain"]) > 1e-6))


    stress_input = {
        "temp_field": temp.get("max_junction_temp"),
        "deformation": deform.get("max_displacement"),
        "solder_thickness": igbt_params.get("solder_thickness", 80),
    }
    stress = orch._run_igbt_stress(stress_input)
    print("  Stress output keys: %s" % list(stress.keys()))
    print("  Stress uses temp/deformation: " + str((("thermal_stress" in stress and abs(stress["thermal_stress"]) > 10) or ("mech_stress" in stress and abs(stress["mech_stress"]) > 10))))


    ok1 = check_key_chain("Thermal->Deformation", temp, ["max_junction_temp", "max_solder_temp"], deform_input, ["temp_field", "solder_temp"])
    ok2 = check_key_chain("Deformation->Stress", deform, ["max_displacement"], stress_input, ["deformation"])

    deform_used = deform.get("mismatch_strain", 0) != 0
    stress_used = ("thermal_stress" in stress and abs(stress["thermal_stress"]) > 10) or ("mech_stress" in stress and abs(stress["mech_stress"]) > 10)

    if not deform_used:
        print("  [BROKEN] Deformation sim does NOT use temperature input!")
        ok1 = False
    if not stress_used:
        print("  [BROKEN] Stress sim does NOT use temperature/deformation input!")
        ok2 = False


    orch.close()
    return ok1 and ok2


if __name__ == "__main__":
    # 确保当前工作目录是脚本所在位置，便于相对导入和资源查找
    print(f"--- Running tests from: {os.path.abspath(__file__)} ---")

    r1 = test_motor_mdao_chain()
    r2 = test_igbt_chain()

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    # 判定是否成功从工具的退出码和输出结果推断
    if r1 and r2:
        print(f"Motor MDAO key chain: [OK] PASS")
        print(f"IGBT 3-phase key chain: [OK] PASS")
        print("\n所有数据流链已连接完成 [PASS]")
        exit(0)
    else:
        print(f"Motor MDAO key chain: {'[FAIL] BROKEN' if not r1 else '[OK] PASS'}")
        print(f"IGBT 3-phase key chain: {'[FAIL] BROKEN' if not r2 else '[OK] PASS'}")
        print("\n数据流链路断裂，需要修复 [FAIL]")
        exit(1)