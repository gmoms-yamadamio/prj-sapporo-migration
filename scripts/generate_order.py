#!/usr/bin/env python3
"""Generate order.csv for SB00092."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_csv, write_report
from lib.join_keys import deleted_usernos
from lib.order_filters import exclusion_reason
from lib.round_config import current_round, load_already_migrated_order_ids, load_round_rules
from lib.transforms import (
    MANAGEMENT_GROUP_CODE,
    SITE_CODE,
    format_order_date,
    join_name,
    to_int_str,
)

RAW = ROOT / "input" / "raw"
OUT = ROOT / "output" / "processed"
REPORTS = ROOT / "output" / "reports"

ORDER_FIELDS = [
    "注文番号", "サイトコード", "会員ID（メールアドレス）", "注文日",
    "合計金額", "税額合計", "小計", "配送料", "調整金額",
    "購入者氏名（苗字）", "購入者氏名（名）", "購入者氏名カナ（苗字）", "購入者氏名カナ（名）",
    "購入者メールアドレス", "購入者電話番号", "購入者郵便番号", "購入者都道府県",
    "購入者市区町村", "購入者町名・番地", "購入者建物名", "購入者会社名",
    "購入者会社名カナ", "購入者部署名", "購入者役職", "管理グループコード",
    "受取人氏名（苗字）", "受取人氏名（名）", "受取人氏名カナ（苗字）", "受取人氏名カナ（名）",
    "受取人メールアドレス", "受取人電話番号", "受取人郵便番号", "受取人都道府県名",
    "受取人市区町村", "受取人町名・番地", "受取人建物名", "受取人会社名",
    "受取人会社名カナ", "受取人部署名", "受取人役職",
]


def address_fields(addr: dict[str, str]) -> dict[str, str]:
  return {
      "last": addr.get("recipientlastname", ""),
      "first": addr.get("recipientfirstname", ""),
      "last_kana": addr.get("recipientlastnamekana", ""),
      "first_kana": addr.get("recipientfirstnamekana", ""),
      "zip": addr.get("zipCode", ""),
      "pref": addr.get("pref", "") if addr.get("pref") != "***" else "",
      "city": addr.get("city", ""),
      "street": addr.get("street", ""),
      "building": addr.get("building", ""),
      "tel": addr.get("tel", ""),
  }


def main() -> None:
    round_rules = load_round_rules(ROOT / "scripts" / "config", current_round())
    cutoff_order_date = round_rules.get("cutoff_order_date")
    require_shipped = bool(round_rules.get("require_shipped"))
    already_migrated = load_already_migrated_order_ids()

    orders = read_csv(RAW / "PurchaseOrder.csv")
    customers = {c["customerId"]: c for c in read_csv(RAW / "OrderCustomer.csv")}
    addresses = {a["addressId"]: a for a in read_csv(RAW / "Address.csv")}
    users_list = read_csv(RAW / "User.csv")
    accounts_list = read_csv(RAW / "UserAccount.csv")
    users = {u["Id"]: u for u in users_list}
    accounts = {a["UserNo"]: a for a in accounts_list}
    deleted = deleted_usernos(users_list, accounts_list)

    output_rows: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []
    included_total_payment = 0.0

    for po in orders:
        cust = customers.get(po["customerId"])
        if not cust:
            continue

        reason = exclusion_reason(
            po, cust, deleted,
            cutoff_order_date=cutoff_order_date,
            require_shipped=require_shipped,
            already_migrated_order_ids=already_migrated,
        )
        if reason:
            excluded.append({
                "orderId": po["orderId"],
                "reason": reason,
                "isGuest": cust.get("isGuest", ""),
                "orderStatus": po.get("orderStatus", ""),
            })
            continue

        included_total_payment += float(po.get("totalPayment") or 0)

        buyer = address_fields(addresses.get(cust.get("orderedAddressId", ""), {}))
        recipient = address_fields(addresses.get(cust.get("invoiceAddressId", ""), {}))

        # 会員注文のメールアドレスは一律「旧サイト User.csv のメールアドレス」とする。
        # 会員CSVの突合（赤星商店CEC会員との一致判定）はメールアドレス一致で行うため、
        # 更新パターン（U）の場合 User.csv のメールアドレスと CEC 側メールアドレスは
        # 定義上一致する。よって注文側では CEC 突合結果を経由せず User.csv を直接参照する。
        member_email = ""
        acc = accounts.get(cust.get("UserNo", ""))
        if acc:
            user = users.get(acc.get("UserName", ""))
            member_email = user.get("Email", "") if user else ""
        if not member_email:
            unmatched.append({"orderId": po["orderId"], "UserNo": cust.get("UserNo", "")})

        total = float(po.get("totalPayment") or 0)
        delivery = float(po.get("deliveryCharge") or 0)
        discount = float(po.get("discountPrice") or 0)

        output_rows.append({
            "注文番号": po["orderId"],
            "サイトコード": SITE_CODE,
            "会員ID（メールアドレス）": member_email,
            "注文日": format_order_date(po.get("orderDate", "")),
            "合計金額": to_int_str(po.get("totalPayment", "0")),
            "税額合計": "0",
            "小計": str(int(total - delivery)),
            "配送料": to_int_str(po.get("deliveryCharge", "0")),
            "調整金額": to_int_str(str(discount)),
            "購入者氏名（苗字）": buyer["last"],
            "購入者氏名（名）": buyer["first"],
            "購入者氏名カナ（苗字）": buyer["last_kana"],
            "購入者氏名カナ（名）": buyer["first_kana"],
            "購入者メールアドレス": cust.get("emailAddr", ""),
            "購入者電話番号": buyer["tel"],
            "購入者郵便番号": buyer["zip"],
            "購入者都道府県": buyer["pref"],
            "購入者市区町村": buyer["city"],
            "購入者町名・番地": buyer["street"],
            "購入者建物名": buyer["building"],
            "購入者会社名": "",
            "購入者会社名カナ": "",
            "購入者部署名": "",
            "購入者役職": "",
            "管理グループコード": MANAGEMENT_GROUP_CODE,
            "受取人氏名（苗字）": recipient["last"],
            "受取人氏名（名）": recipient["first"],
            "受取人氏名カナ（苗字）": recipient["last_kana"],
            "受取人氏名カナ（名）": recipient["first_kana"],
            "受取人メールアドレス": cust.get("emailAddr", ""),
            "受取人電話番号": recipient["tel"],
            "受取人郵便番号": recipient["zip"],
            "受取人都道府県名": recipient["pref"],
            "受取人市区町村": recipient["city"],
            "受取人町名・番地": recipient["street"],
            "受取人建物名": recipient["building"],
            "受取人会社名": "",
            "受取人会社名カナ": "",
            "受取人部署名": "",
            "受取人役職": "",
        })

    write_csv(OUT / "order.csv", output_rows, ORDER_FIELDS)
    write_report(REPORTS / "unmatched_order_members.csv", unmatched, ["orderId", "UserNo"])
    write_report(REPORTS / "excluded_orders.csv", excluded, ["orderId", "reason", "isGuest", "orderStatus"])

    output_total = sum(int(row["合計金額"]) for row in output_rows)
    reason_counts = Counter(row["reason"] for row in excluded)
    checklist.record_many(
        REPORTS,
        [
            ("3.7", len(output_rows)),
            ("3.9_guest", reason_counts.get("guest", 0)),
            ("3.9_cancelled", reason_counts.get("cancelled", 0)),
            ("3.9_deleted_member", reason_counts.get("deleted_member", 0)),
            ("3.9_after_cutoff_date", reason_counts.get("after_cutoff_date", 0)),
            ("3.9_not_shipped", reason_counts.get("not_shipped", 0)),
            ("3.9_already_migrated", reason_counts.get("already_migrated", 0)),
            ("3.11_raw_total_payment", f"{included_total_payment:.2f}"),
            ("3.11_order_csv_total", output_total),
        ],
        source="generate_order.py",
        note=f"MIGRATION_ROUND={current_round()}",
    )
    print(f"order.csv: {len(output_rows)} rows (excluded: {len(excluded)})")


if __name__ == "__main__":
    main()
