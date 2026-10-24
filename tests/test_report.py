"""Tests for ``invoice_diff.report`` (the report exporter).

``export_report(result, format=..., out_path=...)`` takes a reconcile result
``{"summary": dict, "mismatches": DataFrame}`` and writes one of four formats:
``json``, ``csv``, ``md``, ``xlsx``.  It returns the written path as a ``str``.

Covers:
    * JSON export — valid JSON, summary + mismatches preserved, types intact
    * CSV export — summary comment block, mismatch rows readable
    * Markdown export — title, summary table, mismatch rows
    * XLSX export — openable workbook with the expected sheets
    * Empty-result handling for every format
    * Unsupported format → ValueError
    * ``out_path=None`` default-directory behaviour
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from invoice_diff.reconciler import (
    EXTRA_IN_SETTLEMENT,
    GST_MISMATCH,
    MISSING_IN_SETTLEMENT,
    VALUE_MISMATCH,
)
from invoice_diff.report import export_report

ALL_TYPES = {
    MISSING_IN_SETTLEMENT,
    EXTRA_IN_SETTLEMENT,
    VALUE_MISMATCH,
    GST_MISMATCH,
}


def _mismatch_rows(result: dict) -> list[dict]:
    return result["mismatches"].to_dict(orient="records")


# ===========================================================================
# JSON
# ===========================================================================
class TestJsonExport:
    def test_writes_file_and_returns_path(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        assert returned.endswith(".json")
        assert Path(returned).exists()

    def test_valid_json(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)

    def test_top_level_keys(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        assert set(payload) == {"generated_at", "summary", "mismatches"}

    def test_summary_round_trips(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        assert payload["summary"] == all_discrepancies_result["summary"]

    def test_mismatches_round_trip_row_count(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        assert len(payload["mismatches"]) == len(all_discrepancies_result["mismatches"])

    def test_discrepancy_types_preserved(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        types = {row["Type"] for row in payload["mismatches"]}
        assert types >= ALL_TYPES

    def test_order_ids_preserved(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        ids = {row["Order_ID"] for row in payload["mismatches"]}
        assert {"FKEXTRA", "FK999999"} <= ids

    def test_generated_at_is_iso8601(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="json", out_path=tmp_path / "r.json"
        )
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        # datetime.isoformat() with a trailing Z
        assert payload["generated_at"].endswith("Z")
        assert "T" in payload["generated_at"]

    def test_empty_result(self, clean_result, tmp_path: Path) -> None:
        returned = export_report(clean_result, format="json", out_path=tmp_path / "r.json")
        payload = json.loads(Path(returned).read_text(encoding="utf-8"))
        assert payload["mismatches"] == []


# ===========================================================================
# CSV
# ===========================================================================
class TestCsvExport:
    def test_writes_file(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        assert returned.endswith(".csv")
        assert Path(returned).exists()

    def test_starts_with_summary_comment_block(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        lines = Path(returned).read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("# ")
        assert any(line.startswith("# total_orders_in_settlement") for line in lines)

    def test_header_row_present(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        lines = Path(returned).read_text(encoding="utf-8").splitlines()
        assert lines[-len(lines)] != ""  # sanity
        assert any(line.startswith("Order_ID,Type,") for line in lines)

    def test_mismatch_row_count(self, all_discrepancies_result, tmp_path: Path) -> None:
        """Read the file skipping the ``#`` summary block and the blank line."""
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        lines = Path(returned).read_text(encoding="utf-8").splitlines()
        body = [ln for ln in lines if ln and not ln.startswith("#")]
        header, rows = body[0], body[1:]
        assert header.startswith("Order_ID,")
        assert len(rows) == len(all_discrepancies_result["mismatches"])

    def test_all_types_present_in_csv(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        text = Path(returned).read_text(encoding="utf-8")
        for t in ALL_TYPES:
            assert t in text

    def test_all_types_parseable(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        lines = [
            ln for ln in Path(returned).read_text().splitlines() if ln and not ln.startswith("#")
        ]
        df = pd.read_csv(StringIO("\n".join(lines)))
        assert len(df) == len(all_discrepancies_result["mismatches"])
        assert set(df.columns) == {
            "Order_ID",
            "Type",
            "Expected_Value",
            "Settlement_Value",
            "Difference",
            "Note",
        }
        assert set(df["Type"]) >= ALL_TYPES

    def test_summary_values_written(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        text = Path(returned).read_text(encoding="utf-8")
        expected_total = all_discrepancies_result["summary"]["total_discrepancies"]
        assert f"# total_discrepancies,{expected_total}" in text

    def test_summary_keys_all_present(self, all_discrepancies_result, tmp_path: Path) -> None:
        """Every summary metric from the reconciler reaches the CSV comment block."""
        returned = export_report(
            all_discrepancies_result, format="csv", out_path=tmp_path / "r.csv"
        )
        text = Path(returned).read_text(encoding="utf-8")
        for key in all_discrepancies_result["summary"]:
            assert f"# {key}," in text

    def test_empty_result(self, clean_result, tmp_path: Path) -> None:
        returned = export_report(clean_result, format="csv", out_path=tmp_path / "r.csv")
        text = Path(returned).read_text(encoding="utf-8")
        # Summary block + header, but zero data rows.
        body = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
        assert len(body) == 1
        assert "# total_discrepancies,0" in text


# ===========================================================================
# Markdown
# ===========================================================================
class TestMarkdownExport:
    def test_writes_file(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        assert returned.endswith(".md")
        assert Path(returned).exists()

    def test_has_title(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        assert text.startswith("# Invoice Reconciliation Report")

    def test_has_summary_section(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        assert "## Summary" in text
        assert "| Metric | Value |" in text

    def test_summary_table_has_rows(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        for label in ["Orders in settlement", "Matched", "Total discrepancies"]:
            assert label in text

    def test_discrepancy_types_present(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        for t in ALL_TYPES:
            assert t in text

    def test_order_ids_present(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(all_discrepancies_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        for oid in ["FKEXTRA", "FK999999"]:
            assert oid in text

    def test_empty_result_shows_no_discrepancies_message(
        self, clean_result, tmp_path: Path
    ) -> None:
        returned = export_report(clean_result, format="md", out_path=tmp_path / "r.md")
        text = Path(returned).read_text(encoding="utf-8")
        assert "_No discrepancies found._" in text


# ===========================================================================
# XLSX
# ===========================================================================
class TestXlsxExport:
    def test_writes_file(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="xlsx", out_path=tmp_path / "r.xlsx"
        )
        assert returned.endswith(".xlsx")
        assert Path(returned).exists()
        assert Path(returned).stat().st_size > 0

    def test_xlsx_is_readable_by_pandas(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="xlsx", out_path=tmp_path / "r.xlsx"
        )
        sheets = pd.read_excel(returned, sheet_name=None)
        assert isinstance(sheets, dict)
        assert len(sheets) >= 1

    def test_xlsx_total_row_count(self, all_discrepancies_result, tmp_path: Path) -> None:
        """Across all sheets the mismatch rows must be accounted for."""
        returned = export_report(
            all_discrepancies_result, format="xlsx", out_path=tmp_path / "r.xlsx"
        )
        sheets = pd.read_excel(returned, sheet_name=None)
        total = sum(len(df) for df in sheets.values())
        # A summary sheet may add rows; mismatch rows themselves must be present.
        assert total >= len(all_discrepancies_result["mismatches"])

    def test_xlsx_has_discrepancy_type_info(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="xlsx", out_path=tmp_path / "r.xlsx"
        )
        sheets = pd.read_excel(returned, sheet_name=None)
        # Either a Type column somewhere or type-named sheets — accept either.
        has_type_col = any("Type" in df.columns for df in sheets.values())
        has_type_sheets = any(t in str(sheets.keys()) for t in ALL_TYPES) or any(
            any(t.split("_")[0] in str(name) for t in ALL_TYPES) for name in sheets
        )
        assert has_type_col or has_type_sheets

    def test_xlsx_discrepancy_ids_readable(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="xlsx", out_path=tmp_path / "r.xlsx"
        )
        sheets = pd.read_excel(returned, sheet_name=None)
        all_ids = set()
        for df in sheets.values():
            if "Order_ID" in df.columns:
                all_ids.update(str(v) for v in df["Order_ID"].dropna().tolist())
        assert "FKEXTRA" in all_ids

    def test_empty_result(self, clean_result, tmp_path: Path) -> None:
        returned = export_report(clean_result, format="xlsx", out_path=tmp_path / "r.xlsx")
        sheets = pd.read_excel(returned, sheet_name=None)
        # "All Mismatches" keeps its header row and writes a
        # "(no discrepancies)" placeholder in the Order_ID cell when empty.
        assert "All Mismatches" in sheets
        assert len(sheets["All Mismatches"]) == 1
        assert sheets["All Mismatches"].iloc[0, 0] == "(no discrepancies)"
        # Summary sheet is still fully populated (12 metrics + header).
        assert len(sheets["Summary"]) == 12
        assert sheets["Summary"].iloc[-1, 0] == "Total discrepancies"
        assert sheets["Summary"].iloc[-1, 1] == 0


# ===========================================================================
# Format dispatch / edge cases
# ===========================================================================
class TestExportEdgeCases:
    def test_unsupported_format_raises_value_error(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError) as excinfo:
            export_report(all_discrepancies_result, format="pdf", out_path=tmp_path / "r.pdf")
        assert "pdf" in str(excinfo.value)

    def test_format_is_case_insensitive(self, all_discrepancies_result, tmp_path: Path) -> None:
        returned = export_report(
            all_discrepancies_result, format="JSON", out_path=tmp_path / "r.json"
        )
        assert json.loads(Path(returned).read_text(encoding="utf-8"))["mismatches"]

    def test_out_path_none_writes_under_reports_dir(
        self, all_discrepancies_result, tmp_path: Path, monkeypatch
    ) -> None:
        """``out_path=None`` defaults to ``reports/report_json/report_json.json``.

        Two sharp edges worth pinning down:
          * the default root is the current working directory, not ``tmp_path``,
            so the cwd must be monkeypatched;
          * ``reports/report_json`` is treated as a *directory* and the final
            ``.json`` is applied inside it — so the file lands two levels down.
        """
        monkeypatch.chdir(tmp_path)
        returned = export_report(all_discrepancies_result, format="json")
        try:
            written = Path(returned)
            assert written.suffix == ".json"
            assert written.name == "report_json.json"
            assert written.parts[-3] == "reports"
            assert written.parts[-2] == "report_json"
            assert written.exists()
            assert written.stat().st_size > 0
        finally:
            import shutil

            shutil.rmtree(tmp_path / "reports", ignore_errors=True)

    def test_creates_missing_parent_directories(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        nested = tmp_path / "deep" / "nested" / "report.json"
        assert not nested.parent.exists()
        returned = export_report(all_discrepancies_result, format="json", out_path=nested)
        assert Path(returned).exists()

    def test_out_path_as_bare_directory_appends_default_name(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        """A directory ``out_path`` gets ``report_<format>.<ext>`` appended."""
        target = tmp_path / "outdir"
        target.mkdir()
        returned = export_report(all_discrepancies_result, format="json", out_path=target)
        assert Path(returned).parent == target
        assert Path(returned).name.startswith("report")
        assert Path(returned).suffix == ".json"
        assert Path(returned).exists()

    def test_does_not_mutate_input_result(self, all_discrepancies_result) -> None:
        """Exporting must not corrupt the caller's result dict."""
        original_mismatches = all_discrepancies_result["mismatches"].copy()
        original_summary = dict(all_discrepancies_result["summary"])
        export_report(all_discrepancies_result, format="json", out_path="reports/x.json")
        pd.testing.assert_frame_equal(all_discrepancies_result["mismatches"], original_mismatches)
        assert all_discrepancies_result["summary"] == original_summary

    def test_all_four_formats_from_same_result(
        self, all_discrepancies_result, tmp_path: Path
    ) -> None:
        """The same reconcile result must serialise cleanly in all four formats."""
        written = []
        for fmt in ["json", "csv", "md", "xlsx"]:
            written.append(
                export_report(all_discrepancies_result, format=fmt, out_path=tmp_path / f"r.{fmt}")
            )
        assert len(written) == 4
        assert all(Path(p).exists() and Path(p).stat().st_size > 0 for p in written)
