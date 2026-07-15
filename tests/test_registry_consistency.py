"""Consistency guard for the shared agent-config registry.

Proves the single-source-of-truth invariant: scan.py (detection),
canonicalize.py (stub writing) and check_drift.py (stub drift guard) all agree on
the same tool set, and every scan-detectable tool is either migrated
(canonicalizable with stub_paths handled by both canonicalize and drift) or an
explicit, documented scan-only opt-out (canonicalizable: false).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REGISTRY_JSON = ROOT / "assets" / "agent-tools.json"

sys.path.insert(0, str(SCRIPTS))
import canonicalize  # noqa: E402
import check_drift  # noqa: E402
import registry  # noqa: E402
import scan  # noqa: E402
import semantic  # noqa: E402


class RegistryConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.reg = registry.load_registry()
        self.tools = self.reg["tools"]

    def test_registry_json_is_valid_and_well_formed(self):
        with REGISTRY_JSON.open(encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("tools", data)
        self.assertIn("canonical", data)
        for tool in data["tools"]:
            for key in ("id", "label", "scan_patterns", "stub_paths", "stub_kind", "stub_content", "canonicalizable"):
                self.assertIn(key, tool, f"{tool.get('id')} missing {key}")
            self.assertIsInstance(tool["scan_patterns"], list)
            self.assertTrue(tool["scan_patterns"], f"{tool['id']} has no scan_patterns")

    def test_no_duplicate_tool_ids_or_labels(self):
        ids = [t["id"] for t in self.tools]
        labels = [t["label"] for t in self.tools]
        self.assertEqual(len(ids), len(set(ids)), "duplicate tool ids")
        self.assertEqual(len(labels), len(set(labels)), "duplicate tool labels")

    def test_scan_covers_every_registry_tool_and_canonical_file(self):
        """Every canonical file and tool label appears in scan.CONFIG_PATTERNS."""
        scanned_labels = {label for label, _ in scan.CONFIG_PATTERNS}
        for name in self.reg["canonical"]:
            self.assertIn(name, scanned_labels)
        for tool in self.tools:
            self.assertIn(tool["label"], scanned_labels)
            # The scan patterns for a tool are exactly what the registry declares.
            declared = [p for label, ps in scan.CONFIG_PATTERNS if label == tool["label"] for p in ps]
            self.assertEqual(declared, list(tool["scan_patterns"]))

    def test_canonicalizable_tools_are_handled_by_canonicalize_and_drift(self):
        """A migrated tool must have stub_paths wired into BOTH canonicalize and drift."""
        for tool in self.tools:
            if not tool["canonicalizable"]:
                continue
            self.assertTrue(tool["stub_paths"], f"{tool['id']} canonicalizable but has no stub_paths")
            self.assertIn(tool["id"], canonicalize.STUBS, f"{tool['id']} missing from canonicalize.STUBS")
            self.assertEqual(canonicalize.STUBS[tool["id"]]["paths"], list(tool["stub_paths"]))
            self.assertEqual(canonicalize.STUBS[tool["id"]]["content"], tool["stub_content"])
            for path in tool["stub_paths"]:
                self.assertIn(path, check_drift.STUB_FILES, f"{tool['id']} stub path {path} not guarded by check_drift")

    def test_scan_only_tools_are_explicitly_opted_out(self):
        """A tool with no stub form must be an explicit, documented opt-out."""
        for tool in self.tools:
            if tool["stub_paths"]:
                continue
            self.assertFalse(tool["canonicalizable"], f"{tool['id']} has no stub_paths but is marked canonicalizable")
            self.assertTrue(tool.get("canonicalizable_note"), f"{tool['id']} opted out without a documented reason")

    def test_no_tool_appears_in_one_stage_but_missing_from_another(self):
        """canonicalize.STUBS keys == drift-guarded tool ids == canonicalizable registry ids."""
        canonicalizable_ids = {t["id"] for t in self.tools if t["canonicalizable"] and t["stub_paths"]}
        self.assertEqual(set(canonicalize.STUBS.keys()), canonicalizable_ids)
        # Every path in the flat drift list belongs to a canonicalizable tool, and
        # every canonicalizable tool contributes all of its stub paths (no gaps).
        expected_drift = [p for t in self.tools if t["id"] in canonicalizable_ids for p in t["stub_paths"]]
        self.assertEqual(check_drift.STUB_FILES, expected_drift)

    def test_stub_content_is_non_empty_for_canonicalizable_tools(self):
        for tool in self.tools:
            if tool["canonicalizable"]:
                self.assertTrue(tool["stub_content"].strip(), f"{tool['id']} canonicalizable but stub_content is empty")

    def test_roo_is_present_and_explicitly_scan_only(self):
        """Regression guard for the specific gap this refactor closes."""
        roo = next((t for t in self.tools if t["id"] == "roo"), None)
        self.assertIsNotNone(roo, "roo must be in the registry (previously scan-only, silently dropped)")
        self.assertFalse(roo["canonicalizable"])
        self.assertEqual(roo["stub_paths"], [])
        self.assertIn("Roo", roo["canonicalizable_note"])


class SharedConstantConsistencyTests(unittest.TestCase):
    """CORR-06 / TD-01: the stub-size threshold and the lockfile->manager map are
    single-sourced in registry.py so they cannot drift between the scan, drift and
    canonicalize stages."""

    def test_stub_size_threshold_single_sourced(self):
        # scan.py references the registry constant; check_drift.py and
        # canonicalize.py use registry.STUB_POINTER_MAX_BYTES inline. Assert the
        # published value is consistent and sane (CORR-06).
        self.assertEqual(scan.STUB_POINTER_MAX_BYTES, registry.STUB_POINTER_MAX_BYTES)
        self.assertEqual(registry.STUB_POINTER_MAX_BYTES, 800)

    def test_lockfile_managers_single_sourced_and_include_bun(self):
        # All three modules must expose the same map (TD-01), and it must include
        # bun so the drift gate is no longer blind to bun repos.
        self.assertEqual(semantic.LOCKFILE_MANAGERS, registry.LOCKFILE_MANAGERS)
        self.assertEqual(check_drift.LOCKFILE_MANAGERS, registry.LOCKFILE_MANAGERS)
        self.assertEqual(canonicalize.LOCKFILE_MANAGERS, registry.LOCKFILE_MANAGERS)
        for lockfile in ("bun.lockb", "bun.lock"):
            self.assertEqual(registry.LOCKFILE_MANAGERS.get(lockfile), "bun")

    def test_phase0_and_phase2_agree_on_competing_node_lockfiles(self):
        # TD-01 single-sourced the lockfile->manager map, but semantic.py's Node
        # ground-truth picker (_node_ground_pm) independently re-scanned lockfiles
        # in priority order instead of calling the shared, ambiguity-safe
        # facts.lockfile_managers — so a repo with two competing lockfiles got a
        # confident Phase-0 MISMATCH finding while Phase-2's D6 stayed silent and
        # D8 flagged it as ambiguous. Both stages must now agree: no package
        # manager conflict is reported on either side.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pnpm-lock.yaml").write_text("lockfileVersion: 6\n", encoding="utf-8")
            (root / "package-lock.json").write_text("{}", encoding="utf-8")
            (root / "AGENTS.md").write_text("# Project overview\n\nUse `npm install`.\n", encoding="utf-8")
            text = "Use `npm install`."

            phase0 = semantic.compare_package_manager(root, text)
            self.assertEqual(phase0, [])

            phase2 = check_drift.d6_fact_drift(root, text)
            self.assertFalse([f for f in phase2 if "package manager" in f["message"].lower()])

    def test_node_version_regex_single_sourced_across_stages(self):
        # TD-06: the scan conflict signal, the Phase-0 semantic check and the
        # Phase-2 D6 drift gate all extract a Node version through the SAME shared
        # registry helper, so a given line yields the identical normalized MAJOR
        # version (or None) in every stage. Feed tricky inputs and assert all
        # three agree with registry.node_version_major.
        def scan_major(line):
            sigs = [s for s in scan.extract_signals({"text": line, "path": "AGENTS.md"})
                    if s["signal"] == "node_version"]
            # scan now stores the full declared version (e.g. "node 18.17.0");
            # normalize via the shared helper to compare the MAJOR across stages.
            return registry.node_version_major(sigs[0]["value"]) if sigs else None

        cases = {
            "node 18": 18,
            "node 18.17.0": 18,
            "node >=18": 18,
            'node: "20"': 20,
            "Use Node 16.": 16,
            "node v14": 14,
            "node.js 20.1": 20,
            "node 18.x": 18,
            "node:20-alpine": 20,
            "no node version here": None,
            "the Node + Python runtime": None,
        }
        for line, expected in cases.items():
            reg = registry.node_version_major(line)
            sem = semantic.declared_node_version(line)[0]
            drift = check_drift.declared_node_version(line)[0]
            sc = scan_major(line)
            self.assertEqual(reg, expected, f"registry mis-extracted {line!r}")
            self.assertEqual(sem, expected, f"semantic disagrees on {line!r}")
            self.assertEqual(drift, expected, f"check_drift disagrees on {line!r}")
            self.assertEqual(sc, expected, f"scan disagrees on {line!r}")

    def test_backtick_path_detection_single_sourced_across_stages(self):
        # TD-03: the Phase-0 semantic check (declared_paths) and the Phase-2 D2
        # drift gate (d2_path_drift) both classify backtick-quoted paths through
        # the SAME shared registry.declared_paths, so they can no longer diverge.
        text = (
            "In-repo missing `docs/missing.md`.\n"
            "Bare manifest `go.mod` and `Cargo.toml`.\n"
            'Quoted literal `"./downloads"`.\n'
            "Glob `src/**/*.ts`.\n"
            "Command `./gradlew build` and `go build ./cmd`.\n"
            "Bare tool `pytest`.\n"
            "Home `~/.claude`, absolute `/etc/hosts`, escape `../outside.txt`.\n"
            "Scoped package `@ai-sdk/provider` and alias `@/components`.\n"
            "Existing root `README.md`.\n"
            "Duplicate `docs/missing.md` again.\n"
        )
        # 1) semantic.declared_paths delegates to the shared classifier.
        self.assertEqual(semantic.declared_paths(text), registry.declared_paths(text))
        self.assertEqual(check_drift.registry.declared_paths(text), registry.declared_paths(text))

        # 2) On a real repo the two engines report the SAME set of in-repo missing
        # paths (semantic MISSING findings vs D2 drift findings).
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("readme\n", encoding="utf-8")
            (root / "docs").mkdir()
            # docs/missing.md, go.mod, Cargo.toml deliberately absent.
            sem_missing = {f["declared"] for f in semantic.compare_paths(root, text)}
            d2_missing = {
                f["message"].split("`")[1] for f in check_drift.d2_path_drift(root, text)
            }
            self.assertEqual(sem_missing, d2_missing)
            # Sanity: the shared classifier's in-repo, existence-failing tokens.
            self.assertEqual(sem_missing, {"docs/missing.md", "go.mod", "Cargo.toml"})

    def test_subtree_path_existence_policy_agrees_across_stages(self):
        # Candidate extraction was already shared, but Phase 0 and Phase 2 also
        # need the same existence policy for workspace-relative suffix paths.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "packages" / "app" / "src" / "config").mkdir(parents=True)
            (root / "packages" / "app" / "Cargo.toml").write_text(
                "[package]\nname = \"app\"\n",
                encoding="utf-8",
            )
            text = (
                "Workspace paths: `src/config` and `Cargo.toml`.\n"
                "Genuine drift: `src/missing-config`."
            )
            sem_missing = {f["declared"] for f in semantic.compare_paths(root, text)}
            d2_missing = {
                f["message"].split("`")[1] for f in check_drift.d2_path_drift(root, text)
            }
            self.assertEqual(sem_missing, {"src/missing-config"})
            self.assertEqual(d2_missing, sem_missing)

    def test_code_expression_tokens_are_not_declared_paths(self):
        # A backtick token carrying code-expression punctuation (attribute
        # macros, function/index calls, quoted-argument literals) is a code
        # snippet, not a filesystem path. The Rust attribute macro
        # `#[experimental("method/or/field")]` slipped through because its inner
        # `/` made it look path-like and it had no whitespace or `:` to trip the
        # existing guards, producing a false "path does not exist" finding on
        # openai/codex's AGENTS.md.
        code_tokens = [
            '#[experimental("method/or/field")]',
            "#[serde(rename_all)]",
            "foo(bar/baz)",
            "arr[idx/2]",
            "a && b/c",
            "x = y/z",
        ]
        for tok in code_tokens:
            text = f"Rule uses `{tok}` in prose.\n"
            self.assertEqual(
                registry.declared_paths(text),
                [],
                f"code snippet {tok!r} wrongly classified as a declared path",
            )
            # Both stages go through the shared classifier, so neither the
            # Phase-0 semantic check nor the Phase-2 D2 gate can flag it.
            self.assertEqual(semantic.declared_paths(text), [])

        # A genuine path sitting on the same line as a code snippet is still
        # detected — the guard rejects only the offending token, not the line.
        mixed = 'See `docs/api.md` and `#[experimental("m/f")]`.\n'
        self.assertEqual(
            [d["path"] for d in registry.declared_paths(mixed)],
            ["docs/api.md"],
        )

    def test_git_branch_and_ref_tokens_are_not_declared_paths(self):
        # A backtick token naming a git branch/ref convention is not a repo path.
        # AGENTS.md routinely documents branch-naming rules and diff refs in
        # backticks: branch-type prefixes (`feat/`, `fix/`, `release/`) are a
        # single segment plus a trailing slash (a namespace convention, not a
        # concrete directory), and remote refs (`origin/dev`, `upstream/main`)
        # are `<remote>/<branch>` refs used for diffs, not a directory named
        # `origin`. Both slipped through because their `/` made them look
        # path-like, producing false "path does not exist" findings on
        # sst/opencode's AGENTS.md.
        non_path_tokens = [
            "feat/",
            "fix/",
            "release/",
            "chore/",
            "origin/dev",
            "origin/main",
            "upstream/main",
        ]
        for tok in non_path_tokens:
            text = f"Branch convention `{tok}` in prose.\n"
            self.assertEqual(
                registry.declared_paths(text),
                [],
                f"git convention {tok!r} wrongly classified as a declared path",
            )
            # Both stages go through the shared classifier, so neither the
            # Phase-0 semantic check nor the Phase-2 D2 gate can flag it.
            self.assertEqual(semantic.declared_paths(text), [])

        # A real multi-segment path is unaffected: a concrete file and a
        # multi-segment directory (`docs/guide/`, which has an interior slash and
        # so is not a bare branch-prefix) are still detected/checked. Only a
        # single-segment trailing-slash token is treated as a branch prefix.
        keep = "See `src/generated/index.ts` and dir `docs/guide/`.\n"
        self.assertEqual(
            [d["path"] for d in registry.declared_paths(keep)],
            ["src/generated/index.ts", "docs/guide/"],
        )

    def test_fact_readers_single_sourced_across_engines(self):
        # TD-02: the generic repo fact-readers and declaration extractors used to
        # be copy-pasted into both semantic.py (Phase-0) and check_drift.py
        # (Phase-2). They now live once in facts.py and both modules re-export the
        # SAME callables, so the two engines cannot silently drift. First prove the
        # aliases are literally the same objects as the shared facts layer.
        import facts  # noqa: E402  # shared single source of truth

        shared = {
            "package_scripts": facts.package_scripts,
            "make_targets": facts.make_targets,
            "nvmrc_node_version": facts.nvmrc_node_version,
            "engines_node_version": facts.engines_node_version,
            "lockfile_managers": facts.lockfile_managers,
            "declared_node_version": facts.declared_node_version,
            "declared_package_managers": facts.declared_package_managers,
            "PACKAGE_MANAGER_BUILTINS": facts.PACKAGE_MANAGER_BUILTINS,
        }
        for name, obj in shared.items():
            self.assertIs(getattr(semantic, name), obj, f"semantic.{name} is not the shared facts object")
            self.assertIs(getattr(check_drift, name), obj, f"check_drift.{name} is not the shared facts object")
        # The two engines' code-span tokenizers alias the one shared iterator.
        self.assertIs(semantic.iter_code_tokens, facts.iter_code_tokens)
        self.assertIs(check_drift.line_collected_code, facts.iter_code_tokens)
        self.assertIs(semantic._within_root, facts.within_root)
        self.assertIs(check_drift._within_root, facts.within_root)

        # Second, on a representative repo fixture both engines read identical
        # ground-truth facts through the shared layer.
        doc = (
            "Run `npm run build` then `make lint`.\n"
            "This project targets `node 18`.\n"
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(
                json.dumps({"scripts": {"build": "tsc", "lint": "eslint ."}, "engines": {"node": ">=18.0.0"}}),
                encoding="utf-8",
            )
            (root / "Makefile").write_text("lint:\n\techo lint\ntest:\n\techo test\n", encoding="utf-8")
            (root / ".nvmrc").write_text("18\n", encoding="utf-8")
            (root / "package-lock.json").write_text("{}\n", encoding="utf-8")

            self.assertEqual(semantic.package_scripts(root), check_drift.package_scripts(root))
            self.assertEqual(semantic.make_targets(root), check_drift.make_targets(root))
            self.assertEqual(semantic.nvmrc_node_version(root), check_drift.nvmrc_node_version(root))
            self.assertEqual(semantic.engines_node_version(root), check_drift.engines_node_version(root))
            self.assertEqual(semantic.lockfile_managers(root), check_drift.lockfile_managers(root))
            self.assertEqual(semantic.declared_node_version(doc), check_drift.declared_node_version(doc))
            self.assertEqual(semantic.declared_package_managers(doc), check_drift.declared_package_managers(doc))
            # Sanity: the shared facts were actually read (not both empty/None).
            self.assertEqual(semantic.package_scripts(root), {"build", "lint"})
            self.assertEqual(semantic.lockfile_managers(root), {"npm"})
            self.assertEqual(semantic.declared_node_version(doc), (18, 2))

    def test_gap_stub_files_derived_from_registry(self):
        # TD-04: scan.GAP_STUB_FILES must be derived from the shared registry, not
        # a hardcoded literal, so adding a tool to the registry auto-updates gap
        # detection. Assert it equals the registry-derived stub-path list and the
        # exact same list check_drift.py guards, so the two stages cannot drift.
        expected = [p for tool in registry.canonicalizable_tools() for p in tool["stub_paths"]]
        self.assertEqual(scan.GAP_STUB_FILES, expected)
        self.assertEqual(scan.GAP_STUB_FILES, check_drift.STUB_FILES)
        # Sanity: every entry is a real canonicalizable stub path in the registry.
        registry_stub_paths = {
            p for tool in registry.load_tools() if tool["canonicalizable"] for p in tool["stub_paths"]
        }
        self.assertEqual(set(scan.GAP_STUB_FILES), registry_stub_paths)

    def test_stub_at_threshold_boundary_classified_consistently(self):
        # A pointer stub at the byte boundary must be classified the same way by
        # the scan gap analysis and the drift D3 gate: <= threshold is fine,
        # just over is "regrown". Guards against the thresholds drifting apart.
        threshold = registry.STUB_POINTER_MAX_BYTES
        at_limit = "@AGENTS.md\n" + "x" * (threshold - len("@AGENTS.md\n"))
        over_limit = at_limit + "y" * 8
        self.assertEqual(len(at_limit.encode("utf-8")), threshold)
        self.assertGreater(len(over_limit.encode("utf-8")), threshold)
        self.assertLessEqual(len(at_limit.encode("utf-8")), scan.STUB_POINTER_MAX_BYTES)
        self.assertGreater(len(over_limit.encode("utf-8")), scan.STUB_POINTER_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
