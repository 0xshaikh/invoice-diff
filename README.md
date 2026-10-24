<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python versions" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License MIT" />
  <img src="https://img.shields.io/github/actions/workflow/status/0xshaikh/invoice-diff/ci.yml?branch=main&label=CI" alt="CI status" />
  <img src="https://img.shields.io/badge/Marketplaces-Flipkart%20%7C%20Meesho%20%7C%20Amazon-success" alt="Marketplaces" />
</p>

<h1 align="center">invoice-diff</h1>

<p align="center">
  <strong>Reconcile marketplace settlement files against your order ledger — flag every missing, extra, or mismatched order.</strong>
</p>

---

## What problem does it solve?

Every Indian marketplace seller reconciles settlement files from Flipkart,
Meesho, and Amazon against the orders they actually issued — usually by hand,
in a spreadsheet, for hours every settlement cycle. `invoice-diff` automates
that loop: it parses the marketplace-specific CSV dialects into one universal
schema, joins them to your expected order report, and emits a typed
discrepancy report (missing orders, extra orders, value drift, GST drift,
commission drift).

It ships opinionated four-format exports (JSON, CSV, Markdown, XLSX) so the
same reconciliation can feed a compliance archive, a finance spreadsheet, a
Slack post, or an audit deck without reformatting. It runs locally — no API
keys, no cloud, no data leaves your machine.

## Install

From PyPI:

```bash
pip install invoice-diff
```

From source:

```bash
git clone https://github.com/0xshaikh/invoice-diff.git
cd invoice-diff
pip install -e ".[dev]"
```

Requires **Python 3.10+**. Dependencies: `pandas`, `numpy`, `openpyxl`.

## Quick start

Three commands from zero to a report:

```bash
# 1. Generate sample data (Flipkart + Meesho settlements, expected ledger)
python generate_sample_data.py

# 2. Sanity-check + preview a settlement
invoice-diff parse --input samples/flipkart_settlement.csv
invoice-diff check --settlement samples/flipkart_settlement.csv

# 3. Reconcile against your expected ledger and export
invoice-diff reconcile \
    --settlement samples/flipkart_settlement.csv \
    --expected   samples/flipkart_orders_expected.csv \
    --format md \
    --out reports/flipkart_2026-09.md
```

Sample output for the bundled sample data:

```
=== Reconciliation Summary ===
  Orders in settlement         99
  Orders in expected           100
  Matched                      98
  Missing in settlement        2
  Extra in settlement          1
  Value mismatches             2
  Value mismatch amount (Rs.)  Rs.350
  GST mismatches               3
  GST mismatch amount (Rs.)    Rs.50
  Commission mismatches        1
  Rounded-off                  0
  Total discrepancies          9
```

## CLI reference

```
invoice-diff [--version] <COMMAND> [OPTIONS]
```

| Command | Purpose |
|---------|---------|
| `parse`     | Parse a settlement CSV; print a summary and the first 5 rows. |
| `reconcile` | Reconcile a settlement against an expected order report; export a report. |
| `check`     | Quick sanity check of a settlement's internal arithmetic. |
| `--version` | Print the version and exit. |

### `parse` — normalise and preview a settlement

```bash
invoice-diff parse --input <SETTLEMENT_CSV>
```

| Flag | Required | Description |
|------|----------|-------------|
| `--input`, `-i` | yes | Path to the marketplace settlement CSV. |

The marketplace is **auto-detected** from the header, so there is no
`--format` flag. Prints order count, detected marketplace, date range, and
totals for product value, commission, GST, and settlement.

### `reconcile` — compare settlement vs. expected and export

