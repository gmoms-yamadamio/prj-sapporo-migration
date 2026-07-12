"""Value transformation helpers."""

from __future__ import annotations

from datetime import datetime

# 移行元データはすべてシュパーク 1 サイト分
SITE_CODE = "shupark"
MANAGEMENT_GROUP_CODE = "shupark"

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

SEX_MAP = {"0": "woman", "1": "man", "2": "other", "9": "other"}


def is_deleted(value: str | None) -> bool:
    return bool(value and value.strip().upper() != "NULL")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def format_birthday(value: str) -> str:
    """YYYYMMDD（8桁、区切りなし）。IF設計書「会員CSV項目」シートで確定。"""
    if not value or value.upper() == "NULL":
        return ""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00").split(".")[0])
        return dt.strftime("%Y%m%d")
    except ValueError:
        return "".join(c for c in value[:10] if c.isdigit())


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
