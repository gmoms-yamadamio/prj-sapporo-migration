#!/usr/bin/env python3
"""Generate order_detail.csv for SB00092."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv, write_report
from lib.join_keys import deleted_usernos
from lib.order_filters import is_migratable_order
from lib.order_product_checks import find_unmatched_product_lines
from lib.product_lookup import load_products, sku_for_product_id, tax_rate_for_sku
from lib.round_config import (
    current_round,
    is_verification_mode,
    load_already_migrated_order_ids,
    load_round_rules,
)

RAW = ROOT / "input" / "raw"
OUT = ROOT / "output" / "processed"
REPORTS = ROOT / "output" / "reports"

DETAIL_FIELDS = [
    "注文番号", "注文明細番号", "SKUコード", "販売条件コード",
    "販売価格", "販売価格の税率", "数量",
]


def main() -> None:
    round_rules = load_round_rules(ROOT / "scripts" / "config", current_round())
    cutoff_order_date = round_rules.get("cutoff_order_date")
    require_shipped = bool(round_rules.get("require_shipped"))
    already_migrated = load_already_migrated_order_ids()

    orders = {o["orderId"]: o for o in read_csv(RAW / "PurchaseOrder.csv")}
    customers = {c["customerId"]: c for c in read_csv(RAW / "OrderCustomer.csv")}
    users = read_csv(RAW / "User.csv")
    accounts = read_csv(RAW / "UserAccount.csv")
    deleted = deleted_usernos(users, accounts)
    lines = read_csv(RAW / "OrderLine.csv")
    products = load_products(RAW / "Products.csv")

    unmatched = find_unmatched_product_lines(
        orders,
        lines,
        customers,
        products,
        deleted,
        cutoff_order_date=cutoff_order_date,
        require_shipped=require_shipped,
        already_migrated_order_ids=already_migrated,
    )
    migratable_order_ids = {
        oid for oid, po in orders.items()
        if is_migratable_order(
            po, customers.get(po["customerId"]), deleted,
            cutoff_order_date=cutoff_order_date,
            require_shipped=require_shipped,
            already_migrated_order_ids=already_migrated,
        )
    }

    by_order: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in lines:
        if line["orderId"] not in migratable_order_ids:
            continue
        by_order[line["orderId"]].append(line)

    output_rows: list[dict[str, str]] = []

    for order_id, order_lines in sorted(by_order.items()):
        for idx, line in enumerate(order_lines):
            sku = sku_for_product_id(products, line["productId"])
            if not sku:
                continue
            output_rows.append({
                "注文番号": order_id,
                "注文明細番号": str(idx),
                "SKUコード": sku,
                "販売条件コード": sku,
                "販売価格": line.get("unitPrice", "0"),
                "販売価格の税率": tax_rate_for_sku(sku),
                "数量": line.get("orderAmount", "1"),
            })

    write_csv(OUT / "order_detail.csv", output_rows, DETAIL_FIELDS)
    write_report(REPORTS / "unmatched_product_ids.csv", unmatched, ["orderId", "productId"])
    note = (
        f"MIGRATION_ROUND={current_round()}"
        f"; MIGRATION_VERIFICATION={'1' if is_verification_mode() else '0'}"
        f" (cutoff_order_date={cutoff_order_date})"
    )
    checklist.record(REPORTS, "3.8", len(output_rows), source="generate_order_detail.py", note=note)
    checklist.record(REPORTS, "3.14", len(unmatched), source="generate_order_detail.py", note=note)
    print(f"order_detail.csv: {len(output_rows)} rows (unmatched_product_ids={len(unmatched)})")


if __name__ == "__main__":
    main()
