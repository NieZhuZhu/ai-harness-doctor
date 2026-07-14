import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
SELF_TEST = ROOT / ".github" / "workflows" / "action-self-test.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
RELEASING = ROOT / "RELEASING.md"

MARKETPLACE_DESCRIPTION = (
    "Audit and drift-guard AGENTS.md and AI agent configs for stale commands/paths, "
    "conflicts, and security risks; emit SARIF."
)


class ActionMetadataTests(unittest.TestCase):
    def test_marketplace_metadata_is_complete_and_product_focused(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn('name: "AI Harness Doctor"', text)
        self.assertIn(f'description: "{MARKETPLACE_DESCRIPTION}"', text)
        self.assertIn('icon: "check-circle"', text)
        self.assertIn('color: "purple"', text)
        self.assertIn("using: composite", text)

    def test_selected_action_ref_is_the_default_implementation(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn('default: "bundled"', text)
        self.assertIn('ACTION_PATH: ${{ github.action_path }}', text)
        self.assertIn('cli="$ACTION_PATH/bin/cli.js"', text)

    def test_action_propagates_failures_and_validates_commands(self):
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("set -euo pipefail", text)
        self.assertIn("scan|drift)", text)
        self.assertIn('run_args=("$INPUT_COMMAND" "$INPUT_PATH" "--sarif")', text)
        self.assertNotIn("|| true", text)

    def test_repository_dogfoods_the_composite_action(self):
        text = SELF_TEST.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("uses: ./"), 2)
        self.assertIn("Validate SARIF output", text)
        self.assertIn("Assert invalid command failed", text)

    def test_release_only_triggers_for_full_semver_tags(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn('- "v*.*.*"', text)
        self.assertNotIn('- "v*"\n', text)

    def test_release_self_tests_before_publish_and_after_floating_tag(self):
        text = RELEASE.read_text(encoding="utf-8")
        preflight = text.index("Pre-publish Action self-test")
        publish = text.index("Publish to npm")
        floating = text.index("Update floating Action tag")
        public_test = text.index("Verify published floating Action")
        reminder = text.index("Create Marketplace confirmation reminder")
        self.assertLess(preflight, publish)
        self.assertLess(publish, floating)
        self.assertLess(floating, public_test)
        self.assertLess(public_test, reminder)
        self.assertIn("uses: ./", text)
        self.assertIn("Reject invalid tagged Action command", text)
        self.assertIn("Validate tagged Action failure propagation", text)
        self.assertIn("ref: v0", text)
        self.assertIn("path: published-action", text)
        self.assertIn("uses: ./published-action", text)
        self.assertIn("Verify floating tag target", text)

    def test_release_updates_v0_without_recursively_triggering_publish(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("group: release", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("--sort=-v:refname", text)
        self.assertIn('latest_tag" != "$GITHUB_REF_NAME', text)
        self.assertIn('git tag -f v0 "$release_commit"', text)
        self.assertIn("git push origin refs/tags/v0 --force", text)
        self.assertIn("contents: write", text)

    def test_release_creates_marketplace_confirmation_reminder(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("issues: write", text)
        self.assertIn("Marketplace release confirmation:", text)
        self.assertIn("AI Assisted", text)
        self.assertIn("Code review", text)
        self.assertIn("marketplace=true", text)

    def test_release_docs_use_the_maintained_v0_action_tag(self):
        release_docs = RELEASING.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("NieZhuZhu/ai-harness-doctor@v0", readme)
        self.assertNotIn("NieZhuZhu/ai-harness-doctor@v1", readme)
        self.assertIn("floating `v0`", release_docs)
        self.assertIn("Marketplace", release_docs)


if __name__ == "__main__":
    unittest.main()
