# Contributing

Thanks for your interest in `ai-harness-doctor`. This guide explains how changes
flow from idea to a released version.

## TL;DR

- **Pull requests are required** for every change to `main`; direct pushes are
  blocked by branch protection.
- **Issues are optional** and used for coordination and traceability, not as a
  mandatory gate. Open one when a change benefits from discussion or a public
  record; skip it for small, obvious changes.
- **Tests ship with the change**: any behavior change to `scripts/*.py` or
  `bin/cli.js` must include matching tests in the same PR.

## When to open an issue first

Opening an issue before a PR is encouraged — but not required — in these cases:

- **Larger features or design changes**, where the motivation and approach are
  worth discussing before code exists.
- **Bugs or requests reported by others**: the issue captures the report; the PR
  fixes it and closes the issue with `Closes #<n>`.
- **Anything that benefits from a public roadmap or an audit trail**, forming a
  "discuss → implement → close" record.

You can skip the issue and open a PR directly for:

- Small, self-contained changes (typos, docs tweaks, small bug fixes).
- Changes whose scope and approach are already unambiguous.

There is no requirement to file an issue, land a PR, and then separately close
an issue for every change. Use issues where they add value; otherwise a PR alone
is enough.

## Pull request workflow

1. Branch from the latest `main`.
2. Make the change. Keep scripts deterministic and standard-library-only
   (Python 3.9+ / Node 16+); do not add runtime dependencies. See `AGENTS.md`
   for the full conventions.
3. Add or update tests for any behavior change to `scripts/*.py` or
   `bin/cli.js`.
4. Run the full suite and a self-checkup locally:
   ```bash
   python3 -m unittest discover -s tests -v
   npm test
   node bin/cli.js help
   python3 scripts/scan.py .
   python3 scripts/check_drift.py .
   ```
   Keep the drift health score at grade A.
5. If user-facing behavior changed, keep `README.md`, `README.zh-CN.md`, and
   `README.ja.md` in sync within the same PR (`npm run lint:docs` enforces the
   shared structure).
6. Use Conventional Commit messages in English, e.g. `feat(scan): ...`,
   `fix(drift): ...`, `docs(agents): ...`. Link a related issue with
   `Closes #<n>` when one exists.
7. Open the PR. CI runs the Python (3.9/3.10/3.12) and Node (16/20/22) matrix;
   all checks must pass before merge.

## Releasing

Releases are tag-driven and published by GitHub Actions. See `RELEASING.md` for
the full flow. In short, a maintainer bumps the version on `main`
(`npm version <patch|minor|major>`) and pushes the tag; CI verifies the tag
matches `package.json`, publishes to npm with provenance, and creates a GitHub
Release with auto-generated notes. There is no `CHANGELOG.md`; the GitHub
Release notes are the canonical change history.
