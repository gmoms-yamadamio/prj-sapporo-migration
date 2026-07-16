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
    │       └─→ 受取人メールアドレス … 暫定でブランク（空値）出力（#28・要お客様合意）
    └─→ OrderLine (orderId) … 税額合計（tax 合算）・小計（linePrice 合算）
```

## 生成ルール

- 1 注文（`PurchaseOrder.orderId`）につき 1 行を出力する
- **注文番号**（`PurchaseOrder.orderId`）で [注文履歴明細 CSV](./注文履歴明細CSV.md) と紐付ける
- **注文日**は IF 設計書に従い `yyyymmddhhmiss` 形式（14 桁）に変換する
- **サイトコード**は一律 `shupark`（移行元はシュパーク 1 サイトのため、旧 `siteId` は参照しない）

## 会員 CSV との連携（会員 ID 欄）

**会員 ID（メールアドレス）** 欄は、会員注文の場合は一律「旧サイト `User.csv` のメールアドレス」を設定する（**2026-07-14 確定・ロジック簡略化**）。

| 注文の会員 | 会員 ID（メールアドレス）欄 |
|---|---|
| 会員注文（`OrderCustomer.isGuest = 0`） | 旧サイト `User.csv` のメールアドレス（`OrderCustomer.UserNo` → `UserAccount.UserNo` → `UserAccount.UserName = User.Id` で結合） |
| ゲスト注文（`OrderCustomer.isGuest = 1`） | **移行対象外**（出力しない） |

- SB00092 は会員 ID 欄のメールアドレスで CEC 会員と紐付けて注文を登録する
- 会員 CSV の赤星商店 CEC 会員との突合は**メールアドレス一致**で行うため、更新パターン（`U`）の会員は定義上 `User.csv` のメールアドレスと CEC 側メールアドレスが一致する。したがって、注文側では会員 CSV の突合結果（新規 `C` / 更新 `U` の判定、CEC 側メールアドレスの取得）を経由せず、`User.csv` のメールアドレスを直接参照する（旧: 会員 CSV の突合パターンに応じて参照元を切り替える方式から変更。ロジック簡略化のため）

## 購入者・受取人の取得（確定）

IF 設計書「注文履歴 CSV 項目」シートのシュパーク列（ファイル名・項目名）に基づき、以下の通り確定する。

| 対象 | 氏名・メール | 住所（郵便番号〜建物名・電話番号） |
|---|---|---|
| 購入者 | `OrderCustomer.csv`（`lastName`/`firstName`/`lastNameKana`/`firstNameKana`/`emailAddr`） | `Address.csv`（`OrderCustomer.orderedAddressId` で結合） |
| 受取人 | `Address.csv`（`recipientlastname`/`recipientfirstname`/`recipientlastnamekana`/`recipientfirstnamekana`）＋メールは**暫定ブランク**（#28・要お客様合意） | `Address.csv`（`DeliveryOrder.addressId` で結合。`DeliveryOrder.csv` は `PurchaseOrder.orderId` で結合） |

- 受取人メールアドレスは**暫定でブランク（空値）出力**（お客様合意が必要。[business-rules-confirmation.md](../business-rules-confirmation.md) #28）
- IF 設計書上は受取人メールアドレスの参照元が「`Address.csv` / `mailAddr`」と記載されているが、`Address.csv` に `mailAddr` 列は存在しない（実際は `DeliveryOrder.csv` に存在）。`DeliveryOrder.mailAddr` への読み替えも候補だが、現時点はブランク出力の暫定方針とし、参照元をお客様に確認する

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
| 会員ID（メールアドレス） | 必須 | `User.csv` の `Email`（`OrderCustomer.UserNo` → `UserAccount` → `User` で結合） | 会員注文のみ。旧サイトのメールアドレスを一律設定（会員CSV突合結果は経由しない） |
| 注文日 | 必須 | `PurchaseOrder.orderDate` | `yyyymmddhhmiss`（14 桁） |
| 合計金額 | 必須 | `PurchaseOrder.totalPayment` | 整数文字列。税込み |
| 税額合計 | 必須 | `OrderLine.tax` | **同一 `orderId` の明細行の `tax` を合算**（IF 設計書で確定。従来の `0` 固定を廃止） |
| 小計 | 必須 | `OrderLine.linePrice` | **同一 `orderId` の明細行の `linePrice` を合算**（IF 設計書で確定。従来の `totalPayment - deliveryCharge` 計算を廃止） |
| 配送料 | 必須 | `PurchaseOrder.deliveryCharge` | そのまま |
| 調整金額 | 必須 | `PurchaseOrder.discountPrice` | **マイナス（-）の値**で設定（IF 設計書の属性が「ハイフン半角数字」。符号がプラスの場合は反転。本番データで符号を要確認） |
| 管理グループコード | 必須 | — | 固定 `sp_common`（**2026-07-14 修正**。従来 `shupark` としていたが、商品系（`sp_common`）と統一。詳細は [作業方針設計書.md](../作業方針設計書.md) §9 参照） |
| 購入者氏名（苗字/名） | 必須 | `OrderCustomer.lastName` / `firstName` | そのまま |
| 購入者氏名カナ（苗字/名） | 必須 | `OrderCustomer.lastNameKana` / `firstNameKana` | そのまま |
| 購入者メールアドレス | 必須 | `OrderCustomer.emailAddr` | そのまま |
| 購入者電話番号 | 必須 | `Address.tel`（`orderedAddressId`） | そのまま |
| 購入者郵便番号〜町名・番地 | 必須 | `Address`（`orderedAddressId`） | `zipCode` / `pref` / `city` / `street` |
| 購入者建物名〜役職 | 任意 | `Address`（`orderedAddressId`） | `building`。会社名・会社名カナ・部署名・役職は旧データになし（空） |
| 受取人氏名（苗字/名） | 必須 | `Address.recipientlastname` / `recipientfirstname`（`DeliveryOrder.addressId`） | そのまま |
| 受取人氏名カナ（苗字/名） | 必須 | `Address.recipientlastnamekana` / `recipientfirstnamekana`（同上） | そのまま |
| 受取人メールアドレス | 任意 | — | **ブランク（空値）で出力**（暫定方針。お客様合意が必要。IF 設計書は `Address.mailAddr` と記載だが実データに存在せず、`DeliveryOrder.mailAddr` への読み替えは採用しない） |
| 受取人電話番号〜町名・番地 | 必須 | `Address`（`DeliveryOrder.addressId`） | `tel` / `zipCode` / `pref` / `city` / `street` |
| 受取人建物名〜役職 | 任意 | `Address`（同上） | `building`。会社名以下は空 |
| 調整金額の税率 | 任意 | — | 固定 `10`（IF 設計書の説明列より。税率 10% 前提） |
| 調整金額の税区分ID | 任意 | — | 固定 `tax_type_standard`（IF 設計書の説明列より） |
| 決済方法グループコード | 必須 | — | 固定 `migration-pay-group`（データ移行用決済方法グループコード。**確定**。[商品系Excel.md](./商品系Excel.md) の販売条件と統一） |
| 決済手数料 | 任意 | — | 固定 `0` |
| 決済手数料の税率 | 任意 | — | 固定 `10` |
| 発送元コード | 必須 | — | 固定 `migration-warehouse`（データ移行用発送元コード。**確定**） |
| 配送温度帯ID | 必須 | — | 固定 `T1111`（**確定**。[商品系Excel.md](./商品系Excel.md) の販売条件と統一） |
| 配送方法グループコード | 必須 | — | 固定 `migration-delivery-group`（データ移行用配送方法グループコード。**確定**。[商品系Excel.md](./商品系Excel.md) の販売条件と統一） |
| 配送料の税率 | 必須 | — | 固定 `10` |
| 基本配送料 | 必須 | `PurchaseOrder.deliveryCharge` | 配送料と同値を設定 |
| 在庫引当フラグ | 必須 | — | 固定 `0` |

> `決済方法グループコード` / `発送元コード` / `配送方法グループコード` の実値は **`migration-pay-group` / `migration-warehouse` / `migration-delivery-group` で確定**（[business-rules-confirmation.md](../business-rules-confirmation.md) #26）。これらのコードが CEC 本番マスタに登録済みであることを本番移行前に確認すること。

## フィルタルール（確定）

| 条件 | 処理 |
| --- | --- |
| 削除済み会員の注文 | **移行対象外**（`reason=deleted_member`）。`output/reports/excluded_orders.csv` に記録 |
| ゲスト注文（`isGuest=1`） | **移行対象外**。同上（`reason=guest`） |
| キャンセル（`orderStatus=10`） | **移行対象外**。同上（`reason=cancelled`） |
| 会員注文で User 結合不能 | `output/reports/unmatched_order_members.csv` |

> **除外理由の判定優先順位**: 削除済み会員 → ゲスト → キャンセル → 二重移行済 → 移行対象期間外 → 未出荷、の順で判定する（`lib/order_filters.py` `exclusion_reason()`）。削除済み会員の注文がキャンセル済みである等、複数の除外条件に該当する場合でも `excluded_orders.csv` の `reason` は常に `deleted_member` を優先して記録し、除外理由の内訳集計（[1回目移行チェックリスト.md](../1回目移行チェックリスト.md) 3.9）が会員単位の除外を正しく反映するようにしている。

## 海外住所を含む配送先（要確認）

移行対象注文の購入者／受取人住所は、それぞれ `OrderCustomer.orderedAddressId`／`DeliveryOrder.addressId` 経由で `Address.csv` を参照する。旧サイトデータには、**日本国内の7桁郵便番号・47都道府県形式に合致しない海外住所**が含まれる。

### クラウドEC（CEC）の制約

| 項目 | CEC の仕様 | 旧サイト `Address.csv` との差異 |
| --- | --- | --- |
| 郵便番号 | **7桁の半角数字に限定** | 海外住所は3桁・6桁・9桁等（例: `141`, `200433`, `113725522`） |
| 都道府県 | **必須**（47都道府県） | 英語表記（`Tokyo-to`, `Kanagawa-k` 等）や州コード（`NY`, `AB` 等）が存在 |
| 海外発送 | **非対応** | カナダ・米国・中国等の住所が `Address.csv` に存在 |

### 現行データでの影響（参考）

`generate_receipt_stats.py` の `Address.csv` 項目値検証（移行データ受領チェック 1.23〜1.25）および移行対象注文との突合（2026-07-16 時点）:

| 観点 | 件数 | 備考 |
| --- | --- | --- |
| `Address.csv` 郵便番号不正（7桁以外） | 3件 | いずれも海外住所（カナダ・米国・中国） |
| `Address.csv` 都道府県不正（47都道府県名以外） | 120件 | 英語表記・州コード等 |
| 移行対象注文のうち、購入者住所（`orderedAddressId`）が上記観点で問題あり | **48件** | 受取人住所（`DeliveryOrder.addressId`）のみ問題の注文は0件（現データ） |

※ 上記48件の注文は、現行のフィルタルール上は**移行対象に含まれる**。会員アドレス帳 CSV とは異なり、`UserAddress.csv` 未登録であっても注文履歴 CSV では購入者／受取人住所として `Address.csv` の値がそのまま出力される。

### 要確認事項

- [ ] **海外住所を含む移行対象注文の扱い** — 除外するか、国内形式への変換・ダミー値投入等で移行するか、お客様・CEC仕様と合わせて方針を決定する
- [ ] SB00092／CEC API が、7桁以外の郵便番号・47都道府県以外の都道府県を含む `order.csv` を受け付けるか（エラーになる場合は ETL 段階での対処が必要）

> 関連: [会員アドレス帳CSV.md](./会員アドレス帳CSV.md)（`Address.csv` の末尾スペース・都道府県表記ゆれ）、移行データ受領チェック 1.23〜1.25、`output/reports/address_csv_validation_errors.csv`

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
- [x] 旧 `siteId` → サイトコード / 管理グループコードの変換表 → サイトコード `shupark` / 管理グループコード `sp_common`（2026-07-14 確定）
- [x] 購入者・受取人の住所 ID の使い分け → **購入者: `OrderCustomer.orderedAddressId` / 受取人: `DeliveryOrder.addressId`（IF 設計書で確定、`invoiceAddressId` は使用しない）**
- [x] ゲスト注文の移行対象可否 → **移行対象外**
- [x] キャンセル済み注文の移行対象可否 → **移行対象外**
- [x] `User` / `UserAccount` / `OrderCustomer.UserNo` の結合ロジック
- [x] 税額合計の算出方法 → **`OrderLine.tax` の `orderId` 単位合算（IF 設計書で確定）**
- [x] 小計の算出方法 → **`OrderLine.linePrice` の `orderId` 単位合算（IF 設計書で確定。従来の減算方式は廃止）**
- [ ] 調整金額（`discountPrice`）の符号（マイナス表記が必須のため、旧データが正数の場合は反転が必要。**本番（移行）データを調査して判断予定**）
- [x] 決済方法グループコード／発送元コード／配送方法グループコードの実際の固定値 → **`migration-pay-group` / `migration-warehouse` / `migration-delivery-group`（確定）**。CEC 本番マスタへの登録有無は要確認
- [x] 配送温度帯ID の固定値 → **`T1111`（確定）**
- [ ] 受取人メールアドレス → **ブランク（空値）で出力する暫定方針。お客様合意が必要**（[business-rules-confirmation.md](../business-rules-confirmation.md) #28）
- [ ] **海外住所を含む移行対象注文の扱い** — 購入者／受取人住所に `Address.csv` の海外住所（7桁以外の郵便番号・47都道府県以外の都道府県）がそのまま出力される。CEC は郵便番号7桁限定・都道府県必須・海外発送非対応のため、除外・変換等の方針要確認（[海外住所を含む配送先（要確認）](#海外住所を含む配送先要確認) 参照）
- [x] 「出荷完了」の判定条件 → **`PurchaseOrder.shipDate` が NULL 以外（確定。本番データで確認済み）**（[出荷完了の判定条件（確定）](#出荷完了の判定条件確定) 参照）

## 改訂履歴

| 日付 | 版 | 内容 |
|---|---|---|
| 2026-06-27 | 1.0 | 作業方針設計書から分割作成 |
| 2026-07-01 | 1.1 | ゲスト・キャンセル注文を移行対象外に確定 |
| 2026-07-09 | 1.2 | IF 設計書「注文履歴 CSV 項目」シートのシュパーク列マッピングを全項目反映。受取人住所ソースを `DeliveryOrder.addressId` に修正（`invoiceAddressId` は誤り）。税額合計・小計の算出方法を確定。決済・配送関連の固定値項目（決済プロファイルコード等）を追加 |
| 2026-07-11 | 1.3 | 「出荷完了の判定条件（暫定）」を追加。`PurchaseOrder.shipDate` の NULL 以外判定を暫定採用。サンプルデータでは全件 NULL のため本番データでの検証が必要な旨を明記 |
| 2026-07-11 | 1.4 | 「出荷完了」の判定条件（`shipDate` 基準）を本番データで確認済みとして確定 |
| 2026-07-14 | 1.5 | 除外理由の判定優先順位を変更。削除済み会員の注文を最優先の除外理由とし、キャンセル・ゲスト等と重複する場合も `reason=deleted_member` で記録するよう `exclusion_reason()` を修正（除外理由内訳の集計精度向上のため） |
| 2026-07-14 | 1.6 | 会員ID（メールアドレス）欄の決定方針を簡略化。会員CSVの突合パターン（新規`C`/更新`U`）を経由せず、会員注文は一律「旧サイト `User.csv` のメールアドレス」を設定する方式に変更（会員CSVの突合はメールアドレス一致で行うため、更新`U`の場合は `User.csv` と CEC 側のメールアドレスが定義上一致することによる） |
| 2026-07-14 | 1.7 | 管理グループコードを `sp_common` に変更（従来は会員・注文系のみ `shupark`。商品系（`sp_common`）と統一） |
| 2026-07-16 | 1.9 | 「海外住所を含む配送先（要確認）」を追加。CEC の制約（郵便番号7桁限定・都道府県必須・海外発送非対応）と、移行対象注文の購入者住所に海外形式が含まれる課題（現データで48件）を未確定事項として記載 |
| 2026-07-14 | 1.8 | 「決済プロファイルコード（`migration-payment`）」を「決済方法グループコード（`migration-pay-group`）」に、「配送方法コード（`migration-delivery`）」を「配送方法グループコード（`migration-delivery-group`）」に名称・コード値を変更。[商品系Excel.md](./商品系Excel.md) の販売条件項目名・コード値と統一するための修正（正式な仕様変更として確定。[business-rules-confirmation.md](../business-rules-confirmation.md) #26） |
