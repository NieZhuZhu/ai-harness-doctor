import json
import os
import re
import subprocess
import textwrap
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from tmp_support import ResilientTemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / "action.yml"
SELF_TEST = ROOT / ".github" / "workflows" / "action-self-test.yml"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
DEPRECATE = ROOT / ".github" / "workflows" / "deprecate.yml"
RELEASING = ROOT / "RELEASING.md"
HARNESS_DRIFT = ROOT / ".github" / "workflows" / "harness-drift.yml"
HARNESS_DRIFT_TEMPLATE = ROOT / "assets" / "guard" / "harness-drift.yml"
HARNESS_CHECKUP = ROOT / ".github" / "workflows" / "harness-checkup.yml"
SCAN_BASELINE = ROOT / ".ai-harness-doctor" / "scan-baseline.json"
GUARD_ASSETS = ROOT / "assets" / "guard"
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
PACKAGE_LOCK = ROOT / "package-lock.json"
SECURITY = ROOT / "SECURITY.md"
CODE_OF_CONDUCT = ROOT / "CODE_OF_CONDUCT.md"
SUPPORT = ROOT / "SUPPORT.md"
ISSUE_TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
PULL_REQUEST_TEMPLATE = ROOT / ".github" / "pull_request_template.md"

ACTION_PINS = {
    "actions/checkout": ("9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", "v7"),
    "actions/setup-node": ("820762786026740c76f36085b0efc47a31fe5020", "v7"),
    "actions/setup-python": ("ece7cb06caefa5fff74198d8649806c4678c61a1", "v6"),
    "actions/upload-artifact": ("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "v7"),
}
LOCAL_ACTIONS = {"./", "./published-action"}

MARKETPLACE_DESCRIPTION = (
    "Audit and drift-guard AGENTS.md and AI agent configs for stale commands/paths, "
    "conflicts, and security risks; emit SARIF."
)


class ActionMetadataTests(unittest.TestCase):
    def _workflow_paths(self):
        roots = (ROOT / ".github" / "workflows", GUARD_ASSETS)
        return sorted(
            {
                path
                for root in roots
                for pattern in ("*.yml", "*.yaml")
                for path in root.rglob(pattern)
            }
        )

    def _pull_request_trigger_block(self, path):
        lines = path.read_text(encoding="utf-8").splitlines()
        try:
            start = lines.index("  pull_request:")
        except ValueError:
            self.fail(f"{path} must define a pull_request trigger")
        body = []
        for line in lines[start + 1 :]:
            if line.startswith("  ") and not line.startswith("    "):
                break
            body.append(line)
        return "\n".join(body)

    def _named_step_block(self, path, name):
        text = path.read_text(encoding="utf-8")
        marker = f"      - name: {name}\n"
        try:
            start = text.index(marker)
        except ValueError:
            self.fail(f"{path} must define step {name!r}")
        end = text.find("\n      - ", start + len(marker))
        return text[start : end if end != -1 else len(text)]

    def _run_script(self, path, name):
        block = self._named_step_block(path, name)
        match = re.search(r"(?ms)^        run: \|\n(?P<body>.*)$", block)
        self.assertIsNotNone(match, f"{path} step {name!r} must use a run block")
        return textwrap.dedent(match.group("body"))

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
        self.assertGreaterEqual(text.count("uses: ./"), 3)
        self.assertIn("Validate SARIF output", text)
        self.assertIn("Reject a tail credential through the repository Action", text)
        self.assertIn("--max-bytes 100 --fail-on-security", text)
        self.assertIn('item.ruleId === "security/secret"', text)
        self.assertIn('raw.includes("ghp_")', text)
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

    def test_shipped_guard_templates_use_only_public_cli_commands(self):
        shipped = [
            HARNESS_DRIFT_TEMPLATE,
            GUARD_ASSETS / "harness-checkup.yml",
            GUARD_ASSETS / "gitlab" / "harness-ci.yml",
            GUARD_ASSETS / "codebase" / "harness-guard.sh",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in shipped)
        self.assertNotIn("python3 scripts/", combined)
        self.assertNotIn("scripts/pr_review.py", combined)
        self.assertIn("ai-harness-doctor@latest review", combined)
        self.assertIn("ai-harness-doctor@latest eval --score", combined)

    def test_repository_dogfoods_local_scan_baseline_and_drift(self):
        drift = HARNESS_DRIFT.read_text(encoding="utf-8")
        checkup = HARNESS_CHECKUP.read_text(encoding="utf-8")
        combined = drift + checkup
        self.assertTrue(SCAN_BASELINE.is_file())
        self.assertIn("node bin/cli.js scan .", drift)
        self.assertIn("--baseline .ai-harness-doctor/scan-baseline.json", combined)
        for gate in (
            "--fail-on-security",
            "--fail-on-gaps",
            "--fail-on-semantic",
            "--fail-on-conflicts",
        ):
            self.assertIn(gate, combined)
        self.assertIn("node bin/cli.js scan . --json", drift)
        self.assertIn("node bin/cli.js drift . --strict --json > drift-report.json", drift)
        self.assertIn('exit "$scan_status"', drift)
        self.assertIn('exit "$drift_status"', drift)
        self.assertIn("steps.scan.outputs.status", checkup)
        self.assertIn("🩺 Harness checkup: issues detected", checkup)
        self.assertNotIn("--write-baseline", combined)

    def test_repository_eval_gate_requires_current_committed_evidence(self):
        drift = HARNESS_DRIFT.read_text(encoding="utf-8")
        self.assertIn("Eval evidence and health gate", drift)
        self.assertIn("--score \"$RESULTS\"", drift)
        self.assertIn("--tasks benchmark/self-eval/tasks.json", drift)
        self.assertIn("--evidence AGENTS.md", drift)
        self.assertIn("--require-current-evidence", drift)
        self.assertIn("--fail-under 80", drift)
        self.assertNotIn("No committed eval results", drift)
        self.assertNotIn('if [ -f "$RESULTS" ]', drift)

    def test_github_guard_posts_one_combined_scan_and_drift_review(self):
        for path in (HARNESS_DRIFT_TEMPLATE, HARNESS_DRIFT):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(text.count("> scan-report.json"), 1)
                self.assertEqual(text.count("> drift-report.json"), 1)
                self.assertEqual(text.count("--report scan-report.json"), 1)
                self.assertEqual(text.count("--report drift-report.json"), 1)
                self.assertEqual(text.count("--post"), 1)

    def test_github_guard_runs_on_every_pull_request(self):
        # D2/D7 can depend on any repo-relative path named by AGENTS.md, so no
        # finite path allow-list can cover every drift/security input. Both the
        # shipped guard and this repo's adapted self-guard must run on every PR.
        for path in (HARNESS_DRIFT_TEMPLATE, HARNESS_DRIFT):
            with self.subTest(path=path):
                trigger = self._pull_request_trigger_block(path)
                self.assertNotIn("paths:", trigger)
                self.assertNotIn("paths-ignore:", trigger)

    def test_external_actions_are_immutable_current_major_pins(self):
        external_pattern = re.compile(
            r"uses:\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})"
            r"\s+#\s+\1@(v\d+)\s*$"
        )
        local_pattern = re.compile(r"uses:\s+(\./[^\s#]*)\s*$")
        for path in self._workflow_paths():
            with self.subTest(path=path):
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if "uses:" not in line:
                        continue
                    local_match = local_pattern.search(line)
                    if local_match:
                        self.assertIn(local_match.group(1), LOCAL_ACTIONS, f"{path}:{lineno}: unvetted local Action")
                        continue
                    match = external_pattern.search(line)
                    self.assertIsNotNone(match, f"{path}:{lineno}: mutable or undocumented Action ref")
                    action, sha, major = match.groups()
                    self.assertIn(action, ACTION_PINS, f"{path}:{lineno}: unvetted Action {action}")
                    self.assertEqual((sha, major), ACTION_PINS[action], f"{path}:{lineno}")

    def test_test_workflow_runs_push_matrix_only_on_main(self):
        text = TEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("push:\n    branches: [main]", text)
        self.assertIn("pull_request:", text)
        self.assertNotIn("on:\n  push:\n  pull_request:", text)

    def test_dependabot_updates_github_action_pins_weekly(self):
        text = DEPENDABOT.read_text(encoding="utf-8")
        self.assertIn('package-ecosystem: "github-actions"', text)
        self.assertIn('package-ecosystem: "npm"', text)
        self.assertEqual(text.count('interval: "weekly"'), 2)
        self.assertIn('dependency-type: "development"', text)
        self.assertIn('interval: "weekly"', text)

    def test_public_lockfile_uses_only_the_public_npm_registry(self):
        lockfile = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
        checked = 0
        invalid = []
        for package, metadata in lockfile.get("packages", {}).items():
            if not isinstance(metadata, dict) or not metadata.get("resolved"):
                continue
            checked += 1
            parsed = urlsplit(metadata["resolved"])
            if (
                parsed.scheme != "https"
                or parsed.hostname != "registry.npmjs.org"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                # Report only the package and parsed host/scheme. Never echo a
                # credential-bearing or query-bearing source URL into CI logs.
                invalid.append(
                    f"{package}: scheme={parsed.scheme or '<missing>'}, "
                    f"host={parsed.hostname or '<missing>'}"
                )
        self.assertGreater(checked, 0, "package-lock.json must contain resolved dependency sources")
        self.assertEqual(invalid, [], "non-public npm lockfile source(s): " + "; ".join(invalid))

    def test_public_repository_community_health_files_are_safe_and_actionable(self):
        for path in (SECURITY, CODE_OF_CONDUCT, SUPPORT, PULL_REQUEST_TEMPLATE):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)
                self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 100)

        security = SECURITY.read_text(encoding="utf-8")
        self.assertIn("/security/advisories/new", security)
        self.assertIn("Do **not** open a public issue", security)
        self.assertIn("Never include a live secret", security)

        conduct = CODE_OF_CONDUCT.read_text(encoding="utf-8")
        self.assertIn("Contributor Covenant", conduct)
        self.assertNotIn("INSERT CONTACT", conduct)
        self.assertIn("report-abuse", conduct)

        support = SUPPORT.read_text(encoding="utf-8")
        self.assertIn("SECURITY.md", support)
        self.assertIn("CODE_OF_CONDUCT.md", support)
        self.assertIn("does not currently operate a discussion forum", support)

        pull_request = PULL_REQUEST_TEMPLATE.read_text(encoding="utf-8")
        for required in (
            "Release classification",
            "npm run check",
            "strict drift",
            "isolated `HOME`",
            "Eval evidence",
        ):
            self.assertIn(required, pull_request)

    def test_issue_forms_cover_bugs_findings_features_and_private_security(self):
        expected = {
            "bug.yml": ("Bug report", "Minimal repository shape", "Safety confirmation"),
            "false-positive.yml": (
                "False positive or false negative",
                "Minimal synthetic input",
                "no credential value",
            ),
            "feature.yml": ("Feature request", "Desired doctor outcome", "Project boundaries"),
        }
        for filename, needles in expected.items():
            path = ISSUE_TEMPLATES / filename
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("name:"))
                self.assertIn("body:", text)
                self.assertIn("validations:", text)
                for needle in needles:
                    self.assertIn(needle, text)

        config = (ISSUE_TEMPLATES / "config.yml").read_text(encoding="utf-8")
        self.assertIn("blank_issues_enabled: false", config)
        self.assertIn("/security/advisories/new", config)
        self.assertIn("SUPPORT.md", config)

    def test_release_only_triggers_for_full_semver_tags(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn('- "v*.*.*"', text)
        self.assertNotIn('- "v*"\n', text)

    def test_deprecate_inputs_are_env_only_and_exact_semver_is_validated(self):
        block = self._named_step_block(DEPRECATE, "Deprecate npm version")
        script = self._run_script(DEPRECATE, "Deprecate npm version")
        self.assertIn("VERSION: ${{ inputs.version }}", block)
        self.assertIn("MESSAGE: ${{ inputs.message }}", block)
        self.assertNotIn("${{ inputs.", script)
        self.assertIn('npm deprecate "ai-harness-doctor@$VERSION" "$MESSAGE"', script)
        self.assertIn("set -euo pipefail", script)
        self.assertIn("exact SemVer", script)
        self.assertIn("message.trim()", script)

        node_match = re.search(r"(?ms)^node <<'NODE'\n(?P<script>.*?)^NODE$", script)
        self.assertIsNotNone(node_match, "deprecate validation must be an extractable Node heredoc")
        validator = node_match.group("script")

        valid = ("0.0.0", "1.2.3", "1.2.3-0", "1.2.3-beta.1", "10.20.30-rc-1")
        invalid = ("", "v1.2.3", "1.2", "1.2.3+build", "01.2.3", "1.02.3", "1.2.3-", "1.x", "^1.2.3")
        for version in valid:
            with self.subTest(version=version, expected="valid"):
                proc = subprocess.run(
                    ["node"],
                    input=validator,
                    text=True,
                    capture_output=True,
                    env={**os.environ, "VERSION": version, "MESSAGE": "Use a supported release."},
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
        for version in invalid:
            with self.subTest(version=version, expected="invalid"):
                proc = subprocess.run(
                    ["node"],
                    input=validator,
                    text=True,
                    capture_output=True,
                    env={**os.environ, "VERSION": version, "MESSAGE": "Use a supported release."},
                )
                self.assertNotEqual(proc.returncode, 0)

        empty_message = subprocess.run(
            ["node"],
            input=validator,
            text=True,
            capture_output=True,
            env={**os.environ, "VERSION": "1.2.3", "MESSAGE": "   "},
        )
        self.assertNotEqual(empty_message.returncode, 0)

    def test_release_tag_must_be_reachable_from_main_before_npm_access(self):
        text = RELEASE.read_text(encoding="utf-8")
        step_name = "Verify release tag is reachable from main"
        script = self._run_script(RELEASE, step_name)
        ancestry = text.index(step_name)
        npm_lookup = text.index("Check whether this version is already on npm")
        publish = text.index("Publish to npm")
        self.assertLess(ancestry, npm_lookup)
        self.assertLess(ancestry, publish)
        self.assertIn('git fetch --no-tags origin "+refs/heads/main:refs/remotes/origin/main"', script)
        self.assertIn('git rev-parse --verify "$GITHUB_REF_NAME^{commit}"', script)
        self.assertIn('git merge-base --is-ancestor "$release_commit" refs/remotes/origin/main', script)
        self.assertNotIn("continue-on-error", self._named_step_block(RELEASE, step_name))
        self.assertNotIn("|| true", script)

        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            remote = base / "remote.git"
            repo = base / "repo"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "package.json").write_text('{"version":"1.0.0"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "package.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "main release"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
            subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo, check=True, capture_output=True)

            good = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script],
                cwd=repo,
                env={**os.environ, "GITHUB_REF_NAME": "v1.0.0"},
                text=True,
                capture_output=True,
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)

            subprocess.run(["git", "switch", "-c", "unreviewed"], cwd=repo, check=True, capture_output=True)
            (repo / "package.json").write_text('{"version":"1.0.1"}\n', encoding="utf-8")
            subprocess.run(["git", "add", "package.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "unreviewed release"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "tag", "v1.0.1"], cwd=repo, check=True)

            rejected = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script],
                cwd=repo,
                env={**os.environ, "GITHUB_REF_NAME": "v1.0.1"},
                text=True,
                capture_output=True,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("not reachable from origin/main", rejected.stderr)

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

    def test_release_supersedes_only_exact_older_marketplace_reminders(self):
        text = RELEASE.read_text(encoding="utf-8")
        self.assertIn('^Marketplace release confirmation: v[0-9]+', text)
        self.assertIn('--state open', text)
        self.assertIn('if [ "$issue_title" = "$title" ]', text)
        self.assertIn('Superseded by Marketplace confirmation for $TAG.', text)
        self.assertIn('done < "$RUNNER_TEMP/marketplace-open.tsv"', text)
        cleanup = text.index("marketplace-open.tsv")
        dedupe = text.index('existing="$(')
        create = text.index("gh issue create")
        self.assertLess(cleanup, dedupe)
        self.assertLess(dedupe, create)

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
