[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Español](README.es.md) | [한국어](README.ko.md) | **Português (Brasil)** | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**Seu agente de programação pode parecer confiante enquanto segue instruções antigas.** O AI Harness Doctor audita `AGENTS.md`, `CLAUDE.md`, regras do Cursor, hooks, configurações MCP e outros arquivos do harness.

Ele encontra o drift antes de um PR quebrado, consolida orientações em um `AGENTS.md` humano, mantém ponteiros pequenos e mede se o harness melhora as respostas.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> No benchmark incluído, a canonicalização elevou as respostas corretas de **6/28 para 28/28**, eliminou oscilações, reduziu a latência média em 27% e o custo registrado em 17%.

## Comece em 60 segundos

Execute um checkup somente leitura sem instalar nada:

```bash
npx ai-harness-doctor scan .
```

Explique quais instruções se aplicam a um caminho:

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Verifique os runtimes Node e Python:

```bash
npx ai-harness-doctor doctor --self-test
```

Nenhum desses comandos altera o repositório auditado.

## O que ele verifica

| Área | O que o doctor procura |
|---|---|
| Inventário | Arquivos canônicos, regras, scopes aninhados, MCP, hooks, comandos, permissões e subagentes. |
| Segurança | Segredos em texto, permissões amplas, transportes MCP inseguros, hooks perigosos e bypasses. |
| Consistência | Scripts ausentes, caminhos movidos, drift de gerenciador/runtime, links quebrados e lockfiles concorrentes. |
| Qualidade das instruções | Contexto excessivo, cópia do README, decisão silenciosa, sobreposição e conflito no mesmo scope. |
| Scope | Herança até o `AGENTS.md` mais próximo e globs limitados de Claude, Cursor e Copilot. |
| Eficácia | Correção antes/depois, estabilidade, latência, custo, frescor da evidência e nota de saúde. |

As leituras de segurança ficam dentro do repositório. Arquivos grandes mantêm cobertura completa de SHA-256, linhas, segredos e bypasses; `--max-bytes` limita apenas a análise semântica.

## As quatro fases

| Fase | Objetivo | Comandos principais | Ponto de decisão humana |
|---|---|---|---|
| 0 — Checkup | Descobrir riscos, conflitos, lacunas e fatos do repositório. | `scan`, `explain` | Confirmar o escopo da migração. |
| 1 — Treat | Criar um plano e consolidar a orientação canônica. | `plan`, `validate`, `stubs` | Resolver cada conflito semântico. |
| 2 — Follow-up | Impedir que comandos, caminhos, links, stubs e fatos envelheçam de novo. | `drift`, `guard`, `review` | Decidir se o código ou a orientação está errado. |
| 3 — Efficacy | Medir se o harness melhora o comportamento do agente. | `eval` | Decidir se a evidência é suficiente. |

Os scripts realizam apenas mecânica determinística. Eles não escolhem npm em vez de pnpm, não resolvem comandos disputados nem fazem merge semântico de prosa sem revisão.

## Consolidar um repositório

Crie um plano revisável, escreva `AGENTS.md`, valide e substitua arquivos duplicados por ponteiros mínimos:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Você também pode instalar o skill do Claude Code e executar `/harness-doctor .` ou `/harness-treat .`. O agente para quando a verdade do repositório é ambígua.

## Instalação e atualização

| Objetivo | Comando |
|---|---|
| Instalar o skill do Claude Code para o usuário | `npx ai-harness-doctor install` |
| Instalar prompts do Codex | `npx ai-harness-doctor install --agent codex` |
| Instalar comandos do Cursor no repositório | `npx ai-harness-doctor install --agent cursor --project` |
| Instalar todos os adapters no repositório | `npx ai-harness-doctor install --agent all --project` |
| Redistribuir o pacote mais recente | `npx ai-harness-doctor@latest update` |
| Remover adapters instalados | `npx ai-harness-doctor uninstall --agent all` |

Instalações copiadas registram propriedade. Update e uninstall preservam colisões alheias e arquivos editados. Testes sempre usam um `HOME` isolado.

## Manter saudável no CI

Instale guards para pre-commit, pull requests e checagens agendadas:

```bash
npx ai-harness-doctor guard . --apply
```

O guard do GitHub combina scan e drift em uma revisão de PR. Achados localizados viram comentários inline; o resumo inclui severidade, saúde, evidência, reparo e prioridades.

Já usa o framework pre-commit?

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.3.0
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

O checkup semanal mantém um único issue próprio e o fecha após a recuperação. Consulte [`references/maintenance-contract.md`](references/maintenance-contract.md) para o contrato de manutenção.

## GitHub Action e SARIF

A Action do Marketplace executa por padrão o código incluído no ref e produz SARIF, outputs e Job Summary:

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

Os outputs incluem `status`, contagens por severidade, `finding-count`, `resolved-baseline-count` e `health-score` / `health-grade` para drift.

A prioridade é `findings > maintenance > ok`. Um gate válido publica SARIF e o resumo antes de restaurar o exit code exato.

Resultados SARIF usam fingerprints estáveis e categorias separadas para scan/drift, evitando alertas duplicados e fechamentos cruzados.

