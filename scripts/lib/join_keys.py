"""Join key helpers for old-site CSV tables."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .transforms import is_deleted, normalize_email


@dataclass
class MemberRecord:
    user: dict[str, str]
    account: dict[str, str] | None
    pattern: str  # "C" or "U"
    cec_member_id: str = ""
    cec_email: str = ""
    cec_row: dict[str, str] | None = None


def load_cec_members(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """Email (lower) -> CEC member row."""
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        email = row.get("メールアドレス") or row.get("email", "")
        if email:
            result[normalize_email(email)] = row
    return result


def deleted_usernos(users: list[dict[str, str]], accounts: list[dict[str, str]]) -> set[str]:
    """UserNo set for accounts linked to users with DeletedAt."""
    users_by_id = {u["Id"]: u for u in users}
    result: set[str] = set()
    for acc in accounts:
        if acc.get("IsAnonymous") == "1":
            continue
        user = users_by_id.get(acc.get("UserName", ""))
        if user and is_deleted(user.get("DeletedAt")):
            result.add(acc["UserNo"])
    return result


def excluded_deleted_members(
    users: list[dict[str, str]], accounts: list[dict[str, str]]
) -> list[dict[str, str]]:
    users_by_id = {u["Id"]: u for u in users}
    excluded: list[dict[str, str]] = []
    for acc in accounts:
        if acc.get("IsAnonymous") == "1":
            continue
        user = users_by_id.get(acc.get("UserName", ""))
        if user and is_deleted(user.get("DeletedAt")):
            excluded.append({
                "UserNo": acc["UserNo"],
                "UserId": user["Id"],
                "Email": user.get("Email", ""),
                "DeletedAt": user.get("DeletedAt", ""),
            })
    return excluded


def _tiebreak_key(user: dict[str, str]) -> tuple[str, int]:
    """重複メールの採用優先度キー。`UpdatedAt`降順、同時刻は`Id`降順（確定）。"""
    try:
        id_value = int(user.get("Id", "0") or "0")
    except ValueError:
        id_value = 0
    return (user.get("UpdatedAt", ""), id_value)


def accountless_active_user_ids(
    users: list[dict[str, str]], accounts: list[dict[str, str]]
) -> set[str]:
    """有効な（`IsAnonymous!=1`の）`UserAccount`が1件も無い、削除済みでない`User.Id`の集合。

    1回目移行チェックリスト 1.14 に対応（移行対象に含める確定方針）。
    """
    matched: set[str] = set()
    for acc in accounts:
        if acc.get("IsAnonymous") == "1":
            continue
        user_id = acc.get("UserName", "")
        if user_id:
            matched.add(user_id)
    return {
        u["Id"] for u in users
        if not is_deleted(u.get("DeletedAt")) and u["Id"] not in matched
    }


def duplicate_email_extra_count(users: list[dict[str, str]]) -> int:
    """有効会員のうち、同一メールアドレス重複により除外される件数（グループごとに件数-1の合計）。

    1回目移行チェックリスト 1.15 に対応。
    """
    counts = Counter(
        normalize_email(u.get("Email", ""))
        for u in users
        if not is_deleted(u.get("DeletedAt")) and normalize_email(u.get("Email", ""))
    )
    return sum(n - 1 for n in counts.values() if n > 1)


def build_member_records(
    users: list[dict[str, str]],
    accounts: list[dict[str, str]],
    cec_by_email: dict[str, dict[str, str]],
) -> tuple[list[MemberRecord], list[dict[str, str]], list[dict[str, str]]]:
    """旧サイト会員をパターン C（新規）/ U（更新）に振り分ける。

    戻り値: (振り分け済みレコード, 突合不能リスト, 旧サイト内メール重複リスト)

    `UserAccount`（`IsAnonymous=0`）を起点に `User` を `UserName=Id` で結合するが、
    有効な `UserAccount` を1件も持たない `User`（削除済み除く）も移行対象として候補に加える
    （確定方針。1回目移行チェックリスト 1.14 参照）。

    同一メールアドレスの重複は `User.UpdatedAt` 最新の1件を採用し、同時刻の場合は
    `Id` 降順（大きい方）を採用する（確定方針。会員CSV.md「突合ロジック」参照）。
    他は重複リスト（`duplicate_emails.csv`）に記録する。
    """
    users_by_id = {u["Id"]: u for u in users}
    unmatched: list[dict[str, str]] = []
    candidates: list[tuple[str, dict[str, str], dict[str, str] | None]] = []
    matched_user_ids: set[str] = set()

    for acc in accounts:
        if acc.get("IsAnonymous") == "1":
            continue
        user = users_by_id.get(acc.get("UserName", ""))
        if not user:
            unmatched.append({"UserNo": acc["UserNo"], "UserName": acc["UserName"], "reason": "user_not_found"})
            continue
        matched_user_ids.add(user["Id"])
        if is_deleted(user.get("DeletedAt")):
            continue

        email_key = normalize_email(user.get("Email", ""))
        if not email_key:
            unmatched.append({"UserNo": acc["UserNo"], "UserName": acc["UserName"], "reason": "empty_email"})
            continue
        candidates.append((email_key, user, acc))

    # 有効な UserAccount を持たない User も移行対象に含める（確定方針）。
    for user in users:
        if user["Id"] in matched_user_ids:
            continue
        if is_deleted(user.get("DeletedAt")):
            continue
        email_key = normalize_email(user.get("Email", ""))
        if not email_key:
            unmatched.append({"UserNo": "", "UserName": user["Id"], "reason": "empty_email_no_account"})
            continue
        candidates.append((email_key, user, None))

    def _dup_row(email_key: str, user: dict[str, str], acc: dict[str, str] | None, kept_user_id: str) -> dict[str, str]:
        return {
            "UserNo": acc["UserNo"] if acc else "",
            "UserId": user["Id"],
            "Email": email_key,
            "UpdatedAt": user.get("UpdatedAt", ""),
            "kept_UserId": kept_user_id,
        }

    best_by_email: dict[str, tuple[dict[str, str], dict[str, str] | None]] = {}
    duplicates: list[dict[str, str]] = []
    for email_key, user, acc in candidates:
        existing = best_by_email.get(email_key)
        if existing is None:
            best_by_email[email_key] = (user, acc)
            continue
        existing_user, existing_acc = existing
        if _tiebreak_key(user) >= _tiebreak_key(existing_user):
            duplicates.append(_dup_row(email_key, existing_user, existing_acc, user["Id"]))
            best_by_email[email_key] = (user, acc)
        else:
            duplicates.append(_dup_row(email_key, user, acc, existing_user["Id"]))

    records: list[MemberRecord] = []
    for email_key, (user, acc) in best_by_email.items():
        cec = cec_by_email.get(email_key)
        if cec:
            records.append(MemberRecord(
                user=user, account=acc, pattern="U",
                cec_member_id=cec.get("会員ID", ""),
                cec_email=cec.get("メールアドレス", user.get("Email", "")),
                cec_row=cec,
            ))
        else:
            records.append(MemberRecord(user=user, account=acc, pattern="C"))

    return records, unmatched, duplicates


def resolve_member_email(record: MemberRecord) -> str:
    if record.pattern == "U" and record.cec_email:
        return record.cec_email
    return record.user.get("Email", "")
