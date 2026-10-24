---
name: Bug report
about: Report a discrepancy, crash, or incorrect output
title: "[bug]: "
labels: ["bug", "needs-triage"]
assignees: []
---

## What happened?

<!-- A concise description of the bug. -->

## What should happen?

<!-- A concise description of the expected behaviour. -->

## Reproduction steps

1. Install:
   ```bash
   # pip install invoice-diff  or  git clone ... && pip install -e .
   ```
2. Prepare the input files:
   ```bash
   # describe the CSVs / commands used
   ```
3. Run:
   ```bash
   invoice-diff ...
   ```
4. Observe the actual behaviour:
   ```bash
   # paste the actual output or error here
   ```

## Environment

- **invoice-diff version**: `<invoice-diff --version>`
- **Python version**: `<python --version>`
- **OS**: `<uname -a or winver>`
- **Marketplace dialect**: <flipkart / meesho / amazon>

## Minimal reproduction

Please attach a **minimal** reproduction. Do not include real invoice IDs,
real customer data, or real amounts — anonymise them but preserve the shape:

```csv
invoice_id,amount,gst_amount,issued_date
INV-0001,1000.00,180.00,2026-10-01
INV-0002,2000.00,360.00,2026-10-02
```

You can attach the CSVs to the issue, or drop them in a gist.

## Actual output

```
# paste the actual output, error traceback, or report snippet here
```

## Expected output

```
# paste the output you expected to see
```

## Anything else?

<!-- Logs, screenshots, workarounds you found, related issues. -->

---

- [ ] I have searched open issues and this is not a duplicate.
- [ ] I have included a minimal reproduction.
- [ ] I have included the version, Python version, and OS.
- [ ] The reproduction does not contain confidential data.
