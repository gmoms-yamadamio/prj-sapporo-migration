"""Products.csv lookup (3-row header format)."""

from __future__ import annotations

import csv
from pathlib import Path


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
