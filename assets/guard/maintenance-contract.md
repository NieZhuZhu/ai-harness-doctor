<!-- ai-harness-doctor:maintenance-contract:start -->
## Maintenance contract

- When changing build/test commands, directory structure, or conventions, update `AGENTS.md` in the same change.
- Before finishing, run `npx -y ai-harness-doctor drift .` and fix any reported drift.
- Tool stub files (`CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `GEMINI.md`, `.clinerules`, `.github/copilot-instructions.md`) are pointers.
- Never add rules to tool stubs; keep canonical guidance in `AGENTS.md`.
<!-- ai-harness-doctor:maintenance-contract:end -->
