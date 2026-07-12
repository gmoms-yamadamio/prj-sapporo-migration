# productId → SKUコード / 販売条件コード 変換ルール

> 版: 暫定  
> 関連: [注文履歴明細CSV.md](../migration-policy/deliverables/注文履歴明細CSV.md)、[商品系Excel.md](../migration-policy/deliverables/商品系Excel.md)

## 結論

`OrderLine.productId` は `Products.csv` の **`Id`（内部商品ID）** と対応する。  
CEC への出力では `Products.ExternalId1` を **SKUコード** および **販売条件コード** に使用する（IF 設計書: 販売条件コード = 商品マスターコードと同一値）。

## 変換ルール

| 出力項目 | 入力元 | 変換 |
| --- | --- | --- |
| SKUコード | `OrderLine.productId` | `Products.Id` で検索 → `Products.ExternalId1` |
| 販売条件コード | 同上 | `Products.ExternalId1`（SKU と同一） |
| 販売価格 | `OrderLine.unitPrice` | そのまま（税抜） |
| 販売価格の税率 | `OrderLine.tax` | 下記税率変換表 |
| 数量 | `OrderLine.orderAmount` | そのまま |

### 例（サンプルデータ）

| productId | Products.ExternalId1 | 商品名（抜粋） |
| ---: | --- | --- |
| 381 | a12-z002ng-12 | 12種12本飲み比べコース |
| 70 | （Products.csv 参照） | — |

## 税率変換（暫定）

`OrderLine.tax` は金額列のため、税率コードへの変換は商品マスタまたは固定ルールが必要。

| 条件 | 出力（販売価格の税率） |
| --- | --- |
| サンプルでは `tax=0.00` が大半 | `10`（標準税率）を暫定デフォルト |
| 軽減税率商品 | 商品マスタ側の税区分で判定（要設計） |

## マスタ生成

`scripts/lib/product_lookup.py` が `Products.csv`（3 行ヘッダ）からルックアップテーブルを生成する。  
本番前に商品系 Excel 成果物のコードと突合すること。

## 未マッチ productId の扱い

- `Products.csv` に存在しない `productId` は `output/reports/unmatched_product_ids.csv` に出力
- 該当明細行は注文履歴明細 CSV から除外し、手動確認

## 改訂履歴

| 日付 | 内容 |
| --- | --- |
| 2026-07-01 | 初版。productId = Products.Id、SKU = ExternalId1 を確定 |
