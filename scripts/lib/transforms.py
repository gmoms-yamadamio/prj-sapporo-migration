"""Value transformation helpers."""

from __future__ import annotations

import re
from datetime import datetime

# 移行元データはすべてシュパーク 1 サイト分
SITE_CODE = "shupark"
# 2026-07-14: 商品系(sp_common)と統一。会員・注文系も一律 sp_common に変更
MANAGEMENT_GROUP_CODE = "sp_common"

PREFECTURES = {
    "1": "北海道", "2": "青森県", "3": "岩手県", "4": "宮城県", "5": "秋田県",
    "6": "山形県", "7": "福島県", "8": "茨城県", "9": "栃木県", "10": "群馬県",
    "11": "埼玉県", "12": "千葉県", "13": "東京都", "14": "神奈川県", "15": "新潟県",
    "16": "富山県", "17": "石川県", "18": "福井県", "19": "山梨県", "20": "長野県",
    "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県", "25": "滋賀県",
    "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県",
    "36": "徳島県", "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県",
    "41": "佐賀県", "42": "長崎県", "43": "熊本県", "44": "大分県", "45": "宮崎県",
    "46": "鹿児島県", "47": "沖縄県",
}

SEX_MAP = {"1": "man", "2": "woman"}


def is_deleted(value: str | None) -> bool:
    return bool(value and value.strip().upper() != "NULL")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _parse_datetime(value: str) -> datetime | None:
    if not value or str(value).strip().upper() == "NULL":
        return None
    s = str(value).strip()
    if " +" in s:
        s = s.split(" +", 1)[0].strip()
    elif s.endswith("Z"):
        s = s[:-1]
    s = s.replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0]
    match = re.match(
        r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T](\d{1,2}):(\d{2}):(\d{2}))?$",
        s,
    )
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if match.group(4) is not None:
            hour, minute, second = int(match.group(4)), int(match.group(5)), int(match.group(6))
            return datetime(year, month, day, hour, minute, second)
        return datetime(year, month, day)
    try:
        return datetime.fromisoformat(s.replace("/", "-"))
    except ValueError:
        return None


def format_birthday(value: str) -> str:
    """`YYYY/MM/DD`（月日2桁ゼロ埋め）。会員CSV.md 2026-07-16 確定。"""
    dt = _parse_datetime(value)
    if dt:
        return dt.strftime("%Y/%m/%d")
    if not value or value.upper() == "NULL":
        return ""
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}/{digits[4:6]}/{digits[6:8]}"
    return value


def format_member_datetime(value: str) -> str:
    """`YYYY/MM/DD hh:mm:ss`（JST）。会員登録日時・CSV出力日時で使用。"""
    dt = _parse_datetime(value)
    if dt:
        return dt.strftime("%Y/%m/%d %H:%M:%S")
    return ""


def half_width_digits(value: str) -> str:
    """電話番号・郵便番号向け。全角数字を半角にし、数字以外を除去。"""
    if not value or value.upper() == "NULL":
        return ""
    table = str.maketrans("０１２３４５６７８９", "0123456789")
    normalized = value.translate(table)
    return "".join(c for c in normalized if c.isdigit())


def kana_or_default(value: str, default: str = "・") -> str:
    stripped = (value or "").strip()
    return stripped if stripped else default


def format_migration_memo_create(csv_output_at: str) -> str:
    return f"Created at {csv_output_at}"


def format_migration_memo_update(existing: str, csv_output_at: str) -> str:
    suffix = f"Updated at {csv_output_at}"
    existing = (existing or "").strip()
    if not existing:
        return suffix
    return f"{existing}/{suffix}"


def is_updated_since(value: str, since: str) -> bool:
    """`value`（User.UpdatedAt 等）が `since`（前回抽出日時）以降か。"""
    updated_at = _parse_datetime(value)
    since_at = _parse_datetime(since)
    if updated_at is None or since_at is None:
        return False
    return updated_at >= since_at


def format_order_date(value: str) -> str:
    if not value or value.upper() == "NULL":
        return ""
    try:
        cleaned = value.split(".")[0]
        dt = datetime.fromisoformat(cleaned.replace(" ", "T"))
        return dt.strftime("%Y%m%d%H%M%S")
    except ValueError:
        digits = "".join(c for c in value if c.isdigit())
        return digits[:14].ljust(14, "0")


def prefecture_name(code: str) -> str:
    return PREFECTURES.get(str(code).strip(), str(code))


def sex_code(value: str) -> str:
    """`1`→`man`, `2`→`woman`, その他→`other`（2026-07-16 確定）。"""
    return SEX_MAP.get(str(value).strip(), "other")


def mail_optin(value: str) -> str:
    """`対象`/`対象外`。IF設計書「会員CSV項目」シートで確定（従来のtrue/falseは誤り）。"""
    return "対象" if str(value).strip() == "1" else "対象外"


def join_name(last: str, first: str, default: str = "・") -> str:
    ln, fn = (last or "").strip(), (first or "").strip()
    if not ln and not fn:
        return default
    return f"{ln} {fn}".strip()


def point_total(point_row: dict[str, str]) -> int:
    """Sum ActivePoint and TemporaryPoint for migration."""
    active = int(float(point_row.get("ActivePoint") or 0))
    temporary = int(float(point_row.get("TemporaryPoint") or 0))
    return active + temporary


def to_int_str(value: str) -> str:
    try:
        return str(int(float(value or 0)))
    except ValueError:
        return "0"
