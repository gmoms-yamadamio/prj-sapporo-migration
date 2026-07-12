# 注文履歴 CSV 作成方針

> 全体方針: [作業方針設計書.md](../作業方針設計書.md)  
> 項目定義: [【サッポロビール様】CSVファイルIF設計書.xlsx](../【サッポロビール様】CSVファイルIF設計書.xlsx) シート「注文履歴 CSV 項目」  
> 関連: [注文履歴明細CSV.md](./注文履歴明細CSV.md)

## 概要

| 項目 | 内容 |
|---|---|
| 成果物 | 注文履歴 CSV |
| 配置先 | `output/processed/` |
| 投入先 | 移行バッチ **SB00092** |
| 作成方法 | スクリプト |

## 入力データ

| データ | 配置先 | 役割 |
|---|---|---|
| `PurchaseOrder.csv` | `input/raw/` | 注文ヘッダ（`orderId`, `customerId`, `siteId`, 金額, 注文日, `taxRate` 等） |
| `OrderCustomer.csv` | `input/raw/` | 注文者情報（`customerId`, `UserNo`, `isGuest`, 氏名, `emailAddr`, `orderedAddressId` 等） |
| `Address.csv` | `input/raw/` | 住所詳細（`addressId`, 氏名, 郵便番号, 都道府県 等）※購入者住所用 |
| `DeliveryOrder.csv` | `input/raw/` | 配送先情報（`orderId`, `addressId`, `mailAddr` 等）※受取人住所用 |
| `OrderLine.csv` | `input/raw/` | 注文明細（税額合計・小計の算出に使用。明細本体は [注文履歴明細CSV](./注文履歴明細CSV.md) 参照） |
| `User.csv` | `input/raw/` | 会員基本情報（メールアドレス等） |
| `UserAccount.csv` | `input/raw/` | 会員アカウント（`UserNo` 等） |

※ 本加工では `PurchaseOrderService.csv` は使用しない。

> **IF 設計書からの修正点（2026-07-09 反映）**: 当初 `DeliveryOrder.csv` は「使用しない」としていたが、【サッポロビール様】CSVファイルIF設計書.xlsx「注文履歴 CSV 項目」シートのシュパーク列マッピングを確認した結果、**受取人情報の住所 ID は `OrderCustomer.invoiceAddressId` ではなく `DeliveryOrder.addressId`** であることが判明したため、入力データに追加した（[join-keys.md](../../csv-interface/join-keys.md) 参照）。サンプルデータでは `PurchaseOrder.csv` の全 100 件に対し `DeliveryOrder.csv` が 1:1 で存在する（分割配送なし）。

## データの結合イメージ

```
PurchaseOrder (orderId, customerId, siteId, 金額, taxRate...)
    ├─→ OrderCustomer (customerId)
    │       ├─→ UserAccount (UserNo) → User.csv … 会員メールアドレス
    │       └─→ Address.csv (orderedAddressId) … 購入者住所
    ├─→ DeliveryOrder (orderId) → Address.csv (addressId) … 受取人住所
    │       └─→ DeliveryOrder.mailAddr … 受取人メールアドレス（未設定時は購入者メールアドレスで補完）
    └─→ OrderLine (orderId) … 税額合計（tax 合算）・小計（linePrice 合算）
```

## 生成ルール

- 1 注文（`PurchaseOrder.orderId`）につき 1 行を出力する
- **注文番号**（`PurchaseOrder.orderId`）で [注文履歴明細 CSV](./注文履歴明細CSV.md) と紐付ける
- **注文日**は IF 設計書に従い `yyyymmddhhmiss` 形式（14 桁）に変換する
- **サイトコード**は一律 `shupark`（移行元はシュパーク 1 サイトのため、旧 `siteId` は参照しない）

## 会員 CSV との連携（会員 ID 欄）

**会員 ID（メールアドレス）** 欄は、会員 CSV の突合結果に応じて設定する。

