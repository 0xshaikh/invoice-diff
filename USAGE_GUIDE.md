# Usage Guide — invoice-diff

A step-by-step walkthrough from a clean machine to a finished reconciliation
report. The short version is three commands:

```bash
pip install invoice-diff
python generate_sample_data.py
invoice-diff reconcile -s samples/flipkart_settlement.csv \
                       -e samples/flipkart_orders_expected.csv \
                       -f md -o reports/flipkart.md
```

Everything below expands on that.

## 1. Install

```bash
# Prereqs: Python 3.10+
python --version   # 3.10, 3.11, or 3.12

# From PyPI
pip install invoice-diff

# Or from source (developers)
git clone https://github.com/0xshaikh/invoice-diff.git
cd invoice-diff
pip install -e ".[dev]"
```

Verify:

```bash
invoice-diff --version
# invoice-diff 0.1.0
```

## 2. Generate sample data

```bash
python generate_sample_data.py
ls samples/
```

Writes:

| File | Contents |
|------|----------|
| `samples/flipkart_orders_expected.csv` | 100 expected orders (the "truth") |
| `samples/flipkart_settlement.csv` | 99 settlement rows with **planted discrepancies**: 2 missing, 1 extra, 2 value, 3 GST, 1 commission |
| `samples/meesho_settlement.csv` | 50 Meesho-dialect orders |

The generator always writes into the `samples/` directory next to itself —
there is no output-directory flag. Point your `--settlement`/`--expected`
flags at those paths, or copy the files out and anonymise them.

## 3. Parse a settlement

`parse` prints a human summary and the first 5 normalised rows — a cheap way
to confirm the dialect was detected correctly before you reconcile:

```bash
invoice-diff parse --input samples/flipkart_settlement.csv
```

```
Parsed 99 orders from samples/flipkart_settlement.csv
  Marketplace:     Flipkart
  Date range:      2026-09-01 to 2026-09-26
  Total Product:   Rs.543,930
  Total Commission:Rs.95,690
  Total GST:       Rs.97,908
  Total Settlement:Rs.566,735
```

There is **no `--format` flag**: the dialect is auto-detected from the header
(Flipkart by `Seller Order Id` / `Seller Commission`, Meesho by
`Item Price` / `Platform Fee`, Amazon by a space-free `OrderID` column, or an
explicit `Marketplace` column if present).

Check the CSV is internally consistent before reconciling:

```bash
invoice-diff check --settlement samples/flipkart_settlement.csv
```

`check` reports missing dates, missing order IDs, negative amounts, and
settlement arithmetic drift (rows where `Settlement_Amount` ≠
`Product − Commission − Shipping + Discount + GST` by more than Rs.1).

## 4. Reconcile against expected

```bash
invoice-diff reconcile \
    --settlement samples/flipkart_settlement.csv \
    --expected   samples/flipkart_orders_expected.csv \
    --format md \
    --out reports/flipkart_2026-09.md
```

The CLI does four things internally:

1. `parse_settlement(settlement_csv)` → universal schema.
2. Read `expected` **raw**, then `_normalize_expected` → same schema. Column
   names are fuzzy-matched (`Seller Order Id`, `Product Price`,
   `Seller Commission`, `GST` all resolve correctly), so your own order
   export usually works unchanged.
3. `reconcile(settlement, expected)` → `{"mismatches", "summary"}`.
4. `export_report(result, format, out)` → file.

