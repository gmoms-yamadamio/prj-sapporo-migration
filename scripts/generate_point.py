#!/usr/bin/env python3
"""Generate member_point.csv for SB00091."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv
from lib.join_keys import build_member_records, load_cec_members, resolve_member_email
from lib.transforms import SITE_CODE, point_total

RAW = ROOT / "input" / "raw"
CEC = ROOT / "input" / "cec"
OUT = ROOT / "output" / "processed"

POINT_FIELDS = [
    "付与区分", "会員ID", "ポイントキャンペーンコード", "サイトコード",
    "付与ポイント数", "消化ポイント数", "Description",
]


def main() -> None:
    users = read_csv(RAW / "User.csv")
    accounts = read_csv(RAW / "UserAccount.csv")
    points_by_userno = {p["UserNo"]: p for p in read_csv(RAW / "PointBankAccount.csv")}

    cec_path = CEC / "member_export.csv"
    if not cec_path.exists():
        cec_path = CEC / "member_export_sample.csv"
    cec_by_email = load_cec_members(read_csv(cec_path) if cec_path.exists() else [])

    records, _, _ = build_member_records(users, accounts, cec_by_email)
    output_rows: list[dict[str, str]] = []

    for rec in records:
        # UserAccount を持たない会員（1.14）は UserNo が無いためポイントを紐付けられず対象外。
        if not rec.account:
            continue
        pt = points_by_userno.get(rec.account["UserNo"])
        if not pt:
            continue
        total = point_total(pt)
        if total <= 0:
            continue

        output_rows.append({
            "付与区分": "0",
            "会員ID": resolve_member_email(rec),
            "ポイントキャンペーンコード": "migration-shupark",
            "サイトコード": SITE_CODE,
            "付与ポイント数": str(total),
            "消化ポイント数": "",
            "Description": "shupark migration",
        })

    write_csv(OUT / "member_point.csv", output_rows, POINT_FIELDS)

    # 2回目移行チェックリスト 3.17 に対応（1回目では未使用のIDだが害はない）。
    checklist.record(
        OUT.parent / "reports", "3.17", len(output_rows),
        source="generate_point.py",
        note=f"PointBankAccount.csv受領件数={len(points_by_userno)}件（UserNo単位）、うち付与ポイント数>0={len(output_rows)}件",
    )
    print(f"member_point.csv: {len(output_rows)} rows")


if __name__ == "__main__":
    main()
