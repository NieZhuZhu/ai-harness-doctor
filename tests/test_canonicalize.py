import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_write_stubs_dry_run_prints_diff_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / ".cursor" / "rules").mkdir(parents=True)
            (repo / ".cursor" / "rules" / "extra.mdc").write_text("old cursor rule\n", encoding="utf-8")
            before = (repo / "CLAUDE.md").read_text(encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--write-stubs", str(repo)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--- a/CLAUDE.md", proc.stdout)
            self.assertIn("delete .cursor/rules/extra.mdc", proc.stdout)
            self.assertEqual(before, (repo / "CLAUDE.md").read_text(encoding="utf-8"))
            self.assertTrue((repo / ".cursor" / "rules" / "extra.mdc").is_file())

    def test_write_stubs_apply_rewrites_claude(self):
        with tempfile.TemporaryDirectory() as td:
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
            proc = subprocess.run([sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((repo / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md"))
            self.assertFalse((repo / ".cursor" / "rules" / "extra.mdc").exists())
            self.assertTrue((repo / ".cursor" / "rules" / "agents-md.mdc").is_file())

    def test_validate_missing_and_present(self):
        proc = subprocess.run([sys.executable, str(CANON), "--validate", str(FIXTURE)], text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--validate", str(repo)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_validate_stub_notice_does_not_fail(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            (repo / "CLAUDE.md").write_text("not a stub\n" * 100, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["ok"])
            notices = [f for f in report["findings"] if f["level"] == "NOTICE"]
            self.assertTrue(any("CLAUDE.md" == f.get("path") for f in notices))

    def test_validate_missing_required_section_still_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Project overview\nOnly overview.\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--validate", str(repo), "--json"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 1)
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
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            (repo / "package.json").write_text(
                '{"name":"x","scripts":{"test":"node t.js"}}\n', encoding="utf-8"
            )
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

    def test_draft_o_writes_file_and_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            out_path = Path(td) / "AGENTS.draft.md"
            proc = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path)],
                text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out_path.is_file())
            self.assertIn("# Project overview", out_path.read_text(encoding="utf-8"))
            # Second run must refuse to clobber an existing file without --force.
            proc2 = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path)],
                text=True, capture_output=True,
            )
            self.assertNotEqual(proc2.returncode, 0)
            self.assertIn("Refusing to overwrite", proc2.stderr)
            # --force allows overwrite.
            proc3 = subprocess.run(
                [sys.executable, str(CANON), str(repo), "--draft", "-o", str(out_path), "--force"],
                text=True, capture_output=True,
            )
            self.assertEqual(proc3.returncode, 0, proc3.stderr)


class ConflictDefaultTests(unittest.TestCase):
    def test_lockfile_backs_package_manager_recommendation(self):
        with tempfile.TemporaryDirectory() as td:
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
        with tempfile.TemporaryDirectory() as td:
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
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".nvmrc").write_text("20\n", encoding="utf-8")
            values = {
                "node 18": [{"path": "CLAUDE.md", "line": 3}],
                "node 20": [{"path": ".cursorrules", "line": 3}],
            }
            value, rationale = canonicalize.recommend_conflict_default("node_version", values, root)
            self.assertEqual(value, "node 20")
            self.assertIn(".nvmrc", rationale)


if __name__ == "__main__":
    unittest.main()
