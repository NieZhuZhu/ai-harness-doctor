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

    def test_yarn_workspace_builtin_not_flagged(self):
        # `yarn workspace <name> <cmd>` / `yarn workspaces foreach ...` are Yarn
        # subcommands, not package.json scripts (found scanning tldraw/tldraw's
        # AGENTS.md, which documents `yarn workspace examples.tldraw.com dev`).
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}}')
            text = "Run `yarn workspace examples dev` or `yarn workspaces info`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_yarn_bin_passthrough_via_dependency_not_flagged(self):
        # Yarn Classic/Berry run a binary straight out of node_modules/.bin when
        # no matching script exists (`yarn vitest`). Found scanning tldraw's
        # AGENTS.md, which documents `yarn vitest` even though the root
        # package.json has no "vitest" script — only a "vitest" devDependency.
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}, "devDependencies": {"vitest": "^2.0.0"}}')
            text = "Run `yarn vitest` to test everything."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_yarn_bin_passthrough_via_installed_node_modules_bin_not_flagged(self):
        # When node_modules/.bin is actually installed it is the more accurate
        # ground truth (covers binaries whose name differs from the package that
        # provides them, e.g. `tsc` from the `typescript` package).
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}, "devDependencies": {"typescript": "^5.0.0"}}')
            write(td, "node_modules/.bin/tsc", "#!/bin/sh\n")
            text = "Run `yarn tsc --noEmit`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])

    def test_yarn_bin_passthrough_does_not_apply_to_npm_or_pnpm(self):
        # npm has no such fallback (`npm vitest` errors) and pnpm does not resolve
        # node_modules/.bin this way either, so the exemption must stay yarn-only.
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}, "devDependencies": {"vitest": "^2.0.0"}}')
            text = "Run `npm vitest` or `pnpm vitest`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 2)

    def test_yarn_unknown_binary_still_flagged(self):
        # A yarn invocation with no matching script AND no matching dependency
        # (nor an installed bin) is still a genuine drift, not a passthrough.
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {}, "devDependencies": {}}')
            text = "Run `yarn totally-made-up-tool`."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("totally-made-up-tool", cmds[0]["message"])

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

    def test_prose_imperative_not_misdetected_as_make_command(self):
        # "make sure the tests pass" is English prose, not a `make sure` target;
        # it must not be parsed into a phantom command, while a genuine fenced
        # `make deploy` invocation is still detected (CORR-02).
        with tempfile.TemporaryDirectory() as td:
            write(td, "Makefile", "build:\n\techo hi\n")
            text = (
                "Please make sure the tests pass before committing.\n\n"
                "```bash\n"
                "# make sure to run the tests first\n"
                "make deploy\n"
                "```\n"
            )
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("deploy", cmds[0]["message"])
            self.assertFalse(any("sure" in f["message"] for f in cmds))

    def test_hyphenated_command_name_missing_target_still_flagged(self):
        # CORRECTNESS-01: `[A-Za-z']+` used to extract sub-words from INSIDE a
        # hyphen/colon-joined identifier too, so "and" in "lint-and-fix" (or
        # "on" in "build:on:save") counted as a prose-word hit and the whole
        # line was misread as an English sentence — silently disabling the D1
        # command-drift check for any command shaped like that.
        with tempfile.TemporaryDirectory() as td:
            write(td, "Makefile", "build:\n\techo hi\n")
            text = "Run `make lint-and-fix` before committing."
            result = semantic.analyze(td, text)
            cmds = [f for f in result["findings"] if f["category"] == "command"]
            self.assertEqual(len(cmds), 1)
            self.assertIn("lint-and-fix", cmds[0]["message"])

    def test_hyphenated_command_name_present_target_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Makefile", "lint-and-fix:\n\techo ok\n")
            text = "Run `make lint-and-fix` before committing."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "command"], [])


