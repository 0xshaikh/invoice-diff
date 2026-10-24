# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-24

### Added

- **Initial public release** of `invoice-diff`, a reconciliation engine for
  marketplace settlement files.
- **CSV parsers** for three marketplaces:
  - Flipkart settlements
  - Meesho settlements
  - Amazon (SP-API / seller reports) settlements
- **Reconciler engine** producing six discrepancy types:
  - `MISSING_IN_SETTLEMENT` — an expected order never reached the settlement.
  - `EXTRA_IN_SETTLEMENT` — a settlement row has no matching expected order.
  - `VALUE_MISMATCH` — product value differs by more than the Rs.1 tolerance.
  - `GST_MISMATCH` — GST/tax amounts differ.
  - `COMMISSION_MISMATCH` — commission/fee amounts differ.
  - `ROUNDED_OFF` — sub-rupee drift within tolerance (informational).
- **Report exporter** supporting four output formats: JSON, CSV, Markdown,
  and Excel (XLSX).
- **CLI** (`invoice-diff`) with `parse`, `reconcile`, and `check` subcommands;
  marketplace dialects are auto-detected from the CSV header.
- **Sample data generator** (`generate_sample_data.py`) for onboarding new
  users.
- Comprehensive test suite covering parser, reconciler, and exporter modules.
- CI/CD via GitHub Actions (Python 3.10, 3.11, 3.12 matrix).

### Documentation

- README with install, quick-start, CLI reference, and marketplace support.
- USAGE_GUIDE for step-by-step walkthroughs.
- CONTRIBUTING, SECURITY, and CODE_OF_CONDUCT.
- GitHub issue and PR templates.

[0.1.0]: https://github.com/0xshaikh/invoice-diff/releases/tag/v0.1.0

## [Unreleased]

### Added
### Changed
### Fixed
