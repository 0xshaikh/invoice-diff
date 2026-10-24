## What this PR does

<!--
  A one-paragraph summary. Start with the verb (Adds / Fixes / Refactors /
  Removes / Updates / Documents). Link any related issues with "Closes #123"
  or "Refs #123" so GitHub tracks them automatically.
-->

Closes #

## Why

<!-- What user problem or maintainer pain does this address? -->

## Type of change

- [ ] Bug fix (a non-breaking change that fixes an issue)
- [ ] New feature (adds new capability without breaking existing usage)
- [ ] Marketplace dialect (adds a new Flipkart / Meesho / Amazon reader)
- [ ] Output format (adds a new report format)
- [ ] Documentation only (no behaviour change)
- [ ] Refactor / cleanup (no behaviour change)
- [ ] Performance improvement
- [ ] Test-only change

## Checklist

- [ ] I have followed the [contribution guidelines](../CONTRIBUTING.md).
- [ ] I have added or updated tests covering the change.
- [ ] I have updated `CHANGELOG.md` under `## [Unreleased]` if the change is user-visible.
- [ ] I have updated `README.md` and/or `USAGE_GUIDE.md` if the change affects user-facing behaviour.
- [ ] `make lint` passes locally.
- [ ] `make test` passes locally.
- [ ] The new code follows the existing style (ruff + ruff format).
- [ ] The new code has type hints on public functions and classes.
- [ ] For a new marketplace dialect: I have added a golden test + sample CSV generator entry.
- [ ] For a breaking change: I have bumped the version in `pyproject.toml` and `CHANGELOG.md`.

## Screenshots / sample output

<!-- If the change produces user-visible output (a new report, a new CLI
     flag), paste a snippet of the actual output. -->

## Notes for the reviewer

<!-- Anything unusual: a hack, a trade-off, an open question, a follow-up
     PR planned. -->

## Security considerations

- [ ] This PR does not introduce a new dependency.
- [ ] If it does, the dependency is pinned and license-compatible (MIT / BSD / Apache-2.0).
- [ ] This PR does not change how settlement data is persisted or logged.
- [ ] If it does: I have described the change and reviewed it against [SECURITY.md](../SECURITY.md).