class ProseHeuristicTests(unittest.TestCase):
    """Direct unit coverage for facts.looks_like_prose (CORRECTNESS-01):
    previously exercised only indirectly through compare_commands/D1."""

    def test_hyphen_or_colon_joined_identifiers_are_not_prose(self):
        for segment in (
            "make lint-and-fix",
            "npm run build:on:save",
            "make test-and-build",
            "make build-and-deploy",
        ):
            self.assertFalse(semantic._looks_like_prose(segment), segment)

    def test_genuine_english_sentences_are_still_prose(self):
        for segment in (
            "Please make sure the tests pass before committing.",
            "Make sure to run the tests first before you commit anything.",
        ):
            self.assertTrue(semantic._looks_like_prose(segment), segment)

    def test_short_segments_are_never_prose(self):
        self.assertFalse(semantic._looks_like_prose("make sure"))
        self.assertFalse(semantic._looks_like_prose("make deploy"))


class SemanticPackageScriptsTests(unittest.TestCase):
    def test_valid_package_json_with_scripts(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", '{"scripts": {"build": "tsc", "lint": "eslint"}}')
            self.assertEqual(semantic.package_scripts(Path(td)), {"build", "lint"})

    def test_valid_package_json_without_scripts_is_empty_set(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", "{}")
            self.assertEqual(semantic.package_scripts(Path(td)), set())

    def test_absent_package_json_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(semantic.package_scripts(Path(td)))

    def test_invalid_json_returns_none_not_empty_set(self):
        # A present-but-unparseable package.json must be a sentinel distinct from
        # "parsed, no scripts" so callers do not treat it as "no scripts" (CORR-01).
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", "{ this is not valid json ")
            self.assertIsNone(semantic.package_scripts(Path(td)))

    def test_invalid_json_yields_no_false_unknown_script_finding(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "package.json", "{ this is not valid json ")
            result = semantic.analyze(td, "Run `npm run build` and `npm run lint`.")
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

    def test_scoped_package_names_ignored(self):
        # Scoped npm package names (`@ai-sdk/provider`) and path-alias imports
        # (`@/components`) contain a slash but are package/module identifiers, not
        # repo-relative paths, so they must not be flagged as missing paths.
        with tempfile.TemporaryDirectory() as td:
            text = (
                "Providers live in `@ai-sdk/provider` and `@ai-sdk/provider-utils`; "
                "aliases like `@/components` are imports."
            )
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "path"], [])

    def test_placeholder_name_segment_ignored(self):
        # A leading `<word>-name` segment (`skill-name/SKILL.md`) documents a
        # naming pattern in prose, not a literal path (found scanning
        # tldraw/tldraw's AGENTS.md, which uses this idiom for its skill-folder
        # convention). A real path segment that merely contains "name"
        # (`username/profile.py`) must still be checked for existence.
        with tempfile.TemporaryDirectory() as td:
            text = (
                "Skill folders use `skill-name/SKILL.md` as a template. "
                "See `username/profile.py` for the real handler."
            )
            result = semantic.analyze(td, text)
            paths = [f for f in result["findings"] if f["category"] == "path"]
            self.assertEqual(len(paths), 1)
            self.assertIn("username/profile.py", paths[0]["message"])

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

    def test_competing_lockfiles_not_flagged(self):
        # A repo with two committed lockfiles (e.g. a leftover package-lock.json
        # next to the real pnpm-lock.yaml, common mid-migration) is genuinely
        # ambiguous — check_drift.py's D8 gate already treats this as "human
        # must decide" and D6 stays silent. `_node_ground_pm` previously
        # first-matched pnpm-lock.yaml and confidently reported a MISMATCH here,
        # contradicting Phase-2's own verdict on the identical repo state.
        with tempfile.TemporaryDirectory() as td:
            write(td, "pnpm-lock.yaml", "lockfileVersion: 6\n")
            write(td, "package-lock.json", "{}")
            text = "Use `npm install` for dependencies."
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

    def test_gradle_legacy_version_1_8_enum_normalized_ok(self):
        # Gradle's legacy Java-8-and-below enum spelling uses an underscore
        # (`JavaVersion.VERSION_1_8`), not a dot. The dot-only regex previously
        # captured only the leading "1" and reported a nonsensical "Java 1"
        # mismatch against a correct "Requires Java 8" declaration.
        with tempfile.TemporaryDirectory() as td:
            write(td, "build.gradle", "sourceCompatibility = JavaVersion.VERSION_1_8\n")
            text = "Requires Java 8."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "java_version"], [])

    def test_gradle_legacy_version_1_8_enum_mismatch_still_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "build.gradle", "sourceCompatibility = JavaVersion.VERSION_1_8\n")
            text = "Requires Java 11."
            result = semantic.analyze(td, text)
            jv = [f for f in result["findings"] if f["category"] == "java_version"]
            self.assertEqual(len(jv), 1)
            self.assertIn("8", jv[0]["message"])


