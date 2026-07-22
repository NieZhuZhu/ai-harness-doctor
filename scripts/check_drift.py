#!/usr/bin/env python3
"""Read-only drift guard for canonical AGENTS.md files."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# canonicalize.py lives in the same scripts/ dir; reuse its canonical stub
# content/logic instead of duplicating it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonicalize  # noqa: E402
import facts  # noqa: E402  # shared repo fact-readers (single source of truth, TD-02)
import plugins  # noqa: E402  # user-extensible deterministic rule plugins
import registry  # noqa: E402
import scan  # noqa: E402  # reuse scan.SKIP_DIRS so the drift walk prunes the same vendored dirs

DEFAULT_MAX_BYTES = 32768
# Flat list of every canonical stub path, derived (in registry order) from the
# shared agent-config registry so the drift guard tracks exactly the same stubs
# canonicalize.py writes. See assets/agent-tools.json.
STUB_FILES = [p for tool in registry.canonicalizable_tools() for p in tool["stub_paths"]]

# Package-manager subcommands that are always valid; the prose heuristics; and the
# shared code-span tokenizer are single-sourced in facts.py so this drift gate and
# the Phase-0 semantic engine parse commands identically (TD-02).
PACKAGE_MANAGER_BUILTINS = facts.PACKAGE_MANAGER_BUILTINS
_PROSE_WORDS = facts._PROSE_WORDS
_PROSE_TARGET_WORDS = facts._PROSE_TARGET_WORDS
_looks_like_prose = facts.looks_like_prose
line_collected_code = facts.iter_code_tokens

# package.json scripts and Makefile targets are read via the shared facts layer
# so this gate and the Phase-0 engine read them identically (TD-02).
package_scripts = facts.package_scripts
make_targets = facts.make_targets

# Positive evidence that a file IS a managed pointer stub written by
# canonicalize.py: either the Claude `@AGENTS.md` import directive, or the
# canonical "instructions live in AGENTS.md" redirect phrase shared by the
# cursor/windsurf/cline/continue/copilot/gemini stubs. Matching a bare
# "AGENTS.md" mention (the old D3 heuristic) over-fires on full hand-authored
# configs that merely *link* to nested `dir/AGENTS.md` files or name the file in
# prose — e.g. pydantic-ai's CLAUDE.md, a complete duplicate of AGENTS.md that
# indexes ten nested `*/AGENTS.md` docs, was wrongly flagged as a regrown stub.
_STUB_POINTER_SIGNAL_RE = re.compile(
    r"(?m)^\s*@AGENTS\.md\b|instructions live in\s+`?AGENTS\.md`?",
    re.IGNORECASE,
)


def _fact_ancestors(root, fallback_root=None, ancestors=None):
    """Return one contained nearest-first fact chain for a drift scope."""
    root = Path(root).resolve()
    if ancestors is not None:
        directories = [Path(directory).resolve() for directory in ancestors]
        if not directories or directories[0] != root:
            raise ValueError("ancestor chain must start at the drift scope")
        repository_root = (
            Path(fallback_root).resolve()
            if fallback_root is not None
            else root
        )
        if (
            directories[-1] != repository_root
            or len(directories) != len(set(directories))
            or any(
                child.parent != parent
                for child, parent in zip(directories, directories[1:])
            )
        ):
            raise ValueError("ancestor chain must be lexical and contained")
        return directories
    if fallback_root is None or Path(fallback_root).resolve() == root:
        return [root]
    return facts.ancestor_dirs(root, fallback_root)


def _package_name_at(root):
    return facts.package_name(root)


def _make_finding(lineno, name):
    return {
        "check": "D1",
        "level": "ERROR",
        "line": lineno,
        "message": f"Unknown Makefile target `{name}`",
        "suggestion": "Update AGENTS.md or add the Makefile target.",
    }


def d1_command_drift(root, text, fallback_root=None, ancestors=None):
    findings = []
    directories = _fact_ancestors(root, fallback_root, ancestors)
    containment_root = directories[-1]
    script_sets = [
        scripts
        for directory in directories
        if (scripts := package_scripts(directory)) is not None
    ]
    target_sets = [
        targets
        for directory in directories
        if (targets := make_targets(directory)) is not None
    ]
    scope_dependencies = "not computed"
    # Keep the package-manager alternation in lock-step with semantic.py's
    # _NODE_CMD_RE (npm|pnpm|bun); omitting bun left this CI gate blind to
    # `bun run <script>` references that the Phase-0 engine already audits.
    # `make` invocations go through the shared option-aware parser instead
    # (facts.iter_make_invocations) so `-C`/globs are never misread (Plan 070).
    cmd_re = re.compile(
        r"\b(?:(npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_][A-Za-z0-9:_-]*)"
        r"|yarn\s+([A-Za-z0-9:_][A-Za-z0-9:_-]*))\b"
    )
    for lineno, code in line_collected_code(text):
        # Skip English prose sentences so imperatives like "make sure the tests
        # pass" are not parsed into phantom command targets (CORR-02).
        if _looks_like_prose(code):
            continue
        for invocation in facts.iter_make_invocations(code):
            name = invocation["name"]
            directory = invocation["directory"]
            # A make "target" that is a bare English word ("make sure",
            # "make the ...") is prose, not a Makefile target (CORR-02).
            if directory is None and name in _PROSE_TARGET_WORDS:
                continue
            if directory is not None:
                # `make -C DIR target` names DIR's Makefile, not the scope's.
                # Resolve DIR against every fact-chain directory (containment-
                # checked) and accept the target if ANY resolved Makefile
                # defines it — mirroring the any-of semantics of target_sets
                # below, so a nearer unrelated Makefile can never mask (or
                # manufacture) drift. Abstain when no candidate resolves.
                candidate_target_sets = [
                    targets
                    for base in directories
                    if (
                        candidate := facts.resolve_within_root(
                            base / directory, containment_root, strict=False
                        )
                    )
                    is not None
                    and (targets := make_targets(candidate)) is not None
                ]
                if candidate_target_sets and not any(
                    name in targets for targets in candidate_target_sets
                ):
                    findings.append(_make_finding(lineno, name))
                continue
            if target_sets and not any(name in targets for targets in target_sets):
                findings.append(_make_finding(lineno, name))
        for m in cmd_re.finditer(code):
            tool = m.group(1) or "yarn"
            name = m.group(2) or m.group(3)
            # Treat package-manager builtins as valid unconditionally; false negatives
            # are cheaper than noisy false positives here.
            if name in PACKAGE_MANAGER_BUILTINS:
                continue
            # Same for yarn/pnpm node_modules/.bin passthrough (`yarn vitest`,
            # `pnpm mastra`) — see facts.is_node_bin_passthrough (TD-02).
            if (
                any(
                    facts.is_node_bin_passthrough(directory, tool, name)
                    for directory in directories
                )
                or (
                    tool in {"yarn", "pnpm"}
                    and name
                    in (
                        scope_dependencies
                        if scope_dependencies != "not computed"
                        else facts.all_package_dependency_bin_names(directories[0])
                    )
                )
            ):
                if tool in {"yarn", "pnpm"} and scope_dependencies == "not computed":
                    # Preserve the existing canonical-scope contract: a parent
                    # AGENTS.md may describe a binary supplied by one of its
                    # descendant packages. Scripts/paths/facts below never use
                    # this descendant fallback.
                    scope_dependencies = facts.all_package_dependency_bin_names(
                        directories[0]
                    )
                continue
            if script_sets and not any(name in scripts for scripts in script_sets):
                findings.append(
                    {
                        "check": "D1",
                        "level": "ERROR",
                        "line": lineno,
                        "message": f"Unknown package.json script `{name}`",
                        "suggestion": "Update AGENTS.md or add the package.json script.",
                    }
                )
    return findings


# Path-containment info-leak guard (rejects absolute / `../`-escaping tokens
# before probing them on disk). Single-sourced in facts.py so this gate and the
# Phase-0 engine apply the same containment rule (TD-02).
_within_root = facts.within_root


def d2_path_drift(root, text, fallback_root=None, ancestors=None, repository_index_cache=None):
    findings = []
    directories = _fact_ancestors(root, fallback_root, ancestors)
    containment_root = directories[-1]
    nested_scope = len(directories) > 1
    # Shared per-run memo for the repository-root suffix index used by the
    # nested-scope uniqueness fallback below; run_checks passes one dict for
    # all scopes so the repository is walked at most once per run.
    if repository_index_cache is None:
        repository_index_cache = {}
    # Use the shared registry.declared_paths classifier so this Phase-2 gate and
    # the Phase-0 semantic check agree on exactly what counts as a declared path
    # (TD-03). Candidacy is decided by the shared token rules; this gate then
    # applies its own containment (_within_root) and existence checks.
    #
    # Lazily computed only on a potential finding, mirroring
    # semantic.compare_paths so the common case (path exists) never pays for a
    # repo walk.
    package_names = "not computed"
    non_path_context = None
    subtree_index = None
    missing = []
    for decl in registry.declared_paths(text):
        token, lineno = decl["path"], decl["line"]
        candidates = []
        for directory in directories:
            candidate = facts.resolve_within_root(
                directory / token,
                containment_root,
                strict=False,
            )
            if candidate is None:
                continue
            if facts.exists_within_root(containment_root, candidate):
                break
            candidates.append(candidate.relative_to(containment_root).as_posix())
        else:
            if candidates:
                missing.append((decl, candidates))
    ignored = facts.repository_ignored_paths(
        containment_root,
        [
            repository_token
            for _decl, repository_tokens in missing
            for repository_token in repository_tokens
        ],
    )
    for decl, repository_tokens in missing:
        token, lineno = decl["path"], decl["line"]
        if any(repository_token in ignored for repository_token in repository_tokens):
            continue
        # Monorepo package self-import guard — mirrors semantic.compare_paths
        # so both gates agree (TD-03). Restrict nested lookup to lexical
        # ancestors; root keeps its historical whole-repository fallback.
        if package_names == "not computed":
            package_names = (
                {
                    name
                    for directory in directories
                    if (name := _package_name_at(directory)) is not None
                }
                if nested_scope
                else facts.all_package_names(directories[0])
            )
        if token.split("/", 1)[0] in package_names:
            continue
        if any(
            facts.is_eslint_rule_identifier(directory, token)
            for directory in directories
        ):
            continue
        # Go/npm import paths and Go exported symbols wear the same
        # backtick-and-slash clothes as repo paths; classify them against the
        # scope's own manifests (go.mod, package.json) before flagging — same
        # rule as semantic.compare_paths (TD-02/TD-03, Plan 070).
        if non_path_context is None:
            non_path_context = facts.non_path_reference_context(
                containment_root, directories
            )
        if facts.is_import_or_symbol_reference(token, non_path_context):
            continue
        # Deploy/Docker docs spell paths from one level above the checkout
        # (`<repo-name>/backend/...`); strip the repository's own name when the
        # remainder exists (Plan 070).
        if facts.strips_repository_name_prefix(containment_root, token):
            continue
        # Root keeps repository-wide suffix lookup. A nested canonical scope
        # may describe conventions in its own descendants, so its suffix index
        # is bounded to that scope root; it must never search sibling packages.
        if facts.is_subtree_path_candidate(token) and subtree_index is None:
            subtree_index = facts.build_subtree_path_index(directories[0])
        if (
            subtree_index is not None
            and facts.path_resolves_in_subtree(directories[0], token, subtree_index)
        ):
            continue
        # One narrow exception to the sibling-package bound: a suffix with
        # exactly ONE source in the whole repository AND no local anchor (its
        # first segment exists under no fact-chain directory) is an unambiguous
        # cross-subtree reference (`cmd/enterprise` named from `deploy/`), not
        # drift; ambiguous names (`dal/po` in many modules) and locally
        # anchored ones (`src/only.ts` beside an existing `src/`) stay findings
        # (Plan 070).
        if (
            nested_scope
            and facts.is_subtree_path_candidate(token)
            and not facts.has_local_anchor(containment_root, directories, token)
        ):
            if "index" not in repository_index_cache:
                repository_index_cache["index"] = facts.build_subtree_path_index(
                    containment_root
                )
            if repository_index_cache["index"].resolves_uniquely(
                containment_root, token
            ):
                continue
        findings.append(
            {
                "check": "D2",
                "level": "ERROR",
                "line": lineno,
                "message": f"Referenced path `{token}` does not exist",
                "suggestion": "Fix or remove the backtick-quoted path.",
            }
        )
    return findings


def d3_stub_regrowth(root):
    findings = []
    if not facts.is_file_within_root(root, root / "AGENTS.md"):
        return findings
    for rel in STUB_FILES:
        path = root / rel
        if path.is_symlink():
            findings.append(
                {
                    "check": "D3",
                    "level": "ERROR",
                    "path": rel,
                    "message": f"Unsafe tool stub `{rel}` is a symlink",
                    "suggestion": "Replace it with an owned regular file before applying fixes.",
                }
            )
            continue
        data = facts.read_bytes_within_root(root, path)
        if data is None:
            continue
        text = data.decode("utf-8", errors="replace")
        # Only flag a file as a regrown/broken canonical stub when there is
        # positive evidence it IS a managed pointer stub: it carries a canonical
        # pointer signal (`@AGENTS.md` import or the "instructions live in
        # AGENTS.md" redirect phrase) but has grown past the minimal-stub size
        # budget. A file that merely mentions or links to AGENTS.md (a full
        # hand-authored doc indexing nested `dir/AGENTS.md` files) is not a
        # broken stub, so D3 must not claim it "lost" a pointer it never had.
        if _STUB_POINTER_SIGNAL_RE.search(text) and len(data) > registry.STUB_POINTER_MAX_BYTES:
            findings.append(
                {
                    "check": "D3",
                    "level": "ERROR",
                    "path": rel,
                    "message": f"Tool stub `{rel}` regrew past the pointer-stub size budget",
                    "suggestion": "Run canonicalize.py --write-stubs after reviewing changes.",
                }
            )
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_symlink():
        findings.append(
            {
                "check": "D3",
                "level": "ERROR",
                "path": ".cursor/rules",
                "message": "Unsafe Cursor rules directory is a symlink",
                "suggestion": "Replace it with an owned directory before applying fixes.",
            }
        )
        return findings
    if facts.is_dir_within_root(root, cursor_rules):
        for p in cursor_rules.glob("*"):
            data = facts.read_bytes_within_root(root, p)
            if data is None:
                continue
            text = data.decode("utf-8", errors="replace")
            # Same rule as above: only a genuine pointer rule (carries a
            # canonical `@AGENTS.md`/"instructions live in AGENTS.md" signal)
            # that regrew past the size budget is drift; a rule that merely
            # mentions or links to AGENTS.md is not a broken stub.
            if _STUB_POINTER_SIGNAL_RE.search(text) and len(data) > registry.STUB_POINTER_MAX_BYTES:
                findings.append(
                    {
                        "check": "D3",
                        "level": "ERROR",
                        "path": p.relative_to(root).as_posix(),
                        "message": "Cursor rule regrew past the pointer-stub size budget",
                        "suggestion": "Keep a single minimal pointer rule.",
                    }
                )
    return findings


def d4_size(root, max_bytes):
    path = root / "AGENTS.md"
    data = facts.read_bytes_within_root(root, path)
    if data is None:
        return [
            {
                "check": "D4",
                "level": "ERROR",
                "message": "AGENTS.md is missing",
                "suggestion": "Create canonical AGENTS.md first.",
            }
        ]
    size = len(data)
    if size > max_bytes:
        return [
            {
                "check": "D4",
                "level": "ERROR",
                "message": f"AGENTS.md is {size} bytes, above {max_bytes}",
                "suggestion": "Move details to references/ and keep AGENTS.md concise.",
            }
        ]
    if size > 12 * 1024:
        return [
            {
                "check": "D4",
                "level": "NOTICE",
                "message": f"AGENTS.md is {size} bytes; context bloat risk",
                "suggestion": "Consider progressive disclosure.",
            }
        ]
    return []


# Lockfile -> package-manager map, from the shared registry single source of
# truth so the drift gate (D6/D8) tracks the SAME managers as semantic.py and
# canonicalize.py — including bun (bun.lockb / bun.lock), which this map
# previously omitted, leaving the gate blind to bun repos (TD-01).
LOCKFILE_MANAGERS = registry.LOCKFILE_MANAGERS


# ``(major, line)`` for a Node.js version declared in AGENTS.md; the .nvmrc /
# engines.node ground-truth readers; the package managers a doc declares; and the
# committed-lockfile manager set are all single-sourced in facts.py so this D6
# drift gate and the Phase-0 semantic check read every fact one way (TD-02/TD-06).
declared_node_version = facts.declared_node_version
nvmrc_node_version = facts.nvmrc_node_version
engines_node_version = facts.engines_node_version
declared_package_managers = facts.declared_package_managers
lockfile_managers = facts.lockfile_managers


def d6_fact_drift(root, text, fallback_root=None, ancestors=None):
    """Cross-validate factual claims in AGENTS.md against repo ground-truth files."""
    findings = []
    if not text:
        return findings
    directories = _fact_ancestors(root, fallback_root, ancestors)

    # Node version: declared claim vs .nvmrc and package.json engines.node.
    declared_node, node_line = declared_node_version(text)
    if declared_node is not None:
        node_root = next(
            (
                directory
                for directory in directories
                if nvmrc_node_version(directory) is not None
                or engines_node_version(directory) is not None
            ),
            None,
        )
        nvmrc = nvmrc_node_version(node_root) if node_root is not None else None
        if nvmrc is not None and nvmrc != declared_node:
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "line": node_line,
                    "message": f"AGENTS.md claims Node {declared_node} but `.nvmrc` pins Node {nvmrc}",
                    "suggestion": "Align AGENTS.md with `.nvmrc` or update `.nvmrc`.",
                }
            )
        engines = engines_node_version(node_root) if node_root is not None else None
        if engines is not None and engines != declared_node:
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "line": node_line,
                    "message": f"AGENTS.md claims Node {declared_node} but "
                    f"`package.json` engines.node requires Node {engines}",
                    "suggestion": "Align AGENTS.md with `package.json` engines.node or update engines.node.",
                }
            )

    # Package manager: declared claim vs the lockfile that actually exists.
    declared_pms = declared_package_managers(text)
    ground_root = next(
        (
            directory
            for directory in directories
            if lockfile_managers(directory)
        ),
        directories[0],
    )
    ground_pms = lockfile_managers(ground_root)
    if len(declared_pms) == 1 and len(ground_pms) == 1:
        declared_pm = next(iter(declared_pms))
        ground_pm = next(iter(ground_pms))
        if declared_pm != ground_pm:
            lockfile = next(
                name
                for name, mgr in LOCKFILE_MANAGERS.items()
                if mgr == ground_pm and facts.is_file_within_root(ground_root, ground_root / name)
            )
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "message": f"AGENTS.md uses `{declared_pm}` but the repo has `{lockfile}` implying `{ground_pm}`",
                    "suggestion": f"Align AGENTS.md with `{ground_pm}` or "
                    f"replace the lockfile to match `{declared_pm}`.",
                }
            )
    return findings


# Markdown inline links: [label](target) and [label](target "title"). We only
# probe the target, and only when it is a repo-relative filesystem path (never a
# URL, anchor, template placeholder, or path outside the repo — see _within_root).
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)]+?)\s*\)")


def _link_target_is_probeable(target):
    """Return the repo-relative path to probe, or None if the target must be skipped."""
    if not target:
        return None
    # Strip a bracketed <...> target and any optional "title" suffix.
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    else:
        target = target.split(" ", 1)[0].strip()
    if not target or target.startswith("#"):
        return None
    if target.startswith(("http://", "https://", "mailto:", "tel:")) or "://" in target:
        return None
    if "<" in target or "{" in target or "*" in target or "?" in target or "`" in target:
        # A backtick would break out of the single-backtick code span that
        # carries the target into the D7 finding message (posted verbatim as a
        # PR review comment by pr_review.py); a real repo-relative path never
        # contains one.
        return None
    if "," in target:
        # No real repo-relative path contains a comma; `[T](ctx, c)`-shaped
        # code that leaks past the code-span guards is not a link (Plan 070).
        return None
    if target.startswith(("~", "/", "$")) or ":" in target:
        # Home-relative, absolute, env-var or scheme/drive-like targets are not
        # repo-relative paths; skip them exactly like d2_path_drift does.
        return None
    # Drop any in-page fragment so `references/foo.md#section` probes the file.
    target = target.split("#", 1)[0].strip()
    return target or None


def d7_markdown_link_drift(root, text, fallback_root=None):
    """Broken relative Markdown-link targets in AGENTS.md.

    D2 only probes backtick-quoted tokens; a canonical section that links to a
    config file or reference doc via Markdown link syntax (`[text](path)`) is not
    covered by D2. This flags link targets that resolve inside the repo but point
    at a file/dir that no longer exists — a documented path that drifted away.
    """
    findings = []
    if not text:
        return findings
    containment_root = Path(fallback_root).resolve() if fallback_root is not None else Path(root).resolve()
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        # Bracket-and-paren source code is not Markdown link syntax. Skip
        # fenced-code lines entirely (Go generics like
        # `iris.UpdateStore[MyStore](run, store)` match the link regex), and
        # skip matches that OPEN inside an inline backtick code span
        # (`hertz.BindValidate[T](ctx, c)`). A genuine link whose *label*
        # contains a code span (`[`docs/x.md`](../docs/x.md)`) opens before the
        # span and is still probed. Same fence contract as
        # facts.iter_code_tokens (Plan 070).
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        # An odd number of backticks means the left-to-right span pairing is
        # unreliable (a stray backtick would pair across real content and
        # swallow a genuine broken link after it), so fall back to probing the
        # whole line — conservative toward drift detection.
        code_spans = (
            [(span.start(), span.end()) for span in re.finditer(r"`[^`]+`", line)]
            if line.count("`") % 2 == 0
            else []
        )
        for m in _MD_LINK_RE.finditer(line):
            if any(start <= m.start() < end for start, end in code_spans):
                continue
            target = _link_target_is_probeable(m.group(1))
            if target is None:
                continue
            # Markdown may percent-encode spaces/specials in link targets
            # (`docs/my%20file.md`); decode before probing so a valid file is
            # not falsely reported as a broken link and failing CI.
            target = unquote(target)
            candidate = facts.resolve_within_root(Path(root) / target, containment_root, strict=False)
            if candidate is None:
                continue
            if not facts.exists_within_root(containment_root, candidate):
                findings.append(
                    {
                        "check": "D7",
                        "level": "ERROR",
                        "line": lineno,
                        "message": f"Markdown link target `{target}` does not exist",
                        "suggestion": "Fix or remove the Markdown link to the missing path.",
                    }
                )
    return findings


def d8_competing_lockfiles(root):
    """Competing package-manager lockfiles committed to the same repo.

    If lockfiles for more than one package manager are present (e.g. both
    `package-lock.json` and `pnpm-lock.yaml`), the intended package manager is
    ambiguous and downstream tooling (and AGENTS.md fact checks) cannot pick a
    ground truth. This is not mechanically auto-fixable — a human must decide
    which manager wins — so it is reported for manual attention.
    """
    present = [
        (name, mgr)
        for name, mgr in LOCKFILE_MANAGERS.items()
        if facts.is_file_within_root(root, root / name)
    ]
    managers = sorted({mgr for _, mgr in present})
    if len(managers) <= 1:
        return []
    names = ", ".join(f"`{name}`" for name, _ in sorted(present))
    return [
        {
            "check": "D8",
            "level": "ERROR",
            "message": f"Competing package-manager lockfiles committed ({names}); intended manager is ambiguous",
            "suggestion": "Keep exactly one lockfile for the chosen package manager and delete the rest.",
        }
    ]


def nested_agents(root):
    out = []
    # Walk with os.walk so we can prune vendored dirs in place and avoid
    # following directory symlinks (which can loop). Reuse the shared
    # registry.prune_walk_dirs so scan.py, facts.py and check_drift.py never
    # maintain divergent skip sets or nested-repository boundary semantics.
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        registry.prune_walk_dirs(dirpath, dirnames)
        if "AGENTS.md" not in filenames:
            continue
        p = Path(dirpath) / "AGENTS.md"
        if p == root / "AGENTS.md":
            continue
        if not facts.is_file_within_root(root, p):
            continue
        out.append(p.relative_to(root).as_posix())
    return sorted(out)


def drift_scopes(root):
    """Return the root and contained nested AGENTS.md drift scopes.

    Content-relative checks prefer each canonical file's parent as their
    fact/path root and use the repository root as a conservative fallback.
    The repository root stays first and nested paths inherit the deterministic,
    pruned, non-symlink-following discovery in ``nested_agents``.
    """
    root = Path(root).resolve()
    scopes = [{"root": root, "path": "AGENTS.md", "is_root": True}]
    for rel_path in nested_agents(root):
        scope_root = root / Path(rel_path).parent
        scopes.append(
            {
                "root": scope_root,
                "path": rel_path,
                "is_root": False,
            }
        )
    return scopes


def _attribute_scope(findings, scope):
    """Attach nested content findings to their canonical source file."""
    if scope["is_root"]:
        # Preserve the historical root finding/baseline shape: root D1/D2/D6/D7
        # findings intentionally omit `path` and use AGENTS.md as the implicit
        # source in SARIF/PR-review integrations.
        return findings
    return [{**finding, "path": scope["path"]} for finding in findings]


SCORE_WEIGHTS = {"ERROR": 15, "NOTICE": 5}


def health_score(findings):
    """Aggregate findings into a 0-100 score and a letter grade."""
    score = 100
    for f in findings:
        score -= SCORE_WEIGHTS.get(f.get("level"), 0)
    score = max(0, score)
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    return score, grade


# --- Baseline support ------------------------------------------------------
# A baseline lets a repo adopt the drift gate immediately: record the current
# (pre-existing) drift once, then fail CI only on NEW drift introduced later.
# This mirrors the baseline feature every mature linter ships (ruff, mypy,
# detekt, ktlint). It is opt-in and additive — with no --baseline flag the
# engine behaves exactly as before.
BASELINE_VERSION = 1
BASELINE_MAINTENANCE_EXIT = scan.BASELINE_MAINTENANCE_EXIT


class BaselineFileError(ValueError):
    """A safe, caller-facing baseline maintenance error."""


def finding_fingerprint(finding):
    """Stable identity for a drift finding, independent of line numbers.

    Line numbers shift on any unrelated AGENTS.md edit, so a baseline keyed on
    them would go stale immediately. The (check, message, path) trio is durable:
    the message already embeds the offending token (script/path/lockfile), so it
    uniquely identifies the drift while surviving line moves.
    """
    return (finding.get("check", ""), finding.get("message", ""), finding.get("path") or "")


def load_baseline(path):
    """Read a baseline file into a set of finding fingerprints.

    Tolerant by design: a missing, blank, or malformed file yields an empty set
    so the guard fails safe (every finding counts as new) rather than crashing
    CI on a bad baseline.
    """
    return load_baseline_store(path)["fingerprints"]


def parse_baseline(data, path="", strict=False):
    valid = (
        isinstance(data, dict)
        and data.get("version") == BASELINE_VERSION
        and isinstance(data.get("findings"), list)
    )
    entries = []
    if valid:
        for entry in data["findings"]:
            entry_valid = (
                isinstance(entry, dict)
                and isinstance(entry.get("check"), str)
                and isinstance(entry.get("message"), str)
                and (
                    entry.get("path") is None
                    or isinstance(entry.get("path"), str)
                )
            )
            if not entry_valid:
                if strict:
                    valid = False
                    break
                continue
            entries.append(
                {
                    "check": entry.get("check", ""),
                    "message": entry.get("message", ""),
                    "path": entry.get("path"),
                }
            )
    if not valid:
        if strict:
            raise BaselineFileError("baseline must be a version-1 drift baseline")
        entries = []
    unique = {finding_fingerprint(entry): entry for entry in entries}
    ordered = sorted(
        unique.values(),
        key=lambda entry: (
            entry["check"] or "",
            entry["message"] or "",
            entry["path"] or "",
        ),
    )
    return {
        "path": str(path),
        "valid": valid,
        "entries": ordered,
        "fingerprints": set(unique),
        "by_fingerprint": {finding_fingerprint(entry): entry for entry in ordered},
    }


def load_baseline_store(path, strict=False):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise BaselineFileError("baseline file is missing or invalid JSON")
        data = None
    return parse_baseline(data, path=path, strict=strict)


def baseline_payload(findings):
    """Build the deterministic baseline document for the given findings.

    Records every ERROR/NOTICE built-in finding (INFO/D5 inventory is not drift)
    as a minimal ``{check, message, path}`` entry, de-duplicated and sorted so
    the file is stable across runs and produces clean git diffs. No timestamp is
    written, keeping the engine deterministic.
    """
    seen = set()
    entries = []
    for f in findings:
        if f.get("level") not in ("ERROR", "NOTICE"):
            continue
        fp = finding_fingerprint(f)
        if fp in seen:
            continue
        seen.add(fp)
        entries.append({"check": f.get("check", ""), "message": f.get("message", ""), "path": f.get("path")})
    entries.sort(key=lambda e: (e["check"] or "", e["message"] or "", e["path"] or ""))
    return {"version": BASELINE_VERSION, "findings": entries}


def run_checks(root, max_bytes, strict=False, rules_dirs=None, allow_plugins=False, baseline=None):
    root = Path(root).resolve()
    scopes = drift_scopes(root)
    root_text = ""
    findings = []
    # One repository-root suffix index shared by every nested scope's
    # uniqueness fallback; built lazily on the first nested miss (Plan 070).
    repository_index_cache = {}
    for scope in scopes:
        text = facts.read_text_within_root(root, root / scope["path"], errors="replace") or ""
        if scope["is_root"]:
            root_text = text
        scoped = []
        fallback_root = root if not scope["is_root"] else None
        ancestors = (
            facts.ancestor_dirs(scope["root"], root)
            if not scope["is_root"]
            else [root]
        )
        scoped.extend(
            d1_command_drift(
                scope["root"],
                text,
                fallback_root=fallback_root,
                ancestors=ancestors,
            )
        )
        scoped.extend(
            d2_path_drift(
                scope["root"],
                text,
                fallback_root=fallback_root,
                ancestors=ancestors,
                repository_index_cache=repository_index_cache,
            )
        )
        scoped.extend(
            d6_fact_drift(
                scope["root"],
                text,
                fallback_root=fallback_root,
                ancestors=ancestors,
            )
        )
        scoped.extend(d7_markdown_link_drift(scope["root"], text, fallback_root=fallback_root))
        findings.extend(_attribute_scope(scoped, scope))

    # Repository ownership/size/lockfile checks run once. They are not
    # content-relative checks and must not be multiplied by nested scopes.
    findings.extend(d3_stub_regrowth(root))
    findings.extend(d4_size(root, max_bytes))
    findings.extend(d8_competing_lockfiles(root))
    if strict:
        for f in findings:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    # Baseline suppression: split off findings already recorded in the baseline
    # so only NEW drift affects ok/score/exit code. Suppressed findings stay in
    # the report under `baselined` for visibility but are never counted as
    # failures. Fingerprints ignore line numbers, so re-runs stay stable.
    baselined = []
    if baseline:
        baseline_fps = baseline["fingerprints"] if isinstance(baseline, dict) else baseline
        baseline_entries = baseline["entries"] if isinstance(baseline, dict) else []
        current_fps = {finding_fingerprint(f) for f in findings}
        kept = []
        for f in findings:
            (baselined if finding_fingerprint(f) in baseline_fps else kept).append(f)
        findings = kept
        resolved_baseline = [
            entry
            for entry in baseline_entries
            if finding_fingerprint(entry) not in current_fps
        ]
    else:
        resolved_baseline = []
    info = [
        {
            "check": "D5",
            "level": "INFO",
            "path": scope["path"],
            "message": "Nested AGENTS.md inventory",
        }
        for scope in scopes
        if not scope["is_root"]
    ]
    # User-extensible deterministic rule plugins (opt-in, default OFF). Plugin
    # files live inside the scanned repo, so importing them runs arbitrary code
    # on the host/CI; discovery + execution therefore happens ONLY when the
    # caller opts in via --allow-plugins. Otherwise this is a no-op returning an
    # empty list. Discovered from <root>/.ai-harness-doctor/rules/*.py plus any
    # --rules DIR; each plugin is isolated so a broken one is reported as an
    # ERROR finding, never a crash. Custom findings are reported additively
    # under `custom`; they do not alter the built-in D1-D8 health score.
    custom = plugins.run_plugins(
        root,
        {"phase": "drift", "agents_text": root_text},
        rules_dirs,
        allow_plugins=allow_plugins,
    )
    if strict:
        for f in custom:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    failures = [f for f in findings if f.get("level") == "ERROR"]
    score, grade = health_score(findings)
    report = {
        "ok": not failures,
        "findings": findings,
        "info": info,
        "custom": custom,
        "baselined": baselined,
        "score": score,
        "grade": grade,
    }
    if isinstance(baseline, dict):
        report["resolved_baseline"] = resolved_baseline
        report["baseline"] = {
            "path": baseline.get("path", ""),
            "known": len(baselined),
            "resolved": len(resolved_baseline),
        }
    return report


def render(report):
    lines = ["# Phase 2 — Follow-up Drift Guard Report", ""]
    if report["ok"]:
        lines.append("No blocking drift found.")
    for check in ["D1", "D2", "D3", "D4", "D6", "D7", "D8"]:
        items = [f for f in report["findings"] if f["check"] == check]
        if not items:
            continue
        lines.extend(["", f"## {check}"])
        for f in items:
            loc = _finding_loc(f)
            lines.append(f"- **{f['level']}**{loc} {f['message']} Repair advice: {f['suggestion']}")
    lines.extend(["", "## D5 Nested AGENTS.md (informational, non-blocking)"])
    if report["info"]:
        lines.extend(f"- `{i['path']}`" for i in report["info"])
    else:
        lines.append("None.")
    custom = report.get("custom", [])
    lines.extend(["", "## Custom rule plugins"])
    if custom:
        for f in custom:
            loc = f":{f['line']}" if "line" in f else (f" `{f['path']}`" if "path" in f else "")
            suggestion = f" Repair advice: {f['suggestion']}" if f.get("suggestion") else ""
            lines.append(
                f"- **{f['level']}** [{f.get('plugin', '?')}:{f.get('rule', 'custom')}]{loc} {f['message']}{suggestion}"
            )
    else:
        lines.append("None.")
    baselined = report.get("baselined", [])
    if baselined:
        lines.extend(
            [
                "",
                "## Baseline",
                f"{len(baselined)} pre-existing finding(s) suppressed by the baseline "
                "(not counted as failures).",
            ]
        )
    resolved = report.get("resolved_baseline", [])
    if resolved:
        lines.extend(
            [
                "",
                "## Resolved baseline debt",
                f"{len(resolved)} baseline finding(s) are no longer present and ready to prune "
                "with `--baseline FILE --prune-baseline`.",
            ]
        )
    lines.extend(["", "## Health score", f"Score: {report['score']}/100 (grade {report['grade']})"])
    return "\n".join(lines) + "\n"


def canonical_stub_content(root, rel_path):
    """Return the minimal canonical stub content for a regrown stub path.

    Reuses canonicalize.STUBS (path -> content) and the Cursor rule template so
    the auto-fix rewrites drift back to exactly what canonicalize.py would write.
    Returns None if the path is not a known auto-fixable tool stub.
    """
    for spec in canonicalize.STUBS.values():
        if rel_path in spec["paths"]:
            return spec["content"]
    posix = Path(rel_path).as_posix()
    if posix.startswith(".cursor/rules/"):
        return canonicalize.CURSOR_RULE_STUB
    return None


def _finding_loc(f):
    if "path" in f and "line" in f:
        return f" `{f['path']}:{f['line']}`"
    if "line" in f:
        return f":{f['line']}"
    if "path" in f:
        return f" `{f.get('path')}`"
    return ""


def run_fix(root, max_bytes, apply, strict=False, rules_dirs=None, allow_plugins=False, baseline=None):
    """Auto-repair ONLY the safe, mechanical subset of drift (D3 stub regrowth).

    Dry run by default (writes nothing); with apply=True actually rewrites the
    regrown tool stubs back to their minimal canonical import-stub form. Any drift
    that is not safely auto-fixable is reported as "needs manual attention" and its
    files are left untouched.
    """
    report = run_checks(root, max_bytes, strict, rules_dirs, allow_plugins=allow_plugins, baseline=baseline)
    d3 = [f for f in report["findings"] if f["check"] == "D3"]
    manual = [f for f in report["findings"] if f["check"] != "D3" and f.get("level") in ("ERROR", "NOTICE")]

    lines = ["# check_drift --fix (%s)" % ("apply" if apply else "dry run"), ""]
    fixed = 0
    skipped = []

    lines.append("## Auto-fixable: D3 stub regrowth")
    if not d3:
        lines.append("- None.")
    unsafe = []
    for f in d3:
        rel_path = f["path"]
        if canonical_stub_content(root, rel_path) is None:
            continue
        if facts.safe_mutation_path(root, root / rel_path) is None:
            unsafe.append(
                {
                    **f,
                    "message": f"Unsafe repository mutation target `{rel_path}` is a symlink or escapes the root",
                    "suggestion": "Replace the symlink with an owned regular file before applying fixes.",
                }
            )
    if unsafe:
        skipped.extend(unsafe)
        unsafe_paths = {f["path"] for f in unsafe}
        d3 = [f for f in d3 if f["path"] not in unsafe_paths]
    for f in d3:
        rel_path = f["path"]
        path = root / rel_path
        new = canonical_stub_content(root, rel_path)
        if new is None:
            skipped.append(f)
            continue
        old = facts.read_text_within_root(root, path, errors="replace") or ""
        if old == new:
            continue
        fixed += 1
        if apply:
            if facts.safe_mutation_path(root, path) is None:
                skipped.append(
                    {
                        **f,
                        "message": f"Unsafe repository mutation target `{rel_path}` changed before apply",
                        "suggestion": "Retry after replacing the symlink with an owned regular file.",
                    }
                )
                fixed -= 1
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
            lines.append(f"- rewrote `{rel_path}` back to minimal canonical stub")
        else:
            lines.append(f"- would rewrite `{rel_path}` back to minimal canonical stub:")
            lines.append("")
            lines.append("```diff")
            lines.append(canonicalize.unified_diff(Path(rel_path), old, new).rstrip("\n"))
            lines.append("```")

    # Stubs flagged as D3 but with no known canonical form fall back to manual.
    manual = manual + skipped

    lines.extend(["", "## Needs manual attention (not safely auto-fixable)"])
    if manual:
        for f in manual:
            loc = _finding_loc(f)
            lines.append(
                f"- needs manual attention: **{f['check']}**{loc} {f['message']} — {f.get('suggestion', '')}".rstrip(
                    " —"
                )
            )
    else:
        lines.append("- None.")

    action = "fixed" if apply else "fixable"
    lines.extend(["", f"Summary: {fixed} {action}, {len(manual)} need manual attention."])
    text = "\n".join(lines) + "\n"

    # Exit non-zero while drift remains. After --apply the D3 items are resolved,
    # so only manual items keep it failing; in dry run the pending fixes also count.
    remaining = len(manual) + (0 if apply else fixed)
    return text, 0 if remaining == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check AGENTS.md drift.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--sarif", action="store_true", help="Emit SARIF 2.1.0 JSON for GitHub code scanning.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--fix", action="store_true", help="Auto-repair the safe subset (D3 stub regrowth); dry run unless --apply."
    )
    parser.add_argument("--apply", action="store_true", help="With --fix, actually rewrite files instead of a dry run.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument(
        "--allow-plugins",
        action="store_true",
        help="Opt in to executing custom rule plugins (`*.py`) found inside the scanned repo "
        "or in --rules DIRs. SECURITY: this runs arbitrary code from the target repository; "
        "it is OFF by default and no plugin code is discovered or imported without this flag.",
    )
    parser.add_argument(
        "--rules",
        action="append",
        default=None,
        metavar="DIR",
        dest="rules",
        help="Directory of custom rule plugins (`*.py` exposing `check(root, context)`). "
        "Repeatable; searched in addition to `<repo>/.ai-harness-doctor/rules/`.",
    )
    parser.add_argument(
        "--min-score", type=int, default=None, help="Exit non-zero if the health score is below N (CI gating)."
    )
    parser.add_argument(
        "--baseline",
        metavar="FILE",
        default=None,
        help="Suppress drift already recorded in FILE so CI fails only on NEW drift. "
        "Fingerprints are line-number independent; a missing/malformed file suppresses nothing.",
    )
    parser.add_argument(
        "--write-baseline",
        metavar="FILE",
        default=None,
        dest="write_baseline",
        help="Record the current findings to FILE as a baseline and exit 0 "
        "(adopt the drift gate on a repo with pre-existing drift). Deterministic; no timestamp.",
    )
    parser.add_argument(
        "--check-baseline",
        action="store_true",
        help=f"Exit {BASELINE_MAINTENANCE_EXIT} when FILE contains resolved/stale debt. Requires --baseline.",
    )
    parser.add_argument(
        "--prune-baseline",
        action="store_true",
        help="Atomically remove only resolved/stale entries from --baseline FILE and exit 0.",
    )
    args = parser.parse_args(argv)
    if (args.check_baseline or args.prune_baseline) and not args.baseline:
        print("error: --check-baseline/--prune-baseline requires --baseline FILE", file=sys.stderr)
        return 1
    if args.write_baseline and (args.baseline or args.check_baseline or args.prune_baseline):
        print(
            "error: --write-baseline cannot be combined with --baseline maintenance modes",
            file=sys.stderr,
        )
        return 1
    if args.check_baseline and args.prune_baseline:
        print("error: --check-baseline and --prune-baseline are mutually exclusive", file=sys.stderr)
        return 1
    if (args.check_baseline or args.prune_baseline) and args.fix:
        print("error: baseline maintenance modes cannot be combined with --fix", file=sys.stderr)
        return 1
    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        message = f"error: not a directory: {args.repo_root}"
        if args.as_json:
            print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
        else:
            print(message, file=sys.stderr)
        return 1
    # Executing plugins runs untrusted code from the scanned repo; warn loudly.
    if args.allow_plugins:
        print(
            "WARNING: --allow-plugins enabled: executing untrusted rule plugin code from the "
            "scanned repository (<repo>/.ai-harness-doctor/rules/ and any --rules DIR).",
            file=sys.stderr,
        )
    # --write-baseline records the CURRENT natural findings (never baseline-filtered,
    # strict OFF so NOTICE-level drift is captured too) and exits 0. It takes
    # precedence over --baseline/--fix/report output so the recording step is a
    # dedicated, side-effect-only mode.
    if args.write_baseline:
        report = run_checks(root, args.max_bytes, strict=False, rules_dirs=args.rules, allow_plugins=args.allow_plugins)
        payload = baseline_payload(report["findings"])
        scan.write_json_atomic(args.write_baseline, payload)
        print(f"Wrote baseline with {len(payload['findings'])} finding(s) to {args.write_baseline}")
        return 0
    try:
        baseline = (
            load_baseline_store(
                args.baseline,
                strict=args.check_baseline or args.prune_baseline,
            )
            if args.baseline
            else None
        )
    except BaselineFileError as exc:
        print(f"baseline error: {exc}", file=sys.stderr)
        return 1
    if args.fix:
        text, code = run_fix(
            root,
            args.max_bytes,
            args.apply,
            args.strict,
            args.rules,
            allow_plugins=args.allow_plugins,
            baseline=baseline,
        )
        print(text, end="")
        return code
    report = run_checks(
        root, args.max_bytes, args.strict, args.rules, allow_plugins=args.allow_plugins, baseline=baseline
    )
    if args.prune_baseline:
        resolved_fps = {
            finding_fingerprint(entry)
            for entry in report["resolved_baseline"]
        }
        kept = [
            entry
            for entry in baseline["entries"]
            if finding_fingerprint(entry) not in resolved_fps
        ]
        scan.write_json_atomic(
            args.baseline,
            {"version": BASELINE_VERSION, "findings": kept},
        )
        print(
            f"Pruned {len(report['resolved_baseline'])} resolved drift baseline finding(s); "
            f"{len(kept)} known finding(s) remain."
        )
        return 0
    exit_code = 0 if report["ok"] else 1
    if args.min_score is not None and report["score"] < args.min_score:
        exit_code = exit_code or 2
    if exit_code == 0 and args.check_baseline and report["resolved_baseline"]:
        exit_code = BASELINE_MAINTENANCE_EXIT
    # SARIF takes precedence over --json/markdown but preserves the same exit
    # semantics (--strict / --min-score) as the normal path.
    if args.sarif:
        import sarif  # noqa: E402  # sibling module (scripts/ is on sys.path)

        print(json.dumps(sarif.drift_report_to_sarif(report), ensure_ascii=False, indent=2))
        return exit_code
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report), end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
