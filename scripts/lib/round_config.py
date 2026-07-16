"""移行ラウンド（1〜3回目）ごとの注文抽出ルール読込み。

ルール本体は `config/round_rules.json`。対象ラウンドは環境変数 `MIGRATION_ROUND`
（既定 `1`）で切り替える。詳細は各回の移行手順書
（`docs/migration-policy/{1,2,3}回目移行手順書.md`）を参照。

## 検証時のカットオフ日付切り替え

本番移行のカットオフ日付（`cutoff_order_date`）とは別に、移行検証用のカットオフ日付を
`cutoff_order_date_verification` として `round_rules.json` に設定できる。
環境変数 `MIGRATION_VERIFICATION`（`1`/`true`/`yes` のいずれかで有効）を指定すると、
`load_round_rules()` が `cutoff_order_date` をこの検証用日付に差し替えて返す。
本番移行時は `MIGRATION_VERIFICATION` を指定しない（未設定 = 本番のカットオフ日付を使用）。
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


def current_round() -> str:
    return os.environ.get("MIGRATION_ROUND", "1")


def is_verification_mode() -> bool:
    """環境変数 `MIGRATION_VERIFICATION` が真値なら検証モード。"""
    return os.environ.get("MIGRATION_VERIFICATION", "").strip().lower() in {"1", "true", "yes"}


def load_round_rules(config_dir: Path, round_no: str | None = None) -> dict:
    round_no = round_no or current_round()
    data = json.loads((config_dir / "round_rules.json").read_text(encoding="utf-8"))
    rules = data.get(round_no)
    if rules is None:
        raise ValueError(f"Unknown MIGRATION_ROUND: {round_no!r} (config/round_rules.json に未定義)")
    rules = dict(rules)
    if is_verification_mode():
        verification_cutoff = rules.get("cutoff_order_date_verification")
        if verification_cutoff is not None:
            rules["cutoff_order_date"] = verification_cutoff
    return rules


def _load_order_ids_from_csv(path: Path) -> set[str]:
    """1 つの CSV から注文番号集合を読み込む（列名『注文番号』、無ければ先頭列）。"""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col = "注文番号" if "注文番号" in fieldnames else (fieldnames[0] if fieldnames else None)
        if not col:
            return set()
        return {row[col] for row in reader if row.get(col)}


def load_already_migrated_order_ids() -> set[str]:
    """前回までに移行済みの注文番号一覧（列名『注文番号』）。

    環境変数 `MIGRATION_PREVIOUS_ORDER_IDS_CSV` で CSV パスを指定した場合のみ読み込む。
    **カンマ区切りで複数の CSV を指定できる**（3 回目移行で 1 回目・2 回目の
    `order.csv` をまとめて指定する用途）。各 CSV の注文番号を和集合で返す。
    1 回目は常に空集合、未指定時も空集合。
    """
    paths_str = os.environ.get("MIGRATION_PREVIOUS_ORDER_IDS_CSV")
    if not paths_str:
        return set()
    order_ids: set[str] = set()
    for part in paths_str.split(","):
        part = part.strip()
        if not part:
            continue
        order_ids |= _load_order_ids_from_csv(Path(part))
    return order_ids


def member_previous_extraction_at(config_dir: Path, round_no: str | None = None) -> str | None:
    """会員CSVの2回目以降突合で使う前回抽出日時（`round_rules.json` の `member_previous_extraction_at`）。"""
    rules = load_round_rules(config_dir, round_no)
    value = rules.get("member_previous_extraction_at")
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()
