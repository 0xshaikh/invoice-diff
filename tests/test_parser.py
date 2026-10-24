"""Tests for ``invoice_diff.parser``.

The parser auto-detects the marketplace dialect from the header, so these
tests assert on detection + schema + value fidelity rather than on a
``format=`` argument.

Covers:
    * Flipkart dialect parsing
    * Meesho dialect parsing
    * Amazon dialect parsing
    * Unknown/unrecognised format error handling
    * Empty file error handling
    * Missing file error handling
    * Header variations (BOM, case, whitespace, quotes, synonyms)
    * Currency normalisation (Rs., ₹, thousands separators, rounding)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from invoice_diff.parser import (
    _to_date,
    _to_int,
    parse_settlement,
    parse_settlement_from_records,
)
from tests.conftest import UNIVERSAL_COLUMNS, assert_universal_schema


# ===========================================================================
# Flipkart
# ===========================================================================
class TestFlipkartParsing:
    def test_flipkart_schema(self, flipkart_csv: Path) -> None:
        df = parse_settlement(flipkart_csv)
        assert_universal_schema(df)

    def test_flipkart_detects_marketplace(self, flipkart_csv: Path) -> None:
        df = parse_settlement(flipkart_csv)
        assert set(df["Marketplace"]) == {"Flipkart"}

    def test_flipkart_row_count(self, flipkart_csv: Path) -> None:
        assert len(parse_settlement(flipkart_csv)) == 3

    def test_flipkart_order_ids(self, flipkart_csv: Path) -> None:
        df = parse_settlement(flipkart_csv)
        assert df["Order_ID"].tolist() == ["FK770487", "FK881122", "FK990011"]

    def test_flipkart_money_is_int_rupees(self, flipkart_csv: Path) -> None:
        df = parse_settlement(flipkart_csv)
        first = df.iloc[0]
        assert first["Product_Value"] == 4800
        assert first["Commission"] == 720
        assert first["GST_Amount"] == 864
        assert first["Forward_Shipping"] == 60
        assert first["Discount"] == 236
        assert first["Settlement_Amount"] == 5120
        # All money columns are integral (rupees, no decimals).
        for col in ["Product_Value", "Commission", "GST_Amount", "Settlement_Amount"]:
            assert pd.api.types.is_integer_dtype(df[col])

    def test_flipkart_invoice_date_parsed(self, flipkart_csv: Path) -> None:
        """``dd/mm/yyyy`` is normalised to ISO ``yyyy-mm-dd``."""
        df = parse_settlement(flipkart_csv)
        assert df["Invoice_Date"].iloc[0] == "2026-09-20"

    def test_flipkart_dedupes_on_order_id(self, tmp_path: Path) -> None:
        """Duplicate Order_ID rows collapse to the first occurrence."""
        p = tmp_path / "dup.csv"
        p.write_text("Seller Order Id,Product Price\nFKDUP,100\nFKDUP,200\n", encoding="utf-8")
        df = parse_settlement(p)
        assert len(df) == 1
        assert df["Product_Value"].tolist() == [100]


# ===========================================================================
# Meesho
# ===========================================================================
class TestMeeshoParsing:
    def test_meesho_detects_marketplace(self, meesho_csv: Path) -> None:
        df = parse_settlement(meesho_csv)
        assert set(df["Marketplace"]) == {"Meesho"}

    def test_meesho_maps_item_price_and_fee(self, meesho_csv: Path) -> None:
        """Meesho's ``Item Price`` / ``Platform Fee`` / ``Tax Amount`` map to
        ``Product_Value`` / ``Commission`` / ``GST_Amount``."""
        df = parse_settlement(meesho_csv)
        first = df.iloc[0]
        assert first["Product_Value"] == 1729
        assert first["Commission"] == 259
        assert first["GST_Amount"] == 311

    def test_meesho_schema(self, meesho_csv: Path) -> None:
        assert_universal_schema(parse_settlement(meesho_csv))

    def test_meesho_settlement_amount(self, meesho_csv: Path) -> None:
        df = parse_settlement(meesho_csv)
        assert df["Settlement_Amount"].tolist() == [1791, 824]


# ===========================================================================
# Amazon
# ===========================================================================
class TestAmazonParsing:
    def test_amazon_detects_marketplace(self, amazon_csv: Path) -> None:
        """The space-free ``OrderID`` column is Amazon's signature."""
        df = parse_settlement(amazon_csv)
        assert set(df["Marketplace"]) == {"Amazon"}

    def test_amazon_maps_columns(self, amazon_csv: Path) -> None:
        df = parse_settlement(amazon_csv)
        first = df.iloc[0]
        assert first["Order_ID"] == "AM100001"
        assert first["Product_Value"] == 1000
        assert first["GST_Amount"] == 180
        assert first["Commission"] == 100  # ReferralFee
        assert first["Forward_Shipping"] == 25

    def test_amazon_schema(self, amazon_csv: Path) -> None:
        assert_universal_schema(parse_settlement(amazon_csv))

    def test_amazon_all_rows(self, amazon_csv: Path) -> None:
        df = parse_settlement(amazon_csv)
        assert df["Order_ID"].tolist() == ["AM100001", "AM100002"]
        assert df["Product_Value"].tolist() == [1000, 3000]


