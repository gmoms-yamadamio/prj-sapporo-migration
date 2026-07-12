"""チェックリスト結果の自動記録ユーティリティ。

各 ETL スクリプトが実行時に計算した件数等を、チェック項目 ID
（[1回目移行チェックリスト.md](../../docs/migration-policy/1回目移行チェックリスト.md) の `#` 列）
に紐づけて `output/reports/checklist_results.json` に集約する。

最終的な Markdown レポートは `render_checklist_report.py` で生成する。

記録先 JSON のフォーマット:

```json
{
  "1.1": {
    "result": "1000",
    "auto": true,
    "source": "generate_receipt_stats.py",
    "recorded_at": "2026-07-11 18:00:00",
    "note": ""
  }
}
```
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

RESULTS_FILENAME = "checklist_results.json"


def results_path(reports_dir: Path) -> Path:
    return reports_dir / RESULTS_FILENAME


def load_results(reports_dir: Path) -> dict[str, dict]:
    path = results_path(reports_dir)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(reports_dir: Path, data: dict[str, dict]) -> None:
    path = results_path(reports_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def record(
    reports_dir: Path,
    check_id: str,
    result,
    *,
    source: str,
    auto: bool = True,
    note: str = "",
    by: str = "",
    judge: str = "",
) -> None:
    """1件のチェック項目結果を記録（既存の同IDは上書き）。"""
    data = load_results(reports_dir)
    data[check_id] = {
        "result": str(result),
        "auto": auto,
        "source": source,
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
        "by": by,
        "judge": judge,
    }
    _save(reports_dir, data)


def record_many(
    reports_dir: Path,
    entries: Iterable[tuple[str, object]],
    *,
    source: str,
    auto: bool = True,
    note: str = "",
) -> None:
    """複数のチェック項目結果を1回のI/Oでまとめて記録する（自動集計用）。"""
    data = load_results(reports_dir)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for check_id, result in entries:
        data[check_id] = {
            "result": str(result),
            "auto": auto,
            "source": source,
            "recorded_at": now,
            "note": note,
            "by": "",
            "judge": "",
        }
    _save(reports_dir, data)
