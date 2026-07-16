#!/usr/bin/env python3
"""エッジケース対象データの抽出・自動検証（1回目移行チェックリスト 3.13.1〜3.13.3）。

従来チェックリスト 3.13「エッジケースのシナリオ確認」は3件の代表ケースを
1行にまとめて目視確認する項目だったが、ケースごとに対象データの自動抽出・
可能な範囲での自動判定を行うよう分割した（3.13.1〜3.13.3）。

- 3.13.1: 複数住所を持つ会員（`UserAddress.csv` で1会員に2件以上の住所）
  → `address_import.csv` が1住所1行で出力されているか（[会員アドレス帳CSV.md](../docs/migration-policy/deliverables/会員アドレス帳CSV.md) 出力ルール）
- 3.13.2: カナ氏名が空の会員（`User.LastNameKana`/`FirstNameKana` が両方空）
  → 会員CSV（新規登録用）の「名前読み（苗字）」「名前読み（名）」が規定のフォールバック値 `・` になっているか（`lib/transforms.py` `kana_or_default()`）
- 3.13.3: `discountPrice` が正数の注文
  → `order.csv` の「調整金額」がマイナス値（IF設計書の必須仕様）で出力されているか
    （[business-rules-confirmation.md](../docs/migration-policy/business-rules-confirmation.md) #25 は符号反転の要否が未決のため、
    現状の実装（素通し）では基本的に不一致＝NGとなる想定。判定結果は仕様確定までの現状把握に用いる）

各ケースの対象データサンプル（最大 `SAMPLE_LIMIT` 件）を `output/reports/edge_case_*.csv` に出力し、
件数・判定を `checklist.record()` で `output/reports/checklist_results.json` に記録する。
最終的な仕様適合性の判断・お客様確認は本スクリプトの結果を踏まえて人手で行うこと。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import read_csv, write_report
from lib.transforms import kana_or_default

RAW = ROOT / "input" / "raw"
OUT = ROOT / "output" / "processed"
REPORTS = ROOT / "output" / "reports"

SAMPLE_LIMIT = 20


def check_multi_address_members() -> tuple[int, int]:
    """3.13.1: 複数住所を持つ会員 → address_import.csv の行数整合性を確認する。"""
    user_addresses = read_csv(RAW / "UserAddress.csv")
    by_userno: dict[str, list[dict[str, str]]] = defaultdict(list)
    for ua in user_addresses:
        by_userno[ua["UserNo"]].append(ua)
    multi = {no: rows for no, rows in by_userno.items() if len(rows) >= 2}

    cache_path = OUT / "_member_match_cache.csv"
    cache = {r["UserNo"]: r for r in read_csv(cache_path)} if cache_path.exists() else {}

    address_path = OUT / "address_import.csv"
    address_rows = read_csv(address_path) if address_path.exists() else []
    count_by_email: dict[str, int] = defaultdict(int)
    for row in address_rows:
        count_by_email[row.get("会員メールアドレス", "")] += 1

    samples = []
    mismatch = 0
    for user_no, rows in multi.items():
        member = cache.get(user_no)
        email = member.get("member_email", "") if member else ""
        generated_count = count_by_email.get(email, 0)
        ok = generated_count == len(rows)
        if not ok:
            mismatch += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append({
                "UserNo": user_no,
                "UserAddress件数": len(rows),
                "会員メールアドレス": email,
                "address_import件数": generated_count,
                "判定": "OK" if ok else "NG",
            })

    write_report(
        REPORTS / "edge_case_multi_address_members.csv",
        samples,
        ["UserNo", "UserAddress件数", "会員メールアドレス", "address_import件数", "判定"],
    )
    return len(multi), mismatch


def check_empty_kana_members() -> tuple[int, int]:
    """3.13.2: カナ氏名が空の会員 → 新規登録CSVの「名前読み」フォールバック値を確認する。"""
    users = read_csv(RAW / "User.csv")
    empty_kana_users = [
        u for u in users
        if not (u.get("LastNameKana") or "").strip() and not (u.get("FirstNameKana") or "").strip()
    ]

    create_path = OUT / "member_import_create.csv"
    create_rows = read_csv(create_path) if create_path.exists() else []
    kana_by_old_id = {
        r.get("[カスタム]旧会員ID", ""): (
            r.get("名前読み（苗字）", ""),
            r.get("名前読み（名）", ""),
        )
        for r in create_rows
    }

    expected = (kana_or_default(""), kana_or_default(""))

    samples = []
    mismatch = 0
    checked = 0
    for u in empty_kana_users:
        kana = kana_by_old_id.get(u["Id"])
        if kana is None:
            # パターンB（更新のみ）は名前読み列を出力しないため対象外
            continue
        checked += 1
        ok = kana == expected
        if not ok:
            mismatch += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append({
                "UserId": u["Id"],
                "Email": u.get("Email", ""),
                "名前読み（苗字）(出力値)": kana[0],
                "名前読み（名）(出力値)": kana[1],
                "期待値": expected[0],
                "判定": "OK" if ok else "NG",
            })

    write_report(
        REPORTS / "edge_case_empty_kana_members.csv",
        samples,
        ["UserId", "Email", "名前読み(出力値)", "期待値", "判定"],
    )
    return checked, mismatch


def check_positive_discount_orders() -> tuple[int, int]:
    """3.13.3: discountPriceが正数の注文 → order.csvの調整金額の符号を確認する。"""
    orders = read_csv(RAW / "PurchaseOrder.csv")
    positive_orders = {
        po["orderId"]: po for po in orders if float(po.get("discountPrice") or 0) > 0
    }

    order_path = OUT / "order.csv"
    order_rows = {r["注文番号"]: r for r in read_csv(order_path)} if order_path.exists() else {}

    samples = []
    mismatch = 0
    checked = 0
    for order_id, po in positive_orders.items():
        row = order_rows.get(order_id)
        if not row:
            continue  # 移行対象外（除外済み）注文はスコープ外
        checked += 1
        adjusted = float(row.get("調整金額") or 0)
        ok = adjusted < 0
        if not ok:
            mismatch += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append({
                "注文番号": order_id,
                "discountPrice(元データ)": po.get("discountPrice", ""),
                "調整金額(order.csv)": row.get("調整金額", ""),
                "判定": "OK" if ok else "NG",
            })

    write_report(
        REPORTS / "edge_case_positive_discount_orders.csv",
        samples,
        ["注文番号", "discountPrice(元データ)", "調整金額(order.csv)", "判定"],
    )
    return checked, mismatch


def main() -> None:
    multi_total, multi_mismatch = check_multi_address_members()
    kana_total, kana_mismatch = check_empty_kana_members()
    discount_total, discount_mismatch = check_positive_discount_orders()

    checklist.record(
        REPORTS, "3.13.1", multi_total, source="generate_edge_case_samples.py",
        judge=("OK" if multi_mismatch == 0 else "NG"),
        note=f"複数住所会員{multi_total}件中、address_import.csv件数不一致={multi_mismatch}件",
    )
    checklist.record(
        REPORTS, "3.13.2", kana_total, source="generate_edge_case_samples.py",
        judge=("OK" if kana_mismatch == 0 else "NG"),
        note=f"カナ氏名が空の会員（新規登録分）{kana_total}件中、名前読み不一致={kana_mismatch}件",
    )
    checklist.record(
        REPORTS, "3.13.3", discount_total, source="generate_edge_case_samples.py",
        judge=("OK" if discount_mismatch == 0 else "NG"),
        note=(
            f"discountPriceが正数の移行対象注文{discount_total}件中、"
            f"調整金額の符号が仕様（マイナス）通りでない件数={discount_mismatch}"
            "（business-rules-confirmation.md #25 未決。符号反転が未実装の間は基本的にNGとなる想定）"
        ),
    )

    print(
        f"edge_case_multi_address_members.csv: {multi_total}件 (不一致={multi_mismatch}) / "
        f"edge_case_empty_kana_members.csv: {kana_total}件 (不一致={kana_mismatch}) / "
        f"edge_case_positive_discount_orders.csv: {discount_total}件 (不一致={discount_mismatch})"
    )


if __name__ == "__main__":
    main()
