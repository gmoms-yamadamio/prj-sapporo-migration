#!/usr/bin/env python3
"""Generate member address book import CSV."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv
from lib.join_keys import build_member_records, load_cec_members, resolve_member_email
from lib.transforms import is_deleted, join_name, prefecture_name

RAW = ROOT / "input" / "raw"
CEC = ROOT / "input" / "cec"
OUT = ROOT / "output" / "processed"

ADDRESS_FIELDS = [
    "操作区分", "会員メールアドレス", "アドレス名", "お名前", "お名前（フリガナ）",
    "郵便番号", "都道府県", "市区町村", "番地", "建物名等", "電話番号1",
]


def main() -> None:
    users = read_csv(RAW / "User.csv")
    accounts = read_csv(RAW / "UserAccount.csv")
    user_addresses = read_csv(RAW / "UserAddress.csv")
    addresses = {a["addressId"]: a for a in read_csv(RAW / "Address.csv")}

    cec_path = CEC / "member_export.csv"
    if not cec_path.exists():
        cec_path = CEC / "member_export_sample.csv"
    cec_by_email = load_cec_members(read_csv(cec_path) if cec_path.exists() else [])

    records, _, _ = build_member_records(users, accounts, cec_by_email)
    # UserAccount を持たない会員（1.14）は UserNo が無いため住所を紐付けられず対象外。
    record_by_userno = {r.account["UserNo"]: r for r in records if r.account}

    output_rows: list[dict[str, str]] = []
    skipped_no_address: list[dict[str, str]] = []
    for ua in user_addresses:
        rec = record_by_userno.get(ua["UserNo"])
        if not rec:
            continue
        address_id = ua.get("AddressId") or ua.get("addressId", "")
        addr = addresses.get(address_id)
        if not addr:
            skipped_no_address.append({"UserNo": ua["UserNo"], "AddressId": address_id})
            continue

        output_rows.append({
            "操作区分": "C",
            "会員メールアドレス": resolve_member_email(rec),
            "アドレス名": ua.get("AddressName", ""),
            "お名前": join_name(addr.get("recipientlastname", ""), addr.get("recipientfirstname", "")),
            "お名前（フリガナ）": join_name(addr.get("recipientlastnamekana", ""), addr.get("recipientfirstnamekana", "")),
            "郵便番号": addr.get("zipCode", ""),
            "都道府県": addr.get("pref", "") if addr.get("pref", "") != "***" else "",
            "市区町村": addr.get("city", ""),
            "番地": addr.get("street", ""),
            "建物名等": addr.get("building", ""),
            "電話番号1": addr.get("tel", ""),
        })

    write_csv(OUT / "address_import.csv", output_rows, ADDRESS_FIELDS)
    from lib.csv_io import write_report
    write_report(ROOT / "output" / "reports" / "address_id_not_found.csv", skipped_no_address, ["UserNo", "AddressId"])

    # 2回目移行チェックリスト 3.16 に対応（1回目では未使用のIDだが害はない）。
    checklist.record(
        ROOT / "output" / "reports", "3.16", len(output_rows),
        source="generate_address.py",
        note=f"UserAddress.csv受領件数={len(user_addresses)}件、address_id_not_found（住所ID不明でスキップ）={len(skipped_no_address)}件",
    )
    print(f"address_import.csv: {len(output_rows)} rows (skipped: {len(skipped_no_address)})")


if __name__ == "__main__":
    main()
