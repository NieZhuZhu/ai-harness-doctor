[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Español](README.es.md) | [한국어](README.ko.md) | [Português (Brasil)](README.pt-BR.md) | **Français**

# 🩺 AI Harness Doctor

**Votre agent de code peut sembler sûr de lui tout en suivant des consignes obsolètes.** AI Harness Doctor audite `AGENTS.md`, `CLAUDE.md`, les règles Cursor, les hooks, les réglages MCP et les autres fichiers du harness.

Il détecte la dérive avant une PR cassée, consolide les règles dans un `AGENTS.md` humain, garde de petits pointeurs et mesure si le harness améliore les réponses.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> Dans le benchmark inclus, la canonicalisation a fait passer les bonnes réponses de **6/28 à 28/28**, supprimé les hésitations, réduit la latence moyenne de 27 % et le coût enregistré de 17 %.

## Démarrer en 60 secondes

Lancez un checkup en lecture seule, sans installation :

```bash
npx ai-harness-doctor scan .
```

Expliquez quelles instructions s’appliquent à un chemin :

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Vérifiez les runtimes Node et Python :

```bash
npx ai-harness-doctor doctor --self-test
```

Aucune de ces commandes ne modifie le dépôt audité.

## Ce qui est vérifié

| Domaine | Ce que le doctor recherche |
|---|---|
| Inventaire | Fichiers canoniques, règles, scopes imbriqués, MCP, hooks, commandes, permissions et sous-agents. |
| Sécurité | Secrets en clair, permissions trop larges, transports MCP non sûrs, hooks dangereux et contournements. |
| Cohérence | Scripts absents, chemins déplacés, drift du gestionnaire/runtime, liens cassés et lockfiles concurrents. |
| Qualité des instructions | Contexte excessif, copie du README, arbitrage silencieux, chevauchements et conflits locaux. |
| Scope | Héritage jusqu’au `AGENTS.md` le plus proche et globs bornés de Claude, Cursor et Copilot. |
| Efficacité | Exactitude avant/après, stabilité, latence, coût, fraîcheur des preuves et note de santé. |

Les lectures de sécurité restent dans le dépôt. Les gros fichiers conservent une couverture complète de SHA-256, lignes, secrets et bypass ; `--max-bytes` ne limite que l’analyse sémantique.

## Les quatre phases

| Phase | Objectif | Commandes principales | Point d’arrêt humain |
|---|---|---|---|
| 0 — Checkup | Découvrir risques, conflits, lacunes et faits du dépôt. | `scan`, `explain` | Confirmer le périmètre de migration. |
| 1 — Treat | Créer un plan et consolider la documentation canonique. | `plan`, `validate`, `stubs` | Arbitrer chaque conflit sémantique. |
| 2 — Follow-up | Empêcher commandes, chemins, liens, stubs et faits de redevenir obsolètes. | `drift`, `guard`, `review` | Décider si le code ou la règle est faux. |
| 3 — Efficacy | Mesurer si le harness améliore l’agent. | `eval` | Décider si les preuves suffisent. |

Les scripts n’exécutent que des opérations déterministes. Ils ne choisissent pas npm contre pnpm, ne tranchent pas une commande contestée et ne fusionnent pas la prose sans revue.

## Consolider un dépôt

Créez un plan révisable, écrivez `AGENTS.md`, validez-le puis remplacez les fichiers dupliqués par de petits pointeurs :

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Vous pouvez aussi installer le skill Claude Code et lancer `/harness-doctor .` ou `/harness-treat .`. L’agent s’arrête lorsque la vérité du dépôt est ambiguë.

## Installer et mettre à jour

| Objectif | Commande |
|---|---|
| Installer le skill Claude Code pour l’utilisateur | `npx ai-harness-doctor install` |
| Installer les prompts Codex | `npx ai-harness-doctor install --agent codex` |
| Installer les commandes Cursor dans un dépôt | `npx ai-harness-doctor install --agent cursor --project` |
| Installer tous les adapters dans un dépôt | `npx ai-harness-doctor install --agent all --project` |
| Redéployer le dernier package | `npx ai-harness-doctor@latest update` |
| Supprimer les adapters installés | `npx ai-harness-doctor uninstall --agent all` |

