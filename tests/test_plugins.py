import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ROOT / "scripts" / "scan.py"
DRIFT = ROOT / "scripts" / "check_drift.py"

sys.path.insert(0, str(ROOT / "scripts"))
import plugins  # noqa: E402

GOOD_PLUGIN = """\
def check(root, context):
    return [
        {
            "rule": "demo/hello",
            "level": "WARN",
            "path": "AGENTS.md",
            "line": 3,
            "message": "custom rule fired",
            "suggestion": "do the thing",
        }
    ]
"""

# Reads the injected context so we can assert the loader passes it through.
CONTEXT_PLUGIN = """\
def check(root, context):
    return [{"rule": "demo/phase", "level": "NOTICE", "message": "phase=%s" % context.get("phase")}]
"""

IMPORT_ERROR_PLUGIN = """\
import this_module_definitely_does_not_exist_xyz  # noqa: F401


def check(root, context):
    return []
"""

RUNTIME_ERROR_PLUGIN = """\
def check(root, context):
    raise ValueError("boom from plugin")
"""

NO_CHECK_PLUGIN = """\
def not_check(root, context):
    return []
"""

BAD_RETURN_PLUGIN = """\
def check(root, context):
    return {"not": "a list"}
"""


def _make_repo(tmp):
    repo = Path(tmp) / "repo"
    (repo / ".ai-harness-doctor" / "rules").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# Project overview\n\nSome docs.\n", encoding="utf-8")
    return repo


def _write_rule(repo, name, body):
    path = repo / ".ai-harness-doctor" / "rules" / name
    path.write_text(body, encoding="utf-8")
    return path


class PluginScanIntegrationTests(unittest.TestCase):
    def run_json(self, repo, *extra):
        proc = subprocess.run([sys.executable, str(SCAN), str(repo), "--json", *extra], text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_conventional_dir_findings_appear_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "good.py", GOOD_PLUGIN)
            report = self.run_json(repo)
            self.assertIn("custom", report)
            rules = {f["rule"] for f in report["custom"]}
            self.assertIn("demo/hello", rules)
            hit = next(f for f in report["custom"] if f["rule"] == "demo/hello")
            self.assertEqual(hit["level"], "WARN")
            self.assertEqual(hit["message"], "custom rule fired")
            # The loader stamps the source plugin path onto every finding.
            self.assertEqual(hit["plugin"], ".ai-harness-doctor/rules/good.py")

    def test_explicit_rules_flag_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            rules_dir = Path(tmp) / "myrules"
            rules_dir.mkdir()
            (rules_dir / "ctx.py").write_text(CONTEXT_PLUGIN, encoding="utf-8")
            report = self.run_json(repo, "--rules", str(rules_dir))
            phases = [f["message"] for f in report["custom"] if f["rule"] == "demo/phase"]
            self.assertEqual(phases, ["phase=scan"])

    def test_broken_import_is_isolated_as_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "broken.py", IMPORT_ERROR_PLUGIN)
            _write_rule(repo, "good.py", GOOD_PLUGIN)
            report = self.run_json(repo)  # must NOT crash (returncode 0 asserted)
            errors = [f for f in report["custom"] if f["level"] == "ERROR"]
            self.assertTrue(any(f["rule"] == "plugin-load" for f in errors))
            load_err = next(f for f in errors if f["rule"] == "plugin-load")
            self.assertEqual(load_err["plugin"], ".ai-harness-doctor/rules/broken.py")
            # A sibling good plugin still runs despite the broken one.
            self.assertTrue(any(f["rule"] == "demo/hello" for f in report["custom"]))

    def test_runtime_error_is_isolated_as_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "raiser.py", RUNTIME_ERROR_PLUGIN)
            report = self.run_json(repo)
            errors = [f for f in report["custom"] if f["level"] == "ERROR"]
            self.assertTrue(any(f["rule"] == "plugin-error" for f in errors))
            self.assertTrue(any("boom from plugin" in f["message"] for f in errors))

    def test_optout_default_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            report = self.run_json(repo)
            # No rules dir and no --rules → section present but empty.
            self.assertEqual(report["custom"], [])

    def test_no_custom_flag_drops_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "good.py", GOOD_PLUGIN)
            report = self.run_json(repo, "--no-custom")
            self.assertNotIn("custom", report)


class PluginDriftIntegrationTests(unittest.TestCase):
    def run_drift_json(self, repo, *extra):
        proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--json", *extra], text=True, capture_output=True)
        return proc

    def test_drift_reports_custom_without_affecting_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "good.py", GOOD_PLUGIN)
            proc = self.run_drift_json(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertIn("custom", report)
            self.assertTrue(any(f["rule"] == "demo/hello" for f in report["custom"]))
            # Custom findings are additive: they do not change the D1-D8 score.
            self.assertEqual(report["score"], 100)
            self.assertTrue(report["ok"])

    def test_drift_broken_plugin_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "raiser.py", RUNTIME_ERROR_PLUGIN)
            proc = self.run_drift_json(repo)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(any(f["rule"] == "plugin-error" for f in report["custom"]))


class PluginLoaderUnitTests(unittest.TestCase):
    def test_missing_check_is_contract_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "nocheck.py", NO_CHECK_PLUGIN)
            findings = plugins.run_plugins(repo, {"phase": "scan", "agents_text": ""})
            self.assertTrue(any(f["rule"] == "plugin-contract" for f in findings))

    def test_bad_return_type_is_output_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "badret.py", BAD_RETURN_PLUGIN)
            findings = plugins.run_plugins(repo, {"phase": "scan", "agents_text": ""})
            self.assertTrue(any(f["rule"] == "plugin-output" for f in findings))

    def test_private_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "_helper.py", RUNTIME_ERROR_PLUGIN)
            _write_rule(repo, "__init__.py", RUNTIME_ERROR_PLUGIN)
            findings = plugins.run_plugins(repo, {"phase": "scan", "agents_text": ""})
            self.assertEqual(findings, [])

    def test_discovery_is_ordered_and_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            _write_rule(repo, "b.py", GOOD_PLUGIN)
            _write_rule(repo, "a.py", GOOD_PLUGIN)
            files = plugins.discover_rule_files(repo)
            names = [p.name for p in files]
            self.assertEqual(names, ["a.py", "b.py"])
            # Passing the same dir again via extra_dirs must not duplicate entries.
            again = plugins.discover_rule_files(repo, [repo / ".ai-harness-doctor" / "rules"])
            self.assertEqual([p.name for p in again], ["a.py", "b.py"])

    def test_example_plugin_conforms_to_contract(self):
        example = ROOT / "references" / "example-rule-plugin.py"
        self.assertTrue(example.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            repo = _make_repo(tmp)
            # Copy the shipped example into the rules dir and run it end to end.
            (repo / ".ai-harness-doctor" / "rules" / "example.py").write_text(
                example.read_text(encoding="utf-8"), encoding="utf-8"
            )
            (repo / "AGENTS.md").write_text("# Project overview\n\nTODO(agents): finish this.\n", encoding="utf-8")
            findings = plugins.run_plugins(
                repo, {"phase": "scan", "agents_text": (repo / "AGENTS.md").read_text(encoding="utf-8")}
            )
            rules = {f["rule"] for f in findings}
            self.assertIn("example/require-license", rules)
            self.assertIn("example/no-agent-todo", rules)
            self.assertFalse(any(f["level"] == "ERROR" for f in findings))


if __name__ == "__main__":
    unittest.main()
