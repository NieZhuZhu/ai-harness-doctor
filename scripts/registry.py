#!/usr/bin/env python3
"""Loader for the shared agent-config registry (single source of truth).

All knowledge about known AI-agent config files — detection globs, canonical stub
paths and stub content — lives in ``assets/agent-tools.json``. ``scan.py``,
``canonicalize.py`` and ``check_drift.py`` all derive their lists from this module
instead of hardcoding them separately, so adding a new tool is a one-line change to
the JSON. Python 3.9 standard library only; no runtime dependencies.
"""

import json
import os
import re
from pathlib import Path

# scripts/ is a sibling of assets/ under the package root.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _PACKAGE_ROOT / "assets" / "agent-tools.json"

# Single source of truth for the maximum size (in bytes) of a canonical pointer
# stub. A tool file that references AGENTS.md but exceeds this has "regrown" past
# the minimal-pointer budget. Shared by scan.py (gap analysis), check_drift.py
# (D3 drift gate) and canonicalize.py (Phase 1 stub validation) so the threshold
# cannot drift between stages. Reconciled to the value the canonical/writing
# stage (canonicalize.py) already used; genuine minimal stubs are well under it
# (<200 bytes) (CORR-06).
STUB_POINTER_MAX_BYTES = 800

# Single source of truth for the draft-review markers `canonicalize.py --draft`
# inserts and `--validate` flags. Hosted here (not in canonicalize.py, which
# imports scan.py) so scan's maturity ladder can detect an unreviewed draft
# without an import cycle; canonicalize.py aliases these names, so the writer
# and both detectors cannot drift (TD-02).
DRAFT_INFERRED_MARKER = "(inferred — confirm)"
DRAFT_SUGGESTED_MARKER = "(suggested default)"

# Single source of truth for directories a repository walk should never descend
# into: version control internals and build/dependency output that is either
# huge (node_modules), not source the agent should read, or both. Shared by
# scan.py (the main scanner) and facts.py (the fact-reader engines) so a
# repo-wide walk in one module can't drift from the other (TD-02).
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}


def prune_walk_dirs(dirpath, dirnames):
    """In-place ``os.walk`` pruning shared by every repository walk.

    Drops ``SKIP_DIRS`` entries and nested-repository boundaries: a
    subdirectory that carries its own ``.git`` (a submodule working tree or a
    vendored checkout — ``.git`` is a file in the former, a directory in the
    latter) is a different repository, so its instruction files, manifests and
    paths are that repository's harness, not this one's. Scanning a nested
    repository is still supported by passing it as the ``repo_root`` (its own
    ``.git`` sits at the root, which this prune never inspects).
    """
    dirnames[:] = [
        d
        for d in dirnames
        if d not in SKIP_DIRS and not os.path.lexists(os.path.join(dirpath, d, ".git"))
    ]

# Single source of truth mapping a committed lockfile name -> the package manager
# it implies. Shared by semantic.py, check_drift.py and canonicalize.py so the
# drift gate, the semantic engine and the draft generator agree on which managers
# exist — including bun (bun.lockb / bun.lock), which the drift gate previously
# omitted and was therefore blind to (TD-01).
LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "bun.lock": "bun",
}

# Single source of truth for recognizing a Node.js version reference in a line of
# AGENTS.md / config prose and normalizing it to its MAJOR version. Previously
# scan.py (Phase-0 conflict signal), semantic.py (Phase-0 declared-version check)
# and check_drift.py (Phase-2 D6 drift gate) each carried their OWN slightly
# different regex, so the same line could yield a different Node version (or none)
# depending on the stage (TD-06). They now all go through ``node_version_major``
# so every stage extracts the identical value. The pattern accepts: an optional
# ``.js`` suffix, an optional ``:`` separator, an optional ``version``/``v`` word,
# an optional comparator (``>=``/``<=``/``==``/``^``/``~``), an optional ``v``
# prefix and an optional surrounding quote, then the version. The full version
# token (major plus any ``.minor`` / ``.patch`` / ``.x`` suffix) is captured as
# the ``version`` group; the leading MAJOR component alone as the ``major``
# group. ``node_version_major`` normalizes to the major for cross-stage
# comparison, while ``node_version_ref`` preserves the full token for display
# and for semantic-version conflict comparison (CORR-05).
NODE_VERSION_RE = re.compile(
    r"\bnode(?:\.js)?\s*:?\s*(?:v|version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?[\"']?"
    r"(?P<version>(?P<major>\d+)(?:\.\d+|\.x)*)",
    re.I,
)


