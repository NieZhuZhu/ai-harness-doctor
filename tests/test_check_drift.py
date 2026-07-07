import shutil
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
DRIFT = ROOT / "scripts" / "check_drift.py"


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

    def test_package_manager_builtins_do_not_trigger_d1(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS + "```bash\nnpm install\nyarn add foo\nnpm run nonexist\n```\n", encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
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
        (repo / "CLAUDE.md").write_text("lots\n" * 200, encoding="utf-8")
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("D3", proc.stdout)

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


if __name__ == "__main__":
    unittest.main()
