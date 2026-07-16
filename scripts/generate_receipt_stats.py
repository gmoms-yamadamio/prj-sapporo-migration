#!/usr/bin/env python3
"""移行データ受領チェック（1回目移行チェックリスト §1・§2.1）の件数を自動集計する。

ETL 生成物（member_import_*.csv 等）とは独立に、`input/raw/` の生データを直接
カウントすることで、ETL処理の入力側の件数を検証する。
`User.csv` については §1.17〜1.21 の項目値検証も行う。
`Address.csv` については §1.23〜1.26 の項目値検証も行う。
移行対象注文の商品ID突合（§1.22）も行う。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_report
from lib.join_keys import accountless_active_user_ids, deleted_usernos, duplicate_email_extra_count
from lib.user_receipt_checks import validate_users
from lib.address_receipt_checks import validate_addresses
from lib.order_product_checks import find_unmatched_product_lines
from lib.order_filters import exclusion_reason, is_cancelled_order, is_guest_order, is_shipped
from lib.product_lookup import load_products
from lib.round_config import (
    current_round,
    is_verification_mode,
    load_already_migrated_order_ids,
    load_round_rules,
)
from lib.transforms import is_deleted

RAW = ROOT / "input" / "raw"
CEC = ROOT / "input" / "cec"
REPORTS = ROOT / "output" / "reports"


def main() -> None:
    round_no = current_round()
    round_rules = load_round_rules(ROOT / "scripts" / "config", round_no)
    cutoff_order_date = round_rules.get("cutoff_order_date")
    require_shipped = bool(round_rules.get("require_shipped"))
    already_migrated = load_already_migrated_order_ids()

    users = read_csv(RAW / "User.csv")
    user_validation = validate_users(users)
    if user_validation.errors:
        write_report(
            REPORTS / "user_csv_validation_errors.csv",
            (
                {
                    "Id": err.user_id,
                    "field": err.field,
                    "value": err.value,
                    "reason": err.reason,
                }
                for err in user_validation.errors
            ),
            ["Id", "field", "value", "reason"],
        )
    accounts = read_csv(RAW / "UserAccount.csv")
    products = load_products(RAW / "Products.csv")
    orders_list = read_csv(RAW / "PurchaseOrder.csv")
    orders = {o["orderId"]: o for o in orders_list}
    customers = {c["customerId"]: c for c in read_csv(RAW / "OrderCustomer.csv")}
    order_lines = read_csv(RAW / "OrderLine.csv")
    addresses = read_csv(RAW / "Address.csv")
    address_validation = validate_addresses(addresses)
    if address_validation.errors:
        write_report(
            REPORTS / "address_csv_validation_errors.csv",
            (
                {
                    "addressId": err.address_id,
                    "field": err.field,
                    "value": err.value,
                    "reason": err.reason,
                }
                for err in address_validation.errors
            ),
            ["addressId", "field", "value", "reason"],
        )
    delivery_orders = read_csv(RAW / "DeliveryOrder.csv")
    deleted = deleted_usernos(users, accounts)

    deleted_user_count = sum(1 for u in users if is_deleted(u.get("DeletedAt")))
    accountless_count = len(accountless_active_user_ids(users, accounts))
    duplicate_extra_count = duplicate_email_extra_count(users)

    cancelled_count = sum(1 for po in orders_list if is_cancelled_order(po))
    guest_count = sum(1 for po in orders_list if is_guest_order(customers.get(po["customerId"], {})))
    shipped_count = sum(1 for po in orders_list if is_shipped(po))
    if cutoff_order_date:
        cutoff_count = sum(
            1 for po in orders_list
            if (po.get("orderDate") or "").strip()[:10] <= cutoff_order_date
        )
    else:
        cutoff_count = None

    migratable_count = sum(
        1 for po in orders_list
        if exclusion_reason(
            po, customers.get(po["customerId"]), deleted,
            cutoff_order_date=cutoff_order_date,
            require_shipped=require_shipped,
            already_migrated_order_ids=already_migrated,
        ) is None
    )

    unmatched_products = find_unmatched_product_lines(
        orders,
        order_lines,
        customers,
        products,
        deleted,
        cutoff_order_date=cutoff_order_date,
        require_shipped=require_shipped,
        already_migrated_order_ids=already_migrated,
    )
    if unmatched_products:
        write_report(
            REPORTS / "unmatched_product_ids.csv",
            unmatched_products,
            ["orderId", "productId"],
        )

    cec_path = CEC / "member_export.csv"
    cec_note = ""
    if not cec_path.exists():
        cec_path = CEC / "member_export_sample.csv"
        cec_note = "member_export.csv 未配置のため member_export_sample.csv（サンプル）で集計"
    cec_rows = read_csv(cec_path) if cec_path.exists() else []

    entries: list[tuple[str, object]] = [
        ("1.1", len(users)),
        ("1.2", deleted_user_count),
        ("1.3", len(users) - deleted_user_count - duplicate_extra_count),
        ("1.4", len(accounts)),
        ("1.5", len(products)),
        ("1.6", len(orders_list)),
        ("1.9", cancelled_count),
        ("1.10", guest_count),
        ("1.8", shipped_count),
        ("1.11", migratable_count),
        ("1.12", len(order_lines)),
        ("1.13_OrderCustomer", len(customers)),
        ("1.13_Address", len(addresses)),
        ("1.13_DeliveryOrder", len(delivery_orders)),
        ("1.14", accountless_count),
        ("1.15", duplicate_extra_count),
        ("1.16", len(already_migrated)),
        ("1.17", user_validation.zip_code_invalid),
        ("1.18", user_validation.prefecture_invalid),
        ("1.19", user_validation.sex_invalid),
        ("1.20", user_validation.birthday_invalid),
        ("1.21", user_validation.phone_number_invalid),
        ("1.22", len(unmatched_products)),
        ("1.23", address_validation.zip_code_invalid),
        ("1.24", address_validation.pref_empty),
        ("1.25", address_validation.pref_invalid),
        ("1.26", address_validation.phone_invalid),
        ("2.1", len(cec_rows)),
    ]
    if cutoff_count is not None:
        entries.append(("1.7", cutoff_count))
    else:
        entries.append(("1.7", "N/A（ラウンド設定でカットオフ日付なし）"))

    verify_note = (
        f"MIGRATION_VERIFICATION={'1' if is_verification_mode() else '0'}"
        f" (cutoff_order_date={cutoff_order_date})"
    )
    user_val_note = (
        "User.csv項目検証OK"
        if user_validation.all_ok
        else (
            f"User.csv項目検証NG: ZipCode={user_validation.zip_code_invalid}, "
            f"Prefecture={user_validation.prefecture_invalid}, Sex={user_validation.sex_invalid}, "
            f"Birthday={user_validation.birthday_invalid}, "
            f"PhoneNumber={user_validation.phone_number_invalid}"
        )
    )
    product_val_note = (
        "商品ID突合OK"
        if not unmatched_products
        else f"商品ID突合NG: unmatched={len(unmatched_products)}"
    )
    address_val_note = (
        "Address.csv項目検証OK"
        if address_validation.all_ok
        else (
            f"Address.csv項目検証NG: zipCode={address_validation.zip_code_invalid}, "
            f"pref_empty={address_validation.pref_empty}, "
            f"pref_invalid={address_validation.pref_invalid}, "
            f"tel={address_validation.phone_invalid}"
        )
    )
    checklist.record_many(
        REPORTS,
        entries,
        source="generate_receipt_stats.py",
        note=(
            f"MIGRATION_ROUND={round_no}; {verify_note}; {user_val_note}; "
            f"{product_val_note}; {address_val_note}"
            + (f"; {cec_note}" if cec_note else "")
        ),
    )

    print(
        f"[round={round_no}, verification={is_verification_mode()}] "
        f"User={len(users)}(削除済={deleted_user_count}) "
        f"PurchaseOrder={len(orders_list)}(cutoff={cutoff_count}, shipped={shipped_count}, "
        f"cancelled={cancelled_count}, guest={guest_count}, 対象={migratable_count}) "
        f"Address={len(addresses)} member_export={len(cec_rows)}; "
        f"{user_val_note}; {product_val_note}; {address_val_note}"
    )


if __name__ == "__main__":
    main()
