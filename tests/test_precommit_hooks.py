import json
import re
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
PRE_COMMIT_REPO = "https://github.com/NieZhuZhu/ai-harness-doctor"
EXACT_STABLE_REV = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")
FENCED_YAML = re.compile(r"^```ya?ml\n(.*?)\n```$", re.MULTILINE | re.DOTALL)


def documented_pre_commit_revs(text):
    """Return the configured rev for each fenced example of this repository."""
    revisions = []
    for block in FENCED_YAML.findall(text):
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if not re.fullmatch(rf"\s*-\s+repo:\s*{re.escape(PRE_COMMIT_REPO)}\s*", line):
                continue
            revision = None
            for following in lines[index + 1 :]:
                if re.fullmatch(r"\s*-\s+repo:\s*.+", following):
                    break
                match = re.fullmatch(r"\s*rev:\s*(\S+)\s*", following)
                if match:
                    revision = match.group(1)
                    break
            revisions.append(revision)
    return revisions


def has_current_exact_pre_commit_rev(text, expected):
    return bool(EXACT_STABLE_REV.fullmatch(expected)) and documented_pre_commit_revs(text) == [expected]


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
                self.assertIn(f"repo: {PRE_COMMIT_REPO}", text)

    def test_readme_pre_commit_examples_use_current_exact_release(self):
        version = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
        expected = f"v{version}"
        self.assertRegex(expected, EXACT_STABLE_REV)
        for name in README_FILES:
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                self.assertTrue(
                    has_current_exact_pre_commit_rev(text, expected),
                    f"{name} must contain exactly one {PRE_COMMIT_REPO} pre-commit "
                    f"example at {expected}; found {documented_pre_commit_revs(text)!r}",
                )

    def test_pre_commit_example_version_contract_rejects_stale_mutable_and_ambiguous_refs(self):
        def example(rev):
            revision = "" if rev is None else f"\n    rev: {rev}"
            return (
                "```yaml\n"
                "repos:\n"
                f"  - repo: {PRE_COMMIT_REPO}"
                f"{revision}\n"
                "    hooks:\n"
                "      - id: ai-harness-doctor-drift\n"
                "```"
            )

        current = "v" + json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["version"]
        self.assertTrue(has_current_exact_pre_commit_rev(example(current), current))
        for bad in ("v0.0.1", "v1", "main"):
            with self.subTest(rev=bad):
                self.assertFalse(has_current_exact_pre_commit_rev(example(bad), current))
        self.assertFalse(has_current_exact_pre_commit_rev(example(None), current))
        duplicate = example(current) + "\n\n" + example(current)
        self.assertFalse(has_current_exact_pre_commit_rev(duplicate, current))


if __name__ == "__main__":
    unittest.main()
