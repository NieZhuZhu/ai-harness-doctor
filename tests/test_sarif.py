import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "messy-repo"
SCAN = ROOT / "scripts" / "scan.py"
DRIFT = ROOT / "scripts" / "check_drift.py"

sys.path.insert(0, str(ROOT / "scripts"))
import sarif  # noqa: E402


class LevelMappingTests(unittest.TestCase):
    def test_known_levels_map_to_sarif_levels(self):
        self.assertEqual(sarif.sarif_level("HIGH"), "error")
        self.assertEqual(sarif.sarif_level("ERROR"), "error")
        self.assertEqual(sarif.sarif_level("MEDIUM"), "warning")
        self.assertEqual(sarif.sarif_level("WARN"), "warning")
        self.assertEqual(sarif.sarif_level("NOTICE"), "warning")

    def test_info_and_unknown_fall_back_to_note(self):
        self.assertEqual(sarif.sarif_level("INFO"), "note")
        self.assertEqual(sarif.sarif_level("SOMETHING_ELSE"), "note")
        self.assertEqual(sarif.sarif_level(None), "note")


class BuildDocumentTests(unittest.TestCase):
    def test_document_shape(self):
        doc = sarif.build_document([], [], version="9.9.9")
        self.assertEqual(doc["$schema"], sarif.SCHEMA)
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(len(doc["runs"]), 1)
        driver = doc["runs"][0]["tool"]["driver"]
        self.assertEqual(driver["name"], sarif.TOOL_NAME)
        self.assertEqual(driver["name"], "ai-harness-doctor")
        self.assertEqual(driver["informationUri"], sarif.INFORMATION_URI)
        self.assertEqual(driver["version"], "9.9.9")
        self.assertEqual(driver["rules"], [])
        self.assertEqual(doc["runs"][0]["results"], [])

    def test_version_defaults_to_tool_version(self):
        # tool_version reads the real package.json; never blank.
        doc = sarif.build_document([], [])
        self.assertTrue(doc["runs"][0]["tool"]["driver"]["version"])


class ScanReportTests(unittest.TestCase):
    def _report(self):
        return {
            "security": [
                {
                    "level": "HIGH",
                    "category": "secret",
                    "path": "src/config.js",
                    "line": 12,
                    "message": "Possible AWS key committed in src/config.js",
                }
            ],
            "gaps": [
                {
                    "check": "G1",
                    "level": "ERROR",
                    "message": "No canonical AGENTS.md",
                    "suggestion": "Create AGENTS.md at the repo root.",
                }
            ],
            "semantic": {
                "findings": [
                    {
                        "category": "command",
                        "level": "MISMATCH",
                        "message": "Declared npm script does not exist",
                        "line": 5,
                    }
                ]
            },
            "conflicts": [
                {
                    "signal": "package_manager",
                    "values": {"pnpm": [], "npm": []},
                }
            ],
            "overlaps": [{"a": "AGENTS.md", "b": "CLAUDE.md"}],
            "custom": [{"check": "X", "level": "ERROR", "message": "ignored for scan"}],
        }

    def test_scan_ruleids_levels_and_locations(self):
        doc = sarif.scan_report_to_sarif(self._report(), version="1.0.0")
        results = doc["runs"][0]["results"]
        # overlaps and custom are skipped for scan SARIF v1.
        self.assertEqual(len(results), 4)

        security = results[0]
        self.assertEqual(security["ruleId"], "security/secret")
        self.assertEqual(security["level"], "error")
        loc = security["locations"][0]["physicalLocation"]
        self.assertEqual(loc["artifactLocation"]["uri"], "src/config.js")
        self.assertEqual(loc["region"]["startLine"], 12)

        gap = results[1]
        self.assertEqual(gap["ruleId"], "gap/G1")
        self.assertEqual(gap["level"], "error")
        self.assertEqual(
            gap["message"]["text"],
            "No canonical AGENTS.md — Create AGENTS.md at the repo root.",
        )
        gap_loc = gap["locations"][0]["physicalLocation"]
        self.assertEqual(gap_loc["artifactLocation"]["uri"], "AGENTS.md")
        self.assertNotIn("region", gap_loc)

        semantic = results[2]
        self.assertEqual(semantic["ruleId"], "semantic/command")
        self.assertEqual(semantic["level"], "note")  # MISMATCH is unmapped
        sem_loc = semantic["locations"][0]["physicalLocation"]
        self.assertEqual(sem_loc["artifactLocation"]["uri"], "AGENTS.md")
        self.assertEqual(sem_loc["region"]["startLine"], 5)

        conflict = results[3]
        self.assertEqual(conflict["ruleId"], "conflict/package_manager")
        self.assertEqual(conflict["level"], "warning")
        self.assertEqual(
            conflict["message"]["text"],
            "Conflicting package_manager declarations: npm, pnpm",
        )
        self.assertEqual(conflict["locations"], [])

    def test_scan_rules_sorted_by_id(self):
        doc = sarif.scan_report_to_sarif(self._report())
        rule_ids = [r["id"] for r in doc["runs"][0]["tool"]["driver"]["rules"]]
        self.assertEqual(rule_ids, sorted(rule_ids))
        self.assertEqual(
            rule_ids,
            ["conflict/package_manager", "gap/G1", "security/secret", "semantic/command"],
        )
        for rule in doc["runs"][0]["tool"]["driver"]["rules"]:
            self.assertEqual(rule["id"], rule["name"])
            self.assertIn("shortDescription", rule)
            self.assertIn("defaultConfiguration", rule)

    def test_monorepo_path_prefixing(self):
        report = {
            "packages": [
                {
                    "path": "packages/app",
                    "report": {
                        "security": [
                            {
                                "level": "HIGH",
                                "category": "secret",
                                "path": "index.js",
                                "line": 3,
                                "message": "secret",
                            }
                        ],
                        "gaps": [{"check": "G1", "level": "ERROR", "message": "missing"}],
                    },
                }
            ]
        }
        doc = sarif.scan_report_to_sarif(report)
        results = doc["runs"][0]["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            "packages/app/index.js",
        )
        self.assertEqual(
            results[1]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            "packages/app/AGENTS.md",
        )

    def test_security_without_path_has_no_location(self):
        report = {"security": [{"level": "MEDIUM", "category": "mcp", "message": "no path"}]}
        doc = sarif.scan_report_to_sarif(report)
        result = doc["runs"][0]["results"][0]
        self.assertEqual(result["level"], "warning")
        self.assertEqual(result["locations"], [])

    def test_empty_report_is_valid_document_with_zero_results(self):
        doc = sarif.scan_report_to_sarif({})
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["$schema"], sarif.SCHEMA)
        self.assertEqual(doc["runs"][0]["results"], [])
        self.assertEqual(doc["runs"][0]["tool"]["driver"]["rules"], [])


