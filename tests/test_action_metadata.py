import json
import os
import re
import subprocess
import sys
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

    def _job_block(self, path, job):
        lines = path.read_text(encoding="utf-8").splitlines()
        try:
            start = lines.index(f"  {job}:", lines.index("jobs:"))
        except ValueError:
            self.fail(f"{path} must define job {job!r}")
        body = []
        for line in lines[start + 1 :]:
            if line and not line.startswith("    "):
                break
            body.append(line)
        return "\n".join(body)

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
        self.assertIn("args-json:", text)
        self.assertIn("INPUT_ARGS_JSON: ${{ inputs.args-json }}", text)
        self.assertIn(
            'node "$ACTION_PATH/bin/action-run.js" \\\n'
            '          "$cli" "$INPUT_SARIF_FILE" "$INPUT_COMMAND" "$INPUT_PATH"',
            text,
        )
        self.assertNotIn("read -r -a", text)
        self.assertNotIn('run_args=(', text)
        self.assertIn('cli_status=$?', text)
        self.assertIn('report_status=$?', text)
        self.assertIn(
            'node "$ACTION_PATH/bin/action-report.js" "$INPUT_SARIF_FILE" "$INPUT_COMMAND"',
            text,
        )
        self.assertIn('exit "$cli_status"', text)
        self.assertNotIn("|| true", text)
        for forbidden in ("eval ", "sh -c", "bash -c"):
            self.assertNotIn(forbidden, text)
        self.assertIn("first-line spaces/tabs split argv", text)
        self.assertIn("JSON array of exact extra CLI arguments", text)

    def test_action_exposes_composable_quality_outputs(self):
        text = ACTION.read_text(encoding="utf-8")
        for output in (
            "sarif-file",
            "status",
            "finding-count",
            "error-count",
            "warning-count",
            "note-count",
            "resolved-baseline-count",
            "health-score",
            "health-grade",
        ):
            self.assertIn(f"  {output}:\n", text)
            self.assertIn(f"steps.run.outputs.{output}", text)
        self.assertIn("GITHUB_STEP_SUMMARY", (ROOT / "bin" / "action-report.js").read_text())

    def test_action_run_helper_is_shipped_and_release_paths_use_the_wrapper(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertIn("bin", package["files"])
        self.assertTrue((ROOT / "bin" / "action-run.js").is_file())
        self.assertNotIn("!bin/action-run.js", package["files"])

        for name in (
            "Pre-publish bundled scan self-test",
            "Pre-publish bundled drift self-test",
            "Verify published floating bundled scan",
            "Verify published exact npm drift override",
        ):
            block = self._named_step_block(RELEASE, name)
            self.assertRegex(block, r"(?m)^        uses: \./(?:published-action)?$")
            self.assertNotIn("bin/cli.js", block)

    def test_repository_dogfoods_the_composite_action(self):
        text = SELF_TEST.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("uses: ./"), 6)
        self.assertIn("Run bundled scan against this checkout", text)
        self.assertIn("Run bundled drift against a clean fixture", text)
        self.assertIn("Run bundled scan against a Claude rule fixture", text)
        self.assertIn("Run exact published npm override", text)
        self.assertIn("Validate Action success matrix", text)
        self.assertIn("checkout_version=", text)
        self.assertIn("published_version=", text)
        self.assertIn("npm view ai-harness-doctor@latest version", text)
        self.assertIn("version: ${{ steps.fixture.outputs.published_version }}", text)
        self.assertNotIn("version: latest", text)
        self.assertIn("driver.version !== expected", text)
        self.assertIn('path.relative(temp, install).startsWith("..")', text)
        self.assertIn('"node_modules",', text)
        self.assertIn('.claude/rules/future.md', text)
        self.assertIn('paths:', text)
        self.assertIn('item.ruleId === "applicability/no-current-match"', text)
        self.assertIn("BUNDLED_DRIFT_SCORE", text)
        self.assertIn("BUNDLED_DRIFT_GRADE", text)
        self.assertIn("Expected findings output before failure", text)
        self.assertIn("finding-count output mismatch", text)
        self.assertIn("Report resolved baseline maintenance before failure", text)
        self.assertIn("resolved baseline repo", text)
        self.assertIn("drift baseline.json", text)
        self.assertIn("args-json: >-", text)
        self.assertIn("Expected maintenance output", text)
        self.assertIn("resolved-baseline-count", text)
        self.assertIn("Reject malformed structured Action arguments", text)
        self.assertIn("Reject conflicting Action argument inputs", text)
        self.assertIn("Reject shell metacharacters as opaque arguments", text)
        self.assertIn("Assert structured argument failures are side-effect free", text)
        self.assertIn("action-run-pwned", text)
        for name in (
            "Run bundled scan against this checkout",
            "Run bundled drift against a clean fixture",
            "Run bundled scan against a Claude rule fixture",
            "Run exact published npm override",
        ):
            self.assertNotIn(
                "continue-on-error",
                self._named_step_block(SELF_TEST, name),
            )
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

    def test_checkup_issue_lifecycle_is_symmetric_and_exact_title_owned(self):
        for path in (GUARD_ASSETS / "harness-checkup.yml", HARNESS_CHECKUP):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                block = self._named_step_block(path, "Reconcile harness issue")
                self.assertIn("if: always()", block)
                self.assertIn("CHECKUP_STATUS: ${{ steps.drift.outputs.status }}", block)
                self.assertIn("RUN_URL:", block)
                self.assertIn("COMMIT_SHA:", block)
                self.assertIn('--search "$TITLE in:title"', block)
                self.assertIn("select(.title == env.TITLE)", block)
                self.assertIn("][0] // empty", block)
                self.assertNotIn("head -n 1", block)
                self.assertIn('if [ "$CHECKUP_STATUS" != "0" ]', block)
                self.assertIn("gh issue comment", block)
                self.assertIn("gh issue create", block)
                self.assertIn("gh issue close", block)
                self.assertIn("Harness checkup recovered", block)
                self.assertIn("no open incident issue", block)
                self.assertNotIn("|| true", block)
                self.assertIn("if: always()", self._named_step_block(path, "Upload harness checkup report"))
                self.assertIn("🩺 Harness checkup: issues detected", text)

        shipped = (GUARD_ASSETS / "harness-checkup.yml").read_text(encoding="utf-8")
        self.assertIn("Fail when harness issues remain", shipped)
        self.assertIn('exit "$CHECKUP_STATUS"', shipped)
        self.assertNotIn("Fail when harness issues remain", HARNESS_CHECKUP.read_text(encoding="utf-8"))

    def test_checkup_issue_shell_handles_create_update_recovery_and_noop(self):
        script = self._run_script(GUARD_ASSETS / "harness-checkup.yml", "Reconcile harness issue")
        title = "🩺 Harness checkup: issues detected"
        scenarios = [
            ("create", "3", "", ["create"], []),
            ("update", "3", "17", ["comment"], []),
            ("recover", "0", "17", ["close"], []),
            ("healthy", "0", "", [], ["create", "comment", "close"]),
            (
                "unrelated",
                "0",
                "",
                [],
                ["create", "comment", "close"],
            ),
        ]
        for name, status, issue_number, required, forbidden in scenarios:
            with self.subTest(name=name), ResilientTemporaryDirectory() as td:
                root = Path(td)
                fake_gh = root / "gh"
                log = root / "gh.log"
                fake_gh.write_text(
                    "#!/bin/sh\n"
                    "set -eu\n"
                    "printf '%s\\n' \"$*\" >> \"$GH_TEST_LOG\"\n"
                    "if [ \"${1:-}\" = issue ] && [ \"${2:-}\" = list ]; then\n"
                    "  printf '%s\\n' \"$GH_TEST_ISSUE_NUMBER\"\n"
                    "fi\n",
                    encoding="utf-8",
                )
                fake_gh.chmod(0o755)
                (root / "harness-checkup-report.md").write_text("# report\n", encoding="utf-8")
                env = os.environ.copy()
                env.update(
                    {
                        "PATH": f"{root}{os.pathsep}{env.get('PATH', '')}",
                        "GH_TEST_LOG": str(log),
                        "GH_TEST_ISSUE_NUMBER": issue_number,
                        "CHECKUP_STATUS": status,
                        "TITLE": title,
                        "RUN_URL": "https://example.invalid/run/1",
                        "COMMIT_SHA": "a" * 40,
                    }
                )

                proc = subprocess.run(
                    ["bash", "-c", script],
                    cwd=root,
                    env=env,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(proc.returncode, 0, proc.stderr)
                calls = log.read_text(encoding="utf-8") if log.exists() else ""
                for operation in required:
                    self.assertIn(f"issue {operation}", calls)
                for operation in forbidden:
                    self.assertNotIn(f"issue {operation}", calls)
                if name == "recover":
                    self.assertIn("Harness checkup recovered", calls)
                    self.assertIn("example.invalid/run/1", calls)

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

    def test_lint_ci_installs_the_reviewed_npm_lock_exactly(self):
        block = self._named_step_block(TEST_WORKFLOW, "Install Node dev dependencies")
        expected = "npm ci --ignore-scripts --no-audit --no-fund"
        match = re.search(r"(?m)^        run:\s+(.+)$", block)
        self.assertIsNotNone(match, "dependency install step must have one inline run command")
        script = match.group(1).strip()
        self.assertEqual(script, expected)
        self.assertNotIn("yarn", block.lower())
        self.assertNotIn("pnpm", block.lower())
        self.assertNotIn("npm install", script)

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        lockfile = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
        root_record = lockfile["packages"][""]
        self.assertEqual(root_record.get("devDependencies"), package.get("devDependencies"))
        for name in sorted(package.get("devDependencies", {})):
            record = lockfile["packages"].get(f"node_modules/{name}")
            self.assertIsInstance(record, dict, name)
            self.assertRegex(str(record.get("version", "")), r"^\d+\.\d+\.\d+")
            self.assertTrue(record.get("integrity"), name)
            parsed = urlsplit(record.get("resolved", ""))
            self.assertEqual(parsed.scheme, "https", name)
            self.assertEqual(parsed.hostname, "registry.npmjs.org", name)

    def test_required_ci_verifies_the_packed_candidate_once(self):
        text = TEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("Verify packed npm candidate"), 1)
        block = self._named_step_block(
            TEST_WORKFLOW,
            "Verify packed npm candidate",
        )
        self.assertIn("run: npm run check:package", block)
        self.assertNotIn("npm pack --dry-run", text)

        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"].get("check:package"),
            "python3 scripts/check_package_candidate.py",
        )
        self.assertEqual(
            package["scripts"]["check"],
            "npm run lint && npm test && npm run check:package",
        )
        self.assertIn("!scripts/check_package_candidate.py", package["files"])

    def test_local_all_green_check_includes_the_packed_candidate(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(
            package["scripts"]["check"],
            "npm run lint && npm test && npm run check:package",
        )
        self.assertEqual(
            package["scripts"].get("check:package"),
            "python3 scripts/check_package_candidate.py",
        )

        text = TEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count("npm run check:package"), 1)
        self.assertIn("run: npm run check:package", self._job_block(TEST_WORKFLOW, "lint"))
        for job in ("unittest", "node"):
            with self.subTest(job=job):
                # "npm run check" also matches "npm run check:package", so this
                # keeps the matrix jobs free of both entry points at once.
                self.assertNotIn("npm run check", self._job_block(TEST_WORKFLOW, job))

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
        npm_lookup = text.index("Verify published npm identity or mark version unpublished")
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

    def _run_release_identity(
        self,
        mode,
        git_head=None,
        registry_shasum=None,
        pack_shasum=None,
        registry_version="1.2.3",
        annotated=False,
    ):
        script = self._run_script(RELEASE, "Verify published npm identity or mark version unpublished")
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            runner_temp = base / "runner"
            bin_dir = base / "bin"
            repo.mkdir()
            runner_temp.mkdir()
            bin_dir.mkdir()
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "package.json").write_text(
                '{"name":"ai-harness-doctor","version":"1.2.3"}\n',
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "package.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "release"], cwd=repo, check=True, capture_output=True)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            tag_args = ["git", "tag"]
            if annotated:
                tag_args.extend(["-a", "-m", "release"])
            tag_args.append("v1.2.3")
            subprocess.run(tag_args, cwd=repo, check=True)

            npm = bin_dir / "npm"
            npm.write_text(
                f"#!{sys.executable}\n"
                "import json, os, sys\n"
                "command = sys.argv[1] if len(sys.argv) > 1 else ''\n"
                "if command == 'view':\n"
                "    mode = os.environ['MOCK_NPM_MODE']\n"
                "    if mode == 'missing':\n"
                "        print(json.dumps({'error': {'code': 'E404'}}))\n"
                "        raise SystemExit(1)\n"
                "    if mode == 'network':\n"
                "        print(json.dumps({'error': {'code': 'ECONNRESET'}}))\n"
                "        raise SystemExit(1)\n"
                "    if mode == 'malformed-json':\n"
                "        print('not-json')\n"
                "        raise SystemExit(1)\n"
                "    print(json.dumps({\n"
                "        'version': os.environ.get('MOCK_VERSION', '1.2.3'),\n"
                "        'gitHead': os.environ.get('MOCK_GIT_HEAD'),\n"
                "        'dist.shasum': os.environ.get('MOCK_REGISTRY_SHASUM'),\n"
                "    }))\n"
                "elif command == 'pack':\n"
                "    if os.environ['MOCK_NPM_MODE'] == 'pack-malformed':\n"
                "        print(json.dumps([]))\n"
                "    else:\n"
                "        print(json.dumps([{'shasum': os.environ.get('MOCK_PACK_SHASUM')}]))\n"
                "else:\n"
                "    raise SystemExit('unexpected npm command: ' + command)\n",
                encoding="utf-8",
            )
            npm.chmod(0o755)
            output = base / "github-output"
            env = {
                **os.environ,
                "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                "GITHUB_REF_NAME": "v1.2.3",
                "GITHUB_OUTPUT": str(output),
                "RUNNER_TEMP": str(runner_temp),
                "MOCK_NPM_MODE": mode,
                "MOCK_GIT_HEAD": git_head if git_head is not None else commit,
                "MOCK_VERSION": registry_version,
                "MOCK_REGISTRY_SHASUM": registry_shasum if registry_shasum is not None else "a" * 40,
                "MOCK_PACK_SHASUM": pack_shasum if pack_shasum is not None else "a" * 40,
            }
            proc = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
            )
            return proc, output.read_text(encoding="utf-8") if output.exists() else "", commit

    def test_release_existing_version_requires_matching_source_and_artifact_identity(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                proc, output, _commit = self._run_release_identity("present", annotated=annotated)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertIn("already_published=true", output)

        mismatches = [
            {"git_head": "b" * 40, "expected": "gitHead does not match"},
            {"git_head": "not-a-commit", "expected": "gitHead is missing or malformed"},
            {"registry_version": "1.2.4", "expected": "version does not match"},
            {"registry_shasum": "not-a-sha", "expected": "dist.shasum is missing or malformed"},
            {"pack_shasum": "b" * 40, "expected": "pack shasum does not match"},
            {"mode": "pack-malformed", "expected": "pack metadata is missing or malformed"},
        ]
        for case in mismatches:
            with self.subTest(case=case):
                params = dict(case)
                expected = params.pop("expected")
                mode = params.pop("mode", "present")
                proc, output, _commit = self._run_release_identity(mode, **params)
                self.assertNotEqual(proc.returncode, 0)
                self.assertNotIn("already_published=true", output)
                self.assertIn(expected, proc.stderr)

    def test_release_distinguishes_npm_not_found_from_lookup_failure(self):
        missing, output, _commit = self._run_release_identity("missing")
        self.assertEqual(missing.returncode, 0, missing.stdout + missing.stderr)
        self.assertIn("already_published=false", output)

        for mode in ("network", "malformed-json"):
            with self.subTest(mode=mode):
                failed, output, _commit = self._run_release_identity(mode)
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn("already_published=false", output)
                self.assertNotIn("already_published=true", output)

    def test_release_identity_guard_precedes_every_release_write(self):
        text = RELEASE.read_text(encoding="utf-8")
        guard = text.index("Verify published npm identity or mark version unpublished")
        self.assertLess(guard, text.index("Publish to npm"))
        self.assertLess(guard, text.index("Create GitHub Release if missing"))
        self.assertLess(guard, text.index("Update floating Action tag"))
        script = self._run_script(RELEASE, "Verify published npm identity or mark version unpublished")
        self.assertIn('git rev-parse --verify "$GITHUB_REF_NAME^{commit}"', script)
        self.assertIn("gitHead", script)
        self.assertIn("dist.shasum", script)
        self.assertIn("npm pack --dry-run --json", script)
        self.assertNotIn("|| true", script)

    def test_release_visibility_retries_the_exact_action_install_path(self):
        script = self._run_script(RELEASE, "Wait for exact npm package visibility")
        with ResilientTemporaryDirectory() as td:
            base = Path(td)
            runner_temp = base / "runner"
            bin_dir = base / "bin"
            call_log = base / "npm-calls.jsonl"
            attempt_file = base / "npm-attempt"
            runner_temp.mkdir()
            bin_dir.mkdir()

            npm = bin_dir / "npm"
            npm.write_text(
                f"#!{sys.executable}\n"
                "import json, os, pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "with open(os.environ['MOCK_NPM_CALLS'], 'a', encoding='utf-8') as stream:\n"
                "    stream.write(json.dumps(args) + '\\n')\n"
                "if not args or args[0] != 'install':\n"
                "    raise SystemExit('expected an install probe')\n"
                "attempt_file = pathlib.Path(os.environ['MOCK_NPM_ATTEMPT'])\n"
                "attempt = int(attempt_file.read_text() or '0') if attempt_file.exists() else 0\n"
                "attempt_file.write_text(str(attempt + 1))\n"
                "if attempt == 0:\n"
                "    print('npm error code ETARGET', file=sys.stderr)\n"
                "    raise SystemExit(1)\n"
                "prefix = pathlib.Path(args[args.index('--prefix') + 1])\n"
                "package = prefix / 'node_modules' / 'ai-harness-doctor'\n"
                "package.mkdir(parents=True)\n"
                "(package / 'package.json').write_text(\n"
                "    json.dumps({'version': os.environ['PACKAGE_VERSION']}) + '\\n'\n"
                ")\n",
                encoding="utf-8",
            )
            npm.chmod(0o755)
            sleep = bin_dir / "sleep"
            sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            sleep.chmod(0o755)

            proc = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", script],
                env={
                    **os.environ,
                    "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                    "RUNNER_TEMP": str(runner_temp),
                    "PACKAGE_VERSION": "1.2.3",
                    "MOCK_NPM_CALLS": str(call_log),
                    "MOCK_NPM_ATTEMPT": str(attempt_file),
                },
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            calls = [
                json.loads(line)
                for line in call_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(calls), 2)
            for call in calls:
                self.assertEqual(call[0], "install")
                self.assertIn("ai-harness-doctor@1.2.3", call)
                self.assertIn("--prefix", call)
                self.assertIn("--no-audit", call)
                self.assertIn("--no-fund", call)
                self.assertIn("--ignore-scripts", call)
            self.assertIn("Waiting for ai-harness-doctor@1.2.3", proc.stdout)
            self.assertIn("Verified ai-harness-doctor@1.2.3", proc.stdout)
            self.assertFalse((runner_temp / "npm-visibility").exists())

    def test_release_self_tests_before_publish_and_after_floating_tag(self):
        text = RELEASE.read_text(encoding="utf-8")
        candidate = text.index("Verify packed npm candidate")
        preflight_scan = text.index("Pre-publish bundled scan self-test")
        preflight_drift = text.index("Pre-publish bundled drift self-test")
        publish = text.index("Publish to npm")
        floating = text.index("Update floating Action tag")
        public_bundled = text.index("Verify published floating bundled scan")
        npm_visibility = text.index("Wait for exact npm package visibility")
        public_npm = text.index("Verify published exact npm drift override")
        public_matrix = text.index("Validate published Action success matrix")
        reminder = text.index("Create Marketplace confirmation reminder")
        self.assertLess(candidate, preflight_scan)
        self.assertLess(preflight_scan, publish)
        self.assertLess(preflight_drift, publish)
        self.assertLess(publish, floating)
        self.assertLess(floating, public_bundled)
        self.assertLess(public_bundled, npm_visibility)
        self.assertLess(npm_visibility, public_npm)
        self.assertLess(public_npm, public_matrix)
        self.assertLess(public_matrix, reminder)
        self.assertGreaterEqual(text.count("uses: ./"), 5)
        self.assertIn("command: scan", self._named_step_block(RELEASE, "Pre-publish bundled scan self-test"))
        self.assertIn("command: drift", self._named_step_block(RELEASE, "Pre-publish bundled drift self-test"))
        self.assertNotIn(
            "version:",
            self._named_step_block(RELEASE, "Pre-publish bundled scan self-test"),
        )
        self.assertNotIn(
            "version:",
            self._named_step_block(RELEASE, "Pre-publish bundled drift self-test"),
        )
        self.assertIn("Reject invalid tagged Action command", text)
        self.assertIn("Validate tagged Action failure propagation", text)
        self.assertIn("ref: ${{ needs.publish.outputs.floating_tag }}", text)
        self.assertIn("path: published-action", text)
        self.assertIn("uses: ./published-action", text)
        self.assertIn("Verify floating tag target", text)
        self.assertIn(
            "package_version: ${{ steps.release_meta.outputs.package_version }}",
            text,
        )
        self.assertIn(
            'echo "package_version=$package_version" >> "$GITHUB_OUTPUT"',
            text,
        )
        visibility = self._run_script(
            RELEASE,
            "Wait for exact npm package visibility",
        )
        self.assertIn('"ai-harness-doctor@$PACKAGE_VERSION"', visibility)
        self.assertIn("npm install", visibility)
        self.assertIn("--prefix", visibility)
        self.assertNotIn("npm pack", visibility)
        self.assertIn("for attempt in {1..12}", visibility)
        self.assertNotIn("@latest", visibility)
        self.assertNotIn("|| true", visibility)
        npm_override = self._named_step_block(
            RELEASE,
            "Verify published exact npm drift override",
        )
        self.assertIn("command: drift", npm_override)
        self.assertIn(
            "version: ${{ needs.publish.outputs.package_version }}",
            npm_override,
        )
        self.assertNotIn("continue-on-error", npm_override)
        self.assertIn("driver.version !== expected", text)
        self.assertIn('path.relative(temp, install).startsWith("..")', text)
        self.assertIn("needs: [publish, verify-action]", text)
        candidate_block = self._named_step_block(
            RELEASE,
            "Verify packed npm candidate",
        )
        self.assertIn("run: npm run check:package", candidate_block)
        self.assertNotIn("npm pack --dry-run", candidate_block)
        self.assertIn("Wait for exact npm package visibility", text)
        self.assertIn("Verify published exact npm drift override", text)

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
