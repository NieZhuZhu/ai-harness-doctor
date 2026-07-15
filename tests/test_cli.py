import hashlib
import json
import os
import subprocess
import unittest
from pathlib import Path

from tmp_support import ResilientTemporaryDirectory

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
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
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
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))

            proc = self.run_cli(["guard", str(repo)], home, repo)

            self.assertIn("Guard install plan", proc.stdout)
            self.assertIn("Mode: dry-run", proc.stdout)
            self.assertIn("harness-drift.yml", proc.stdout)
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())
            self.assertNotIn(
                "ai-harness-doctor:maintenance-contract:start", (repo / "AGENTS.md").read_text(encoding="utf-8")
            )

    def test_guard_apply_installs_and_is_idempotent(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))

            first = self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertIn("Applied", first.stdout)

            hook = repo / ".git" / "hooks" / "pre-commit"
            drift_workflow = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup_workflow = repo / ".github" / "workflows" / "harness-checkup.yml"
            agents = repo / "AGENTS.md"
            self.assertIn("# ai-harness-doctor:guard", hook.read_text(encoding="utf-8"))
            workflow_text = drift_workflow.read_text(encoding="utf-8")
            checkup_text = checkup_workflow.read_text(encoding="utf-8")
            self.assertEqual(
                workflow_text,
                (ROOT / "assets" / "guard" / "harness-drift.yml").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                checkup_text,
                (ROOT / "assets" / "guard" / "harness-checkup.yml").read_text(encoding="utf-8"),
            )
            self.assertIn("npx -y ai-harness-doctor@latest drift . --strict", workflow_text)
            self.assertIn("npx -y ai-harness-doctor@latest review", workflow_text)
            scan_gate = (
                "scan . --fail-on-security --fail-on-gaps "
                "--fail-on-semantic --fail-on-conflicts"
            )
            self.assertIn(scan_gate, workflow_text)
            self.assertIn("SCAN_BASELINE: .ai-harness-doctor/scan-baseline.json", workflow_text)
            self.assertIn("- .ai-harness-doctor/scan-baseline.json", workflow_text)
            self.assertIn(scan_gate, checkup_text)
            self.assertIn("steps.scan.outputs.status", checkup_text)
            self.assertNotIn('npx -y ai-harness-doctor@latest scan . --write-baseline', workflow_text + checkup_text)
            self.assertNotIn("python3 scripts/", workflow_text)
            self.assertIn("🩺 Harness checkup: issues detected", checkup_text)
            self.assertEqual(
                agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1
            )

            second = self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertIn("No changes needed", second.stdout)
            self.assertEqual(
                agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1
            )

    def test_guard_consumer_repo_can_build_review_through_public_cli(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertFalse((repo / "scripts").exists())
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            drift = subprocess.run(
                ["node", str(CLI), "drift", str(repo), "--json"],
                cwd=str(repo),
                env=env,
                text=True,
                capture_output=True,
            )
            report_path = repo / "drift-report.json"
            report_path.write_text(drift.stdout, encoding="utf-8")

            review = subprocess.run(
                [
                    "node",
                    str(CLI),
                    "review",
                    "--report",
                    str(report_path),
                    "--default-path",
                    "AGENTS.md",
                ],
                cwd=str(repo),
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(review.returncode, 0, review.stderr)
            payload = json.loads(review.stdout)
            self.assertIn("body", payload)
            self.assertIn("comments", payload)
            self.assertIn("ai-harness-doctor:pr-review", payload["body"])

    def test_guard_without_agents_exits_1(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir), with_agents=False)

            proc = self.run_cli_raw(["guard", str(repo)], home, repo)

            self.assertEqual(proc.returncode, 1)
            self.assertIn("run the treat phase first", proc.stderr)

    def test_guard_preserves_foreign_pre_commit_while_installing_other_items(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
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
            self.assertIn(
                "ai-harness-doctor:maintenance-contract:start", (repo / "AGENTS.md").read_text(encoding="utf-8")
            )

    def test_guard_remove_apply_restores_installed_files(self):
        variants = [
            b"# Agent Guide\n\nKeep this intact.",
            b"# Agent Guide\n\nKeep this intact.\n",
            b"# Agent Guide\n\nKeep this intact.\n\n  \t",
        ]
        for original_agents_bytes in variants:
            with (
                self.subTest(original=original_agents_bytes),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as parent_dir,
            ):
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

    def test_guard_remove_strips_block_and_preserves_user_appended_hook_lines(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)

            hook = repo / ".git" / "hooks" / "pre-commit"
            self.assertIn("# ai-harness-doctor:guard", hook.read_text(encoding="utf-8"))
            user_line = "\n# my own hook line\necho custom-check\n"
            hook.write_text(hook.read_text(encoding="utf-8") + user_line, encoding="utf-8")

            proc = self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)

            self.assertTrue(hook.exists())
            hook_after = hook.read_text(encoding="utf-8")
            self.assertIn("echo custom-check", hook_after)
            self.assertNotIn("# ai-harness-doctor:guard", hook_after)
            self.assertIn("strip", proc.stdout)

    def test_guard_remove_does_not_delete_user_edited_workflow(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)

            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            edited = drift.read_text(encoding="utf-8") + "\n# user tweak\n"
            drift.write_text(edited, encoding="utf-8")

            proc = self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)

            self.assertTrue(drift.exists())
            self.assertEqual(drift.read_text(encoding="utf-8"), edited)
            self.assertIn("skip", proc.stdout)

    def test_guard_reinstall_does_not_overwrite_user_edited_workflow(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)

            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            edited = drift.read_text(encoding="utf-8").replace("# ai-harness-doctor:guard\n", "") + "\n# user tweak\n"
            drift.write_text(edited, encoding="utf-8")

            proc = self.run_cli(["guard", str(repo), "--apply"], home, repo)

            self.assertIn("manual-merge", proc.stdout)
            self.assertEqual(drift.read_text(encoding="utf-8"), edited)

    def test_guard_apply_refuses_symlinked_agents_file(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            base = Path(parent_dir)
            repo = self.make_git_repo(base, with_agents=False)
            outside = base / "outside-agents.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            try:
                (repo / "AGENTS.md").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")
            before = outside.read_bytes()

            proc = self.run_cli_raw(["guard", str(repo), "--apply"], home, repo)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(outside.read_bytes(), before)
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())

    def test_guard_apply_refuses_symlinked_managed_workflow(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            base = Path(parent_dir)
            repo = self.make_git_repo(base)
            workflow = repo / ".github" / "workflows" / "harness-drift.yml"
            workflow.parent.mkdir(parents=True)
            outside = base / "outside-workflow.yml"
            outside.write_text("# ai-harness-doctor:guard\noutside\n", encoding="utf-8")
            try:
                workflow.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")
            before = outside.read_bytes()

            proc = self.run_cli_raw(["guard", str(repo), "--apply"], home, repo)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(outside.read_bytes(), before)
            self.assertTrue(workflow.is_symlink())

    def test_guard_remove_refuses_symlinked_managed_workflow(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            base = Path(parent_dir)
            repo = self.make_git_repo(base)
            self.run_cli(["guard", str(repo), "--apply"], home, repo)
            workflow = repo / ".github" / "workflows" / "harness-drift.yml"
            installed = workflow.read_bytes()
            workflow.unlink()
            outside = base / "outside-workflow.yml"
            outside.write_bytes(installed)
            try:
                workflow.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")

            proc = self.run_cli_raw(["guard", str(repo), "--remove", "--apply"], home, repo)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(outside.read_bytes(), installed)
            self.assertTrue(workflow.is_symlink())

    def test_guard_provider_gitlab_installs_gitlab_ci(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            proc = self.run_cli(["guard", str(repo), "--apply", "--provider", "gitlab"], home, repo)
            self.assertIn("CI provider: gitlab", proc.stdout)
            pipeline = repo / ".gitlab" / "harness-ci.yml"
            self.assertTrue(pipeline.exists())
            pipeline_text = pipeline.read_text(encoding="utf-8")
            self.assertIn("--fail-on-security", pipeline_text)
            self.assertIn("--fail-on-conflicts", pipeline_text)
            self.assertIn(".ai-harness-doctor/scan-baseline.json", pipeline_text)
            self.assertNotIn("scan . --write-baseline", pipeline_text)
            self.assertFalse((repo / ".github" / "workflows" / "harness-drift.yml").exists())
            # remove cleans up the gitlab file too.
            self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)
            self.assertFalse(pipeline.exists())

    def test_guard_provider_codebase_installs_portable_script(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
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
            script_text = script.read_text(encoding="utf-8")
            self.assertIn("AI_HARNESS_DOCTOR_SKIP", script_text)
            self.assertIn("run_scan_gate", script_text)
            self.assertIn("--fail-on-conflicts", script_text)
            self.assertIn("--fail-on-security", script_text)
            self.assertIn(".ai-harness-doctor/scan-baseline.json", script_text)
            self.assertNotIn("run scan . --write-baseline", script_text)
            # remove cleans up the codebase files too.
            self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)
            self.assertFalse(script.exists())
            self.assertFalse(pipeline.exists())

    def test_guard_auto_detects_gitlab_from_ci_file(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            (repo / ".gitlab-ci.yml").write_text("stages: [test]\n", encoding="utf-8")
            proc = self.run_cli(["guard", str(repo)], home, repo)
            self.assertIn("CI provider: gitlab (auto-detected)", proc.stdout)

    def test_guard_rejects_unknown_provider(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            proc = self.run_cli_raw(["guard", str(repo), "--provider", "bogus"], home, repo)
            self.assertNotEqual(proc.returncode, 0)

    def test_forced_update_check_unreachable_registry_does_not_crash_help(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            env = os.environ.copy()
            env["HOME"] = home_dir
            env.pop("AI_HARNESS_DOCTOR_NO_UPDATE_CHECK", None)
            env["AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK"] = "1"
            env["AI_HARNESS_DOCTOR_REGISTRY"] = "http://127.0.0.1:9/"

            # The update check uses a bounded network timeout and unref'd handles,
            # so `help` must never block on an unreachable registry. A regression
            # that drops the timeout/unref would hang until the hard timeout below
            # fires — we turn that into a clear failure. We deliberately do NOT
            # assert a tight wall-clock bound: that made the test flaky on loaded
            # CI runners (cold-start jitter could brush a sub-4s limit even with
            # no real hang). The generous timeout still catches a genuine hang
            # while tolerating jitter, so the check is deterministic.
            try:
                proc = subprocess.run(
                    ["node", str(CLI), "help"],
                    cwd=project_dir,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                self.fail(
                    "`help` blocked on an unreachable registry; the update check "
                    "must use a bounded network timeout with unref'd handles."
                )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("ai-harness-doctor validate [...args]", proc.stdout)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertNotIn("TypeError", proc.stderr)

    def test_help_lists_mcp_command(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            proc = self.run_cli(["help"], home, Path(project_dir))
            self.assertIn("ai-harness-doctor mcp", proc.stdout)

    def test_mcp_command_starts_and_responds_to_initialize(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
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
