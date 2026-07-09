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

    def test_quoted_absolute_path_and_example_value_ignored(self):
        # Backtick spans wrapped in quotes are string-literal example values, not
        # repo path references; only backticks were stripped before, leaving the
        # inner quotes to defeat the guards so the value was flagged as missing.
        with tempfile.TemporaryDirectory() as td:
            text = (
                "Chrome lives at `'/usr/bin/google-chrome'`; set downloads to "
                "a string like `'./downloads'` or `\"/tmp/out\"`."
            )
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


class SemanticPythonTests(unittest.TestCase):
    def test_pip_declared_but_poetry_lock(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "poetry.lock", "# lock\n")
            text = "Install with `pip install -r requirements.txt`."
            result = semantic.analyze(td, text)
            pms = [f for f in result["findings"] if f["category"] == "package_manager"]
            self.assertEqual(len(pms), 1)
            self.assertEqual(pms[0]["declared"], "pip")
            self.assertEqual(pms[0]["actual"], "poetry")

    def test_requires_python_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pyproject.toml", '[project]\nrequires-python = ">=3.11"\n')
            text = "Requires Python 3.9."
            result = semantic.analyze(td, text)
            pv = [f for f in result["findings"] if f["category"] == "python_version"]
            self.assertEqual(len(pv), 1)
            self.assertIn("3.11", pv[0]["message"])

    def test_python_version_from_dotfile_ok(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, ".python-version", "3.12.1\n")
            text = "Use Python 3.12 for development."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "python_version"], [])

    def test_poetry_run_missing_script_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pyproject.toml", '[tool.poetry.scripts]\nmyapp = "pkg.cli:main"\n')
            text = "Run `poetry run myapp` then `poetry run ghost`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("ghost", cmds[0]["message"])

    def test_poetry_run_common_tool_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pyproject.toml", '[tool.poetry.scripts]\nmyapp = "pkg.cli:main"\n')
            text = "Run `poetry run pytest` and `poetry run mypy`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_uv_run_script_file_not_flagged(self):
        # `uv run examples/simple.py` / `uv run script.py` execute script files,
        # not project console scripts, so neither may be flagged as missing.
        with tempfile.TemporaryDirectory() as td:
            write(td, "pyproject.toml", '[project.scripts]\nmytool = "pkg:main"\n')
            text = "Run `uv run examples/simple.py` then `uv run scripts/lint.py`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_uv_run_missing_console_script_still_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pyproject.toml", '[project.scripts]\nmytool = "pkg:main"\n')
            text = "Run `uv run ghost`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("ghost", cmds[0]["message"])


class SemanticGoTests(unittest.TestCase):
    def test_go_mod_version_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "go.mod", "module example.com/x\n\ngo 1.22\n")
            text = "Requires Go 1.21."
            result = semantic.analyze(td, text)
            gv = [f for f in result["findings"] if f["category"] == "go_version"]
            self.assertEqual(len(gv), 1)
            self.assertIn("1.22", gv[0]["message"])

    def test_go_package_path_missing_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "go.mod", "module example.com/x\n\ngo 1.22\n")
            text = "Run `go run ./cmd/app`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("./cmd/app", cmds[0]["message"])

    def test_go_package_path_existing_ok(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "go.mod", "module example.com/x\n\ngo 1.22\n")
            write(td, "cmd/app/main.go", "package main\n")
            text = "Run `go build ./cmd/app` and `go test ./...`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])


class SemanticRustTests(unittest.TestCase):
    def test_rust_version_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Cargo.toml", '[package]\nname = "x"\nrust-version = "1.70"\n')
            text = "Requires Rust 1.65."
            result = semantic.analyze(td, text)
            rv = [f for f in result["findings"] if f["category"] == "rust_version"]
            self.assertEqual(len(rv), 1)
            self.assertIn("1.70", rv[0]["message"])

    def test_cargo_bin_missing_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Cargo.toml", '[package]\nname = "x"\n\n[[bin]]\nname = "main-app"\n')
            text = "Run `cargo run --bin ghost`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("ghost", cmds[0]["message"])

    def test_cargo_bin_known_target_ok(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Cargo.toml", '[package]\nname = "x"\n\n[[bin]]\nname = "main-app"\n')
            text = "Run `cargo run --bin main-app`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])


class SemanticJavaTests(unittest.TestCase):
    def test_gradle_declared_but_maven_repo(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "pom.xml", "<project></project>\n")
            text = "Build with `gradle build`."
            result = semantic.analyze(td, text)
            pms = [f for f in result["findings"] if f["category"] == "package_manager"]
            self.assertEqual(len(pms), 1)
            self.assertEqual(pms[0]["declared"], "gradle")
            self.assertEqual(pms[0]["actual"], "maven")

    def test_java_version_mismatch_from_pom(self):
        with tempfile.TemporaryDirectory() as td:
            pom = "<project><properties><maven.compiler.release>17</maven.compiler.release></properties></project>\n"
            write(td, "pom.xml", pom)
            text = "Requires Java 11."
            result = semantic.analyze(td, text)
            jv = [f for f in result["findings"] if f["category"] == "java_version"]
            self.assertEqual(len(jv), 1)
            self.assertIn("17", jv[0]["message"])

    def test_java_legacy_1_8_normalized_ok(self):
        with tempfile.TemporaryDirectory() as td:
            pom = "<project><properties><maven.compiler.source>1.8</maven.compiler.source></properties></project>\n"
            write(td, "pom.xml", pom)
            text = "Requires Java 8."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "java_version"], [])


class SemanticMultiEcosystemTests(unittest.TestCase):
    def test_polyglot_all_matching_no_findings(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package-lock.json", "{}")
            write(td, "poetry.lock", "# lock\n")
            write(td, "go.mod", "module example.com/x\n\ngo 1.22\n")
            text = "Use `npm install`, `poetry install`, and `go build ./...`."
            result = semantic.analyze(td, text)
            self.assertEqual(result["findings"], [])

    def test_findings_ordered_across_ecosystems(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "poetry.lock", "# lock\n")
            write(td, "go.mod", "module example.com/x\n\ngo 1.22\n")
            write(td, "Cargo.toml", '[package]\nname = "x"\nrust-version = "1.70"\n')
            text = "Use `pip install` here. Requires Go 1.21 and Rust 1.65."
            result = semantic.analyze(td, text)
            cats = [f["category"] for f in result["findings"]]
            self.assertEqual(cats, sorted(cats, key=lambda c: semantic.ORDER[c]))
            self.assertIn("package_manager", cats)
            self.assertIn("go_version", cats)
            self.assertIn("rust_version", cats)


if __name__ == "__main__":
    unittest.main()
