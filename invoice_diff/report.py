"""Generate multi-format reconciliation reports.

Supported formats: ``json``, ``csv``, ``md``, ``xlsx``.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# ANSI / color helpers (used by markdown + csv pretty printers)
# ---------------------------------------------------------------------------


def _fmt_int(n: Any) -> str:
    """Format an integer with thousands separators for rupees."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def _export_json(result: dict[str, Any], out_path: Path) -> Path:
    summary = dict(result.get("summary", {}))
    mismatches = result.get("mismatches", pd.DataFrame())

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "mismatches": mismatches.to_dict(orient="records"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    return out_path


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _export_csv(result: dict[str, Any], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mismatches = result.get("mismatches", pd.DataFrame())

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        # write a summary header block first
        summary = result.get("summary", {})
        f.write("# invoice-diff reconciliation summary\n")
        f.write(f"# generated_at,{datetime.utcnow().isoformat()}Z\n")
        for k, v in summary.items():
            f.write(f"# {k},{v}\n")
        f.write("\n")
        writer = csv.writer(f)
        writer.writerow(["Order_ID", "Type", "Expected_Value",
                         "Settlement_Value", "Difference", "Note"])
        for _, row in mismatches.iterrows():
            writer.writerow([
                row["Order_ID"], row["Type"],
                row["Expected_Value"], row["Settlement_Value"],
                row["Difference"], row.get("Note", ""),
            ])
    return out_path


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def _export_md(result: dict[str, Any], out_path: Path) -> Path:
    summary = result.get("summary", {})
    mismatches = result.get("mismatches", pd.DataFrame())
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Invoice Reconciliation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    label_map = {
        "total_orders_in_settlement": "Orders in settlement",
        "total_orders_in_expected": "Orders in expected",
        "matched": "Matched",
        "missing_in_settlement": "Missing in settlement",
        "extra_in_settlement": "Extra in settlement",
        "value_mismatch_count": "Value mismatches",
        "value_mismatch_amount": "Value mismatch amount (Rs.)",
        "gst_mismatch_count": "GST mismatches",
        "gst_mismatch_amount": "GST mismatch amount (Rs.)",
        "commission_mismatch_count": "Commission mismatches",
        "rounded_off_count": "Rounded-off",
        "total_discrepancies": "Total discrepancies",
    }
    for k, v in summary.items():
        label = label_map.get(k, k)
        val = _fmt_int(v) if isinstance(v, int) else str(v)
        lines.append(f"| {label} | {val} |")
    lines.append("")

    lines.append("## All Mismatches")
    lines.append("")
    if mismatches.empty:
        lines.append("_No discrepancies found._")
    else:
        lines.append("| Order ID | Type | Expected | Settlement | Difference | Note |")
        lines.append("|---|---|---:|---:|---:|---|")
        for _, row in mismatches.iterrows():
            lines.append(
                f"| {row['Order_ID']} | {row['Type']} | "
                f"{_fmt_int(row['Expected_Value'])} | "
                f"{_fmt_int(row['Settlement_Value'])} | "
                f"{_fmt_int(row['Difference'])} | "
                f"{row.get('Note', '')} |"
            )
    lines.append("")

    # Per-type breakdowns
    lines.append("## Breakdown by Type")
    lines.append("")
    if not mismatches.empty:
        counts = mismatches["Type"].value_counts().to_dict()
        lines.append("| Type | Count |")
        lines.append("|---|---:|")
        for t, c in counts.items():
            lines.append(f"| {t} | {c} |")
    else:
        lines.append("_None._")
    lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path


# ---------------------------------------------------------------------------
# XLSX (openpyxl with styled sheets)
# ---------------------------------------------------------------------------


def _export_xlsx(result: dict[str, Any], out_path: Path) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    summary = result.get("summary", {})
    mismatches = result.get("mismatches", pd.DataFrame())

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    alt_fill = PatternFill("solid", fgColor="F2F7FC")
    total_fill = PatternFill("solid", fgColor="FFF2CC")
    bad_fill = PatternFill("solid", fgColor="FCE4E4")
    good_fill = PatternFill("solid", fgColor="E2EFDA")
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # --- Summary sheet ---
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Metric", "Value"])
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    label_map = {
        "total_orders_in_settlement": "Orders in settlement",
        "total_orders_in_expected": "Orders in expected",
        "matched": "Matched",
        "missing_in_settlement": "Missing in settlement",
        "extra_in_settlement": "Extra in settlement",
        "value_mismatch_count": "Value mismatches",
        "value_mismatch_amount": "Value mismatch amount (Rs.)",
        "gst_mismatch_count": "GST mismatches",
        "gst_mismatch_amount": "GST mismatch amount (Rs.)",
        "commission_mismatch_count": "Commission mismatches",
        "rounded_off_count": "Rounded-off",
        "total_discrepancies": "Total discrepancies",
    }
    for k, v in summary.items():
        row_idx = ws.max_row + 1
        ws.append([label_map.get(k, k), v])
        ws.cell(row=row_idx, column=1).border = border
        ws.cell(row=row_idx, column=2).border = border
        if row_idx % 2 == 0:
            for c in ws[row_idx]:
                c.fill = alt_fill
        # highlight discrepancies in red, clean in green
        if k in ("missing_in_settlement", "extra_in_settlement",
                 "value_mismatch_count", "gst_mismatch_count",
                 "commission_mismatch_count", "total_discrepancies"):
            if isinstance(v, int) and v > 0:
                ws.cell(row=row_idx, column=2).fill = bad_fill
                ws.cell(row=row_idx, column=2).font = Font(bold=True, color="C00000")
            elif isinstance(v, int) and v == 0:
                ws.cell(row=row_idx, column=2).fill = good_fill
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 18
    ws.freeze_panes = "A2"

    # --- All Mismatches sheet ---
    ws2 = wb.create_sheet("All Mismatches")
    cols = ["Order_ID", "Type", "Expected_Value", "Settlement_Value",
            "Difference", "Note"]
    ws2.append(cols)
    for cell in ws2[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = border
    if mismatches.empty:
        ws2.append(["(no discrepancies)"])
        ws2["A2"].font = Font(italic=True, color="808080")
    else:
        for i, (_, row) in enumerate(mismatches.iterrows(), start=2):
            ws2.append([row["Order_ID"], row["Type"], row["Expected_Value"],
                        row["Settlement_Value"], row["Difference"],
                        row.get("Note", "")])
            for c in ws2[i]:
                c.border = border
            if row["Type"] in ("MISSING_IN_SETTLEMENT", "EXTRA_IN_SETTLEMENT",
                               "VALUE_MISMATCH", "GST_MISMATCH",
                               "COMMISSION_MISMATCH"):
                if abs(int(row["Difference"])) > 0:
                    ws2.cell(row=i, column=5).fill = bad_fill
                    ws2.cell(row=i, column=5).font = Font(bold=True, color="C00000")
            elif row["Type"] == "ROUNDED_OFF":
                ws2.cell(row=i, column=5).fill = total_fill
    widths = {"A": 18, "B": 24, "C": 14, "D": 16, "E": 12, "F": 50}
    for col, w in widths.items():
        ws2.column_dimensions[col].width = w
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = ws2.dimensions

    # --- Per-type breakdown sheets ---
    if not mismatches.empty:
        type_counts = mismatches["Type"].value_counts()
        for t, cnt in type_counts.items():
            # sanitize sheet name (openpyxl max 31 chars)
            name = t.replace("_", " ")[:31]
            wst = wb.create_sheet(name)
            wst.append([f"Type: {t}", f"Count: {cnt}"])
            wst["A1"].font = Font(bold=True, size=12, color="1F4E78")
            wst["B1"].font = Font(bold=True, size=12)
            wst.append([])
            wst.append(["Order_ID", "Expected_Value", "Settlement_Value",
                        "Difference", "Note"])
            for cell in wst[3]:
                cell.fill = header_fill
                cell.font = header_font
                cell.border = border
            subset = mismatches[mismatches["Type"] == t]
            for i, (_, row) in enumerate(subset.iterrows(), start=4):
                wst.append([row["Order_ID"], row["Expected_Value"],
                            row["Settlement_Value"], row["Difference"],
                            row.get("Note", "")])
                for c in wst[i]:
                    c.border = border
            for col, w in widths.items():
                wst.column_dimensions[col].width = w

    wb.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def export_report(result: dict[str, Any], format: str = "json",
                  out_path: str | Path | None = None) -> str:
    """Export a reconciliation result to a file.

    Args:
        result: dict with ``summary`` and ``mismatches`` (see reconciler).
        format: one of ``json``, ``csv``, ``md``, ``xlsx``.
        out_path: destination path; if None, generated under ``./reports/``.

    Returns:
        The path written to (as ``str``).

    Raises:
        ValueError: on unsupported format.
    """
    fmt = format.lower()
    if out_path is None:
        out_path = Path("reports") / f"report_{fmt}"
    else:
        out_path = Path(out_path)
    if out_path.is_dir() or out_path.suffix == "":
        out_path = out_path / f"report_{fmt}"

    if fmt == "json":
        out_path = _export_json(result, out_path.with_suffix(".json"))
    elif fmt == "csv":
        out_path = _export_csv(result, out_path.with_suffix(".csv"))
    elif fmt == "md":
        out_path = _export_md(result, out_path.with_suffix(".md"))
    elif fmt == "xlsx":
        out_path = _export_xlsx(result, out_path.with_suffix(".xlsx"))
    else:
        raise ValueError(f"Unsupported format: {format!r}. Use json|csv|md|xlsx.")
    return str(out_path)
