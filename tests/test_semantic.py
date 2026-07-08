import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic  # noqa: E402


def write(root, name, content):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class SemanticCommandTests(unittest.TestCase):
    def test_flags_missing_npm_script(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {"build": "tsc"}}')
            text = "Run `npm run build` then `npm run lint`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("lint", cmds[0]["message"])
            self.assertEqual(cmds[0]["level"], "MISMATCH")

    def test_package_manager_builtins_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}}')
            text = "Install with `npm install` and `npm ci`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_make_target_missing(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Makefile", "build:\n\techo hi\n")
            text = "Run `make build` and `make deploy`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("deploy", cmds[0]["message"])

    def test_no_package_json_means_no_command_findings(self):
        with tempfile.TemporaryDirectory() as td:
            text = "Run `npm run build`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])


class SemanticPathTests(unittest.TestCase):
    def test_missing_path_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "src/index.ts", "// exists")
            text = "Entry is `src/index.ts`, helpers in `src/missing.ts`."
            result = semantic.analyze(td, text)
            paths = [f for f in result["findings"] if f["category"] == "path"]
            self.assertEqual(len(paths), 1)
            self.assertIn("src/missing.ts", paths[0]["message"])

    def test_urls_and_placeholders_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            text = "See `https://example.com/x`, `<your-path>`, `${VAR}`, `~/.config`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "path"], [])

    def test_escape_outside_root_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            text = "See `../../etc/passwd`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "path"], [])


class SemanticPackageManagerTests(unittest.TestCase):
    def test_declared_pm_mismatch_with_lockfile(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pnpm-lock.yaml", "lockfileVersion: 6\n")
            text = "Use `npm install` for dependencies."
            result = semantic.analyze(td, text)
            pms = [f for f in result["findings"] if f["category"] == "package_manager"]
            self.assertEqual(len(pms), 1)
            self.assertEqual(pms[0]["declared"], "npm")
            self.assertEqual(pms[0]["actual"], "pnpm")

    def test_ambiguous_declared_pms_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pnpm-lock.yaml", "lockfileVersion: 6\n")
            text = "Use `npm install` or `yarn install`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "package_manager"], [])


class SemanticNodeVersionTests(unittest.TestCase):
    def test_nvmrc_and_engines_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, ".nvmrc", "v20\n")
            write(td, "package.json", '{"engines": {"node": ">=18"}}')
            text = "Requires node 16."
            result = semantic.analyze(td, text)
            nodes = [f for f in result["findings"] if f["category"] == "node_version"]
            self.assertEqual(len(nodes), 2)

    def test_matching_node_version_ok(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, ".nvmrc", "v20\n")
            text = "Requires node 20."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "node_version"], [])


class SemanticSummaryTests(unittest.TestCase):
    def test_checked_and_mismatch_counts(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {"build": "tsc"}}')
            text = "Run `npm run build` and `npm run lint`."
            result = semantic.analyze(td, text)
            self.assertEqual(result["mismatches"], 1)
            self.assertEqual(result["checked"], 2)

    def test_empty_text_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            result = semantic.analyze(td, "")
            self.assertEqual(result, {"findings": [], "checked": 0, "mismatches": 0})

    def test_findings_deterministically_ordered(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}}')
            write(td, ".nvmrc", "v20\n")
            text = "Path `a/b.ts`, run `npm run x`, node 16."
            result = semantic.analyze(td, text)
            cats = [f["category"] for f in result["findings"]]
            order = {"command": 0, "path": 1, "package_manager": 2, "node_version": 3}
            self.assertEqual(cats, sorted(cats, key=lambda c: order[c]))


if __name__ == "__main__":
    unittest.main()
