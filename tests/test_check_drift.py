import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
DRIFT = ROOT / "scripts" / "check_drift.py"

sys.path.insert(0, str(ROOT / "scripts"))
import check_drift  # noqa: E402


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

    def test_fix_dry_run_reports_but_writes_nothing(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("lots\n" * 200, encoding="utf-8")
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
        (repo / "CLAUDE.md").write_text("lots\n" * 200, encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")

        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True)

        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("rewrote `CLAUDE.md`", proc.stdout)
        self.assertIn("1 fixed", proc.stdout)
        rewritten = (repo / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(rewritten.startswith("@AGENTS.md"))
        self.assertLessEqual(len(rewritten.encode("utf-8")), 600)
        # A follow-up drift check now passes (D3 resolved).
        recheck = subprocess.run([sys.executable, str(DRIFT), str(repo)], text=True, capture_output=True)
        self.assertEqual(recheck.returncode, 0, recheck.stdout + recheck.stderr)

    def test_fix_reports_non_autofixable_drift_and_leaves_files_untouched(self):
        td, repo = self.copy_repo()
        self.addCleanup(td.cleanup)
        agents = CLEAN_AGENTS.replace("npm run test", "npm run nonexist")
        (repo / "AGENTS.md").write_text(agents, encoding="utf-8")
        (repo / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (repo / ".cursorrules").write_text("All agent instructions live in AGENTS.md.\n", encoding="utf-8")
        (repo / ".github" / "copilot-instructions.md").write_text("See AGENTS.md.\n", encoding="utf-8")

        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--fix", "--apply"], text=True, capture_output=True)

        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("needs manual attention", proc.stdout)
        self.assertIn("D1", proc.stdout)
        self.assertIn("nonexist", proc.stdout)
        self.assertIn("1 need manual attention", proc.stdout)
        # AGENTS.md is not modified by --fix for D1 command drift.
        self.assertEqual(agents, (repo / "AGENTS.md").read_text(encoding="utf-8"))

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
        (repo / "AGENTS.md").write_text(CLEAN_AGENTS + "\n# Toolchain\nUse Node 18 for development.\n", encoding="utf-8")
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
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--min-score", "101"], text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Score:", proc.stdout)


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


if __name__ == "__main__":
    unittest.main()
