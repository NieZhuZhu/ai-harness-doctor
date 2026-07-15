import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "gen_adapters.py"
ADAPTERS = ROOT / "adapters"

sys.path.insert(0, str(ROOT / "scripts"))
import gen_adapters  # noqa: E402


class GenAdaptersUnitTests(unittest.TestCase):
    def test_generate_produces_18_files_from_6_commands(self):
        files = gen_adapters.generate(ROOT)
        self.assertEqual(len(gen_adapters.ADAPTER_COMMANDS), 6)
        self.assertEqual(len(files), 18)  # 6 commands x (codex + cursor + gemini)

    def test_generated_paths_match_expected_layout(self):
        files = gen_adapters.generate(ROOT)
        rels = {p.relative_to(ROOT).as_posix() for p in files}
        for name in ("doctor", "scan", "treat", "drift", "eval", "explain"):
            self.assertIn(f"adapters/codex/harness-{name}.md", rels)
            self.assertIn(f"adapters/cursor/harness-{name}.md", rels)
            self.assertIn(f"adapters/gemini/harness/{name}.toml", rels)

    def test_generated_matches_committed_byte_for_byte(self):
        for path, content in gen_adapters.generate(ROOT).items():
            self.assertTrue(path.is_file(), f"missing committed adapter: {path}")
            self.assertEqual(
                content,
                path.read_text(encoding="utf-8"),
                f"generated content differs from committed {path.relative_to(ROOT)}",
            )

    def test_codex_and_cursor_flavors_are_identical(self):
        files = gen_adapters.generate(ROOT)
        for name in (c["name"] for c in gen_adapters.ADAPTER_COMMANDS):
            codex = files[ROOT / "adapters" / "codex" / f"harness-{name}.md"]
            cursor = files[ROOT / "adapters" / "cursor" / f"harness-{name}.md"]
            self.assertEqual(codex, cursor)

    def test_mustache_placeholders_preserved_and_no_template_tokens_leak(self):
        for path, content in gen_adapters.generate(ROOT).items():
            self.assertIn("{{PLAYBOOK}}", content)
            self.assertNotIn("__ACTION__", content)
            self.assertNotIn("__STOP__", content)
            self.assertNotIn("__DESC__", content)
            if path.suffix == ".toml":
                self.assertIn("{{args}}", content)
                self.assertTrue(content.startswith('description = "'))
                self.assertIn('prompt = """', content)


class GenAdaptersCliTests(unittest.TestCase):
    def _copy_repo_adapters(self):
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name) / "repo"
        (repo / "scripts").mkdir(parents=True)
        shutil.copytree(ADAPTERS, repo / "adapters")
        shutil.copy2(GEN, repo / "scripts" / "gen_adapters.py")
        return td, repo

    def _run(self, repo, *args):
        return subprocess.run(
            [sys.executable, str(repo / "scripts" / "gen_adapters.py"), str(repo), *args],
            text=True,
            capture_output=True,
        )

    def test_check_passes_on_committed_repo(self):
        proc = subprocess.run([sys.executable, str(GEN), str(ROOT), "--check"], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("18 generated adapters match", proc.stdout)

    def test_check_detects_drift_and_names_the_file(self):
        td, repo = self._copy_repo_adapters()
        self.addCleanup(td.cleanup)
        drifted = repo / "adapters" / "cursor" / "harness-drift.md"
        drifted.write_text("hand-edited divergence\n", encoding="utf-8")
        proc = self._run(repo, "--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("DRIFT:", proc.stdout)
        self.assertIn("adapters/cursor/harness-drift.md", proc.stdout)

    def test_check_detects_missing_file(self):
        td, repo = self._copy_repo_adapters()
        self.addCleanup(td.cleanup)
        (repo / "adapters" / "gemini" / "harness" / "scan.toml").unlink()
        proc = self._run(repo, "--check")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("MISSING:", proc.stdout)
        self.assertIn("adapters/gemini/harness/scan.toml", proc.stdout)

    def test_write_regenerates_drifted_file_and_check_then_passes(self):
        td, repo = self._copy_repo_adapters()
        self.addCleanup(td.cleanup)
        drifted = repo / "adapters" / "codex" / "harness-eval.md"
        original = drifted.read_text(encoding="utf-8")
        drifted.write_text("clobbered\n", encoding="utf-8")
        write_proc = self._run(repo)
        self.assertEqual(write_proc.returncode, 0, write_proc.stdout + write_proc.stderr)
        self.assertEqual(drifted.read_text(encoding="utf-8"), original)
        # After regeneration --check is clean again.
        check_proc = self._run(repo, "--check")
        self.assertEqual(check_proc.returncode, 0, check_proc.stdout + check_proc.stderr)

    def test_write_from_empty_creates_all_18(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "scripts").mkdir(parents=True)
            shutil.copy2(GEN, repo / "scripts" / "gen_adapters.py")
            proc = self._run(repo)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Wrote 18 adapter(s) of 18 total", proc.stdout)
            self.assertTrue((repo / "adapters" / "gemini" / "harness" / "doctor.toml").is_file())


if __name__ == "__main__":
    unittest.main()
