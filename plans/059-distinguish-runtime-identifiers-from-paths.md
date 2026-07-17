# Plan 059: Distinguish Docker and RPC identifiers from repository paths

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 8b0d19e..HEAD -- \
>   scripts/registry.py tests/test_registry_consistency.py \
>   tests/test_semantic.py tests/test_check_drift.py \
>   EXTERNAL_VALIDATION.md SKILL.md \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md \
>   plans/059-distinguish-runtime-identifiers-from-paths.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 014, 018, 052, and 053 (DONE)
- **Category**: bug / diagnostic precision / external validity
- **Planned at**: commit `8b0d19e`, 2026-07-17
- **Reconciled**: REJECTED — fixed independently by direct `main` commit
  `d3a6a3e` (no associated plan/implementation PR), released in `v1.12.1` and
  retained through `v1.13.1`. Do not execute this plan again.
- **Verification**: commit `d3a6a3e` added the shared bounded classifier,
  semantic/D2 parity tests, all seven README + `SKILL.md` docs, and
  `EXTERNAL_VALIDATION.md` round 32. On current `origin/main`, 201 registry /
  semantic / drift tests pass, strict drift is 100/A, and self-eval is 38/38.
  The commit's push `test` and `action-self-test` workflows succeeded, but
  because it bypassed the planned PR flow there is no nine-context PR evidence.

## Why this matters

The shared backtick classifier treats every slash-bearing `org/name` token as a
repository path unless another syntax rule excludes it. Real harness docs use
the same shape for Docker image names and RPC/API method identifiers. Both
Phase 0 semantic checks and Phase 2 D2 therefore fail accurate instructions.

Fix the shared classifier with bounded same-line context, not a blanket
`org/name` exclusion: repositories legitimately contain two-segment directories
such as `org/service`, and explicit file/directory/edit guidance must continue
to be checked.

## Mechanical reproduction

Current shared classification:

```text
Run the `letta/letta` image locally.        -> declared path
Call RPC method `thread/read`.              -> declared path
The endpoint is `app/list`.                 -> declared path
Edit the real repository `src/service`.     -> declared path
```

On a synthetic repository containing only `src/service`, both engines report
three false missing-path findings:

```text
semantic: letta/letta, thread/read, app/list
drift D2: letta/letta, thread/read, app/list
```

External evidence already records the same classes:

- `EXTERNAL_VALIDATION.md` round 28: Letta's documented `letta/letta` Docker
  image is reported MISSING.
- OpenAI Codex validation: `thread/read` and `app/list` RPC method examples are
  reported MISSING.

## Current state

### One classifier controls both engines

`scripts/registry.py:277-388` implements `declared_paths(text)`. Semantic and
D2 consume it, and `tests/test_registry_consistency.py` enforces parity.

The classifier already has evidence-based exclusions for:

- shell commands;
- quoted/code expressions;
- scoped package imports;
- placeholders;
- Git refs;
- Go import hosts;
- dotenv runtime files;
- generated output roots;
- globs and whitespace.

This plan adds a contextual identifier class at that same seam. Do not patch
semantic and drift independently.

### Context must preserve real paths

The token shape alone is ambiguous:

```text
Docker image `org/service`       # not a path
RPC method `org/service`         # not a path
Edit `org/service`               # path
The `org/service` directory      # path
```

Use lexical cues adjacent to the exact backtick match. Do not globally skip all
two-segment tokens or all lowercase slash tokens.

## Target contract

1. Add one shared helper that receives the full line and backtick match span.
2. Classify as non-filesystem when bounded context explicitly labels the token
   as one of:
   - Docker/container/OCI image or image name;
   - RPC method/procedure;
   - API method/endpoint/operation/route.
3. Preserve path classification when bounded context explicitly labels the
   token as a file, directory, folder, path, module source location, or target
   to edit/open/modify.
4. Define deterministic precedence for mixed cues. Recommended:
   - immediate syntactic label attached to the token wins;
   - explicit filesystem noun/verb wins over a distant generic API word;
   - ambiguous context remains a path (fail closed).
5. Match case-insensitively and only within the current line/sentence-sized
   bounded window. Never infer section-level prose intent.
6. Preserve tokens with three or more path components, extensions, leading
   dots, or explicit relative markers unless they are explicitly labeled as a
   runtime identifier.
7. Phase 0 and D2 must remove exactly the false runtime identifiers while
   retaining the real missing `org/service` directory case.
8. Add real-line regression fixtures based on Letta and Codex, sanitized and
   commit-pinned in `EXTERNAL_VALIDATION.md`.
9. Do not suppress Docker Compose/YAML file paths merely because the word
   Docker occurs elsewhere on the line.
