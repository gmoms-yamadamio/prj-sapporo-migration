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
| 販売価格の税率 | 必須 | 未確定（下記「税率ソースの矛盾」参照） | `10`（標準）/ `8`（軽減）/ `0`（非課税） |
| 数量 | 必須 | `OrderLine.orderAmount` | そのまま |
| 販売価格の税端数処理方法 | 必須 | — | 固定 `floor`（IF 設計書より） |

### 税率ソースの矛盾（要確認）

IF 設計書のシュパーク列は「販売価格の税率 ← `OrderLine.csv` / `taxRate`」と記載されているが、実際に受領した `OrderLine.csv` のヘッダーには **`taxRate` 列が存在しない**（`orderLineId,orderLineType,orderId,...,unitPrice,reportPrice,linePrice,tax,...` で、金額としての `tax` はあるが税率としての `taxRate` はない）。

一方、`PurchaseOrder.csv` には注文ヘッダ単位で `taxRate` 列が存在する（サンプルでは全件 `0`）。

**軽減税率対象商品（8%）は存在することが確定している**ため、固定 `10` の一律適用は不可。商品単位の税率を保持する必要がある。

| 案 | 内容 | 課題 |
| --- | --- | --- |
| A | `Products.csv` に税率列を追加してもらい、SKU 単位の税率を適用 | **お客様調整中**（税率列を含めて受領する方向）。受領後はこれを正とする（第一候補） |
| B | `PurchaseOrder.taxRate`（注文単位）を明細全行に適用 | 注文単位のため明細ごとの軽減／標準の混在に対応できない。サンプルは全件 `0` |
| C（旧・暫定実装） | 固定 `10` をデフォルト適用 | 軽減税率商品（8%）が存在するため**誤りとなる（不可）** |

→ 案 A（`Products.csv` の税率列）での対応を前提に、税率列の受領を待って実装・検証する（[business-rules-confirmation.md](../business-rules-confirmation.md) #21・#27）。

## 未確定事項（TODO）

- [x] `OrderLine.csv` 各列 → 注文履歴明細 CSV 各項目のマッピング
- [x] `productId` → `SKUコード` / `販売条件コード` への変換ルール
- [x] 基本販売価格の入力元 → `OrderLine.reportPrice`（IF 設計書で確定）
- [x] 同一 `orderId` に複数明細がある場合の明細番号採番ルール → 0 始まり連番
- [ ] 税率（`販売価格の税率`）の変換方法 → **軽減税率(8%)対象商品が存在するため固定 `10` は不可**。`Products.csv` への税率列追加をお客様調整中（案 A）。税率列受領後に実装・検証（[business-rules-confirmation.md](../business-rules-confirmation.md) #21・#27）

## 改訂履歴

| 日付 | 版 | 内容 |
|---|---|---|
| 2026-06-27 | 1.0 | 作業方針設計書から分割作成 |
| 2026-07-09 | 1.1 | IF 設計書のシュパーク列マッピングを反映。基本販売価格を `reportPrice` に確定。税率ソースの矛盾（`taxRate` 列が実データに存在しない）を明記 |
