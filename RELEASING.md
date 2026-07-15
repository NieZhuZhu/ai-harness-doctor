# Releasing

Releases are tag-driven and published by GitHub Actions.

## Publish a new version

1. Bump the package version and create a matching Git tag:
   ```bash
   npm version patch
   ```
2. Push the commit and tag:
   ```bash
   git push --follow-tags
   ```
3. The `release` workflow:
   - runs the full release tests;
   - self-tests the exact tagged checkout through `uses: ./`;
   - verifies the tag version matches `package.json`;
   - verifies the exact tag commit is reachable from `origin/main`;
   - if the version already exists on npm, verifies its `gitHead` and packed
     tarball shasum match the exact tag before treating the run as idempotent;
   - publishes to npm with provenance and an explicit release-channel dist-tag;
   - creates the GitHub Release when it does not already exist;
   - for a stable version, force-updates the matching floating major Action tag
     to the release commit, checks out that public tag, validates its Action
     SARIF version, and opens a Marketplace confirmation issue.

The npm publish never runs before the tagged Action self-test passes. For stable
versions, floating-major verification runs after publish so it exercises the
same ref consumers will use.

Release verification also includes the workflow annotations: current
full-SHA-pinned Action dependencies must not emit embedded Node runtime
deprecation warnings. Dependabot is the supported path for refreshing these
pins; review its Action updates before merging, especially for the publish job
with `id-token: write`.

The public project's `package-lock.json` must resolve public npm packages from
`registry.npmjs.org`, not a private mirror that GitHub-hosted Dependabot cannot
reach. Treat both npm and Action dependency updates as full-matrix code changes.
The required lint job installs that exact graph with
`npm ci --ignore-scripts --no-audit --no-fund`; do not replace it with an
unlocked package-manager install or a fallback that ignores the reviewed lock.
After changing Dependabot or lockfile source policy, run a real npm update check
and verify that it succeeds even when no upgrade PR is needed.

## Stable and prerelease channels

The version in `package.json` determines the release channel:

- A stable version such as `1.0.1` publishes to npm dist-tag `latest`, creates
  the exact GitHub Release, moves and verifies `v1`, and opens the Marketplace
  confirmation reminder.
- A prerelease such as `1.1.0-beta.1` publishes to npm dist-tag `next` and
  creates an exact GitHub prerelease. It does **not** move `latest` or `v1`, run
  stable floating-tag verification, or open a Marketplace reminder.

This keeps both stable consumer pointers — npm `latest` and the Action's
floating `vN` tag — isolated from prerelease builds. Exact prerelease tags
remain usable by consumers who opt in explicitly.

## Version guard

The publish job extracts the version from the pushed tag (`v1.2.3` -> `1.2.3`) and compares it to `package.json`. It also peels the exact tag to a commit and requires that commit to be reachable from `origin/main`. A matching version on an unreviewed side branch is not sufficient. Any mismatch, missing ref, Git verification failure, or off-main tag stops before npm receives a network or publish command.

An idempotent rerun is stricter than version existence. If the exact npm
version is already present, the workflow requires registry `gitHead` to equal
the peeled exact-tag commit and `dist.shasum` to equal a clean
`npm pack --dry-run --json` result before it skips publish. A real npm 404 is
the only lookup outcome treated as unpublished; malformed metadata, DNS/auth/
registry failures, moved tags, or mismatched tarballs stop before GitHub
Release creation and floating-tag mutation. Do not try to “repair” a mismatch
by republishing an immutable npm version—investigate the tag/artifact history.

## Deprecate a version

Use the manual `deprecate` workflow in GitHub Actions. Provide:

- `version`: one exact published SemVer to deprecate, for example `0.1.0` or
  `1.2.0-beta.1` (no leading `v`, range, dist-tag, whitespace, or build
  metadata).
- `message`: the npm deprecation message.

The workflow passes both dispatch inputs through environment variables, validates
the exact version and non-empty message before npm runs, and then supplies both
as quoted, opaque arguments to `npm deprecate`. Input values never enter the
generated shell script text.

The repository still uses `NPM_TOKEN`. Moving to npm trusted publishing remains
a separate operation because it requires npmjs account-side trusted-publisher
configuration and a real publication proof; do not claim it from workflow code
alone.

## Secret rotation

`NPM_TOKEN` is a granular npm token with 2FA bypass for publishing. To rotate it, regenerate the token on npmjs.com and update the GitHub secret:

```bash
printf '%s' '<new-token>' | gh secret set NPM_TOKEN --repo NieZhuZhu/ai-harness-doctor
```

Do not print token values in logs or release notes.

## Tags

Every published npm version must have a corresponding Git tag. Existing published versions may be retroactively tagged only after verifying the npm tarball shasum matches the candidate commit's packed tarball.

Protect exact `vMAJOR.MINOR.PATCH` tags with a server-side ruleset or immutable
release control when the repository's GitHub plan exposes one. This workflow's
npm identity check is the portable fail-closed control; it does not claim that
GitHub Release immutability is enabled or available through the current API.

Exact release tags use full semantic versions such as `v1.0.0`. The workflow
derives and maintains a floating major tag for Action consumers (`0.x` -> `v0`,
`1.x` -> `v1`, `2.x` -> `v2`, and so on):

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
```

Only exact `v*.*.*` tags (stable or prerelease) trigger npm publishing; moving a
bare major tag cannot recursively start another release. Stable publication
ignores prerelease tags when selecting the newest version eligible to move
`vN`. Publishing a new major does not move the previous major's tag, so `v0`
remains on the final `0.x` release after `v1.0.0`.

## Marketplace confirmation

GitHub does not expose a stable public API for publishing an Action Release to
Marketplace and setting its categories. After automation succeeds, the workflow
opens a deduplicated issue named `Marketplace release confirmation: <tag>` with
links and this checklist:

- publish the GitHub Release to Marketplace;
- confirm the category set includes `AI Assisted` and `Code review` (GitHub may
  choose their display order);
- confirm the Marketplace page shows the new tag as Latest;
- close the reminder issue.

When a newer stable release succeeds, the workflow closes older open issues
whose title exactly matches the generated Marketplace reminder pattern. It
never closes the current tag's reminder or unrelated issues.

## Repository operations baseline

After workflow/job renames, dependency-policy changes, or maintainer changes,
verify the repository settings as production configuration:

- secret scanning, push protection, validity checks, and Dependabot security
  updates are enabled when supported;
- `main` requires the current PR check contexts and conversation resolution;
- force pushes/deletions remain disabled;
- admin enforcement remains disabled only because a sole maintainer cannot
  approve their own PR. Admin bypass must never be used to merge red CI.

Use `gh api` read-back after every settings mutation; a successful write without
verification is not evidence. Never print secret-scanning alert values.
