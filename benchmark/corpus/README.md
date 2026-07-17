# Benchmark corpus: real-world harness surfaces

The self-benchmark (`benchmark/README.md`) proves the before/after efficacy story on one
controlled demo repo pair. This corpus complements it with breadth: **14 well-known,
high-star open-source repositories** whose agent-facing harness files are real, actively
maintained, and diverse, pinned as **shallow git submodules** so every reported number is
reproducible against an exact commit.

## What the corpus measures

`scan.py --repos-file` runs the full read-only Phase-0 checkup against every pinned repo
in one batch and reports a cross-repo summary: config-file inventory, gaps, HIGH security
findings, and semantic declaration-vs-code mismatches per repository. The corpus is
deterministic and free — no agent or LLM runs — so it can be refreshed on every pin
update without eval cost. Findings against third-party repos are *evidence about their
current harness state at the pinned commit*, not judgments: a gap simply means a repo has
not adopted a canonical `AGENTS.md`, and semantic findings frequently turn out to be
genuine upstream doc drift (see `EXTERNAL_VALIDATION.md` for adjudicated examples).

## Repositories

Stars recorded 2026-07-17. Each submodule pins the default-branch HEAD from that date.

| Submodule | Repository | Stars | Pinned commit | Harness surface at pin |
|---|---|---:|---|---|
| `react` | [react/react](https://github.com/react/react) | 246,532 | `172742b419ba` | `CLAUDE.md`, `.claude/` |
| `n8n` | [n8n-io/n8n](https://github.com/n8n-io/n8n) | 196,732 | `3f7258b1a4f3` | `AGENTS.md`, `CLAUDE.md`, `.claude/` |
| `vscode` | [microsoft/vscode](https://github.com/microsoft/vscode) | 187,582 | `e1b183798f02` | `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/` |
| `ollama` | [ollama/ollama](https://github.com/ollama/ollama) | 176,283 | `714b6fc2a47c` | `AGENTS.md`, `CLAUDE.md` |
| `transformers` | [huggingface/transformers](https://github.com/huggingface/transformers) | 162,667 | `150eb7c9ed40` | `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` |
| `dify` | [langgenius/dify](https://github.com/langgenius/dify) | 149,091 | `a7aff83d52a6` | nested `AGENTS.md` tree, `CLAUDE.md`, `.claude/` |
| `supabase` | [supabase/supabase](https://github.com/supabase/supabase) | 106,428 | `1c827c5cbb29` | `.cursor/rules/`, `.github/copilot-instructions.md`, `.github/instructions/`, `.claude/` |
| `gemini-cli` | [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 106,024 | `3ff5ba20fc1a` | `GEMINI.md` |
| `codex` | [openai/codex](https://github.com/openai/codex) | 98,901 | `315195492c80` | `AGENTS.md` |
| `home-assistant` | [home-assistant/core](https://github.com/home-assistant/core) | 89,281 | `d33d6d9aacd2` | `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/`, `.claude/` |
| `zed` | [zed-industries/zed](https://github.com/zed-industries/zed) | 87,116 | `058f01fa9350` | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` |
| `elasticsearch` | [elastic/elasticsearch](https://github.com/elastic/elasticsearch) | 77,518 | `2f2662ab097e` | `AGENTS.md`, `CLAUDE.md` |
| `cline` | [cline/cline](https://github.com/cline/cline) | 64,728 | `9a5e1751b280` | `.github/copilot-instructions.md`, `.clinerules/`, `.claude/` |
| `ghostty` | [ghostty-org/ghostty](https://github.com/ghostty-org/ghostty) | 58,283 | `73534c4680a8` | `AGENTS.md`, `CLAUDE.md` |

Selection criteria: widely known (58k–247k stars), a real committed harness surface
(verified via the GitHub API before pinning), and diversity along two axes — ecosystem
(JS/TS, Python, Go, Rust, Java, Zig, C++) and harness style (canonical `AGENTS.md`
adopters, `CLAUDE.md`/`GEMINI.md` duplicates, Copilot instruction rules, Cursor rules,
Cline rules, and one deliberate non-adopter of any canonical file).

## Working with the submodules

A fresh clone leaves the corpus uninitialized (empty directories) — nothing here affects
normal development, tests, or CI. Initialize only what you need:

```bash
# one repo
git submodule update --init benchmark/corpus/repos/react
# the whole corpus (~2.7 GB working trees, shallow)
git submodule update --init benchmark/corpus/repos
```

Every entry sets `shallow = true` in `.gitmodules`, so initialization fetches only the
pinned commit's tree, not upstream history.

To move a pin to the current upstream default branch:

```bash
git submodule update --remote --depth 1 benchmark/corpus/repos/<name>
git add benchmark/corpus/repos/<name>
```

then regenerate the results below, update the pinned-commit table above, and commit both
together — committed results must always describe the committed pins
(`tests/test_benchmark_corpus.py` guards the list/results consistency, and the results
are dated so staleness is visible).

## Reproduce

From the repository root, with the corpus initialized:

```bash
python3 scripts/scan.py --repos-file benchmark/corpus/repos.txt --json --no-report-file \
  | python3 -c "import json,sys; p=json.load(sys.stdin); [r.pop('resolved', None) for r in p['repos']]; print(json.dumps(p, indent=2))" \
  > benchmark/corpus/results/corpus-scan.json
python3 scripts/scan.py --repos-file benchmark/corpus/repos.txt --no-report-file > benchmark/corpus/results/corpus-scan.md
```

The `resolved` fields are dropped before committing: they hold machine-local absolute
paths, and committed artifacts must stay host-independent
(`tests/test_benchmark_corpus.py` enforces this).

## Results (2026-07-17, pinned commits above)

One deterministic batch over all 14 pinned repositories: **150 agent-config files**,
96 gaps, **0 HIGH security findings**, 44 overlaps, 3 conflicts, 15 semantic mismatches,
and 10/14 repositories with a root `AGENTS.md`.

| Repo | Root `AGENTS.md` | Config files | Gaps | HIGH sec | Overlaps | Conflicts | Semantic mismatches |
|---|:---:|---:|---:|---:|---:|---:|---:|
| `react` | no | 2 | 3 | 0 | 0 | 0 | 0 |
| `n8n` | yes | 21 | 7 | 0 | 15 | 1 | 3 |
| `vscode` | yes | 33 | 9 | 0 | 0 | 1 | 0 |
| `ollama` | yes | 2 | 8 | 0 | 0 | 0 | 0 |
| `transformers` | yes | 4 | 10 | 0 | 3 | 0 | 2 |
| `dify` | yes | 12 | 7 | 0 | 3 | 1 | 0 |
| `supabase` | no | 14 | 3 | 0 | 1 | 0 | 0 |
| `gemini-cli` | no | 8 | 3 | 0 | 0 | 0 | 0 |
| `codex` | yes | 2 | 7 | 0 | 0 | 0 | 6 |
| `home-assistant` | yes | 4 | 10 | 0 | 3 | 0 | 2 |
| `zed` | yes | 4 | 10 | 0 | 3 | 0 | 2 |
| `elasticsearch` | yes | 15 | 7 | 0 | 15 | 0 | 0 |
| `cline` | no | 19 | 3 | 0 | 0 | 0 | 0 |
| `ghostty` | yes | 10 | 9 | 0 | 1 | 0 | 0 |

The first corpus run (pre-fix scanner) reported exactly one HIGH security finding across
all 14 repositories — a TypeScript type annotation in vscode's Copilot-extension
`AGENTS.md` misread as a hardcoded secret. It was adjudicated as a scanner false
positive and fixed in
[#255](https://github.com/NieZhuZhu/ai-harness-doctor/pull/255) before these results
were committed (`EXTERNAL_VALIDATION.md` round 31) — the corpus doing exactly the job it
was added for. The remaining findings are committed as unadjudicated evidence: codex's 6
semantic mismatches, for example, include the known RPC-method-token class plus genuine
upstream doc drift documented in rounds 14–15.

See [`results/corpus-scan.md`](results/corpus-scan.md) for the rendered per-repo report
and [`results/corpus-scan.json`](results/corpus-scan.json) for the machine-readable
payload.

## Honest limitations

- Results describe the pinned commits only; upstream repos move daily, and refreshed pins
  will produce different numbers.
- This is a Phase-0 scan corpus: it measures inventory, gaps, security and semantic
  consistency deterministically. The Phase-3 before/after efficacy eval (which makes
  paid agent calls) has been run against one corpus repo so far — openai/codex, with
  an honestly published null result; see [`evals/codex/`](evals/codex/README.md) —
  and is not part of the deterministic corpus refresh.
- Third-party findings are unadjudicated evidence. Unlike `EXTERNAL_VALIDATION.md`
  rounds, corpus refreshes do not individually verify whether each finding is genuine
  upstream drift or a scanner limitation; the corpus exists precisely to surface such
  candidates for validation rounds.
- Shallow submodules fetch the pinned tree from GitHub; a pin whose commit is later
  garbage-collected upstream (e.g. after a force-push) would need re-pinning.
