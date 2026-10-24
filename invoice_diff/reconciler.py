"""Reconcile a parsed settlement against an expected order report."""

from __future__ import annotations

from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Discrepancy type constants
# ---------------------------------------------------------------------------

MISSING_IN_SETTLEMENT = "MISSING_IN_SETTLEMENT"
EXTRA_IN_SETTLEMENT = "EXTRA_IN_SETTLEMENT"
VALUE_MISMATCH = "VALUE_MISMATCH"
GST_MISMATCH = "GST_MISMATCH"
COMMISSION_MISMATCH = "COMMISSION_MISMATCH"
ROUNDED_OFF = "ROUNDED_OFF"

TOLERANCE_RUPEES = 1  # VALUE_MISMATCH threshold: differs by more than 1 rupee

# Columns considered in reconciliation
_COMPARE_FIELDS = ["Product_Value", "Commission", "GST_Amount"]


def _ensure_fields(df: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    """Return df with the given fields guaranteed to exist (as 0 if absent)."""
    out = df.copy()
    for f in fields:
        if f not in out.columns:
            out[f] = 0
    return out


def reconcile(settlement: pd.DataFrame, expected: pd.DataFrame) -> dict[str, Any]:
    """Compare a parsed settlement against an expected order report.

    Args:
        settlement: Universal-schema DataFrame (from ``parse_settlement``).
        expected:   DataFrame with at least an ``Order_ID`` column and
                    ideally Product_Value / Commission / GST_Amount columns.
                    May be a raw order report; missing columns default to 0.

    Returns:
        dict with keys:
          - ``mismatches``: DataFrame of discrepancies
          - ``summary``: dict of aggregate counts (see module docstring)
    """
    expected = _ensure_fields(expected, _COMPARE_FIELDS + ["Order_ID"])
    settlement = _ensure_fields(settlement, _COMPARE_FIELDS + ["Order_ID"])

    # Normalize ID dtype to str
    expected = expected.copy()
    settlement = settlement.copy()
    expected["Order_ID"] = expected["Order_ID"].astype(str)
    settlement["Order_ID"] = settlement["Order_ID"].astype(str)

    exp_ids = set(expected["Order_ID"])
    sett_ids = set(settlement["Order_ID"])

    missing_ids = exp_ids - sett_ids
    extra_ids = sett_ids - exp_ids
    common_ids = exp_ids & sett_ids

    mismatches: list[dict[str, Any]] = []

    # --- Missing in settlement ---
    for oid in sorted(missing_ids):
        row = expected[expected["Order_ID"] == oid].iloc[0]
        mismatches.append({
            "Order_ID": oid,
            "Type": MISSING_IN_SETTLEMENT,
            "Expected_Value": int(row.get("Product_Value", 0) or 0),
            "Settlement_Value": 0,
            "Difference": int(row.get("Product_Value", 0) or 0),
            "Note": "Order present in expected but absent from settlement",
        })

    # --- Extra in settlement ---
    for oid in sorted(extra_ids):
        row = settlement[settlement["Order_ID"] == oid].iloc[0]
        mismatches.append({
            "Order_ID": oid,
            "Type": EXTRA_IN_SETTLEMENT,
            "Expected_Value": 0,
            "Settlement_Value": int(row.get("Product_Value", 0) or 0),
            "Difference": int(row.get("Product_Value", 0) or 0),
            "Note": "Order in settlement but not in expected order report",
        })

    # --- Field-level comparisons on common orders ---
    value_mismatch_count = 0
    value_mismatch_amount = 0
    gst_mismatch_count = 0
    gst_mismatch_amount = 0
    commission_mismatch_count = 0
    rounded_off_count = 0

    exp_by_id = expected.set_index("Order_ID")
    sett_by_id = settlement.set_index("Order_ID")

    for oid in sorted(common_ids):
        e = exp_by_id.loc[oid]
        s = sett_by_id.loc[oid]

        # If duplicate index, .loc returns a DataFrame; handle gracefully.
        if isinstance(e, pd.DataFrame):
            e = e.iloc[0]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[0]

        # --- Value mismatch ---
        ev = int(e.get("Product_Value", 0) or 0)
        sv = int(s.get("Product_Value", 0) or 0)
        diff = sv - ev
        if abs(diff) > TOLERANCE_RUPEES:
            value_mismatch_count += 1
            value_mismatch_amount += abs(diff)
            mismatches.append({
                "Order_ID": oid,
                "Type": VALUE_MISMATCH,
                "Expected_Value": ev,
                "Settlement_Value": sv,
                "Difference": diff,
                "Note": f"Product value differs by Rs.{abs(diff)}",
            })
        elif diff != 0:
            # small rounding drift
            rounded_off_count += 1
            mismatches.append({
                "Order_ID": oid,
                "Type": ROUNDED_OFF,
                "Expected_Value": ev,
                "Settlement_Value": sv,
                "Difference": diff,
                "Note": f"Sub-rupee / rounding drift of Rs.{abs(diff)}",
            })

        # --- GST mismatch ---
        eg = int(e.get("GST_Amount", 0) or 0)
        sg = int(s.get("GST_Amount", 0) or 0)
        gdiff = sg - eg
        if gdiff != 0:
            gst_mismatch_count += 1
            gst_mismatch_amount += abs(gdiff)
            mismatches.append({
                "Order_ID": oid,
                "Type": GST_MISMATCH,
                "Expected_Value": eg,
                "Settlement_Value": sg,
                "Difference": gdiff,
                "Note": f"GST differs by Rs.{abs(gdiff)} (platform may have recalculated)",
            })

        # --- Commission mismatch ---
        ec = int(e.get("Commission", 0) or 0)
        sc = int(s.get("Commission", 0) or 0)
        cdiff = sc - ec
        if cdiff != 0:
            commission_mismatch_count += 1
            mismatches.append({
                "Order_ID": oid,
                "Type": COMMISSION_MISMATCH,
                "Expected_Value": ec,
                "Settlement_Value": sc,
                "Difference": cdiff,
                "Note": f"Commission differs by Rs.{abs(cdiff)} (rate off)",
            })

    mismatches_df = pd.DataFrame(
        mismatches,
        columns=["Order_ID", "Type", "Expected_Value", "Settlement_Value",
                 "Difference", "Note"],
    )
    if mismatches_df.empty:
        mismatches_df = pd.DataFrame(
            columns=["Order_ID", "Type", "Expected_Value", "Settlement_Value",
                     "Difference", "Note"],
        )

    summary = {
        "total_orders_in_settlement": int(len(sett_ids)),
        "total_orders_in_expected": int(len(exp_ids)),
        "matched": int(len(common_ids)),
        "missing_in_settlement": int(len(missing_ids)),
        "extra_in_settlement": int(len(extra_ids)),
        "value_mismatch_count": int(value_mismatch_count),
        "value_mismatch_amount": int(value_mismatch_amount),
        "gst_mismatch_count": int(gst_mismatch_count),
        "gst_mismatch_amount": int(gst_mismatch_amount),
        "commission_mismatch_count": int(commission_mismatch_count),
        "rounded_off_count": int(rounded_off_count),
        "total_discrepancies": int(len(mismatches)),
    }

    return {"mismatches": mismatches_df, "summary": summary}
