import shutil
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
CANON = ROOT / "scripts" / "canonicalize.py"


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


if __name__ == "__main__":
    unittest.main()
