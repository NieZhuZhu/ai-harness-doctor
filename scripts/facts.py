#!/usr/bin/env python3
"""Shared repository fact-readers for the semantic engine and the drift gate.

Phase-0 (``semantic.py``) and the Phase-2 drift gate (``check_drift.py``) both need
to read the SAME ground-truth facts out of a repository — package.json scripts,
Makefile targets, the committed lockfile's package manager, the pinned Node
version (``.nvmrc`` / ``engines.node``), the package managers a doc *declares*, and
the shared code-span / prose heuristics used to parse commands. Those readers used
to be copy-pasted near-verbatim into both modules and could silently drift — the
exact failure mode this whole tool exists to catch (TD-02). They now live here as
the single source of truth; both engines import them so every fact is read one way.

Python 3.9 standard library only; no runtime dependencies.
"""

import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# scripts/ holds the shared agent-config registry (lockfile->manager map, the
# Node-version regex, etc.). Add it to sys.path so importing this module
# standalone still resolves ``registry``.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry  # noqa: E402

# Package-manager subcommands that are always valid regardless of package.json;
# a reference to one of these is never a "missing script". Shared so the Phase-0
# semantic engine and the Phase-2 drift gate agree on what counts as a "real"
# script name.
PACKAGE_MANAGER_BUILTINS = {
    "install",
    "ci",
    "i",
    "init",
    "add",
    "remove",
    "rm",
    "uninstall",
    "update",
    "up",
    "upgrade",
    "exec",
    "dlx",
    "create",
    "audit",
    "link",
    "unlink",
    "publish",
    "outdated",
    "config",
    "cache",
    "login",
    "logout",
    "whoami",
    "version",
    "info",
    "list",
    "ls",
    "why",
    "dedupe",
    "prune",
    "rebuild",
    "help",
    "test",
    "start",
    "workspace",
    "workspaces",
}


# English function words whose presence marks a code span as an English prose
# sentence (a comment or descriptive line) rather than a shell command. Extracting
# a "command" from such prose only produces phantom targets (CORR-02).
_PROSE_WORDS = frozenset(
    {
        "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "if",
        "then", "that", "this", "your", "you", "we", "is", "are", "be", "should",
        "must", "will", "can", "please", "before", "after", "when", "which",
        "with", "into", "sure",
    }
)
# Words that appear as the object of a common English imperative ("make sure",
# "make certain", "make the ...") — never real Makefile targets / npm scripts.
# Guards the short (sub-sentence) prose case that _looks_like_prose misses.
_PROSE_TARGET_WORDS = frozenset(
    {"sure", "certain", "it", "them", "the", "a", "an", "use", "do", "note", "your", "this", "that"}
)


def looks_like_prose(segment):
    """Return True when a code span reads as an English prose sentence rather than
    a shell command line, so command extraction from it would be spurious.

    Splits on whitespace only, not on internal punctuation: a hyphen/colon-
    joined identifier (``lint-and-fix``, ``build:on:save``) is a single
    command/target/script token, not standalone English words. Previously
    ``[A-Za-z']+`` extracted sub-words from inside such identifiers too, so
    e.g. the "and" in ``make lint-and-fix`` counted as a prose-word hit and
    the whole line was misread as a sentence, silently disabling the D1
    command-drift check for any command name shaped like that (CORRECTNESS-01).
    """
    words = []
    for token in segment.lower().split():
        if "-" in token or ":" in token:
            continue
        words.extend(re.findall(r"[a-z']+", token))
    if len(words) < 4:
        return False
    return any(w in _PROSE_WORDS for w in words)


def iter_code_tokens(text):
    """Yield ``(lineno, token)`` for fenced-code lines and inline backtick spans.

    Commands frequently live inside ```` ```bash ```` fences as well as inline
    ``code`` spans, so both are scanned. This is the single shared code-span
    tokenizer used by both the semantic engine and the drift gate.
    """
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        # Inside a fenced block a line beginning with `#` is a shell comment, not
        # a command; skip it so prose in comments (e.g. "# make sure the tests
        # pass") is not misread as a command (CORR-02).
        if in_fence and not line.strip().startswith("#"):
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


def within_root(root, token):
    """Return True only if ``token`` resolves to a path contained in ``root``.

    Both engines read backtick tokens from an untrusted AGENTS.md and probe them
    on disk. ``pathlib`` happily lets an absolute (``/etc/hostname``) or
    ``../``-escaping token point outside the repo, which would let a malicious
    AGENTS.md infer the existence of arbitrary filesystem paths. Reject anything
    that does not stay under the repo root before calling ``.exists()``.
    """
    return resolves_within_root(root / token, root, strict=False)


def resolve_within_root(path, root, strict=True):
    """Resolve ``path`` only when it remains inside ``root``.

    Repository manifests are untrusted scan inputs too: a lexical
    ``repo/package.json`` may be a symlink to a file outside the audited tree.
    Every fact reader uses this helper before probing or reading a path so
    external symlinks cannot influence semantic/drift output. In-repo symlinks
    remain supported. Returns the resolved path, or ``None`` on escape,
    non-existence (when ``strict``), or resolution errors.
    """
    try:
        resolved_root = Path(root).resolve()
        candidate = Path(path).resolve(strict=strict)
        candidate.relative_to(resolved_root)
        return candidate
    except (OSError, ValueError):
        return None


def resolves_within_root(path, root, strict=True):
    """Return whether ``path`` resolves inside ``root``."""
    return resolve_within_root(path, root, strict=strict) is not None