Les installations copiées suivent la propriété. Update et uninstall préservent les collisions étrangères et les fichiers modifiés. Les tests utilisent toujours un `HOME` isolé.

## Le garder sain dans la CI

Installez des guards pour pre-commit, pull requests et contrôles planifiés :

```bash
npx ai-harness-doctor guard . --apply
```

Le guard GitHub combine scan et drift dans une revue de PR. Les findings localisés deviennent des commentaires inline ; le résumé contient sévérité, santé, preuves, correction et priorités.

Vous utilisez déjà le framework pre-commit ?

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.12.0
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

Le checkup hebdomadaire maintient un seul issue détenu et le ferme après récupération. Consultez [`references/maintenance-contract.md`](references/maintenance-contract.md) pour le contrat de maintenance.

## GitHub Action et SARIF

L’Action Marketplace exécute par défaut le code inclus dans le ref et produit SARIF, des outputs et un Job Summary :

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

Les outputs incluent `status`, les comptes de sévérité, `finding-count`, `resolved-baseline-count` et `health-score` / `health-grade` pour drift.

La priorité est `findings > maintenance > ok`. Un gate non nul valide publie SARIF et le résumé avant de restaurer l’exit code exact.

Les résultats SARIF ont des fingerprints stables et des catégories scan/drift séparées, évitant les doublons et les fermetures croisées.

Utilisez `args-json` lorsqu’une valeur contient des espaces ou exige des frontières argv exactes/répétées :

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json` et l’ancien `args` sont exclusifs. `args` sépare seulement les espaces de la première ligne ; aucun input n’est évalué par le shell.

## Adopter la dette existante en sécurité

Les baselines sont des registres de dette révisables, pas des listes d’ignore. Elles classent les findings en new, known ou repaired :

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` contient la dette known et `resolved_baseline` les entrées réparées. Check sort avec `9` si un nettoyage est nécessaire ; prune supprime seulement le réparé et n’enregistre jamais de nouvelle dette.

Les findings HIGH de sécurité ne sont jamais éligibles. Une baseline malformée ne supprime rien ; check/prune explicites échouent fermés sans écrire.

## Guide des commandes

| Commande | Usage | Écrit par défaut ? |
|---|---|---:|
| `scan` | Checkup complet, sécurité, gaps, conflits, sémantique et snapshot. | Non |
| `explain` | Chaîne d’instructions et scope pour un chemin. | Non |
| `plan` | Plan de consolidation révisable. | Seulement avec chemin de sortie |
| `validate` | Chemin canonique, taille, sections et marqueurs draft. | Non |
| `stubs` | Prévisualiser ou appliquer des pointeurs minimaux. | Non |
| `drift` | D1–D8, santé, cycle de baseline et réparation D3 sûre. | Non |
| `guard` | Installer ou retirer les guards pre-commit et CI. | Non |
| `review` | Créer ou publier une revue PR depuis scan/drift. | Seulement avec `--post` |
| `eval` | Générer, exécuter, comparer, regrader, noter et suivre les tendances. | Selon les flags |
| `mcp` | Démarrer le serveur MCP stdio en lecture seule. | Non |
| `doctor` | Valider les runtimes et moteurs empaquetés. | Non |

Lancez `npx ai-harness-doctor help` ou consultez [`SKILL.md`](SKILL.md) pour la référence complète.

## Surfaces prises en charge

| Surface | Support |
|---|---|
| Claude Code | Skill natif et slash commands. |
| OpenAI Codex CLI | Prompt adapters. |
| Cursor | Command adapters projet ou utilisateur. |
| Gemini CLI | Adapters TOML pour installations enterprise/existantes. |
| Clients MCP | Sept outils en lecture seule via JSON-RPC stdio. |
| GitHub Actions | Composite Action, SARIF, Job Summary, outputs et feedback PR. |
| GitLab / Codebase | Gates partagés scan, drift et eval optionnel. |
| Autres agents | Pointeur universel vers le playbook. |

