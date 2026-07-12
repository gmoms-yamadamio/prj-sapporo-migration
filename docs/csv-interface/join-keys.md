# 旧サイト CSV 結合キー定義

> 調査日: 2026-07-01  
> 対象データ: `input/raw/` サンプル CSV

## 結論（確定）

旧サイトの会員系テーブルは **`UserAccount` をハブ** として結合する。  
`User.Id` と `UserAccount.UserNo` は **別 ID 体系** のため、直接結合できない。

### 推奨結合パス

```text
User.csv (Id)
    ↑ UserAccount.UserName = User.Id（文字列一致）
UserAccount.csv (UserNo, UserName)
    ├─→ PointBankAccount.csv (UserNo)
    ├─→ UserAddress.csv (UserNo) → Address.csv (AddressId)
    └─→ OrderCustomer.csv (UserNo)

PurchaseOrder.csv (orderId, customerId)
    └─→ OrderCustomer.csv (customerId)
            └─→ Address.csv (orderedAddressId) … 購入者住所
    └─→ DeliveryOrder.csv (orderId) → Address.csv (addressId) … 受取人住所・受取人メール（mailAddr）
```

| 結合 | キー | サンプル突合結果 |
| --- | --- | --- |
| UserAccount → User | `UserAccount.UserName` = `User.Id` | 61 / 100 件 |
| OrderCustomer → UserAccount | `OrderCustomer.UserNo` = `UserAccount.UserNo` | 65 / 100 件 |
| OrderCustomer → User（間接） | UserNo → UserName → Id | 63 / 100 件 |
| PointBankAccount → UserAccount | `PointBankAccount.UserNo` = `UserAccount.UserNo` | 76 / 85 件 |
| UserAddress → UserAccount | `UserAddress.UserNo` = `UserAccount.UserNo` | 12 / 17 件 |
| UserAddress → Address | `UserAddress.AddressId` = `Address.addressId` | サンプルでは ID 範囲不一致（0/17）。本番データで再検証 |
| OrderCustomer → Address（購入者） | `OrderCustomer.orderedAddressId` = `Address.addressId` | 35 / 100 件 |
| DeliveryOrder → PurchaseOrder | `DeliveryOrder.orderId` = `PurchaseOrder.orderId` | 100 / 100 件（1 注文 1 配送、分割配送なし） |
| DeliveryOrder → Address（受取人） | `DeliveryOrder.addressId` = `Address.addressId` | 35 / 100 件 |

> **受取人住所の結合キーについて（2026-07-09 確定）**: 当初 `OrderCustomer.invoiceAddressId` を受取人住所の結合キーと想定していたが、【サッポロビール様】CSVファイルIF設計書.xlsx「注文履歴 CSV 項目」シートのシュパーク列マッピングにより、正しくは **`DeliveryOrder.addressId`** であることが判明した。`OrderCustomer.invoiceAddressId` は受取人住所には使用しない（詳細は [注文履歴CSV.md](../migration-policy/deliverables/注文履歴CSV.md) を参照）。
>
> `OrderCustomer → Address（購入者）` と `DeliveryOrder → Address（受取人）` の突合率がいずれも 35/100 と同水準なのは、サンプル抽出時に `Address.csv` が全システムの住所のうち一部のみを含む window 切り出しであるためと推測される（本番データでは全件抽出のため突合率向上が見込まれる）。

## ID 体系の整理

| 列 | テーブル | 例 | 用途 |
| --- | --- | --- | --- |
| `Id` | User | 1, 2, 3 | 会員マスタ主キー。`UserAccount.UserName` と対応 |
| `UserNo` | UserAccount | 229363, 229362 | アカウント主キー。注文・ポイント・アドレスの結合キー |
| `UserName` | UserAccount | 200000106, Guest_* | `User.Id` またはゲスト用 GUID |
| `customerId` | OrderCustomer | 48647 | 注文者 ID。`PurchaseOrder.customerId` と対応 |
| `orderId` | PurchaseOrder / OrderLine | 48597 | 注文番号 |
| `productId` | OrderLine | 381 | `Products.Id` と対応 |

## 結合不能レコードの扱い

| パターン | 件数（サンプル） | 扱い |
| --- | ---: | --- |
| ゲストアカウント（`UserAccount.IsAnonymous=1`） | 39 / 100 | 会員 CSV 対象外。ゲスト注文も注文履歴移行対象外 |
| `UserAccount.UserName` が `User.Id` に存在しない | 39 / 100 | ゲストまたは退会済みアカウント。会員 CSV 対象外 |
| `User.DeletedAt` あり | 24 / 113 | **移行対象外**（会員・ポイント・アドレス帳・注文すべて） |
| `UserAddress` 未登録会員 | 多数 | 会員アドレス帳 CSV は出力スキップ |
| `PointBankAccount` 未登録 | 9 / 85 相当 | 会員ポイント CSV は出力スキップ |

## ETL 実装での結合例（Python）

```python
# UserAccount を起点に User を結合
users = {r["Id"]: r for r in read_csv("User.csv")}
accounts = read_csv("UserAccount.csv")

members = []
for acc in accounts:
    if acc["IsAnonymous"] == "1":
        continue  # ゲストは会員 CSV 対象外
    user = users.get(acc["UserName"])
    if not user:
        report_unmatched(acc)
        continue
    if user.get("DeletedAt") and user["DeletedAt"] not in ("", "NULL"):
        continue  # 削除済み会員は移行対象外
    members.append({**user, "UserNo": acc["UserNo"]})
```

## 改訂履歴

| 日付 | 内容 |
| --- | --- |
| 2026-07-01 | 初版。サンプル CSV による結合キー調査結果を反映 |
| 2026-07-09 | IF 設計書のシュパーク列マッピングを反映。受取人住所の結合キーを `DeliveryOrder.addressId` に修正（`OrderCustomer.invoiceAddressId` から変更）。`DeliveryOrder.csv` の結合パスを追加 |
