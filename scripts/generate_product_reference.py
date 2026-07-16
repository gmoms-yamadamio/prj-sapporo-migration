#!/usr/bin/env python3
"""Generate product SKU reference CSV from Products.csv."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import write_csv
from lib.product_lookup import load_products, tax_rate_for_sku

RAW = ROOT / "input" / "raw"
OUT = ROOT / "output" / "products"
REPORTS = ROOT / "output" / "reports"

FIELDS = ["Id", "ExternalId1", "Name", "UnitPrice", "TaxRate", "SalesStatus", "SalesPatternId"]


def main() -> None:
    products = load_products(RAW / "Products.csv")
    rows = []
    for prod in sorted(products.values(), key=lambda x: int(x["Id"])):
        sku = prod.get("ExternalId1", "")
        rows.append({
            "Id": prod.get("Id", ""),
            "ExternalId1": sku,
            "Name": prod.get("Name", ""),
            "UnitPrice": prod.get("UnitPrice", ""),
            "TaxRate": tax_rate_for_sku(sku) if sku else "",
            "SalesStatus": prod.get("SalesStatus", ""),
            "SalesPatternId": prod.get("SalesPatternId", ""),
        })
    write_csv(OUT / "product_sku_reference.csv", rows, FIELDS)
    checklist.record(REPORTS, "3.6", len(rows), source="generate_product_reference.py")
    reduced = sum(1 for r in rows if r["TaxRate"] == "8")
    print(f"product_sku_reference.csv: {len(rows)} rows (tax8={reduced})")


if __name__ == "__main__":
    main()