def node_version_major(line):
    """Return the MAJOR Node.js version (int) referenced in ``line``, else ``None``.

    Single shared extractor used by scan.py, semantic.py and check_drift.py so all
    three stages normalize a Node version reference to the same value (TD-06)."""
    m = NODE_VERSION_RE.search(line)
    return int(m.group("major")) if m else None


def node_version_ref(line):
    """Return the full declared Node.js version token (str) in ``line``, else ``None``.

    Unlike ``node_version_major``, this preserves the minor/patch/``.x`` suffix
    (e.g. ``"18.17.0"``, ``"18.x"``, ``"20"``) so callers can display the exact
    declared version. Semantic conflict comparison still normalizes to the major
    via ``node_version_major`` so ``18`` and ``18.17.0`` are treated as
    compatible, not a false conflict (CORR-05)."""
    m = NODE_VERSION_RE.search(line)
    return m.group("version") if m else None


# ---------------------------------------------------------------------------
# Backtick-quoted repo path detection (single source of truth).
#
# The Phase-0 semantic engine (semantic.declared_paths) and the Phase-2 drift
# gate (check_drift.d2_path_drift) both need to answer "which backtick-quoted
# tokens in AGENTS.md are repo-relative file paths worth existence-checking?".
# They previously carried two separate, drifted rulesets (different command
# prefixes, a smaller known-root-file set, and a missing quoted-literal guard),
# so the same AGENTS.md line could be a "declared path" in one stage and ignored
# in the other (TD-03). ``declared_paths`` below is the ONE shared classifier both
# call, so the two stages can no longer disagree on what counts as a path.
# ---------------------------------------------------------------------------

# Command prefixes that make a backtick token a shell invocation, not a path.
CMD_PATH_PREFIXES = (
    "npm ",
    "pnpm ",
    "yarn ",
    "bun ",
    "make ",
    "python",
    "git ",
    "node ",
    "go ",
    "cargo ",
    "mvn ",
    "gradle ",
    "./gradlew",
    "./mvnw",
    "poetry ",
    "pdm ",
    "uv ",
    "pip ",
    "pipenv ",
    "pytest",
    "rustc ",
    "javac ",
    "java ",
)

# Repo-root files that are referenced by bare name (no slash) yet are legitimate
# repo-relative paths worth verifying. Covers every ecosystem's manifest/lockfile.
KNOWN_ROOT_FILES = {
    # Generic
    "AGENTS.md",
    "README.md",
    "Makefile",
    # Node
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    # Python
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
    # Go
    "go.mod",
    "go.sum",
    "go.work",
    # Rust
    "Cargo.toml",
    "Cargo.lock",
    # Java
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
}

