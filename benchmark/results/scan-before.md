# Phase 0 — Checkup Report

## Configuration file inventory
| File | Tool | Bytes | Lines | SHA256 |
|---|---:|---:|---:|---|
| `.cursorrules` | Cursor | 1413 | 39 | `d92aaa02520a` |
| `.github/copilot-instructions.md` | GitHub Copilot | 659 | 18 | `c959b6e99d41` |
| `CLAUDE.md` | Claude Code | 1710 | 55 | `1095e35855d3` |

## Size warnings
No size warnings found.

## Overlap candidates
No overlap candidates above 30% were found.

## Conflict candidates
- **package_manager**
  - `pnpm`: .cursorrules:5 `Run lint with `pnpm lint`.`
  - `npm`: .cursorrules:12 `Start the dev server with `npm start`.`; .github/copilot-instructions.md:11 `Treat the app as CommonJS and run development with `npm start`.`; CLAUDE.md:25 `- Run `npm run build` before opening a pull request.`
- **test_command**
  - `jest`: .cursorrules:6 `Run coverage with `jest --coverage`.`; .github/copilot-instructions.md:7 `Run coverage with `jest --coverage`.`; CLAUDE.md:18 `- Run coverage with `jest --coverage`.`
  - `npm test`: .github/copilot-instructions.md:6 `Run the unit tests with `npm run test:unit`.`; CLAUDE.md:17 `- Run the unit tests with `npm run test:unit`.`
- **quote_style**
  - `single`: .cursorrules:8 `Use single quotes for strings.`
  - `double`: .github/copilot-instructions.md:9 `Use double quotes and 4-space indentation.`; CLAUDE.md:39 `- Use double quotes in TypeScript and JSX.`
- **indent_style**
  - `2 spaces`: .cursorrules:9 `Use 2 spaces for indentation.`
  - `4 spaces`: CLAUDE.md:40 `- Use 4 spaces for indentation.`

## Nested AGENTS.md
None.

> Stop condition: confirm the migration scope (whole repository / subdirectory / selected files) before entering Phase 1 — Treat.
