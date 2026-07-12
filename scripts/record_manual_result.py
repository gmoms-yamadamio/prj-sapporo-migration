#!/usr/bin/env python3
"""手動確認項目の結果をチェックリスト結果ファイルに記録するCLI。

スクリプトで自動集計できない項目（CEC管理画面での目視確認、お客様レビュー等）も、
本ツールで同じ `output/reports/checklist_results.json` に記録することで、
`render_checklist_report.py` が生成する最終レポートに自動・手動の結果を一元的に
反映できるようにする。

使用例:
    python scripts/record_manual_result.py 2.2 "1234" --by "山田" --judge OK \
        --note "CEC管理画面 決済方法マスタで確認"

    python scripts/record_manual_result.py 6.15 "問題なし" --by "サッポロビール様" --judge OK
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist

REPORTS = ROOT / "output" / "reports"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("check_id", help="チェック項目ID（例: 2.2, 4.1, 6.15）")
    parser.add_argument("result", help="結果（件数・確認内容等）")
    parser.add_argument("--by", default="", help="実施者")
    parser.add_argument("--judge", default="", choices=["", "OK", "NG"], help="判定（OK/NG）")
    parser.add_argument("--note", default="", help="備考")
    args = parser.parse_args()

    checklist.record(
        REPORTS,
        args.check_id,
        args.result,
        source="manual",
        auto=False,
        note=args.note,
        by=args.by,
        judge=args.judge,
    )
    print(f"記録しました: {args.check_id} = {args.result} (実施者={args.by or '未記入'}, 判定={args.judge or '未記入'})")


if __name__ == "__main__":
    main()
