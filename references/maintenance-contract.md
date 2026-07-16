# Maintenance contract

Progressive-disclosure details for repository maintainers. The root
`AGENTS.md` retains the invariants agents need on every turn; use this reference
when changing GitHub integration, baselines, CI, release, or installer state.

## Baseline lifecycle

- Baselines are reviewed debt registers, never opaque ignore lists.
- Scan security findings are ineligible.
- Stable identities exclude line numbers. Current state is classified as:
  - new: active finding arrays;
  - known: `baselined`;
  - repaired: `resolved_baseline`.
- `--check-baseline` exits `9` for repaired entries only after active finding
  gates; `--prune-baseline` atomically subtracts only repaired persisted
  entries. Never absorb new findings.
- Ordinary missing/malformed baseline use is fail-safe (suppresses nothing);
  explicit check/prune is fail-closed and writes nothing.
- Each repository owns its baseline. Multi-repo batch mode does not compose
  baselines.

## SARIF and Marketplace Action

- Every result carries a stable line-insensitive `partialFingerprints` identity.
- Scan and drift use separate `automationDetails` categories.
- `properties.aiHarnessDoctor` is the producer truth for command, severity
  counts, resolved-baseline count, and drift health.
- `bin/action-report.js` is the only Action output/Job Summary parser. Never
  reimplement counts in Bash or run the doctor twice.
- Action status precedence is `findings > maintenance > ok`. A valid non-zero
  finding/maintenance gate reports first, then restores the exact CLI exit.
  Operational/malformed reports never fabricate health.
- Any Action-facing change must update `tests/test_action_metadata.py` and pass
  a real `uses: ./` fixture; direct CLI tests are insufficient.
- PR self-test proves bundled scan/drift plus an exact published npm override.
  Release verifies bundled commands pre-publish, then the floating stable Action
  plus the exact new npm version post-publish. Prereleases do not move stable
  pointers.

## GitHub guard and feedback

- Keep `assets/guard/` and repository self-bootstrap copies synchronized.
- GitHub drift guards run on every PR without path filters: D2/D7 can depend on
  any named path.
- Weekly failure opens/updates one exact-title issue; recovery comments and
  closes it; unrelated issues stay untouched. Self-checkup remains non-failing.
- PR feedback keeps one owned marker summary current, preserves inline
  findings, never edits foreign markers, and does not duplicate the summary on
  HTTP 422. Package paths stay attributed; batch findings are summary-only; host
  resolved paths never leak.

## CI, release, and repository operations

- Required checks cover lint, Python 3.9/3.10/3.12, Node 16/20/22, self-test,
  strict drift, and current eval evidence.
- Lint installs the committed graph with
  `npm ci --ignore-scripts`; no unlocked/fallback installer.
- External Actions use vetted full SHAs with version hints. Move template and
  self copies together.
- Privileged workflow inputs enter scripts only through `env`, are validated,
  and remain quoted.
- Release tags must be on `origin/main`. An existing npm version is skipped only
  when registry `gitHead` and packed tarball shasum match the exact tag.
- Feature = minor, bugfix-only = patch, breaking = major. Stable moves
  `latest`/`vN` and opens one Marketplace reminder; prerelease uses `next`.
- Secret scanning, push protection, Dependabot security updates, required
  contexts, and conversation resolution are operational controls. Admin bypass
  exists only for the sole-maintainer self-approval deadlock, never red/pending
  CI or unresolved discussions.

## Installer recovery

- Installer state authorizes deletion. Serialize commands with the owned lock,
  journal each contained mutation before applying it, atomically replace the
  exact next manifest, and recover by digest.
- A journal-less transaction directory is an incomplete artifact and may be
  cleaned within the transactions root. Present-but-malformed/unsafe journals,
  tampered backups, or post-crash external edits fail closed with evidence
  retained.
- Preserve user content and unowned collisions. Tests always use isolated
  `HOME`; never write real agent config directories.
