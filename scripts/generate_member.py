#!/usr/bin/env python3
"""Generate member import CSVs (create/update split) and match report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv, write_report
from lib.join_keys import build_member_records, excluded_deleted_members, load_cec_members
from lib.transforms import SITE_CODE, format_birthday, join_name, mail_optin, prefecture_name, sex_code

RAW = ROOT / "input" / "raw"
CEC = ROOT / "input" / "cec"
OUT = ROOT / "output" / "processed"
REPORTS = ROOT / "output" / "reports"

# パターンA（新規登録`C`）: 会員CSV.md「項目マッピング（パターンA）」
CREATE_FIELDS = [
    "操作区分", "名前", "名前読み", "メールアドレス", "生年月日", "性別",
    "電話番号1", "郵便番号", "都道府県", "市区町村", "番地", "建物名等",
    "登録元サイトID", "[カスタム]メールマガジン配信（シュパーク）", "[カスタム]旧会員ID",
    "[カスタム]法人コード",
]

# パターンB（更新のみ`U`）: 会員CSV.md「項目マッピング（パターンB）」
# 氏名・メール・住所等の基本属性は赤星商店データを維持するため出力しない。
UPDATE_FIELDS = [
    "操作区分", "会員ID", "[カスタム]メールマガジン配信（シュパーク）", "[カスタム]旧会員ID",
]


def build_create_row(user: dict[str, str]) -> dict[str, str]:
    return {
        "操作区分": "C",
        "名前": join_name(user.get("LastName", ""), user.get("FirstName", "")),
        "名前読み": join_name(user.get("LastNameKana", ""), user.get("FirstNameKana", "")),
        "メールアドレス": user.get("Email", ""),
        "生年月日": format_birthday(user.get("Birthday", "")),
        "性別": sex_code(user.get("Sex", "")),
        "電話番号1": user.get("PhoneNumber", ""),
        "郵便番号": user.get("ZipCode", ""),
        "都道府県": prefecture_name(user.get("Prefecture", "")),
        "市区町村": user.get("City", ""),
        "番地": user.get("Street", ""),
        "建物名等": user.get("Building", ""),
        "登録元サイトID": SITE_CODE,
        "[カスタム]メールマガジン配信（シュパーク）": mail_optin(user.get("IsApproveMailDelivery", "0")),
        "[カスタム]旧会員ID": user["Id"],  # User.Id（確定。UserNo ではない）
        "[カスタム]法人コード": "",  # 一律ブランク（確定。法人CSV・法人会員は対象外）
    }


def build_update_row(user: dict[str, str], cec_member_id: str) -> dict[str, str]:
    return {
        "操作区分": "U",
        "会員ID": cec_member_id,
        "[カスタム]メールマガジン配信（シュパーク）": mail_optin(user.get("IsApproveMailDelivery", "0")),
        "[カスタム]旧会員ID": user["Id"],
    }


def main() -> None:
    users = read_csv(RAW / "User.csv")
    accounts = read_csv(RAW / "UserAccount.csv")

    cec_path = CEC / "member_export.csv"
    if not cec_path.exists():
        cec_path = CEC / "member_export_sample.csv"
    cec_rows = read_csv(cec_path) if cec_path.exists() else []
    cec_by_email = load_cec_members(cec_rows)

    records, unmatched, duplicates = build_member_records(users, accounts, cec_by_email)

    create_rows: list[dict[str, str]] = []
    update_rows: list[dict[str, str]] = []
    for rec in records:
        if rec.pattern == "U":
            update_rows.append(build_update_row(rec.user, rec.cec_member_id))
        else:
            create_rows.append(build_create_row(rec.user))

    write_csv(OUT / "member_import_create.csv", create_rows, CREATE_FIELDS)
    write_csv(OUT / "member_import_update.csv", update_rows, UPDATE_FIELDS)
    write_report(REPORTS / "member_unmatched_accounts.csv", unmatched, ["UserNo", "UserName", "reason"])
    write_report(
        REPORTS / "excluded_deleted_members.csv",
        excluded_deleted_members(users, accounts),
        ["UserNo", "UserId", "Email", "DeletedAt"],
    )
    write_report(
        REPORTS / "duplicate_emails.csv",
        duplicates,
        ["UserNo", "UserId", "Email", "UpdatedAt", "kept_UserId"],
    )

    summary_path = REPORTS / "member_match_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        f"create(C): {len(create_rows)}\nupdate(U): {len(update_rows)}\ntotal: {len(records)}\n",
        encoding="utf-8",
    )

    # Persist match results for downstream scripts (order.csv 等の会員ID欄突合に使用)
    match_data = [
        {
            "UserNo": r.account["UserNo"],
            "UserId": r.user["Id"],
            "Email": r.user.get("Email", ""),
            "pattern": r.pattern,
            "member_email": r.cec_email if r.pattern == "U" else r.user.get("Email", ""),
        }
        for r in records
    ]
    write_report(OUT / "_member_match_cache.csv", match_data,
                 ["UserNo", "UserId", "Email", "pattern", "member_email"])

    # 3.3（3.1+3.2 = 1.3）は render_checklist_report.py で 1.3 と合わせて自動判定する。
    checklist.record_many(
        REPORTS,
        [
            ("3.1", len(create_rows)),
            ("3.2", len(update_rows)),
            ("3.4", len(unmatched)),
            ("3.5", len(duplicates)),
        ],
        source="generate_member.py",
    )

    print(
        f"member_import_create.csv: {len(create_rows)} rows / "
        f"member_import_update.csv: {len(update_rows)} rows "
        f"(unmatched={len(unmatched)}, duplicates={len(duplicates)})"
    )


if __name__ == "__main__":
    main()
