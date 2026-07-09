"""Guards for the optional test-coverage tooling (TEST-03).

Coverage is a dev convenience, not a required gate, but the wiring (npm scripts
plus the coverage.py config) should not silently disappear. These checks are
config-only and never run coverage itself, so they stay fast and dependency-free.
"""

import configparser
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CoverageWiringTests(unittest.TestCase):
    def test_package_json_exposes_coverage_scripts(self):
        scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["scripts"]
        for name in ("coverage", "coverage:py", "coverage:js"):
            self.assertIn(name, scripts, f"missing npm script {name!r}")
        # Python coverage measures scripts/; JS coverage uses Node's built-in reporter.
        self.assertIn("coverage run", scripts["coverage:py"])
        self.assertIn("unittest", scripts["coverage:py"])
        self.assertIn("--experimental-test-coverage", scripts["coverage:js"])

    def test_coveragerc_targets_scripts_package(self):
        cfg = configparser.ConfigParser()
        cfg.read(ROOT / ".coveragerc")
        self.assertTrue(cfg.has_section("run"), ".coveragerc is missing a [run] section")
        self.assertEqual(cfg.get("run", "source").strip(), "scripts")


if __name__ == "__main__":
    unittest.main()
