import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR_REVIEW = ROOT / "scripts" / "pr_review.py"

sys.path.insert(0, str(ROOT / "scripts"))
import pr_review  # noqa: E402


class BuildReviewTests(unittest.TestCase):
    def test_located_findings_become_inline_comments(self):
        report = {
            "findings": [
                {"check": "D2", "level": "ERROR", "path": "docs/x.md", "line": 12,
                 "message": "Referenced path missing", "suggestion": "Fix it."},
            ],
            "security": [
                {"level": "HIGH", "category": "secret", "path": "CLAUDE.md",
                 "message": "token leaked"},
            ],
        }
        payload = pr_review.build_review(report)
        self.assertEqual(payload["inline_count"], 2)
        self.assertEqual(payload["summary_count"], 0)

        d2 = payload["comments"][0]
        self.assertEqual(d2["path"], "docs/x.md")
        self.assertEqual(d2["line"], 12)
        self.assertIn("D2", d2["body"])
        self.assertIn("Fix it.", d2["body"])

        # A finding with a path but no line is still inline, without a line key.
        secret = payload["comments"][1]
        self.assertEqual(secret["path"], "CLAUDE.md")
        self.assertNotIn("line", secret)
        self.assertIn("secret", secret["body"])

    def test_unlocated_findings_go_to_summary(self):
        report = {
            "findings": [
                {"check": "D4", "level": "ERROR", "message": "AGENTS.md missing",
                 "suggestion": "Create it."},
            ],
        }
        payload = pr_review.build_review(report)
        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["inline_count"], 0)
        self.assertEqual(payload["summary_count"], 1)
        self.assertIn(pr_review.MARKER, payload["body"])
        self.assertIn("D4", payload["body"])
        self.assertIn("Create it.", payload["body"])

    def test_line_only_findings_use_default_path_when_given(self):
        report = {"findings": [
            {"check": "D1", "level": "ERROR", "line": 7,
             "message": "Unknown script `nope`", "suggestion": "Update AGENTS.md."},
        ]}
        # Without a default_path, a line-only finding cannot be located.
        without = pr_review.build_review(report)
        self.assertEqual(without["inline_count"], 0)
        self.assertEqual(without["summary_count"], 1)
        # With a default_path, it is attached to that file inline.
        withpath = pr_review.build_review(report, default_path="AGENTS.md")
        self.assertEqual(withpath["inline_count"], 1)
        self.assertEqual(withpath["comments"][0]["path"], "AGENTS.md")
        self.assertEqual(withpath["comments"][0]["line"], 7)

    def test_empty_findings_case(self):
        payload = pr_review.build_review({})
        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["inline_count"], 0)
        self.assertEqual(payload["summary_count"], 0)
        self.assertIn(pr_review.MARKER, payload["body"])
        self.assertIn("No drift or scan findings", payload["body"])

    def test_collects_from_scan_and_drift_shapes(self):
        report = {
            "findings": [{"check": "D3", "path": "CLAUDE.md", "message": "regrew"}],
            "gaps": [{"check": "G1", "level": "ERROR", "message": "no AGENTS.md"}],
            "semantic": {"findings": [
                {"category": "command", "level": "ERROR", "line": 3,
                 "message": "cmd mismatch", "suggestion": "align"}
            ]},
        }
        findings = pr_review.collect_findings(report)
        self.assertEqual(len(findings), 3)

    def test_body_is_deterministic(self):
        report = {"findings": [{"check": "D4", "level": "ERROR", "message": "m"}]}
        first = pr_review.build_review(report)["body"]
        second = pr_review.build_review(report)["body"]
        self.assertEqual(first, second)


class CliTests(unittest.TestCase):
    def test_dry_run_prints_valid_json_via_stdin(self):
        report = json.dumps({
            "findings": [
                {"check": "D2", "level": "ERROR", "path": "a.md", "line": 1,
                 "message": "m", "suggestion": "s"},
                {"check": "D4", "level": "ERROR", "message": "n"},
            ]
        })
        proc = subprocess.run(
            [sys.executable, str(PR_REVIEW)],
            input=report, text=True, capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)  # must be valid JSON
        self.assertEqual(payload["inline_count"], 1)
        self.assertEqual(payload["summary_count"], 1)
        self.assertEqual(payload["comments"][0]["path"], "a.md")

    def test_dry_run_reads_report_file(self):
        import tempfile
        report = {"findings": [{"check": "D4", "level": "ERROR", "message": "x"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(report, fh)
            path = fh.name
        try:
            proc = subprocess.run(
                [sys.executable, str(PR_REVIEW), "--report", path],
                text=True, capture_output=True,
            )
        finally:
            Path(path).unlink()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(pr_review.MARKER, json.loads(proc.stdout)["body"])

    def test_dry_run_default_never_posts(self):
        # Ensure the default main() path prints JSON and does not invoke the
        # network-posting helper. We monkeypatch post_review to blow up if used.
        called = {"posted": False}

        def _boom(*args, **kwargs):
            called["posted"] = True
            raise AssertionError("post_review must not be called in --dry-run")

        original = pr_review.post_review
        pr_review.post_review = _boom
        original_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps({"findings": []}))
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = pr_review.main([])
        finally:
            pr_review.post_review = original
            sys.stdin = original_stdin
        self.assertEqual(rc, 0)
        self.assertFalse(called["posted"])
        json.loads(buf.getvalue())  # still valid JSON


if __name__ == "__main__":
    unittest.main()