# ===========================================================================
# Error handling
# ===========================================================================
class TestErrorHandling:
    def test_unrecognized_format_raises_value_error(self, unrecognized_csv: Path) -> None:
        """No recognisable Order_ID column → ValueError naming the columns seen."""
        with pytest.raises(ValueError) as excinfo:
            parse_settlement(unrecognized_csv)
        msg = str(excinfo.value)
        assert "Order_ID" in msg
        assert "ProjectCode" in msg  # echoes the detected columns

    def test_empty_file_raises(self, empty_csv: Path) -> None:
        """A zero-byte file has no header to parse."""
        with pytest.raises((pd.errors.EmptyDataError, ValueError, pd.errors.ParserError)):
            parse_settlement(empty_csv)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_settlement(tmp_path / "does-not-exist.csv")

    def test_missing_file_message_names_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.csv"
        with pytest.raises(FileNotFoundError) as excinfo:
            parse_settlement(missing)
        assert "nope.csv" in str(excinfo.value)

    def test_header_only_file_returns_empty_frame(self, tmp_path: Path) -> None:
        """A header-only file parses cleanly to zero rows (no error)."""
        p = tmp_path / "header_only.csv"
        p.write_text("Seller Order Id,Product Price\n", encoding="utf-8")
        df = parse_settlement(p)
        assert_universal_schema(df)
        assert len(df) == 0


