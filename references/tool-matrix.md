# Tool matrix

Use this table during Phase 1 — Treat to decide which files should be downgraded to stubs. Capabilities and limits follow official documentation; uncertain entries are explicitly marked.

## Claude Code

- Read files: repository `CLAUDE.md`, `.claude/CLAUDE.md`, and recursively discovered `.claude/rules/**/*.md`; user-level or parent-level configuration stays outside the audited repository.
- Import/reference: supports `@path` file references.
- Priority/merge order: follow the official Claude Code resolution order.
- Size limits: follow official documentation.
- Structured rules: no-frontmatter project rules are always-on; `paths` block/inline string lists select project-relative glob targets. External shared-rule symlinks remain outside the audit boundary.
- Downgrade strategy: put `@AGENTS.md` on the first line of `CLAUDE.md`, followed by a minimal comment; do not copy the body or rewrite recursively discovered `.claude/rules/`.

## Codex

- Read files: `AGENTS.md`, including root and local subdirectory files.
- Import/reference: follow official documentation; this skill does not depend on imports.
- Priority/merge order: usually applied by directory hierarchy, with rules closer to the working directory being more specific; follow official documentation.
- Size limits: `project_doc_max_bytes` commonly defaults to 32KB, and oversized files may be truncated from context.
- Downgrade strategy: keep root `AGENTS.md` as the single source of truth; monorepos may keep local subdirectory `AGENTS.md` files.

## Cursor

- Read files: legacy `.cursorrules`; newer `.cursor/rules/*.mdc` or `.md` files.
- Import/reference: rule capabilities vary by Cursor version; follow official documentation.
- Priority/merge order: follow official documentation for project and global rule merging.
- Size limits: follow official documentation.
- Downgrade strategy: write a pointer in `.cursorrules`; under `.cursor/rules/`, keep a single `agents-md.mdc` with `alwaysApply: true` that points to `AGENTS.md`.

## Windsurf

- Read files: `.windsurfrules`, `.windsurf/rules/*`.
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: keep a minimal pointer saying all rules live in `AGENTS.md`.

## GitHub Copilot

- Read files: `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`.
- Import/reference: this skill does not depend on imports and assumes `AGENTS.md` cannot be safely imported.
- Priority/merge order: follow official GitHub Copilot documentation.
- Size limits: follow official documentation.
- Downgrade strategy: keep a very short pointer note and remind maintainers not to copy rule bodies.

## Gemini CLI

- Read files: commonly `GEMINI.md`; the context filename can be configured.
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: write a pointer in `GEMINI.md` and recommend configuring `contextFileName=AGENTS.md`.

## Cline

- Read files: `.clinerules` file or rule files under a `.clinerules/` directory.
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: keep a minimal pointer; complex directory rules require human confirmation before migration.

## Roo

- Read files: `.roo/rules/*.md`, `.roo/rules/*.mdc`, and similar files.
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: v1 mainly scans and reports; whether to downgrade to a pointer requires human confirmation.

## Continue

- Read files: legacy `.continuerules` single file; current `.continue/rules/*.md` directory (loaded in lexicographical order).
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: write a pointer in `.continuerules`; `.continue/rules/*.md` is detected and reported but not automatically collapsed, the same treatment as Cursor's `.cursor/rules/`.

## Trae

- Read files: `.trae/rules/project_rules.md` (project-scoped); `.trae/rules/user_rules.md` is personal/global and intentionally not treated as a repo config file.
- Import/reference: follow official documentation.
- Priority/merge order: follow official documentation.
- Size limits: follow official documentation.
- Downgrade strategy: scans and reports only; no single conventional stub-file location exists to downgrade to, so it stays scan-only like Roo.
