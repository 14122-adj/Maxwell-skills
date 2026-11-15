#!/usr/bin/env python3
"""
Driver — 调用 skill 的 scripts/main.py (MotorModelBuilder) 为 25N·m SPMSM 生成
可运行的 ANSYS Maxwell 2D IronPython 建模脚本（即"画出电机"）。

参数取自 projects/25Nm_PMSM/pmsm_config.py，与现有设计 B 完全一致：
  8 极 12 槽 表贴式永磁同步电机 (SPMSM)
  定子外径 150mm / 内径 93mm / 叠长 160mm / 气隙 0.675mm
  磁钢 N35, Br=1.17T, 极弧系数 0.87
  绕组 Kw=0.933, 每相 81 匝, 每槽 40 导体, AWG15

用法
----
    python gen_maxwell_model.py            # 重新生成 maxwell_model/*.py
    python gen_maxwell_model.py --check    # 只比对、不落盘；有漂移则 rc=1

⚠ 重跑前必读（2026-11-12 G3b 已回灌）
--------------------------------------------------------------------------
2026-11-11 之前，`maxwell_model/` 里的 4 处真机修复只存在于手工改过的
`build_25Nm_SPMSM.py`，模板（`scripts/main.py::_gen_geometry`）里是旧写法，
重跑本脚本会把模型改回不可解。G3b 已把 4 处修复回灌模板，并补上第 5 处
（克隆体实名列表）：当前 `--check` 必须输出「无漂移」。
若这里重新报漂移，说明模板又被改回去了 —— 先修模板，再落盘。
"""
import argparse
import os
import sys

# ---- 让本脚本能 import skill 的 scripts 模块 ----
SKILL_SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SKILL_SCRIPTS))

from main import MotorModelBuilder  # noqa: E402
from motor_config import MotorConfig, MotorType, PMTopology, SlotType  # noqa: E402

# 合并顺序必须 materials → geometry：Maxwell 里对象的 MaterialValue 引用必须已存在，
# 反序会让 build_25Nm_SPMSM.py 在 "SetMaterial" 处直接报 Unknown material。
# （2026-11-11 G3：旧顺序是 setup→geometry→materials，与 tests/test_prepare_batch.py
#  的 test_materials_before_geometry 冲突，本次一并纠正。）
ORDER = ["setup", "materials", "geometry", "winding", "boundary", "mesh", "solver"]


def build_config(load: bool = False, init_deg: float = 0.0) -> MotorConfig:
    """25 N·m 8p12s SPMSM 配置（与 pmsm_config.py 冻结值一致）。

    ``load=False``（默认）→ 空载：三相绕组电流 "0A"，生成物与 G4/M8 基线逐字一致。
    ``load=True`` → M7 负载：三相 9.89 A rms 正弦，初相 120/240/0° 电角、sign=−1（电动），
    口径与手写路径 `m4_build_solve.py` 的 `MAXWELL_CASE=load` 完全相同，
    使两条路径的差异只可能来自建模（几何/网格/线圈），不来自激励。
    ``init_deg`` → `AssignBand` 的 `Init Pos`（机械 deg），G7 多切片用；0.0 时生成物
    与历史基线**逐字一致**（格式化成 "0deg"），这是 `--check` 8/8 的前提。
    """
    return MotorConfig(
        motor_type=MotorType.PMSM,
        rated_power_kw=3.93,
        rated_speed_rpm=1500.0,
        dc_bus_voltage_v=537.0,
        phases=3,

        slot_type=SlotType.PEAR,               # M8：表 2 梨形槽（11 点 + 半圆底）
        pm_topology=PMTopology.SPM,
        pole_pairs=4,
        slots=12,

        # 几何 (mm)
        stator_od=150.0,
        stator_id=93.0,
        rotor_od=91.65,
        rotor_id=30.0,
        airgap=0.675,
        stack_length=160.0,

        # 槽参数 (mm) — 表 2「定子槽尺寸」（docs/PEAR_SLOT_SPEC.md）
        #   Hs2 口径 = 内径 → 槽底**最底端**：x1=48.0 / x2=49.8 / x3=54.25 / x4=59.0，
        #   轭部 = 75 − 59 = 16.0 mm。解析槽面积 93.03 mm²。
        slot_Bs0=0.8,        # 槽口宽
        slot_Hs0=1.5,        # 窄颈高
        slot_Hs1=1.8,        # 斜肩高
        slot_Hs2=12.5,       # 槽深（到槽底最底端）
        slot_Bs1=6.0,        # 肩部宽
        slot_Bs2=9.5,        # 槽底直径
        slot_Rs=4.75,        # 槽底半圆半径 = Bs2/2

        # 永磁体 (mm)
        pm_thickness=1.95,
        pm_pole_arc=0.87,

        # 绕组
        turns_per_phase=81,
        conductors_per_slot=40,
        wire_diameter_mm=1.45,
        slot_fill_factor=0.40,

        # 电气
        rated_current_rms=9.89,
        frequency_hz=100.0,
        phase_resistance=0.48,
        phase_inductance=0.0038,

        # 激励工况（M7）：空载 0A / 负载三相正弦（φ_A/B/C = 120/240/0° 电角、电动）
        load_case=load,
        current_phase_deg=(120.0, 240.0, 0.0),
        current_sign=-1,
        rotor_init_deg=float(init_deg),

        # 材料
        stator_material="M270_35A",
        rotor_material="M270_35A",
        pm_material="N35",
        pm_br_20c=1.17,
        pm_hc_kam=890.0,
        pm_mur=1.05,
        conductor_material="copper",
        shaft_material="steel_stainless",
    )