_BACKTICK_RE = re.compile(r"`([^`]+)`")
# Matches a bare "<word>-name" placeholder path segment; see declared_paths.
_PLACEHOLDER_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9]*-name$")
# Code-expression punctuation that never appears in a legitimate repo-relative
# path an AGENTS.md would reference. A backtick token carrying any of these is a
# code snippet — an attribute macro, a function/index expression, or a
# quoted-argument literal — not a filesystem path; see declared_paths.
_CODE_EXPR_CHARS = frozenset("#()[]{}\"'!=;|&<>")
# Matches a git branch-type prefix written as a namespace convention: a single
# path segment followed by a trailing slash and nothing else (`feat/`, `fix/`,
# `release/`). AGENTS.md documents these as branch-naming rules, not as concrete
# repo directories worth existence-checking; see declared_paths.
_BRANCH_PREFIX_RE = re.compile(r"^[A-Za-z][\w.-]*/$")
# Git remote-ref prefixes. A token like `origin/dev` or `upstream/main` is a
# `<remote>/<branch>` ref used for diffs, not a directory named `origin`; see
# declared_paths.
_GIT_REMOTE_PREFIXES = ("origin/", "upstream/")
# Conventional git-flow / GitHub branch-type prefixes. A backtick token whose
# first segment is one of these AND whose bounded same-line context names a git
# branch (e.g. "create a feature branch", "checkout -b") is an EXAMPLE branch
# NAME (`feature/my-new-feature`, `fix/login-bug`), not a repo directory. The
# bare-prefix form (`feat/`, `fix/`) is already handled by `_BRANCH_PREFIX_RE`;
# this covers the concrete `<prefix>/<name>` form that slips through because its
# interior `/` makes it look path-like. Requiring BOTH the prefix and the branch
# cue keeps real directories that merely share a prefix word (`docs/guide`,
# `test/fixtures`, `release/notes.md`) checked. See _is_labeled_branch_ref.
_BRANCH_TYPE_PREFIXES = (
    "feature/",
    "feat/",
    "fix/",
    "bugfix/",
    "hotfix/",
    "release/",
    "chore/",
    "refactor/",
)
# Same-line cue that a token is being introduced as a git branch name.
_BRANCH_CONTEXT_RE = re.compile(r"\bbranch(?:es)?\b|\bcheckout\b|\bgit\s+switch\b", re.I)
# A STRONG equative branch cue directly names the token as a branch ("the
# current branch is `X`", "on branch `X`", "branch named `X`"). Unlike the weak
# cue above (a mere mention of "branch" on the line), this equates the token to
# a branch, so it suppresses the token even when its first segment is NOT a
# conventional branch-type prefix (`feature/`, `fix/`, ...). Found running the
# full chain against assistant-ui/assistant-ui, whose AGENTS.md says "If the
# current branch is `gitbutler/workspace`, the user uses GitButler, not Git" —
# the GitButler workspace ref was falsely flagged MISSING by the Phase-0
# semantic scan and the Phase-2 D2 gate.
_STRONG_BRANCH_CUE_RE = re.compile(
    r"\b(?:current\s+branch|branch\s+is|branch\s+named|branch\s+called|on\s+branch)\b",
    re.I,
)
# Filesystem cues that force a path classification and override the branch cue
# (fail-closed toward paths): "edit the `feature/login.tsx` file" is a real path
# even though the line mentions a branch. Deliberately narrow.
_BRANCH_PATH_CUE_RE = re.compile(
    r"\b(?:files?|directory|directories|folder|path|edit|open|modify|source|"
    r"located|repository|repo)\b",
    re.I,
)
# Bounded window (chars) scanned around the token so section-level prose intent
# never leaks into the branch classification.
_BRANCH_LABEL_WINDOW = 40
# A path segment that looks like a hostname (contains a literal `.`, not a
# leading one like `.github`) — the first component of a Go import/module
# path (`github.com/org/pkg`, `charm.land/bubbletea/v2`), never a real
# repo-relative directory. See declared_paths.
_GO_IMPORT_HOST_RE = re.compile(r"^[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+$")
# A negation trigger word, followed by everything up to the next clause
# terminator (deliberately NOT a comma — "never npm, yarn, or bun" needs the
# whole comma-separated list to stay inside one negated span). A token/signal
# whose match position falls inside one of these spans is being named as an
# anti-pattern or a forbidden alternative, not asserted as real/current.
#
# Found scanning two real AGENTS.md files:
# - vercel/ai: "Do not create flat top-level provider files like
#   `src/stream-text/openai.ts`" flagged the path MISSING even though the
#   sentence documents that this path should never exist.
# - better-auth/better-auth: "ALWAYS use `pnpm` (never npm, yarn, or bun)"
#   and "NEVER run `pnpm test` ... Use `vitest ...`" both manufactured a
#   package_manager/test_command conflict out of the explicitly-rejected
#   alternatives, even though the doc is unusually unambiguous.
_NEGATED_CLAUSE_RE = re.compile(
    r"\b(?:do not|don't|never|avoid|shouldn't|should not"
    # Existence negations — "There are no per-package npm lockfiles" states a
    # tool is ABSENT, so the manager named inside must not be extracted as a
    # declared signal (found scanning cline/cline, a false package_manager
    # conflict).
    r"|there are no|there is no|there's no|have no|has no)\b[^.;)\n]*",
    re.I,
)


# Committed dotenv *template* variants: unlike a bare `.env` (gitignored), these
# are meant to be tracked, so a reference to a missing one is genuine drift.
_DOTENV_TEMPLATE_SUFFIXES = frozenset(
    {"example", "sample", "template", "dist", "defaults"}
)


