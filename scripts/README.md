# データ移行 ETL スクリプト

旧サイト生 CSV から弊社指定フォーマット CSV を `output/processed/` に生成する。

## 前提

- Python 3.10+
- 標準ライブラリのみ（追加パッケージ不要）

## ディレクトリ構成

```text
scripts/
├── config/
│   ├── site_id_mapping.json    # サイトコード定数（一律 shupark）
│   └── round_rules.json        # 移行ラウンド（1〜3回目）ごとの注文抽出ルール
├── lib/
│   ├── csv_io.py               # CSV 読込・書込
│   ├── join_keys.py            # 結合キー・会員突合（重複メール検出含む）
│   ├── transforms.py           # 値変換（日付・性別・都道府県等）
│   ├── order_filters.py        # 注文の移行対象判定（出荷完了・カットオフ日付等）
│   ├── round_config.py         # 移行ラウンド設定の読込み
│   ├── product_lookup.py       # Products.csv ルックアップ
│   └── checklist.py            # チェックリスト結果の自動記録
├── generate_receipt_stats.py   # 受領データ件数の自動集計（チェックリスト§1・2.1）
├── generate_member.py          # 会員 CSV（新規/更新の2ファイルに分割）
├── generate_address.py         # 会員アドレス帳 CSV
├── generate_point.py           # 会員ポイント CSV（SB00091 入力）
├── generate_order.py           # 注文履歴 CSV（SB00092 入力）
├── generate_order_detail.py    # 注文履歴明細 CSV
├── generate_product_reference.py  # 商品 SKU 参照表
├── render_checklist_report.py  # チェックリスト自動集計レポート生成
├── record_manual_result.py     # 手動確認項目の結果記録CLI
├── parse_sb00092_log.py        # SB00092 実行ログ解析（バッチ件数・処理時間）
└── run_all.py                  # 一括実行（受領統計→ETL→チェックリストレポートの順）
```

## 実行方法

```bash
cd data-migration-etl
python scripts/run_all.py
```

個別実行:

```bash
python scripts/generate_member.py
```

## 入力

| パス | 内容 |
| --- | --- |
| `input/raw/*.csv` | 旧サイト生 CSV |
| `input/cec/member_export.csv` | 赤星商店 CEC 会員エクスポート（なければ `member_export_sample.csv`） |

## 出力

| パス | 内容 |
| --- | --- |
| `output/processed/member_import_create.csv` | 会員 CSV（新規登録用。パターンA `C`） |
| `output/processed/member_import_update.csv` | 会員 CSV（更新用。パターンB `U`） |
| `output/processed/address_import.csv` | 会員アドレス帳 CSV |
| `output/processed/member_point.csv` | SB00091 入力 |
| `output/processed/order.csv` | SB00092 入力 |
| `output/processed/order_detail.csv` | SB00092 入力 |
| `output/products/product_sku_reference.csv` | 商品 SKU 参照表 |
| `output/reports/*.csv` | 突合不能・未マッチ・除外注文・重複メール等のレポート |
| `output/reports/checklist_results.json` | チェックリスト結果の生データ（自動/半自動/手動記録の集約） |
| `output/reports/checklist_report.md` | チェックリスト自動集計レポート（Markdown） |

## 移行ラウンドの切り替え（注文抽出ルール）

注文データの抽出条件（注文日カットオフ・出荷完了要否）は環境変数 `MIGRATION_ROUND`（既定 `1`）で切り替える。
ルール本体は `config/round_rules.json` を参照。

```bash
MIGRATION_ROUND=1 python scripts/generate_order.py   # 1回目: 注文日6/30以前 かつ 出荷完了
MIGRATION_ROUND=2 python scripts/generate_order.py   # 2回目: 前回未移行 かつ 出荷完了（前回移行済みIDの指定は未実装）
```

## チェックリストの自動入力

[1回目移行チェックリスト.md](../docs/migration-policy/1回目移行チェックリスト.md) の実施結果は、可能な限りスクリプト実行時に自動入力する。

```bash
python scripts/run_all.py                                  # ETL一括実行 + チェックリストレポート生成
python scripts/record_manual_result.py 2.2 "migration-payment001" --by "山田" --judge OK
python scripts/parse_sb00092_log.py sb00092_run1.log --mode api
python scripts/render_checklist_report.py                  # レポートのみ再生成
```

詳細はチェックリスト本体の「0. 結果の自動入力について」を参照。

## 本番移行時の実行順序

1. `run_all.py` で CSV 生成（受領統計→ETL→チェックリストレポートの順に自動実行）
2. 会員 CSV（新規用・更新用）を CEC 管理画面にそれぞれインポート
3. CEC から `member.csv` をエクスポート → `input/cec/member.csv`
4. SB00091 実行（`member_point.csv` + `member.csv`）
5. SB00092 実行（`order.csv` + `order_detail.csv` + `member.csv`）
6. SB00092 実行ログを `parse_sb00092_log.py` で解析し、チェックリストの§5を記録

詳細は [作業方針設計書.md](../docs/migration-policy/作業方針設計書.md) §12 を参照。
