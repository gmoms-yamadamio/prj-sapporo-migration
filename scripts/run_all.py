#!/usr/bin/env python3
"""Run all ETL generators in dependency order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "generate_receipt_stats.py",
    "generate_member.py",
    "generate_address.py",
    "generate_point.py",
    "generate_order.py",
    "generate_order_detail.py",
    "generate_edge_case_samples.py",
    "generate_product_reference.py",
    "render_checklist_report.py",
]


def main() -> None:
    root = Path(__file__).resolve().parent
    for name in SCRIPTS:
        path = root / name
        print(f"\n=== {name} ===")
        result = subprocess.run([sys.executable, str(path)], cwd=root.parent)
        if result.returncode != 0:
            sys.exit(result.returncode)
    print("\nAll generators completed.")


if __name__ == "__main__":
    main()
