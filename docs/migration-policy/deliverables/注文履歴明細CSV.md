# 注文履歴明細 CSV 作成方針

> 全体方針: [作業方針設計書.md](../作業方針設計書.md)  
> 項目定義: [【サッポロビール様】CSVファイルIF設計書.xlsx](../【サッポロビール様】CSVファイルIF設計書.xlsx) シート「注文履歴明細 CSV 項目」  
> 関連: [注文履歴CSV.md](./注文履歴CSV.md)

## 概要

| 項目 | 内容 |
|---|---|
| 成果物 | 注文履歴明細 CSV |
| 配置先 | `output/processed/` |
| 投入先 | 移行バッチ **SB00092** |
| 作成方法 | スクリプト |

## 入力データ

**`OrderLine.csv` のみ**を入力とする。

| データ | 配置先 | 役割 |
|---|---|---|
| `OrderLine.csv` | `input/raw/` | 注文明細（`orderId`, `productId`, `unitPrice`, `orderAmount` 等） |

※ `Products.csv` や商品系 Excel 成果物は使用しない。

## 生成ルール

- `OrderLine.csv` の各行を、弊社指定フォーマットの注文履歴明細 CSV 1 行に変換する
- **注文番号**には `OrderLine.orderId` を設定し、[注文履歴 CSV](./注文履歴CSV.md) と紐付ける
- **注文明細番号**は同一 `orderId` 内で 0 から採番する
- [注文履歴 CSV](./注文履歴CSV.md) のフィルタルールに従い、**ゲスト注文・キャンセル注文・削除済み会員の注文明細は出力しない**

## `OrderLine.csv` の主な項目（サンプルより）

| 列名 | 例 | 想定される用途 |
|---|---|---|
| `orderId` | 48597 | 注文番号 |
| `productId` | 381 | SKUコード / 販売条件コードへの変換元 |
| `unitPrice` | 7700.00 | 販売価格・基本販売価格 |
| `orderAmount` | 1 | 数量 |
| `linePrice` | 7700.00 | 明細金額 |
| `tax` | 0.00 | 税率関連 |

## IF 設計書との対応（暫定）

| 出力項目 | 入力元（`OrderLine.csv`） | 備考 |
|---|---|---|
| 注文番号 | `orderId` | 注文履歴 CSV と同一値 |
| 注文明細番号 | （採番） | 注文内で 0 から連番 |
| SKUコード | `productId` 等 | 変換ルール要設計 |
| 販売条件コード | `productId` 等 | IF 上は商品マスターコードと同一値 |
| 販売価格 | `unitPrice` 等 | 要設計 |
| 基本販売価格 | `unitPrice` / `reportPrice` 等 | 要設計 |
| 販売価格の税率 | `tax` 等 | 10 / 8 / 0 へ変換要設計 |
| 数量 | `orderAmount` 等 | 要設計 |
| 販売価格の税端数処理方法 | 固定値 | `floor`（IF 設計書） |

## 処理順序

[注文履歴 CSV](./注文履歴CSV.md) とセットで SB00092 へ投入する。  
入力は `OrderLine.csv` のみのため、会員 CSV・商品系 Excel とは独立して変換処理可能。

## 項目マッピング（SB00092 `order_detail.csv` 準拠）

> 2026-07-09: IF 設計書「注文履歴明細 CSV 項目」シートのシュパーク列マッピングを反映。基本販売価格の入力元を `reportPrice` に確定。税率の入力元に矛盾があることが判明（下記参照）。

| order_detail.csv 項目 | 必須 | 入力元 | 変換ルール |
| --- | --- | --- | --- |
| 注文番号 | 必須 | `OrderLine.orderId` | そのまま |
| 注文明細番号 | 必須 | — | 同一 `orderId` 内で 0 から連番 |
| SKUコード | 必須 | `OrderLine.productId` | [product-id-mapping.md](../../csv-interface/product-id-mapping.md) |
| 販売条件コード | 必須 | `OrderLine.productId` | SKU と同一（`Products.ExternalId1`） |
| 販売価格 | 必須 | `OrderLine.unitPrice` | 税抜。0 以上の正数 |
| 基本販売価格 | 必須 | `OrderLine.reportPrice` | **IF 設計書で確定**（`unitPrice` ではなく `reportPrice`） |
| 販売価格の税率 | 必須 | #21 SKU ホワイトリスト | `productId` → `ExternalId1` 変換後、軽減税率(8%)対象 12 SKU は `8`、それ以外 `10` |
| 数量 | 必須 | `OrderLine.orderAmount` | そのまま |
| 販売価格の税端数処理方法 | 必須 | — | 固定 `floor`（IF 設計書より） |

### 税率の決定方法（確定）

IF 設計書のシュパーク列は「販売価格の税率 ← `OrderLine.csv` / `taxRate`」と記載されているが、実際に受領した `OrderLine.csv` のヘッダーには **`taxRate` 列が存在しない**（金額としての `tax` はあるが税率としての `taxRate` はない）。`PurchaseOrder.taxRate` もサンプルでは全件 `0` のため利用不可。

**確定方針（[business-rules-confirmation.md](../business-rules-confirmation.md) #21 / #27）:**

1. `OrderLine.productId` → `Products.ExternalId1`（SKU）へ変換
2. SKU が `scripts/config/reduced_tax_skus.json` の一覧に含まれる → `8`
3. それ以外 → `10`

実装: `scripts/lib/product_lookup.py` の `tax_rate_for_sku` / `generate_order_detail.py`。

## 未確定事項（TODO）

- [x] `OrderLine.csv` 各列 → 注文履歴明細 CSV 各項目のマッピング
- [x] `productId` → `SKUコード` / `販売条件コード` への変換ルール
- [x] 基本販売価格の入力元 → `OrderLine.reportPrice`（IF 設計書で確定）
- [x] 同一 `orderId` に複数明細がある場合の明細番号採番ルール → 0 始まり連番
- [x] 税率（`販売価格の税率`）の変換方法 → SKU ホワイトリスト（8% 対象 12 SKU、それ以外 10%）で確定（#21 / #27）

## 改訂履歴

| 日付 | 版 | 内容 |
|---|---|---|
| 2026-06-27 | 1.0 | 作業方針設計書から分割作成 |
| 2026-07-09 | 1.1 | IF 設計書のシュパーク列マッピングを反映。基本販売価格を `reportPrice` に確定。税率ソースの矛盾（`taxRate` 列が実データに存在しない）を明記 |
| 2026-07-14 | 1.2 | 税率を SKU ホワイトリスト方式で確定（案 A の列追加は不要）。実装を `generate_order_detail.py` に反映 |
