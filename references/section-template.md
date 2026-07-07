# AGENTS.md section template

## Project overview

Write: repository purpose, critical subsystems, and boundaries agents are likely to misread.

Do not write: marketing copy already covered by README, or long background narratives.

## Build & test

Write: core commands that must run from the repository root, common variants, and required environment prerequisites.

Do not write: a full copy of `package.json` scripts; reference the real manifest and let the drift guard validate it.

## Conventions

Write: repository-specific conventions that tools cannot infer, such as layer boundaries, error-handling strategy, or naming restrictions.

Do not write: language-default style or details already enforced by the formatter.

## Testing requirements

Write: which changes require tests, where fixtures live, and which external dependencies must not be touched.

Do not write: the test framework's official tutorial.

## Safety

Write: secrets that must never be committed, production resources that must not be accessed, dangerous scripts, and data-compliance boundaries.

Do not write: generic reminders to "be safe".

## Commit & PR

Write: commit-message style, verification that PR descriptions must include, and whether squash is allowed.

Do not write: workflows that are identical to the platform default.