class DriftReportTests(unittest.TestCase):
    def test_drift_maps_error_to_sarif_error_with_location(self):
        report = {
            "findings": [
                {
                    "check": "D2",
                    "level": "ERROR",
                    "line": 7,
                    "path": "AGENTS.md",
                    "message": "Referenced path `src/old` does not exist",
                    "suggestion": "Fix or remove the backtick-quoted path.",
                }
            ],
            "info": [{"check": "D5", "level": "INFO", "path": "sub/AGENTS.md", "message": "inventory"}],
        }
        doc = sarif.drift_report_to_sarif(report)
        results = doc["runs"][0]["results"]
        self.assertEqual(len(results), 1)  # info excluded
        result = results[0]
        self.assertEqual(result["ruleId"], "drift/D2")
        self.assertEqual(result["level"], "error")
        loc = result["locations"][0]["physicalLocation"]
        self.assertEqual(loc["artifactLocation"]["uri"], "AGENTS.md")
        self.assertEqual(loc["region"]["startLine"], 7)
        self.assertEqual(
            result["message"]["text"],
            "Referenced path `src/old` does not exist — Fix or remove the backtick-quoted path.",
        )

    def test_drift_finding_without_path_defaults_to_agents_md(self):
        report = {"findings": [{"check": "D4", "level": "ERROR", "message": "AGENTS.md is missing"}]}
        doc = sarif.drift_report_to_sarif(report)
        loc = doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]
        self.assertEqual(loc["artifactLocation"]["uri"], "AGENTS.md")
        self.assertNotIn("region", loc)

    def test_drift_includes_custom_findings(self):
        report = {
            "findings": [],
            "custom": [{"level": "WARN", "message": "custom rule"}],
        }
        doc = sarif.drift_report_to_sarif(report)
        result = doc["runs"][0]["results"][0]
        self.assertEqual(result["ruleId"], "drift/custom")
        self.assertEqual(result["level"], "warning")

    def test_drift_empty_report_is_valid(self):
        doc = sarif.drift_report_to_sarif({})
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["runs"][0]["results"], [])
        self.assertEqual(doc["runs"][0]["tool"]["driver"]["rules"], [])


class CliSmokeTests(unittest.TestCase):
    def _fixture_repo(self):
        # A tiny temp repo with an AGENTS.md so both commands have something real
        # to scan without depending on fixture internals.
        td = tempfile.TemporaryDirectory()
        repo = Path(td.name)
        (repo / "AGENTS.md").write_text("# Project overview\nDemo.\n", encoding="utf-8")
        (repo / "package.json").write_text('{"name": "demo", "version": "1.0.0"}\n', encoding="utf-8")
        return td, repo

    def test_scan_cli_emits_valid_sarif(self):
        td, repo = self._fixture_repo()
        try:
            proc = subprocess.run([sys.executable, str(SCAN), str(repo), "--sarif"], text=True, capture_output=True)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["$schema"], sarif.SCHEMA)
            self.assertEqual(doc["version"], "2.1.0")
            self.assertEqual(doc["runs"][0]["tool"]["driver"]["name"], "ai-harness-doctor")
        finally:
            td.cleanup()

    def test_drift_cli_emits_valid_sarif(self):
        td, repo = self._fixture_repo()
        try:
            proc = subprocess.run([sys.executable, str(DRIFT), str(repo), "--sarif"], text=True, capture_output=True)
            doc = json.loads(proc.stdout)
            self.assertEqual(doc["$schema"], sarif.SCHEMA)
            self.assertEqual(doc["version"], "2.1.0")
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