## Adotar dívida existente com segurança

Baselines são registros revisáveis de dívida, não listas de ignore. Classificam achados como new, known ou repaired:

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` contém dívida known; `resolved_baseline`, entradas reparadas. Check sai com `9` quando é preciso limpar; prune remove só o que foi reparado e nunca registra dívida nova.

Achados HIGH de segurança nunca entram no baseline. Um baseline malformado não suprime nada; check/prune explícitos falham fechados sem escrever.

## Guia de comandos

| Comando | Para que serve | Escreve por padrão? |
|---|---|---:|
| `scan` | Checkup completo, segurança, gaps, conflitos, semântica e snapshot. | Não |
| `explain` | Cadeia efetiva de instruções e scope para um caminho. | Não |
| `plan` | Plano de consolidação revisável. | Só com caminho de saída |
| `validate` | Caminho canônico, tamanho, seções e marcadores draft. | Não |
| `stubs` | Visualizar ou aplicar ponteiros mínimos. | Não |
| `drift` | D1–D8, saúde, ciclo de baseline e reparo D3 seguro. | Não |
| `guard` | Instalar ou remover guards de pre-commit e CI. | Não |
| `review` | Criar ou publicar revisão de PR a partir de scan/drift. | Só com `--post` |
| `eval` | Gerar, executar, comparar, reavaliar, pontuar e mostrar tendências. | Depende dos flags |
| `mcp` | Iniciar o servidor MCP stdio somente leitura. | Não |
| `doctor` | Validar runtimes e motores empacotados. | Não |

Execute `npx ai-harness-doctor help` ou consulte [`SKILL.md`](SKILL.md) para a referência completa.

## Superfícies suportadas

| Superfície | Suporte |
|---|---|
| Claude Code | Skill nativo e slash commands. |
| OpenAI Codex CLI | Prompt adapters. |
| Cursor | Command adapters de projeto ou usuário. |
| Gemini CLI | Adapters TOML para instalações enterprise/existentes. |
| Clientes MCP | Sete ferramentas somente leitura via JSON-RPC stdio. |
| GitHub Actions | Composite Action, SARIF, Job Summary, outputs e feedback de PR. |
| GitLab / Codebase | Gates compartilhados de scan, drift e eval opcional. |
| Outros agentes | Ponteiro universal para o playbook. |

Adapters não Claude são deliberadamente finos. Distribuição ampla cabe ao Ruler/rulesync; este projeto foca diagnóstico, evidência, segurança, drift e eficácia.

## Modelo de segurança

- Scan é somente leitura e exclui symlinks externos derivados do repositório.
- Caminhos de escrita rejeitam arquivos ou pais symlinked.
- Plugins só são ativados com `--allow-plugins`.
- Achados de segredo informam tipo/caminho sem repetir valores; hooks perigosos são redigidos em JSON, Markdown, SARIF e feedback de PR.
- O instalador usa lock, journal, propriedade e recuperação.
- Ferramentas MCP são somente leitura; finding não é falha de transporte.
- Juízes externos e LLM reais são opt-in. Endpoints remotos exigem HTTPS, HTTP só é permitido em loopback, redirects são recusados e falhas voltam ao juiz determinístico.
- Sem telemetria. Desative o check npm com `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`.

## Evidência e benchmark

| Lado | Acertos | Tarefas instáveis | Latência média/tarefa | Custo registrado |
|---|---:|---:|---:|---:|
| Antes: configs em conflito/obsoletas | 6/28 | 2 | 16.0s | $5.82 |
| Depois: `AGENTS.md` canônico | 28/28 | 0 | 11.7s | $4.81 |

Consulte [`benchmark/README.md`](benchmark/README.md) para metodologia e reprodução. É evidência de um repositório demo com duas execuções por lado, não uma promessa universal.

## Mapa da documentação

| Documento | Finalidade |
|---|---|
| [`SKILL.md`](SKILL.md) | Contrato completo das quatro fases e comandos. |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | Escolher a rota de migração. |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | Fluxo de decisão humana. |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Suporte e propriedade de arquivos. |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Invariantes de baseline, Action, guard, CI, release e installer. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Fluxo de contribuição e checks. |
| [`RELEASING.md`](RELEASING.md) | npm por tags, GitHub Release, Action flutuante e Marketplace. |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | Validações somente leitura em repositórios reais. |

## Estado do projeto

- Python 3.9+ e Node 16+, runtime apenas com biblioteca padrão.
- Releases npm por tags com provenance.
- Releases estáveis movem a tag maior flutuante (`v1` para `1.x`).
- Features usam minor; bugfix-only usa patch.
- Mudanças públicas exigem documentação sincronizada em todos os idiomas publicados.

## Contribuir

Issues e PRs são bem-vindos. Leia [`CONTRIBUTING.md`](CONTRIBUTING.md), adicione testes para mudanças de comportamento e atualize todos os README traduzidos no mesmo PR.

Para vulnerabilidades, siga [`SECURITY.md`](SECURITY.md) em vez de abrir um issue público.

## Licença

[MIT](LICENSE)