| 注文の会員 | 会員 ID（メールアドレス）欄 |
|---|---|
| 会員注文（`OrderCustomer.isGuest = 0`）かつ会員 CSV: 新規 `C` | 旧サイト `User.csv` のメールアドレス |
| 会員注文かつ会員 CSV: 更新 `U`（赤星商店登録済） | 赤星商店 CEC 側のメールアドレス |
| ゲスト注文（`OrderCustomer.isGuest = 1`） | **移行対象外**（出力しない） |

- SB00092 は会員 ID 欄のメールアドレスで CEC 会員と紐付けて注文を登録する

## 購入者・受取人の取得（確定）

IF 設計書「注文履歴 CSV 項目」シートのシュパーク列（ファイル名・項目名）に基づき、以下の通り確定する。

| 対象 | 氏名・メール | 住所（郵便番号〜建物名・電話番号） |
|---|---|---|
| 購入者 | `OrderCustomer.csv`（`lastName`/`firstName`/`lastNameKana`/`firstNameKana`/`emailAddr`） | `Address.csv`（`OrderCustomer.orderedAddressId` で結合） |
| 受取人 | `Address.csv`（`recipientlastname`/`recipientfirstname`/`recipientlastnamekana`/`recipientfirstnamekana`）＋メールは `DeliveryOrder.mailAddr` | `Address.csv`（`DeliveryOrder.addressId` で結合。`DeliveryOrder.csv` は `PurchaseOrder.orderId` で結合） |

- 受取人メールアドレスが未設定の場合は購入者メールアドレスで補完する（IF 設計書の記載に基づく）
- IF 設計書上は受取人メールアドレスの参照元が「`Address.csv` / `mailAddr`」と記載されているが、`Address.csv` に `mailAddr` 列は存在しない（実際は `DeliveryOrder.csv` に存在）。**実データのスキーマに合わせて `DeliveryOrder.mailAddr` を正とする**（IF 設計書側の誤記と判断。要お客様確認）

## 処理順序

会員 CSV の突合・振り分けが完了した後に作成する。  
注文履歴明細 CSV と同時期に SB00092 へ投入する。

## 項目マッピング（SB00092 `order.csv` 準拠）

> 2026-07-09: IF 設計書「注文履歴 CSV 項目」シート（No.1〜52、シュパーク列）の全項目を反映。従来の抜粋版マッピングを置き換え。

結合: `PurchaseOrder.customerId` → `OrderCustomer` → `Address`（購入者）/ `DeliveryOrder` → `Address`（受取人）/ `User`（[join-keys.md](../../csv-interface/join-keys.md)）

