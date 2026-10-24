#!/usr/bin/env python3
"""Generate deterministic sample settlement CSVs for testing invoice-diff.

Produces:
    samples/flipkart_settlement.csv        - 100 orders with planted discrepancies
    samples/flipkart_orders_expected.csv   - clean ground truth for the same 100
    samples/meesho_settlement.csv          - 50 orders (clean)

Uses random.seed(42) for reproducibility.

Planted discrepancies (Flipkart settlement vs expected):
    - 2 MISSING_IN_SETTLEMENT  (orders in expected but dropped from settlement)
    - 1 EXTRA_IN_SETTLEMENT    (order invented in settlement, not in expected)
    - 2 VALUE_MISMATCH         (product value off by Rs.50-200)
    - 3 GST_MISMATCH           (GST off by small amounts)
    - 1 COMMISSION_MISMATCH    (commission rate off - bonus)
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

SAMPLES_DIR = Path("samples")
SAMPLES_DIR.mkdir(exist_ok=True)


def _flipkart_ids(n: int) -> list[str]:
    return [f"FK{random.randint(100000, 999999)}" for _ in range(n)]


def _flipkart_row(oid: str, d: date) -> dict:
    """Build a clean Flipkart settlement row for one order."""
    qty = random.randint(1, 3)
    unit_price = random.randint(199, 4999)
    product_value = qty * unit_price
    commission = int(product_value * random.choice([0.10, 0.15, 0.20, 0.25]))
    gst = int(product_value * 0.18)
    fship = random.randint(40, 120)
    discount = random.randint(0, max(1, product_value // 10))
    settlement = product_value - commission + gst + discount - fship
    return {
        "Seller Order Id": oid,
        "Order Date": d.isoformat(),
        "Product Price": product_value,
        "Seller Commission": commission,
        "GST": gst,
        "Forward Shipping": fship,
        "Discount": discount,
        "Settlement Amount": settlement,
    }


def generate_flipkart() -> None:
    n = 100
    ids = _flipkart_ids(n)
    start = date(2026, 9, 1)

    # Build clean expected rows first
    expected_rows: list[dict] = []
    for oid in ids:
        d = start + timedelta(days=random.randint(0, 25))
        expected_rows.append(_flipkart_row(oid, d))

    # Settlement = expected with planted discrepancies
    settlement_rows = [dict(r) for r in expected_rows]

    # --- 2 MISSING_IN_SETTLEMENT: drop orders #10 and #42 from settlement ---
    missing_idx = [10, 42]
    drop_ids = {settlement_rows[i]["Seller Order Id"] for i in missing_idx}
    settlement_rows = [r for r in settlement_rows if r["Seller Order Id"] not in drop_ids]

    # --- 1 EXTRA_IN_SETTLEMENT: append an order not in expected ---
    extra_row = _flipkart_row("FKEXTRA999", date(2026, 9, 15))
    settlement_rows.append(extra_row)

    # --- 2 VALUE_MISMATCH: shift product price by Rs.50-200 ---
    value_idx = [20, 55]
    for i in value_idx:
        r = settlement_rows[i]
        shift = random.choice([-150, 75, -200, 120])
        r["Product Price"] = r["Product Price"] + shift
        r["Settlement Amount"] = r["Settlement Amount"] + shift

    # --- 3 GST_MISMATCH: nudge GST by small amounts ---
    gst_idx = [30, 60, 80]
    for i in gst_idx:
        r = settlement_rows[i]
        nudge = random.choice([-15, 20, -8, 12, -25])
        r["GST"] = r["GST"] + nudge
        r["Settlement Amount"] = r["Settlement Amount"] + nudge

    # --- 1 COMMISSION_MISMATCH (bonus): commission rate off ---
    ci = 70
    r = settlement_rows[ci]
    # bump commission ~5 percentage points
    r["Seller Commission"] = r["Seller Commission"] + max(1, int(r["Product Price"] * 0.05))
    r["Settlement Amount"] = r["Settlement Amount"] - max(1, int(r["Product Price"] * 0.05))

    # --- write expected (clean) ---
    exp_path = SAMPLES_DIR / "flipkart_orders_expected.csv"
    exp_fields = ["Seller Order Id", "Order Date", "Product Price", "Seller Commission", "GST"]
    with open(exp_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=exp_fields)
        w.writeheader()
        for r in expected_rows:
            w.writerow({k: r[k] for k in exp_fields})

    # --- write settlement (with discrepancies) ---
    sett_path = SAMPLES_DIR / "flipkart_settlement.csv"
    sett_fields = [
        "Seller Order Id",
        "Order Date",
        "Product Price",
        "Seller Commission",
        "GST",
        "Forward Shipping",
        "Discount",
        "Settlement Amount",
    ]
    with open(sett_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sett_fields)
        w.writeheader()
        for r in settlement_rows:
            w.writerow({k: r[k] for k in sett_fields})

    print(f"Wrote {exp_path} ({len(expected_rows)} clean orders)")
    print(f"Wrote {sett_path} ({len(settlement_rows)} settlement rows)")
    print("  Planted: 2 missing, 1 extra, 2 value, 3 gst, 1 commission")


def generate_meesho() -> None:
    n = 50
    ids = _flipkart_ids(n)
    start = date(2026, 8, 1)
    rows = []
    for oid in ids:
        d = start + timedelta(days=random.randint(0, 20))
        qty = random.randint(1, 2)
        item_price = random.randint(99, 1999)
        product_value = qty * item_price
        platform_fee = int(product_value * random.choice([0.08, 0.12, 0.15]))
        gst = int(product_value * 0.18)
        discount = random.randint(0, max(1, product_value // 10))
        settlement = product_value - platform_fee + gst + discount
        rows.append(
            {
                "Order ID": oid,
                "Invoice Date": d.isoformat(),
                "Item Price": product_value,
                "Platform Fee": platform_fee,
                "Tax Amount": gst,
                "Discount": discount,
                "Settlement Amount": settlement,
            }
        )
    path = SAMPLES_DIR / "meesho_settlement.csv"
    fields = [
        "Order ID",
        "Invoice Date",
        "Item Price",
        "Platform Fee",
        "Tax Amount",
        "Discount",
        "Settlement Amount",
    ]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {path} ({len(rows)} orders)")


if __name__ == "__main__":
    generate_flipkart()
    generate_meesho()
