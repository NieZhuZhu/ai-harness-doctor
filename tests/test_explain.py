import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
EXPLAIN = ROOT / "scripts" / "explain.py"

sys.path.insert(0, str(ROOT / "scripts"))
import explain  # noqa: E402
import scan  # noqa: E402


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class ExplainTests(unittest.TestCase):
    def test_root_only_chain(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "src/index.js", "x\n")

            report = explain.build_explanation(td, "src/index.js")

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["repo"], ".")
            self.assertEqual(report["target"]["path"], "src/index.js")
            self.assertEqual(report["effective_scope"], ".")
            self.assertEqual(
                report["canonical_chain"],
                [{"path": "AGENTS.md", "scope": ".", "parent": None}],
            )

    def test_nested_deep_and_sibling_targets_follow_component_ancestry(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "packages/api/AGENTS.md", "Use pnpm.\n")
            write(td, "packages/api/src/AGENT.md", "Use yarn.\n")
            write(td, "packages/application/CLAUDE.md", "Use npm.\n")
            write(td, "packages/api/src/handler.py", "pass\n")
            write(td, "packages/application/index.py", "pass\n")

            deep = explain.build_explanation(td, "packages/api/src/handler.py")
            sibling = explain.build_explanation(td, "packages/application/index.py")

            self.assertEqual(deep["effective_scope"], "packages/api/src")
            self.assertEqual(
                [row["scope"] for row in deep["canonical_chain"]],
                [".", "packages/api", "packages/api/src"],
            )
            self.assertEqual(sibling["effective_scope"], ".")
            self.assertNotIn(
                "packages/api",
                [row["scope"] for row in sibling["canonical_chain"]],
            )

    def test_future_target_is_allowed_without_creating_it(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "packages/api/AGENTS.md", "Use pnpm.\n")
            target = Path(td) / "packages/api/src/future.py"

            report = explain.build_explanation(td, "packages/api/src/future.py")

            self.assertFalse(report["target"]["exists"])
            self.assertEqual(report["target"]["kind"], "missing")
            self.assertEqual(report["effective_scope"], "packages/api")
            self.assertFalse(target.exists())

    def test_directory_at_deep_scope_root_uses_that_scope(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "packages/api/src/AGENTS.md", "Use pnpm.\n")

            report = explain.build_explanation(td, "packages/api/src")

            self.assertTrue(report["target"]["exists"])
            self.assertEqual(report["target"]["kind"], "directory")
            self.assertEqual(report["effective_scope"], "packages/api/src")
            self.assertEqual(
                [row["scope"] for row in report["canonical_chain"]],
                [".", "packages/api/src"],
            )

    def test_contained_absolute_target_normalizes_like_relative(self):
        with tempfile.TemporaryDirectory() as td:
            path = write(td, "src/index.js", "x\n")
            write(td, "AGENTS.md", "Use npm.\n")
            relative = explain.build_explanation(td, "src/index.js")
            absolute = explain.build_explanation(td, str(path.resolve()))
            self.assertEqual(relative, absolute)

    def test_escape_and_external_symlink_are_rejected_without_path_leak(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            write(repo, "AGENTS.md", "Use npm.\n")
            outside = base / "outside"
            outside.mkdir()
            try:
                (repo / "escape").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported")

            for target in ("../outside/file.py", "escape/file.py"):
                with self.subTest(target=target):
                    proc = subprocess.run(
                        [sys.executable, str(EXPLAIN), str(repo), target, "--json"],
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(proc.returncode, 1)
                    self.assertIn("must stay inside", proc.stderr)
                    self.assertNotIn(str(base.resolve()), proc.stderr)
                    self.assertEqual(proc.stdout, "")

    def test_contained_symlink_keeps_lexical_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, "AGENTS.md", "Use npm.\n")
            write(root, "packages/api/AGENTS.md", "Use pnpm.\n")
            write(root, "packages/api/src/real.py", "pass\n")
            alias = root / "alias"
            try:
                alias.symlink_to(root / "packages" / "api", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported")

            report = explain.build_explanation(root, "alias/src/real.py")

            self.assertEqual(report["target"]["path"], "alias/src/real.py")
            self.assertEqual(report["effective_scope"], ".")
            self.assertEqual(
                report["canonical_chain"],
                [{"path": "AGENTS.md", "scope": ".", "parent": None}],
            )

    def test_skipped_subtree_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            report = explain.build_explanation(td, "node_modules/pkg/index.js")
            self.assertTrue(report["target"]["excluded_by_scan"])
            self.assertEqual(
                report["canonical_chain"],
                [{"path": "AGENTS.md", "scope": ".", "parent": None}],
            )
            markdown = explain.render_markdown(report)
            self.assertIn("excluded directory", markdown)

    def test_missing_root_canonical_does_not_fabricate_chain(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "CLAUDE.md", "Use npm.\n")
            report = explain.build_explanation(td, "src/future.js")
            self.assertEqual(report["canonical_chain"], [])
            self.assertEqual(report["effective_scope"], ".")
            self.assertEqual(report["diagnostic_sources"][0]["path"], "CLAUDE.md")

    def test_relevant_overrides_conflicts_and_diagnostic_wording(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "packages/api/AGENTS.md", "Use pnpm.\n")
            write(td, "packages/api/CLAUDE.md", "Use yarn.\n")
            write(td, "packages/web/AGENTS.md", "Use bun.\n")

            report = explain.build_explanation(td, "packages/api/src/future.py")

            self.assertTrue(report["scope_overrides"])
            self.assertEqual(report["conflicts"], [])
            source_paths = {item["path"] for item in report["diagnostic_sources"]}
            self.assertIn("packages/api/CLAUDE.md", source_paths)
            self.assertNotIn("packages/web/AGENTS.md", source_paths)
            statuses = {
                item["path"]: item["status"]
                for item in report["source_applicability"]
            }
            self.assertEqual(statuses["packages/api/AGENTS.md"], "automatic")
            self.assertEqual(statuses["packages/api/CLAUDE.md"], "diagnostic")
            serialized = json.dumps(report)
            self.assertNotIn("Use pnpm.", serialized)
            self.assertIn("diagnostically associated", report["limitations"][0])

    def test_structured_rules_are_classified_for_existing_and_future_targets(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "General guidance.\n")
            write(td, "src/app.js", "x\n")
            write(td, "scripts/check.py", "pass\n")
            write(
                td,
                ".github/instructions/js.instructions.md",
                '---\napplyTo: "src/**/*.js"\n---\nUse npm.\n',
            )
            write(
                td,
                ".github/instructions/python.instructions.md",
                '---\napplyTo: "scripts/**/*.py"\n---\nUse uv.\n',
            )
            write(
                td,
                ".cursor/rules/conditional.mdc",
                "---\ndescription: Database conventions\nalwaysApply: false\n---\nUse pnpm.\n",
            )

            js = explain.build_explanation(td, "src/app.js")
            python_future = explain.build_explanation(td, "scripts/future.py")

            js_status = {
                item["path"]: item["status"]
                for item in js["source_applicability"]
            }
            py_status = {
                item["path"]: item["status"]
                for item in python_future["source_applicability"]
            }
            self.assertEqual(
                js_status[".github/instructions/js.instructions.md"],
                "automatic",
            )
            self.assertEqual(
                js_status[".github/instructions/python.instructions.md"],
                "non-matching",
            )
            self.assertEqual(
                py_status[".github/instructions/python.instructions.md"],
                "automatic",
            )
            self.assertEqual(
                py_status[".github/instructions/js.instructions.md"],
                "non-matching",
            )
            self.assertEqual(
                js_status[".cursor/rules/conditional.mdc"],
                "conditional",
            )
            self.assertEqual(js["conflicts"], [])
            self.assertEqual(python_future["conflicts"], [])
            markdown = explain.render_markdown(js)
            self.assertIn("Target applicability", markdown)
            self.assertIn("`non-matching`", markdown)
            self.assertIn("description", js["limitations"][0].lower())

    def test_claude_rules_apply_to_matching_existing_and_future_targets(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use pnpm.\n")
            write(td, "scripts/check.py", "pass\n")
            write(
                td,
                ".claude/rules/python.md",
                "---\n"
                "paths:\n"
                '  - "scripts/**/*.py"\n'
                "---\n"
                "Use `uv run pytest`.\n",
            )

            existing = explain.build_explanation(td, "scripts/check.py")
            future = explain.build_explanation(td, "scripts/future.py")
            unrelated = explain.build_explanation(td, "src/future.ts")

            for report in (existing, future):
                statuses = {
                    item["path"]: item["status"]
                    for item in report["source_applicability"]
                }
                self.assertEqual(
                    statuses[".claude/rules/python.md"],
                    "automatic",
                )
                self.assertEqual(
                    {
                        value
                        for conflict in report["conflicts"]
                        if conflict["signal"] == "package_manager"
                        for value in conflict["values"]
                    },
                    {"pnpm", "uv"},
                )

            statuses = {
                item["path"]: item["status"]
                for item in unrelated["source_applicability"]
            }
            self.assertEqual(
                statuses[".claude/rules/python.md"],
                "non-matching",
            )
            self.assertEqual(unrelated["conflicts"], [])

    def test_explain_reports_only_conflicts_applicable_to_target(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "src/app.js", "x\n")
            write(td, "scripts/check.py", "pass\n")
            write(
                td,
                ".github/instructions/js-a.instructions.md",
                '---\napplyTo: "src/**/*.js"\n---\nUse npm.\n',
            )
            write(
                td,
                ".github/instructions/js-b.instructions.md",
                '---\napplyTo: "src/**/*.js"\n---\nUse pnpm.\n',
            )
            write(
                td,
                ".github/instructions/python.instructions.md",
                '---\napplyTo: "scripts/**/*.py"\n---\nUse uv.\n',
            )

            js = explain.build_explanation(td, "src/future.js")
            python = explain.build_explanation(td, "scripts/check.py")

            self.assertEqual(len(js["conflicts"]), 1)
            self.assertEqual(
                set(js["conflicts"][0]["values"]),
                {"npm", "pnpm"},
            )
            self.assertEqual(python["conflicts"], [])

    def test_inventory_walks_once_and_repeat_json_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            write(td, "packages/api/AGENTS.md", "Use pnpm.\n")
            calls = {"count": 0}
            real = scan.build_file_index

            def counting(root):
                calls["count"] += 1
                return real(root)

            with mock.patch.object(scan, "build_file_index", counting):
                first = explain.build_explanation(td, "packages/api/x.py")
            second = explain.build_explanation(td, "packages/api/x.py")
            self.assertEqual(calls["count"], 1)
            self.assertEqual(
                json.dumps(first, ensure_ascii=False, sort_keys=True),
                json.dumps(second, ensure_ascii=False, sort_keys=True),
            )

    def test_oversize_source_reports_partial_semantic_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", ("Use npm.\n" * 100) + "Use pnpm in the unseen tail.\n")

            report = explain.build_explanation(td, "src/future.js", max_bytes=32)

            self.assertEqual(report["conflicts"], [])
            self.assertEqual(report["analysis_limits"][0]["path"], "AGENTS.md")
            self.assertEqual(report["analysis_limits"][0]["analyzed_bytes"], 32)
            markdown = explain.render_markdown(report)
            self.assertIn("No finding is claimed for the unseen semantic tail", markdown)

    def test_cli_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "AGENTS.md", "Use npm.\n")
            json_proc = subprocess.run(
                [sys.executable, str(EXPLAIN), td, "src/future.js", "--json"],
                text=True,
                capture_output=True,
            )
            markdown_proc = subprocess.run(
                [sys.executable, str(EXPLAIN), td, "src/future.js"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(json_proc.returncode, 0, json_proc.stderr)
            self.assertEqual(json.loads(json_proc.stdout)["schema_version"], 1)
            self.assertEqual(markdown_proc.returncode, 0, markdown_proc.stderr)
            self.assertIn("Canonical instruction chain", markdown_proc.stdout)
            self.assertNotIn(str(Path(td).resolve()), json_proc.stdout + markdown_proc.stdout)


if __name__ == "__main__":
    unittest.main()
