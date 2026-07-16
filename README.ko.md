[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Español](README.es.md) | **한국어** | [Português (Brasil)](README.pt-BR.md) | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**코딩 에이전트는 오래된 저장소 지침을 따르면서도 자신 있게 행동할 수 있습니다.** AI Harness Doctor는 `AGENTS.md`, `CLAUDE.md`, Cursor 규칙, hooks, MCP 설정과 관련 harness 파일을 감사해 drift가 실패한 PR로 이어지기 전에 드러냅니다.

흩어진 지침을 사람이 관리하는 하나의 `AGENTS.md`로 통합하고, 도구별 파일은 작은 pointer로 유지하며, 정리된 harness가 실제로 에이전트 답변을 개선했는지 측정합니다.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> 포함된 benchmark에서 canonicalization은 객관식 정답을 **6/28에서 28/28**로 높였고, flip-flop을 제거했으며, 평균 latency를 27%, 기록된 cost를 17% 줄였습니다.

## 60초 만에 시작

설치 없이 read-only checkup을 실행합니다:

```bash
npx ai-harness-doctor scan .
```

특정 경로에 적용되는 지침을 설명합니다:

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Node와 Python runtime을 확인합니다:

```bash
npx ai-harness-doctor doctor --self-test
```

위 명령은 감사 대상 저장소를 변경하지 않습니다.

## 검사 항목

| 영역 | Doctor가 확인하는 내용 |
|---|---|
| Inventory | Canonical files, tool rules, nested scopes, MCP, hooks, commands, permissions, subagents. |
| Security | Plaintext secrets, 과도한 권한, 안전하지 않은 MCP transport, 위험한 hook, bypass 지침. |
| Consistency | 없는 script, 이동한 path, package manager/runtime drift, broken links, competing lockfiles. |
| Instruction quality | 과도한 context, README 전체 복사, silent adjudication, overlap, same-scope conflict. |
| Scope | root부터 가장 가까운 `AGENTS.md`까지의 상속과 bounded Claude/Cursor/Copilot glob applicability. |
| Efficacy | Before/after 정확도, 안정성, latency, cost, evidence freshness, health grade. |

보안 읽기는 감사 대상 저장소 안에만 머뭅니다. 큰 파일도 SHA-256, 줄 수, secret, permission-bypass를 전체 검사하며 `--max-bytes`는 semantic analysis만 제한합니다.

## 네 단계

| 단계 | 목표 | 주요 명령 | 사람이 멈춰 결정할 지점 |
|---|---|---|---|
| 0 — Checkup | 위험, 충돌, 누락, 저장소 사실 발견. | `scan`, `explain` | 마이그레이션 범위 확인. |
| 1 — Treat | Merge plan 작성과 canonical guidance 통합. | `plan`, `validate`, `stubs` | 모든 semantic conflict 판정. |
| 2 — Follow-up | Command, path, link, stub, fact 재 drift 방지. | `drift`, `guard`, `review` | 코드와 지침 중 무엇이 잘못됐는지 결정. |
| 3 — Efficacy | Harness가 에이전트 행동을 개선하는지 측정. | `eval` | 증거가 충분한지 결정. |

스크립트는 deterministic한 기계 작업만 합니다. npm과 pnpm 중 하나를 몰래 선택하거나, 논쟁 중인 명령을 결정하거나, prose를 semantic merge하지 않습니다.

## 저장소 통합

검토 가능한 plan을 만들고 `AGENTS.md`를 작성·검증한 뒤 중복 도구 파일을 작은 pointer로 교체합니다:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Claude Code skill을 설치하고 `/harness-doctor .` 또는 `/harness-treat .`을 실행할 수도 있습니다. 저장소 사실이 모호하면 에이전트는 멈추고 결정을 요청합니다.

## 설치 및 업데이트

| 목적 | 명령 |
|---|---|
| 현재 사용자에게 Claude Code skill 설치 | `npx ai-harness-doctor install` |
| Codex prompts 설치 | `npx ai-harness-doctor install --agent codex` |
| 저장소에 Cursor commands 설치 | `npx ai-harness-doctor install --agent cursor --project` |
| 저장소에 모든 adapter 설치 | `npx ai-harness-doctor install --agent all --project` |
| 최신 package를 추적 중인 설치에 재배포 | `npx ai-harness-doctor@latest update` |
| 설치된 adapter 제거 | `npx ai-harness-doctor uninstall --agent all` |