Les adapters non Claude sont volontairement légers. La distribution massive appartient à Ruler/rulesync ; ce projet se concentre sur diagnostic, preuve, sécurité, drift et efficacité.

## Modèle de sécurité

- Scan est en lecture seule et exclut les symlinks externes dérivés du dépôt.
- Les chemins absents ignorés par le `.gitignore` du dépôt sont des runtime paths volontaires ; des metadata Git synthétiques excluent les règles locales/globales et une panne Git conserve le finding.
- Un `org/name` entre backticks que des mots adjacents étiquettent comme image Docker/OCI ou méthode RPC/API est traité comme runtime identifier, pas comme chemin vérifié ; l'exclusion est fail-closed et les tokens avec extension ou de trois segments ou plus restent des chemins.
- Nested drift résout commands, paths et facts runtime/package manager via les ancestors lexicaux sans chercher les packages frères ; les liens Markdown restent relatifs au fichier.
- Les chemins d’écriture refusent les fichiers ou parents symlinked.
- Les plugins ne s’activent qu’avec `--allow-plugins`.
- Les findings de secrets indiquent type/chemin sans reproduire la valeur ; les hooks dangereux sont expurgés dans JSON, Markdown, SARIF et les retours PR.
- L’installateur utilise lock, journal, propriété et récupération.
- Les outils MCP restent en lecture seule ; un finding n’est pas une erreur de transport.
- Les juges externes et LLM réels sont opt-in. Les endpoints distants exigent HTTPS, HTTP est réservé au loopback, les redirections sont refusées et les échecs reviennent au juge déterministe.
- Les artefacts de résultats eval expurgent les identifiants à haute confiance des diagnostics runner/judge et templates matrix ; le grading utilise encore en mémoire la sortie bornée originale.
- Aucune télémétrie. Désactivez le contrôle npm avec `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`.

## Preuves et benchmark

| Côté | Réussites | Tâches instables | Latence moyenne/tâche | Coût enregistré |
|---|---:|---:|---:|---:|
| Avant : configs conflictuelles/obsolètes | 6/28 | 2 | 16.0s | $5.82 |
| Après : `AGENTS.md` canonique | 28/28 | 0 | 11.7s | $4.81 |

Voir [`benchmark/README.md`](benchmark/README.md) pour la méthode et la reproduction. C’est une preuve sur un dépôt de démonstration avec deux runs par côté, pas une promesse universelle.

## Carte de la documentation

| Document | Rôle |
|---|---|
| [`SKILL.md`](SKILL.md) | Contrat complet des quatre phases et commandes. |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | Choisir la voie de migration. |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | Workflow d’arbitrage humain. |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Support et propriété des fichiers. |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Invariants baseline, Action, guard, CI, release et installer. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Workflow de contribution et checks. |
| [`RELEASING.md`](RELEASING.md) | npm par tags, GitHub Release, Action flottante et Marketplace. |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | Validations en lecture seule sur de vrais dépôts. |

## État du projet

- Python 3.9+ et Node 16+, runtime uniquement en bibliothèque standard.
- Releases npm pilotées par tags avec provenance.
- Les releases stables déplacent le tag Action majeur flottant (`v1` pour `1.x`).
- Les features utilisent minor ; les bugfix-only utilisent patch.
- Tout changement public doit synchroniser la documentation dans toutes les langues publiées.

## Contribuer

Issues et PR sont bienvenus. Lisez [`CONTRIBUTING.md`](CONTRIBUTING.md), ajoutez des tests aux changements de comportement et mettez à jour tous les README traduits dans la même PR.

Pour une vulnérabilité, suivez [`SECURITY.md`](SECURITY.md) au lieu d’ouvrir un issue public.

## Licence

[MIT](LICENSE)
