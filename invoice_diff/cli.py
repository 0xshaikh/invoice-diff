"""Command-line interface for invoice-diff."""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from invoice_diff import __version__
from invoice_diff.parser import parse_settlement
from invoice_diff.reconciler import reconcile
from invoice_diff.report import export_report

# ---------------------------------------------------------------------------
# ANSI color helpers (no colorama dep)
# ---------------------------------------------------------------------------

_ANSI = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "grey": "\033[90m",
}


def _colorize(text: str, color: str, enabled: bool = True) -> str:
    if not enabled:
        return text
    code = _ANSI.get(color, "")
    return f"{code}{text}{_ANSI['reset']}"


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in __import__("os").environ


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_parse(args: argparse.Namespace) -> int:
    """Parse a settlement CSV and print summary + head of rows."""
    color = _use_color()
    try:
        df = parse_settlement(args.input)
    except FileNotFoundError as e:
        print(_colorize(f"Error: {e}", "red", color), file=sys.stderr)
        return 2
    except ValueError as e:
        print(_colorize(f"Error: {e}", "red", color), file=sys.stderr)
        return 2

    if df.empty:
        print(_colorize("Parsed 0 orders.", "yellow", color))
        return 0

    market = df["Marketplace"].mode().iloc[0] if not df.empty else "?"
    print(_colorize(f"Parsed {len(df):,} orders from {args.input}", "cyan", color))
    print(f"  Marketplace:     {_colorize(market, 'green', color)}")
    print(
        f"  Date range:      {df['Invoice_Date'].min() or '(none)'} to {df['Invoice_Date'].max() or '(none)'}"
    )
    print(f"  Total Product:   Rs.{df['Product_Value'].sum():,}")
    print(f"  Total Commission:Rs.{df['Commission'].sum():,}")
    print(f"  Total GST:       Rs.{df['GST_Amount'].sum():,}")
    print(f"  Total Settlement:Rs.{df['Settlement_Amount'].sum():,}")
    print()
    print(_colorize("First 5 orders:", "bold", color))
    print(df.head().to_string(index=False))
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    """Parse settlement + expected, reconcile, and export a report."""
    color = _use_color()
    try:
        settlement = parse_settlement(args.settlement)
    except (FileNotFoundError, ValueError) as e:
        print(_colorize(f"Error parsing settlement: {e}", "red", color), file=sys.stderr)
        return 2

    # Expected may be a raw order report; be lenient
    try:
        expected = pd.read_csv(args.expected, dtype=str, keep_default_na=False, na_values=[""])
        expected = expected.apply(
            lambda col: col.map(lambda v: v.strip() if isinstance(v, str) else v)
        )
    except FileNotFoundError as e:
        print(_colorize(f"Error: {e}", "red", color), file=sys.stderr)
        return 2

    # Best-effort normalization of expected columns
    expected = _normalize_expected(expected)

    result = reconcile(settlement, expected)
    summary = result["summary"]
    mismatches = result["mismatches"]

    # Export report
    try:
        out = export_report(result, format=args.format, out_path=args.out)
    except ValueError as e:
        print(_colorize(f"Error: {e}", "red", color), file=sys.stderr)
        return 2
    print(_colorize(f"Report written: {out}", "cyan", color))

    # Console summary
    print()
    print(_colorize("=== Reconciliation Summary ===", "bold", color))
    rows = [
        ("Orders in settlement", summary["total_orders_in_settlement"]),
        ("Orders in expected", summary["total_orders_in_expected"]),
        ("Matched", summary["matched"]),
        ("Missing in settlement", summary["missing_in_settlement"]),
        ("Extra in settlement", summary["extra_in_settlement"]),
        ("Value mismatches", summary["value_mismatch_count"]),
        ("Value mismatch amount (Rs.)", summary["value_mismatch_amount"]),
        ("GST mismatches", summary["gst_mismatch_count"]),
        ("GST mismatch amount (Rs.)", summary["gst_mismatch_amount"]),
        ("Commission mismatches", summary["commission_mismatch_count"]),
        ("Rounded-off", summary.get("rounded_off_count", 0)),
        ("Total discrepancies", summary["total_discrepancies"]),
    ]
    width = max(len(r[0]) for r in rows)
    for label, val in rows:
        shown = f"Rs.{val:,}" if "amount" in label.lower() else f"{val:,}"
        if (
            isinstance(val, int)
            and val > 0
            and label not in ("Orders in settlement", "Orders in expected", "Matched")
        ):
            shown_s = _colorize(shown, "red", color)
        elif (
            isinstance(val, int)
            and val == 0
            and label not in ("Orders in settlement", "Orders in expected")
        ):
            shown_s = _colorize(shown, "green", color)
        else:
            shown_s = shown
        print(f"  {label:<{width}}  {shown_s}")

    print()
    if not mismatches.empty:
        print(_colorize("Discrepancy breakdown:", "bold", color))
        counts = mismatches["Type"].value_counts()
        for t, c in counts.items():
            print(f"  {_colorize(t, 'yellow', color):<24} {c}")
    else:
        print(_colorize("No discrepancies found.", "green", color))

    return 1 if summary["total_discrepancies"] > 0 else 0