def _is_gitignored_dotenv(token):
    """True when ``token`` names a conventionally-gitignored runtime dotenv file.

    Matches a basename of exactly ``.env`` or ``.env.<suffix>`` (e.g.
    ``frontend/.env``, ``.env.local``, ``.env.production``) but NOT the committed
    template variants in ``_DOTENV_TEMPLATE_SUFFIXES`` (``.env.example`` etc.),
    which stay checked so real drift is still caught.
    """
    base = token.rsplit("/", 1)[-1]
    if base == ".env":
        return True
    if base.startswith(".env."):
        return base[len(".env.") :].lower() not in _DOTENV_TEMPLATE_SUFFIXES
    return False


# A slash-joined run of two or more package-manager names — e.g.
# "npm/yarn/pnpm workspaces" or "pnpm/yarn" — enumerates the tools a doc
# *supports* or *detects*, it does not declare the ONE package manager the repo
# itself uses. Found self-scanning this repo's own AGENTS.md, where the
# feature description "auto-detects npm/yarn/pnpm workspaces" manufactured a
# bogus 3-way npm/yarn/pnpm package_manager conflict against the real `npm`
# declaration elsewhere in the same file.
_PM_TOKEN = (
    r"(?:npm|pnpm|yarn|bun|pip3?|poetry|pipenv|pdm|uv|cargo|maven|mvn|gradlew?)"
)
_PM_ENUMERATION_RE = re.compile(
    rf"\b{_PM_TOKEN}(?:\s*/\s*{_PM_TOKEN})+\b",
    re.I,
)


def pm_enumeration_spans(line):
    """Return ``[(start, end), ...]`` char spans of slash-joined package-manager
    enumerations (see ``_PM_ENUMERATION_RE``). A match whose start falls inside
    one of these spans lists a manager as *supported*, not *declared*, so
    ``scan.extract_signals`` skips it instead of manufacturing a false
    package_manager conflict.
    """
    return [m.span() for m in _PM_ENUMERATION_RE.finditer(line)]


def negated_spans(line):
    """Return ``[(start, end), ...]`` character spans of ``line`` that fall
    inside a negation clause (see ``_NEGATED_CLAUSE_RE``). Shared by
    ``declared_paths`` here and ``scan.extract_signals`` so a match's own
    start position can be checked against ``any(start <= pos < end for ...)``
    instead of blanket-skipping the whole line — which would also throw away
    a real positive declaration living earlier on the same line (e.g. the
    asserted `pnpm` in "ALWAYS use `pnpm` (never npm, yarn, or bun)").
    """
    return [m.span() for m in _NEGATED_CLAUSE_RE.finditer(line)]


# A slash-bearing `org/name` backtick token has the same lexical shape whether
# it names a repo-relative directory, a Docker/OCI image, or an RPC/API method.
# Real harness docs use all three (found scanning Letta's `letta/letta` Docker
# image and OpenAI Codex's `thread/read` / `app/list` RPC-method examples, all
# falsely reported MISSING). A bounded, evidence-based context check — NOT a
# blanket `org/name` exclusion — decides when the token is a runtime identifier
# instead of a path, because repositories legitimately contain two-segment
# directories such as `src/service`. Ambiguity stays fail-closed (treated as a
# path) and an explicit file/directory/edit cue always wins.

# Only a plain two-segment token (exactly one "/", no dot in either segment, no
# leading dot or relative marker) is eligible: anything with an extension, a
# leading dot, or three or more components is a filesystem path regardless of
# nearby prose — so a Docker Compose file like `docker/compose.yml` is never
# suppressed merely because the word "Docker" appears on the line.
_RUNTIME_ID_SHAPE_RE = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+")

# Bounded window (chars) scanned immediately before/after the backtick token so
# section-level prose intent never leaks into the classification.
_LABEL_WINDOW = 40

# Explicit filesystem cues: when present next to the token they force a path
# classification and win over any runtime-identifier word (fail-closed toward
# paths). Deliberately excludes broad words such as "service" or "app".
_PATH_LABEL_RE = re.compile(
    r"\b(?:files?|directory|directories|folder|path|edit|open|modify|"
    r"source|located\s+under|repository|repo)\b",
    re.I,
)

# Explicit runtime-identifier cues that mark the token as NOT a filesystem path.
_NONPATH_LABEL_RE = re.compile(
    r"\b(?:docker\s+image|container\s+image|image|"
    r"rpc\s+method|method|endpoint|operation|route|action|skill|command|tool|library|component|package)\b",
    re.I,
)

