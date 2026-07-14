import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
SELF_TEST = ROOT / ".github" / "workflows" / "action-self-test.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
RELEASING = ROOT / "RELEASING.md"
HARNESS_DRIFT = ROOT / ".github" / "workflows" / "harness-drift.yml"
HARNESS_DRIFT_TEMPLATE = ROOT / "assets" / "guard" / "harness-drift.yml"

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

    def test_pr_review_workflows_anchor_comments_to_pull_request_head(self):
        head_sha = "${{ github.event.pull_request.head.sha }}"
        merge_sha = "${{ github.sha }}"
        for path in (HARNESS_DRIFT, HARNESS_DRIFT_TEMPLATE):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f'--commit "{head_sha}"', text)
                self.assertNotIn(f"--commit {merge_sha}", text)
                self.assertNotIn(f'--commit "{merge_sha}"', text)

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
        self.assertIn("ref: ${{ needs.publish.outputs.floating_tag }}", text)
        self.assertIn("path: published-action", text)
        self.assertIn("uses: ./published-action", text)
        self.assertIn("Verify floating tag target", text)

    def test_release_updates_dynamic_major_tag_without_recursively_triggering_publish(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("group: release", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn('major="${package_version%%.*}"', text)
        self.assertIn('floating_tag="v$major"', text)
        self.assertIn("floating_tag=$floating_tag", text)
        self.assertIn('git tag --list "$FLOATING_TAG.*.*" --sort=-v:refname', text)
        self.assertIn('latest_tag" != "$GITHUB_REF_NAME', text)
        self.assertIn('git tag -f "$FLOATING_TAG" "$release_commit"', text)
        self.assertIn('git push origin "refs/tags/$FLOATING_TAG" --force', text)
        self.assertNotIn("git tag -f v0", text)
        self.assertIn("contents: write", text)

    def test_release_routes_stable_and_prerelease_channels_safely(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("is_prerelease: ${{ steps.release_meta.outputs.is_prerelease }}", text)
        self.assertIn("npm_tag: ${{ steps.release_meta.outputs.npm_tag }}", text)
        self.assertIn('if [[ "$package_version" == *-* ]]; then', text)
        self.assertIn('is_prerelease="true"', text)
        self.assertIn('npm_tag="next"', text)
        self.assertIn('floating_tag=""', text)
        self.assertIn('is_prerelease="false"', text)
        self.assertIn('npm_tag="latest"', text)
        self.assertIn('floating_tag="v$major"', text)
        self.assertIn('echo "is_prerelease=$is_prerelease" >> "$GITHUB_OUTPUT"', text)
        self.assertIn('echo "npm_tag=$npm_tag" >> "$GITHUB_OUTPUT"', text)
        self.assertIn("NPM_TAG: ${{ steps.release_meta.outputs.npm_tag }}", text)
        self.assertIn('npm publish --provenance --access public --tag "$NPM_TAG"', text)

    def test_prereleases_do_not_move_or_verify_stable_action_refs(self):
        text = RELEASE.read_text(encoding="utf-8")
        stable_only = "if: steps.release_meta.outputs.is_prerelease != 'true'"
        self.assertIn(stable_only, text)
        self.assertGreaterEqual(
            text.count("needs.publish.outputs.is_prerelease != 'true'"),
            2,
        )
        self.assertIn('release_args+=(--prerelease)', text)
        self.assertIn("needs: [publish, verify-action]", text)
        self.assertIn('grep -v -- \'-\'', text)

    def test_release_creates_marketplace_confirmation_reminder(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn("issues: write", text)
        self.assertIn("Marketplace release confirmation:", text)
        self.assertIn("categories include AI Assisted and Code review", text)
        self.assertNotIn("primary category", text)
        self.assertNotIn("secondary category", text)
        self.assertIn("marketplace=true", text)

    def test_release_docs_use_the_maintained_v1_action_tag(self):
        release_docs = RELEASING.read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("NieZhuZhu/ai-harness-doctor@v1", readme)
        self.assertNotIn("NieZhuZhu/ai-harness-doctor@v0", readme)
        self.assertIn("floating major tag", release_docs)
        self.assertIn("`1.x` -> `v1`", release_docs)
        self.assertIn("Marketplace", release_docs)


if __name__ == "__main__":
    unittest.main()
