# Security Policy

## Supported versions

Security fixes are made on the default branch and released in the newest stable
version. Upgrade to the current npm `latest` / GitHub Action floating major tag
before reporting a problem that may already be fixed.

## Report a vulnerability privately

Do **not** open a public issue with exploit details, credentials, private
repository content, or a proof of concept that could harm users.

Use [GitHub Private Vulnerability Reporting](https://github.com/NieZhuZhu/ai-harness-doctor/security/advisories/new)
instead. Include:

- the affected version, command, Action, or MCP surface;
- the impact and prerequisites;
- minimal reproduction steps using synthetic data;
- suggested mitigations, if known.

Never include a live secret. Revoke or rotate any credential that may have been
exposed before submitting the report.

The maintainer will acknowledge a complete report as soon as practical, keep
discussion private while a fix is prepared, and coordinate disclosure through
the advisory. Exact response or release dates cannot be guaranteed.

## Scope

Security-relevant examples include repository-boundary escapes, unintended
writes/deletes, command execution beyond an explicit opt-in, secret leakage,
unsafe GitHub Action or release behavior, and MCP result/input handling that
could mislead clients.

Ordinary false positives, false negatives without sensitive details, and
feature requests belong in the repository's issue forms.