# A linter rule id (`react/exhaustive-deps`, `import/no-cycle`,
# `react/rules-of-hooks`) has the same `plugin/rule` shape as a two-segment repo
# path, but its rule segment is a hyphenated identifier that no real directory
# uses in this position. Combined with an explicit linter name AND the word
# "rule(s)" on the same line, the token is a lint rule, not a path. Found running
# the full chain against assistant-ui/assistant-ui, whose AGENTS.md says "hook
# rules are checked by oxlint's native `react/exhaustive-deps` and
# `react/rules-of-hooks`" — both rule ids were falsely reported MISSING by the
# Phase-0 semantic scan and the Phase-2 D2 gate. The existing config-backed
# ``facts.is_eslint_rule_identifier`` only catches rules quoted verbatim in an
# ESLint config file; oxlint's native rules live in no such file, so a
# prose-labelled fallback is needed too.
_LINT_RULE_SHAPE_RE = re.compile(
    r"(?:react|react-hooks|import|jsx-a11y|unicorn|promise|node|n|vue|svelte|solid|"
    r"astro|prettier|jest|vitest|testing-library)/[A-Za-z0-9][A-Za-z0-9-]*"
)
_LINTER_NAME_RE = re.compile(r"\b(?:eslint|oxlint|tslint|stylelint|biome)\b", re.I)
_RULE_WORD_RE = re.compile(r"\brules?\b", re.I)


def _is_labeled_lint_rule(line, match):
    """True when a backtick token is a linter ``plugin/rule`` id, not a path.

    Requires three independent signals so real two-segment directories are never
    over-suppressed: the token has the hyphenated ``plugin/rule-name`` shape, the
    same line names a concrete linter (eslint/oxlint/...), and the same line uses
    the word "rule(s)". An explicit filesystem cue (file, directory, edit, ...)
    in the bounded window around the token always wins and keeps it a path.
    """
    token = match.group(1).strip()
    if "." in token or token.count("/") != 1:
        return False
    if not _LINT_RULE_SHAPE_RE.fullmatch(token):
        return False
    before = line[max(0, match.start() - _LABEL_WINDOW):match.start()]
    after = line[match.end():match.end() + _LABEL_WINDOW]
    window = before + " " + after
    # Explicit filesystem intent wins over the lint-rule cue.
    if _PATH_LABEL_RE.search(window):
        return False
    return bool(_LINTER_NAME_RE.search(line) and _RULE_WORD_RE.search(line))


def _is_labeled_runtime_identifier(line, match):
    """True when bounded same-line context explicitly labels the backtick token
    as a Docker/OCI image or an RPC/API method rather than a repo path.

    Uses only a small character window immediately before/after the exact match
    span, so section-level prose never leaks in. Precedence is deterministic and
    conservative: an explicit filesystem cue (file, directory, edit, ...) always
    wins, and an unlabeled token stays a path.
    """
    token = match.group(1).strip()
    if not _RUNTIME_ID_SHAPE_RE.fullmatch(token):
        return False
    before = line[max(0, match.start() - _LABEL_WINDOW):match.start()]
    after = line[match.end():match.end() + _LABEL_WINDOW]
    window = before + " " + after
    # Explicit filesystem intent wins over any runtime-identifier word.
    if _PATH_LABEL_RE.search(window):
        return False
    return bool(_NONPATH_LABEL_RE.search(window))


def _is_labeled_branch_ref(line, match):
    """True when a backtick token is an example git BRANCH NAME rather than a
    repo path.

    Requires two independent signals so real directories are never over-
    suppressed: the token's first segment is a conventional branch-type prefix
    (`feature/`, `fix/`, ...), AND bounded same-line context names a git branch
    (`branch`, `checkout`, `git switch`). A STRONG equative cue ("current branch
    is `X`", "on branch `X`") is the one exception: it directly names the token
    as a branch, so it suppresses the token on its own even without a
    conventional prefix. Reads only a small window around the exact match span so
    section-level prose never leaks in, and an explicit filesystem cue (file,
    directory, edit, ...) always wins and keeps the token a path.
    """
    token = match.group(1).strip()
    if "/" not in token:
        return False
    before = line[max(0, match.start() - _BRANCH_LABEL_WINDOW):match.start()]
    after = line[match.end():match.end() + _BRANCH_LABEL_WINDOW]
    window = before + " " + after
    # Explicit filesystem intent wins over the branch cue (fail-closed to path).
    if _BRANCH_PATH_CUE_RE.search(window):
        return False
    # A strong equative cue equates the token to a branch, so no conventional
    # branch-type prefix is required.
    if _STRONG_BRANCH_CUE_RE.search(window):
        return True
    # Otherwise require both signals: a branch-type prefix AND a weaker cue.
    if not token.startswith(_BRANCH_TYPE_PREFIXES):
        return False
    return bool(_BRANCH_CONTEXT_RE.search(window))


