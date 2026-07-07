# 项目概览

This demo repo is a Vite React app used by the ai-harness-doctor benchmark.
The repository reality is authoritative: `package.json`, `.nvmrc`, and the `src/`
tree decide commands and paths when old tool docs disagree.

# Build & test

- Package manager: pnpm 9 (`packageManager` is `pnpm@9.0.0`).
- Install dependencies: `pnpm install`.
- Run tests: `pnpm test`.
- Lint code: `pnpm lint`.
- Build app: `pnpm build`.
- Type-check: `pnpm typecheck`.
- Node.js major version: 20, from `.nvmrc`.
- Test framework: Vitest, via the `test` script.

# 代码规范

- Use TypeScript for source files.
- Keep React components in `src/components/`.
- Keep reusable utilities in `src/utils/`.
- Use 2 spaces for indentation.
- Prefer explicit names and small functions.
- Do not commit generated build output.
- Follow existing package scripts rather than inventing commands.

# Commit 约定

Use conventional commits, for example `feat: add button variant` or
`fix: handle empty date input`.

