"""Consistency guard for the shared agent-config registry.

Proves the single-source-of-truth invariant: scan.py (detection),
canonicalize.py (stub writing) and check_drift.py (stub drift guard) all agree on
the same tool set, and every scan-detectable tool is either migrated
(canonicalizable with stub_paths handled by both canonicalize and drift) or an
explicit, documented scan-only opt-out (canonicalizable: false).
"""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REGISTRY_JSON = ROOT / "assets" / "agent-tools.json"

sys.path.insert(0, str(SCRIPTS))
import registry  # noqa: E402
import scan  # noqa: E402
import canonicalize  # noqa: E402
import check_drift  # noqa: E402


class RegistryConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.reg = registry.load_registry()
        self.tools = self.reg["tools"]

    def test_registry_json_is_valid_and_well_formed(self):
        with REGISTRY_JSON.open(encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("tools", data)
        self.assertIn("canonical", data)
        for tool in data["tools"]:
            for key in ("id", "label", "scan_patterns", "stub_paths",
                        "stub_kind", "stub_content", "canonicalizable"):
                self.assertIn(key, tool, f"{tool.get('id')} missing {key}")
            self.assertIsInstance(tool["scan_patterns"], list)
            self.assertTrue(tool["scan_patterns"], f"{tool['id']} has no scan_patterns")

    def test_no_duplicate_tool_ids_or_labels(self):
        ids = [t["id"] for t in self.tools]
        labels = [t["label"] for t in self.tools]
        self.assertEqual(len(ids), len(set(ids)), "duplicate tool ids")
        self.assertEqual(len(labels), len(set(labels)), "duplicate tool labels")

    def test_scan_covers_every_registry_tool_and_canonical_file(self):
        """Every canonical file and tool label appears in scan.CONFIG_PATTERNS."""
        scanned_labels = {label for label, _ in scan.CONFIG_PATTERNS}
        for name in self.reg["canonical"]:
            self.assertIn(name, scanned_labels)
        for tool in self.tools:
            self.assertIn(tool["label"], scanned_labels)
            # The scan patterns for a tool are exactly what the registry declares.
            declared = [p for label, ps in scan.CONFIG_PATTERNS if label == tool["label"] for p in ps]
            self.assertEqual(declared, list(tool["scan_patterns"]))

    def test_canonicalizable_tools_are_handled_by_canonicalize_and_drift(self):
        """A migrated tool must have stub_paths wired into BOTH canonicalize and drift."""
        for tool in self.tools:
            if not tool["canonicalizable"]:
                continue
            self.assertTrue(tool["stub_paths"], f"{tool['id']} canonicalizable but has no stub_paths")
            self.assertIn(tool["id"], canonicalize.STUBS,
                          f"{tool['id']} missing from canonicalize.STUBS")
            self.assertEqual(canonicalize.STUBS[tool["id"]]["paths"], list(tool["stub_paths"]))
            self.assertEqual(canonicalize.STUBS[tool["id"]]["content"], tool["stub_content"])
            for path in tool["stub_paths"]:
                self.assertIn(path, check_drift.STUB_FILES,
                              f"{tool['id']} stub path {path} not guarded by check_drift")

    def test_scan_only_tools_are_explicitly_opted_out(self):
        """A tool with no stub form must be an explicit, documented opt-out."""
        for tool in self.tools:
            if tool["stub_paths"]:
                continue
            self.assertFalse(tool["canonicalizable"],
                             f"{tool['id']} has no stub_paths but is marked canonicalizable")
            self.assertTrue(tool.get("canonicalizable_note"),
                            f"{tool['id']} opted out without a documented reason")

    def test_no_tool_appears_in_one_stage_but_missing_from_another(self):
        """canonicalize.STUBS keys == drift-guarded tool ids == canonicalizable registry ids."""
        canonicalizable_ids = {t["id"] for t in self.tools if t["canonicalizable"] and t["stub_paths"]}
        self.assertEqual(set(canonicalize.STUBS.keys()), canonicalizable_ids)
        # Every path in the flat drift list belongs to a canonicalizable tool, and
        # every canonicalizable tool contributes all of its stub paths (no gaps).
        expected_drift = [p for t in self.tools if t["id"] in canonicalizable_ids for p in t["stub_paths"]]
        self.assertEqual(check_drift.STUB_FILES, expected_drift)

    def test_stub_content_is_non_empty_for_canonicalizable_tools(self):
        for tool in self.tools:
            if tool["canonicalizable"]:
                self.assertTrue(tool["stub_content"].strip(),
                                f"{tool['id']} canonicalizable but stub_content is empty")

    def test_roo_is_present_and_explicitly_scan_only(self):
        """Regression guard for the specific gap this refactor closes."""
        roo = next((t for t in self.tools if t["id"] == "roo"), None)
        self.assertIsNotNone(roo, "roo must be in the registry (previously scan-only, silently dropped)")
        self.assertFalse(roo["canonicalizable"])
        self.assertEqual(roo["stub_paths"], [])
        self.assertIn("Roo", roo["canonicalizable_note"])


if __name__ == "__main__":
    unittest.main()
