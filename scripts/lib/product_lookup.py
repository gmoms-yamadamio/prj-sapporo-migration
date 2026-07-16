"""Products.csv lookup (3-row header format) and SKU tax rate resolution."""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=1)
def _tax_rate_config() -> tuple[frozenset[str], str, str]:
    path = _CONFIG_DIR / "reduced_tax_skus.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    skus = frozenset(str(s) for s in data["skus"])
    return skus, str(data["reduced_tax_rate"]), str(data["default_tax_rate"])


def load_products(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        lines = f.readlines()
    if len(lines) < 4:
        return {}
    fieldnames = next(csv.reader([lines[2]]))
    reader = csv.DictReader(lines[3:], fieldnames=fieldnames)
    return {row["Id"]: row for row in reader if row.get("Id")}


def sku_for_product_id(products: dict[str, dict[str, str]], product_id: str) -> str | None:
    row = products.get(str(product_id))
    if not row:
        return None
    return row.get("ExternalId1") or None


def tax_rate_for_sku(sku: str) -> str:
    """Return sales tax rate (%) for a product SKU (ExternalId1)."""
    reduced_skus, reduced_rate, default_rate = _tax_rate_config()
    return reduced_rate if sku in reduced_skus else default_rate


def tax_rate_for_product_id(products: dict[str, dict[str, str]], product_id: str) -> str | None:
    sku = sku_for_product_id(products, product_id)
    if not sku:
        return None
    return tax_rate_for_sku(sku)