def is_file_within_root(root, path):
    """Return True only for a regular file contained by ``root``."""
    candidate = resolve_within_root(path, root)
    return candidate is not None and candidate.is_file()


def is_dir_within_root(root, path):
    """Return True only for a directory contained by ``root``."""
    candidate = resolve_within_root(path, root)
    return candidate is not None and candidate.is_dir()


def exists_within_root(root, path):
    """Return True only for an existing path contained by ``root``."""
    return resolve_within_root(path, root) is not None


def ancestor_dirs(scope_root, repository_root):
    """Return contained lexical directories nearest-first through repo root."""
    scope_root = Path(scope_root).resolve()
    repository_root = Path(repository_root).resolve()
    if scope_root != repository_root and repository_root not in scope_root.parents:
        raise ValueError("scope escapes repository")
    directories = []
    current = scope_root
    while True:
        directories.append(current)
        if current == repository_root:
            return directories
        current = current.parent


def repository_ignored_paths(root, tokens, timeout=5):
    """Return contained relative paths ignored by repository ``.gitignore`` files.

    Git supplies the matcher so nested rules and negation keep their native
    semantics. A synthetic metadata directory prevents the audited repository's
    ``.git/config`` and ``.git/info/exclude`` (plus user/system config) from
    changing deterministic scan output. Any unavailable or ambiguous result
    fails closed to an empty set, preserving existing missing-path findings.
    """
    root = Path(root).resolve()
    candidates = []
    originals_by_candidate = {}
    for value in tokens:
        token = str(value)
        if (
            not token
            or "\0" in token
            or resolve_within_root(root / token, root, strict=False) is None
        ):
            continue
        normalized = Path(os.path.normpath(token)).as_posix()
        normalized = posixpath.normpath(normalized)
        if normalized in ("", ".", "..") or normalized.startswith("../"):
            continue
        if token.endswith("/") and not normalized.endswith("/"):
            normalized += "/"
        if normalized not in originals_by_candidate:
            candidates.append(normalized)
            originals_by_candidate[normalized] = []
        originals_by_candidate[normalized].append(token)
    if not candidates:
        return set()

    try:
        temp_parent = Path(tempfile.gettempdir()).resolve()
        try:
            temp_parent.relative_to(root)
        except ValueError:
            pass
        else:
            # Scanning is read-only. A caller-controlled TMPDIR inside the
            # audited repository must not turn ignore classification into a
            # repository write; retain existing missing-path findings instead.
            return set()
        with tempfile.TemporaryDirectory(prefix="ai-harness-doctor-gitignore-") as td:
            temp_root = Path(td)
            git_dir = temp_root / "git"
            for relative in (
                "objects/info",
                "objects/pack",
                "refs/heads",
                "refs/tags",
                "info",
            ):
                (git_dir / relative).mkdir(parents=True, exist_ok=True)
            (git_dir / "HEAD").write_text(
                "ref: refs/heads/main\n",
                encoding="utf-8",
            )
            (git_dir / "config").write_text(
                "[core]\n"
                "\trepositoryformatversion = 0\n"
                "\tbare = false\n"
                "\tfilemode = true\n",
                encoding="utf-8",
            )
            (git_dir / "info" / "exclude").write_text("", encoding="utf-8")

            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            }
            env.update(
                {
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull,
                    "GIT_OPTIONAL_LOCKS": "0",
                    "HOME": str(temp_root),
                    "XDG_CONFIG_HOME": str(temp_root),
                }
            )
            proc = subprocess.run(
                [
                    "git",
                    f"--git-dir={git_dir}",
                    f"--work-tree={root}",
                    "-c",
                    f"core.excludesFile={os.devnull}",
                    "-c",
                    "core.fsmonitor=false",
                    "check-ignore",
                    "--no-index",
                    "-z",
                    "--stdin",
                ],
                input=b"".join(
                    token.encode("utf-8") + b"\0" for token in candidates
                ),
                capture_output=True,
                timeout=timeout,
                env=env,
            )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return set()

    if proc.returncode == 1:
        return set()
    if (
        proc.returncode != 0
        or proc.stderr
        or not proc.stdout
        or not proc.stdout.endswith(b"\0")
    ):
        return set()
    try:
        ignored = {
            item.decode("utf-8")
            for item in proc.stdout[:-1].split(b"\0")
            if item
        }
    except UnicodeError:
        return set()
    if not ignored.issubset(originals_by_candidate):
        return set()
    return {
        original
        for candidate in ignored
        for original in originals_by_candidate[candidate]
    }


def read_text_within_root(root, path, errors="strict"):
    """Read a contained file, returning ``None`` when it is unsafe/unreadable."""
    candidate = resolve_within_root(path, root)
    if candidate is None or not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8", errors=errors)
    except OSError:
        return None


def read_bytes_within_root(root, path):
    """Read bytes from a contained file, returning ``None`` when unsafe/unreadable."""
    candidate = resolve_within_root(path, root)
    if candidate is None or not candidate.is_file():
        return None
    try:
        return candidate.read_bytes()
    except OSError:
        return None