class SemanticRubyTests(unittest.TestCase):
    def test_ruby_version_mismatch_from_ruby_version_file(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, ".ruby-version", "3.2.0\n")
            text = "Requires ruby 3.1."
            result = semantic.analyze(td, text)
            rv = [f for f in result["findings"] if f["category"] == "ruby_version"]
            self.assertEqual(len(rv), 1)
            self.assertIn("3.2", rv[0]["message"])
            self.assertIn(".ruby-version", rv[0]["message"])

    def test_ruby_version_mismatch_from_gemfile_directive(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Gemfile", 'source "https://rubygems.org"\nruby "3.3.1"\n')
            text = "Requires ruby 3.2."
            result = semantic.analyze(td, text)
            rv = [f for f in result["findings"] if f["category"] == "ruby_version"]
            self.assertEqual(len(rv), 1)
            self.assertIn("3.3", rv[0]["message"])
            self.assertIn("Gemfile", rv[0]["message"])

    def test_ruby_version_match_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, ".ruby-version", "3.2.0\n")
            text = "Requires ruby 3.2."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "ruby_version"], [])

    def test_bundle_package_manager_declared_and_present_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Gemfile.lock", "GEM\n  remote: https://rubygems.org/\n")
            text = "Install with `bundle install`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "package_manager"], [])

    def test_no_gemfile_means_no_ruby_findings(self):
        with tempfile.TemporaryDirectory() as td:
            text = "Requires ruby 3.2. Run `bundle install`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "ruby_version"], [])
            self.assertEqual([f for f in result["findings"] if f["category"] == "package_manager"], [])

    def test_gem_install_flagged_when_gemfile_lock_implies_bundle(self):
        # `gem install X` (manual, unlocked gem management) bypasses the
        # dependency lock a committed Gemfile.lock says the project relies on
        # — the same anti-pattern class as declaring npm when the lockfile
        # implies yarn.
        with tempfile.TemporaryDirectory() as td:
            write(td, "Gemfile.lock", "GEM\n  remote: https://rubygems.org/\n")
            text = "Install deps with `gem install rails`."
            result = semantic.analyze(td, text)
            pms = [f for f in result["findings"] if f["category"] == "package_manager"]
            self.assertEqual(len(pms), 1)
            self.assertEqual(pms[0]["declared"], "gem")
            self.assertEqual(pms[0]["actual"], "bundle")

    def test_gem_alongside_bundle_is_ambiguous_not_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            write(td, "Gemfile.lock", "GEM\n  remote: https://rubygems.org/\n")
            text = "Run `bundle install`, or `gem install rails` for a one-off."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "package_manager"], [])

    def test_gem_without_gemfile_lock_not_flagged(self):
        # A standalone gem library (only a .gemspec, no Gemfile.lock) has no
        # ground truth to compare against — `_ruby_ground_pm` returns None.
        with tempfile.TemporaryDirectory() as td:
            text = "Install deps with `gem install rails`."
            result = semantic.analyze(td, text)
            self.assertEqual([f for f in result["findings"] if f["category"] == "package_manager"], [])


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
