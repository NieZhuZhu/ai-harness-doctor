import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".pre-commit-hooks.yaml"
PACKAGE_JSON = ROOT / "package.json"
README_FILES = (
    "README.md",
    "README.zh-CN.md",
    "README.ja.md",
    "README.es.md",
    "README.ko.md",
    "README.pt-BR.md",
    "README.fr.md",
)

# Public packaged subcommands a shipped hook is allowed to call.
PUBLIC_COMMANDS = {"scan", "drift"}


def parse_hooks(text):
    """Parse the flat list-of-mappings .pre-commit-hooks.yaml (stdlib only).

    The file is a simple YAML sequence of single-level mappings, so a tiny
    line parser is enough and avoids a third-party YAML dependency, matching
    the repository's standard-library-only constraint.
    """
    hooks = []
    current = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw
        if line.startswith("- "):
            if current is not None:
                hooks.append(current)
            current = {}
            line = line[2:]
        stripped = line.strip()
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            current[key.strip()] = value.strip()
    if current is not None:
        hooks.append(current)
    return hooks


class PreCommitHookTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOOKS.is_file(), ".pre-commit-hooks.yaml must exist")
        self.text = HOOKS.read_text(encoding="utf-8")
        self.hooks = parse_hooks(self.text)
        self.by_id = {h.get("id"): h for h in self.hooks}

    def test_defines_the_drift_and_scan_hooks(self):
        self.assertEqual(set(self.by_id), {"ai-harness-doctor-drift", "ai-harness-doctor-scan"})
        self.assertEqual(len(self.hooks), 2)

    def test_hooks_are_repo_wide_node_hooks(self):
        for hook_id, hook in self.by_id.items():
            with self.subTest(hook=hook_id):
                self.assertEqual(hook.get("language"), "node")
                self.assertEqual(hook.get("pass_filenames"), "false")
                self.assertEqual(hook.get("always_run"), "true")
                self.assertTrue(hook.get("name"), "hook needs a human-readable name")
                self.assertTrue(hook.get("description"), "hook needs a description")

    def test_entries_use_only_public_cli_commands(self):
        bin_name = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["bin"]
        self.assertIn("ai-harness-doctor", bin_name)
        self.assertNotIn("python3 scripts/", self.text)
        for hook_id, hook in self.by_id.items():
            self.assertNotIn("scripts/", hook.get("entry", ""), f"{hook_id} must not call source scripts")
        expected = {
            "ai-harness-doctor-drift": "ai-harness-doctor drift",
            "ai-harness-doctor-scan": "ai-harness-doctor scan --fail-on-security",
        }
        for hook_id, entry in expected.items():
            with self.subTest(hook=hook_id):
                self.assertEqual(self.by_id[hook_id].get("entry"), entry)
                tokens = entry.split()
                self.assertEqual(tokens[0], "ai-harness-doctor")
                self.assertIn(tokens[1], PUBLIC_COMMANDS)

    def test_readmes_document_the_pre_commit_hooks(self):
        for name in README_FILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                self.assertIn("ai-harness-doctor-drift", text)
                self.assertIn("ai-harness-doctor-scan", text)
                self.assertIn("repo: https://github.com/NieZhuZhu/ai-harness-doctor", text)


if __name__ == "__main__":
    unittest.main()
