#!/usr/bin/env python3
"""1回目移行チェックリストの自動集計結果を Markdown レポートとして生成する。

各 `generate_*.py` / `parse_sb00092_log.py` / `record_manual_result.py` が
`output/reports/checklist_results.json` に記録した値を読み込み、
[1回目移行チェックリスト.md](../docs/migration-policy/1回目移行チェックリスト.md)
と同じ項目ID構成で `output/reports/checklist_report.md` を生成する。

- 自動集計項目: スクリプト実行結果をそのまま反映し、期待値と比較できるものは判定(OK/NG)を自動算出する
- 手動確認項目: `record_manual_result.py` で記録済みの場合はその値を反映、未記録の場合は「未記入」と表示する

このレポートはチェックリスト本体（.md）を上書きするものではなく、
実施記録を補助する自動生成物。最終的な承認・判定はチェックリスト本体側で管理者が行うこと。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist

REPORTS = ROOT / "output" / "reports"
OUT_PATH = REPORTS / "checklist_report.md"


def to_num(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


class Row:
    def __init__(self, check_id: str, title: str, expected: str, combine: Callable[[dict], str] | None = None):
        self.check_id = check_id
        self.title = title
        self.expected = expected
        self.combine = combine


# 1.13 / 3.9 / 3.11 は複数の内部キーを1行にまとめて表示する。
def combine_1_13(results: dict) -> str:
    parts = []
    for key, label in [("1.13_OrderCustomer", "OrderCustomer"), ("1.13_Address", "Address"), ("1.13_DeliveryOrder", "DeliveryOrder")]:
        r = results.get(key)
        parts.append(f"{label}={r['result'] if r else '未記入'}")
    return " / ".join(parts)


def combine_3_9(results: dict) -> str:
    labels = [
        ("3.9_guest", "guest"), ("3.9_cancelled", "cancelled"), ("3.9_deleted_member", "deleted_member"),
        ("3.9_after_cutoff_date", "after_cutoff_date"), ("3.9_not_shipped", "not_shipped"),
        ("3.9_already_migrated", "already_migrated"),
    ]
    parts = []
    for key, label in labels:
        r = results.get(key)
        if r:
            parts.append(f"{label}={r['result']}")
    return " / ".join(parts) if parts else "未記入"


def combine_3_11(results: dict) -> str:
    raw = results.get("3.11_raw_total_payment")
    gen = results.get("3.11_order_csv_total")
    return f"受領データ合計={raw['result'] if raw else '未記入'} / order.csv合計={gen['result'] if gen else '未記入'}"


ROWS: list[Row] = [
    Row("1.1", "`User.csv` 受領件数", "0件でないこと"),
    Row("1.2", "うち削除済（`User.DeletedAt` あり）件数", "別途カウント"),
    Row("1.3", "移行対象会員件数", "1.1 − 1.2"),
    Row("1.4", "`UserAccount.csv` 受領件数", "`User.csv` と概ね一致"),
    Row("1.5", "`Products.csv` 受領件数", "3行ヘッダ除いた商品データ行数"),
    Row("1.6", "`PurchaseOrder.csv` 受領件数", "0件でないこと"),
    Row("1.7", "うち注文日（`orderDate`）が6/30以前の件数", "別途カウント"),
    Row("1.8", "うち出荷完了（`shipDate` が NULL 以外）の件数", "別途カウント"),
    Row("1.9", "うちキャンセル（`orderStatus=10`）件数", "別途カウント"),
    Row("1.10", "うちゲスト注文（`isGuest=1`）件数", "OrderCustomer.csv と突合"),
    Row("1.11", "移行対象注文件数（1回目移行対象）", "1.7 かつ 1.8 を満たし、1.9・1.10・削除済み会員注文を除いた件数"),
    Row("1.12", "`OrderLine.csv` 受領件数", "対象注文の明細行数と概ね対応"),
    Row("1.13", "`OrderCustomer.csv`/`Address.csv`/`DeliveryOrder.csv` 受領件数", "各ファイル存在・紐付け可能なこと", combine_1_13),
    Row("2.1", "赤星商店 CEC 会員データエクスポート件数", "CEC管理画面エクスポート件数"),
    Row("2.2", "決済プロファイルコードが登録済みであること", "管理画面で確認（手動）"),
    Row("2.3", "発送元コードが登録済みであること", "管理画面で確認（手動）"),
    Row("2.4", "配送方法コードが登録済みであること", "管理画面で確認（手動）"),
    Row("2.5", "配送温度帯IDが登録済みであること", "管理画面で確認（手動）"),
    Row("2.6", "SB00092 実行環境が本番相当に設定済みであること", "設定確認（手動）"),
    Row("2.7", "再実行時の重複防止動作確認（事前検証）", "ステージング環境での事前検証（手動）"),
    Row("2.8", "切り戻し（ロールバック）手順の事前整理", "ドキュメント化・共有済み（手動）"),
    Row("3.1", "会員CSV（新規登録用）件数", "別途カウント"),
    Row("3.2", "会員CSV（更新用）件数", "別途カウント"),
    Row("3.3", "3.1 + 3.2 = 1.3 と一致すること", "自動判定"),
    Row("3.4", "突合不能会員リスト件数", "0件であること"),
    Row("3.5", "旧サイト内メール重複リスト件数", "内容確認（最新UpdatedAt優先で集約）"),
    Row("3.6", "商品マスタ／販売基本情報／販売条件の行数", "1.5 と一致すること"),
    Row("3.7", "注文CSV（`order.csv`）件数", "1.11 と一致すること"),
    Row("3.8", "注文明細CSV（`order_detail.csv`）件数", "対象注文の明細行数と一致"),
    Row("3.9", "除外注文リストの内訳・理由確認", "理由別件数を確認", combine_3_9),
    Row("3.10", "会員CSVのサンプル値目視チェック", "サンプル確認（手動）"),
    Row("3.11", "注文金額サマリ突合（ETL段階）", "受領データ合計 = order.csv合計", combine_3_11),
    Row("3.12", "ETL生成データの値レベル突合（サンプル）", "サンプル確認（手動）"),
    Row("3.13", "エッジケースのシナリオ確認（ETLサンプル）", "サンプル確認（手動）"),
    Row("4.1", "会員データ新規登録：アップロード成功件数", "3.1 と一致すること（手動記録）"),
    Row("4.2", "会員データ新規登録：エラー件数", "0件であること（手動記録）"),
    Row("4.3", "会員データ更新：アップロード成功件数", "3.2 と一致すること（手動記録）"),
    Row("4.4", "会員データ更新：エラー件数", "0件であること（手動記録）"),
    Row("4.5", "商品データ登録：成功件数", "3.6 と一致すること（手動記録）"),
    Row("4.6", "商品データ登録：エラー件数", "0件であること（手動記録）"),
    Row("4.7", "`member.csv` エクスポート件数", "4.1 + 4.3 と一致すること（手動記録）"),
    Row("5.1", "S3配置ファイル確認", "手動確認"),
    Row("5.2", "SB00092（dbモード）：一時DB取込件数", "3.7 と一致すること（ログ解析 or 手動記録）"),
    Row("5.3", "SB00092（apiモード）：注文移行 成功件数", "5.2 と一致すること（ログ解析 or 手動記録）"),
    Row("5.4", "SB00092（apiモード）：注文移行 エラー件数", "0件であること（ログ解析 or 手動記録）"),
    Row("5.5", "重複チェックによるスキップ件数", "1回目のため0件想定（ログ解析 or 手動記録）"),
    Row("5.6", "ダミー注文作成件数", "1回目はSB00091未実施のため0件想定（ログ解析 or 手動記録）"),
    Row("5.7", "エラー・スキップ理由の内容確認", "ログ内容確認（手動）"),
    Row("5.8", "バッチ処理時間の記録", "ログ解析 or 手動記録"),
    Row("6.1", "会員最終登録件数（CEC管理画面で確認）", "4.1 + 4.3 と一致すること（手動記録）"),
    Row("6.2", "商品最終登録件数（CEC管理画面で確認）", "4.5 と一致すること（手動記録）"),
    Row("6.3", "注文最終登録件数（CEC管理画面で確認）", "5.3 と一致すること（手動記録）"),
    Row("6.4", "CEC管理画面：会員詳細表示（サンプル確認）", "手動確認"),
    Row("6.5", "CEC管理画面：商品詳細表示（サンプル確認）", "手動確認"),
    Row("6.6", "CEC管理画面：注文詳細表示（サンプル確認）", "手動確認"),
    Row("6.7", "ECサイト：マイページ注文履歴表示", "手動確認"),
    Row("6.8", "ECサイト：商品検索・カテゴリ表示・購入可否", "手動確認"),
    Row("6.9", "ECサイト：会員ログイン確認", "手動確認"),
    Row("6.10", "CEC最終登録後の会員データ値突合（サンプル）", "手動確認"),
    Row("6.11", "CEC最終登録後の商品データ値突合（サンプル）", "手動確認"),
    Row("6.12", "CEC最終登録後の注文データ値突合（サンプル）", "手動確認"),
    Row("6.13", "CEC最終登録後の注文合計金額突合", "3.11（order.csv合計）と一致すること（手動記録）"),
    Row("6.14", "CEC操作ログの記録確認", "手動確認"),
    Row("6.15", "お客様（サッポロビール様）レビュー結果", "手動確認"),
]

# 単純な2項比較（対象ID の値 == 比較対象ID の値 なら OK）。
# 1.3 / 3.3 / 4.7 / 6.1 / 6.13 / 3.11 は個別ロジックのため derive_judge() 側で直接処理する。
DERIVED_EQ: list[tuple[str, str]] = [
    ("3.6", "1.5"), ("3.7", "1.11"),
    ("4.1", "3.1"), ("4.3", "3.2"), ("4.5", "3.6"),
    ("5.2", "3.7"), ("5.3", "5.2"),
    ("6.2", "4.5"), ("6.3", "5.3"),
]
DERIVED_ZERO: list[str] = ["3.4", "4.2", "4.4", "5.4"]


def derive_judge(check_id: str, results: dict) -> str:
    if check_id == "1.3":
        v1, v2, v3 = to_num_result(results, "1.1"), to_num_result(results, "1.2"), to_num_result(results, "1.3")
        if None not in (v1, v2, v3):
            return "OK" if v3 == v1 - v2 else "NG"
        return ""
    if check_id == "3.3":
        a, b, c = to_num_result(results, "3.1"), to_num_result(results, "3.2"), to_num_result(results, "1.3")
        if None not in (a, b, c):
            return "OK" if a + b == c else "NG"
        return ""
    if check_id in DERIVED_ZERO:
        v = to_num_result(results, check_id)
        if v is None:
            return ""
        return "OK" if v == 0 else "NG"
    if check_id == "6.1":
        a, b, c = to_num_result(results, "4.1"), to_num_result(results, "4.3"), to_num_result(results, "6.1")
        if None not in (a, b, c):
            return "OK" if a + b == c else "NG"
        return ""
    if check_id == "4.7":
        a, b, c = to_num_result(results, "4.1"), to_num_result(results, "4.3"), to_num_result(results, "4.7")
        if None not in (a, b, c):
            return "OK" if a + b == c else "NG"
        return ""
    if check_id == "6.13":
        gen = results.get("3.11_order_csv_total")
        actual = to_num_result(results, "6.13")
        if gen and actual is not None:
            gen_val = to_num(gen["result"])
            if gen_val is not None:
                return "OK" if abs(gen_val - actual) < 0.01 else "NG"
        return ""
    if check_id == "3.11":
        raw = results.get("3.11_raw_total_payment")
        gen = results.get("3.11_order_csv_total")
        if raw and gen:
            raw_val, gen_val = to_num(raw["result"]), to_num(gen["result"])
            if raw_val is not None and gen_val is not None:
                return "OK" if abs(raw_val - gen_val) < 0.01 else "NG"
        return ""
    for target, other in DERIVED_EQ:
        if check_id == target and other:
            v_target, v_other = to_num_result(results, target), to_num_result(results, other)
            if v_target is not None and v_other is not None:
                return "OK" if v_target == v_other else "NG"
    return ""


def to_num_result(results: dict, check_id: str) -> float | None:
    r = results.get(check_id)
    if not r:
        return None
    return to_num(r["result"])


def format_row(row: Row, results: dict) -> str:
    r = results.get(row.check_id)
    if row.combine:
        result_str = row.combine(results)
        recorded_at = r["recorded_at"] if r else ""
        source = r.get("source", "") if r else ""
        judge = (r.get("judge") if r else "") or derive_judge(row.check_id, results)
    elif r:
        result_str = r["result"]
        recorded_at = r["recorded_at"]
        source = r.get("source", "")
        judge = r.get("judge") or derive_judge(row.check_id, results)
    else:
        judge = derive_judge(row.check_id, results)
        if judge:
            result_str = f"（自動判定: {judge}）"
            source = "derived"
        else:
            result_str = "未記入"
            source = ""
        recorded_at = ""

    by = (r.get("by") or "") if r else ""
    if r and r.get("auto") and not by:
        by = f"自動（{source}）"
    note = (r.get("note") or "") if r else ""

    return f"| {row.check_id} | {row.title} | {row.expected} | {recorded_at} | {by} | {result_str} | {judge} | {note} |"


def render() -> str:
    results = checklist.load_results(REPORTS)
    lines = [
        "# 1回目データ移行 作業チェックリスト（自動集計レポート）",
        "",
        "> 自動生成: `render_checklist_report.py`。手動確認項目は `record_manual_result.py` で記録した内容を反映する。",
        "> 本レポートは [1回目移行チェックリスト.md](../../docs/migration-policy/1回目移行チェックリスト.md) の実施記録を補助するものであり、",
        "> 最終的な承認・総合判定はチェックリスト本体（Excel/Markdown）側で管理者が行うこと。",
        "",
        "| # | チェック項目 | 期待値・確認方法 | 実施日時 | 実施者 | 結果 | 判定 | 備考 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in ROWS:
        lines.append(format_row(row, results))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render(), encoding="utf-8")
    print(f"checklist_report.md を生成しました: {OUT_PATH}")


if __name__ == "__main__":
    main()
