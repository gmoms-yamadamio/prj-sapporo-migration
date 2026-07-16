"""移行対象注文の OrderLine.productId が Products.csv に存在するか検証する。"""

from __future__ import annotations

from typing import Iterable

from lib.order_filters import is_migratable_order
from lib.product_lookup import sku_for_product_id


def find_unmatched_product_lines(
    orders: dict[str, dict[str, str]],
    order_lines: Iterable[dict[str, str]],
    customers: dict[str, dict[str, str]],
    products: dict[str, dict[str, str]],
    deleted_usernos: set[str],
    *,
    cutoff_order_date: str | None,
    require_shipped: bool,
    already_migrated_order_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """移行対象注文の明細行のうち、Products.csv に存在しない productId を返す。"""
    migratable_order_ids = {
        oid for oid, po in orders.items()
        if is_migratable_order(
            po,
            customers.get(po.get("customerId", "")),
            deleted_usernos,
            cutoff_order_date=cutoff_order_date,
            require_shipped=require_shipped,
            already_migrated_order_ids=already_migrated_order_ids,
        )
    }

    unmatched: list[dict[str, str]] = []
    for line in order_lines:
        order_id = (line.get("orderId") or "").strip()
        if order_id not in migratable_order_ids:
            continue
        product_id = (line.get("productId") or "").strip()
        if not sku_for_product_id(products, product_id):
            unmatched.append({"orderId": order_id, "productId": product_id})
    return unmatched
