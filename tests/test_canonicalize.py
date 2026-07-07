import shutil
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

    def test_write_stubs_dry_run_prints_diff_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            before = (repo / "CLAUDE.md").read_text(encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--write-stubs", str(repo)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("--- a/CLAUDE.md", proc.stdout)
            self.assertEqual(before, (repo / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_write_stubs_apply_rewrites_claude(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            proc = subprocess.run([sys.executable, str(CANON), "--write-stubs", str(repo), "--apply"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((repo / "CLAUDE.md").read_text(encoding="utf-8").startswith("@AGENTS.md"))

    def test_validate_missing_and_present(self):
        proc = subprocess.run([sys.executable, str(CANON), "--validate", str(FIXTURE)], text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            shutil.copytree(FIXTURE, repo)
            (repo / "AGENTS.md").write_text(AGENTS_MIN, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(CANON), "--validate", str(repo)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