Copy 설치는 ownership을 추적합니다. Update/uninstall은 소유하지 않은 충돌과 사용자 편집을 보존합니다. 테스트는 항상 격리된 `HOME`을 사용합니다.

## CI에서 건강하게 유지

Provider-aware pre-commit, PR, scheduled guard를 설치합니다:

```bash
npx ai-harness-doctor guard . --apply
```

GitHub guard는 scan과 drift를 하나의 풍부한 PR review로 합칩니다. 위치가 있는 finding은 inline comment가 되고, summary에는 severity, health, evidence, repair, 우선순위가 포함됩니다.

이미 pre-commit framework를 사용하나요?

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.3.0
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

주간 checkup은 소유한 incident issue 하나만 갱신하고 복구 후 닫습니다. 유지보수 계약은 [`references/maintenance-contract.md`](references/maintenance-contract.md)를 참고하세요.

## GitHub Action과 SARIF

Marketplace Action은 기본적으로 선택한 ref의 bundled code를 실행하고 SARIF, Action outputs, Job Summary를 생성합니다:

```yaml
- id: doctor
  uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: scan
    path: .
- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: ${{ steps.doctor.outputs.sarif-file }}
```

출력에는 `status`, severity counts, `finding-count`, `resolved-baseline-count`, drift의 `health-score` / `health-grade`가 있습니다.

상태 우선순위는 `findings > maintenance > ok`입니다. 유효한 non-zero quality gate는 SARIF와 summary를 먼저 게시한 뒤 정확한 CLI exit code를 복원합니다.

SARIF 결과는 안정적인 partial fingerprint와 분리된 scan/drift category를 사용해 줄 이동에 따른 중복과 상호 종료를 방지합니다.

추가 option value에 공백이 있거나 exact/repeated argv 경계가 필요하면 `args-json`을 사용합니다:

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json`과 legacy `args`는 상호 배타적입니다. Legacy `args`는 첫 줄의 공백만 분할하며 어느 input도 shell evaluation을 거치지 않습니다.

## 기존 부채를 안전하게 도입

Baseline은 검토 가능한 debt register이지 ignore list가 아닙니다. Finding을 new, known, repaired로 분류합니다:

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined`는 known debt, `resolved_baseline`은 repaired entry입니다. Check는 정리가 필요하면 `9`로 종료하고, prune은 repaired entry만 atomic하게 제거하며 새 finding을 기록하지 않습니다.

HIGH security finding은 baseline 대상이 아닙니다. 일반 malformed baseline은 아무것도 억제하지 않으며, 명시적 check/prune은 fail closed하고 쓰지 않습니다.

## 명령 가이드

| 명령 | 용도 | 기본적으로 쓰나요? |
|---|---|---:|
| `scan` | 전체 checkup, security, gaps, conflicts, semantics, project snapshot. | 아니요 |
| `explain` | 한 경로의 effective instruction chain과 diagnostic scope. | 아니요 |
| `plan` | 검토 가능한 consolidation plan. | 출력 경로가 있을 때만 |
| `validate` | Canonical path, size, required sections, unresolved draft markers. | 아니요 |
| `stubs` | Minimal tool pointer preview/apply. | 아니요 |
| `drift` | D1–D8, health, baseline lifecycle, 안전한 D3 repair. | 아니요 |
| `guard` | Pre-commit 및 CI guard 설치/제거. | 아니요 |
| `review` | Scan/drift report에서 GitHub PR review 생성/게시. | `--post`일 때만 |
| `eval` | Efficacy task 생성, 실행, 비교, regrade, score, trend. | 출력 flag에 따라 다름 |
| `mcp` | Read-only MCP stdio server 시작. | 아니요 |
| `doctor` | Node/Python runtime 및 packaged engine 검증. | 아니요 |

전체 옵션과 동작은 `npx ai-harness-doctor help` 또는 [`SKILL.md`](SKILL.md)를 확인하세요.

## 지원 surface

