"""移行ラウンド（1〜3回目）ごとの注文抽出ルール読込み。

ルール本体は `config/round_rules.json`。対象ラウンドは環境変数 `MIGRATION_ROUND`
（既定 `1`）で切り替える。詳細は各回の移行手順書
（`docs/migration-policy/{1,2,3}回目移行手順書.md`）を参照。
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


def current_round() -> str:
    return os.environ.get("MIGRATION_ROUND", "1")


def load_round_rules(config_dir: Path, round_no: str | None = None) -> dict:
    round_no = round_no or current_round()
    data = json.loads((config_dir / "round_rules.json").read_text(encoding="utf-8"))
    rules = data.get(round_no)
    if rules is None:
        raise ValueError(f"Unknown MIGRATION_ROUND: {round_no!r} (config/round_rules.json に未定義)")
    return rules


def load_already_migrated_order_ids() -> set[str]:
    """前回までに移行済みの注文番号一覧（列名『注文番号』）。

    環境変数 `MIGRATION_PREVIOUS_ORDER_IDS_CSV` で CSV パスを指定した場合のみ読み込む。
    2回目・3回目移行で使用予定（1回目は常に空集合、未指定時も空集合）。
    """
    path_str = os.environ.get("MIGRATION_PREVIOUS_ORDER_IDS_CSV")
    if not path_str:
        return set()
    path = Path(path_str)
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        col = "注文番号" if "注文番号" in fieldnames else (fieldnames[0] if fieldnames else None)
        if not col:
            return set()
        return {row[col] for row in reader if row.get(col)}
