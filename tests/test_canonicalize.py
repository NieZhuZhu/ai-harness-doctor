import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from tmp_support import ResilientTemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
CANON = ROOT / "scripts" / "canonicalize.py"

sys.path.insert(0, str(ROOT / "scripts"))
import canonicalize  # noqa: E402

AGENTS_MIN = """# Project overview
Fixture repo.

# Build & test
Run `npm run test`.

# Conventions
Keep changes small.
"""


def _can_symlink_files():
    with ResilientTemporaryDirectory() as td:
        target = Path(td) / "target"
        target.write_text("target\n", encoding="utf-8")
        link = Path(td) / "link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        return link.is_symlink()


class CanonicalizeTests(unittest.TestCase):
    def test_plan_contains_inventory_and_conflict(self):
        proc = subprocess.run([sys.executable, str(CANON), "--plan", str(FIXTURE)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Inventory", proc.stdout)
        self.assertIn("Conflict list", proc.stdout)
        self.assertIn("package_manager", proc.stdout)

    def test_plan_contains_merge_suggestions_section(self):
        proc = subprocess.run([sys.executable, str(CANON), "--plan", str(FIXTURE)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        # New semi-automatic merge-suggestion section is appended.
        self.assertIn("## Merge suggestions (semi-automatic)", out)
        # Existing skeleton sections are still intact.
        self.assertIn("## TODO decision checklist", out)
        # Overlap consolidation names AGENTS.md as canonical and lists the drifted files.
        self.assertIn("### Overlap consolidation", out)
        self.assertIn("reduce `CLAUDE.md` to an import stub", out)
        # Concrete conflict recommendation with evidence for the messy-repo fixture.
        self.assertIn("### Conflict resolutions", out)
        self.assertIn("**package_manager** → recommend `npm`", out)
        self.assertIn("`.cursorrules:4`", out)

    def test_plan_preserves_nested_scope_overrides(self):
        report = {
            "files": [
                {"path": "AGENTS.md", "tool": "AGENTS.md", "bytes": 10, "lines": 1},
                {
                    "path": "packages/api/AGENTS.md",
                    "tool": "AGENTS.md",
                    "bytes": 10,
                    "lines": 1,
                },
            ],
            "overlaps": [
                {
                    "a": "AGENTS.md",
                    "b": "packages/api/AGENTS.md",
                    "percent": 80.0,
                }
            ],
            "conflicts": [],
            "instruction_scopes": [
                {"path": "AGENTS.md", "scope": ".", "parent": None},
                {
                    "path": "packages/api/AGENTS.md",
                    "scope": "packages/api",
                    "parent": ".",
                },
            ],
            "scope_overrides": [
                {
                    "signal": "package_manager",
                    "parent_scope": ".",
                    "scope": "packages/api",
                    "parent_values": ["npm"],
                    "values": ["pnpm"],
                    "evidence": [],
                }
            ],
        }
        output = canonicalize.render_plan(report)
        self.assertIn("## Declared scope overrides (preserve; non-blocking)", output)
        self.assertIn("Preserve `packages/api` as a nested canonical scope", output)
        self.assertIn("do not collapse it into a root stub", output)
        self.assertIn("preserve nested canonical `packages/api/AGENTS.md`", output)
        self.assertNotIn(
            "reduce `packages/api/AGENTS.md` to an import stub",
            output,
        )

    def test_plan_labels_true_nested_conflict_scope(self):
        report = {
            "files": [],
            "overlaps": [],
            "instruction_scopes": [],
            "scope_overrides": [],
            "conflicts": [
                {
                    "signal": "package_manager",
                    "scope": "packages/api",
                    "values": {
                        "pnpm": [
                            {
                                "path": "packages/api/AGENTS.md",
                                "line": 2,
                                "evidence": "Use pnpm.",
                            }
                        ],
                        "yarn": [
                            {
                                "path": "packages/api/CLAUDE.md",
                                "line": 3,
                                "evidence": "Use yarn.",
                            }
                        ],
                    },
                }
            ],
        }
        output = canonicalize.render_plan(report)
        self.assertIn("**package_manager** (scope `packages/api`)", output)

    def test_write_stubs_dry_run_prints_diff_and_writes_nothing(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / ".cursor" / "rules").mkdir(parents=True)
            (repo / ".cursor" / "rules" / "extra.mdc").write_text("old cursor rule\n", encoding="utf-8")
            before = (repo / "CLAUDE.md").read_text(encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo)], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--- a/CLAUDE.md", proc.stdout)
            self.assertIn("delete .cursor/rules/extra.mdc", proc.stdout)
            self.assertEqual(before, (repo / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertTrue((repo / ".cursor" / "rules" / "extra.mdc").is_file())

    def test_write_stubs_apply_rewrites_claude(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / ".cursor" / "rules").mkdir(parents=True)
            (repo / ".cursor" / "rules" / "extra.mdc").write_text("old cursor rule\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((repo / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md"))
            self.assertFalse((repo / ".cursor" / "rules" / "extra.mdc").exists())
            self.assertTrue((repo / ".cursor" / "rules" / "agents-md.mdc").is_file())

    def test_recursive_scan_discovery_does_not_authorize_nested_rule_deletion(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            rules = repo / ".cursor" / "rules"
            nested = rules / "team" / "python.mdc"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                '---\nglobs: "**/*.py"\nalwaysApply: false\n---\nUse uv.\n',
                encoding="utf-8",
            )
            top = rules / "legacy.mdc"
            top.write_text("top-level legacy rule\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            nested_before = nested.read_bytes()

            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(nested.read_bytes(), nested_before)
            self.assertFalse(top.exists())
            self.assertTrue((rules / "agents-md.mdc").is_file())

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_write_stubs_apply_refuses_external_file_symlink(self):
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            outside = base / "outside-claude.md"
            outside.write_text("outside instructions\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / "CLAUDE.md").symlink_to(outside)
            regular_stub = repo / ".cursorrules"
            regular_stub.write_text("regular cursor instructions\n", encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            before = outside.read_bytes()
            regular_before = regular_stub.read_bytes()

            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("unsafe", (proc.stdout + proc.stderr).lower())
            self.assertEqual(outside.read_bytes(), before)
            self.assertEqual(regular_stub.read_bytes(), regular_before)
            self.assertTrue((repo / "CLAUDE.md").is_symlink())

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_write_stubs_apply_refuses_symlinked_cursor_rules_directory(self):
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            outside_rules = base / "outside-rules"
            (repo / ".cursor").mkdir(parents=True)
            outside_rules.mkdir()
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            outside_rule = outside_rules / "external.mdc"
            outside_rule.write_text("external cursor rule\n", encoding="utf-8")
            try:
                (repo / ".cursor" / "rules").symlink_to(outside_rules, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            before = outside_rule.read_bytes()

            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("unsafe", (proc.stdout + proc.stderr).lower())
            self.assertEqual(outside_rule.read_bytes(), before)
            self.assertFalse((outside_rules / "agents-md.mdc").exists())

    def test_write_stubs_default_tools_covers_every_canonicalizable_registry_tool(self):
        # Regression: --tools' default used to be a hand-maintained string
        # ("claude,cursor,windsurf,copilot,gemini,cline") instead of being
        # derived from the registry, so a newly-added canonicalizable tool
        # (e.g. continue, added alongside this test) silently fell through
        # write_stubs's default run even though STUBS itself (used by --apply)
        # already covered it — a two-tier drift within this single script.
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / ".continuerules").write_text("old continue rule, not yet a stub\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--write-stubs", str(repo)], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--- a/.continuerules", proc.stdout)

    def test_validate_default_tools_covers_every_canonicalizable_registry_tool(self):
        # Same regression as above, for validate()'s independently
        # hand-maintained tool list (a second, separate hardcoded copy).
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / ".continuerules").write_text("old continue rule, not yet a stub\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True
            )
            report = json.loads(proc.stdout)
            stub_findings = [f for f in report["findings"] if f["check"] == "STUB" and f["path"] == ".continuerules"]
            self.assertEqual(len(stub_findings), 1)

    def test_validate_missing_and_present(self):
        proc = subprocess.run([sys.executable, str(CANON), "--validate", str(FIXTURE)], text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--validate", str(repo)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_validate_stub_notice_does_not_fail(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / "CLAUDE.md").write_text("not a stub\n" * 100, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["ok"])
            notices = [f for f in report["findings"] if f["level"] == "NOTICE"]
            self.assertTrue(any("CLAUDE.md" == f.get("path") for f in notices))

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_validate_reports_external_agents_and_stub_symlinks_as_unsafe(self):
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            outside_agents = base / "outside-agents.md"
            outside_stub = base / "outside-claude.md"
            outside_agents.write_text(AGENTS_MIN, encoding="utf-8")
            outside_stub.write_text("@AGENTS.md\n", encoding="utf-8")
            (repo / "AGENTS.md").symlink_to(outside_agents)
            (repo / "CLAUDE.md").symlink_to(outside_stub)

            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"],
                text=True,
                capture_output=True,
            )
            report = json.loads(proc.stdout)

            self.assertEqual(proc.returncode, 1)
            unsafe = [f for f in report["findings"] if f["check"] == "UNSAFE_PATH"]
            self.assertEqual({f.get("path") for f in unsafe}, {"AGENTS.md", "CLAUDE.md"})

    def test_validate_missing_required_section_still_fails(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Project overview\nOnly overview.\n", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 1)
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(any(f["check"] == "SECTION" and f["level"] == "ERROR" for f in report["findings"]))

    def test_validate_custom_require_sections_is_honored(self):
        # A custom --require-sections list overrides the defaults: a heading not
        # in the list is not required, and a heading in the list that is missing
        # is flagged as a SECTION error.
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Overview\n# Deployment\nContent.\n", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(CANON),
                    "--validate",
                    str(repo),
                    "--require-sections",
                    "Overview,Rollback plan",
                    "--json",
                ],
                text=True,
                capture_output=True,
            )
            report = json.loads(proc.stdout)
            sections = [f["message"] for f in report["findings"] if f["check"] == "SECTION"]
            # 'Overview' is present → not flagged; 'Rollback plan' is required but
            # missing → flagged; the default 'Build & test' is NOT required here.
            self.assertTrue(any("Rollback plan" in m for m in sections), report["findings"])
            self.assertFalse(any("Overview" in m for m in sections), report["findings"])
            self.assertFalse(any("Build & test" in m for m in sections), report["findings"])

    def test_validate_library_doc_downgrades_section_and_size_errors(self):
        # A large end-user library/reference AGENTS.md (installation + API
        # reference + support sections + import examples) must not be hard-failed
        # for lacking contributor-guide sections or for exceeding the size budget.
        library_doc = (
            "# Quickstart\n\n"
            "Install with `pip install mylib`.\n\n"
            "```python\nfrom mylib import Agent\nagent = Agent()\n```\n\n"
            "# Available Parameters\n\n"
            "- `model`: the LLM to use.\n\n"
            "# Get Help\n\nJoin our community chat.\n\n"
            "# Telemetry\n\nAnonymous usage data is collected; opt out with an env var.\n\n"
            + "Reference paragraph describing the public API in detail.\n"
            * 800
        )
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(library_doc, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["ok"])
            # The size/section findings are still surfaced, but only as
            # non-blocking WARN rather than blocking ERROR.
            self.assertFalse([f for f in report["findings"] if f["level"] == "ERROR"])
            downgraded = [f for f in report["findings"] if f["check"] in ("SIZE", "SECTION")]
            self.assertTrue(downgraded)
            self.assertTrue(all(f["level"] == "WARN" for f in downgraded))

    def test_validate_contributor_doc_not_treated_as_library_doc(self):
        # A conventional contributor guide missing required sections must still
        # hard-fail: the library-doc relaxation must not misclassify it.
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(
                "# Project overview\n\nContributor guide.\n\n# Testing requirements\n\nRun the suite before pushing.\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(any(f["check"] == "SECTION" and f["level"] == "ERROR" for f in report["findings"]))


REQUIRED_DRAFT_HEADINGS = [
    "# Project overview",
    "# Build & test",
    "# Conventions",
    "# Testing requirements",
    "# Safety",
    "# Commit & PR",
]


class DraftTests(unittest.TestCase):
    def test_draft_fills_all_canonical_sections_with_marked_inferences(self):
        proc = subprocess.run([sys.executable, str(CANON), str(FIXTURE), "--draft"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        # Every canonical AGENTS.md section from assets/AGENTS.template.md is present.
        for heading in REQUIRED_DRAFT_HEADINGS:
            self.assertIn(heading, out)
        # Draft banner tells the human this is a mechanical draft to review.
        self.assertIn("Auto-drafted by", out)
        # Inferred lines are clearly marked as suggestions to confirm.
        self.assertIn("(inferred — confirm)", out)
        # Fact-derived build commands come from the fixture's package.json scripts.
        self.assertIn("npm install", out)
        self.assertIn("npm run test", out)
        self.assertIn("npm run build", out)
        # Detected tech stack surfaced from the manifest.
        self.assertIn("Node.js (`package.json`)", out)
        # A safe default convention is offered too.
        self.assertIn("(suggested default)", out)

    def test_draft_suggests_conflict_defaults_backed_by_lockfile(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "package.json").write_text('{"name":"x","scripts":{"test":"node t.js"}}\n', encoding="utf-8")
            # A committed pnpm lockfile is stronger evidence than instruction text.
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
            (repo / "CLAUDE.md").write_text(
                "# Claude\nUse npm install before development.\nRun npm test.\n", encoding="utf-8"
            )
            (repo / ".cursorrules").write_text(
                "# Cursor\nUse pnpm install before development.\nRun pnpm test.\n", encoding="utf-8"
            )
            proc = subprocess.run([sys.executable, str(CANON), str(repo), "--draft"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertIn("suggested defaults", out)
            # The lockfile-backed manager wins the package_manager conflict.
            self.assertIn("`package_manager` → `pnpm`", out)
            # And the draft's build commands use pnpm accordingly.
            self.assertIn("pnpm install", out)

    def test_draft_abstains_from_commands_when_lockfile_managers_compete(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                '{"scripts":{"test":"vitest run"}}\n',
                encoding="utf-8",
            )
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")

            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn("pnpm install", proc.stdout)
            self.assertNotIn("npm install", proc.stdout)
            self.assertNotIn("pnpm run test", proc.stdout)
            self.assertNotIn("npm run test", proc.stdout)

    def test_draft_o_writes_file_and_refuses_to_overwrite(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            out_path = Path(td) / "AGENTS.draft.md"
            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out_path.is_file())
            self.assertIn("# Project overview", out_path.read_text(encoding="utf-8"))
            # Second run must refuse to clobber an existing file without --force.
            proc2 = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path)],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc2.returncode, 0)
            self.assertIn("Refusing to overwrite", proc2.stderr)
            # --force allows overwrite.
            proc3 = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path), "--force"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc3.returncode, 0, proc3.stderr)

    def test_draft_infers_python_commands_for_pyproject_repo(self):
        # A Python repo (pyproject + uv + a console script + a pytest setup) must
        # yield real inferred build/test commands, not the "could not be inferred"
        # TODO that only Node/Make repos used to avoid.
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "pyproject.toml").write_text(
                "[project]\n"
                'name = "mylib"\n'
                'requires-python = ">=3.11"\n\n'
                "[project.scripts]\n"
                'mycli = "mylib.cli:main"\n\n'
                "[tool.uv]\n"
                'dev-dependencies = ["pytest", "ruff"]\n',
                encoding="utf-8",
            )
            (repo / "tests").mkdir()
            (repo / "tests" / "test_basic.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), str(repo), "--draft"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertNotIn("no build/test commands could be inferred", out)
            # uv detected from [tool.uv]; install + common runners inferred.
            self.assertIn("uv sync", out)
            self.assertIn("uv run pytest", out)
            self.assertIn("uv run ruff check", out)
            # Console script from pyproject surfaced (as an entry-point note).
            self.assertIn("`mycli`", out)
            # Every drafted command stays tagged for human confirmation.
            self.assertIn("(inferred — confirm)", out)

    def test_draft_reuses_python_commands_documented_in_claude_md(self):
        # When a CLAUDE.md already documents build/test/lint commands, --draft
        # reuses them verbatim instead of guessing.
        with ResilientTemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "mylib"\n\n[tool.poetry]\nname = "mylib"\n',
                encoding="utf-8",
            )
            (repo / "CLAUDE.md").write_text(
                "# CLAUDE.md\n\n- Run tests: `poetry run pytest -q`\n- Lint: `poetry run ruff check`\n",
                encoding="utf-8",
            )
            proc = subprocess.run([sys.executable, str(CANON), str(repo), "--draft"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout
            self.assertIn("poetry install", out)
            self.assertIn("poetry run pytest -q", out)
            self.assertIn("poetry run ruff check", out)
            self.assertIn("documented in CLAUDE.md", out)

    def test_draft_ignores_external_fact_symlinks(self):
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            outside = base / "outside"
            repo.mkdir()
            outside.mkdir()
            sentinel = "external-only-command"
            (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
            (outside / "CLAUDE.md").write_text(
                f"```bash\nuv run pytest {sentinel}\n```\n",
                encoding="utf-8",
            )
            try:
                (repo / "CLAUDE.md").symlink_to(outside / "CLAUDE.md")
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")

            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(sentinel, proc.stdout + proc.stderr)

    def test_draft_ignores_external_node_python_and_tool_facts(self):
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            outside = base / "outside"
            repo.mkdir()
            outside.mkdir()
            sentinel = "outside-test-script"
            sources = {
                "package.json": json.dumps({"scripts": {"test": sentinel}}),
                "pnpm-lock.yaml": "lockfileVersion: 9\n",
                "pyproject.toml": "[tool.uv]\n[tool.pytest.ini_options]\n[tool.ruff]\n",
                "ruff.toml": "line-length = 99\n",
                "Makefile": "outside-target:\n\t@true\n",
            }
            for name, content in sources.items():
                (outside / name).write_text(content, encoding="utf-8")
                try:
                    (repo / name).symlink_to(outside / name)
                except (OSError, NotImplementedError):
                    self.skipTest("file symlinks unsupported")

            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotIn(sentinel, proc.stdout + proc.stderr)
            self.assertNotIn("pnpm install", proc.stdout)
            self.assertNotIn("uv sync", proc.stdout)
            self.assertNotIn("uv run pytest", proc.stdout)
            self.assertNotIn("uv run ruff", proc.stdout)
            self.assertNotIn("make outside-target", proc.stdout)

    def test_draft_supports_contained_claude_symlink(self):
        with ResilientTemporaryDirectory() as td:
            repo = Path(td)
            shared = repo / "shared"
            shared.mkdir()
            (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
            (shared / "CLAUDE.md").write_text(
                "```bash\nuv run pytest contained-only\n```\n",
                encoding="utf-8",
            )
            try:
                (repo / "CLAUDE.md").symlink_to(shared / "CLAUDE.md")
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")

            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("uv run pytest contained-only", proc.stdout)


class ConflictDefaultTests(unittest.TestCase):
    def test_lockfile_backs_package_manager_recommendation(self):
        with ResilientTemporaryDirectory() as td:
            root = Path(td)
            (root / "yarn.lock").write_text("# yarn lockfile\n", encoding="utf-8")
            values = {
                "npm": [{"path": "CLAUDE.md", "line": 3}],
                "yarn": [{"path": ".cursorrules", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("package_manager", values, root)
            self.assertEqual(value, "yarn")
            self.assertIn("yarn.lock", rationale)

    def test_falls_back_to_vote_when_no_lockfile(self):
        with ResilientTemporaryDirectory() as td:
            root = Path(td)
            values = {
                "npm": [{"path": ".cursorrules", "line": 3}],
                "pnpm": [{"path": "CLAUDE.md", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("package_manager", values, root)
            # Tie broken lexicographically -> npm.
            self.assertEqual(value, "npm")
            self.assertIn("configuration files agree", rationale)

    def test_node_version_recommendation_matches_nvmrc(self):
        with ResilientTemporaryDirectory() as td:
            root = Path(td)
            (root / ".nvmrc").write_text("20\n", encoding="utf-8")
            values = {
                "node 18": [{"path": "CLAUDE.md", "line": 3}],
                "node 20": [{"path": ".cursorrules", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("node_version", values, root)
            self.assertEqual(value, "node 20")
            self.assertIn(".nvmrc", rationale)

    def test_node_version_recommendation_matches_nvmrc_against_dotted_versions(self):
        # `values` is keyed by the full declared string scan.py preserves (e.g.
        # "node 18.2.0"), not the bare major .nvmrc/engines.node resolve to.
        # Comparing by exact string equality never matches a dotted conflict
        # value, silently falling through to the vote-count tiebreak and
        # recommending a version that contradicts the repo's own .nvmrc.
        with ResilientTemporaryDirectory() as td:
            root = Path(td)
            (root / ".nvmrc").write_text("20\n", encoding="utf-8")
            values = {
                "node 18.2.0": [{"path": "CLAUDE.md", "line": 3}, {"path": "README.md", "line": 1}],
                "node 20.1.0": [{"path": ".cursorrules", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("node_version", values, root)
            self.assertEqual(value, "node 20.1.0")
            self.assertIn(".nvmrc", rationale)

    def test_node_version_recommendation_falls_back_when_nvmrc_matches_no_candidate(self):
        with ResilientTemporaryDirectory() as td:
            root = Path(td)
            (root / ".nvmrc").write_text("22\n", encoding="utf-8")
            values = {
                "node 18.2.0": [{"path": "CLAUDE.md", "line": 3}, {"path": "README.md", "line": 1}],
                "node 20.1.0": [{"path": ".cursorrules", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("node_version", values, root)
            self.assertEqual(value, "node 18.2.0")
            self.assertIn("configuration files agree", rationale)


if __name__ == "__main__":
    unittest.main()
