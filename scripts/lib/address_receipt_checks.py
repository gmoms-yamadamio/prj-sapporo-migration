"""Address.csv 受領時の項目値検証（移行データ受領チェック §1.23〜1.26）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from lib.transforms import PREFECTURES
from lib.user_receipt_checks import _invalid_phone_number, _invalid_zip_code

VALID_PREFECTURE_NAMES = frozenset(PREFECTURES.values())


@dataclass
class AddressValidationError:
    address_id: str
    field: str
    value: str
    reason: str


@dataclass
class AddressValidationSummary:
    total_rows: int = 0
    zip_code_invalid: int = 0
    pref_empty: int = 0
    pref_invalid: int = 0
    phone_invalid: int = 0
    errors: list[AddressValidationError] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return (
            self.zip_code_invalid == 0
            and self.pref_empty == 0
            and self.pref_invalid == 0
            and self.phone_invalid == 0
        )


def _invalid_prefecture_name(value: str) -> str | None:
    """末尾スペース除去後、47都道府県名以外なら理由を返す（空は別カウント）。"""
    stripped = (value or "").rstrip()
    if not stripped:
        return None
    if stripped not in VALID_PREFECTURE_NAMES:
        return "not_prefecture_name"
    return None


def validate_addresses(addresses: Iterable[dict[str, str]]) -> AddressValidationSummary:
    """Address.csv 各行について、移行前提の項目値ルールを検証する。"""
    summary = AddressValidationSummary()
    for row in addresses:
        summary.total_rows += 1
        address_id = (row.get("addressId") or "").strip()

        zip_reason = _invalid_zip_code(row.get("zipCode") or "")
        if zip_reason:
            summary.zip_code_invalid += 1
            summary.errors.append(
                AddressValidationError(
                    address_id=address_id,
                    field="zipCode",
                    value=(row.get("zipCode") or "").rstrip(),
                    reason=zip_reason,
                )
            )

        pref_raw = row.get("pref") or ""
        if not pref_raw.rstrip():
            summary.pref_empty += 1
            summary.errors.append(
                AddressValidationError(
                    address_id=address_id,
                    field="pref",
                    value=pref_raw.rstrip(),
                    reason="empty",
                )
            )
        else:
            pref_reason = _invalid_prefecture_name(pref_raw)
            if pref_reason:
                summary.pref_invalid += 1
                summary.errors.append(
                    AddressValidationError(
                        address_id=address_id,
                        field="pref",
                        value=pref_raw.rstrip(),
                        reason=pref_reason,
                    )
                )

        tel_reason = _invalid_phone_number(row.get("tel") or "")
        if tel_reason:
            summary.phone_invalid += 1
            summary.errors.append(
                AddressValidationError(
                    address_id=address_id,
                    field="tel",
                    value=(row.get("tel") or "").rstrip(),
                    reason=tel_reason,
                )
            )
    return summary