```bash
invoice-diff reconcile --settlement <CSV> --expected <CSV> [--format F] [--out PATH]
```

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--settlement`, `-s` | yes | — | Settlement CSV (any supported dialect). |
| `--expected`, `-e`   | yes | — | Expected order report CSV. Column names are fuzzy-matched onto the universal schema. |
| `--format`, `-f`     | no  | `json` | Report format: `json`, `csv`, `md`, or `xlsx`. |
| `--out`, `-o`        | no  | `reports/report_<format>` | Output path (created if missing). |

Exit codes: `0` when the reconciliation is clean, `1` when discrepancies were
found, `2` on input/IO errors. This makes it safe to run in CI.

### `check` — sanity-check settlement arithmetic

```bash
invoice-diff check --settlement <CSV>
```

Reports missing dates, missing order IDs, negative amounts, and settlement
arithmetic drift (rows where `Settlement_Amount` disagrees with
`Product − Commission − Shipping + Discount + GST` by more than Rs.1).

## Supported marketplaces

Detection is header-based and automatic — no dialect flag needed.

| Marketplace | Detected via | Notes |
|-------------|--------------|-------|
| **Flipkart** | `Seller Order Id` / `Seller Commission` / `Settlement Amount` | Handles the standard `Settlement_Statement` export. |
| **Meesho**   | `Item Price` / `Platform Fee` / `Tax Amount` | `Item Price` → `Product_Value`, `Platform Fee` → `Commission`, `Tax Amount` → `GST_Amount`. |
| **Amazon**   | space-free `OrderID` column | Handles the SP-API `flat-file-settlements` report. `ReferralFee` → `Commission`. |
| Any of the above | an explicit `Marketplace` column | A literal `Marketplace`/`Platform`/`Channel` column wins over column-shape heuristics. |

Everything is normalised to one universal schema:

```
Order_ID, Marketplace, Invoice_Date, Product_Value, Commission, GST_Amount,
Forward_Shipping, Reverse_Shipping, Discount, Settlement_Amount
```

Money values are integers in rupees (`"Rs. 1,234.56"` → `1235`). Dates are
normalised to ISO `yyyy-mm-dd` regardless of source format.

## Discrepancy types

Every discrepancy row carries a `Type`:

| Type | Meaning | Severity |
|------|---------|----------|
| `MISSING_IN_SETTLEMENT` | Order present in your expected report but absent from the settlement. | 🔴 High — likely missing payout. |
| `EXTRA_IN_SETTLEMENT`   | Order present in the settlement but absent from your expected report. | 🟠 Medium — fee, credit note, duplicate, or untracked return. |
| `VALUE_MISMATCH`        | `Product_Value` differs by more than Rs.1 (the tolerance). | 🔴 High — rate error or partial settle. |
| `GST_MISMATCH`          | `GST_Amount` differs. | 🟠 Medium — ITC mismatch; check reverse-charge treatment. |
| `COMMISSION_MISMATCH`   | `Commission` differs. | 🟡 Low — commission-rate drift. |
| `ROUNDED_OFF`           | Non-zero difference **within** the Rs.1 tolerance. | ⚪ Info — harmless rounding drift. |

Each row also carries `Order_ID`, `Expected_Value`, `Settlement_Value`,
`Difference`, and a human-readable `Note`.

## Sample output

A Markdown report:

```markdown
# Invoice Reconciliation Report

Generated: 2026-10-24T01:45:13Z

## Summary

| Metric | Value |
|---|---:|
| Orders in settlement | 99 |
| Orders in expected | 100 |
| Matched | 98 |
| Missing in settlement | 2 |
| Extra in settlement | 1 |
| Value mismatches | 2 |
| Total discrepancies | 9 |
```

The XLSX report writes two sheets: a styled **Summary** (discrepancy rows
highlighted red) and **All Mismatches**.

## How it works

```
┌──────────────┐     ┌──────────────┐
│ Marketplace  │     │  Order ledger │
│ settlement   │     │  CSV (any     │
│ CSV          │     │  dialect)     │
└──────┬───────┘     └──────┬───────┘
       │ parse_settlement   │ _normalize_expected
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│ universal    │     │ universal    │
│ schema       │     │ schema       │
└──────┬───────┘     └──────┬───────┘
       └───────────┬────────┘
                   ▼
        ┌────────────────────┐
        │  reconcile         │
        │  • set diff on     │
        │    Order_ID        │
        │  • value/GST/comm  │
        │    compare         │
        └────────┬───────────┘
                 ▼
        ┌────────────────────┐
        │  {"mismatches",    │
        │   "summary"}       │
        └────────┬───────────┘
                 ▼
        ┌────────────────────┐
        │  export_report     │
        │  json/csv/md/xlsx  │
        └────────────────────┘
```

**Important contract:** `reconcile()` compares two *already-normalised*
frames. The CLI normalises the expected ledger for you via
`_normalize_expected`; if you call the library directly, do the same — passing
a raw marketplace CSV into `expected` silently injects `Order_ID = 0` and
masks every match.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md). Highlights:

- Python 3.10+ only (no 3.9 syntax, no 3.13-only features).
- `make lint && make test` must pass before opening a PR.
- New marketplace dialects must ship with a golden test + sample data.
- User-visible changes go in `CHANGELOG.md` under `## [Unreleased]`.

## License

[MIT](LICENSE) — Anas Shaikh, 2026.

## Author

**Anas Shaikh** — [github.com/0xshaikh](https://github.com/0xshaikh)

---

<p align="center"><sub>Built for sellers who refuse to reconcile by hand.</sub></p>