### `reconcile` options

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--settlement`, `-s` | yes | — | Settlement CSV. |
| `--expected`, `-e` | yes | — | Expected order report CSV. |
| `--format`, `-f` | no | `json` | `json`, `csv`, `md`, or `xlsx`. |
| `--out`, `-o` | no | `reports/report_<format>` | Output path; parent dirs are created. |

**Exit codes matter for automation:**

| Code | Meaning |
|------|---------|
| `0` | Clean — no discrepancies found. |
| `1` | Discrepancies found (this is *not* a crash). |
| `2` | Input error: file missing, undetectable columns, bad format. |

⚠️ **Library users:** if you call `reconcile()` directly, pass
**normalised** frames on both sides. `_ensure_fields` silently fills a missing
`Order_ID` column with `0`, so a raw marketplace CSV handed into `expected`
will report every order as `EXTRA_IN_SETTLEMENT`. Run your ledger through
`invoice_diff.cli._normalize_expected` first, as the CLI does.

## 5. Export in multiple formats

Re-run `reconcile` with a different `--format` — the reconciliation is cheap:

```bash
invoice-diff reconcile -s s.csv -e e.csv -f json -o reports/diff.json   # dashboards, CI artefacts
invoice-diff reconcile -s s.csv -e e.csv -f csv  -o reports/diff.csv    # finance spreadsheets
invoice-diff reconcile -s s.csv -e e.csv -f md   -o reports/diff.md     # Slack / GitHub / audit decks
invoice-diff reconcile -s s.csv -e e.csv -f xlsx -o reports/diff.xlsx   # finance teams (2 styled sheets)
```

Format notes:

- **JSON** — `{"generated_at", "summary", "mismatches"}`; best for
  scripting further.
- **CSV** — a `# key,value` summary comment block, then the mismatch table.
- **MD** — title, summary table, mismatch rows. `_No discrepancies found._`
  when clean.
- **XLSX** — `Summary` sheet (discrepancy metrics highlighted red / green)
  plus an `All Mismatches` sheet.

There is no separate `export` subcommand — re-running `reconcile` with a new
`--format` is the intended workflow.

## 6. Handle real Flipkart / Meesho / Amazon CSVs

Drop your real file in place of the sample and keep the same command:

```bash
invoice-diff reconcile \
    --settlement flipkart_settlement_2026-09.csv \
    --expected   my_orders_2026-09.csv \
    --format xlsx --out reports/flipkart.xlsx

invoice-diff reconcile \
    --settlement meesho_settlement_2026-09.csv \
    --expected   my_orders_2026-09.csv \
    --format md --out reports/meesho.md
```

Expected-ledger column names recognised (fuzzy-matched, case-insensitive):

| Universal field | Accepted source names |
|-----------------|-----------------------|
| `Order_ID`        | `Seller Order Id`, `Order ID`, `OrderID`, `Order Number`, `Order#` |
| `Product_Value`   | `Product Price`, `Item Price`, `Price`, `MRP`, `Sale Price`, `Price Per Unit` |
| `Commission`      | `Seller Commission`, `Commission`, `Platform Fee`, `Referral Fee`, `Platform Charges` |
| `GST_Amount`      | `GST`, `Tax`, `Tax Amount`, `IGST`, `Total Tax` |

Money strings like `Rs. 1,234.56` or `₹500` are parsed to whole rupees; dates
in `dd/mm/yyyy`, `yyyy-mm-dd`, or `dd Mon yyyy` all normalise to ISO. If your
ledger has none of the recognised order-ID column names, `reconcile` fails
loudly with `Error: Expected report has no recognizable Order_ID column`.

## 7. Automate in CI

Because `reconcile` exits `1` on discrepancies and `2` on input errors, it
doubles as a CI gate:

```yaml
name: daily-reconciliation
on:
  schedule:
    - cron: "0 7 * * 1-5"   # 07:00 UTC Mon–Fri
  workflow_dispatch:

jobs:
  reconcile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install invoice-diff
      - name: Reconcile (upload report, do not fail on discrepancies)
        continue-on-error: true
        run: |
          mkdir -p reports
          invoice-diff reconcile \
            --settlement artifacts/settlement.csv \
            --expected   artifacts/expected.csv \
            --format xlsx --out reports/reconciliation.xlsx
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: reconciliation-report
          path: reports/
```

To make discrepancies **fail the build**, drop `continue-on-error`:

```yaml
      - name: Reconcile (must be clean)
        run: invoice-diff reconcile -s s.csv -e e.csv -f json -o reports/diff.json
```

A local pre-push gate via the Makefile:

```bash
make sample
make test
```