| Surface | 지원 |
|---|---|
| Claude Code | Native skill과 slash commands. |
| OpenAI Codex CLI | Prompt adapters. |
| Cursor | Project/user command adapters. |
| Gemini CLI | Enterprise/기존 설치용 TOML command adapters. |
| MCP clients | JSON-RPC stdio를 통한 7개 read-only tool. |
| GitHub Actions | Composite Action, SARIF, Job Summary, outputs, PR feedback. |
| GitLab / Codebase | 공통 scan, drift, optional eval gates. |
| 기타 agents | Playbook을 가리키는 universal pointer. |

Non-Claude adapter는 의도적으로 얇습니다. 폭넓은 rule distribution은 Ruler/rulesync의 역할이며, 이 프로젝트는 diagnosis, evidence, safety, drift, efficacy에 집중합니다.

## 안전 모델

- Scan은 read-only이며 저장소에서 파생된 external symlink를 제외합니다.
- 저장소 `.gitignore`가 제외한 missing path는 의도된 runtime path로 처리합니다. Synthetic Git metadata는 local/global rule을 배제하며 Git failure 시 finding을 유지합니다.
- Nested drift는 command, path, runtime/package-manager fact를 lexical package ancestor에서 해석하며 sibling package를 검색하지 않습니다. Markdown link는 계속 file-relative입니다.
- Write path는 symlinked file 또는 기존 parent directory를 거부합니다.
- Plugin은 `--allow-plugins`를 명시한 경우에만 활성화됩니다.
- Secret finding은 값 대신 유형/경로만 보고하며 위험한 hook snippet은 JSON, Markdown, SARIF, PR feedback에서 redacted됩니다.
- Installer mutation은 lock, journal, ownership, recovery를 사용합니다.
- MCP tool은 read-only이며 finding은 transport failure가 아닙니다.
- External judge와 real LLM grading은 opt-in입니다. 원격 endpoint는 HTTPS가 필요하고 loopback HTTP만 명시적으로 허용되며 redirect는 거부되고 실패 시 deterministic judge로 fallback합니다.
- Eval 결과 artifact는 runner/judge 진단과 matrix runner template의 신뢰도 높은 credential을 redacted 처리하며 grading은 메모리의 원본 bounded output을 계속 사용합니다.
- Telemetry는 없습니다. `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`로 npm update check를 끌 수 있습니다.

## 증거와 benchmark

| 구분 | 통과 | 불안정 task | 평균 latency/task | 기록된 cost |
|---|---:|---:|---:|---:|
| Before: 충돌/오래된 config | 6/28 | 2 | 16.0s | $5.82 |
| After: canonical `AGENTS.md` | 28/28 | 0 | 11.7s | $4.81 |

방법과 재현은 [`benchmark/README.md`](benchmark/README.md)를 참고하세요. 하나의 demo 저장소에서 양쪽을 두 번 실행한 증거이며 보편적 성능 보장은 아닙니다.

## 문서 지도

| 문서 | 목적 |
|---|---|
| [`SKILL.md`](SKILL.md) | 전체 4단계 동작 및 명령 계약. |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | 적절한 마이그레이션 경로 선택. |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | 사람의 판정 workflow. |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Tool-file 지원과 ownership. |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Baseline, Action, guard, CI, release, installer invariants. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 기여 workflow와 checks. |
| [`RELEASING.md`](RELEASING.md) | Tag 기반 npm, GitHub Release, floating Action tag, Marketplace. |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | 실제 저장소 read-only validation. |

## 프로젝트 상태

- Python 3.9+, Node 16+, runtime은 표준 라이브러리만 사용.
- npm release는 provenance가 있는 tag-driven 방식.
- Stable release는 floating major Action tag(`1.x`의 `v1`)를 이동.
- Feature는 minor, bugfix-only는 patch.
- 공개 동작 변경은 같은 PR에서 모든 공개 언어 문서를 동기화해야 합니다.

## 기여

Issue와 PR을 환영합니다. [`CONTRIBUTING.md`](CONTRIBUTING.md)를 읽고, 동작 변경에는 테스트를 추가하며, 같은 PR에서 모든 번역 README를 갱신하세요.

보안 취약점은 공개 issue 대신 [`SECURITY.md`](SECURITY.md)를 따르세요.

## 라이선스

[MIT](LICENSE)
