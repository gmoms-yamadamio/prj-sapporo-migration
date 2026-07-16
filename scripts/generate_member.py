#!/usr/bin/env python3
"""Generate member import CSVs (create / update full / update mailmag) and match report."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv, write_report
from lib.join_keys import MemberRecord, build_member_records, excluded_deleted_members, load_cec_members
from lib.round_config import current_round, member_previous_extraction_at
from lib.transforms import (
    SITE_CODE,
    format_birthday,
    format_member_datetime,
    format_migration_memo_create,
    format_migration_memo_update,
    half_width_digits,
    is_updated_since,
    kana_or_default,
    mail_optin,
    prefecture_name,
    sex_code,
)

RAW = ROOT / "input" / "raw"
CEC = ROOT / "input" / "cec"
CONFIG = ROOT / "scripts" / "config"
OUT = ROOT / "output" / "processed"
REPORTS = ROOT / "output" / "reports"

# パターンA（新規登録`C`）: 会員CSV.md「項目マッピング（パターン A）」31項目
CREATE_FIELDS = [
    "操作区分",
    "名前（苗字）",
    "名前（名）",
    "名前読み（苗字）",
    "名前読み（名）",
    "メールアドレス",
    "メールアドレス2",
    "メール送信先選択",
    "生年月日",
    "性別",
    "電話番号1",
    "電話番号2",
    "FAX",
    "郵便番号",
    "都道府県",
    "市区町村",
    "番地",
    "建物名等",
    "会社名",
    "会社名読み",
    "部署名",
    "役職",
    "登録元サイトコード",
    "会員登録日時",
    "ニックネーム",
    "会員グループコード",
    "[カスタム]メールマガジン配信（シュパーク）",
    "[カスタム]メールマガジン配信（メンバーズショップ）",
    "[カスタム]法人コード",
    "[カスタム]旧会員ID",
    "[カスタム]移行メモ",
]

# B-1（全項目更新用）: 操作区分の次に会員ID列を追加した32項目
UPDATE_FULL_FIELDS = ["操作区分", "会員ID", *CREATE_FIELDS[1:]]

# B-2（メルマガ配信のみ更新用）: 5項目
UPDATE_MAILMAG_FIELDS = [
    "操作区分",
    "会員ID",
    "[カスタム]メールマガジン配信（シュパーク）",
    "[カスタム]旧会員ID",
    "[カスタム]移行メモ",
]


def _cec_migration_memo(cec_row: dict[str, str] | None) -> str:
    if not cec_row:
        return ""
    return (cec_row.get("[カスタム]移行メモ") or cec_row.get("移行メモ") or "").strip()


def _cec_old_member_id(cec_row: dict[str, str] | None) -> str:
    if not cec_row:
        return ""
    return (cec_row.get("[カスタム]旧会員ID") or cec_row.get("旧会員ID") or "").strip()


def classify_original_pattern(user_id: str, cec_row: dict[str, str] | None) -> str | None:
    """当初C/U判定。`Created`/`Updated`/`None`（判定不能）を返す。"""
    if not cec_row:
        return None
    old_id = _cec_old_member_id(cec_row)
    if old_id != str(user_id):
        return None
    memo = _cec_migration_memo(cec_row)
    if memo.startswith("Created"):
        return "C"
    if memo:
        return "U"
    return None


def build_member_body(user: dict[str, str], csv_output_at: str, *, migration_memo: str) -> dict[str, str]:
    return {
        "名前（苗字）": user.get("LastName", ""),
        "名前（名）": user.get("FirstName", ""),
        "名前読み（苗字）": kana_or_default(user.get("LastNameKana", "")),
        "名前読み（名）": kana_or_default(user.get("FirstNameKana", "")),
        "メールアドレス": user.get("Email", ""),
        "メールアドレス2": "",
        "メール送信先選択": "primary",
        "生年月日": format_birthday(user.get("Birthday", "")),
        "性別": sex_code(user.get("Sex", "")),
        "電話番号1": half_width_digits(user.get("PhoneNumber", "")),
        "電話番号2": "",
        "FAX": "",
        "郵便番号": half_width_digits(user.get("ZipCode", "")),
        "都道府県": prefecture_name(user.get("Prefecture", "")),
        "市区町村": user.get("City", ""),
        "番地": user.get("Street", ""),
        "建物名等": user.get("Building", ""),
        "会社名": "",
        "会社名読み": "",
        "部署名": "",
        "役職": "",
        "登録元サイトコード": SITE_CODE,
        "会員登録日時": format_member_datetime(user.get("CreatedAt", "")),
        "ニックネーム": "",
        "会員グループコード": "",
        "[カスタム]メールマガジン配信（シュパーク）": mail_optin(user.get("IsApproveMailDelivery", "0")),
        "[カスタム]メールマガジン配信（メンバーズショップ）": "",
        "[カスタム]法人コード": "",
        "[カスタム]旧会員ID": user["Id"],
        "[カスタム]移行メモ": migration_memo,
    }


def build_create_row(user: dict[str, str], csv_output_at: str) -> dict[str, str]:
    row = build_member_body(
        user,
        csv_output_at,
        migration_memo=format_migration_memo_create(csv_output_at),
    )
    return {"操作区分": "C", **row}


def build_update_full_row(user: dict[str, str], cec_member_id: str, cec_row: dict[str, str] | None, csv_output_at: str) -> dict[str, str]:
    row = build_member_body(
        user,
        csv_output_at,
        migration_memo=format_migration_memo_update(_cec_migration_memo(cec_row), csv_output_at),
    )
    return {"操作区分": "U", "会員ID": cec_member_id, **row}


def build_update_mailmag_row(user: dict[str, str], cec_member_id: str, cec_row: dict[str, str] | None, csv_output_at: str) -> dict[str, str]:
    return {
        "操作区分": "U",
        "会員ID": cec_member_id,
        "[カスタム]メールマガジン配信（シュパーク）": mail_optin(user.get("IsApproveMailDelivery", "0")),
        "[カスタム]旧会員ID": user["Id"],
        "[カスタム]移行メモ": format_migration_memo_update(_cec_migration_memo(cec_row), csv_output_at),
    }


def process_records(
    records: list[MemberRecord],
    *,
    round_no: str,
    previous_extraction_at: str | None,
    csv_output_at: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    create_rows: list[dict[str, str]] = []
    update_full_rows: list[dict[str, str]] = []
    update_mailmag_rows: list[dict[str, str]] = []
    skipped_no_update: list[dict[str, str]] = []
    origin_unknown: list[dict[str, str]] = []

    for rec in records:
        if rec.pattern == "C":
            create_rows.append(build_create_row(rec.user, csv_output_at))
            continue

        if round_no == "1" or not previous_extraction_at:
            update_mailmag_rows.append(
                build_update_mailmag_row(rec.user, rec.cec_member_id, rec.cec_row, csv_output_at)
            )
            continue

        if not is_updated_since(rec.user.get("UpdatedAt", ""), previous_extraction_at):
            skipped_no_update.append({
                "UserId": rec.user["Id"],
                "Email": rec.user.get("Email", ""),
                "会員ID": rec.cec_member_id,
                "UpdatedAt": rec.user.get("UpdatedAt", ""),
                "reason": "no_update_since_previous_extraction",
            })
            continue

        original = classify_original_pattern(rec.user["Id"], rec.cec_row)
        if original == "C":
            update_full_rows.append(
                build_update_full_row(rec.user, rec.cec_member_id, rec.cec_row, csv_output_at)
            )
        elif original == "U":
            update_mailmag_rows.append(
                build_update_mailmag_row(rec.user, rec.cec_member_id, rec.cec_row, csv_output_at)
            )
        else:
            origin_unknown.append({
                "UserId": rec.user["Id"],
                "Email": rec.user.get("Email", ""),
                "会員ID": rec.cec_member_id,
                "[カスタム]旧会員ID": _cec_old_member_id(rec.cec_row),
                "[カスタム]移行メモ": _cec_migration_memo(rec.cec_row),
                "reason": "origin_unknown",
            })

    return create_rows, update_full_rows, update_mailmag_rows, skipped_no_update, origin_unknown


def main() -> None:
    users = read_csv(RAW / "User.csv")
    accounts = read_csv(RAW / "UserAccount.csv")

    cec_path = CEC / "member_export.csv"
    if not cec_path.exists():
        cec_path = CEC / "member_export_sample.csv"
    cec_rows = read_csv(cec_path) if cec_path.exists() else []
    cec_by_email = load_cec_members(cec_rows)

    round_no = current_round()
    previous_extraction_at = member_previous_extraction_at(CONFIG, round_no)
    csv_output_at = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    records, unmatched, duplicates = build_member_records(users, accounts, cec_by_email)
    create_rows, update_full_rows, update_mailmag_rows, skipped_no_update, origin_unknown = process_records(
        records,
        round_no=round_no,
        previous_extraction_at=previous_extraction_at,
        csv_output_at=csv_output_at,
    )

    write_csv(OUT / "member_import_create.csv", create_rows, CREATE_FIELDS)
    if round_no == "1" or not previous_extraction_at:
        write_csv(OUT / "member_import_update_mailmag.csv", update_mailmag_rows, UPDATE_MAILMAG_FIELDS)
    else:
        write_csv(OUT / "member_import_update_full.csv", update_full_rows, UPDATE_FULL_FIELDS)
        write_csv(OUT / "member_import_update_mailmag.csv", update_mailmag_rows, UPDATE_MAILMAG_FIELDS)

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
    write_report(
        REPORTS / "member_skipped_no_update.csv",
        skipped_no_update,
        ["UserId", "Email", "会員ID", "UpdatedAt", "reason"],
    )
    write_report(
        REPORTS / "member_origin_unknown.csv",
        origin_unknown,
        ["UserId", "Email", "会員ID", "[カスタム]旧会員ID", "[カスタム]移行メモ", "reason"],
    )

    summary_path = REPORTS / "member_match_summary.txt"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_lines = [
        f"round: {round_no}",
        f"previous_extraction_at: {previous_extraction_at or '(none)'}",
        f"csv_output_at: {csv_output_at}",
        f"create(C): {len(create_rows)}",
        f"update_full(B-1): {len(update_full_rows)}",
        f"update_mailmag(B-2): {len(update_mailmag_rows)}",
        f"skipped_no_update: {len(skipped_no_update)}",
        f"origin_unknown: {len(origin_unknown)}",
        f"total: {len(records)}",
        "",
    ]
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    match_data = [
        {
            "UserNo": r.account["UserNo"] if r.account else "",
            "UserId": r.user["Id"],
            "Email": r.user.get("Email", ""),
            "pattern": r.pattern,
            "member_email": r.cec_email if r.pattern == "U" else r.user.get("Email", ""),
        }
        for r in records
    ]
    write_report(
        OUT / "_member_match_cache.csv",
        match_data,
        ["UserNo", "UserId", "Email", "pattern", "member_email"],
    )

    checklist_entries: list[tuple[str, int]] = [
        ("3.1", len(create_rows)),
        ("3.4", len(unmatched)),
        ("3.5", len(duplicates)),
    ]
    if round_no == "1" or not previous_extraction_at:
        checklist_entries.append(("3.2", len(update_mailmag_rows)))
    else:
        checklist_entries.extend([
            ("3.2", len(update_full_rows)),
            ("3.2.1", len(update_mailmag_rows)),
        ])

    checklist.record_many(REPORTS, checklist_entries, source="generate_member.py")

    if round_no == "1" or not previous_extraction_at:
        print(
            f"member_import_create.csv: {len(create_rows)} rows / "
            f"member_import_update_mailmag.csv: {len(update_mailmag_rows)} rows "
            f"(unmatched={len(unmatched)}, duplicates={len(duplicates)})"
        )
    else:
        print(
            f"member_import_create.csv: {len(create_rows)} rows / "
            f"member_import_update_full.csv: {len(update_full_rows)} rows / "
            f"member_import_update_mailmag.csv: {len(update_mailmag_rows)} rows "
            f"(skipped_no_update={len(skipped_no_update)}, origin_unknown={len(origin_unknown)}, "
            f"unmatched={len(unmatched)}, duplicates={len(duplicates)})"
        )


if __name__ == "__main__":
    main()
