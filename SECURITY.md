# Security Policy

`invoice-diff` is a single-shot reconciliation tool that runs locally on
marketplace settlement CSVs and an expected invoice ledger. It does not contact
any external service, does not store credentials, and does not persist
settlement data.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |

Only the most recent minor release is actively patched for security issues.
Older minor releases will receive a backport only if the vulnerability is
CRITICAL or HIGH and affects a supported Python version.

## Reporting a vulnerability

**Please do not file a public issue** for a security vulnerability. Public
disclosure before a fix is available is the primary way these bugs become
exploitable.

To report:

1. **Email**: `security@zerovyn.com` (preferred).
2. **GitHub private advisory**: use the "Security" tab on the repository →
   "Report a vulnerability". GitHub will open a private advisory that I can
   respond to without exposing the vulnerability publicly.
3. **PGP**: a public key will be published here within 30 days of the first
   disclosure. Until then, encrypt sensitive material with
   `gpg --armor -e anas@zerovyn.com` if you have access to that address.

Include:

- A description of the vulnerability and its impact.
- Steps to reproduce (or a proof of concept if practical).
- The affected version(s).
- Any suggested fix.

## Response SLA

| Severity | First response | Fix target |
|----------|----------------|------------|
| **CRITICAL** — remote code execution, data exfiltration, credential leak | 24 hours | 7 days |
| **HIGH** — parsing of a maliciously crafted CSV could corrupt reconciliation output | 3 days | 14 days |
| **MEDIUM** — denial of service on crafted input | 7 days | 30 days |
| **LOW** — information disclosure via error messages | 14 days | next minor release |

## What I will do when you report

1. **Acknowledge** within the SLA above.
2. **Triage** and confirm the vulnerability is in scope.
3. **Patch** on a private branch.
4. **Coordinate disclosure** — the fix will be released and the advisory
   published on the day you agree (default: 7 days after the patch lands, per
   the OpenSSF Vulnerability Disclosure Guidelines).
5. **Credit** you in `CHANGELOG.md` and the advisory unless you prefer
   anonymity.

## Scope

In scope:

- Parsing of untrusted marketplace CSVs.
- Parsing of an untrusted "expected invoice" ledger.
- Any code path reachable through the CLI.
- Any data leak into logs, reports, or exported files.

Out of scope:

- Vulnerabilities in third-party dependencies (please report upstream;
  we will bump the pinned version once the upstream is patched).
- Local filesystem permissions around the seller's own working directory.
- Disclosure of data the seller already owns and chose to load into the tool.

## Mitigations to consider

- Run `invoice-diff` inside a sandbox / container when processing settlements
  from untrusted sources.
- The default tolerance values (0.01 for both amount and GST) are strict;
  if you loosen them, treat the output as best-effort.
- Reports contain invoice IDs and amounts — keep `reports/` out of version
  control (it is already in `.gitignore`).
