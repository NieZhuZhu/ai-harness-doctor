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


if __name__ == "__main__":
    unittest.main()
