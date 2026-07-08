import json
import hashlib
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "cli.js"
PKG_VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]


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
            self.assertEqual(manifest["version"], PKG_VERSION)
            self.assertEqual(len(manifest["installs"]), 1)
            self.assertEqual(manifest["installs"][0]["agent"], "claude")
            self.assertEqual(Path(manifest["installs"][0]["project"]).resolve(), project.resolve())
            self.assertFalse(manifest["installs"][0]["link"])

            update = self.run_cli(["update"], home, project)
            self.assertIn(f"Deploying ai-harness-doctor {PKG_VERSION}", update.stdout)
            self.assertIn("Update summary", update.stdout)
            self.assertIn(f"deployed {PKG_VERSION}", update.stdout)

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
        variants = [
            b"# Agent Guide\n\nKeep this intact.",
            b"# Agent Guide\n\nKeep this intact.\n",
            b"# Agent Guide\n\nKeep this intact.\n\n  \t",
        ]
        for original_agents_bytes in variants:
            with self.subTest(original=original_agents_bytes), tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
                home = Path(home_dir)
                repo = self.make_git_repo(Path(parent_dir))
                (repo / "AGENTS.md").write_bytes(original_agents_bytes)
                original_hash = hashlib.sha256(original_agents_bytes).hexdigest()
                self.run_cli(["guard", str(repo), "--apply"], home, repo)

                proc = self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)

                self.assertIn("Guard remove plan", proc.stdout)
                self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())
                self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
                self.assertFalse((repo / ".github" / "workflows" / "harness-checkup.yml").exists())
                agents_after_bytes = (repo / "AGENTS.md").read_bytes()
                agents_after = agents_after_bytes.decode("utf-8")
                self.assertNotIn("ai-harness-doctor:maintenance-contract:start", agents_after)
                self.assertIn("Keep this intact.", agents_after)
                self.assertEqual(hashlib.sha256(agents_after_bytes).hexdigest(), original_hash)

    def test_guard_provider_gitlab_installs_gitlab_ci(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            proc = self.run_cli(["guard", str(repo), "--apply", "--provider", "gitlab"], home, repo)
            self.assertIn("CI provider: gitlab", proc.stdout)
            self.assertTrue((repo / ".gitlab" / "harness-ci.yml").exists())
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            # remove cleans up the gitlab file too.
            self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)
            self.assertFalse((repo / ".gitlab" / "harness-ci.yml").exists())

    def test_guard_provider_codebase_installs_portable_script(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            proc = self.run_cli(["guard", str(repo), "--apply", "--provider", "codebase"], home, repo)
            self.assertIn("CI provider: codebase", proc.stdout)
            script = repo / ".harness-ci" / "harness-guard.sh"
            self.assertTrue(script.exists())
            self.assertTrue(os.access(script, os.X_OK))
            self.assertTrue((repo / ".harness-ci" / "README.md").exists())
            pipeline = repo / ".codebase" / "pipelines" / "harness-guard.yaml"
            self.assertTrue(pipeline.exists())
            pipeline_text = pipeline.read_text(encoding="utf-8")
            self.assertIn("trigger:", pipeline_text)
            self.assertIn("cron:", pipeline_text)
            self.assertIn("harness-guard.sh", pipeline_text)
            # The portable script honours the AI_HARNESS_DOCTOR_SKIP escape hatch.
            self.assertIn("AI_HARNESS_DOCTOR_SKIP", script.read_text(encoding="utf-8"))
            # remove cleans up the codebase files too.
            self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)
            self.assertFalse(script.exists())
            self.assertFalse(pipeline.exists())

    def test_guard_auto_detects_gitlab_from_ci_file(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            (repo / ".gitlab-ci.yml").write_text("stages: [test]\n", encoding="utf-8")
            proc = self.run_cli(["guard", str(repo)], home, repo)
            self.assertIn("CI provider: gitlab (auto-detected)", proc.stdout)

    def test_guard_rejects_unknown_provider(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            proc = self.run_cli_raw(["guard", str(repo), "--provider", "bogus"], home, repo)
            self.assertNotEqual(proc.returncode, 0)

    def test_forced_update_check_unreachable_registry_does_not_crash_help(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as project_dir:
            env = os.environ.copy()
            env["HOME"] = home_dir
            env.pop("AI_HARNESS_DOCTOR_NO_UPDATE_CHECK", None)
            env["AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK"] = "1"
            env["AI_HARNESS_DOCTOR_REGISTRY"] = "http://127.0.0.1:9/"

            started = time.monotonic()
            proc = subprocess.run(
                ["node", str(CLI), "help"],
                cwd=project_dir,
                env=env,
                text=True,
                capture_output=True,
                timeout=5,
            )
            elapsed = time.monotonic() - started

            self.assertEqual(proc.returncode, 0, proc.stderr)
            # The update check uses a 1.5s network timeout and unref'd handles, so
            # `help` must not block on an unreachable registry. Locally this returns
            # in well under 0.1s; the bound is kept generous (but far below the 5s
            # subprocess hard-timeout) to tolerate cold-start jitter on CI runners
            # while still catching a real hang/regression.
            self.assertLess(elapsed, 4.0)
            self.assertIn("ai-harness-doctor validate [...args]", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertNotIn("TypeError", proc.stderr)


    def test_help_lists_mcp_command(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as project_dir:
            home = Path(home_dir)
            proc = self.run_cli(["help"], home, Path(project_dir))
            self.assertIn("ai-harness-doctor mcp", proc.stdout)

    def test_mcp_command_starts_and_responds_to_initialize(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as project_dir:
            env = os.environ.copy()
            env["HOME"] = home_dir
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
            proc = subprocess.run(
                ["node", str(CLI), "mcp"],
                input=payload,
                cwd=project_dir,
                env=env,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            first = next(line for line in proc.stdout.splitlines() if line.strip())
            response = json.loads(first)
            self.assertEqual(response["id"], 1)
            self.assertEqual(response["result"]["serverInfo"]["name"], "ai-harness-doctor")


if __name__ == "__main__":
    unittest.main()
