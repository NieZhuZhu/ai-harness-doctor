import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
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

    def run_cli_raw_with_env(self, args, home, cwd, extra_env):
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
        env.update(extra_env)
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
            self.assertIn("unchanged", update.stdout)

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

    def test_explain_cli_and_claude_command_install_lifecycle(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "AGENTS.md").write_text("Use npm.\n", encoding="utf-8")
            (project / "packages" / "api").mkdir(parents=True)
            (project / "packages" / "api" / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")

            explain_proc = self.run_cli(
                ["explain", str(project), "packages/api/src/future.py", "--json"],
                home,
                project,
            )
            report = json.loads(explain_proc.stdout)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["effective_scope"], "packages/api")

            self.run_cli(["install", "--project"], home, project)
            command = project / ".claude" / "commands" / "harness-explain.md"
            self.assertTrue(command.is_file())
            self.assertIn("read-only", command.read_text(encoding="utf-8"))
            command.unlink()
            self.run_cli(["update"], home, project)
            self.assertTrue(command.is_file())
            self.run_cli(["uninstall", "--project"], home, project)
            self.assertFalse(command.exists())

    def test_install_refuses_malformed_manifest_without_overwriting_it(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            manifest = home / ".ai-harness-doctor" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            original = b"{broken\n"
            manifest.write_bytes(original)

            proc = self.run_cli_raw(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("manifest", proc.stderr.lower())
            self.assertIn("back up", proc.stderr.lower())
            self.assertEqual(manifest.read_bytes(), original)
            self.assertFalse((project / ".cursor").exists())

    def test_all_installer_commands_preserve_malformed_manifest(self):
        for args in (
            ["install", "--agent", "cursor", "--project"],
            ["update"],
            ["uninstall", "--agent", "cursor", "--project"],
        ):
            with (
                self.subTest(command=args[0]),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as project_dir,
            ):
                home = Path(home_dir)
                project = Path(project_dir)
                (project / "package.json").write_text("{}\n", encoding="utf-8")
                manifest = home / ".ai-harness-doctor" / "manifest.json"
                manifest.parent.mkdir(parents=True)
                original = b"{broken\n"
                manifest.write_bytes(original)

                proc = self.run_cli_raw(args, home, project)

                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("manifest", proc.stderr.lower())
                self.assertEqual(manifest.read_bytes(), original)

    def test_installer_refuses_invalid_or_future_manifest_schema(self):
        payloads = (
            {"schemaVersion": 2, "version": PKG_VERSION, "lastUpdateCheck": 0, "installs": {}},
            {"schemaVersion": 999, "version": PKG_VERSION, "lastUpdateCheck": 0, "installs": []},
        )
        for payload in payloads:
            with (
                self.subTest(payload=payload),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as project_dir,
            ):
                home = Path(home_dir)
                project = Path(project_dir)
                (project / "package.json").write_text("{}\n", encoding="utf-8")
                manifest = home / ".ai-harness-doctor" / "manifest.json"
                manifest.parent.mkdir(parents=True)
                original = (json.dumps(payload) + "\n").encode()
                manifest.write_bytes(original)

                proc = self.run_cli_raw(
                    ["install", "--agent", "cursor", "--project"],
                    home,
                    project,
                )

                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("manifest", proc.stderr.lower())
                self.assertEqual(manifest.read_bytes(), original)

    def test_install_refuses_symlinked_manifest_directory(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as project_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            project = Path(project_dir)
            outside = Path(outside_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            try:
                (home / ".ai-harness-doctor").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")

            proc = self.run_cli_raw(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((project / ".cursor").exists())

    def test_install_refuses_symlinked_manifest_file(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as project_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            project = Path(project_dir)
            outside = Path(outside_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            state = home / ".ai-harness-doctor"
            state.mkdir()
            target = outside / "manifest.json"
            original = b'{"outside": true}\n'
            target.write_bytes(original)
            try:
                (state / "manifest.json").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")

            proc = self.run_cli_raw(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(target.read_bytes(), original)
            self.assertFalse((project / ".cursor").exists())

    def test_update_nudge_skips_malformed_manifest_without_overwriting_it(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            manifest = home / ".ai-harness-doctor" / "manifest.json"
            manifest.parent.mkdir(parents=True)
            original = b"{broken\n"
            manifest.write_bytes(original)

            proc = self.run_cli_raw_with_env(
                ["doctor", "--json"],
                home,
                project,
                {
                    "AI_HARNESS_DOCTOR_NO_UPDATE_CHECK": "0",
                    "AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK": "1",
                },
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])
            self.assertEqual(manifest.read_bytes(), original)

    def test_update_nudge_uses_separate_cache_without_rewriting_manifest(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            state = home / ".ai-harness-doctor"
            manifest = state / "manifest.json"
            before = manifest.read_bytes()

            proc = self.run_cli_raw_with_env(
                ["doctor", "--json"],
                home,
                project,
                {
                    "AI_HARNESS_DOCTOR_NO_UPDATE_CHECK": "0",
                    "AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK": "1",
                    "AI_HARNESS_DOCTOR_REGISTRY": "http://127.0.0.1:9/",
                },
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])
            self.assertEqual(manifest.read_bytes(), before)
            cache = json.loads((state / "update-check.json").read_text(encoding="utf-8"))
            self.assertIsInstance(cache["lastUpdateCheck"], (int, float))

    def test_update_nudge_skips_while_installer_lock_exists(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            state = home / ".ai-harness-doctor"
            lock = state / "installer.lock"
            lock.mkdir(parents=True)
            (lock / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "token": "test-owner"}) + "\n",
                encoding="utf-8",
            )

            proc = self.run_cli_raw_with_env(
                ["help"],
                home,
                project,
                {
                    "AI_HARNESS_DOCTOR_NO_UPDATE_CHECK": "0",
                    "AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK": "1",
                    "AI_HARNESS_DOCTOR_REGISTRY": "http://127.0.0.1:9/",
                },
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse((state / "update-check.json").exists())
            self.assertTrue(lock.is_dir())

    def test_failed_atomic_manifest_replace_preserves_previous_state(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            manifest = home / ".ai-harness-doctor" / "manifest.json"
            original = manifest.read_bytes()
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            payload = project / ".ai-harness-doctor" / "payload" / "SKILL.md"
            adapter.chmod(0o600)
            manifest.chmod(0o644)
            adapter_before = adapter.read_bytes()
            payload_before = payload.read_bytes()
            adapter_mode = adapter.stat().st_mode & 0o777
            manifest_mode = manifest.stat().st_mode & 0o777

            proc = self.run_cli_raw_with_env(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
                {"AI_HARNESS_DOCTOR_TEST_MANIFEST_WRITE_FAILURE": "1"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("manifest", proc.stderr.lower())
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(adapter.read_bytes(), adapter_before)
            self.assertEqual(payload.read_bytes(), payload_before)
            self.assertEqual(adapter.stat().st_mode & 0o777, adapter_mode)
            self.assertEqual(manifest.stat().st_mode & 0o777, manifest_mode)
            self.assertEqual(
                [path for path in manifest.parent.iterdir() if path.name.startswith(".manifest-")],
                [],
            )
            self.assertFalse((manifest.parent / "transactions").exists())
            self.assertFalse((manifest.parent / "installer.lock").exists())

    def test_failed_first_install_rolls_back_files_and_absent_manifest(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            proc = self.run_cli_raw_with_env(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
                {"AI_HARNESS_DOCTOR_TEST_MANIFEST_WRITE_FAILURE": "1"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((project / ".ai-harness-doctor").exists())
            state = home / ".ai-harness-doctor"
            self.assertFalse((state / "manifest.json").exists())
            self.assertFalse((state / "transactions").exists())
            self.assertFalse((state / "installer.lock").exists())

    def test_failed_update_restores_all_managed_bytes(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            manifest = home / ".ai-harness-doctor" / "manifest.json"
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            payload = project / ".ai-harness-doctor" / "payload" / "SKILL.md"
            adapter.unlink()
            payload.unlink()
            manifest_before = manifest.read_bytes()

            proc = self.run_cli_raw_with_env(
                ["update"],
                home,
                project,
                {"AI_HARNESS_DOCTOR_TEST_MANIFEST_WRITE_FAILURE": "1"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(manifest.read_bytes(), manifest_before)
            self.assertFalse(adapter.exists())
            self.assertFalse(payload.exists())
            self.assertFalse((manifest.parent / "transactions").exists())
            self.assertFalse((manifest.parent / "installer.lock").exists())

    def test_fresh_process_recovers_interrupted_installer_transactions(self):
        phases = ("after-mutation", "before-manifest", "after-manifest")
        for phase in phases:
            with (
                self.subTest(phase=phase),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as project_dir,
            ):
                home = Path(home_dir)
                project = Path(project_dir)
                (project / "package.json").write_text("{}\n", encoding="utf-8")
                crash = self.run_cli_raw_with_env(
                    ["install", "--agent", "cursor", "--project"],
                    home,
                    project,
                    {"AI_HARNESS_DOCTOR_TEST_TRANSACTION_CRASH": phase},
                )
                self.assertEqual(crash.returncode, 86, crash.stderr)
                state = home / ".ai-harness-doctor"
                self.assertTrue((state / "transactions").is_dir())

                if phase == "after-manifest":
                    # Manifest commit won; startup recovery keeps installed files
                    # and only retires the completed journal.
                    recovered = self.run_cli(["update"], home, project)
                    self.assertIn("Update summary", recovered.stdout)
                    self.assertTrue((project / ".cursor" / "commands" / "harness-scan.md").is_file())
                    self.assertEqual(
                        len(json.loads((state / "manifest.json").read_text(encoding="utf-8"))["installs"]),
                        1,
                    )
                else:
                    # No manifest commit: startup recovery restores pre-install
                    # absence before the requested uninstall observes empty state.
                    self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)
                    self.assertFalse((project / ".cursor").exists())
                    self.assertFalse((project / ".ai-harness-doctor").exists())
                    self.assertEqual(
                        json.loads((state / "manifest.json").read_text(encoding="utf-8"))["installs"],
                        [],
                    )
                self.assertFalse((state / "transactions").exists())
                self.assertFalse((state / "installer.lock").exists())

    def test_recovery_refuses_malformed_or_escaping_transaction_journal(self):
        payloads = (
            b"{broken\n",
            json.dumps(
                {
                    "schemaVersion": 1,
                    "id": "tx",
                    "command": "install",
                    "roots": ["/"],
                    "originalManifest": {"kind": "absent"},
                    "nextManifestDigest": None,
                    "snapshots": [
                        {
                            "path": "/tmp/outside",
                            "prior": {"kind": "absent"},
                            "expected": {"kind": "absent"},
                        }
                    ],
                }
            ).encode(),
        )
        for payload in payloads:
            with (
                self.subTest(payload=payload[:20]),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as project_dir,
            ):
                home = Path(home_dir)
                project = Path(project_dir)
                (project / "package.json").write_text("{}\n", encoding="utf-8")
                transaction = home / ".ai-harness-doctor" / "transactions" / "tx"
                transaction.mkdir(parents=True)
                journal = transaction / "journal.json"
                journal.write_bytes(payload)
                original = journal.read_bytes()

                proc = self.run_cli_raw(
                    ["install", "--agent", "cursor", "--project"],
                    home,
                    project,
                )

                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("transaction", proc.stderr.lower())
                self.assertEqual(journal.read_bytes(), original)
                self.assertFalse((project / ".cursor").exists())
                self.assertFalse((project / ".ai-harness-doctor").exists())

    def test_recovery_cleans_up_journal_less_transaction_directory(self):
        # Plan 044: a process killed between beginInstallerTransaction's
        # fs.mkdirSync(dir) and writeTransactionJournal leaves a transaction
        # directory with no journal.json. Recovery runs before every installer
        # command, so it must treat that as an abandoned artifact and clean it
        # up rather than throwing ENOENT and bricking install/update/uninstall.
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as project_dir,
        ):
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            transactions = home / ".ai-harness-doctor" / "transactions"
            stray = transactions / "1700000000000-123-abcdef"
            stray.mkdir(parents=True)
            # A stray manifest backup with still no journal.json — exactly the
            # shape of a crash between mkdir and journal write.
            (stray / "manifest-original.json").write_text("{}\n", encoding="utf-8")

            result = self.run_cli(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertIn("Install summary", result.stdout)
            self.assertTrue((project / ".cursor" / "commands" / "harness-scan.md").is_file())
            # The journal-less directory was cleaned up; the completed install
            # also retires its own transaction, so the dir is empty or gone.
            self.assertFalse(stray.exists())
            self.assertFalse((home / ".ai-harness-doctor" / "installer.lock").exists())

    def test_recovery_refuses_symlinked_transaction_directory(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as project_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            project = Path(project_dir)
            outside = Path(outside_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            transactions = home / ".ai-harness-doctor" / "transactions"
            transactions.mkdir(parents=True)
            (outside / "journal.json").write_text("{}\n", encoding="utf-8")
            try:
                (transactions / "tx").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")

            proc = self.run_cli_raw(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("transaction", proc.stderr.lower())
            self.assertEqual((outside / "journal.json").read_text(encoding="utf-8"), "{}\n")
            self.assertFalse((project / ".cursor").exists())

    def test_recovery_refuses_to_overwrite_external_post_crash_edit(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            crash = self.run_cli_raw_with_env(
                ["install", "--agent", "cursor", "--project"],
                home,
                project,
                {"AI_HARNESS_DOCTOR_TEST_TRANSACTION_CRASH": "before-manifest"},
            )
            self.assertEqual(crash.returncode, 86, crash.stderr)
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            adapter.write_text("external edit after crash\n", encoding="utf-8")

            recovery = self.run_cli_raw(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("externally modified", recovery.stderr)
            self.assertEqual(adapter.read_text(encoding="utf-8"), "external edit after crash\n")
            self.assertTrue((home / ".ai-harness-doctor" / "transactions").is_dir())
            self.assertFalse((home / ".ai-harness-doctor" / "installer.lock").exists())

    def test_recovery_refuses_tampered_transaction_backup(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            crash = self.run_cli_raw_with_env(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
                {"AI_HARNESS_DOCTOR_TEST_TRANSACTION_CRASH": "before-manifest"},
            )
            self.assertEqual(crash.returncode, 86, crash.stderr)
            transactions = home / ".ai-harness-doctor" / "transactions"
            transaction = next(transactions.iterdir())
            backup = next(path for path in transaction.iterdir() if path.name.startswith("backup-") and path.is_file())
            backup.write_bytes(backup.read_bytes() + b"tampered")
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            adapter_before = adapter.exists()

            recovery = self.run_cli_raw(
                ["update"],
                home,
                project,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("backup digest does not match", recovery.stderr)
            self.assertEqual(adapter.exists(), adapter_before)
            self.assertTrue(transaction.is_dir())
            self.assertFalse((home / ".ai-harness-doctor" / "installer.lock").exists())

    def test_concurrent_installer_fails_without_recovering_live_transaction(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            env["AI_HARNESS_DOCTOR_TEST_TRANSACTION_PAUSE"] = "after-mutation"
            first = subprocess.Popen(
                ["node", str(CLI), "install", "--agent", "cursor", "--project"],
                cwd=project,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            lock = home / ".ai-harness-doctor" / "installer.lock"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not lock.exists():
                time.sleep(0.05)
            self.assertTrue(lock.is_dir())

            second = self.run_cli_raw(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("another installer command is active", second.stderr)
            self.assertTrue((home / ".ai-harness-doctor" / "transactions").is_dir())
            first.send_signal(signal.SIGTERM)
            first.communicate(timeout=10)

            recovered = self.run_cli(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
            )
            self.assertIn("Uninstall summary", recovered.stdout)
            self.assertFalse((project / ".cursor").exists())
            self.assertFalse((home / ".ai-harness-doctor" / "installer.lock").exists())
            self.assertFalse((home / ".ai-harness-doctor" / "transactions").exists())

    def test_installer_refuses_malformed_or_symlinked_lock_state(self):
        cases = ("malformed", "symlink")
        for case in cases:
            with (
                self.subTest(case=case),
                ResilientTemporaryDirectory() as home_dir,
                ResilientTemporaryDirectory() as project_dir,
                ResilientTemporaryDirectory() as outside_dir,
            ):
                home = Path(home_dir)
                project = Path(project_dir)
                outside = Path(outside_dir)
                (project / "package.json").write_text("{}\n", encoding="utf-8")
                state = home / ".ai-harness-doctor"
                state.mkdir()
                lock = state / "installer.lock"
                if case == "malformed":
                    lock.mkdir()
                    owner = lock / "owner.json"
                    owner.write_text("{broken\n", encoding="utf-8")
                    evidence = owner
                else:
                    outside_lock = outside / "lock"
                    outside_lock.mkdir()
                    (outside_lock / "owner.json").write_text(
                        json.dumps({"pid": 99999999, "token": "outside"}) + "\n",
                        encoding="utf-8",
                    )
                    try:
                        lock.symlink_to(outside_lock, target_is_directory=True)
                    except (OSError, NotImplementedError):
                        self.skipTest("directory symlinks unsupported on this platform")
                    evidence = outside_lock / "owner.json"
                before = evidence.read_bytes()

                proc = self.run_cli_raw(
                    ["install", "--agent", "cursor", "--project"],
                    home,
                    project,
                )

                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("lock", proc.stderr.lower())
                self.assertEqual(evidence.read_bytes(), before)
                self.assertFalse((project / ".cursor").exists())

    def test_project_adapter_install_preserves_repository_harness_state(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            state = project / ".ai-harness-doctor"
            rules = state / "rules"
            rules.mkdir(parents=True)
            baseline = state / "scan-baseline.json"
            rule = rules / "custom.py"
            unrelated = state / "owner-notes.md"
            baseline.write_text('{"version": 1, "findings": []}\n', encoding="utf-8")
            rule.write_text("def check(root, context): return []\n", encoding="utf-8")
            unrelated.write_text("keep me\n", encoding="utf-8")
            expected = {path: path.read_bytes() for path in (baseline, rule, unrelated)}

            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            self.run_cli(["update"], home, project)
            self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)

            for path, content in expected.items():
                self.assertEqual(path.read_bytes(), content, f"installer changed user-owned {path}")
            self.assertFalse((state / "payload").exists())

    def test_cursor_install_tracks_implicit_target_root_across_working_directories(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as first_dir,
            ResilientTemporaryDirectory() as second_dir,
        ):
            home = Path(home_dir)
            first = Path(first_dir)
            second = Path(second_dir)
            for project in (first, second):
                subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
                (project / "package.json").write_text("{}\n", encoding="utf-8")

            self.run_cli(["install", "--agent", "cursor"], home, first)
            adapter = first / ".cursor" / "commands" / "harness-scan.md"
            self.assertTrue(adapter.is_file())
            manifest_path = home / ".ai-harness-doctor" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cursor = next(record for record in manifest["installs"] if record["agent"] == "cursor")
            self.assertEqual(Path(cursor["targetRoot"]).resolve(), first.resolve())

            adapter.unlink()
            self.run_cli(["update"], home, second)
            self.assertTrue(adapter.is_file())
            self.assertFalse((second / ".cursor").exists())

            self.run_cli(["uninstall", "--agent", "cursor"], home, second)
            self.assertTrue(adapter.is_file())
            self.run_cli(["uninstall", "--agent", "cursor"], home, first)
            self.assertFalse(adapter.exists())

    def test_shared_payload_mode_switch_updates_all_implicit_cursor_roots(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as first_dir,
            ResilientTemporaryDirectory() as second_dir,
        ):
            home = Path(home_dir)
            first = Path(first_dir)
            second = Path(second_dir)
            for project in (first, second):
                subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
                (project / "package.json").write_text("{}\n", encoding="utf-8")

            self.run_cli(["install", "--agent", "cursor"], home, first)
            self.run_cli(["install", "--agent", "cursor"], home, second)
            first_adapter = first / ".cursor" / "commands" / "harness-scan.md"
            second_adapter = second / ".cursor" / "commands" / "harness-scan.md"
            payload = home / ".ai-harness-doctor" / "payload"
            self.assertIn(str(payload), first_adapter.read_text(encoding="utf-8"))
            self.assertIn(str(payload), second_adapter.read_text(encoding="utf-8"))

            self.run_cli(["install", "--agent", "cursor", "--link"], home, second)

            self.assertTrue(payload.is_symlink())
            self.assertIn(str(ROOT), first_adapter.read_text(encoding="utf-8"))
            self.assertIn(str(ROOT), second_adapter.read_text(encoding="utf-8"))
            manifest = json.loads(
                (home / ".ai-harness-doctor" / "manifest.json").read_text(encoding="utf-8")
            )
            cursor_records = [record for record in manifest["installs"] if record["agent"] == "cursor"]
            self.assertEqual(len(cursor_records), 2)
            self.assertTrue(all(record["link"] for record in cursor_records))

    def test_install_preserves_unowned_adapter_name_collision(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            adapter.parent.mkdir(parents=True)
            adapter.write_text("user-owned adapter\n", encoding="utf-8")
            before = adapter.read_bytes()

            install = self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            self.assertIn("manual-merge", install.stdout)
            self.assertEqual(adapter.read_bytes(), before)

            self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)
            self.assertEqual(adapter.read_bytes(), before)

    def test_install_does_not_adopt_unowned_payload_link_with_matching_target(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            payload = home / ".ai-harness-doctor" / "payload"
            payload.parent.mkdir(parents=True)
            try:
                payload.symlink_to(ROOT, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")

            install = self.run_cli(["install", "--agent", "codex", "--link"], home, project)

            self.assertIn("manual-merge", install.stdout)
            manifest = json.loads(
                (home / ".ai-harness-doctor" / "manifest.json").read_text(encoding="utf-8")
            )
            codex = next(record for record in manifest["installs"] if record["agent"] == "codex")
            self.assertNotIn(str(payload), [output["path"] for output in codex["outputs"]])

            self.run_cli(["uninstall", "--agent", "codex"], home, project)
            self.assertTrue(payload.is_symlink())
            self.assertEqual(payload.resolve(), ROOT)

    def test_project_adapter_install_refuses_symlinked_parent_directory(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            base = Path(parent_dir)
            project = base / "project"
            outside = base / "outside-cursor"
            project.mkdir()
            outside.mkdir()
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            try:
                (project / ".cursor").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")

            proc = self.run_cli_raw(["install", "--agent", "cursor", "--project"], home, project)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("symlink", proc.stderr.lower())
            self.assertEqual(list(outside.iterdir()), [])

    def test_update_and_uninstall_preserve_edited_managed_adapter(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            adapter.write_text(adapter.read_text(encoding="utf-8") + "\nuser extension\n", encoding="utf-8")
            edited = adapter.read_bytes()

            update = self.run_cli(["update"], home, project)
            self.assertIn("modified-preserved", update.stdout)
            self.assertEqual(adapter.read_bytes(), edited)

            uninstall = self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)
            self.assertIn("modified-preserved", uninstall.stdout)
            self.assertEqual(adapter.read_bytes(), edited)
            manifest = json.loads(
                (home / ".ai-harness-doctor" / "manifest.json").read_text(encoding="utf-8")
            )
            cursor = next(record for record in manifest["installs"] if record["agent"] == "cursor")
            self.assertTrue(cursor["orphaned"])
            self.assertEqual(
                [Path(output["path"]).resolve() for output in cursor["outputs"]],
                [adapter.resolve()],
            )
            update_again = self.run_cli(["update"], home, project)
            self.assertIn("orphaned-preserved", update_again.stdout)
            self.assertEqual(adapter.read_bytes(), edited)

    def test_uninstall_retires_ownership_for_already_missing_managed_file(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            adapter = project / ".cursor" / "commands" / "harness-scan.md"
            adapter.unlink()

            uninstall = self.run_cli(
                ["uninstall", "--agent", "cursor", "--project"],
                home,
                project,
            )

            self.assertIn("already-absent", uninstall.stdout)
            manifest = json.loads(
                (home / ".ai-harness-doctor" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["installs"], [])

    def test_manifest_cannot_claim_and_delete_external_file(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            external = home.parent / "external-owned-by-user.txt"
            external.write_text("do not delete\n", encoding="utf-8")
            manifest_path = home / ".ai-harness-doctor" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cursor = next(record for record in manifest["installs"] if record["agent"] == "cursor")
            cursor["outputs"].append(
                {
                    "path": str(external),
                    "kind": "file",
                    "digest": hashlib.sha256(external.read_bytes()).hexdigest(),
                }
            )
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

            self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)

            self.assertEqual(external.read_text(encoding="utf-8"), "do not delete\n")

    def test_uninstall_one_agent_keeps_shared_project_payload(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")

            self.run_cli(["install", "--agent", "all", "--project"], home, project)
            payload = project / ".ai-harness-doctor" / "payload"
            self.assertTrue((payload / "SKILL.md").is_file())

            self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)
            self.assertTrue((payload / "SKILL.md").is_file())

            self.run_cli(["uninstall", "--agent", "codex", "--project"], home, project)
            self.run_cli(["uninstall", "--agent", "gemini", "--project"], home, project)
            self.assertFalse(payload.exists())

    def test_uninstall_keeps_unowned_empty_adapter_parent_directories(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            command_dir = project / ".cursor" / "commands"

            self.run_cli(["install", "--agent", "cursor", "--project"], home, project)
            self.run_cli(["uninstall", "--agent", "cursor", "--project"], home, project)

            self.assertTrue(command_dir.is_dir())

    def test_shared_payload_mode_switch_updates_existing_non_claude_agents(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--agent", "codex", "--project"], home, project)
            payload = project / ".ai-harness-doctor" / "payload"
            self.assertTrue((payload / "SKILL.md").is_file())
            codex = home / ".codex" / "prompts" / "harness-scan.md"
            self.assertIn(str(payload), codex.read_text(encoding="utf-8"))

            self.run_cli(["install", "--agent", "cursor", "--project", "--link"], home, project)

            self.assertTrue(payload.is_symlink())
            self.assertEqual(payload.resolve(), ROOT)
            self.assertIn(str(ROOT), codex.read_text(encoding="utf-8"))
            cursor = project / ".cursor" / "commands" / "harness-scan.md"
            self.assertIn(str(ROOT), cursor.read_text(encoding="utf-8"))
            manifest = json.loads(
                (home / ".ai-harness-doctor" / "manifest.json").read_text(encoding="utf-8")
            )
            records = {
                record["agent"]: record
                for record in manifest["installs"]
                if record.get("project") == str(project.resolve())
            }
            self.assertTrue(records["codex"]["link"])
            self.assertTrue(records["cursor"]["link"])

    def test_copy_to_link_refuses_claude_skill_with_user_extension(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--project"], home, project)
            skill = project / ".claude" / "skills" / "ai-harness-doctor"
            extension = skill / "user-notes.md"
            extension.write_text("keep this extension\n", encoding="utf-8")

            link = self.run_cli(["install", "--link", "--project"], home, project)

            self.assertIn("modified-preserved", link.stdout)
            self.assertFalse(skill.is_symlink())
            self.assertEqual(extension.read_text(encoding="utf-8"), "keep this extension\n")

    def test_claude_link_to_copy_retires_owned_link_without_writing_package(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            self.run_cli(["install", "--link", "--project"], home, project)
            skill = project / ".claude" / "skills" / "ai-harness-doctor"
            self.assertTrue(skill.is_symlink())
            package_skill_before = (ROOT / "SKILL.md").read_bytes()

            copy_install = self.run_cli(["install", "--project"], home, project)

            self.assertIn("link-retired", copy_install.stdout)
            self.assertTrue(skill.is_dir())
            self.assertFalse(skill.is_symlink())
            self.assertTrue((skill / "SKILL.md").is_file())
            self.assertEqual((ROOT / "SKILL.md").read_bytes(), package_skill_before)

    def test_legacy_manifest_migrates_managed_payload_without_unknown_file_loss(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            project = Path(project_dir)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "package.json").write_text("{}\n", encoding="utf-8")
            state = project / ".ai-harness-doctor"
            state.mkdir()
            # Recreate the legacy v1 copy layout at the state root.
            shutil.copy2(ROOT / "SKILL.md", state / "SKILL.md")
            for name in ("scripts", "references", "assets"):
                shutil.copytree(
                    ROOT / name,
                    state / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            unknown = state / "owner-notes.md"
            unknown.write_text("preserve\n", encoding="utf-8")
            baseline = state / "scan-baseline.json"
            baseline.write_text('{"version": 1, "findings": []}\n', encoding="utf-8")
            manifest_dir = home / ".ai-harness-doctor"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "version": PKG_VERSION,
                        "lastUpdateCheck": 0,
                        "installs": [
                            {
                                "agent": "cursor",
                                "project": str(project.resolve()),
                                "link": False,
                                "installedAt": "legacy",
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            self.run_cli(["update"], home, project)

            self.assertTrue((state / "payload" / "SKILL.md").is_file())
            self.assertEqual(unknown.read_text(encoding="utf-8"), "preserve\n")
            self.assertEqual(baseline.read_text(encoding="utf-8"), '{"version": 1, "findings": []}\n')
            # Matching legacy payload is safely retired; unknown state remains.
            self.assertFalse((state / "SKILL.md").exists())
            self.assertFalse((state / "scripts").exists())
            manifest = json.loads((manifest_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schemaVersion"], 2)
            self.assertTrue(manifest["installs"][0]["outputs"])

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
            for gate in (
                "--fail-on-security",
                "--fail-on-gaps",
                "--fail-on-semantic",
                "--fail-on-conflicts",
            ):
                self.assertIn(gate, workflow_text)
            self.assertIn("SCAN_BASELINE: .ai-harness-doctor/scan-baseline.json", workflow_text)
            self.assertIn('scan_args+=(--baseline "$SCAN_BASELINE")', workflow_text)
            self.assertIn("--report scan-report.json", workflow_text)
            self.assertIn("--report drift-report.json", workflow_text)
            self.assertEqual(workflow_text.count("--post"), 1)
            self.assertIn(
                "scan . --fail-on-security --fail-on-gaps "
                "--fail-on-semantic --fail-on-conflicts",
                checkup_text,
            )
            self.assertIn("steps.scan.outputs.status", checkup_text)
            self.assertNotIn('npx -y ai-harness-doctor@latest scan . --write-baseline', workflow_text + checkup_text)
            self.assertNotIn("python3 scripts/", workflow_text)
            self.assertIn("🩺 Harness checkup: issues detected", checkup_text)
            self.assertIn("Reconcile harness issue", checkup_text)
            self.assertIn("CHECKUP_STATUS: ${{ steps.drift.outputs.status }}", checkup_text)
            self.assertIn("select(.title == env.TITLE)", checkup_text)
            self.assertIn("gh issue close", checkup_text)
            self.assertIn("Harness checkup recovered", checkup_text)
            self.assertIn("Fail when harness issues remain", checkup_text)
            self.assertNotIn("|| true", checkup_text)
            self.assertEqual(
                agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1
            )

            second = self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertIn("No changes needed", second.stdout)
            self.assertEqual(
                agents.read_text(encoding="utf-8").count("ai-harness-doctor:maintenance-contract:start"), 1
            )

    def test_guard_apply_rolls_back_all_files_on_mid_transaction_failure(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            agents = repo / "AGENTS.md"
            agents_before = agents.read_bytes()
            hook = repo / ".git" / "hooks" / "pre-commit"
            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup = repo / ".github" / "workflows" / "harness-checkup.yml"

            proc = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-mutation"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("rolled back", proc.stderr.lower())
            self.assertNotIn("node:internal", proc.stderr)
            self.assertFalse(hook.exists())
            self.assertFalse(drift.exists())
            self.assertFalse(checkup.exists())
            self.assertEqual(agents.read_bytes(), agents_before)
            self.assertFalse((repo / ".github").exists())
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

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

    def test_guard_consumer_combines_scan_and_drift_findings_in_one_review(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)
            self.assertFalse((repo / "scripts").exists())

            agents = repo / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8")
                + "\nBroken reference: [missing guide](docs/missing.md).\n",
                encoding="utf-8",
            )
            settings = repo / ".claude" / "settings.json"
            settings.parent.mkdir()
            settings.write_text(
                json.dumps({"permissions": {"allow": ["Bash(*)"]}}) + "\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"

            reports = []
            for name, args in (
                ("scan-report.json", ["scan", str(repo), "--json"]),
                ("drift-report.json", ["drift", str(repo), "--strict", "--json"]),
            ):
                proc = subprocess.run(
                    ["node", str(CLI), *args],
                    cwd=str(repo),
                    env=env,
                    text=True,
                    capture_output=True,
                )
                self.assertTrue(proc.stdout.strip(), proc.stderr)
                json.loads(proc.stdout)
                report = repo / name
                report.write_text(proc.stdout, encoding="utf-8")
                reports.append(report)

            review = subprocess.run(
                [
                    "node",
                    str(CLI),
                    "review",
                    "--report",
                    str(reports[0]),
                    "--report",
                    str(reports[1]),
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
            body = payload["body"]
            self.assertEqual(body.count("Broad agent permission"), 2)
            self.assertEqual(body.count("Markdown-link drift"), 2)
            self.assertIn("Bash(*)", body)
            self.assertIn("docs/missing.md", body)
            d7_comments = [
                comment
                for comment in payload["comments"]
                if "D7 · Markdown-link drift" in comment["body"]
            ]
            self.assertEqual(len(d7_comments), 1)
            self.assertEqual(d7_comments[0]["path"], "AGENTS.md")

    def test_guard_consumer_review_preserves_nested_drift_path(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply"], home, repo)

            package = repo / "packages" / "api"
            package.mkdir(parents=True)
            (package / "package.json").write_text(
                json.dumps({"scripts": {"test:api": "echo ok"}}),
                encoding="utf-8",
            )
            (package / "AGENTS.md").write_text(
                "# API\n\nRun `npm run removed-script`.\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"

            drift = subprocess.run(
                ["node", str(CLI), "drift", str(repo), "--strict", "--json"],
                cwd=str(repo),
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(drift.returncode, 1, drift.stdout + drift.stderr)
            report = repo / "drift-report.json"
            report.write_text(drift.stdout, encoding="utf-8")

            review = subprocess.run(
                [
                    "node",
                    str(CLI),
                    "review",
                    "--report",
                    str(report),
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
            comments = [
                comment
                for comment in payload["comments"]
                if "removed-script" in comment["body"]
            ]
            self.assertEqual(len(comments), 1)
            self.assertEqual(comments[0]["path"], "packages/api/AGENTS.md")
            self.assertEqual(comments[0]["line"], 3)

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

    def test_guard_remove_rolls_back_all_files_on_mid_transaction_failure(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply", "--provider", "github"], home, repo)
            managed = (
                repo / ".git" / "hooks" / "pre-commit",
                repo / ".github" / "workflows" / "harness-drift.yml",
                repo / ".github" / "workflows" / "harness-checkup.yml",
                repo / "AGENTS.md",
            )
            before = {
                path: (path.read_bytes(), path.stat().st_mode & 0o777)
                for path in managed
            }

            proc = self.run_cli_raw_with_env(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-mutation"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("rolled back", proc.stderr.lower())
            self.assertNotIn("node:internal", proc.stderr)
            for path, (content, mode) in before.items():
                with self.subTest(path=path):
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.read_bytes(), content)
                    self.assertEqual(path.stat().st_mode & 0o777, mode)
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_recovers_interrupted_transaction_before_next_apply(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            agents = repo / "AGENTS.md"
            agents_before = agents.read_bytes()
            hook = repo / ".git" / "hooks" / "pre-commit"
            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup = repo / ".github" / "workflows" / "harness-checkup.yml"

            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )

            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertTrue(hook.is_file())
            self.assertFalse(drift.exists())
            self.assertFalse(checkup.exists())
            self.assertEqual(agents.read_bytes(), agents_before)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            self.assertTrue(transaction.is_dir())

            dry_run = self.run_cli_raw(["guard", str(repo), "--provider", "github"], home, repo)

            self.assertNotEqual(dry_run.returncode, 0)
            self.assertIn("pending", dry_run.stderr.lower())
            self.assertTrue(hook.is_file())
            self.assertFalse(drift.exists())
            self.assertTrue(transaction.is_dir())

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertTrue(hook.is_file())
            self.assertTrue(drift.is_file())
            self.assertTrue(checkup.is_file())
            self.assertIn(
                "ai-harness-doctor:maintenance-contract:start",
                agents.read_text(encoding="utf-8"),
            )
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_recovery_refuses_to_overwrite_post_crash_edit(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            hook = repo / ".git" / "hooks" / "pre-commit"
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            hook.write_text("#!/bin/sh\necho user-edited-after-crash\n", encoding="utf-8")
            edited = hook.read_bytes()
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"

            recovery = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("externally modified", recovery.stderr)
            self.assertEqual(hook.read_bytes(), edited)
            self.assertTrue(transaction.is_dir())

    def test_guard_recovery_refuses_tampered_backup(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply", "--provider", "github"], home, repo)
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            backup = next(path for path in transaction.iterdir() if path.name.startswith("backup-"))
            backup.write_bytes(backup.read_bytes() + b"tampered")

            recovery = self.run_cli_raw(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("backup digest does not match", recovery.stderr)
            self.assertTrue(transaction.is_dir())

    def test_guard_recovery_refuses_malformed_journal(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            journal = transaction / "journal.json"
            journal.write_text("{broken\n", encoding="utf-8")

            recovery = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("malformed guard transaction journal", recovery.stderr)
            self.assertEqual(journal.read_text(encoding="utf-8"), "{broken\n")
            self.assertTrue(transaction.is_dir())

    def test_guard_rollback_preserves_special_mode_bits(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply", "--provider", "github"], home, repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            try:
                hook.chmod(0o4755)
            except OSError as error:
                self.skipTest(f"special mode bits unsupported: {error}")
            expected_mode = hook.stat().st_mode & 0o7777
            if expected_mode != 0o4755:
                self.skipTest("filesystem does not retain setuid mode on the test hook")
            content = hook.read_bytes()

            proc = self.run_cli_raw_with_env(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-mutation"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("rolled back", proc.stderr.lower())
            self.assertEqual(hook.read_bytes(), content)
            self.assertEqual(hook.stat().st_mode & 0o7777, expected_mode)

    def test_guard_codebase_failure_rolls_back_parents_and_executable_mode(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            agents_before = (repo / "AGENTS.md").read_bytes()

            proc = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "codebase"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-3"},
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("rolled back", proc.stderr.lower())
            self.assertFalse((repo / ".harness-ci").exists())
            self.assertFalse((repo / ".codebase").exists())
            self.assertFalse((repo / ".git" / "hooks" / "pre-commit").exists())
            self.assertEqual((repo / "AGENTS.md").read_bytes(), agents_before)
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

            installed = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "codebase"],
                home,
                repo,
            )
            self.assertIn("Applied 5 change(s)", installed.stdout)
            script = repo / ".harness-ci" / "harness-guard.sh"
            self.assertTrue(script.is_file())
            self.assertTrue(script.stat().st_mode & 0o111)

    def test_guard_recovers_interrupted_remove_before_completing_remove(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply", "--provider", "github"], home, repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup = repo / ".github" / "workflows" / "harness-checkup.yml"

            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )

            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertFalse(hook.exists())
            self.assertTrue(drift.is_file())
            self.assertTrue(checkup.is_file())

            recovered = self.run_cli(["guard", str(repo), "--remove", "--apply"], home, repo)

            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertFalse(hook.exists())
            self.assertFalse(drift.exists())
            self.assertFalse(checkup.exists())
            self.assertNotIn(
                "ai-harness-doctor:maintenance-contract:start",
                (repo / "AGENTS.md").read_text(encoding="utf-8"),
            )
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_commit_point_keeps_completed_changes_and_cleans_on_next_apply(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            hook = repo / ".git" / "hooks" / "pre-commit"
            drift = repo / ".github" / "workflows" / "harness-drift.yml"
            checkup = repo / ".github" / "workflows" / "harness-checkup.yml"

            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-commit"},
            )

            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertTrue(hook.is_file())
            self.assertTrue(drift.is_file())
            self.assertTrue(checkup.is_file())
            self.assertIn(
                "ai-harness-doctor:maintenance-contract:start",
                (repo / "AGENTS.md").read_text(encoding="utf-8"),
            )
            state = repo / ".git" / "ai-harness-doctor"
            self.assertTrue(any(path.name.startswith(".guard-committed-") for path in state.iterdir()))
            self.assertFalse((state / "guard-transaction").exists())

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("No changes needed.", recovered.stdout)
            self.assertTrue(hook.is_file())
            self.assertTrue(drift.is_file())
            self.assertTrue(checkup.is_file())
            self.assertFalse(state.exists())

    def test_guard_recovers_interrupted_atomic_write_and_removes_temp_file(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            agents_before = (repo / "AGENTS.md").read_bytes()
            hook = repo / ".git" / "hooks" / "pre-commit"

            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "before-rename"},
            )

            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertFalse(hook.exists())
            temp_files = list(hook.parent.glob(".pre-commit-guard-*.tmp"))
            self.assertEqual(len(temp_files), 1)
            self.assertTrue(
                (repo / ".git" / "ai-harness-doctor" / "guard-transaction").is_dir()
            )

            recovered = self.run_cli(
                [ "guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertTrue(hook.is_file())
            self.assertEqual(list(hook.parent.glob(".pre-commit-guard-*.tmp")), [])
            self.assertNotEqual((repo / "AGENTS.md").read_bytes(), agents_before)
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_recovery_is_idempotent_after_second_crash_during_restore(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            self.run_cli(["guard", str(repo), "--apply", "--provider", "github"], home, repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook_before = hook.read_bytes()
            hook_mode = hook.stat().st_mode & 0o777
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--remove", "--apply"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertFalse(hook.exists())

            recovery_crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "before-rename"},
            )

            self.assertEqual(recovery_crash.returncode, 87, recovery_crash.stderr)
            self.assertFalse(hook.exists())
            temp_files = list(hook.parent.glob(".pre-commit-guard-*.tmp"))
            self.assertEqual(len(temp_files), 1)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            self.assertTrue(transaction.is_dir())

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("No changes needed.", recovered.stdout)
            self.assertEqual(hook.read_bytes(), hook_before)
            self.assertEqual(hook.stat().st_mode & 0o777, hook_mode)
            self.assertEqual(list(hook.parent.glob(".pre-commit-guard-*.tmp")), [])
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_rollback_commit_point_cleans_without_reapplying_mutations(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            agents_before = (repo / "AGENTS.md").read_bytes()
            hook = repo / ".git" / "hooks" / "pre-commit"

            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {
                    "AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-mutation",
                    "AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-rollback",
                },
            )

            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertFalse(hook.exists())
            self.assertFalse((repo / ".github").exists())
            self.assertEqual((repo / "AGENTS.md").read_bytes(), agents_before)
            state = repo / ".git" / "ai-harness-doctor"
            self.assertTrue(any(path.name.startswith(".guard-rolled-back-") for path in state.iterdir()))
            self.assertFalse((state / "guard-transaction").exists())

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertTrue(hook.is_file())
            self.assertTrue((repo / ".github" / "workflows" / "harness-drift.yml").is_file())
            self.assertFalse(state.exists())

    def test_concurrent_guard_apply_refuses_live_lock_then_recovers_dead_owner(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            env["AI_HARNESS_DOCTOR_TEST_GUARD_PAUSE"] = "after-mutation"
            first = subprocess.Popen(
                ["node", str(CLI), "guard", str(repo), "--apply", "--provider", "github"],
                cwd=repo,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            lock = repo / ".git" / "ai-harness-doctor" / "guard-lock"
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not (lock.is_dir() and transaction.is_dir()):
                time.sleep(0.05)
            self.assertTrue(lock.is_dir())
            self.assertTrue(transaction.is_dir())

            second = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("another guard mutation is active", second.stderr)
            self.assertTrue(transaction.is_dir())
            first.send_signal(signal.SIGTERM)
            first.communicate(timeout=10)

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )
            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertFalse((repo / ".git" / "ai-harness-doctor").exists())

    def test_guard_recovery_rejects_journal_path_outside_fixed_allowlist(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as parent_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            outside = Path(outside_dir) / "do-not-touch"
            outside.write_text("outside\n", encoding="utf-8")
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            journal = transaction / "journal.json"
            payload = json.loads(journal.read_text(encoding="utf-8"))
            payload["snapshots"][0]["path"] = str(outside)
            journal.write_text(json.dumps(payload) + "\n", encoding="utf-8")

            recovery = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("unsafe snapshot", recovery.stderr)
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
            self.assertTrue(transaction.is_dir())

    def test_guard_linked_worktree_separates_common_hook_and_worktree_files(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            parent = Path(parent_dir)
            primary = parent / "primary"
            linked = parent / "linked"
            primary.mkdir()
            subprocess.run(["git", "init"], cwd=primary, check=True, capture_output=True, text=True)
            (primary / "AGENTS.md").write_text("# Agent Guide\n\nPrimary.\n", encoding="utf-8")
            subprocess.run(["git", "add", "AGENTS.md"], cwd=primary, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "init",
                ],
                cwd=primary,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-b", "guard-test", str(linked)],
                cwd=primary,
                check=True,
                capture_output=True,
                text=True,
            )
            common_hook = primary / ".git" / "hooks" / "pre-commit"
            linked_agents_before = (linked / "AGENTS.md").read_bytes()

            failed = self.run_cli_raw_with_env(
                ["guard", str(linked), "--apply", "--provider", "github"],
                home,
                linked,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_FAILURE": "after-mutation"},
            )

            self.assertNotEqual(failed.returncode, 0)
            self.assertFalse(common_hook.exists())
            self.assertFalse((linked / ".github").exists())
            self.assertEqual((linked / "AGENTS.md").read_bytes(), linked_agents_before)
            self.assertFalse((primary / ".git" / "ai-harness-doctor").exists())

            installed = self.run_cli(
                ["guard", str(linked), "--apply", "--provider", "github"],
                home,
                linked,
            )

            self.assertIn("Applied 4 change(s)", installed.stdout)
            self.assertTrue(common_hook.is_file())
            self.assertTrue((linked / ".github" / "workflows" / "harness-drift.yml").is_file())
            self.assertFalse((primary / ".github").exists())
            self.assertIn(
                "ai-harness-doctor:maintenance-contract:start",
                (linked / "AGENTS.md").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "ai-harness-doctor:maintenance-contract:start",
                (primary / "AGENTS.md").read_text(encoding="utf-8"),
            )

    def test_guard_recovers_linked_worktree_transaction_from_primary_worktree(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            parent = Path(parent_dir)
            primary = parent / "primary"
            linked = parent / "linked"
            primary.mkdir()
            subprocess.run(["git", "init"], cwd=primary, check=True, capture_output=True, text=True)
            original = b"# Agent Guide\n\nShared baseline.\n"
            (primary / "AGENTS.md").write_bytes(original)
            subprocess.run(["git", "add", "AGENTS.md"], cwd=primary, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.com",
                    "commit",
                    "-m",
                    "init",
                ],
                cwd=primary,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-b", "guard-recovery-test", str(linked)],
                cwd=primary,
                check=True,
                capture_output=True,
                text=True,
            )
            hook = primary / ".git" / "hooks" / "pre-commit"
            crash = self.run_cli_raw_with_env(
                ["guard", str(linked), "--apply", "--provider", "github"],
                home,
                linked,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            self.assertTrue(hook.is_file())
            self.assertEqual((linked / "AGENTS.md").read_bytes(), original)

            recovered = self.run_cli(
                ["guard", str(primary), "--apply", "--provider", "github"],
                home,
                primary,
            )

            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertTrue(hook.is_file())
            self.assertTrue((primary / ".github" / "workflows" / "harness-drift.yml").is_file())
            self.assertFalse((linked / ".github").exists())
            self.assertEqual((linked / "AGENTS.md").read_bytes(), original)
            self.assertIn(
                "ai-harness-doctor:maintenance-contract:start",
                (primary / "AGENTS.md").read_text(encoding="utf-8"),
            )
            self.assertFalse((primary / ".git" / "ai-harness-doctor").exists())

    def test_guard_recovery_refuses_symlinked_transaction_state(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as parent_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            outside = Path(outside_dir)
            (outside / "journal.json").write_text("{}\n", encoding="utf-8")
            crash = self.run_cli_raw_with_env(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
                {"AI_HARNESS_DOCTOR_TEST_GUARD_CRASH": "after-mutation"},
            )
            self.assertEqual(crash.returncode, 87, crash.stderr)
            transaction = repo / ".git" / "ai-harness-doctor" / "guard-transaction"
            shutil.rmtree(transaction)
            try:
                transaction.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported on this platform")

            recovery = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(recovery.returncode, 0)
            self.assertIn("unsafe guard transaction path", recovery.stderr)
            self.assertEqual((outside / "journal.json").read_text(encoding="utf-8"), "{}\n")
            self.assertTrue(transaction.is_symlink())

    def test_guard_transaction_owner_blocks_recovery_even_if_lock_is_removed(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as parent_dir:
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            env["AI_HARNESS_DOCTOR_TEST_GUARD_PAUSE"] = "after-mutation"
            first = subprocess.Popen(
                ["node", str(CLI), "guard", str(repo), "--apply", "--provider", "github"],
                cwd=repo,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            state = repo / ".git" / "ai-harness-doctor"
            lock = state / "guard-lock"
            transaction = state / "guard-transaction"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and not (lock.is_dir() and transaction.is_dir()):
                time.sleep(0.05)
            self.assertTrue(lock.is_dir())
            self.assertTrue(transaction.is_dir())
            shutil.rmtree(lock)

            second = self.run_cli_raw(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertNotEqual(second.returncode, 0)
            self.assertIn("transaction is still owned by a live process", second.stderr)
            self.assertTrue(transaction.is_dir())
            first.send_signal(signal.SIGTERM)
            first.communicate(timeout=10)

            recovered = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )
            self.assertIn("Applied 4 change(s)", recovered.stdout)
            self.assertFalse(state.exists())

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

    def test_guard_ignores_unselected_provider_symlink(self):
        with (
            ResilientTemporaryDirectory() as home_dir,
            ResilientTemporaryDirectory() as parent_dir,
            ResilientTemporaryDirectory() as outside_dir,
        ):
            home = Path(home_dir)
            repo = self.make_git_repo(Path(parent_dir))
            outside = Path(outside_dir) / "gitlab.yml"
            outside.write_text("outside gitlab config\n", encoding="utf-8")
            gitlab = repo / ".gitlab" / "harness-ci.yml"
            gitlab.parent.mkdir(parents=True)
            try:
                gitlab.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")

            result = self.run_cli(
                ["guard", str(repo), "--apply", "--provider", "github"],
                home,
                repo,
            )

            self.assertIn("Applied 4 change(s)", result.stdout)
            self.assertTrue((repo / ".github" / "workflows" / "harness-drift.yml").is_file())
            self.assertTrue(gitlab.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside gitlab config\n")

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
                    ["node", str(CLI), "doctor", "--json"],
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
            self.assertTrue(json.loads(proc.stdout)["ok"])
            self.assertNotIn("Traceback", proc.stderr)
            self.assertNotIn("TypeError", proc.stderr)

    def test_help_lists_mcp_command(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            proc = self.run_cli(["help"], home, Path(project_dir))
            self.assertIn("ai-harness-doctor mcp", proc.stdout)

    def test_eval_cli_forwards_target_aware_generation(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            repo = Path(project_dir)
            package = repo / "packages" / "api"
            package.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (package / "AGENTS.md").write_text("Use local commands.\n", encoding="utf-8")
            (package / "package.json").write_text(
                json.dumps({"scripts": {"test:api": "vitest run"}}),
                encoding="utf-8",
            )

            proc = self.run_cli(
                [
                    "eval",
                    "--generate",
                    str(repo),
                    "--target",
                    "packages/api/src/future.py",
                ],
                home,
                repo,
            )
            tasks = json.loads(proc.stdout)

            self.assertTrue(tasks)
            self.assertTrue(all(task["scope"] == "packages/api" for task in tasks))
            self.assertIn(
                "scope:packages%2Fapi:test:api",
                {task["id"] for task in tasks},
            )

    def test_scan_cli_propagates_batch_operational_exit(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            home = Path(home_dir)
            root = Path(project_dir)
            repos_file = root / "repos.txt"
            repos_file.write_text(str(root / "missing-repository") + "\n", encoding="utf-8")

            proc = self.run_cli_raw(
                [
                    "scan",
                    "--repos-file",
                    str(repos_file),
                    "--json",
                ],
                home,
                root,
            )

            self.assertEqual(proc.returncode, 8, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["summary"]["error_count"], 1)
            self.assertIn("listed repositories were not scanned", proc.stderr)

    def test_mcp_command_starts_and_responds_to_initialize(self):
        with ResilientTemporaryDirectory() as home_dir, ResilientTemporaryDirectory() as project_dir:
            env = os.environ.copy()
            env["HOME"] = home_dir
            env["AI_HARNESS_DOCTOR_NO_UPDATE_CHECK"] = "1"
            payload = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "cli-smoke", "version": "1.0.0"},
                        },
                    }
                )
                + "\n"
            )
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
            self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
            self.assertEqual(response["result"]["serverInfo"]["name"], "ai-harness-doctor")


if __name__ == "__main__":
    unittest.main()
