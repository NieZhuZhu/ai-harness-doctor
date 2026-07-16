[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **Español** | [한국어](README.ko.md) | [Português (Brasil)](README.pt-BR.md) | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**Tu agente de programación puede parecer seguro mientras sigue instrucciones obsoletas.** AI Harness Doctor audita `AGENTS.md`, `CLAUDE.md`, reglas de Cursor, hooks, ajustes MCP y otros archivos del harness.

Detecta el desvío antes de que termine en un PR roto. También consolida reglas dispersas en un `AGENTS.md` humano, conserva punteros pequeños y mide si el harness mejora las respuestas.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> En el benchmark incluido, la canonicalización elevó las respuestas correctas de **6/28 a 28/28**, eliminó inconsistencias, redujo la latencia media un 27% y el coste registrado un 17%.

## Empieza en 60 segundos

Ejecuta un chequeo de solo lectura sin instalar nada:

```bash
npx ai-harness-doctor scan .
```

Explica qué instrucciones se aplican a una ruta:

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Comprueba los runtimes de Node y Python:

```bash
npx ai-harness-doctor doctor --self-test
```

Ninguno de estos comandos modifica el repositorio auditado.

## Qué comprueba

| Área | Qué busca el doctor |
|---|---|
| Inventario | Archivos canónicos, reglas, scopes anidados, MCP, hooks, comandos, permisos y subagentes. |
| Seguridad | Secretos en texto plano, permisos amplios, transportes MCP inseguros, hooks peligrosos y bypasses. |
| Consistencia | Scripts ausentes, rutas movidas, drift de gestor o runtime, enlaces rotos y lockfiles rivales. |
| Calidad de instrucciones | Contexto excesivo, copias del README, decisiones silenciosas, solapamientos y conflictos locales. |
| Scope | Herencia hasta el `AGENTS.md` más cercano y globs acotados de Claude, Cursor y Copilot. |
| Eficacia | Exactitud antes/después, estabilidad, latencia, coste, frescura de evidencia y nota de salud. |

Las lecturas de seguridad permanecen dentro del repositorio. Los archivos grandes conservan cobertura completa de SHA-256, líneas, secretos y bypasses; `--max-bytes` solo limita el análisis semántico.

## Las cuatro fases

| Fase | Objetivo | Comandos principales | Punto de decisión humana |
|---|---|---|---|
| 0 — Checkup | Descubrir riesgos, conflictos, carencias y hechos del repositorio. | `scan`, `explain` | Confirmar el alcance de migración. |
| 1 — Treat | Crear un plan y consolidar la guía canónica. | `plan`, `validate`, `stubs` | Resolver cada conflicto semántico. |
| 2 — Follow-up | Evitar que comandos, rutas, enlaces, stubs y hechos vuelvan a caducar. | `drift`, `guard`, `review` | Decidir si falla el código o la guía. |
| 3 — Efficacy | Medir si el harness mejora el comportamiento del agente. | `eval` | Decidir si la evidencia basta. |

Los scripts solo realizan mecánica determinista. Nunca eligen npm frente a pnpm, resuelven comandos disputados ni fusionan prosa semánticamente sin revisión.

## Consolidar un repositorio

Crea un plan revisable, escribe `AGENTS.md`, valídalo y sustituye los archivos duplicados por punteros mínimos:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

También puedes instalar el skill de Claude Code y ejecutar `/harness-doctor .` o `/harness-treat .`. El agente se detiene cuando la verdad del repositorio es ambigua.

## Instalar y actualizar

| Objetivo | Comando |
|---|---|
| Instalar el skill de Claude Code para el usuario | `npx ai-harness-doctor install` |
| Instalar prompts de Codex | `npx ai-harness-doctor install --agent codex` |
| Instalar comandos de Cursor en un repositorio | `npx ai-harness-doctor install --agent cursor --project` |
| Instalar todos los adapters en un repositorio | `npx ai-harness-doctor install --agent all --project` |
| Volver a desplegar el paquete más reciente | `npx ai-harness-doctor@latest update` |
| Eliminar adapters instalados | `npx ai-harness-doctor uninstall --agent all` |

Las instalaciones copiadas registran propiedad. Update y uninstall conservan colisiones ajenas y archivos editados. Las pruebas usan siempre un `HOME` aislado.

## Mantenerlo sano en CI

Instala guards para pre-commit, pull requests y comprobaciones programadas:

```bash
npx ai-harness-doctor guard . --apply
```

El guard de GitHub combina scan y drift en una revisión de PR. Los hallazgos localizados se vuelven comentarios inline; el resumen incluye severidad, salud, evidencia, reparación y prioridades.

¿Ya usas el framework pre-commit?

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.11.0
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

El chequeo semanal mantiene un único issue propio y lo cierra al recuperarse. Consulta [`references/maintenance-contract.md`](references/maintenance-contract.md) para el contrato de mantenimiento.

## GitHub Action y SARIF

La Action de Marketplace ejecuta por defecto el código incluido en el ref y produce SARIF, outputs y un Job Summary:

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

Los outputs incluyen `status`, conteos por severidad, `finding-count`, `resolved-baseline-count` y `health-score` / `health-grade` para drift.

La prioridad es `findings > maintenance > ok`. Un gate válido publica SARIF y el resumen antes de restaurar el exit code exacto.

Los resultados SARIF usan fingerprints estables y categorías separadas para scan/drift, evitando alertas duplicadas y cierres cruzados.

Usa `args-json` cuando un valor extra contenga espacios o necesites límites argv exactos/repetidos:

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json` y el `args` legacy son mutuamente excluyentes. `args` solo divide espacios de la primera línea; ninguno se evalúa por shell.

## Adoptar deuda existente con seguridad

Los baselines son registros revisables de deuda, no listas de ignore. Clasifican hallazgos como new, known o repaired:

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` contiene deuda known y `resolved_baseline` entradas reparadas. Check sale con `9` cuando hace falta limpiar; prune elimina solo lo reparado y nunca registra deuda nueva.

Los hallazgos HIGH de seguridad nunca son elegibles. Un baseline malformado no suprime nada; check/prune explícitos fallan cerrados sin escribir.

## Guía de comandos

| Comando | Para qué sirve | ¿Escribe por defecto? |
|---|---|---:|
| `scan` | Chequeo completo, seguridad, gaps, conflictos, semántica y snapshot. | No |
| `explain` | Cadena efectiva de instrucciones y scope para una ruta. | No |
| `plan` | Plan de consolidación revisable. | Solo con ruta de salida |
| `validate` | Ruta canónica, tamaño, secciones y marcadores draft. | No |
| `stubs` | Previsualizar o aplicar punteros mínimos. | No |
| `drift` | D1–D8, salud, ciclo de baseline y reparación D3 segura. | No |
| `guard` | Instalar o quitar guards de pre-commit y CI. | No |
| `review` | Crear o publicar una revisión de PR desde scan/drift. | Solo con `--post` |
| `eval` | Generar, ejecutar, comparar, revaluar, puntuar y mostrar tendencias. | Depende de los flags |
| `mcp` | Iniciar el servidor MCP stdio de solo lectura. | No |
| `doctor` | Validar runtimes y motores empaquetados. | No |

Ejecuta `npx ai-harness-doctor help` o consulta [`SKILL.md`](SKILL.md) para la referencia completa.

## Superficies compatibles

| Superficie | Soporte |
|---|---|
| Claude Code | Skill nativo y slash commands. |
| OpenAI Codex CLI | Prompt adapters. |
| Cursor | Command adapters de proyecto o usuario. |
| Gemini CLI | Adapters TOML para instalaciones enterprise/existentes. |
| Clientes MCP | Siete herramientas de solo lectura por JSON-RPC stdio. |
| GitHub Actions | Composite Action, SARIF, Job Summary, outputs y feedback de PR. |
| GitLab / Codebase | Gates compartidos de scan, drift y eval opcional. |
| Otros agentes | Puntero universal al playbook. |

Los adapters no Claude son deliberadamente finos. La distribución masiva corresponde a Ruler/rulesync; este proyecto se centra en diagnóstico, evidencia, seguridad, drift y eficacia.

## Modelo de seguridad

- Scan es de solo lectura y excluye symlinks externos derivados del repositorio.
- Las rutas ausentes ignoradas por `.gitignore` del repositorio se consideran runtime deliberado; metadata Git sintética excluye reglas locales/globales y un fallo de Git conserva el finding.
- Nested drift resuelve commands, paths y facts de runtime/package manager por ancestors léxicos sin buscar paquetes hermanos; los links Markdown siguen relativos al archivo.
- Las rutas de escritura rechazan archivos o padres symlinked.
- Los plugins solo se activan con `--allow-plugins`.
- Los hallazgos de secretos indican tipo/ruta sin repetir valores; los hooks peligrosos se redactan en JSON, Markdown, SARIF y feedback de PR.
- El instalador usa lock, journal, propiedad y recuperación.
- Las herramientas MCP son de solo lectura; un finding no es un fallo de transporte.
- Jueces externos y LLM reales son opt-in. Los endpoints remotos requieren HTTPS, HTTP solo se permite en loopback, los redirects se rechazan y los fallos vuelven al juez determinista.
- Los resultados eval redactan credenciales de alta confianza en diagnósticos runner/judge y templates matrix; la evaluación aún usa en memoria la salida acotada original.
- No hay telemetría. Desactiva el chequeo npm con `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`.

## Evidencia y benchmark

| Lado | Aciertos | Tareas inestables | Latencia media/tarea | Coste registrado |
|---|---:|---:|---:|---:|
| Antes: configs en conflicto/obsoletas | 6/28 | 2 | 16.0s | $5.82 |
| Después: `AGENTS.md` canónico | 28/28 | 0 | 11.7s | $4.81 |

Consulta [`benchmark/README.md`](benchmark/README.md) para metodología y reproducción. Es evidencia de un repositorio demo con dos ejecuciones por lado, no una promesa universal.

## Mapa de documentación

| Documento | Propósito |
|---|---|
| [`SKILL.md`](SKILL.md) | Contrato completo de las cuatro fases y comandos. |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | Elegir la ruta de migración. |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | Flujo de decisión humana. |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Soporte y propiedad de archivos. |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Invariantes de baseline, Action, guard, CI, release e installer. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Flujo de contribución y checks. |
| [`RELEASING.md`](RELEASING.md) | npm por tags, GitHub Release, Action flotante y Marketplace. |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | Validaciones de solo lectura en repositorios reales. |

## Estado del proyecto

- Python 3.9+ y Node 16+, runtime solo con biblioteca estándar.
- Releases npm por tags con provenance.
- Releases estables mueven la etiqueta mayor flotante (`v1` para `1.x`).
- Features usan minor; bugfix-only usa patch.
- Todo cambio público debe sincronizar la documentación en todos los idiomas publicados.

## Contribuir

Issues y PRs son bienvenidos. Lee [`CONTRIBUTING.md`](CONTRIBUTING.md), añade pruebas para cambios de comportamiento y actualiza todos los README traducidos en el mismo PR.

Para vulnerabilidades, sigue [`SECURITY.md`](SECURITY.md) en lugar de abrir un issue público.

## Licencia

[MIT](LICENSE)
