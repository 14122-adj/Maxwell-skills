#!/usr/bin/env python3
"""
Step 5: Airgap flux density spatial FFT.

修复: 经 bridge 调用 get_field_data / export_data / create_report。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))

from pmsm_config import *  # noqa: F403,F401
from maxwell_bridge import MaxwellBridge

_DR = os.environ.get("MAXWELL_DRY_RUN", "1") == "1"
bridge = MaxwellBridge(dry_run=_DR)


def extract_airgap_flux():
    """Extract airgap B-field and spatial FFT."""

    # 空气隙中径向磁通密度
    bg_data = bridge.get_field_data(
        quantity="Mag_B",
        objects=["Airgap_Outer"],
        setup_name="NoLoad",
    )

    # 导出空间波形数据
    bridge.export_data(
        file_path=f"{EXPORT_DIR}airgap_flux_density.csv",
        expressions=["Mag_B", "Distance"],
        setup_name="NoLoad",
    )

    # 空间 FFT 报告
    bridge.create_report(
        report_name="Airgap_Flux_FFT",
        report_type="Data Table",
        x_quantity="Distance",
        y_quantities=["Mag_B"],
        display_type="Rectangular Plot",
    )

    print(f"Airgap flux data exported to {EXPORT_DIR}")
    return bg_data


if __name__ == "__main__":
    extract_airgap_flux()
    bridge.save_project()