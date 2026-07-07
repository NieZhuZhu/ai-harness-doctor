# Project overview

This demo repo is a Vite React app used by the ai-harness-doctor benchmark.
The repository reality is authoritative: `package.json`, `.nvmrc`, and the `src/`
tree decide commands and paths when old tool docs disagree.

# Build & test

- Package manager: pnpm 9 (`packageManager` is `pnpm@9.0.0`).
- Install dependencies: `pnpm install`.
- Start the dev server: `pnpm dev`.
- Run tests: `pnpm test`.
- Lint code: `pnpm lint`.
- Build app: `pnpm build`.
- Type-check: `pnpm typecheck` (`tsc --noEmit`).
- Run coverage: `pnpm coverage`.
- Format code: `pnpm format` (Prettier).
- Node.js major version: 20, from `.nvmrc`.
- Test framework: Vitest, via the `test` script.
- Module type: ESM (`"type": "module"` in `package.json`).
- CI workflow: `.github/workflows/ci.yml`.

# Conventions

- Use TypeScript for source files.
- Keep React components in `src/components/`.
- Keep reusable utilities in `src/utils/`.
- Use 2 spaces for indentation.
- Use single quotes and no semicolons; `.prettierrc` configures Prettier with
  `singleQuote: true` and `semi: false`.
- Keep tests colocated with source as `*.test.tsx` / `*.test.ts`; for example,
  component tests live next to components in `src/components/`.
- Prefer explicit names and small functions.
- Do not commit generated build output.
- Follow existing package scripts rather than inventing commands.

# Commit conventions

Use conventional commits, for example `feat: add button variant` or
`fix: handle empty date input`.
