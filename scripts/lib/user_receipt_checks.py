"""User.csv 受領時の項目値検証（移行データ受領チェック §1.17〜1.21）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from lib.transforms import _parse_datetime, half_width_digits

VALID_SEX = frozenset({"0", "1", "2", "9"})


@dataclass
class UserValidationError:
    user_id: str
    field: str
    value: str
    reason: str


@dataclass
class UserValidationSummary:
    total_rows: int = 0
    zip_code_invalid: int = 0
    prefecture_invalid: int = 0
    sex_invalid: int = 0
    birthday_invalid: int = 0
    phone_number_invalid: int = 0
    errors: list[UserValidationError] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return (
            self.zip_code_invalid == 0
            and self.prefecture_invalid == 0
            and self.sex_invalid == 0
            and self.birthday_invalid == 0
            and self.phone_number_invalid == 0
        )


def _invalid_zip_code(value: str) -> str | None:
    digits = half_width_digits(value)
    if len(digits) != 7:
        return f"zip_digits_not_7 (digit_count={len(digits)})"
    return None


def _invalid_prefecture(value: str) -> str | None:
    stripped = (value or "").strip()
    if not stripped:
        return "empty"
    try:
        code = int(stripped)
    except ValueError:
        return "not_integer"
    if code < 1 or code > 47:
        return "out_of_range"
    return None


def _invalid_sex(value: str) -> str | None:
    stripped = (value or "").strip()
    if not stripped:
        return "empty"
    if stripped not in VALID_SEX:
        return "invalid_value"
    return None


def _invalid_birthday(value: str) -> str | None:
    stripped = (value or "").strip()
    if not stripped:
        return "empty"
    if _parse_datetime(stripped) is None:
        return "not_date"
    return None


def _invalid_phone_number(value: str) -> str | None:
    digits = half_width_digits(value)
    if not digits:
        return "empty"
    if len(digits) not in (10, 11):
        return f"digit_count_not_10_or_11 (digit_count={len(digits)})"
    return None


def validate_users(users: Iterable[dict[str, str]]) -> UserValidationSummary:
    """User.csv 各行について、移行前提の項目値ルールを検証する。"""
    summary = UserValidationSummary()
    for row in users:
        summary.total_rows += 1
        user_id = (row.get("Id") or "").strip()

        checks = (
            ("ZipCode", row.get("ZipCode"), _invalid_zip_code, "zip_code_invalid"),
            ("Prefecture", row.get("Prefecture"), _invalid_prefecture, "prefecture_invalid"),
            ("Sex", row.get("Sex"), _invalid_sex, "sex_invalid"),
            ("Birthday", row.get("Birthday"), _invalid_birthday, "birthday_invalid"),
            ("PhoneNumber", row.get("PhoneNumber"), _invalid_phone_number, "phone_number_invalid"),
        )
        for field_name, raw_value, validator, counter_attr in checks:
            reason = validator(raw_value or "")
            if reason is None:
                continue
            setattr(summary, counter_attr, getattr(summary, counter_attr) + 1)
            summary.errors.append(
                UserValidationError(
                    user_id=user_id,
                    field=field_name,
                    value=(raw_value or "").strip(),
                    reason=reason,
                )
            )
    return summary
