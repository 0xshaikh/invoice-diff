"""Tests for ``invoice_diff.reconciler``.

``reconcile(settlement, expected)`` returns ``{"mismatches": DataFrame, "summary": dict}``.
Each mismatch row carries an ``Order_ID``, a ``Type`` (one of the four primary
discrepancy constants), ``Expected_Value`` / ``Settlement_Value`` /
``Difference``, and a human ``Note``.

Covers:
    * Clean match — no discrepancies
    * MISSING_IN_SETTLEMENT
    * EXTRA_IN_SETTLEMENT
    * VALUE_MISMATCH (including the rupee-tolerance boundary)
    * GST_MISMATCH
    * COMMISSION_MISMATCH and ROUNDED_OFF (bonus types present in the core)
    * Multiple discrepancy types in a single run
    * Summary counters
    * Column/ID normalisation edge cases
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from invoice_diff.parser import parse_settlement
from invoice_diff.reconciler import (
    COMMISSION_MISMATCH,
    EXTRA_IN_SETTLEMENT,
    GST_MISMATCH,
    MISSING_IN_SETTLEMENT,
    ROUNDED_OFF,
    TOLERANCE_RUPEES,
    VALUE_MISMATCH,
    reconcile,
)
from tests.conftest import MISMATCH_COLUMNS, result_types


# ---------------------------------------------------------------------------
# Helpers to build minimal valid frames.
# ---------------------------------------------------------------------------
def _settlement(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal settlement frame with every money field defaulted to 0."""
    return pd.DataFrame(
        [
            {
                "Order_ID": r["Order_ID"],
                "Product_Value": r.get("Product_Value", 0),
                "Commission": r.get("Commission", 0),
                "GST_Amount": r.get("GST_Amount", 0),
            }
            for r in rows
        ],
        columns=["Order_ID", "Product_Value", "Commission", "GST_Amount"],
    )


