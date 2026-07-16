import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
DRIFT = ROOT / "scripts" / "check_drift.py"

sys.path.insert(0, str(ROOT / "scripts"))
import check_drift  # noqa: E402
import facts  # noqa: E402


def _can_symlink_dirs():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "target"
        target.mkdir()
        link = Path(td) / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
        return link.is_symlink()


def _can_symlink_files():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "target"
        target.write_text("target\n", encoding="utf-8")
        link = Path(td) / "link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        return link.is_symlink()


CLEAN_AGENTS = """# Project overview
Fixture repo.

# Build & test
Run `npm run test`.

# Conventions
Keep changes small.
"""


class DriftTests(unittest.TestCase):
    def copy_repo(self):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name) / "repo"
        shutil.copytree(FIXTURE, repo)
        return td, repo

    def test_nested_agents_content_checks_use_package_scope_and_attribution(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps({"scripts": {"test": "echo root"}}),
                encoding="utf-8",
            )
            (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")

            api = repo / "packages" / "api"
            (api / "src").mkdir(parents=True)
            (api / "docs").mkdir()
            (api / "src" / "handler.py").write_text("pass\n", encoding="utf-8")
            (api / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            (api / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"test:api": "echo api"},
                        "engines": {"node": ">=20"},
                    }
                ),
                encoding="utf-8",
            )
            (api / ".nvmrc").write_text("20\n", encoding="utf-8")
            (api / "AGENTS.md").write_text(
                "# API package\n\n"
                "Use Node 18 in this package.\n"
                "Run `npm run test:api` and `npm run removed-script`.\n"
                "The handler lives at `src/handler.py`.\n"
                "The missing migration should be at `src/missing-handler.py`.\n"
                "See the [guide](docs/guide.md) and [missing guide](docs/missing.md).\n",
                encoding="utf-8",
            )

            web = repo / "packages" / "web"
            web.mkdir(parents=True)
            (web / "package.json").write_text(
                json.dumps({"scripts": {"test:web": "echo web"}}),
                encoding="utf-8",
            )
            (web / "AGENTS.md").write_text(
                "# Web package\n\nRun `npm run test:web`.\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--strict", "--json"],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            nested = [
                finding
                for finding in report["findings"]
                if finding.get("path") == "packages/api/AGENTS.md"
            ]
            self.assertEqual({finding["check"] for finding in nested}, {"D1", "D2", "D6", "D7"})
            self.assertTrue(all(finding.get("line", 0) > 0 for finding in nested))
            messages = " ".join(finding["message"] for finding in nested)
            self.assertIn("removed-script", messages)
            self.assertIn("src/missing-handler.py", messages)
            self.assertIn("Node 18", messages)
            self.assertIn("docs/missing.md", messages)
            self.assertNotIn("test:api`", messages)
            self.assertNotIn("src/handler.py`", messages)
            self.assertNotIn("docs/guide.md", messages)
            self.assertFalse(
                [
                    finding
                    for finding in report["findings"]
                    if finding.get("path") == "packages/web/AGENTS.md"
                ]
            )
            self.assertLess(report["score"], 100)
            self.assertNotEqual(report["grade"], "A")

            markdown = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--strict"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(markdown.returncode, 1)
            self.assertIn("`packages/api/AGENTS.md:4`", markdown.stdout)
            self.assertIn("`packages/api/AGENTS.md:6`", markdown.stdout)

            fix = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--fix"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(fix.returncode, 1)
            self.assertIn("needs manual attention", fix.stdout)
            self.assertIn("`packages/api/AGENTS.md:4`", fix.stdout)

    def test_nested_scope_accepts_explicit_root_commands_and_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps({"scripts": {"build:cli": "echo root"}}),
                encoding="utf-8",
            )
            (repo / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
            root_test = repo / "packages" / "core" / "src" / "server.test.ts"
            root_test.parent.mkdir(parents=True)
            root_test.write_text("test\n", encoding="utf-8")
            package = repo / "examples" / "app"
            package.mkdir(parents=True)
            (package / "package.json").write_text(
                json.dumps({"scripts": {"dev": "echo local"}}),
                encoding="utf-8",
            )
            (package / "AGENTS.md").write_text(
                "Run `pnpm build:cli` from the repo root and edit "
                "`packages/core/src/server.test.ts`.\n",
                encoding="utf-8",
            )

            report = check_drift.run_checks(repo, check_drift.DEFAULT_MAX_BYTES)

            self.assertTrue(report["ok"], report["findings"])
            self.assertEqual(report["findings"], [])

    def test_nested_scope_without_local_manifest_still_checks_root_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps({"scripts": {"test": "echo root"}}),
                encoding="utf-8",
            )
            (repo / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
            nested = repo / "docs"
            nested.mkdir()
            (nested / "AGENTS.md").write_text(
                "Run `npm run removed-script`.\n",
                encoding="utf-8",
            )

            report = check_drift.run_checks(repo, check_drift.DEFAULT_MAX_BYTES)

            self.assertFalse(report["ok"])
            self.assertEqual(len(report["findings"]), 1)
            self.assertEqual(report["findings"][0]["check"], "D1")
            self.assertEqual(report["findings"][0]["path"], "docs/AGENTS.md")

    def test_nested_scope_without_local_facts_falls_back_for_d6(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps({"engines": {"node": ">=20"}}),
                encoding="utf-8",
            )
            (repo / ".nvmrc").write_text("20\n", encoding="utf-8")
            (repo / "package-lock.json").write_text(
                '{"lockfileVersion": 3}\n',
                encoding="utf-8",
            )
            (repo / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
            nested = repo / "docs"
            nested.mkdir()
            (nested / "AGENTS.md").write_text(
                "Use Node 18 and run `pnpm install` in this scope.\n",
                encoding="utf-8",
            )

            report = check_drift.run_checks(repo, check_drift.DEFAULT_MAX_BYTES)

            d6 = [finding for finding in report["findings"] if finding["check"] == "D6"]
            self.assertGreaterEqual(len(d6), 2)
            self.assertTrue(all(finding["path"] == "docs/AGENTS.md" for finding in d6))
            messages = " ".join(finding["message"] for finding in d6)
            self.assertIn("Node 18", messages)
            self.assertIn("package-lock.json", messages)

    def test_nested_paths_and_links_may_reach_parent_but_not_escape_repo(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            scope = repo / "packages" / "api"
            scope.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
            (repo / "packages" / "shared.py").write_text("shared\n", encoding="utf-8")
            (repo / "packages" / "guide.md").write_text("# Guide\n", encoding="utf-8")
            outside = base / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            (scope / "AGENTS.md").write_text(
                "Use `../shared.py` and [the guide](../guide.md).\n"
                "Missing `../missing.py` and [missing guide](../missing.md).\n"
                "Ignore external `../../../outside.md` and "
                "[external](../../../outside.md).\n",
                encoding="utf-8",
            )

            report = check_drift.run_checks(repo, check_drift.DEFAULT_MAX_BYTES)

            nested = [
                finding
                for finding in report["findings"]
                if finding.get("path") == "packages/api/AGENTS.md"
            ]
            self.assertEqual({finding["check"] for finding in nested}, {"D2", "D7"})
            messages = " ".join(finding["message"] for finding in nested)
            self.assertIn("../missing.py", messages)
            self.assertIn("../missing.md", messages)
            self.assertNotIn("../shared.py", messages)
            self.assertNotIn("../guide.md", messages)
            self.assertNotIn("outside.md", messages)

    def test_nonexistent_target_errors_instead_of_reporting_healthy(self):
        # A typo'd target path must fail loudly, not silently report a passing
        # health score for nothing scanned (found: `drift /typo-path` previously
        # exited 0 with "Health score: 85/100 (grade B)").
        missing = str(Path(tempfile.gettempdir()) / "ai-harness-doctor-nonexistent-path-xyz")
        proc = subprocess.run([sys.executable, str(DRIFT), missing], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not a directory", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_nonexistent_target_json_mode_reports_error_not_a_fake_report(self):
        missing = str(Path(tempfile.gettempdir()) / "ai-harness-doctor-nonexistent-path-xyz")
        proc = subprocess.run([sys.executable, str(DRIFT), missing, "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertIn("not a directory", payload["error"])
        self.assertNotIn("score", payload)

    def test_subtree_scoped_path_does_not_trigger_d2(self):
        # Root AGENTS.md sections commonly scope instructions to one workspace,
        # then name paths relative to that workspace. Phase 0 already resolves
        # these suffix paths; Phase 2 must apply the same existence policy.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "packages" / "app" / "src" / "config").mkdir(parents=True)
            text = "In the packages/app workspace, edit `src/config`."
            self.assertEqual(check_drift.d2_path_drift(root, text), [])

    def test_fully_missing_path_still_triggers_d2_with_subtrees_present(self):
        # Subtree leniency must not mask genuine drift merely because the repo
        # has nested packages; only an exact trailing-path match is accepted.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "packages" / "app" / "src" / "config").mkdir(parents=True)
            text = "Use `src/missing-config` for runtime settings."
            findings = check_drift.d2_path_drift(root, text)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["check"], "D2")
            self.assertIn("src/missing-config", findings[0]["message"])

    def test_many_missing_paths_build_one_subtree_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(120):
                path = root / "areas" / f"area-{i:03d}" / "keep.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            (root / "workspace" / "src" / "config").mkdir(parents=True)
            (root / "workspace" / "Cargo.toml").write_text("[package]\nname = \"demo\"\n", encoding="utf-8")
            text = "\n".join(
                ["Use `src/config` and `Cargo.toml`."]
                + [f"Missing `not-present-{i}/file.txt`." for i in range(20)]
            )

            calls = {"n": 0}
            real_build = facts.build_subtree_path_index
            real_walk = facts.os.walk
            walk_calls = {"n": 0}

            def counting_build(*args, **kwargs):
                calls["n"] += 1
                return real_build(*args, **kwargs)

            def counting_walk(*args, **kwargs):
                walk_calls["n"] += 1
                return real_walk(*args, **kwargs)

            with mock.patch.object(facts, "build_subtree_path_index", counting_build), mock.patch.object(
                facts.os, "walk", counting_walk
            ):
                findings = check_drift.d2_path_drift(root, text)

            self.assertEqual(calls["n"], 1)
            self.assertEqual(walk_calls["n"], 2)
            self.assertEqual(
                {finding["message"].split("`")[1] for finding in findings},
                {f"not-present-{i}/file.txt" for i in range(20)},
            )

    def test_unknown_script_d1(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS.replace("npm run test", "npm run nonexist"), encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("D1", proc.stdout)
        self.assertIn("nonexist", proc.stdout)

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_external_package_json_symlink_cannot_supply_drift_facts(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(
                "# Project overview\n"
                "# Build & test\n"
                "Use Node.js 20 and run `npm run external-only`.\n"
                "# Conventions\n"
                "Keep changes small.\n",
                encoding="utf-8",
            )
            outside = base / "outside-package.json"
            outside.write_text(
                json.dumps(
                    {
                        "scripts": {"external-only": "echo outside"},
                        "engines": {"node": "99"},
                    }
                ),
                encoding="utf-8",
            )
            (repo / "package.json").symlink_to(outside)

            proc = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--json"],
                text=True,
                capture_output=True,
            )
            report = json.loads(proc.stdout)

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse(
                any("Node 99" in finding["message"] for finding in report["findings"])
            )
            self.assertFalse(
                any(
                    finding["check"] == "D1" and "external-only" in finding["message"]
                    for finding in report["findings"]
                )
            )

    def test_package_manager_builtins_do_not_trigger_d1(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nnpm install\nyarn add foo\nnpm run nonexist\n```\n", encoding="utf-8"
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        self.assertEqual(len(d1), 1)
        self.assertIn("nonexist", d1[0]["message"])

    def test_yarn_workspace_builtin_does_not_trigger_d1(self):
        # `yarn workspace <name> <cmd>` / `yarn workspaces foreach ...` are Yarn
        # subcommands, not package.json scripts (found scanning tldraw/tldraw's
        # AGENTS.md, which documents `yarn workspace examples.tldraw.com dev`).
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nyarn workspace examples dev\nyarn workspaces info\n```\n",
            encoding="utf-8",
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual([f for f in report["findings"] if f["check"] == "D1"], [])

    def test_yarn_bin_passthrough_does_not_trigger_d1(self):
        # Yarn Classic/Berry run a binary straight out of node_modules/.bin when
        # no matching script exists (`yarn vitest`). Found scanning tldraw's
        # AGENTS.md, which documents `yarn vitest` even though the root
        # package.json has no "vitest" script — only a "vitest" devDependency.
        # This previously failed the CI gate (D1 ERROR) on a legitimate command.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "package.json").write_text(
            json.dumps({"scripts": {"test": "node src/index.js"}, "devDependencies": {"vitest": "^2.0.0"}}),
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nyarn vitest\n```\n", encoding="utf-8"
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual([f for f in report["findings"] if f["check"] == "D1"], [])

    def test_pnpm_bin_passthrough_and_option_are_not_scripts(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"test": "node src/index.js"},
                    "devDependencies": {"mastra": "1.0.0"},
                }
            ),
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS
            + "Run `pnpm mastra dev` locally and `pnpm --filter ./packages/app test` from root.\n",
            encoding="utf-8",
        )
        self._stub_pointers(repo)
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--json"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual([f for f in report["findings"] if f["check"] == "D1"], [])

    def test_pnpm_descendant_dependency_binary_not_flagged_from_parent_scope(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text('{"scripts": {}}\n', encoding="utf-8")
            (repo / "AGENTS.md").write_text("# Root\n", encoding="utf-8")
            examples = repo / "examples"
            examples.mkdir()
            (examples / "AGENTS.md").write_text(
                "Run `pnpm mastra dev` from an example directory.\n",
                encoding="utf-8",
            )
            app = examples / "app"
            app.mkdir()
            (app / "package.json").write_text(
                '{"devDependencies": {"mastra": "1.0.0"}}\n',
                encoding="utf-8",
            )

            report = check_drift.run_checks(repo, check_drift.DEFAULT_MAX_BYTES)

            self.assertTrue(report["ok"], report["findings"])
            self.assertEqual(report["findings"], [])

    def test_npm_bin_style_reference_still_triggers_d1(self):
        # The yarn bin-passthrough exemption must not leak to npm, which has no
        # such fallback (`npm vitest` errors with "Unknown command").
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "package.json").write_text(
            json.dumps({"scripts": {"test": "node src/index.js"}, "devDependencies": {"vitest": "^2.0.0"}}),
            encoding="utf-8",
        )
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nnpm vitest\n```\n", encoding="utf-8"
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        self.assertEqual(len(d1), 1)
        self.assertIn("vitest", d1[0]["message"])

    def test_bun_run_unknown_script_triggers_d1(self):
        # The Phase-2 gate must match semantic.py's (npm|pnpm|bun) command
        # detection; a `bun run <script>` referencing a missing package.json
        # script previously slipped past the drift gate (bun blindness).
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nbun run nonexist\n```\n", encoding="utf-8"
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        self.assertEqual(len(d1), 1)
        self.assertIn("nonexist", d1[0]["message"])

    def test_glob_backtick_does_not_trigger_d2(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS + "Run against `src/**/*.ts`.\n", encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D2"])

    def test_home_relative_backtick_does_not_trigger_d2(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "Never write into the real `~/.claude`, `~/.codex`, or `/etc/hosts`.\n",
            encoding="utf-8",
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D2"])

    def test_placeholder_name_segment_does_not_trigger_d2(self):
        # A leading `<word>-name` segment (`skill-name/SKILL.md`) documents a
        # naming pattern in prose, not a literal path (found scanning
        # tldraw/tldraw's AGENTS.md). This previously failed the CI gate (D2
        # ERROR) on a legitimate, common documentation idiom.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "Skill folders use `skill-name/SKILL.md` as a template.\n",
            encoding="utf-8",
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D2"])

    def test_package_self_import_specifier_does_not_trigger_d2(self):
        # A token whose first segment is a package.json `name` (e.g.
        # `better-auth/test`) is a package export subpath, not a repo-relative
        # path. semantic.compare_paths (Phase-0 `scan`) already skips these via
        # the monorepo package-name guard, so D2 (Phase-2 `drift`) must skip them
        # too — otherwise `scan` stays silent while `drift` ERRORs on the
        # identical token, violating the TD-03 "both gates agree" invariant.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "packages" / "better-auth").mkdir(parents=True, exist_ok=True)
        (repo / "packages" / "better-auth" / "package.json").write_text(
            '{"name": "better-auth"}\n', encoding="utf-8"
        )
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "Use `getTestInstance()` from `better-auth/test`.\n",
            encoding="utf-8",
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d2 = [f for f in report["findings"] if f["check"] == "D2"]
        self.assertFalse(d2, d2)

    def test_unrelated_missing_path_still_triggers_d2(self):
        # Guard rail for the package self-import skip: a token whose first
        # segment is NOT a package name must still be flagged, so the fix does
        # not open a false-negative hole for genuinely drifted paths.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "packages" / "better-auth").mkdir(parents=True, exist_ok=True)
        (repo / "packages" / "better-auth" / "package.json").write_text(
            '{"name": "better-auth"}\n', encoding="utf-8"
        )
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "See `totally-unrelated/missing-file.ts` for details.\n",
            encoding="utf-8",
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        report = json.loads(proc.stdout)
        d2 = [f for f in report["findings"] if f["check"] == "D2"]
        self.assertTrue(any("totally-unrelated/missing-file.ts" in f["message"] for f in d2), d2)

    def test_clean_fixture_exit_zero(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_stub_regrown_d3(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        # A genuine pointer stub that regrew: it still references AGENTS.md as a
        # pointer but has grown far past the minimal-stub size budget.
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n" + "lots\n" * 200, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("D3", proc.stdout)

    def test_independent_doc_without_pointer_not_flagged_d3(self):
        # An independent, hand-authored CLAUDE.md (substantial standalone content
        # with NO AGENTS.md pointer) is not a managed pointer stub, so D3 must not
        # flag it as regrown/broken. This mirrors browser-use's standalone
        # CLAUDE.md and keeps D3 consistent with the overlap subsystem.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        independent = (
            "# CLAUDE.md\n\n"
            "This file provides guidance to Claude Code when working with this repo.\n\n"
            + "Standalone documentation paragraph.\n"
            * 200
        )
        (repo / "CLAUDE.md").write_text(independent, encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D3"])

    def test_regrown_pointer_stub_still_flagged_d3(self):
        # The counterpart guarantee: a genuine pointer stub that references
        # AGENTS.md but exceeds the size budget IS still flagged by D3.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n" + "extra guidance line\n" * 100, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d3 = [f for f in report["findings"] if f["check"] == "D3"]
        self.assertTrue(any(f["path"] == "CLAUDE.md" for f in d3))

    def test_full_duplicate_linking_nested_agents_md_not_flagged_d3(self):
        # A full hand-authored CLAUDE.md that is a complete duplicate of AGENTS.md
        # and only *links* to nested `dir/AGENTS.md` files (no `@AGENTS.md` import,
        # no "instructions live in AGENTS.md" redirect phrase) is NOT a managed
        # pointer stub. The old `"AGENTS.md" in text` heuristic wrongly flagged it
        # as a regrown stub (an ERROR that fails `drift --strict` in CI) — this
        # mirrors pydantic-ai's CLAUDE.md, which indexes ten nested `*/AGENTS.md`
        # docs. D3 must stay silent here.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        full_dup = (
            "# Project guidance\n\n"
            "This document is the primary guidance for this repository.\n\n"
            + "A substantial hand-authored paragraph of real guidance.\n" * 200
            + "\n## Nested agent docs\n\n"
            "- [docs/AGENTS.md](docs/AGENTS.md)\n"
            "- [packages/core/AGENTS.md](packages/core/AGENTS.md)\n"
            "- [tests/AGENTS.md](tests/AGENTS.md)\n"
        )
        (repo / "CLAUDE.md").write_text(full_dup, encoding="utf-8")
        self.assertGreater(len((repo / "CLAUDE.md").read_bytes()), 800)
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D3"])

    def test_pre_migration_without_agents_suppresses_d3_but_reports_d4(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "CLAUDE.md").write_text("existing pre-migration instructions\n" * 40, encoding="utf-8")

        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)

        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D3"])
        d4 = [f for f in report["findings"] if f["check"] == "D4"]
        self.assertEqual(len(d4), 1)
        self.assertIn("AGENTS.md is missing", d4[0]["message"])

    def test_fix_dry_run_reports_but_writes_nothing(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n" + "lots\n" * 200, encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        before = (repo / "CLAUDE.md").read_text(encoding="utf-8")

        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--fix"], text=True, capture_output=True)

        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("dry run", proc.stdout)
        self.assertIn("would rewrite `CLAUDE.md`", proc.stdout)
        self.assertIn("1 fixable", proc.stdout)
        # Nothing was actually written.
        self.assertEqual(before, (repo / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_fix_apply_rewrites_regrown_stub_to_minimal_form(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n" + "lots\n" * 200, encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True
        )

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("rewrote `CLAUDE.md`", proc.stdout)
        self.assertIn("1 fixed", proc.stdout)
        rewritten = (repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(rewritten.startswith("@AGENTS.md"))
        self.assertLessEqual(len(rewritten.encode("utf-8")), 600)
        # A follow-up drift check now passes (D3 resolved).
        recheck = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(recheck.returncode, 0, recheck.stdout + recheck.stderr)

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_fix_apply_refuses_external_stub_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            outside = base / "outside-claude.md"
            outside.write_text("@AGENTS.md\n" + "outside\n" * 200, encoding="utf-8")
            (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
            (repo / "CLAUDE.md").symlink_to(outside)
            regular_stub = repo / ".cursorrules"
            regular_stub.write_text(
                "All agent instructions live in AGENTS.md.\n" + "regular\n" * 200,
                encoding="utf-8",
            )
            before = outside.read_bytes()
            regular_before = regular_stub.read_bytes()

            proc = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--fix", "--apply"],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("unsafe", proc.stdout.lower())
            self.assertEqual(outside.read_bytes(), before)
            self.assertEqual(regular_stub.read_bytes(), regular_before)
            self.assertTrue((repo / "CLAUDE.md").is_symlink())

    def test_fix_reports_non_autofixable_drift_and_leaves_files_untouched(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        agents = CLEAN_AGENTS.replace("npm run test", "npm run nonexist")
        (repo / "AGENTS.md").write_text(agents, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True
        )

        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("needs manual attention", proc.stdout)
        self.assertIn("D1", proc.stdout)
        self.assertIn("nonexist", proc.stdout)
        self.assertIn("1 need manual attention", proc.stdout)
        # AGENTS.md is not modified by --fix for D1 command drift.
        self.assertEqual(agents, (repo / "AGENTS.md").read_text(encoding="utf-8"))

    def test_prose_imperative_does_not_trigger_d1_but_real_command_does(self):
        # A prose imperative ("make sure the tests pass") must not be parsed into
        # a phantom Makefile target and fail the gate, while a genuine fenced
        # `make deploy` (absent from the Makefile) is still flagged (CORR-02).
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "Makefile").write_text("build:\n\techo hi\n", encoding="utf-8")
        body = (
            CLEAN_AGENTS
            + "\nPlease make sure the tests pass before committing.\n\n"
            + "```bash\n# make sure to run the tests first\nmake deploy\n```\n"
        )
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        messages = " ".join(f["message"] for f in d1)
        self.assertIn("deploy", messages)
        self.assertNotIn("sure", messages)

    def test_hyphenated_command_name_missing_target_triggers_d1(self):
        # CORRECTNESS-01: `make lint-and-fix` was previously misread as an
        # English sentence (the "and" inside the hyphenated identifier counted
        # as a prose-word hit), silently disabling the D1 gate for it.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "Makefile").write_text("build:\n\techo hi\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "\nRun `make lint-and-fix` before committing.\n", encoding="utf-8"
        )
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        self.assertEqual(len(d1), 1)
        self.assertIn("lint-and-fix", d1[0]["message"])

    def test_invalid_package_json_does_not_produce_false_unknown_script_d1(self):
        # A present-but-unparseable package.json must not be treated as "no
        # scripts": package_scripts returns None so D1 skips the unknown-script
        # check instead of flagging every referenced script (CORR-01).
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS.replace("npm run test", "npm run build"), encoding="utf-8")
        (repo / "package.json").write_text("{ this is not valid json ", encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        report = json.loads(proc.stdout)
        d1 = [f for f in report["findings"] if f["check"] == "D1"]
        self.assertEqual(d1, [])

    def test_package_scripts_none_on_invalid_and_absent_but_set_on_valid(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertIsNone(check_drift.package_scripts(root))  # absent
            (root / "package.json").write_text("{ invalid", encoding="utf-8")
            self.assertIsNone(check_drift.package_scripts(root))  # invalid JSON
            (root / "package.json").write_text('{"scripts": {"build": "x"}}', encoding="utf-8")
            self.assertEqual(check_drift.package_scripts(root), {"build"})
            (root / "package.json").write_text("{}", encoding="utf-8")
            self.assertEqual(check_drift.package_scripts(root), set())  # valid, no scripts

    def test_make_targets_handles_multi_target_rules_and_assignments(self):
        # `build test: deps` previously matched nothing at all (neither `build`
        # nor `test` was added), while `CFLAGS:=-O2` and `.PHONY: ...` were
        # WRONGLY added as if they were real invokable targets.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Makefile").write_text(
                "build test: deps\n\techo building\n\n"
                "deps:\n\techo deps\n\n"
                "CFLAGS:=-O2 -Wall\n"
                "CFLAGS2 ::= -O3\n"
                ".PHONY: build test\n"
                "debug: CFLAGS = -g\n\techo debug\n",
                encoding="utf-8",
            )
            self.assertEqual(check_drift.make_targets(root), {"build", "test", "deps", "debug"})

    def test_multi_target_makefile_rule_does_not_false_positive_d1(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "Makefile").write_text("build test: deps\n\techo hi\n\ndeps:\n\techo deps\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "```bash\nmake build\nmake test\n```\n", encoding="utf-8"
        )
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual([f for f in report["findings"] if f["check"] == "D1"], [])

    def test_out_of_repo_tokens_do_not_probe_but_in_repo_missing_does(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        body = (
            CLEAN_AGENTS
            + "\nAbsolute: `/etc/hostname`.\n"
            + "Escaping: `../outside.txt`.\n"
            + "In-repo: `docs/missing.md`.\n"
        )
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d2 = [f for f in report["findings"] if f["check"] == "D2"]
        messages = " ".join(f["message"] for f in d2)
        # Out-of-repo tokens are ignored entirely (no filesystem probing).
        self.assertNotIn("/etc/hostname", messages)
        self.assertNotIn("../outside.txt", messages)
        # The in-repo missing path is still reported.
        self.assertTrue(any("docs/missing.md" in f["message"] for f in d2))

    def _stub_pointers(self, repo):
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")

    def test_node_version_fact_drift_d6(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS + "\n# Toolchain\nUse Node 18 for development.\n", encoding="utf-8"
        )
        (repo / ".nvmrc").write_text("20\n", encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d6 = [f for f in report["findings"] if f["check"] == "D6"]
        self.assertTrue(d6)
        self.assertTrue(any("Node 18" in f["message"] and "Node 20" in f["message"] for f in d6))

    def test_package_manager_fact_drift_d6(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS.replace("npm run test", "pnpm run test"), encoding="utf-8")
        (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d6 = [f for f in report["findings"] if f["check"] == "D6"]
        self.assertTrue(d6)
        self.assertTrue(any("pnpm" in f["message"] and "package-lock.json" in f["message"] for f in d6))

    def test_clean_repo_high_score_grade_and_no_d6(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D6"])
        self.assertGreaterEqual(report["score"], 80)
        self.assertIn(report["grade"], ("A", "B"))

    def test_min_score_gate_returns_nonzero(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        # Clean repo scores 100 (exit 0), but a threshold above the score must gate CI.
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--min-score", "101"], text=True, capture_output=True
        )
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Score:", proc.stdout)

    def test_broken_markdown_link_triggers_d7(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        body = CLEAN_AGENTS + "\nSee the [runbook](references/missing.md) for details.\n"
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d7 = [f for f in report["findings"] if f["check"] == "D7"]
        self.assertEqual(len(d7), 1)
        self.assertIn("references/missing.md", d7[0]["message"])
        self.assertEqual(d7[0]["level"], "ERROR")

    def test_existing_markdown_link_and_url_do_not_trigger_d7(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "docs").mkdir()
        (repo / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
        body = (
            CLEAN_AGENTS
            + "\nSee the [guide](docs/guide.md) and the [site](https://example.com/x).\n"
            + "Jump to the [top](#project-overview) or email [us](mailto:a@b.com).\n"
        )
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D7"])

    def test_url_encoded_markdown_link_does_not_trigger_d7(self):
        # Markdown percent-encodes spaces in link targets; the D7 probe must
        # decode before checking existence, else a valid file is falsely
        # flagged as a broken link and fails CI.
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "docs").mkdir()
        (repo / "docs" / "my guide.md").write_text("# Guide\n", encoding="utf-8")
        body = CLEAN_AGENTS + "\nSee the [guide](docs/my%20guide.md) for details.\n"
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D7"])

    def test_out_of_repo_markdown_link_does_not_probe(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        body = CLEAN_AGENTS + "\nAbsolute: [x](/etc/hostname). Escaping: [y](../outside.md).\n"
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse([f for f in report["findings"] if f["check"] == "D7"])

    def test_d7_is_reported_as_manual_by_fix(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        body = CLEAN_AGENTS + "\nSee the [runbook](references/missing.md).\n"
        (repo / "AGENTS.md").write_text(body, encoding="utf-8")
        self._stub_pointers(repo)
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("needs manual attention", proc.stdout)
        self.assertIn("D7", proc.stdout)
        # AGENTS.md is never rewritten by --fix.
        self.assertEqual(body, (repo / "AGENTS.md").read_text(encoding="utf-8"))

    def test_competing_lockfiles_trigger_d8(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d8 = [f for f in report["findings"] if f["check"] == "D8"]
        self.assertEqual(len(d8), 1)
        self.assertIn("package-lock.json", d8[0]["message"])
        self.assertIn("pnpm-lock.yaml", d8[0]["message"])

    def test_competing_bun_lockfile_triggers_d8(self):
        # TD-01: the drift gate previously omitted bun from its lockfile map and
        # was blind to bun repos. A bun.lockb alongside package-lock.json is now
        # a competing-manager conflict (D8).
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        (repo / "bun.lockb").write_bytes(b"\x00bun binary lockfile\x00")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        d8 = [f for f in report["findings"] if f["check"] == "D8"]
        self.assertEqual(len(d8), 1)
        self.assertIn("bun.lockb", d8[0]["message"])
        self.assertIn("package-lock.json", d8[0]["message"])

    def test_single_lockfile_does_not_trigger_d8(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        (repo / "npm-shrinkwrap.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        # Both lockfiles map to npm -> only one manager -> no ambiguity.
        self.assertFalse([f for f in report["findings"] if f["check"] == "D8"])

    def test_d8_is_reported_as_manual_by_fix(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        self._stub_pointers(repo)
        (repo / "package-lock.json").write_text('{"lockfileVersion": 3}\n', encoding="utf-8")
        (repo / "yarn.lock").write_text("# yarn lockfile v1\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("needs manual attention", proc.stdout)
        self.assertIn("D8", proc.stdout)


class NestedAgentsWalkTests(unittest.TestCase):
    def test_prunes_vendored_dirs_but_finds_real_nested(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "node_modules" / "pkg").mkdir(parents=True)
            (repo / "node_modules" / "pkg" / "AGENTS.md").write_text("vendored\n", encoding="utf-8")
            (repo / "dist").mkdir()
            (repo / "dist" / "AGENTS.md").write_text("built\n", encoding="utf-8")
            (repo / ".git").mkdir()
            (repo / ".git" / "AGENTS.md").write_text("git\n", encoding="utf-8")
            (repo / "sub").mkdir()
            (repo / "sub" / "AGENTS.md").write_text("real nested\n", encoding="utf-8")
            (repo / "AGENTS.md").write_text("root\n", encoding="utf-8")
            found = check_drift.nested_agents(repo)
            self.assertIn("sub/AGENTS.md", found)
            self.assertNotIn("node_modules/pkg/AGENTS.md", found)
            self.assertFalse([p for p in found if "node_modules" in p or "dist" in p or ".git" in p])
            self.assertNotIn("AGENTS.md", found)  # root itself excluded

    @unittest.skipUnless(_can_symlink_dirs(), "directory symlinks unsupported on this platform")
    def test_symlink_loop_terminates(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "sub").mkdir(parents=True)
            (repo / "sub" / "AGENTS.md").write_text("nested\n", encoding="utf-8")
            # Create a self-referential directory symlink cycle.
            (repo / "sub" / "loop").symlink_to(repo / "sub", target_is_directory=True)
            found = check_drift.nested_agents(repo)  # must terminate, not loop forever
            self.assertIn("sub/AGENTS.md", found)

    @unittest.skipUnless(_can_symlink_files(), "file symlinks unsupported on this platform")
    def test_external_nested_agents_symlink_is_not_a_scope(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            nested = repo / "packages" / "api"
            nested.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("root\n", encoding="utf-8")
            outside = base / "outside.md"
            outside.write_text("Run `npm run outside-only`.\n", encoding="utf-8")
            (nested / "AGENTS.md").symlink_to(outside)

            self.assertEqual(check_drift.nested_agents(repo), [])
            self.assertEqual(
                check_drift.drift_scopes(repo),
                [{"root": repo.resolve(), "path": "AGENTS.md", "is_root": True}],
            )


class BaselineTests(unittest.TestCase):
    """--baseline / --write-baseline: adopt the drift gate on a repo that already
    has drift, then fail CI only on NEW drift."""

    def _repo_with_drift(self, script="nope"):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name) / "repo"
        shutil.copytree(FIXTURE, repo)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS.replace("npm run test", f"npm run {script}"), encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        return td, repo

    def test_write_baseline_records_current_findings_and_exits_zero(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        bl = repo.parent / "drift-baseline.json"
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--write-baseline", str(bl)], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(bl.is_file())
        data = json.loads(bl.read_text(encoding="utf-8"))
        self.assertEqual(data["version"], check_drift.BASELINE_VERSION)
        self.assertIn("Unknown package.json script `nope`", [e["message"] for e in data["findings"]])

    def test_baseline_suppresses_preexisting_drift(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        bl = repo.parent / "bl.json"
        subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--write-baseline", str(bl)],
            check=True,
            text=True,
            capture_output=True,
        )
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--baseline", str(bl), "--json"], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report["ok"])
        self.assertFalse(report["findings"])
        self.assertEqual(len(report["baselined"]), 1)
        self.assertEqual(report["score"], 100)
        self.assertEqual(report["grade"], "A")

    def test_new_drift_fails_while_baselined_is_suppressed(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        bl = repo.parent / "bl.json"
        subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--write-baseline", str(bl)],
            check=True,
            text=True,
            capture_output=True,
        )
        # Introduce a SECOND, new bad command; the baselined one must stay suppressed.
        two = CLEAN_AGENTS.replace("Run `npm run test`.", "Run `npm run nope` and `npm run brandnew`.")
        (repo / "AGENTS.md").write_text(two, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--baseline", str(bl), "--json"], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ok"])
        new_msgs = [f["message"] for f in report["findings"]]
        self.assertIn("Unknown package.json script `brandnew`", new_msgs)
        self.assertNotIn("Unknown package.json script `nope`", new_msgs)
        self.assertEqual(len(report["baselined"]), 1)

    def test_resolved_baseline_is_visible_checkable_and_prunable(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        baseline = repo.parent / "drift-baseline.json"
        subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--write-baseline", str(baseline)],
            check=True,
            text=True,
            capture_output=True,
        )
        original = json.loads(baseline.read_text(encoding="utf-8"))
        self.assertEqual(len(original["findings"]), 1)

        # Replace the known command drift with a new one. The old entry is
        # resolved; the new finding must remain active and never be auto-added.
        (repo / "AGENTS.md").write_text(
            CLEAN_AGENTS.replace("npm run test", "npm run brandnew"),
            encoding="utf-8",
        )
        reported = subprocess.run(
            [
                sys.executable,
                str(DRIFT),
                str(repo),
                "--baseline",
                str(baseline),
                "--json",
            ],
            text=True,
            capture_output=True,
        )
        report = json.loads(reported.stdout)
        self.assertEqual(report["baselined"], [])
        self.assertEqual(report["resolved_baseline"], original["findings"])
        self.assertEqual(report["baseline"]["known"], 0)
        self.assertEqual(report["baseline"]["resolved"], 1)
        self.assertIn(
            "Unknown package.json script `brandnew`",
            [finding["message"] for finding in report["findings"]],
        )

        checked = subprocess.run(
            [
                sys.executable,
                str(DRIFT),
                str(repo),
                "--baseline",
                str(baseline),
                "--check-baseline",
                "--json",
            ],
            text=True,
            capture_output=True,
        )
        # Active drift exit 1 keeps precedence over baseline maintenance exit 9.
        self.assertEqual(checked.returncode, 1)

        # Repair every active finding so the maintenance-only exit becomes 9.
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        checked_clean = subprocess.run(
            [
                sys.executable,
                str(DRIFT),
                str(repo),
                "--baseline",
                str(baseline),
                "--check-baseline",
                "--json",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(checked_clean.returncode, check_drift.BASELINE_MAINTENANCE_EXIT)
        self.assertEqual(len(json.loads(checked_clean.stdout)["resolved_baseline"]), 1)

        pruned = subprocess.run(
            [
                sys.executable,
                str(DRIFT),
                str(repo),
                "--baseline",
                str(baseline),
                "--prune-baseline",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(pruned.returncode, 0, pruned.stdout + pruned.stderr)
        self.assertEqual(
            json.loads(baseline.read_text(encoding="utf-8")),
            {"version": check_drift.BASELINE_VERSION, "findings": []},
        )

    def test_baseline_maintenance_fails_closed_on_malformed_input(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        baseline = repo.parent / "bad.json"
        baseline.write_text("{bad", encoding="utf-8")
        original = baseline.read_bytes()
        for mode in ("--check-baseline", "--prune-baseline"):
            with self.subTest(mode=mode):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(DRIFT),
                        str(repo),
                        "--baseline",
                        str(baseline),
                        mode,
                    ],
                    text=True,
                    capture_output=True,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("baseline error", proc.stderr)
                self.assertEqual(baseline.read_bytes(), original)

    def test_baseline_survives_line_number_shift(self):
        # Fingerprints ignore line numbers, so an unrelated edit above the drift
        # must not "un-baseline" it (the whole point of a durable baseline).
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        bl = repo.parent / "bl.json"
        subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--write-baseline", str(bl)],
            check=True,
            text=True,
            capture_output=True,
        )
        original = (repo / "AGENTS.md").read_text(encoding="utf-8")
        (repo / "AGENTS.md").write_text("# Note\n\nUnrelated preamble line.\n\n" + original, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--baseline", str(bl)], text=True, capture_output=True
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("suppressed by the baseline", proc.stdout)

    def test_missing_or_malformed_baseline_suppresses_nothing(self):
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        missing = repo.parent / "does-not-exist.json"
        proc = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--baseline", str(missing), "--json"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 1)
        report = json.loads(proc.stdout)
        self.assertFalse(report["ok"])
        self.assertFalse(report["baselined"])
        bad = repo.parent / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        proc2 = subprocess.run(
            [sys.executable, str(DRIFT), str(repo), "--baseline", str(bad), "--json"], text=True, capture_output=True
        )
        self.assertEqual(proc2.returncode, 1)
        self.assertFalse(json.loads(proc2.stdout)["baselined"])

    def test_no_baseline_flag_means_no_baseline_section(self):
        # Additive: without --baseline the output is unchanged and `baselined` is empty.
        td, repo = self._repo_with_drift()
        self.addCleanup(td.cleanup)
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(json.loads(proc.stdout)["baselined"], [])
        self.assertNotIn("baseline", json.loads(proc.stdout))
        md = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertNotIn("## Baseline", md.stdout)

    def test_baseline_payload_is_deterministic_and_untimestamped(self):
        findings = [
            {"check": "D2", "level": "ERROR", "message": "b", "path": None, "line": 9},
            {"check": "D1", "level": "ERROR", "message": "a", "line": 3},
            {"check": "D1", "level": "ERROR", "message": "a", "line": 99},  # duplicate fingerprint
            {"check": "D5", "level": "INFO", "message": "ignored inventory"},
        ]
        payload = check_drift.baseline_payload(findings)
        self.assertEqual(payload["version"], check_drift.BASELINE_VERSION)
        self.assertNotIn("generated", payload)  # deterministic: no timestamp
        self.assertEqual(
            [(e["check"], e["message"]) for e in payload["findings"]],
            [("D1", "a"), ("D2", "b")],  # sorted, de-duplicated, INFO dropped
        )

    def test_nested_baseline_identity_is_path_scoped_and_root_compatible(self):
        root = {
            "check": "D1",
            "level": "ERROR",
            "message": "Unknown package.json script `nope`",
            "line": 2,
        }
        api = {**root, "path": "packages/api/AGENTS.md"}
        web = {**root, "path": "packages/web/AGENTS.md"}
        payload = check_drift.baseline_payload([root, api, web])

        self.assertEqual(
            [(entry["path"], entry["message"]) for entry in payload["findings"]],
            [
                (None, root["message"]),
                ("packages/api/AGENTS.md", root["message"]),
                ("packages/web/AGENTS.md", root["message"]),
            ],
        )
        baseline = {
            (entry["check"], entry["message"], entry.get("path") or "")
            for entry in payload["findings"][:2]
        }
        self.assertIn(check_drift.finding_fingerprint(root), baseline)
        self.assertIn(check_drift.finding_fingerprint(api), baseline)
        self.assertNotIn(check_drift.finding_fingerprint(web), baseline)


if __name__ == "__main__":
    unittest.main()
