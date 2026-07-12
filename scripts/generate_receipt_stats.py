#!/usr/bin/env python3
"""移行データ受領チェック（1回目移行チェックリスト §1・§2.1）の件数を自動集計する。

ETL 生成物（member_import_*.csv 等）とは独立に、`input/raw/` の生データを直接
カウントすることで、ETL処理の入力側の件数を検証する。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv
from lib.join_keys import deleted_usernos
from lib.order_filters import exclusion_reason, is_cancelled_order, is_guest_order, is_shipped
from lib.product_lookup import load_products
from lib.round_config import current_round, load_already_migrated_order_ids, load_round_rules
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
    accounts = read_csv(RAW / "UserAccount.csv")
    products = load_products(RAW / "Products.csv")
    orders = read_csv(RAW / "PurchaseOrder.csv")
    customers = {c["customerId"]: c for c in read_csv(RAW / "OrderCustomer.csv")}
    order_lines = read_csv(RAW / "OrderLine.csv")
    addresses = read_csv(RAW / "Address.csv")
    delivery_orders = read_csv(RAW / "DeliveryOrder.csv")
    deleted = deleted_usernos(users, accounts)

    deleted_user_count = sum(1 for u in users if is_deleted(u.get("DeletedAt")))

    cancelled_count = sum(1 for po in orders if is_cancelled_order(po))
    guest_count = sum(1 for po in orders if is_guest_order(customers.get(po["customerId"], {})))
    shipped_count = sum(1 for po in orders if is_shipped(po))
    if cutoff_order_date:
        cutoff_count = sum(
            1 for po in orders
            if (po.get("orderDate") or "").strip()[:10] <= cutoff_order_date
        )
    else:
        cutoff_count = None

    migratable_count = sum(
        1 for po in orders
        if exclusion_reason(
            po, customers.get(po["customerId"]), deleted,
            cutoff_order_date=cutoff_order_date,
            require_shipped=require_shipped,
            already_migrated_order_ids=already_migrated,
        ) is None
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
        ("1.3", len(users) - deleted_user_count),
        ("1.4", len(accounts)),
        ("1.5", len(products)),
        ("1.6", len(orders)),
        ("1.9", cancelled_count),
        ("1.10", guest_count),
        ("1.8", shipped_count),
        ("1.11", migratable_count),
        ("1.12", len(order_lines)),
        ("1.13_OrderCustomer", len(customers)),
        ("1.13_Address", len(addresses)),
        ("1.13_DeliveryOrder", len(delivery_orders)),
        ("2.1", len(cec_rows)),
    ]
    if cutoff_count is not None:
        entries.append(("1.7", cutoff_count))
    else:
        entries.append(("1.7", "N/A（ラウンド設定でカットオフ日付なし）"))

    checklist.record_many(
        REPORTS,
        entries,
        source="generate_receipt_stats.py",
        note=f"MIGRATION_ROUND={round_no}" + (f"; {cec_note}" if cec_note else ""),
    )

    print(f"[round={round_no}] User={len(users)}(削除済={deleted_user_count}) "
          f"PurchaseOrder={len(orders)}(cutoff={cutoff_count}, shipped={shipped_count}, "
          f"cancelled={cancelled_count}, guest={guest_count}, 対象={migratable_count}) "
          f"member_export={len(cec_rows)}")


if __name__ == "__main__":
    main()
