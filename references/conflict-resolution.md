# Conflict resolution rules

## Conflict categories

### Factual conflicts

Example: one file says `pnpm install` while another says `npm install`; one file says Node 18 while another says Node 20.

Resolution: check manifests, lockfiles, CI, Makefiles, and live code first. Escalate to a human when the facts still do not decide the answer.

### Preference conflicts

Example: single quotes vs double quotes, or 2 spaces vs 4 spaces.

Resolution: prefer formatter and linter configuration. If no machine-readable config exists, ask the owner to decide.

### Stale rules

Example: references to missing directories, removed test frameworks, or old CI commands.

Resolution: cite the evidence and recommend deletion or an update to current facts; still require human confirmation before deletion.

## Resolution principles

1. Machine evidence comes first, but never fabricate a semantic judgment.
2. Escalate safety-related conflicts by default.
3. Commands and paths must be verifiable by the drift guard.
4. Record every decision in the migration plan or PR description.

## Human escalation report format

```markdown
## Conflict: <signal>

- Candidate A: `<value>`
  - Evidence: `path/to/file.md:12` original text
- Candidate B: `<value>`
  - Evidence: `path/to/other.md:8` original text

### Impact

Explain what a wrong choice would affect: install, tests, safety, code style, or agent behavior.

### Recommendation

State the verifiable fact; if the issue is only a preference, write "owner adjudication required".

### Decision needed

- [ ] Choose A
- [ ] Choose B
- [ ] Specify another answer
```
