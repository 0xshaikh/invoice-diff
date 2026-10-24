"""Shared pytest fixtures for the ``invoice-diff`` test suite.

These fixtures are written against the real public API of the ``invoice_diff``
package:

    parse_settlement(path)                  -> universal-schema DataFrame
    parse_settlement_from_records(records)  -> universal-schema DataFrame
    reconcile(settlement, expected)         -> {"mismatches": DataFrame, "summary": dict}
    export_report(result, format, out_path) -> str(path)

The parser **auto-detects** the marketplace from the CSV header, so fixtures
must carry each marketplace's distinctive columns (see
``invoice_diff.parser._detect_marketplace``):

    Flipkart -> ``Seller Order Id`` / ``Seller Commission`` / ``Settlement Amount``
    Meesho   -> ``Item Price`` / ``Platform Fee`` / ``Tax Amount``
    Amazon   -> literal ``OrderID`` (no space)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from invoice_diff.parser import parse_settlement
from invoice_diff.reconciler import (
    reconcile,
)

# ---------------------------------------------------------------------------
# Canonical universal schema — assert this against every parsed frame.
# ---------------------------------------------------------------------------
UNIVERSAL_COLUMNS = [
    "Order_ID",
    "Marketplace",
    "Invoice_Date",
    "Product_Value",
    "Commission",
    "GST_Amount",
    "Forward_Shipping",
    "Reverse_Shipping",
    "Discount",
    "Settlement_Amount",
]

MISMATCH_COLUMNS = [
    "Order_ID",
    "Type",
    "Expected_Value",
    "Settlement_Value",
    "Difference",
    "Note",
]


# ---------------------------------------------------------------------------
# Marketplace-shaped CSV fixtures (real dialect headers, small row counts).
# ---------------------------------------------------------------------------
@pytest.fixture
def flipkart_csv(tmp_path: Path) -> Path:
    """Flipkart Settlement_Statement-shaped CSV with distinctive headers."""
    path = tmp_path / "flipkart.csv"
    path.write_text(
        "Seller Order Id,Order Date,Product Price,Seller Commission,GST,"
        "Forward Shipping,Discount,Settlement Amount\n"
        "FK770487,2026-09-20,4800,720,864,60,236,5120\n"
        "FK881122,2026-09-21,1000,150,180,50,0,900\n"
        "FK990011,2026-09-22,2500,375,450,70,250,2545\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def meesho_csv(tmp_path: Path) -> Path:
    """Meesho Seller Settlement-shaped CSV (Item Price / Platform Fee / Tax Amount)."""
    path = tmp_path / "meesho.csv"
    path.write_text(
        "Order ID,Invoice Date,Item Price,Platform Fee,Tax Amount,"
        "Discount,Settlement Amount\n"
        "MS501001,2026-08-20,1729,259,311,10,1791\n"
        "MS502002,2026-08-21,800,120,144,0,824\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def amazon_csv(tmp_path: Path) -> Path:
    """Amazon flat-file-shaped CSV — note the space-free ``OrderID`` column."""
    path = tmp_path / "amazon.csv"
    path.write_text(
        "OrderID,InvoiceDate,ItemPrice,GSTAmount,ReferralFee,"
        "Shipping,SettlementAmount\n"
        "AM100001,2026-09-20,1000,180,100,25,795\n"
        "AM100002,2026-09-21,3000,540,300,40,2560\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def empty_csv(tmp_path: Path) -> Path:
    """Zero-byte file — exercises the empty-input error path."""
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture
def unrecognized_csv(tmp_path: Path) -> Path:
    """A CSV with none of the recognised order-id synonyms."""
    path = tmp_path / "unknown.csv"
    path.write_text("ProjectCode,Phase,Duration\nFOO-1,alpha,14\n", encoding="utf-8")
    return path


@pytest.fixture
def bom_flipped_headers_csv(tmp_path: Path) -> Path:
    """UTF-8 BOM + inconsistent case + stray spaces + punctuation in headers."""
    path = tmp_path / "messy.csv"
    path.write_bytes(
        b"\xef\xbb\xbf"
        + (
            b" seller ORDER id , order date , product price , "
            b"seller commission , GST \r\n"
            b"FK1,2026-09-20,4800,720,864\r\n"
        )
    )
    return path


@pytest.fixture
def expected_orders_flipkart(tmp_path: Path) -> Path:
    """Expected-order ledger matching :func:`flipkart_csv` exactly."""
    path = tmp_path / "expected.csv"
    path.write_text(
        "Seller Order Id,Order Date,Product Price,Seller Commission,GST\n"
        "FK770487,2026-09-20,4800,720,864\n"
        "FK881122,2026-09-21,1000,150,180\n"
        "FK990011,2026-09-22,2500,375,450\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Reconciliation-result fixtures — pre-built by the real reconciler so the
# report-exporter tests never have to hand-roll its internal dict shape.
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_result(flipkart_csv: Path, expected_orders_flipkart: Path) -> dict:
    """``reconcile`` output for a perfect match — empty mismatches.

    ``reconcile`` requires *normalised* frames on **both** sides (``Order_ID``,
    ``Product_Value``, ``Commission``, ``GST_Amount``); feeding it a raw
    marketplace CSV silently injects ``Order_ID = 0`` for every row and makes
    everything look "extra".  The production path normalises the expected
    ledger through ``invoice_diff.cli._normalize_expected`` — done here too, so
    the tests exercise the same transformation the CLI uses.
    """
    from invoice_diff.cli import _normalize_expected

    return reconcile(
        parse_settlement(flipkart_csv),
        _normalize_expected(pd.read_csv(expected_orders_flipkart)),
    )


@pytest.fixture
def all_discrepancies_result(flipkart_csv: Path) -> dict:
    """A settlement + expected pair that exercises every discrepancy type.

    From ``flipkart_csv``: FK770487 (4800/720/864), FK881122 (1000/150/180),
    FK990011 (2500/375/450).  The scenario below produces all four:

        FK770487  expected value 4000 vs 4800 settled  -> VALUE_MISMATCH
        FK990011  expected GST 400 vs 450 settled      -> GST_MISMATCH
        FK881122  expected 1000 vs 1000, GST 180 vs 180 -> clean (control row)
        FK999999  in expected, absent from settlement  -> MISSING_IN_SETTLEMENT
        FKEXTRA   in settlement, absent from expected  -> EXTRA_IN_SETTLEMENT
    """
    settlement = parse_settlement(flipkart_csv)
    extra = pd.DataFrame(
        [{"Order_ID": "FKEXTRA", "Product_Value": 500, "Commission": 0, "GST_Amount": 90}]
    )
    settlement = pd.concat([settlement, extra], ignore_index=True)

    # Normalise so ``reconcile`` sees ``Order_ID`` (it does not accept raw CSV).
    from invoice_diff.cli import _normalize_expected

    expected = _normalize_expected(
        pd.DataFrame(
            [
                {"Seller Order Id": "FK770487", "Product Price": 4000, "Seller Commission": 720, "GST": 864},
                {"Seller Order Id": "FK881122", "Product Price": 1000, "Seller Commission": 150, "GST": 180},
                {"Seller Order Id": "FK990011", "Product Price": 2500, "Seller Commission": 375, "GST": 400},
                {"Seller Order Id": "FK999999", "Product Price": 250, "Seller Commission": 37, "GST": 45},
            ]
        )
    )
    return reconcile(settlement, expected)


# ---------------------------------------------------------------------------
# Reusable helpers
# ---------------------------------------------------------------------------
def assert_universal_schema(df: pd.DataFrame) -> None:
    """Assert ``df`` has exactly the universal schema, in order."""
    assert list(df.columns) == UNIVERSAL_COLUMNS, (
        f"Unexpected columns: {list(df.columns)}"
    )


def result_types(result: dict) -> list[str]:
    """Sorted list of discrepancy-type strings in a reconcile result."""
    mismatches = result["mismatches"]
    return sorted(mismatches["Type"].tolist()) if not mismatches.empty else []
