"""Parse Flipkart / Meesho / Amazon settlement CSVs into a universal schema.

Universal schema (target output):
    Order_ID, Marketplace, Invoice_Date, Product_Value, Commission,
    GST_Amount, Forward_Shipping, Reverse_Shipping, Discount,
    Settlement_Amount

All monetary values are integers in rupees (round to nearest rupee).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Column-name synonyms, lowercased / whitespace-stripped for matching
# ---------------------------------------------------------------------------

SYNONYMS: dict[str, list[str]] = {
    "Order_ID": [
        "order id",
        "orderid",
        "order_id",
        "seller order id",
        "seller order id",
        "sellerorderid",
        "order number",
        "order no",
        "order_no",
        "orderno",
        "parent order id",
        "order# ",
        "order #",
        "order",
    ],
    "Marketplace": [
        "marketplace",
        "platform",
        "channel",
        "source",
        "seller marketplace",
    ],
    "Invoice_Date": [
        "invoice date",
        "invoicedate",
        "invoice_date",
        "order date",
        "orderdate",
        "order_date",
        "settlement date",
        "settlementdate",
        "settlement_date",
        "transaction date",
        "txn date",
        "date",
        "shipment date",
        "shipdate",
    ],
    "Product_Value": [
        "product price",
        "product price",
        "product price",
        "item price",
        "itemprice",
        "item_price",
        "product value",
        "product_value",
        "price per unit",
        "priceperunit",
        "price_per_unit",
        "price",
        "mrp",
        "unit price",
        "unitprice",
        "unit_price",
        "sale price",
        "saleprice",
        "sale_price",
        "item amount",
        "itemamount",
        "gross amount",
    ],
    "Commission": [
        "seller commission",
        "sellercommission",
        "seller_commission",
        "commission",
        "platform fee",
        "platformfee",
        "platform_fee",
        "platform charges",
        "platformcharges",
        "commission amount",
        "commissionamount",
        "commission_amount",
        "referral fee",
        "referralfee",
        "referral_fee",
    ],
    "GST_Amount": [
        "gst",
        "tax amount",
        "taxamount",
        "tax_amount",
        "tax",
        "gst amount",
        "gstamount",
        "gst_amount",
        "igst",
        "cgst+sgst",
        "total tax",
        "totaltax",
        "total_tax",
        "taxable amount",
    ],
    "Forward_Shipping": [
        "forward shipping",
        "forwardshipping",
        "forward_shipping",
        "shipping",
        "shipping fee",
        "shippingfee",
        "shipping_fee",
        "shipping charge",
        "shippingcharge",
        "shipping_charge",
        "dispatch fee",
        "dispatchfee",
        "logistics",
    ],
    "Reverse_Shipping": [
        "reverse shipping",
        "reverseshipping",
        "reverse_shipping",
        "return shipping",
        "returnshipping",
        "return_shipping",
        "return charge",
        "returncharge",
        "return_charge",
        "reverse logistics",
        "reverselogistics",
    ],
    "Discount": [
        "discount",
        "coupon",
        "coupon amount",
        "couponamount",
        "coupon_amount",
        "promo",
        "promotion",
        "offer",
        "offer amount",
        "offeramount",
        "offer_amount",
        "seller discount",
        "sellerdiscount",
        "seller_discount",
        "platform discount",
        "platformdiscount",
        "platform_discount",
    ],
    "Settlement_Amount": [
        "settlement amount",
        "settlementamount",
        "settlement_amount",
        "net amount",
        "netamount",
        "net_amount",
        "amount payable",
        "amountpayable",
        "amount_payable",
        "payable",
        "settlement",
        "remittance",
        "remittance amount",
        "remittanceamount",
        "remittance_amount",
        "final amount",
        "finalamount",
        "final_amount",
    ],
}


def _normalize(col: str) -> str:
    """Lowercase, strip, collapse whitespace, remove non-alnum punctuation."""
    s = str(col).strip().lower()
    s = re.sub(r"[_\s\-\./\(\)#]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _detect_columns(header: list[str]) -> dict[str, str]:
    """Map universal field names to actual column names.

    Returns dict of universal_field -> actual_column_name.  Only fields that
    are found are included.
    """
    mapping: dict[str, str] = {}
    normed = [(i, _normalize(c)) for i, c in enumerate(header)]

    for field, syns in SYNONYMS.items():
        for syn in syns:
            target = _normalize(syn)
            for i, n in normed:
                if n == target:
                    mapping[field] = header[i]
                    break
            if field in mapping:
                break
        # fuzzy fallback: startswith
        if field not in mapping:
            for syn in syns:
                target = _normalize(syn)
                for i, n in normed:
                    if n.startswith(target) or (target.startswith(n) and len(n) > 4):
                        mapping[field] = header[i]
                        break
                if field in mapping:
                    break
    return mapping


def _detect_marketplace(header: list[str], df: pd.DataFrame) -> str:
    """Guess the marketplace from column names.

    Detection relies on columns distinctive to each marketplace's export
    format, so it works even when none of them is the literal name:

        Amazon   -> literal ``OrderID`` column (no space)
        Meesho   -> ``Item Price`` / ``Platform Fee`` / ``Tax Amount``
        Flipkart -> ``Seller Order Id`` / ``Seller Commission`` /
                    ``Settlement Amount`` (without ``Item Price``)
    """
    normed = {_normalize(c) for c in header}

    # 1. explicit literal Marketplace/Platform column with a known value
    for c in header:
        if _normalize(c) in ("marketplace", "platform", "channel", "source"):
            vals = df[c].astype(str).str.strip().str.lower().unique() if len(df) else []
            for v in vals:
                if v in ("flipkart", "meesho", "amazon"):
                    return v.capitalize()

    # 2. distinctive export-format columns
    if "orderid" in normed:
        return "Amazon"
    if any(n in normed for n in ("item price", "platform fee", "platformcharges", "tax amount")):
        return "Meesho"
    if any(
        n in normed
        for n in ("seller order id", "seller commission", "settlement amount", "sellerorderid")
    ):
        return "Flipkart"

    # 3. last resort: an obvious marker in any column name
    joined = " ".join(str(c).lower() for c in header)
    if "flipkart" in joined:
        return "Flipkart"
    if "meesho" in joined:
        return "Meesho"
    if "amazon" in joined:
        return "Amazon"
    return "Unknown"


def _to_int(v: Any) -> int:
    """Parse a currency value like ``'Rs. 1,234.56'`` / ``'₹500'`` / ``'-150'``
    to the nearest whole rupee (int).

    Negative values are preserved (needed for refunds and GST credits).
    Returns 0 for blank / unparseable input.
    """
    if v is None:
        return 0
    if isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if pd.isna(v):
            return 0
        return int(round(v))  # noqa: RUF046 — bool excluded above

    s = str(v).strip()
    if not s or s.lower() in {"-", "--", "nan", "none", "na", "n/a"}:
        return 0

    # strip currency symbols / thousands separators *before* reading the sign,
    # so both "-50" and "Rs. -50" are detected as negative
    s = s.replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs ", "").replace(" ", "")
    neg = s.startswith("-")
    m = re.search(r"\d+(\.\d+)?", s)
    if not m:
        return 0
    val = float(m.group(0))
    r = round(val)  # type: ignore[assignment]  # round() returns int for float input
    return -r if neg else r


def _to_date(v: Any) -> str:
    """Parse a date-like value to ISO 'YYYY-MM-DD'."""
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()[:10]
    s = str(v).strip()
    if not s:
        return ""
    # try pandas
    try:
        ts = pd.to_datetime(s, errors="coerce")
        if pd.notna(ts):
            return ts.date().isoformat()
    except Exception:
        pass
    # manual patterns
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s[: len(s)], fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s[:10]


def _to_order_id(v: Any) -> str:
    s = str(v).strip() if v is not None else ""
    # strip trailing .0 from float reads
    if s.endswith(".0"):
        s = s[:-2]
    return s


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def parse_settlement(path: str | Path) -> pd.DataFrame:
    """Parse a marketplace settlement CSV.  Auto-detects format.

    Returns a DataFrame with the universal schema columns:
        Order_ID, Marketplace, Invoice_Date, Product_Value, Commission,
        GST_Amount, Forward_Shipping, Reverse_Shipping, Discount,
        Settlement_Amount

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the CSV cannot be recognized (no Order_ID-like column).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Settlement file not found: {path}")

    # read raw (lenient dtype=str so we don't lose leading zeros in IDs)
    df_raw = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])

    if df_raw.empty:
        return _empty_result()

    header = list(df_raw.columns)
    mapping = _detect_columns(header)

    if "Order_ID" not in mapping:
        raise ValueError(f"Could not detect an Order_ID column. Detected columns: {header}")

    marketplace = _detect_marketplace(header, df_raw)

    out = pd.DataFrame(index=df_raw.index)
    out["Order_ID"] = df_raw[mapping["Order_ID"]].map(_to_order_id)

    if "Invoice_Date" in mapping:
        out["Invoice_Date"] = df_raw[mapping["Invoice_Date"]].map(_to_date)
    else:
        out["Invoice_Date"] = ""

    out["Marketplace"] = marketplace

    int_fields = [
        "Product_Value",
        "Commission",
        "GST_Amount",
        "Forward_Shipping",
        "Reverse_Shipping",
        "Discount",
        "Settlement_Amount",
    ]
    for f in int_fields:
        if f in mapping:
            out[f] = df_raw[mapping[f]].map(_to_int)
        else:
            out[f] = 0

    # Drop fully-blank rows (no order id and no amount)
    out = out[out["Order_ID"].str.len() > 0].copy()

    # De-duplicate on Order_ID: keep first occurrence
    out = out.drop_duplicates(subset=["Order_ID"], keep="first")

    out = out.reset_index(drop=True)
    out["Settled_On"] = ""  # placeholder, kept for future
    # Reorder columns
    cols = [
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
    out = out[cols]
    return out


def _empty_result() -> pd.DataFrame:
    cols = [
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
    return pd.DataFrame({c: [] for c in cols})


# ---------------------------------------------------------------------------
# Sample-data-friendly: build a settlement df directly from a record dict
# ---------------------------------------------------------------------------


def parse_settlement_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a universal-schema DataFrame from a list of record dicts.

    Each dict may contain any subset of the universal field names plus
    marketplace-format aliases.  Useful for tests and synthetic data.
    """
    rows = []
    for r in records:
        row: dict[str, Any] = {
            "Order_ID": _to_order_id(
                r.get("Order_ID") or r.get("order_id") or r.get("OrderID") or r.get("orderid", "")
            ),
            "Marketplace": r.get("Marketplace", r.get("marketplace", "")),
            "Invoice_Date": _to_date(
                r.get("Invoice_Date")
                or r.get("invoice_date")
                or r.get("Order_Date")
                or r.get("order_date", "")
            ),
        }
        for f in [
            "Product_Value",
            "Commission",
            "GST_Amount",
            "Forward_Shipping",
            "Reverse_Shipping",
            "Discount",
            "Settlement_Amount",
        ]:
            low = f.lower().replace("_", "")
            row[f] = _to_int(r.get(f, r.get(low, 0)))
        rows.append(row)
    cols = [
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
    return pd.DataFrame(rows, columns=cols)
