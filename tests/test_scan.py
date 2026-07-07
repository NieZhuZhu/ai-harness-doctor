import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
SCAN = ROOT / "scripts" / "scan.py"


class ScanTests(unittest.TestCase):
    def run_json(self, repo):
        proc = subprocess.run([sys.executable, str(SCAN), str(repo), "--json"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_finds_expected_files_conflict_and_overlap(self):
        report = self.run_json(FIXTURE)
        paths = {f["path"] for f in report["files"]}
        self.assertIn("CLAUDE.md", paths)
        self.assertIn(".cursorrules", paths)
        self.assertIn(".github/copilot-instructions.md", paths)
        package_conflicts = [c for c in report["conflicts"] if c["signal"] == "package_manager"]
        self.assertTrue(package_conflicts)
        values = set(package_conflicts[0]["values"].keys())
        self.assertIn("pnpm", values)
        self.assertIn("npm", values)
        self.assertTrue(any({o["a"], o["b"]} == {"CLAUDE.md", ".cursorrules"} for o in report["overlaps"]))

    def test_size_warning_for_generated_big_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "repo"
            shutil.copytree(FIXTURE, tmp)
            (tmp / "AGENTS.md").write_text("line\n" * 4000, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCAN), str(tmp), "--json", "--max-bytes", "100"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(any(w["level"] == "WARN" and w["path"] == "AGENTS.md" for w in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