def declared_paths(text):
    """Return repo-relative paths referenced in inline backticks as ``{path, line}``.

    Single shared classifier used by both ``semantic.declared_paths`` (Phase-0)
    and ``check_drift.d2_path_drift`` (Phase-2) so the two stages agree on exactly
    what counts as a declared path (TD-03). This only decides candidacy from the
    token text; callers still apply their own containment (``_within_root``) and
    existence checks. Tokens are de-duplicated across the whole document.
    """
    out = []
    seen = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        negated = negated_spans(line)
        for m in _BACKTICK_RE.finditer(line):
            if any(start <= m.start() < end for start, end in negated):
                continue
            token = m.group(1).strip()
            if not token or token in seen:
                continue
            # A backtick span wrapped in matching quotes is a string-literal
            # example value (e.g. `'/usr/bin/google-chrome'`, `"./downloads"`),
            # not a repo path reference. Only the backticks were stripped, leaving
            # the inner quotes to defeat the absolute-path / value guards below.
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
                continue
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            # Ellipsis-bearing snippets are illustrative placeholders, not literal repo paths.
            if "..." in token:
                continue
            # A token carrying code-expression punctuation (`#`, brackets,
            # parentheses, quotes, operators) is a code snippet, not a path —
            # e.g. the Rust attribute macro `#[experimental("method/or/field")]`
            # whose inner `/` made it look path-like and produced a false "path
            # does not exist" finding (found scanning openai/codex's AGENTS.md).
            if any(ch in _CODE_EXPR_CHARS for ch in token):
                continue
            # Home-relative (~/.claude), absolute (/etc/...), env-var ($HOME/...),
            # or scheme/drive-like paths reference locations outside the repo tree.
            if token.startswith(("~", "/", "$")) or ":" in token:
                continue
            # Scoped npm package names (`@ai-sdk/provider`) and path-alias imports
            # (`@/components`) contain a slash but are package/module identifiers,
            # not repo-relative filesystem paths; probing `root/@scope/...` always
            # misses and produced false "path does not exist" findings on real
            # AGENTS.md files (e.g. vercel/ai). npm scopes are `@`-prefixed, which
            # no legitimate repo-relative path uses.
            if token.startswith("@"):
                continue
            # A leading `<word>-name` segment (`skill-name/SKILL.md`,
            # `package-name/index.js`) documents a naming *pattern* in prose, not
            # a literal repo path — no real directory is ever named literally
            # "skill-name". Found scanning tldraw/tldraw's AGENTS.md, which uses
            # this idiom to describe its skill-folder convention. Only the exact
            # "<word>-name" shape matches, so a real path segment that merely
            # contains "name" (`username/profile.py`) is still checked.
            if _PLACEHOLDER_SEGMENT_RE.fullmatch(token.split("/", 1)[0]):
                continue
            # A git branch/ref convention is not a repo path. AGENTS.md routinely
            # documents branch-naming rules and diff refs in backticks:
            #   - branch-type prefixes (`feat/`, `fix/`, `release/`): a single
            #     segment plus a trailing slash — a namespace convention, not a
            #     concrete directory the repo is expected to contain;
            #   - remote refs (`origin/dev`, `upstream/main`): `<remote>/<branch>`
            #     refs used for diffs, not a directory literally named `origin`.
            # Both slipped through because their `/` made them look path-like,
            # producing false "path does not exist" findings in the Phase-0
            # semantic scan and the Phase-2 D2 gate (found scanning sst/opencode's
            # AGENTS.md, which states: "use `dev` or `origin/dev` for diffs" and
            # "do not use ... type prefixes such as `feat/` or `fix/`").
            if _BRANCH_PREFIX_RE.match(token) or token.startswith(_GIT_REMOTE_PREFIXES):
                continue
            # The concrete `<branch-type-prefix>/<name>` form (`feature/my-new-
            # feature`, `fix/login-bug`) is an example branch NAME when the same
            # line names a git branch, not a repo directory. See
            # _is_labeled_branch_ref for the two-signal (prefix + branch cue)
            # guard that keeps real `docs/guide`-style directories checked. Found
            # running the full chain against mem0ai/mem0, whose AGENTS.md says
            # "Create a feature branch from `main` (e.g., `feature/my-new-
            # feature`)" — flagged MISSING by the Phase-0 semantic scan and the
            # Phase-2 D2 gate even though no such directory should exist.
            if _is_labeled_branch_ref(line, m):
                continue
            # Go import/module paths are conventionally `domain.tld/org/pkg`
            # (a "vanity" or SCM-hosted path) — the first segment looks like
            # a hostname, never a real repo-relative directory name. Found
            # scanning charmbracelet/crush's AGENTS.md, which references both
            # its own module path ("The module path is
            # `github.com/charmbracelet/crush`") and dependency import paths
            # ("`charm.land/bubbletea/v2`"); neither is a filesystem path.
            # Gated on an actual "/" so this never catches a bare dotted
            # filename like `go.mod` or `Cargo.toml` (single-segment tokens
            # are handled entirely by the KNOWN_ROOT_FILES check below).
            if "/" in token and _GO_IMPORT_HOST_RE.match(token.split("/", 1)[0]):
                continue
            # A two-segment `org/name` token explicitly labeled as a Docker/OCI
            # image or an RPC/API method by adjacent same-line context is a
            # runtime identifier, not a repo-relative path. Bounded and
            # fail-closed: an explicit file/directory/edit cue keeps it a path,
            # and an unlabeled token stays a path (see
            # ``_is_labeled_runtime_identifier``).
            if _is_labeled_runtime_identifier(line, m):
                continue
            # A `plugin/rule-name` linter identifier (`react/exhaustive-deps`,
            # `react/rules-of-hooks`) shares the two-segment shape of a repo path
            # but is a lint rule when the same line names a linter and uses the
            # word "rule(s)". Bounded and fail-closed (see
            # ``_is_labeled_lint_rule``).
            if _is_labeled_lint_rule(line, m):
                continue
            # A conventional runtime dotenv file (`.env`, `frontend/.env`,
            # `.env.local`, `.env.production`, ...) is deliberately gitignored
            # and never committed — AGENTS.md references it as the place to PUT
            # local config, not as a path the repo is expected to contain, so
            # probing `root/.../.env` always misses. Found running the full
            # chain against All-Hands-AI/OpenHands, whose AGENTS.md says "Set
            # in `frontend/.env` or as environment variables" — flagged MISSING
            # even though a committed `.env` would itself be the bug. The
            # committed *template* variants (`.env.example`, `.env.sample`,
            # `.env.template`, `.env.dist`, `.env.defaults`) are the exception:
            # those ARE meant to be tracked, so a reference to a missing one is
            # genuine drift and stays checked.
            if _is_gitignored_dotenv(token):
                continue
            # Conventional generated-output roots are absent from a clean
            # checkout by design. An instruction can document where a build
            # writes declarations/assets (e.g. `dist/_types/`) without claiming
            # that generated output is committed. These directories are also
            # excluded from every repository walk via SKIP_DIRS.
            if token.split("/", 1)[0] in {"dist", "build"}:
                continue
            if token.startswith(CMD_PATH_PREFIXES):
                continue
            if "*" in token or "?" in token:
                continue
            if any(ch.isspace() for ch in token):
                continue
            if "/" not in token and token not in KNOWN_ROOT_FILES:
                continue
            seen.add(token)
            out.append({"path": token, "line": lineno})
    return out


def load_registry():
    """Return the full parsed registry as a dict."""
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_tools():
    """Return the list of tool entries (claude, cursor, ... roo)."""
    return load_registry().get("tools", [])


def load_canonical():
    """Return the list of canonical file names (e.g. AGENTS.md, AGENT.md)."""
    return load_registry().get("canonical", [])


def canonicalizable_tools():
    """Return only the tools that have a canonical stub form to write/guard."""
    return [t for t in load_tools() if t.get("canonicalizable") and t.get("stub_paths")]
