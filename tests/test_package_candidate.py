import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_package_candidate as candidate  # noqa: E402


class PackageCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.version = json.loads(
            (ROOT / "package.json").read_text(encoding="utf-8")
        )["version"]

    def _complete_record(self):
        expected = sorted(candidate.expected_package_files(ROOT))
        return {
            "id": f"ai-harness-doctor@{self.version}",
            "name": "ai-harness-doctor",
            "version": self.version,
            "filename": f"ai-harness-doctor-{self.version}.tgz",
            "files": [{"path": path} for path in expected],
        }

    def test_current_expected_inventory_is_valid(self):
        record = self._complete_record()
        candidate.validate_pack_record(
            ROOT,
            record,
            ROOT / ".package-candidate-test-pack",
            expected_version=self.version,
            require_tarball=False,
        )

    def test_missing_script_allowlist_fails(self):
        record = self._complete_record()
        record["files"] = [
            item for item in record["files"] if item["path"] != "scripts/scan.py"
        ]
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            r"missing required package files: scripts/scan\.py",
        ):
            candidate.validate_pack_record(
                ROOT,
                record,
                ROOT / ".package-candidate-test-pack",
                expected_version=self.version,
                require_tarball=False,
            )

    def test_missing_bin_helper_fails(self):
        record = self._complete_record()
        record["files"] = [
            item
            for item in record["files"]
            if item["path"] != "bin/action-report.js"
        ]
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            r"missing required package files: bin/action-report\.js",
        ):
            candidate.validate_pack_record(
                ROOT,
                record,
                ROOT / ".package-candidate-test-pack",
                expected_version=self.version,
                require_tarball=False,
            )

    def test_missing_public_readme_fails(self):
        record = self._complete_record()
        record["files"] = [
            item for item in record["files"] if item["path"] != "README.fr.md"
        ]
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            r"missing required package files: README\.fr\.md",
        ):
            candidate.validate_pack_record(
                ROOT,
                record,
                ROOT / ".package-candidate-test-pack",
                expected_version=self.version,
                require_tarball=False,
            )

    def test_test_and_maintenance_files_are_rejected(self):
        for forbidden in (
            "bin/cli.test.js",
            "scripts/check_readme_sync.py",
            "scripts/gen_adapters.py",
            "scripts/check_package_candidate.py",
        ):
            with self.subTest(path=forbidden):
                record = self._complete_record()
                record["files"].append({"path": forbidden})
                with self.assertRaisesRegex(
                    candidate.PackageCandidateError,
                    "forbidden package files",
                ):
                    candidate.validate_pack_record(
                        ROOT,
                        record,
                        ROOT / ".package-candidate-test-pack",
                        expected_version=self.version,
                        require_tarball=False,
                    )

    def test_pack_output_must_describe_exactly_one_record(self):
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "exactly one package record",
        ):
            candidate.parse_pack_output("[]")
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "exactly one package record",
        ):
            candidate.parse_pack_output("[{}, {}]")
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "invalid JSON",
        ):
            candidate.parse_pack_output("{bad")

    def test_duplicate_pack_member_fails(self):
        record = self._complete_record()
        record["files"].append({"path": record["files"][0]["path"]})
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "duplicate member path",
        ):
            candidate.validate_pack_record(
                ROOT,
                record,
                ROOT / ".package-candidate-test-pack",
                expected_version=self.version,
                require_tarball=False,
            )

    def test_tarball_path_must_stay_inside_pack_root(self):
        record = self._complete_record()
        record["filename"] = "../escape.tgz"
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "tarball path escapes",
        ):
            candidate.validate_pack_record(
                ROOT,
                record,
                ROOT / ".package-candidate-test-pack",
                expected_version=self.version,
                require_tarball=False,
            )

    def test_doctor_report_requires_exact_version_and_every_healthy_check(self):
        healthy = {
            "ok": True,
            "version": self.version,
            "checks": [
                {"name": name, "ok": True}
                for name in sorted(candidate.REQUIRED_DOCTOR_CHECKS)
            ],
        }
        candidate.validate_doctor_report(
            json.dumps(healthy),
            expected_version=self.version,
        )

        wrong_version = {**healthy, "version": "0.0.0"}
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            "version mismatch",
        ):
            candidate.validate_doctor_report(
                json.dumps(wrong_version),
                expected_version=self.version,
            )

        failed_name = sorted(candidate.REQUIRED_DOCTOR_CHECKS)[-1]
        unhealthy = {
            **healthy,
            "ok": False,
            "checks": [
                {
                    **item,
                    "ok": False if item["name"] == failed_name else item["ok"],
                }
                for item in healthy["checks"]
            ],
        }
        with self.assertRaisesRegex(
            candidate.PackageCandidateError,
            f"unhealthy checks: {re.escape(failed_name)}",
        ):
            candidate.validate_doctor_report(
                json.dumps(unhealthy),
                expected_version=self.version,
            )


if __name__ == "__main__":
    unittest.main()
