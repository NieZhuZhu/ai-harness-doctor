# Contributing

Thanks for your interest in `ai-harness-doctor`. This guide explains how changes
flow from idea to a released version.

Before participating, read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). For usage
questions and public report types see [`SUPPORT.md`](SUPPORT.md). Report
vulnerabilities privately according to [`SECURITY.md`](SECURITY.md), never in a
public issue.

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
4. Run the full suite, the linters, and a self-checkup locally:
   ```bash
   npm run check          # lint (eslint + ruff + docs + adapters) then tests
   node bin/cli.js help
   python3 scripts/scan.py .
   python3 scripts/check_drift.py .
   ```
   `npm run check` is the single "all green" entry point (`npm run lint && npm test`).
   Linting requires Node >= 20.19 (eslint 10) and `ruff` on your PATH
   (`pip install ruff`); the runtime CLI itself still supports Node 16+.
   Keep the drift health score at grade A.
5. If user-facing behavior changed, keep `README.md`, `README.zh-CN.md`, and
   `README.ja.md` in sync within the same PR (`npm run lint:docs` enforces the
   shared structure).
6. Use Conventional Commit messages in English, e.g. `feat(scan): ...`,
   `fix(drift): ...`, `docs(agents): ...`. Link a related issue with
   `Closes #<n>` when one exists.
7. Open the PR. CI runs a lint job (eslint + ruff + docs + adapters) plus the
   Python (3.9/3.10/3.12) and Node (16/20/22) matrix; all checks must pass
   before merge.

Use the pull request template. In particular, classify the release impact,
confirm safety/compatibility boundaries, and refresh evidence-bound self-eval
results whenever `AGENTS.md` or its task pack changes.

## Test coverage

Coverage is optional and **not** part of the required gate, but it helps spot
untested code paths. Both measurements use dev-only tooling — nothing new is
added to the shipped runtime (the scripts stay standard-library-only):

```bash
npm run coverage          # Python + JS coverage
npm run coverage:py       # coverage.py over scripts/ (pip install coverage)
npm run coverage:js       # node --test --experimental-test-coverage over bin/
```

- `coverage:py` needs the dev-only [`coverage`](https://pypi.org/project/coverage/)
  package (`pip install coverage`); its config lives in `.coveragerc`.
- `coverage:js` uses Node's built-in test-coverage reporter (Node >= 20), so it
  needs no extra dependency.

## Releasing

Releases are tag-driven and published by GitHub Actions. See `RELEASING.md` for
the full flow. In short, a maintainer bumps the version on `main`
(`npm version <patch|minor|major>`) and pushes the tag; CI verifies the tag
matches `package.json` and its exact commit is reachable from `origin/main`,
verifies an already-published npm version has matching source/tarball identity,
publishes new versions with provenance, and creates a GitHub Release with
auto-generated notes. There is no `CHANGELOG.md`; the GitHub Release notes are
the canonical change history.

Dependency updates for npm development tooling and immutable GitHub Action pins
are opened weekly by Dependabot. Treat them as code changes and require the
same matrix before merge. Because this is a public package and Dependabot runs
on GitHub-hosted infrastructure, keep committed npm tarball sources on
`registry.npmjs.org`; a successful real update check, not merely a valid
`.github/dependabot.yml`, is the operational health signal.