def load_json_within_root(root, path):
    """Parse a contained JSON object, returning ``None`` when unsafe/invalid."""
    text = read_text_within_root(root, path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def safe_mutation_path(root, path):
    """Return a lexical in-root path only when no existing component is a symlink.

    Read containment may safely follow an in-repo symlink and inspect its
    resolved target. Mutations need a stricter contract: preserving the lexical
    path matters, and writes/deletes must never follow either a target symlink
    or a symlinked parent directory. Missing trailing components are allowed so
    callers can create a new file below an existing, symlink-free parent.
    """
    try:
        lexical_root = Path(root).resolve(strict=True)
        lexical_path = Path(os.path.abspath(str(path)))
        relative = lexical_path.relative_to(lexical_root)
        current = lexical_root
        missing_parent = False
        for part in relative.parts:
            current = current / part
            if missing_parent:
                continue
            try:
                if current.is_symlink():
                    return None
                current.lstat()
            except FileNotFoundError:
                missing_parent = True
            except OSError:
                return None
        return lexical_path
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Repository facts — what the code actually says.
# ---------------------------------------------------------------------------


def package_scripts(root):
    """Return the set of package.json script names.

    ``None`` when there is nothing to verify against: either no package.json
    exists, or it is present but could not be read/parsed. Returning ``None``
    (rather than an empty ``set()``) on a parse failure keeps "invalid JSON"
    distinct from "valid JSON with no scripts", so callers skip the unknown-
    script check instead of falsely reporting every referenced script as unknown
    (CORR-01).
    """
    path = root / "package.json"
    data = load_json_within_root(root, path)
    if data is None:
        return None
    scripts = data.get("scripts")
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


def package_name(root):
    """Return the exact local package.json name, or ``None`` if unavailable."""
    data = load_json_within_root(root, Path(root) / "package.json")
    name = data.get("name") if isinstance(data, dict) else None
    return name if isinstance(name, str) and name else None


def _walk_package_jsons(root):
    """Yield the parsed dict of every readable ``package.json`` under root
    (root plus nested/workspace packages), skipping vendored dirs. Shared by
    ``all_package_scripts`` and ``all_package_names`` so a repo-wide walk
    happens at most once per fact, not once per fact PER CALLER. Uses
    ``os.walk`` with directory pruning (not ``Path.rglob``) so a huge
    unrelated ``node_modules`` never gets traversed.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        registry.prune_walk_dirs(dirpath, dirnames)
        if "package.json" not in filenames:
            continue
        text = read_text_within_root(root, Path(dirpath) / "package.json")
        if text is None:
            continue
        try:
            yield json.loads(text)
        except Exception:
            continue


def all_package_scripts(root):
    """Union of package.json script names across every package.json in the
    repo (root plus nested/workspace packages), skipping vendored dirs.

    Monorepo AGENTS.md commonly documents per-package commands ("run these
    from within packages/foo") that a root-only lookup can't see — checking
    a monorepo's AGENTS.md against just ``package_scripts(root)`` produced a
    false MISMATCH (found scanning vercel/ai, whose root AGENTS.md documents
    `pnpm test:node` / `pnpm build:watch`, which live in packages/ai's
    package.json, not the pnpm-workspace root's).

    ``None`` only when there is no package.json anywhere under root, mirroring
    ``package_scripts``'s None-vs-empty-set contract (CORR-01).
    """
    found_any = False
    names = set()
    for data in _walk_package_jsons(root):
        found_any = True
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            names.update(scripts.keys())
    return names if found_any else None


def all_package_names(root):
    """Union of every package.json ``name`` field under root (root plus
    nested/workspace packages), skipping vendored dirs.

    A backtick-quoted token whose first path segment matches one of these is
    a package self-import specifier — `better-auth/test` imports
    packages/better-auth's own `test` export subpath — not a repo-relative
    filesystem path. Found scanning better-auth/better-auth's AGENTS.md,
    where this was flagged MISSING even though the package resolves fine.
    """
    names = set()
    for data in _walk_package_jsons(root):
        name = data.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def all_package_dependency_names(root):
    """Union of dependency names across every contained package.json."""
    names = set()
    for data in _walk_package_jsons(root):
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            section = data.get(key)
            if isinstance(section, dict):
                names.update(section.keys())
    return names


# Build-system manifest/lockfile basenames that are ubiquitous and routinely
# referenced generically in an AGENTS.md ("if you change `Cargo.toml` or
# `Cargo.lock`, run ...", "check the closest `pyproject.toml`"). A bare mention
# is not a repo-root path assertion, so it should resolve against any such file
# anywhere in the repo, not just one sitting at the root. Single-source this
# from the registry's KNOWN_ROOT_FILES (the same set the path detector uses to
# emit single-segment tokens at all) so the two can never drift apart — the
# exact TD-02 duplication failure this tool exists to catch.
_MANIFEST_BASENAMES = registry.KNOWN_ROOT_FILES


def is_subtree_path_candidate(token):
    """Whether ``token`` is eligible for conservative subtree resolution."""
    return "/" in token or token in _MANIFEST_BASENAMES


class SubtreePathIndex:
    """Immutable per-run index for workspace-relative path lookups.

    ``suffixes`` contains lexical trailing paths below at least one repository
    directory (the root itself is deliberately omitted because callers already
    check it). ``manifest_basenames`` records only known build/config files in a
    subtree. Directory-symlink aliases need a narrow compatibility fallback:
    ``os.walk(..., followlinks=False)`` does not enumerate their descendants,
    while the historical resolver could still probe ``D/token`` through a safe
    in-repository alias.
    """

    __slots__ = (
        "suffixes",
        "ambiguous_suffixes",
        "manifest_basenames",
        "search_roots",
        "has_safe_dir_alias",
    )

    def __init__(
        self,
        suffixes,
        manifest_basenames,
        search_roots,
        has_safe_dir_alias,
        ambiguous_suffixes=(),
    ):
        self.suffixes = frozenset(suffixes)
        self.ambiguous_suffixes = frozenset(ambiguous_suffixes)
        self.manifest_basenames = frozenset(manifest_basenames)
        self.search_roots = tuple(search_roots)
        self.has_safe_dir_alias = bool(has_safe_dir_alias)

    def resolves(self, root, token):
        is_manifest = "/" not in token and token in _MANIFEST_BASENAMES
        is_multiseg = "/" in token
        if not (is_manifest or is_multiseg):
            return False

        normalized = Path(os.path.normpath(token)).as_posix()
        if is_manifest:
            if normalized in self.manifest_basenames:
                return True
        elif normalized in self.suffixes:
            return True

        # Preserve the old resolver's behavior for safe directory symlinks
        # without following them during index construction (or risking cycles).
        if self.has_safe_dir_alias:
            return any(exists_within_root(root, current / token) for current in self.search_roots)
        return False

    def resolves_uniquely(self, root, token):
        """True when ``token`` matches as a trailing path of exactly ONE entry.

        A nested canonical scope may legitimately reference a directory in a
        *different* subtree of the same repository ("`cmd/enterprise` must not
        import `aimeserver/byted`" written from `deploy/harness/`). The bounded
        per-scope lookup rightly refuses to search sibling packages — a generic
        name (`src/utils`, `dal/po`) existing in several packages is exactly the
        drift that bound exists to catch — but a suffix with exactly one source
        in the whole repository is an unambiguous cross-subtree reference, not
        drift. Uniqueness is required; ambiguous suffixes never resolve here.
        The directory-symlink alias fallback is deliberately excluded: probing
        through aliases cannot establish uniqueness.
        """
        if "/" not in token:
            return False
        normalized = Path(os.path.normpath(token)).as_posix()
        return normalized in self.suffixes and normalized not in self.ambiguous_suffixes


def build_subtree_path_index(root):
    """Build one pruned, containment-safe subtree path index for ``root``."""
    rootp = Path(root).resolve()
    entries = set()
    manifests = set()
    search_roots = []
    has_safe_dir_alias = False

    for dirpath, dirnames, filenames in os.walk(rootp, followlinks=False):
        registry.prune_walk_dirs(dirpath, dirnames)
        current = Path(dirpath)
        if current != rootp:
            search_roots.append(current)

        for name in dirnames:
            path = current / name
            if path.is_symlink():
                if not exists_within_root(rootp, path):
                    continue
                has_safe_dir_alias = True
            entries.add(path.relative_to(rootp).as_posix())

        for name in filenames:
            path = current / name
            if path.is_symlink() and not exists_within_root(rootp, path):
                continue
            entries.add(path.relative_to(rootp).as_posix())

    suffixes = set()
    ambiguous = set()
    for entry in entries:
        parts = entry.split("/")
        # The old resolver skipped the repo root, so a path only resolves as a
        # subtree suffix after removing at least one leading directory. A suffix
        # produced by more than one entry is recorded as ambiguous so
        # ``resolves_uniquely`` can refuse it.
        for index in range(1, len(parts)):
            suffix = "/".join(parts[index:])
            if suffix in suffixes:
                ambiguous.add(suffix)
            else:
                suffixes.add(suffix)
        if len(parts) > 1 and parts[-1] in _MANIFEST_BASENAMES:
            manifests.add(parts[-1])

    return SubtreePathIndex(suffixes, manifests, search_roots, has_safe_dir_alias, ambiguous)


def path_resolves_in_subtree(root, token, index=None):
    """True when a backtick path that is missing at the repo root still resolves
    against a subdirectory of the repo.

    Root ``AGENTS.md`` files are frequently scoped to a subdirectory: codex's
    root ``AGENTS.md`` opens with "In the codex-rs folder where the rust code
    lives" and then documents `app-server/README.md`, `Cargo.toml`, etc.
    relative to ``codex-rs/``; opencode's root ``AGENTS.md`` documents
    `src/config` relative to ``packages/opencode/``. A repo-root-only existence
    check flags all of these MISSING even though the referenced file/dir plainly
    exists one level down.

    Resolution rules (both deliberately conservative to avoid masking genuine
    drift):

    - A multi-segment token (contains ``/``) resolves when some pruned
      directory ``D`` in the repo has ``D/token`` existing — i.e. the full
      declared path matches as a trailing path somewhere below root.
    - A bare, single-segment token resolves only when it is a well-known build
      manifest/config basename (``_MANIFEST_BASENAMES``) and any such file
      exists anywhere in the repo.

    ``index`` may be reused across many tokens in one diagnostic call. Omitting
    it preserves the historical single-call API and builds one temporary index.
    """
    if not is_subtree_path_candidate(token):
        return False
    index = index or build_subtree_path_index(root)
    return index.resolves(Path(root).resolve(), token)


def package_dependency_names(root):
    """Return dependency names declared in package.json, or ``None`` if unreadable.

    Covers ``dependencies``, ``devDependencies``, ``peerDependencies``, and
    ``optionalDependencies``. Used as fallback ground truth for yarn/pnpm
    binary passthrough when ``node_modules/.bin`` has not been installed.
    Mirrors ``package_scripts``'s None-vs-empty-set contract (CORR-01).
    """
    path = root / "package.json"
    data = load_json_within_root(root, path)
    if data is None:
        return None
    names = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.update(section.keys())
    return names


def node_modules_bin_names(root):
    """Return binary names present in ``node_modules/.bin``, or ``None`` if absent."""
    bin_dir = root / "node_modules" / ".bin"
    resolved_bin_dir = resolve_within_root(bin_dir, root)
    if resolved_bin_dir is None or not resolved_bin_dir.is_dir():
        return None
    try:
        return {p.name for p in resolved_bin_dir.iterdir()}
    except OSError:
        return None


# Yarn, pnpm, and Bun can execute a binary straight out of
# ``node_modules/.bin`` without an explicit ``run``/``exec`` token — e.g.
# `yarn vitest`, `pnpm mastra dev`, and `bun vitest`. npm has no such fallback
# (`npm vitest` is an unknown command). Keep this fact shared by semantic.py and
# check_drift.py.
_BIN_PASSTHROUGH_TOOLS = {"yarn", "pnpm", "bun"}


def is_node_bin_passthrough(root, tool, name):
    """True if ``tool name`` is a legitimate package binary passthrough.

    Prefers the installed ``node_modules/.bin`` ground truth when available (it
    reflects the binary's real name, e.g. ``tsc`` from the ``typescript``
    package); falls back to the declared dependency names for repositories
    scanned without ``node_modules`` installed.
    """
    if tool not in _BIN_PASSTHROUGH_TOOLS:
        return False
    bin_names = node_modules_bin_names(root)
    if bin_names is not None:
        return name in bin_names
    deps = package_dependency_names(root)
    return deps is not None and name in deps


def is_yarn_bin_passthrough(root, tool, name):
    """Backward-compatible alias for the shared yarn/pnpm passthrough policy."""
    return is_node_bin_passthrough(root, tool, name)


_ESLINT_CONFIG_NAMES = (
    "eslint.config.js",
    "eslint.config.mjs",
    "eslint.config.cjs",
    "eslint.config.ts",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
)


def is_eslint_rule_identifier(root, token):
    """Return whether ``token`` is a configured ESLint ``plugin/rule`` id.

    Rule ids resemble two-segment filesystem paths. Require the exact quoted
    token to appear in a contained, package-root ESLint config instead of
    guessing from prose or suppressing arbitrary hyphenated paths.
    """
    if token.count("/") != 1 or "." in token.rsplit("/", 1)[-1]:
        return False
    for name in _ESLINT_CONFIG_NAMES:
        text = read_text_within_root(root, Path(root) / name, errors="replace")
        if text is None:
            continue
        if any(quote + token + quote in text for quote in ("'", '"', "`")):
            return True
    return False


# --- Import-path / code-symbol classification (repo context) ----------------
# Multi-language monorepo docs routinely backtick NON-filesystem identifiers
# whose interior `/` makes them look like repo paths: short-form Go import
# paths (`gopkg/logs`, `Shopify/sarama`, `net/http`), npm package subpath
# imports (`next/link`), and Go exported symbols (`remote/RemoteBus`). Ground
# truth lives in repository manifests (go.mod, package.json), so this is
# repo-context classification that belongs here — consumed identically by
# ``semantic.compare_paths`` and ``check_drift.d2_path_drift`` (TD-02/TD-03).
# Found auditing a production Go+JS+Swift monorepo whose AGENTS.md files
# produced ~50 such false "path does not exist" findings (Plan 070).

# Go standard-library MULTI-SEGMENT package paths, exact. A first-segment-only
# heuristic misclassified ordinary local directory names (`os/config`,
# `log/rotate`) as stdlib imports, eating genuine missing-path drift; exact
# membership cannot. Single-segment stdlib names (`fmt`, `errors`) never reach
# the path classifier as slash tokens, so only multi-segment paths are listed.
_GO_STDLIB_PACKAGES = frozenset(
    {
        "archive/tar", "archive/zip", "compress/bzip2", "compress/flate",
        "compress/gzip", "compress/lzw", "compress/zlib", "container/heap",
        "container/list", "container/ring", "crypto/aes", "crypto/cipher",
        "crypto/des", "crypto/dsa", "crypto/ecdh", "crypto/ecdsa",
        "crypto/ed25519", "crypto/elliptic", "crypto/hmac", "crypto/md5",
        "crypto/rand", "crypto/rc4", "crypto/rsa", "crypto/sha1",
        "crypto/sha256", "crypto/sha512", "crypto/subtle", "crypto/tls",
        "crypto/x509", "crypto/x509/pkix", "database/sql",
        "database/sql/driver", "debug/buildinfo", "debug/dwarf", "debug/elf",
        "debug/gosym", "debug/macho", "debug/pe", "debug/plan9obj",
        "encoding/ascii85", "encoding/asn1", "encoding/base32",
        "encoding/base64", "encoding/binary", "encoding/csv", "encoding/gob",
        "encoding/hex", "encoding/json", "encoding/pem", "encoding/xml",
        "go/ast", "go/build", "go/build/constraint", "go/constant", "go/doc",
        "go/doc/comment", "go/format", "go/importer", "go/parser",
        "go/printer", "go/scanner", "go/token", "go/types", "go/version",
        "hash/adler32", "hash/crc32", "hash/crc64", "hash/fnv",
        "hash/maphash", "html/template", "image/color", "image/color/palette",
        "image/draw", "image/gif", "image/jpeg", "image/png",
        "index/suffixarray", "io/fs", "io/ioutil", "log/slog", "log/syslog",
        "math/big", "math/bits", "math/cmplx", "math/rand", "math/rand/v2",
        "mime/multipart", "mime/quotedprintable", "net/http", "net/http/cgi",
        "net/http/cookiejar", "net/http/fcgi", "net/http/httptest",
        "net/http/httptrace", "net/http/httputil", "net/http/pprof",
        "net/mail", "net/netip", "net/rpc", "net/rpc/jsonrpc", "net/smtp",
        "net/textproto", "net/url", "os/exec", "os/signal", "os/user",
        "path/filepath", "regexp/syntax", "runtime/cgo", "runtime/coverage",
        "runtime/debug", "runtime/metrics", "runtime/pprof", "runtime/race",
        "runtime/trace", "sync/atomic", "testing/fstest", "testing/iotest",
        "testing/quick", "testing/slogtest", "text/scanner", "text/tabwriter",
        "text/template", "text/template/parse", "time/tzdata",
        "unicode/utf16", "unicode/utf8",
    }
)


def _go_module_import_paths(text):
    """Import/module paths declared in a go.mod: module, require, replace."""
    paths = []
    in_require = False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if in_require:
            if line == ")":
                in_require = False
                continue
            head = line.split()[0]
            if "/" in head and not head.startswith((".", "/")):
                paths.append(head)
            continue
        parts = line.split()
        if parts[0] == "require" and len(parts) >= 2 and parts[1] == "(":
            in_require = True
            continue
        if parts[0] in ("module", "require") and len(parts) >= 2 and "/" in parts[1]:
            paths.append(parts[1])
        elif parts[0] == "replace" and "=>" in parts:
            for candidate in (parts[1], parts[parts.index("=>") + 1] if parts.index("=>") + 1 < len(parts) else ""):
                if "/" in candidate and not candidate.startswith((".", "/")):
                    paths.append(candidate)
    return paths


def go_import_suffixes(root, directories):
    """Frozenset of ≥2-segment trailing forms of Go import paths visible to a scope.

    For each ``host/p1/…/pn`` import path in a fact-chain go.mod, every trailing
    suffix of ``[p1…pn]`` with at least two segments is recorded — that is how
    docs abbreviate imports (`Shopify/sarama`, `rocketmq-client-go/v2`,
    `gopkg/logs`). The host's second-level domain is prepended first so vanity
    imports match their conventional short form too (`go.uber.org/fx` →
    `uber/fx`).
    """
    suffixes = set()
    for directory in directories:
        text = read_text_within_root(root, Path(directory) / "go.mod", errors="replace")
        if text is None:
            continue
        for path in _go_module_import_paths(text):
            parts = [p for p in path.split("/") if p]
            host, chain = parts[0], parts[1:]
            host_labels = host.split(".")
            if len(host_labels) >= 2 and host_labels[-2]:
                chain = [host_labels[-2]] + chain
            # Only the shapes docs actually abbreviate to: the SLD-prefixed
            # form (`uber/fx`), the org-rooted form (`Shopify/sarama`,
            # `gopkg/logs`), and the repo-plus-major form for /vN modules
            # (`rocketmq-client-go/v2`). Arbitrary deeper tail windows are
            # deliberately NOT recorded — they collide with generic local
            # paths and would eat genuine drift.
            if len(chain) >= 2:
                suffixes.add("/".join(chain))
            if len(chain) >= 3:
                suffixes.add("/".join(chain[1:]))
            if len(chain) >= 2 and re.fullmatch(r"v\d+", chain[-1]):
                suffixes.add("/".join(chain[-2:]))
    return frozenset(suffixes)


def _token_matches_go_import(token, suffixes):
    # A token equal to a recorded suffix, or extending one with subpackage
    # segments (`sourcegraph/conc/pool` on a `…/sourcegraph/conc` require).
    parts = token.split("/")
    return any("/".join(parts[:end]) in suffixes for end in range(len(parts), 1, -1))


def _is_go_stdlib_import(token):
    return token in _GO_STDLIB_PACKAGES


def _is_go_exported_symbol(token):
    # `remote/RemoteBus`: lowercase Go-package-path segments ending in a
    # COMPOUND exported identifier (internal uppercase — `RemoteBus`,
    # `SessionService`). Plain TitleCase words (`Sources/App/Views`,
    # `components/Button`) and all-caps segments (`docs/API`) are ordinary
    # directory shapes and stay path candidates.
    parts = token.split("/")
    if len(parts) < 2 or "." in parts[-1]:
        return False
    last = parts[-1]
    return (
        all(re.fullmatch(r"[a-z][a-z0-9_]*", part) for part in parts[:-1])
        and re.fullmatch(r"[A-Z][A-Za-z0-9_]*", last) is not None
        and any(ch.islower() for ch in last)
        and any(ch.isupper() for ch in last[1:])
    )


def non_path_reference_context(root, directories):
    """Precompute the per-scope facts ``is_import_or_symbol_reference`` needs.

    Callers build this lazily on the first missing token (the common all-paths-
    exist case never pays for it) and reuse it for every later token in the
    same scope.
    """
    directories = [Path(directory) for directory in directories]
    dependency_names = set()
    for directory in directories:
        names = package_dependency_names(directory)
        if names:
            dependency_names.update(names)
    return {
        "root": Path(root),
        "directories": directories,
        "dependency_names": dependency_names,
        "go_suffixes": go_import_suffixes(root, directories),
        "has_go": any(
            is_file_within_root(root, directory / "go.mod") for directory in directories
        ),
    }


def is_import_or_symbol_reference(token, context):
    """True when a missing backtick token is positively identified as a Go/npm
    import path or a Go exported symbol rather than a repo-relative path.

    Every import-shaped classification is additionally gated on the token
    having NO local anchor: when the token's first segment exists as a
    directory in the fact chain (a dependency named `config` beside a real
    `config/` tree, a `docker/` dir beside a `docker/compose` import window),
    the doc plausibly means that local tree, so the missing path stays a
    finding. The exported-symbol shape needs no anchor gate — a CamelCase
    dotless identifier is not a plausible file.
    """
    if "/" in token:
        anchored = has_local_anchor(context["root"], context["directories"], token)
        if not anchored:
            if token.split("/", 1)[0] in context["dependency_names"]:
                return True
            if context["go_suffixes"] and _token_matches_go_import(
                token, context["go_suffixes"]
            ):
                return True
            if context["has_go"] and _is_go_stdlib_import(token):
                return True
    if context["has_go"] and _is_go_exported_symbol(token):
        return True
    return False


def has_local_anchor(root, directories, token):
    """True when the token's first segment exists as a directory under any
    fact-chain directory.

    The reference then plausibly means that local tree (`src/only.ts` written
    next to an existing `src/`), so a repository-wide uniqueness fallback must
    not resolve it into a sibling package — a missing local file is exactly the
    drift the bounded lookup exists to catch.
    """
    first = token.split("/", 1)[0]
    return any(
        is_dir_within_root(root, Path(directory) / first) for directory in directories
    )


def _repository_names(root):
    """Candidate self-names of the repository: git remote URL basenames when a
    readable ``.git/config`` declares any, else the checkout directory name.

    The remote basename is the durable identity; the ambient checkout
    directory name is only trusted as a fallback (CI checkouts conventionally
    match the repo name, but a Docker mount like ``/app`` must not turn every
    ``app/...`` token into a strippable prefix when the remotes say otherwise).
    """
    rootp = Path(root).resolve()
    names = set()
    config_text = read_text_within_root(rootp, rootp / ".git" / "config", errors="replace")
    if config_text:
        for m in re.finditer(r"(?m)^\s*url\s*=\s*(\S+)", config_text):
            base = m.group(1).rstrip("/").rsplit("/", 1)[-1]
            base = base.rsplit(":", 1)[-1]  # scp-like git@host:name.git
            if base.endswith(".git"):
                base = base[:-4]
            if base:
                names.add(base)
    return names or {rootp.name}


def strips_repository_name_prefix(root, token):
    """True when ``token`` is the repository's own name plus a multi-segment
    path that exists under it.

    Deploy/Docker docs habitually spell repo paths from one level above the
    checkout (`kiwis/backend/agentsphere/image/runtime_general.dockerfile`
    written inside the `kiwis` repo). Only an exact self-name match with an
    existing multi-segment remainder is suppressed: a missing remainder stays
    a finding, and a two-segment token (`app/page.tsx`) is never treated as
    name-prefixed — that shape is an ordinary repo path.
    """
    rootp = Path(root).resolve()
    first, sep, rest = token.partition("/")
    if not sep or "/" not in rest or first not in _repository_names(rootp):
        return False
    candidate = resolve_within_root(rootp / rest, rootp, strict=False)
    return candidate is not None and exists_within_root(rootp, candidate)


# Matches a rule/assignment header: one or more whitespace-separated names,
# then `:` or `::`, then an optional immediately-following `=`. Group 3 only
# captures when `=` has NO whitespace before it, which is what distinguishes an
# immediate-expansion assignment (`CFLAGS := -O2`) from a genuine rule with a
# target-specific variable value (`debug: CFLAGS = -g`, space-separated).
_MAKE_TARGET_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+(?:[ \t]+[A-Za-z0-9_.-]+)*)[ \t]*(::?)(=?)")


def make_targets(root):
    path = root / "Makefile"
    text = read_text_within_root(root, path, errors="replace")
    if text is None:
        return None
    targets = set()
    for line in text.splitlines():
        if line.startswith("\t"):
            continue
        m = _MAKE_TARGET_LINE_RE.match(line)
        if not m:
            continue
        # `VAR := value` / `VAR ::= value` is a variable assignment, not a rule.
        if m.group(3) == "=":
            continue
        for name in m.group(1).split():
            # A standard multi-target rule (`build test: deps`) declares every
            # space-separated name before the colon as its own target. Dot-
            # prefixed names are GNU Make's own special targets (.PHONY,
            # .SUFFIXES, ...), never real invokable targets.
            if not name.startswith("."):
                targets.add(name)
    return targets


# ``make`` invocation parsing, shared by the Phase-0 semantic engine and the
# Phase-2 D1 gate (TD-02). The historical extractor was a bare regex
# (``make\s+([A-Za-z0-9_.-]+)``) that misread option flags as targets: every
# ``make -C deploy/harness <target>`` in a real monorepo's AGENTS.md produced an
# "Unknown Makefile target `-C`" finding (14 in one audit), and a glob like
# ``make ep-local-*`` was truncated at the ``*`` and reported as a missing
# ``ep-local`` target (Plan 070).
_MAKE_KEYWORD_RE = re.compile(r"(?:^|[\s;&|(`])make\s")
# Short options that always consume a following separate token as their
# argument. ``-C DIR`` is semantically load-bearing (it moves which Makefile
# defines the target); the others are consumed only so their argument is never
# misread as the target.
_MAKE_SEPARATE_ARG_FLAGS = frozenset({"-f", "-I", "-o", "-W"})
# Long options that consume a following separate token unless written ``=``-joined.
# ``--jobs``/``--load-average``/``--max-load`` are NOT here: GNU getopt_long
# optional arguments bind only in the ``=`` form, so in ``make --jobs build``
# the word ``build`` is a goal, not the jobs count. Like ``-j``, a following
# bare NUMBER is still consumed as the intended argument.
_MAKE_LONG_ARG_OPTIONS = frozenset(
    {"--directory", "--file", "--makefile", "--include-dir", "--old-file",
     "--assume-old", "--what-if", "--new-file", "--assume-new"}
)
_MAKE_LONG_OPTIONAL_NUMERIC_OPTIONS = frozenset(
    {"--jobs", "--load-average", "--max-load"}
)
_MAKE_TARGET_NAME_RE = re.compile(r"[A-Za-z0-9_.-]+")
_MAKE_SHELL_TERMINATORS = frozenset({"&&", "||", ";", "|"})


def iter_make_invocations(segment):
    """Yield ``{"name", "directory"}`` for each ``make`` invocation in a code span.

    ``name`` is the first non-option word after ``make`` (first-target-only,
    matching the historical extractor); ``directory`` is the ``-C``/
    ``--directory`` argument or ``None``. Invocations whose target cannot be
    read confidently — a glob (``ep-local-*``), a shell/Make expansion, a
    quoted fragment — yield nothing, so callers abstain instead of flagging a
    phantom target.
    """
    for keyword in _MAKE_KEYWORD_RE.finditer(segment):
        tokens = segment[keyword.end():].split()
        directory = None
        name = None
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            i += 1
            if tok in _MAKE_SHELL_TERMINATORS or tok.startswith("#"):
                break
            # A lone line-continuation backslash or a quoted fragment (a
            # ``VAR="a b"`` value split by the whitespace tokenizer) is never a
            # target.
            if tok == "\\" or '"' in tok or "'" in tok:
                continue
            if tok.startswith("--"):
                base, sep, value = tok.partition("=")
                if base == "--directory":
                    if sep:
                        directory = directory or value
                    elif i < len(tokens):
                        directory = directory or tokens[i]
                        i += 1
                elif not sep and base in _MAKE_LONG_ARG_OPTIONS and i < len(tokens):
                    i += 1
                elif (
                    not sep
                    and base in _MAKE_LONG_OPTIONAL_NUMERIC_OPTIONS
                    and i < len(tokens)
                    and tokens[i].isdigit()
                ):
                    i += 1
                continue
            if tok.startswith("-") and len(tok) > 1:
                flag, attached = tok[:2], tok[2:]
                if flag == "-C":
                    if attached:
                        directory = directory or attached
                    elif i < len(tokens):
                        directory = directory or tokens[i]
                        i += 1
                elif flag in _MAKE_SEPARATE_ARG_FLAGS and not attached and i < len(tokens):
                    i += 1
                elif flag in ("-j", "-l") and not attached and i < len(tokens) and tokens[i].isdigit():
                    # ``-j``/``-l`` take an OPTIONAL argument; only a bare
                    # number can be one (``make -j 4 build`` vs ``make -j build``).
                    i += 1
                continue
            if "=" in tok:  # VAR=value assignment
                continue
            name = tok
            break
        if name is None:
            continue
        # Trailing sentence punctuation ("run `make build`.") is not part of a
        # target name; a remaining non-target-charset token (glob, ``$(VAR)``)
        # means the invocation cannot be validated confidently — abstain.
        name = name.rstrip(".,;:")
        if not name or not _MAKE_TARGET_NAME_RE.fullmatch(name):
            continue
        yield {"name": name, "directory": directory}


def nvmrc_node_version(root):
    path = root / ".nvmrc"
    text = read_text_within_root(root, path, errors="replace")
    if text is None:
        return None
    m = re.search(r"v?(\d+)", text.strip())
    return int(m.group(1)) if m else None


def engines_node_version(root):
    path = root / "package.json"
    data = load_json_within_root(root, path)
    if data is None:
        return None
    engines = data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    if not node:
        return None
    m = re.search(r"(\d+)", str(node))
    return int(m.group(1)) if m else None


def lockfile_managers(root):
    """Return the set of package managers implied by committed lockfiles.

    Uses the shared ``registry.LOCKFILE_MANAGERS`` map (single source of truth,
    incl. bun) so the semantic engine and the drift gate see the same managers.
    """
    return {
        mgr
        for name, mgr in registry.LOCKFILE_MANAGERS.items()
        if is_file_within_root(root, root / name)
    }


def package_manager_field(root):
    """Return one contained packageManager name, or ``None`` if absent/invalid."""
    data = load_json_within_root(root, root / "package.json")
    field = data.get("packageManager") if isinstance(data, dict) else None
    if not isinstance(field, str):
        return None
    match = re.match(r"([A-Za-z]+)@", field)
    return match.group(1).lower() if match else None


# ---------------------------------------------------------------------------
# Declaration extractors — what AGENTS.md *claims*.
# ---------------------------------------------------------------------------


def declared_node_version(text):
    """Return ``(major, line)`` for a Node.js version declared in AGENTS.md, else ``(None, None)``.

    Uses the shared ``registry.node_version_major`` extractor so the Phase-0 check,
    the Phase-2 D6 drift gate and the scan conflict signal all read the same value
    from a given line (TD-06)."""
    for lineno, line in enumerate(text.splitlines(), 1):
        major = registry.node_version_major(line)
        if major is not None:
            return major, lineno
    return None, None


def declared_package_managers(text):
    """Return the set of Node package managers named in AGENTS.md code spans.

    Includes bun so this matches ``registry.LOCKFILE_MANAGERS`` (TD-01) and so the
    Phase-0 engine and the Phase-2 D6 drift gate agree on what a doc declares."""
    pms = set()
    for _lineno, token in iter_code_tokens(text):
        for m in re.finditer(r"\b(npm|pnpm|yarn|bun)\b", token):
            pms.add(m.group(1))
    return pms
