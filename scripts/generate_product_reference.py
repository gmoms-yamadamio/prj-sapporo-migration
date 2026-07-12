#!/usr/bin/env python3
"""Generate product SKU reference CSV from Products.csv."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import checklist
from lib.csv_io import write_csv
from lib.product_lookup import load_products

RAW = ROOT / "input" / "raw"
OUT = ROOT / "output" / "products"
REPORTS = ROOT / "output" / "reports"

FIELDS = ["Id", "ExternalId1", "Name", "UnitPrice", "SalesStatus", "SalesPatternId"]


def main() -> None:
    products = load_products(RAW / "Products.csv")
    rows = [
        {k: prod.get(k, "") for k in FIELDS}
        for prod in sorted(products.values(), key=lambda x: int(x["Id"]))
    ]
    write_csv(OUT / "product_sku_reference.csv", rows, FIELDS)
    checklist.record(REPORTS, "3.6", len(rows), source="generate_product_reference.py")
    print(f"product_sku_reference.csv: {len(rows)} rows")


if __name__ == "__main__":
    main()