def _expected(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal expected frame with every money field defaulted to 0."""
    return pd.DataFrame(
        [
            {
                "Order_ID": r["Order_ID"],
                "Product_Value": r.get("Product_Value", 0),
                "Commission": r.get("Commission", 0),
                "GST_Amount": r.get("GST_Amount", 0),
            }
            for r in rows
        ],
        columns=["Order_ID", "Product_Value", "Commission", "GST_Amount"],
    )


# ===========================================================================
# Clean match
# ===========================================================================
class TestCleanMatch:
    def test_identical_frames_have_no_discrepancies(self, clean_result) -> None:
        assert len(clean_result["mismatches"]) == 0
        assert clean_result["summary"]["total_discrepancies"] == 0

    def test_summary_counts_all_match(self, clean_result) -> None:
        s = clean_result["summary"]
        assert s["matched"] == 3
        assert s["missing_in_settlement"] == 0
        assert s["extra_in_settlement"] == 0
        assert s["value_mismatch_count"] == 0
        assert s["gst_mismatch_count"] == 0
        assert s["commission_mismatch_count"] == 0
        assert s["rounded_off_count"] == 0

    def test_empty_mismatches_still_has_columns(self, clean_result) -> None:
        """An empty result must retain its schema so exporters can iterate."""
        assert list(clean_result["mismatches"].columns) == MISMATCH_COLUMNS

    def test_reconcile_returns_dict_shape(self, clean_result) -> None:
        assert set(clean_result.keys()) == {"mismatches", "summary"}
        assert isinstance(clean_result["mismatches"], pd.DataFrame)
        assert isinstance(clean_result["summary"], dict)

    def test_fully_empty_inputs(self) -> None:
        s = pd.DataFrame(columns=["Order_ID", "Product_Value", "Commission", "GST_Amount"])
        result = reconcile(s, s.copy())
        assert len(result["mismatches"]) == 0
        assert result["summary"]["total_orders_in_settlement"] == 0

    def test_missing_columns_default_to_zero(self) -> None:
        """Expected frames without Commission/GST must not crash the compare."""
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 100}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 100}])
        result = reconcile(settlement, expected)
        assert len(result["mismatches"]) == 0


# ===========================================================================
# MISSING_IN_SETTLEMENT
# ===========================================================================
class TestMissingInSettlement:
    def test_missing_order_flagged(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 100}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 100}])
        extra = _expected([{"Order_ID": "B", "Product_Value": 500}])
        result = reconcile(settlement, pd.concat([expected, extra], ignore_index=True))

        assert MISSING_IN_SETTLEMENT in result_types(result)
        row = result["mismatches"][result["mismatches"]["Type"] == MISSING_IN_SETTLEMENT].iloc[0]
        assert row["Order_ID"] == "B"

    def test_missing_carries_expected_value_not_settlement(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 100}])
        expected = _expected([{"Order_ID": "B", "Product_Value": 500}])
        result = reconcile(settlement, expected)

        row = result["mismatches"].iloc[0]
        assert row["Type"] == MISSING_IN_SETTLEMENT
        assert row["Expected_Value"] == 500
        assert row["Settlement_Value"] == 0
        assert row["Difference"] == 500

    def test_missing_note_describes_it(self) -> None:
        result = reconcile(
            _settlement([]),
            _expected([{"Order_ID": "GONE", "Product_Value": 250}]),
        )
        assert "absent" in result["mismatches"].iloc[0]["Note"].lower()

    def test_multiple_missing_orders(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 100}])
        expected = _expected([
            {"Order_ID": "B", "Product_Value": 100},
            {"Order_ID": "C", "Product_Value": 200},
            {"Order_ID": "D", "Product_Value": 300},
        ])
        result = reconcile(settlement, expected)
        assert result["summary"]["missing_in_settlement"] == 3
        missing_ids = set(
            result["mismatches"].loc[
                result["mismatches"]["Type"] == MISSING_IN_SETTLEMENT, "Order_ID"
            ]
        )
        assert missing_ids == {"B", "C", "D"}


# ===========================================================================
# EXTRA_IN_SETTLEMENT
# ===========================================================================
class TestExtraInSettlement:
    def test_extra_order_flagged(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 100}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 100}])
        extra = _settlement([{"Order_ID": "Z", "Product_Value": 780}])
        result = reconcile(pd.concat([settlement, extra], ignore_index=True), expected)

        assert EXTRA_IN_SETTLEMENT in result_types(result)
        row = result["mismatches"][result["mismatches"]["Type"] == EXTRA_IN_SETTLEMENT].iloc[0]
        assert row["Order_ID"] == "Z"

    def test_extra_carries_settlement_value(self) -> None:
        settlement = _settlement([{"Order_ID": "Z", "Product_Value": 780}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 100}])
        result = reconcile(settlement, expected)

        row = result["mismatches"][result["mismatches"]["Type"] == EXTRA_IN_SETTLEMENT].iloc[0]
        assert row["Expected_Value"] == 0
        assert row["Settlement_Value"] == 780
        assert row["Difference"] == 780

    def test_extra_note_describes_it(self) -> None:
        result = reconcile(
            _settlement([{"Order_ID": "X", "Product_Value": 10}]),
            _expected([{"Order_ID": "A", "Product_Value": 10}]),
        )
        note = result["mismatches"].loc[
            result["mismatches"]["Type"] == EXTRA_IN_SETTLEMENT, "Note"
        ].iloc[0]
        assert "not in expected" in note.lower()


# ===========================================================================
# VALUE_MISMATCH
# ===========================================================================
class TestValueMismatch:
    def test_value_differs_beyond_tolerance(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 900}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000}])
        result = reconcile(settlement, expected)

        assert VALUE_MISMATCH in result_types(result)
        row = result["mismatches"][result["mismatches"]["Type"] == VALUE_MISMATCH].iloc[0]
        assert row["Expected_Value"] == 1000
        assert row["Settlement_Value"] == 900
        assert row["Difference"] == -100

    def test_tolerance_boundary(self) -> None:
        """Difference exactly equal to ``TOLERANCE_RUPEES`` is NOT a mismatch."""
        tol = TOLERANCE_RUPEES
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000 - tol}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000}])
        result = reconcile(settlement, expected)
        # |diff| == tol is not > tol → no VALUE_MISMATCH, only ROUNDED_OFF.
        assert VALUE_MISMATCH not in result_types(result)
        assert result["summary"]["value_mismatch_count"] == 0

    def test_just_over_tolerance_flagged(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000 - TOLERANCE_RUPEES - 1}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000}])
        result = reconcile(settlement, expected)
        assert VALUE_MISMATCH in result_types(result)
        assert result["summary"]["value_mismatch_count"] == 1

    def test_exact_match_no_mismatch(self) -> None:
        row = {"Order_ID": "A", "Product_Value": 1000}
        result = reconcile(_settlement([row]), _expected([row]))
        assert result["summary"]["value_mismatch_count"] == 0

    def test_value_mismatch_amount_accumulates(self) -> None:
        settlement = _settlement([
            {"Order_ID": "A", "Product_Value": 900},
            {"Order_ID": "B", "Product_Value": 800},
        ])
        expected = _expected([
            {"Order_ID": "A", "Product_Value": 1000},
            {"Order_ID": "B", "Product_Value": 1000},
        ])
        result = reconcile(settlement, expected)
        assert result["summary"]["value_mismatch_amount"] == 300

    def test_value_note_mentions_rupees(self) -> None:
        result = reconcile(
            _settlement([{"Order_ID": "A", "Product_Value": 900}]),
            _expected([{"Order_ID": "A", "Product_Value": 1000}]),
        )
        note = result["mismatches"].iloc[0]["Note"]
        assert "100" in note


# ===========================================================================
# GST_MISMATCH
# ===========================================================================
class TestGstMismatch:
    def test_gst_differs_flagged(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 300}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 360}])
        result = reconcile(settlement, expected)

        assert GST_MISMATCH in result_types(result)
        row = result["mismatches"][result["mismatches"]["Type"] == GST_MISMATCH].iloc[0]
        assert row["Expected_Value"] == 360
        assert row["Settlement_Value"] == 300
        assert row["Difference"] == -60

    def test_gst_zero_difference_not_flagged(self) -> None:
        row = {"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 180}
        result = reconcile(_settlement([row]), _expected([row]))
        assert GST_MISMATCH not in result_types(result)
        assert result["summary"]["gst_mismatch_count"] == 0

    def test_gst_mismatch_amount_accumulates(self) -> None:
        settlement = _settlement([
            {"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 300},
            {"Order_ID": "B", "Product_Value": 1000, "GST_Amount": 200},
        ])
        expected = _expected([
            {"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 360},
            {"Order_ID": "B", "Product_Value": 1000, "GST_Amount": 140},
        ])
        result = reconcile(settlement, expected)
        assert result["summary"]["gst_mismatch_count"] == 2
        assert result["summary"]["gst_mismatch_amount"] == 120

    def test_gst_still_compared_when_product_value_matches(self) -> None:
        """A value match must not suppress the independent GST comparison."""
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 100}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 180}])
        result = reconcile(settlement, expected)
        assert result["summary"]["value_mismatch_count"] == 0
        assert result["summary"]["gst_mismatch_count"] == 1

    def test_gst_negative_difference_preserved(self) -> None:
        """GST credits (refunds) surface as negative differences."""
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": -27}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 0}])
        result = reconcile(settlement, expected)
        row = result["mismatches"].iloc[0]
        assert row["Type"] == GST_MISMATCH
        assert row["Difference"] == -27

    def test_gst_note_mentions_platform(self) -> None:
        result = reconcile(
            _settlement([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 100}]),
            _expected([{"Order_ID": "A", "Product_Value": 1000, "GST_Amount": 180}]),
        )
        assert "gst" in result["mismatches"].iloc[0]["Note"].lower()


# ===========================================================================
# Commission + rounding (secondary types present in the core)
# ===========================================================================
class TestSecondaryTypes:
    def test_commission_mismatch(self) -> None:
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000, "Commission": 100}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000, "Commission": 150}])
        result = reconcile(settlement, expected)
        assert COMMISSION_MISMATCH in result_types(result)
        assert result["summary"]["commission_mismatch_count"] == 1

    def test_sub_rupee_drift_is_rounded_off(self) -> None:
        """A non-zero difference within tolerance is classified ROUNDED_OFF."""
        settlement = _settlement([{"Order_ID": "A", "Product_Value": 1000 - 1}])
        expected = _expected([{"Order_ID": "A", "Product_Value": 1000}])
        result = reconcile(settlement, expected)
        types = result_types(result)
        assert ROUNDED_OFF in types
        assert VALUE_MISMATCH not in types
        assert result["summary"]["rounded_off_count"] == 1


# ===========================================================================
# Multiple discrepancy types at once
# ===========================================================================
class TestMultipleDiscrepancies:
    def test_all_four_primary_types_in_one_run(self, all_discrepancies_result) -> None:
        types = set(all_discrepancies_result["mismatches"]["Type"])
        assert {
            MISSING_IN_SETTLEMENT,
            EXTRA_IN_SETTLEMENT,
            VALUE_MISMATCH,
            GST_MISMATCH,
        } <= types

    def test_summary_total_discrepancies_matches_rows(self, all_discrepancies_result) -> None:
        result = all_discrepancies_result
        assert result["summary"]["total_discrepancies"] == len(result["mismatches"])

    def test_summary_components_add_up(self, all_discrepancies_result) -> None:
        s = all_discrepancies_result["summary"]
        assert s["total_orders_in_settlement"] == 4  # 3 from CSV + FKEXTRA
        assert s["total_orders_in_expected"] == 4  # 3 matched/diffed + FK999999 missing
        assert s["matched"] == 3
        assert s["missing_in_settlement"] == 1
        assert s["extra_in_settlement"] == 1
        assert s["value_mismatch_count"] == 1
        assert s["gst_mismatch_count"] == 1

    def test_mismatch_schema_preserved(self, all_discrepancies_result) -> None:
        assert list(all_discrepancies_result["mismatches"].columns) == MISMATCH_COLUMNS

    def test_discrepancy_order_ids_present(self, all_discrepancies_result) -> None:
        ids = set(all_discrepancies_result["mismatches"]["Order_ID"])
        assert {"FKEXTRA", "FK999999", "FK770487", "FK990011"} <= ids

    def test_reconcile_is_pure(self, flipkart_csv: Path) -> None:
        """Inputs must not be mutated in place."""
        settlement = parse_settlement(flipkart_csv)
        expected = pd.DataFrame(
            [{"Order_ID": "FK770487", "Product_Value": 1}]
        )
        settlement_before = settlement.copy()
        expected_before = expected.copy()
        reconcile(settlement, expected)
        pd.testing.assert_frame_equal(settlement, settlement_before)
        pd.testing.assert_frame_equal(expected, expected_before)


# ===========================================================================
# Contract: reconcile requires normalised inputs
# ===========================================================================
class TestRequiresNormalizedInputs:
    """``reconcile`` is a *comparison* primitive, not a *parsing* one.

    Both frames must already carry ``Order_ID`` / ``Product_Value`` /
    ``Commission`` / ``GST_Amount``.  Feeding a raw marketplace CSV into
    ``expected`` silently injects ``Order_ID = 0`` for every row, which the
    CLI avoids by calling ``_normalize_expected`` first.
    """

    def test_raw_expected_csv_must_be_normalized_first(
        self, flipkart_csv: Path, expected_orders_flipkart: Path
    ) -> None:
        from invoice_diff.cli import _normalize_expected

        settlement = parse_settlement(flipkart_csv)
        raw = pd.read_csv(expected_orders_flipkart)

        # Bug surface: raw expected injects Order_ID = 0 and hides the matches.
        naive = reconcile(settlement, raw)
        assert naive["summary"]["matched"] == 0

        # Correct path: normalise, then everything matches.
        correct = reconcile(settlement, _normalize_expected(raw))
        assert correct["summary"]["matched"] == 3
        assert len(correct["mismatches"]) == 0

    def test_normalize_expected_rejects_frames_without_order_id(self) -> None:
        from invoice_diff.cli import _normalize_expected

        with pytest.raises(ValueError) as excinfo:
            _normalize_expected(pd.DataFrame({"Foo": [1], "Bar": [2]}))
        assert "Order_ID" in str(excinfo.value)

    def test_normalize_expected_handles_missing_money_columns(self) -> None:
        from invoice_diff.cli import _normalize_expected

        normalized = _normalize_expected(
            pd.DataFrame({"Seller Order Id": ["FK1"], "Product Price": [1000]})
        )
        assert normalized["Order_ID"].tolist() == ["FK1"]
        assert normalized["Product_Value"].tolist() == [1000]
        assert normalized["Commission"].tolist() == [0]
        assert normalized["GST_Amount"].tolist() == [0]


# ===========================================================================
# Input normalisation
# ===========================================================================
class TestInputNormalization:
    def test_order_id_dtype_coerced_to_string(self) -> None:
        """Integer-like Order_IDs should still join correctly."""
        settlement = _settlement([{"Order_ID": 12345, "Product_Value": 100}])
        expected = _expected([{"Order_ID": "12345", "Product_Value": 100}])
        result = reconcile(settlement, expected)
        assert result["summary"]["matched"] == 1
        assert len(result["mismatches"]) == 0

    def test_duplicate_order_ids_do_not_crash(self) -> None:
        settlement = _settlement([
            {"Order_ID": "A", "Product_Value": 100},
            {"Order_ID": "A", "Product_Value": 200},
        ])
        expected = _expected([{"Order_ID": "A", "Product_Value": 100}])
        result = reconcile(settlement, expected)
        assert result["summary"]["total_orders_in_settlement"] == 1

    def test_case_and_whitespace_of_order_ids(self) -> None:
        """Reconciliation is exact on Order_ID — differing case means a miss."""
        settlement = _settlement([{"Order_ID": "fk100", "Product_Value": 100}])
        expected = _expected([{"Order_ID": "FK100", "Product_Value": 100}])
        result = reconcile(settlement, expected)
        assert result["summary"]["matched"] == 0
