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
   - publishes to npm with provenance and an explicit release-channel dist-tag;
   - creates the GitHub Release when it does not already exist;
   - for a stable version, force-updates the matching floating major Action tag
     to the release commit, checks out that public tag, validates its Action
     SARIF version, and opens a Marketplace confirmation issue.

The npm publish never runs before the tagged Action self-test passes. For stable
versions, floating-major verification runs after publish so it exercises the
same ref consumers will use.

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

The publish job extracts the version from the pushed tag (`v1.2.3` -> `1.2.3`) and compares it to `package.json`. If they differ, publishing stops before npm receives anything.

## Deprecate a version

Use the manual `deprecate` workflow in GitHub Actions. Provide:

- `version`: the published version to deprecate, for example `0.1.0`.
- `message`: the npm deprecation message.

The workflow runs `npm deprecate` using the repository npm token.

## Secret rotation

`NPM_TOKEN` is a granular npm token with 2FA bypass for publishing. To rotate it, regenerate the token on npmjs.com and update the GitHub secret:

```bash
printf '%s' '<new-token>' | gh secret set NPM_TOKEN --repo NieZhuZhu/ai-harness-doctor
```

Do not print token values in logs or release notes.

## Tags

Every published npm version must have a corresponding Git tag. Existing published versions may be retroactively tagged only after verifying the npm tarball shasum matches the candidate commit's packed tarball.

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