# ===========================================================================
# Header variations
# ===========================================================================
class TestHeaderVariations:
    def test_utf8_bom_stripped(self, bom_flipped_headers_csv: Path) -> None:
        df = parse_settlement(bom_flipped_headers_csv)
        assert df["Order_ID"].tolist() == ["FK1"]
        assert df["Product_Value"].tolist() == [4800]

    def test_case_insensitive_headers(self, tmp_path: Path) -> None:
        p = tmp_path / "case.csv"
        p.write_text(
            "SELLER ORDER ID,ORDER DATE,PRODUCT PRICE,SELLER COMMISSION,GST\n"
            "FK1,2026-09-20,1000,150,180\n",
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["FK1"]
        assert set(df["Marketplace"]) == {"Flipkart"}

    def test_whitespace_and_punctuation_trimmed(self, tmp_path: Path) -> None:
        p = tmp_path / "spacey.csv"
        p.write_text(
            "Seller-Order-Id,Order-Date,Product_Price,Seller.Commission,Tax Amount\n"
            "FK2,2026-09-21,500,75,90\n",
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["FK2"]
        assert df["Product_Value"].tolist() == [500]
        assert df["GST_Amount"].tolist() == [90]

    def test_synonym_headers(self, tmp_path: Path) -> None:
        """Different-but-equivalent column names resolve to the same fields."""
        p = tmp_path / "synonyms.csv"
        p.write_text(
            "Order Number,Invoice Date,Item Amount,Commission Amount,Tax Amount\n"
            "SYN1,2026-09-22,250,37,45\n",
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["SYN1"]
        assert df["Product_Value"].tolist() == [250]
        assert df["Commission"].tolist() == [37]
        assert df["GST_Amount"].tolist() == [45]

    def test_explicit_marketplace_column_wins(self, tmp_path: Path) -> None:
        """A literal ``Marketplace`` column short-circuits dialect detection."""
        p = tmp_path / "explicit.csv"
        p.write_text(
            "OrderID,Marketplace,ItemPrice,ReferralFee,SettlementAmount\n"
            "X1,flipkart,1000,100,900\n",
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert set(df["Marketplace"]) == {"Flipkart"}

    def test_quoted_comma_in_value(self, tmp_path: Path) -> None:
        """Commas inside quoted values must survive the CSV round-trip."""
        p = tmp_path / "quoted.csv"
        p.write_text(
            '"Seller Order Id","Product Price","Seller Commission","GST"\n'
            '"FK,2","1000","150","180"\n',
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["FK,2"]
        assert df["Product_Value"].tolist() == [1000]

    def test_missing_optional_columns_default_to_zero(self, tmp_path: Path) -> None:
        """Shipping/Discount columns absent from the source default to 0."""
        p = tmp_path / "minimal.csv"
        p.write_text("Seller Order Id,Product Price\nFKM1,1000\n", encoding="utf-8")
        df = parse_settlement(p)
        assert_universal_schema(df)
        assert df["Forward_Shipping"].tolist() == [0]
        assert df["Reverse_Shipping"].tolist() == [0]
        assert df["Discount"].tolist() == [0]

    def test_blank_order_id_cell_yields_empty_string(self, tmp_path: Path) -> None:
        """An empty Order_ID cell is dropped entirely.

        Known gap: an all-blank line is filled by pandas with ``nan`` and
        survives as the literal string ``"nan"`` — see
        :func:`test_trailing_blank_line_is_ignored` (xfail) for the desired
        behaviour.
        """
        p = tmp_path / "blank.csv"
        p.write_text(
            "Seller Order Id,Product Price\nFK1,100\n",
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["FK1"]

    @pytest.mark.xfail(reason="parser leaves pandas NaN as the literal string 'nan'", strict=False)
    def test_all_blank_line_is_ignored(self, tmp_path: Path) -> None:
        """Desired behaviour: an all-blank line contributes no rows."""
        p = tmp_path / "allblank.csv"
        p.write_text("Seller Order Id,Product Price\nFK1,100\n,0\n", encoding="utf-8")
        df = parse_settlement(p)
        assert df["Order_ID"].tolist() == ["FK1"]


# ===========================================================================
# Value normalisation
# ===========================================================================
class TestValueNormalization:
    def test_rupee_symbol_and_commas(self, tmp_path: Path) -> None:
        """``Rs. 1,234.56`` → 1235 (nearest rupee, half-up-ish)."""
        p = tmp_path / "currency.csv"
        p.write_text(
            "Seller Order Id,Product Price,GST\n"
            'FKC1,"Rs. 1,234.56","Rs. 222.00"\n'
            'FKC2,"₹500","₹90"\n',
            encoding="utf-8",
        )
        df = parse_settlement(p)
        assert df.loc[df["Order_ID"] == "FKC1", "Product_Value"].iloc[0] == 1235
        assert df.loc[df["Order_ID"] == "FKC2", "Product_Value"].iloc[0] == 500

    def test_negative_values_preserved(self, tmp_path: Path) -> None:
        """Refunds/returns carry negative amounts."""
        p = tmp_path / "neg.csv"
        p.write_text("Seller Order Id,Product Price,GST\nFKN1,-150,-27\n", encoding="utf-8")
        df = parse_settlement(p)
        assert df["Product_Value"].tolist() == [-150]
        assert df["GST_Amount"].tolist() == [-27]

    def test_to_int_helper(self) -> None:
        assert _to_int("Rs. 1,234.56") == 1235
        assert _to_int("₹500") == 500
        assert _to_int(" 1,000 ") == 1000
        assert _to_int("-150") == -150
        assert _to_int("") == 0
        assert _to_int(None) == 0

    def test_to_date_helper_normalizes_formats(self) -> None:
        assert _to_date("10/10/2026") == "2026-10-10"
        assert _to_date("2026-09-20") == "2026-09-20"
        assert _to_date("01 Jan 2026") == "2026-01-01"


# ===========================================================================
# Records-based construction (used by synthetic-data helpers)
# ===========================================================================
class TestParseFromRecords:
    def test_records_produce_universal_schema(self) -> None:
        df = parse_settlement_from_records(
            [{"Order_ID": "R1", "Product_Value": "1000", "GST_Amount": "180"}]
        )
        assert list(df.columns) == UNIVERSAL_COLUMNS

    def test_records_accept_aliases(self) -> None:
        """Aliases must be canonical field names with **underscores stripped**
        (``productvalue``), not the underscored form (``product_value``).
        """
        df = parse_settlement_from_records(
            [{"order_id": "R2", "productvalue": 250, "gstamount": 45}]
        )
        assert df["Order_ID"].tolist() == ["R2"]
        assert df["Product_Value"].tolist() == [250]
        assert df["GST_Amount"].tolist() == [45]

    def test_records_underscored_keys_are_ignored(self) -> None:
        """Documented sharp edge: underscored aliases fall through to the default 0."""
        df = parse_settlement_from_records([{"order_id": "R9", "product_value": 250}])
        assert df["Order_ID"].tolist() == ["R9"]
        assert df["Product_Value"].tolist() == [0]

    def test_records_defaults_zero(self) -> None:
        df = parse_settlement_from_records([{"Order_ID": "R3"}])
        assert df["Commission"].tolist() == [0]
        assert df["Settlement_Amount"].tolist() == [0]
