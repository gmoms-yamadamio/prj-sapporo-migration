#!/usr/bin/env python3
"""SB00092（注文情報移行バッチ）の実行ログを解析し、チェックリスト §5 の件数・処理時間を
自動記録するCLI。

使用方法:
    python scripts/parse_sb00092_log.py <ログファイルパス> [--mode db|api|all]

ログファイルは CloudWatch Logs 等からエクスポートしたテキストファイルを想定する。
SB00092注文情報移行バッチ処理概要.md §5「処理結果ログ」で確認されている
`成功 n件 / エラー n件` 形式の行、および開始・終了ログの時刻を解析対象とする。

【注意】本番のログ実出力フォーマットは未確認のため、正規表現は暫定パターンである。
本番ログで抽出できなかった項目は "not_found" として一覧表示するので、
その場合は `record_manual_result.py` で該当項目を手動記録すること。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist

REPORTS = ROOT / "output" / "reports"

# 「注文移行データAPI: 成功 12件 / エラー 3件」のような行を想定（(A) 注文移行データ）。
ORDER_API_RESULT_RE = re.compile(r"注文移行.*?成功\s*(\d+)\s*件.*?エラー\s*(\d+)\s*件")
# 「...ダミー...: 成功 12件 / エラー 3件」のような行を想定（(B) ダミーデータ）。
DUMMY_API_RESULT_RE = re.compile(r"ダミー.*?成功\s*(\d+)\s*件.*?エラー\s*(\d+)\s*件")
# 重複スキップ件数（実装依存。見つからない場合は None のまま）。
SKIP_RESULT_RE = re.compile(r"(?:重複|スキップ).*?(\d+)\s*件")
# 一時DB取込件数（実装依存。「n件登録」「n件取込」等を想定）。
DB_IMPORT_RE = re.compile(r"(?:一時DB|取込|登録).*?(\d+)\s*件")
# 所要時間ログ（「所要時間: 12345ms」「経過時間 12.3秒」等、実装依存の暫定パターン）。
DURATION_RE = re.compile(r"(?:所要時間|経過時間|processing time)\D{0,5}(\d+(?:\.\d+)?)\s*(ms|秒|s)?", re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log_path", help="SB00092 実行ログのテキストファイルパス")
    parser.add_argument("--mode", default="all", choices=["db", "api", "all"],
                         help="このログが対応する MIGRATION_PROCESS_MODE（記録時のnoteに残す）")
    args = parser.parse_args()

    log_path = Path(args.log_path)
    text = log_path.read_text(encoding="utf-8", errors="replace")

    found: dict[str, object] = {}
    not_found: list[str] = []

    order_match = ORDER_API_RESULT_RE.search(text)
    if order_match:
        success, error = int(order_match.group(1)), int(order_match.group(2))
        found["5.3"] = success
        found["5.4"] = error
    else:
        not_found += ["5.3", "5.4"]

    dummy_match = DUMMY_API_RESULT_RE.search(text)
    if dummy_match:
        found["5.6"] = int(dummy_match.group(1))
    else:
        not_found.append("5.6")

    skip_match = SKIP_RESULT_RE.search(text)
    if skip_match:
        found["5.5"] = int(skip_match.group(1))
    else:
        not_found.append("5.5")

    db_match = DB_IMPORT_RE.search(text)
    if db_match:
        found["5.2"] = int(db_match.group(1))
    else:
        not_found.append("5.2")

    duration_matches = DURATION_RE.findall(text)
    if duration_matches:
        found["5.8"] = ", ".join(f"{value}{unit or ''}" for value, unit in duration_matches)
    else:
        not_found.append("5.8")

    entries = [(check_id, value) for check_id, value in found.items()]
    if entries:
        checklist.record_many(
            REPORTS, entries, source="parse_sb00092_log.py",
            note=f"MIGRATION_PROCESS_MODE={args.mode}; log={log_path.name}",
        )

    print(f"抽出できた項目: {sorted(found.items())}")
    if not_found:
        print(f"抽出できなかった項目（record_manual_result.py で手動記録してください）: {not_found}")


if __name__ == "__main__":
    main()