10. Update public behavior docs in all seven READMEs and `SKILL.md` concisely:
    backtick path checks exclude explicitly labeled runtime/API identifiers.
11. Python 3.9 stdlib only; no NLP/parser dependency.

## Design

Add a private helper near `declared_paths`, for example:

```python
def _is_labeled_non_path_identifier(line, match):
    ...
```

Build small pre/post windows around `match.start()`/`match.end()` and compile
explicit phrase patterns. Keep positive filesystem cues separate from negative
identifier cues so tests can pin precedence.

Suggested cue families:

```text
non-path before: docker image, container image, image, rpc method,
                 method, endpoint, operation, route
non-path after:  image, container image, rpc method, endpoint
path:            file, directory, folder, path, edit, open, modify,
                 source, located under
```

Do not use broad words such as "service" or "app" as cues.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Registry parity | `python3 -m unittest tests.test_registry_consistency -v` | all pass |
| Semantic tests | `python3 -m unittest tests.test_semantic.SemanticPathTests -v` | all pass |
| Drift tests | `python3 -m unittest tests.test_check_drift.DriftChecksTests -v` or exact owning class | all pass |
| Full gate | `npm run check` | all pass |
| Package candidate | `npm run check:package` | package candidate OK |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |
| Self eval | current evidence-bound score command | all pass, Grade A |

## Scope

**In scope**:

- `scripts/registry.py`
- `tests/test_registry_consistency.py`
- `tests/test_semantic.py`
- `tests/test_check_drift.py`
- `EXTERNAL_VALIDATION.md`
- `SKILL.md`
- all seven public READMEs
- `plans/059-distinguish-runtime-identifiers-from-paths.md`
- `plans/README.md`

**Out of scope**:

- A general English parser or section-context tracker.
- Globally ignoring `org/name`.
- Docker/OCI registry validation or image existence checks.
- RPC schema discovery.
- Rewriting already-reported baselines automatically.
- D7 Markdown links.
- Package-root ancestor resolution.
- Third-party dependencies.

## Git workflow

- Branch: `fix/059-runtime-identifiers-not-paths`.
- Commit: `fix(paths): distinguish runtime identifiers`.
- One focused correctness PR with seven-language docs.
- Wait for all nine required checks before squash merge.
- Bugfix-only: patch-release material.

## Steps

### Step 1: Add cross-engine RED fixtures

Pin:

- `letta/letta` after/before Docker image cues;
- `thread/read` after RPC method cue;
- `app/list` after endpoint cue;
- real existing and missing `org/service` paths;
- Docker-related line containing an explicit Compose file path.

Before implementation, false identifiers must appear in both semantic and D2.

### Step 2: Implement the bounded shared classifier

Add the helper and call it inside `declared_paths()` before adding the token.
Use match positions, not global line exclusion.

### Step 3: Prove conservative precedence

Add negative tests for ambiguous bare `org/service`, explicit file/directory
contexts, edit/open verbs, dotted/three-segment paths, and mixed Docker/path
sentences. Ambiguous remains checked.

### Step 4: Validate real external evidence

Use pinned, read-only Letta/Codex fixtures or the smallest extracted lines.
Record exact evidence boundary and no target mutation in
`EXTERNAL_VALIDATION.md`.

### Step 5: Synchronize docs and run gates

Update the path-check safety statement across all seven READMEs and `SKILL.md`.
Run Standards/Spec review:

- one shared classifier;
- no blanket shape suppression;
- both false-positive classes removed;
- real paths retained.

## Test plan

- Docker image pre/post labels.
- RPC method and endpoint labels.
- Explicit real/missing filesystem path controls.
- Mixed-context precedence.
- Semantic/D2 parity.
- Existing Go import, npm scope, dotenv, git-ref, generated-dir cases.
- External Letta/Codex evidence.

## Done criteria

- [x] Letta Docker image and Codex RPC identifiers produce no path finding.
- [x] Bare/explicit `org/service` paths remain checked.
- [x] Semantic and D2 remain exactly aligned.
- [x] Context is bounded and deterministic.
- [x] Existing classifier regressions remain green.
- [x] Seven READMEs, SKILL, and external evidence are updated.
- [ ] Full local and nine required CI checks pass.

## STOP conditions

Stop and report back if:

- the real examples cannot be distinguished without section-level semantics;
- a proposed cue suppresses explicit file/directory paths;
- semantic and D2 need separate logic;
- real repository validation shows more added false negatives than removed
  false positives;
- any required CI context is red or pending.

## Maintenance notes

- Treat new non-path identifier classes as evidence-backed contextual rules,
  never token-shape guesses.
- Keep ambiguity fail-closed: checking a possible path is safer than silently
  exempting real drift.
- Add future external false-positive classes to this shared seam only after
  preserving positive filesystem controls.
