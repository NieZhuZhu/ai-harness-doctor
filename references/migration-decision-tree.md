# Migration decision tree

## 1. Determine the scope first

- Root configuration files only: prefer a whole-repository migration to root `AGENTS.md`.
- Multiple subprojects with different commands, owners, or stacks: put global rules in root `AGENTS.md` and keep local `AGENTS.md` files for subdirectories.
- The user cares about only some tools: migrate only the selected files and mark the rest as deferred in the report.

## 2. Decide whether to keep local files

Keep a local `AGENTS.md` when:

- The subdirectory has independent build and test commands.
- The subdirectory rules materially differ from the root rules.
- The subdirectory owner explicitly requires local rules.

Do not keep it when:

- The content only copies root rules.
- The content is stale and no owner can be found.
- It would make agent read paths ambiguous.

## 3. When to keep tool stubs

- The tool must read its own fixed filename.
- The tool cannot read `AGENTS.md` directly.
- The team still uses the tool and needs a minimal pointer reminder.

## 4. When to abandon migration

- Conflicts cannot be adjudicated and affect build, test, or safety boundaries.
- The target repository is not a git repository and the user does not allow `--force`.
- The worktree is dirty, so git cannot provide a rollback mechanism.
- The configuration contains sensitive information that the owner must clean up first.
