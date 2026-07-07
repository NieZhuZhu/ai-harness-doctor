# Phase 1 — Treat Merge Plan Skeleton

## Inventory
| File | Tool | Bytes | Lines |
|---|---|---:|---:|
| `.cursorrules` | Cursor | 1413 | 39 |
| `.github/copilot-instructions.md` | GitHub Copilot | 659 | 18 |
| `CLAUDE.md` | Claude Code | 1710 | 55 |

## Overlap clusters
- No overlaps above the threshold.

## Conflict list
- **package_manager**
  - `pnpm`
    - .cursorrules:5 `Run lint with `pnpm lint`.`
  - `npm`
    - .cursorrules:12 `Start the dev server with `npm start`.`
    - .github/copilot-instructions.md:11 `Treat the app as CommonJS and run development with `npm start`.`
    - CLAUDE.md:25 `- Run `npm run build` before opening a pull request.`
- **test_command**
  - `jest`
    - .cursorrules:6 `Run coverage with `jest --coverage`.`
    - .github/copilot-instructions.md:7 `Run coverage with `jest --coverage`.`
    - CLAUDE.md:18 `- Run coverage with `jest --coverage`.`
  - `npm test`
    - .github/copilot-instructions.md:6 `Run the unit tests with `npm run test:unit`.`
    - CLAUDE.md:17 `- Run the unit tests with `npm run test:unit`.`
- **quote_style**
  - `single`
    - .cursorrules:8 `Use single quotes for strings.`
  - `double`
    - .github/copilot-instructions.md:9 `Use double quotes and 4-space indentation.`
    - CLAUDE.md:39 `- Use double quotes in TypeScript and JSX.`
- **indent_style**
  - `2 spaces`
    - .cursorrules:9 `Use 2 spaces for indentation.`
  - `4 spaces`
    - CLAUDE.md:40 `- Use 4 spaces for indentation.`

## TODO decision checklist
- [ ] Confirm the migration scope (whole repository / subdirectory / selected files).
- [ ] Record the human adjudication for every conflict.
- [ ] Manually write the root `AGENTS.md`, keeping only information agents cannot infer from code or manifests.
- [ ] Run `canonicalize.py --write-stubs` to preview the downgrade diff.
- [ ] Run `canonicalize.py --validate` to re-check the result.