def render_scripts(cfg: MotorConfig | None = None) -> dict:
    """生成 7 个分脚本（返回 {name: source}）。"""
    cfg = cfg or build_config()
    return MotorModelBuilder(cfg).generate_all_scripts()


def combine(scripts: dict, cfg: MotorConfig | None = None) -> str:
    """把 7 个分脚本合并成单一脚本（表头数值随配置走，不写死）。"""
    cfg = cfg or build_config()
    head = "# -*- coding: utf-8 -*-\n"
    head += '"""\nANSYS Maxwell 2D 自动建模 — 25N·m SPMSM (8p12s)\n'
    head += (
        f"定子外径 {cfg.stator_od:g}mm / 内径 {cfg.stator_id:g}mm / "
        f"叠长 {cfg.stack_length:g}mm / 气隙 {cfg.airgap:g}mm\n"
    )
    head += f"磁钢 {cfg.pm_material} / 极弧系数 {cfg.pm_pole_arc:g} / 绕组 Kw=0.933\n"
    head += '将本文件内容粘贴进 Maxwell 的 IronPython 控制台即可建模。\n"""\n\n'
    body = ""
    for key in ORDER:
        body += f"\n# ============ {key.upper()} ============\n"
        body += scripts[key] + "\n"
    return head + body


def artifacts(out_dir: str, cfg: MotorConfig | None = None) -> dict:
    """返回 {文件名: 内容}，即本目录应有的全部生成物。"""
    cfg = cfg or build_config()
    scripts = render_scripts(cfg)
    files = {f"{key}.py": scripts[key] for key in ORDER}
    files["build_25Nm_SPMSM.py"] = combine(scripts, cfg)
    return files


def write_all(out_dir: str, cfg: MotorConfig | None = None) -> list:
    """落盘全部分脚本 + 合并脚本，返回写出的路径列表。"""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for name, text in artifacts(out_dir, cfg).items():
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        written.append(path)
    return written


def check(out_dir: str, cfg: MotorConfig | None = None) -> list:
    """比对生成物与模板产物，返回有差异/缺失的文件名（空列表 = 无漂移）。"""
    drift = []
    for name, text in artifacts(out_dir, cfg).items():
        path = os.path.join(out_dir, name)
        if not os.path.exists(path):
            drift.append(name + " (missing)")
            continue
        with open(path, encoding="utf-8") as fh:
            if fh.read() != text:
                drift.append(name)
    return drift


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="25N·m SPMSM Maxwell 建模脚本生成器")
    ap.add_argument("--out_dir", default=None,
                    help="输出目录（默认空载 maxwell_model/、负载 maxwell_model_load/）")
    ap.add_argument("--case", choices=("noload", "load"), default="noload",
                    help="激励工况：noload=三相 0A（G4/M8 基线）/ load=M7 三相正弦电流")
    ap.add_argument("--init-deg", type=float, default=0.0,
                    help="AssignBand 的 Init Pos（机械 deg）；G7 斜槽多切片用，0=基线")
    ap.add_argument("--check", action="store_true", help="只比对不落盘；有漂移则 rc=1")
    args = ap.parse_args(argv)

    if args.check and args.case != "noload":
        print("[ERR] --check 只对空载基线有意义：负载生成物不入库、不参与漂移门禁")
        return 2
    out_dir = args.out_dir or os.path.join(
        here, "maxwell_model" if args.case == "noload" else "maxwell_model_load")
    cfg = build_config(load=(args.case == "load"), init_deg=args.init_deg)
    builder = MotorModelBuilder(cfg)
    print("=" * 60)
    print("25N·m SPMSM — Maxwell 2D 建模脚本生成（case=%s）" % args.case)
    print("=" * 60)
    ok = builder.validate()
    print(f"校验结果: {'通过' if ok else '存在错误'}")
    if not ok:
        return 1

    if args.check:
        drift = check(args.out_dir or out_dir, cfg)
        if drift:
            print("[DRIFT] 生成物与模板不一致（先修模板或重跑不带 --check）：")
            for name in drift:
                print("  - " + name)
            return 1
        print(f"[OK] 无漂移：{len(ORDER) + 1} 个生成物与模板逐字一致")
        return 0

    for path in write_all(out_dir, cfg):
        size = os.path.getsize(path)
        print(f"  ✔ {os.path.basename(path)}  ({size} B)")
    print("=" * 60)
    print(f"输出目录: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