| order.csv 項目 | 必須 | 入力元 | 変換ルール |
| --- | --- | --- | --- |
| 注文番号 | 必須 | `PurchaseOrder.orderId` | そのまま |
| サイトコード | 必須 | — | 固定 `shupark` |
| 会員ID（メールアドレス） | 必須 | 会員 CSV 突合結果（元データは `OrderCustomer.emailAddr`） | 会員注文のみ。突合結果メールを設定 |
| 注文日 | 必須 | `PurchaseOrder.orderDate` | `yyyymmddhhmiss`（14 桁） |
| 合計金額 | 必須 | `PurchaseOrder.totalPayment` | 整数文字列。税込み |
| 税額合計 | 必須 | `OrderLine.tax` | **同一 `orderId` の明細行の `tax` を合算**（IF 設計書で確定。従来の `0` 固定を廃止） |
| 小計 | 必須 | `OrderLine.linePrice` | **同一 `orderId` の明細行の `linePrice` を合算**（IF 設計書で確定。従来の `totalPayment - deliveryCharge` 計算を廃止） |
| 配送料 | 必須 | `PurchaseOrder.deliveryCharge` | そのまま |
| 調整金額 | 必須 | `PurchaseOrder.discountPrice` | **マイナス（-）の値**で設定（IF 設計書の属性が「ハイフン半角数字」。符号がプラスの場合は反転。本番データで符号を要確認） |
| 管理グループコード | 必須 | — | 固定 `shupark` |
| 購入者氏名（苗字/名） | 必須 | `OrderCustomer.lastName` / `firstName` | そのまま |
| 購入者氏名カナ（苗字/名） | 必須 | `OrderCustomer.lastNameKana` / `firstNameKana` | そのまま |
| 購入者メールアドレス | 必須 | `OrderCustomer.emailAddr` | そのまま |
| 購入者電話番号 | 必須 | `Address.tel`（`orderedAddressId`） | そのまま |
| 購入者郵便番号〜町名・番地 | 必須 | `Address`（`orderedAddressId`） | `zipCode` / `pref` / `city` / `street` |
| 購入者建物名〜役職 | 任意 | `Address`（`orderedAddressId`） | `building`。会社名・会社名カナ・部署名・役職は旧データになし（空） |
| 受取人氏名（苗字/名） | 必須 | `Address.recipientlastname` / `recipientfirstname`（`DeliveryOrder.addressId`） | そのまま |
| 受取人氏名カナ（苗字/名） | 必須 | `Address.recipientlastnamekana` / `recipientfirstnamekana`（同上） | そのまま |
| 受取人メールアドレス | 任意 | `DeliveryOrder.mailAddr` | 未設定時は購入者メールアドレスで補完（IF 設計書は `Address.mailAddr` と記載だが実データに存在せず、`DeliveryOrder.mailAddr` に読み替え） |
| 受取人電話番号〜町名・番地 | 必須 | `Address`（`DeliveryOrder.addressId`） | `tel` / `zipCode` / `pref` / `city` / `street` |
| 受取人建物名〜役職 | 任意 | `Address`（同上） | `building`。会社名以下は空 |
| 調整金額の税率 | 任意 | — | 固定 `10`（IF 設計書の説明列より。税率 10% 前提） |
| 調整金額の税区分ID | 任意 | — | 固定 `tax_type_standard`（IF 設計書の説明列より） |
| 決済プロファイルコード | 必須 | — | 固定 `migration-xxxxx`（データ移行用決済コード。**実際の値は未確定・要確認**） |
| 決済手数料 | 任意 | — | 固定 `0` |
| 決済手数料の税率 | 任意 | — | 固定 `10` |
| 発送元コード | 必須 | — | 固定 `migration-xxxxx`（データ移行用発送元コード。**実際の値は未確定・要確認**） |
| 配送温度帯ID | 必須 | — | 固定値（[商品系Excel.md](./商品系Excel.md) の販売条件と表記揺れあり。`A1111` or `T1111` 要確認） |
| 配送方法コード | 必須 | — | 固定 `migration-xxxxx`（データ移行用配送方法コード。**実際の値は未確定・要確認**） |
| 配送料の税率 | 必須 | — | 固定 `10` |
| 基本配送料 | 必須 | `PurchaseOrder.deliveryCharge` | 配送料と同値を設定 |
| 在庫引当フラグ | 必須 | — | 固定 `0` |

> `決済プロファイルコード` / `発送元コード` / `配送方法コード` の実値（`migration-xxxxx` 部分）は IF 設計書上プレースホルダのままで、CEC 側の実際のマスタ登録値が未確定。本番移行前に確定が必要（[business-rules-confirmation.md](../business-rules-confirmation.md) に追記）。

## フィルタルール（確定）

| 条件 | 処理 |
| --- | --- |
| ゲスト注文（`isGuest=1`） | **移行対象外**。`output/reports/excluded_orders.csv` に記録 |
| キャンセル（`orderStatus=10`） | **移行対象外**。同上 |
| 削除済み会員の注文 | **移行対象外**（`reason=deleted_member`）。同上 |
| 会員注文で User 結合不能 | `output/reports/unmatched_order_members.csv` |

## 出荷完了の判定条件（確定）

各回の移行対象を「出荷完了」で絞り込む際（[1回目移行手順書.md](../1回目移行手順書.md) 等）の判定条件。