def _normalize_expected(df: pd.DataFrame) -> pd.DataFrame:
    """Map common order-report column names onto the universal schema.

    Tolerant of Flipkart/Meesho/Amazon order-export naming.  Fills missing
    numeric fields with 0.
    """
    from invoice_diff.parser import _normalize, _to_int, _to_order_id

    out = df.copy()
    lower_map = {_normalize(c): c for c in df.columns}

    def _find(candidates: list[str]) -> str | None:
        for cand in candidates:
            n = _normalize(cand)
            if n in lower_map:
                return lower_map[n]
        # fuzzy: substring
        for n, orig in lower_map.items():
            for cand in candidates:
                cn = _normalize(cand)
                if len(cn) > 3 and (n == cn or cn in n or n in cn):
                    return orig
        return None

    oid_col = _find(
        ["order id", "orderid", "order_id", "seller order id", "order number", "order#"]
    )
    if oid_col:
        out["Order_ID"] = out[oid_col].map(_to_order_id)
    elif "Order_ID" in out.columns:
        out["Order_ID"] = out["Order_ID"].map(_to_order_id)
    else:
        raise ValueError(
            f"Expected report has no recognizable Order_ID column. Columns: {list(df.columns)}"
        )

    pv_col = _find(
        [
            "product price",
            "item price",
            "price",
            "price per unit",
            "mrp",
            "sale price",
            "product value",
            "priceperunit",
        ]
    )
    out["Product_Value"] = out[pv_col].map(_to_int) if pv_col else 0

    c_col = _find(
        ["commission", "seller commission", "platform fee", "platform charges", "referral fee"]
    )
    out["Commission"] = out[c_col].map(_to_int) if c_col else 0

    gst_col = _find(["gst", "tax", "tax amount", "total tax", "igst"])
    out["GST_Amount"] = out[gst_col].map(_to_int) if gst_col else 0

    return out


def _cmd_check(args: argparse.Namespace) -> int:
    """Quick sanity check: parse settlement and flag obvious issues."""
    color = _use_color()
    try:
        df = parse_settlement(args.settlement)
    except (FileNotFoundError, ValueError) as e:
        print(_colorize(f"Error: {e}", "red", color), file=sys.stderr)
        return 2

    if df.empty:
        print(_colorize("Check failed: no orders parsed.", "yellow", color))
        return 2

    print(_colorize("Sanity check:", "bold", color))
    print(f"  Orders parsed:    {len(df):,}")
    print(f"  Marketplace:      {df['Marketplace'].mode().iloc[0]}")
    print(f"  Missing dates:    {(df['Invoice_Date'] == '').sum()}")
    print(f"  Missing Order_ID: {(df['Order_ID'].str.len() == 0).sum()}")
    print(f"  Negative Product: {(df['Product_Value'] < 0).sum()}")
    print(f"  Negative GST:     {(df['GST_Amount'] < 0).sum()}")
    # settlement vs (product - commission - shipping + discount + gst) sanity
    expected_settle = (
        df["Product_Value"]
        - df["Commission"]
        - df["Forward_Shipping"]
        - df["Reverse_Shipping"]
        + df["Discount"]
        + df["GST_Amount"]
    )
    drift = (df["Settlement_Amount"] - expected_settle).abs()
    big_drift = (drift > 1).sum()
    print(f"  Settlement drift >Rs.1: {big_drift}")
    if big_drift == 0:
        print(_colorize("  => Settlement arithmetic looks consistent.", "green", color))
    else:
        print(
            _colorize(f"  => {big_drift} orders have settlement arithmetic drift.", "yellow", color)
        )
    return 0 if big_drift == 0 else 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="invoice-diff",
        description="Reconcile marketplace settlement invoices against order data.",
    )
    p.add_argument("--version", action="version", version=f"invoice-diff {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser("parse", help="Parse a settlement CSV and show summary")
    pp.add_argument("--input", "-i", required=True, help="Path to settlement CSV")
    pp.set_defaults(func=_cmd_parse)

    pr = sub.add_parser("reconcile", help="Reconcile settlement against expected orders")
    pr.add_argument("--settlement", "-s", required=True, help="Settlement CSV")
    pr.add_argument("--expected", "-e", required=True, help="Expected orders CSV")
    pr.add_argument(
        "--format",
        "-f",
        choices=["json", "csv", "md", "xlsx"],
        default="json",
        help="Report format (default: json)",
    )
    pr.add_argument("--out", "-o", default=None, help="Output path (optional)")
    pr.set_defaults(func=_cmd_reconcile)

    pc = sub.add_parser("check", help="Quick sanity check of a settlement")
    pc.add_argument("--settlement", "-s", required=True, help="Settlement CSV")
    pc.set_defaults(func=_cmd_check)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
