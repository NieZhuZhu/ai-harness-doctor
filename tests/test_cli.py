import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "cli.js"


class CliInstallerTests(unittest.TestCase):
    def run_cli(self, args, home, cwd):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
        proc = subprocess.run(
            ["node", str(CLI), *args],
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc

    def run_cli_raw(self, args, home, cwd):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
        return subprocess.run(
            ["node", str(CLI), *args],
            cwd=str(cwd),
            env=env,
            text=True,
            capture_output=True,
        )

    def make_git_repo(self, parent, with_agents=True):
        repo = parent / "target"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True, text=True)
        if with_agents:
            (repo / "AGENTS.md").write_text("# Agent Guide\n\nKeep this intact.\n", encoding="utf-8")
        return repo

    def test_install_update_link_uninstall_manifest_flow(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            install = self.run_cli(["install", "--project"], home, project)
            self.assertIn("Install summary", install.stdout)

            manifest_path = home / ".ai-harness-doctor" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["version"], "0.1.0")
            self.assertEqual(len(manifest["installs"]), 1)
            self.assertEqual(manifest["installs"][0]["agent"], "claude")
            self.assertEqual(Path(manifest["installs"][0]["project"]).resolve(), project.resolve())
            self.assertFalse(manifest["installs"][0]["link"])

            update = self.run_cli(["update"], home, project)
            self.assertIn("Deploying ai-harness-doctor 0.1.0", update.stdout)
            self.assertIn("Update summary", update.stdout)
            self.assertIn("deployed 0.1.0", update.stdout)

            link = self.run_cli(["install", "--link", "--project"], home, project)
            self.assertIn("Linked install", link.stdout)
            skill_link = project / ".claude" / "skills" / "ai-harness-doctor"
            self.assertTrue(skill_link.is_symlink())
            self.assertEqual(skill_link.resolve(), ROOT)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["installs"]), 1)
            self.assertTrue(manifest["installs"][0]["link"])

            uninstall = self.run_cli(["uninstall", "--project"], home, project)
            self.assertIn("Uninstall summary", uninstall.stdout)
            self.assertFalse(skill_link.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["installs"], [])

    def test_guard_dry_run_prints_plan_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))

            proc = self.run_cli(["guard", str(repo)], home, repo)

            self.assertIn("Guard install plan", proc.stdout)
            self.assertIn("Mode: dry-run", proc.stdout)
            self.assertIn("harness-drift.yml", proc.stdout)
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())
            self.assertNotIn("ai-harness-doctor:maintenance-contract:start", (repo / "AGENTS.md").read_text(encoding="utf-8"))

    def test_guard_apply_installs_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))

            first = self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertIn("Applied", first.stdout)

            hook = repo / ".git" / "hooks" / "pre-commit"
            drift_workflow = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup_workflow = repo / ".github" / "workflows" / "harness-checkup.yml"
            agents = repo / "AGENTS.md"
            self.assertIn("# ai-harness-doctor:guard", hook.read_text(encoding="utf-8"))
            self.assertIn("npx -y ai-harness-doctor drift . --strict", drift_workflow.read_text(encoding="utf-8"))
            self.assertIn("🩺 Harness checkup: drift detected", checkup_workflow.read_text(encoding="utf-8"))
            self.assertEqual(agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1)

            second = self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertIn("No changes needed", second.stdout)
            self.assertEqual(agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1)

    def test_guard_without_agents_exits_1(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir), with_agents=False)

            proc = self.run_cli_raw(["guard", str(repo)], home, repo)

            self.assertEqual(proc.returncode, 1)
            self.assertIn("run the treat phase first", proc.stderr)

    def test_guard_preserves_foreign_pre_commit_while_installing_other_items(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            hook = repo / ".git" / "hooks" / "pre-commit"
            foreign = "#!/bin/sh\necho foreign\n"
            hook.write_text(foreign, encoding="utf-8")

            proc = self.run_cli(["guard", str(repo), "--apply"], home, repo)

            self.assertIn("manual-merge", proc.stdout)
            self.assertEqual(hook.read_text(encoding="utf-8"), foreign)
            self.assertTrue((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            self.assertTrue((repo / ".github" / "workflows" / "harness-checkup.yml").exists())
            self.assertIn("ai-harness-doctor:maintenance-contract:start", (repo / "AGENTS.md").read_text(encoding="utf-8"))

    def test_guard_remove_apply_restores_installed_files(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            original_agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
            self.run_cli(["guard", str(repo), "--apply"], home, repo)

            proc = self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)

            self.assertIn("Guard remove plan", proc.stdout)
            self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            self.assertFalse((repo / ".github" / "workflows" / "harness-checkup.yml").exists())
            agents_after = (repo / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("ai-harness-doctor:maintenance-contract:start", agents_after)
            self.assertIn("Keep this intact.", agents_after)
            self.assertEqual(agents_after.strip(), original_agents.strip())


if __name__ == "__main__":
    unittest.main()