| 項目 | 内容 |
| --- | --- |
| 方針 | `PurchaseOrder.shipDate` が **NULL 以外**（出荷日が設定されている）の場合を「出荷完了」と判定する |
| 状態 | **確定**（本番データで確認済み） |

### サンプルデータでの確認結果（2026-07-11 時点）

`input/raw/PurchaseOrder.csv`（サンプル100件）を確認したところ、以下の状況であった。

- `shipDate` / `deliveryCompleteDate` / `deliveryReportDate` は**全100件が NULL**（サンプルデータ内では出荷完了と判定できる行が1件も存在しない）
- `orderStatus` は `0`（82件）と `10`（キャンセル、18件）の2値のみ

サンプルデータでは本条件の妥当性を検証できなかったが、**本番データで確認した結果、`shipDate` を判定条件として採用することが確定した**。サンプルデータは出荷実績が反映されていない（またはマスクされた）テストデータであるため、上記の全件 NULL という結果は本番データの実態を表していない。

## 未確定事項（TODO）

- [x] `PurchaseOrder` 各金額項目 → 注文履歴 CSV 各項目のマッピング
- [x] 旧 `siteId` → サイトコード / 管理グループコードの変換表
- [x] 購入者・受取人の住所 ID の使い分け → **購入者: `OrderCustomer.orderedAddressId` / 受取人: `DeliveryOrder.addressId`（IF 設計書で確定、`invoiceAddressId` は使用しない）**
- [x] ゲスト注文の移行対象可否 → **移行対象外**
- [x] キャンセル済み注文の移行対象可否 → **移行対象外**
- [x] `User` / `UserAccount` / `OrderCustomer.UserNo` の結合ロジック
- [x] 税額合計の算出方法 → **`OrderLine.tax` の `orderId` 単位合算（IF 設計書で確定）**
- [x] 小計の算出方法 → **`OrderLine.linePrice` の `orderId` 単位合算（IF 設計書で確定。従来の減算方式は廃止）**
- [ ] 調整金額（`discountPrice`）の符号（マイナス表記が必須のため、旧データが正数の場合は反転が必要。本番データで検証）
- [ ] 決済プロファイルコード／発送元コード／配送方法コードの実際の固定値（`migration-xxxxx` の具体値）
- [ ] 配送温度帯ID の固定値（IF 設計書本文は `A1111`、サンプル行は `T1111` で表記が食い違う。要お客様確認）
- [ ] 受取人メールアドレスの参照元列（IF 設計書は `Address.mailAddr` と記載だが実データには存在しない。`DeliveryOrder.mailAddr` への読み替えを暫定採用）
- [x] 「出荷完了」の判定条件 → **`PurchaseOrder.shipDate` が NULL 以外（確定。本番データで確認済み）**（[出荷完了の判定条件（確定）](#出荷完了の判定条件確定) 参照）

## 改訂履歴

| 日付 | 版 | 内容 |
|---|---|---|
| 2026-06-27 | 1.0 | 作業方針設計書から分割作成 |
| 2026-07-01 | 1.1 | ゲスト・キャンセル注文を移行対象外に確定 |
| 2026-07-09 | 1.2 | IF 設計書「注文履歴 CSV 項目」シートのシュパーク列マッピングを全項目反映。受取人住所ソースを `DeliveryOrder.addressId` に修正（`invoiceAddressId` は誤り）。税額合計・小計の算出方法を確定。決済・配送関連の固定値項目（決済プロファイルコード等）を追加 |
| 2026-07-11 | 1.3 | 「出荷完了の判定条件（暫定）」を追加。`PurchaseOrder.shipDate` の NULL 以外判定を暫定採用。サンプルデータでは全件 NULL のため本番データでの検証が必要な旨を明記 |
| 2026-07-11 | 1.4 | 「出荷完了」の判定条件（`shipDate` 基準）を本番データで確認済みとして確定 |
