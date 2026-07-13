"""Order inclusion/exclusion rules for migration."""

from __future__ import annotations

CANCELLED_ORDER_STATUS = "10"


def is_guest_order(customer: dict[str, str]) -> bool:
    return customer.get("isGuest") == "1"


def is_cancelled_order(purchase_order: dict[str, str]) -> bool:
    return purchase_order.get("orderStatus") == CANCELLED_ORDER_STATUS


def is_shipped(purchase_order: dict[str, str]) -> bool:
    """出荷完了判定（確定）: shipDate が NULL 以外。

    [注文履歴CSV.md](../../docs/migration-policy/deliverables/注文履歴CSV.md)
    「出荷完了の判定条件（確定）」参照。本番データで確認済み。
    """
    ship_date = purchase_order.get("shipDate")
    return bool(ship_date and ship_date.strip().upper() != "NULL")


def is_within_cutoff(purchase_order: dict[str, str], cutoff_order_date: str) -> bool:
    """orderDate（`YYYY-MM-DD ...`）が cutoff_order_date（`YYYY-MM-DD`）以前か。

    ISO 形式のゼロ埋め日付文字列前提のため、先頭10文字の文字列比較で判定できる。
    """
    order_date = (purchase_order.get("orderDate") or "").strip()
    if not order_date or order_date.upper() == "NULL":
        return False
    return order_date[:10] <= cutoff_order_date


def exclusion_reason(
    purchase_order: dict[str, str],
    customer: dict[str, str] | None,
    deleted_usernos: set[str] | None = None,
    *,
    cutoff_order_date: str | None = None,
    require_shipped: bool = False,
    already_migrated_order_ids: set[str] | None = None,
) -> str | None:
    # 削除済み会員の注文は、ゲスト／キャンセル等の注文単体の状態に関わらず
    # 最優先で除外する（会員単位の除外はレポート上の理由内訳でも最優先で
    # 集計されるべきため。business-rules-confirmation.md #1 参照）。
    if deleted_usernos and customer and customer.get("isGuest") != "1":
        if customer.get("UserNo", "") in deleted_usernos:
            return "deleted_member"
    if customer and is_guest_order(customer):
        return "guest"
    if is_cancelled_order(purchase_order):
        return "cancelled"
    if already_migrated_order_ids and purchase_order.get("orderId", "") in already_migrated_order_ids:
        return "already_migrated"
    if cutoff_order_date and not is_within_cutoff(purchase_order, cutoff_order_date):
        return "after_cutoff_date"
    if require_shipped and not is_shipped(purchase_order):
        return "not_shipped"
    return None


def is_migratable_order(
    purchase_order: dict[str, str],
    customer: dict[str, str] | None,
    deleted_usernos: set[str] | None = None,
    *,
    cutoff_order_date: str | None = None,
    require_shipped: bool = False,
    already_migrated_order_ids: set[str] | None = None,
) -> bool:
    return exclusion_reason(
        purchase_order,
        customer,
        deleted_usernos,
        cutoff_order_date=cutoff_order_date,
        require_shipped=require_shipped,
        already_migrated_order_ids=already_migrated_order_ids,
    ) is None
