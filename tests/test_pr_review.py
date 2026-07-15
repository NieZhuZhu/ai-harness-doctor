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
            "score": 85,
            "grade": "B",
            "findings": [
                {
                    "check": "D2",
                    "level": "ERROR",
                    "path": "docs/x.md",
                    "line": 12,
                    "message": "Referenced path missing",
                    "suggestion": "Fix it.",
                },
            ],
            "security": [
                {"level": "HIGH", "category": "secret", "path": "CLAUDE.md", "message": "token leaked"},
            ],
        }
        payload = pr_review.build_review(report)
        # Only the D2 finding has BOTH a path and a line, so exactly one inline
        # comment; the path-without-line secret goes to the summary instead.
        self.assertEqual(payload["inline_count"], 1)
        self.assertEqual(payload["summary_count"], 1)

        d2 = payload["comments"][0]
        self.assertEqual(d2["path"], "docs/x.md")
        self.assertEqual(d2["line"], 12)
        self.assertIn("### ❌ D2 · Path drift · ERROR", d2["body"])
        self.assertIn("**Finding:** Referenced path missing", d2["body"])
        self.assertIn("**Why it matters:**", d2["body"])
        self.assertIn("AI coding agents", d2["body"])
        self.assertIn("**Evidence:**", d2["body"])
        self.assertIn("`docs/x.md:12`", d2["body"])
        self.assertIn("**Suggested fix:** Fix it.", d2["body"])

        # Every posted inline comment MUST carry a concrete line, otherwise
        # GitHub 422-rejects the whole review.
        for comment in payload["comments"]:
            self.assertIn("line", comment)
            self.assertIsInstance(comment["line"], int)

        # The final review summary is useful without opening each inline thread.
        self.assertIn("### Review overview", payload["body"])
        self.assertIn("**Health:** 85/100 (grade B)", payload["body"])
        self.assertIn("**Severity:** 2 error", payload["body"])
        self.assertIn("### Findings index", payload["body"])
        self.assertIn("`docs/x.md:12`", payload["body"])
        self.assertIn("Referenced path missing", payload["body"])
        self.assertIn("<summary><strong>Detailed findings (2)</strong></summary>", payload["body"])
        self.assertIn("**Review placement:** Inline comment posted at `docs/x.md:12`.", payload["body"])
        self.assertIn("**Suggested fix:** Fix it.", payload["body"])
        self.assertIn("### Recommended next steps", payload["body"])

    def test_rich_comment_includes_declared_actual_and_evidence(self):
        report = {
            "semantic": {
                "findings": [
                    {
                        "category": "package_manager",
                        "level": "MISMATCH",
                        "path": "AGENTS.md",
                        "line": "8",
                        "message": "Package manager declaration differs from the lockfile",
                        "declared": "npm",
                        "actual": "pnpm",
                        "evidence": "pnpm-lock.yaml",
                        "suggestion": "Align the declaration with the repository.",
                    }
                ]
            }
        }
        comment = pr_review.build_review(report)["comments"][0]["body"]
        self.assertIn("### ⚠️ package_manager · Package-manager consistency · MISMATCH", comment)
        self.assertIn("- **Declared:** npm", comment)
        self.assertIn("- **Repository fact:** pnpm", comment)
        self.assertIn("- **Source evidence:** pnpm-lock.yaml", comment)
        self.assertIn("**Suggested fix:** Align the declaration with the repository.", comment)

    def test_path_without_line_goes_to_summary_not_inline(self):
        # A finding with a path but no line must NOT become an inline comment
        # (that would 422 the whole review); it is routed to the summary body
        # while still naming the file it refers to.
        report = {
            "security": [
                {"level": "HIGH", "category": "secret", "path": "CLAUDE.md", "message": "token leaked"},
            ],
        }
        payload = pr_review.build_review(report)
        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["inline_count"], 0)
        self.assertEqual(payload["summary_count"], 1)
        self.assertIn("secret", payload["body"])
        self.assertIn("CLAUDE.md", payload["body"])
        self.assertIn("Detailed findings", payload["body"])
        self.assertIn("Summary only: `CLAUDE.md` has no attachable line.", payload["body"])
        self.assertIn("**Why it matters:**", payload["body"])

    def test_unlocated_findings_go_to_summary(self):
        report = {
            "findings": [
                {"check": "D4", "level": "ERROR", "message": "AGENTS.md missing", "suggestion": "Create it."},
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
        report = {
            "findings": [
                {
                    "check": "D1",
                    "level": "ERROR",
                    "line": 7,
                    "message": "Unknown script `nope`",
                    "suggestion": "Update AGENTS.md.",
                },
            ]
        }
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
        payload = pr_review.build_review({"score": 100, "grade": "A"})
        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["inline_count"], 0)
        self.assertEqual(payload["summary_count"], 0)
        self.assertIn(pr_review.MARKER, payload["body"])
        self.assertIn("### ✅ Harness checks passed", payload["body"])
        self.assertIn("**Health:** 100/100 (grade A)", payload["body"])
        self.assertIn("No drift, semantic, gap, or security findings were reported.", payload["body"])
        self.assertIn("No action is required", payload["body"])

    def test_summary_reports_severity_distribution_and_delivery(self):
        report = {
            "findings": [
                {"check": "D1", "level": "ERROR", "path": "AGENTS.md", "line": 2, "message": "bad command"},
                {"check": "D4", "level": "NOTICE", "message": "large file"},
            ],
            "custom": [{"rule": "org-policy", "level": "WARN", "message": "missing owner"}],
            "score": 80,
            "grade": "B",
        }
        payload = pr_review.build_review(report)
        body = payload["body"]
        self.assertIn("**Delivery:** 3 total", body)
        self.assertIn("1 inline thread", body)
        self.assertIn("2 summary-only", body)
        self.assertIn("1 error", body)
        self.assertIn("2 warnings", body)
        self.assertIn("`AGENTS.md:2`", body)
        self.assertIn("org-policy", body)

    def test_collects_from_scan_and_drift_shapes(self):
        report = {
            "findings": [{"check": "D3", "path": "CLAUDE.md", "message": "regrew"}],
            "warnings": [
                {
                    "level": "WARN",
                    "path": "AGENTS.md",
                    "message": "AGENTS.md is oversized",
                }
            ],
            "gaps": [{"check": "G1", "level": "ERROR", "message": "no AGENTS.md"}],
            "semantic": {
                "findings": [
                    {
                        "category": "command",
                        "level": "ERROR",
                        "line": 3,
                        "message": "cmd mismatch",
                        "suggestion": "align",
                    }
                ]
            },
        }
        findings = pr_review.collect_findings(report)
        self.assertEqual(len(findings), 4)
        self.assertEqual(findings[1]["category"], "size")
        self.assertIn("Instruction size warning", pr_review.build_review(report)["body"])

    def test_collects_conflicts_and_excludes_baselined_debt(self):
        report = {
            "conflicts": [
                {
                    "signal": "package_manager",
                    "values": {
                        "pnpm": [{"path": "AGENTS.md", "line": 4}],
                        "npm": [{"path": "CLAUDE.md", "line": 2}],
                    },
                    "scope": "packages/api",
                }
            ],
            "baselined": [
                {
                    "family": "conflict",
                    "rule": "formatter",
                    "message": "old accepted debt",
                    "values": ["eslint", "prettier"],
                }
            ],
        }

        findings = pr_review.collect_findings(report)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["category"], "conflict/package_manager")
        self.assertEqual(findings[0]["level"], "WARN")
        self.assertEqual(findings[0]["values"], ["npm", "pnpm"])
        self.assertEqual(
            findings[0]["message"],
            "Conflicting package_manager declarations: npm, pnpm (scope: packages/api)",
        )
        self.assertEqual(findings[0]["scope"], "packages/api")
        self.assertEqual(
            findings[0]["evidence"],
            ["npm: CLAUDE.md:2", "pnpm: AGENTS.md:4"],
        )
        self.assertNotIn("old accepted debt", json.dumps(findings))

    def test_scope_overrides_are_not_pr_findings(self):
        report = {
            "scope_overrides": [
                {
                    "signal": "package_manager",
                    "parent_scope": ".",
                    "scope": "packages/api",
                    "parent_values": ["npm"],
                    "values": ["pnpm"],
                    "evidence": [],
                }
            ]
        }
        self.assertEqual(pr_review.collect_findings(report), [])

    def test_monorepo_findings_are_prefixed_and_attributed(self):
        report = {
            "packages": [
                {
                    "path": "packages/app",
                    "name": "app",
                    "report": {
                        "security": [
                            {
                                "category": "secret",
                                "level": "HIGH",
                                "path": ".claude/settings.json",
                                "line": 6,
                                "message": "secret-shaped value",
                            }
                        ],
                        "semantic": {
                            "findings": [
                                {
                                    "category": "command",
                                    "level": "MISMATCH",
                                    "line": 8,
                                    "message": "command mismatch",
                                }
                            ]
                        },
                        "gaps": [
                            {
                                "check": "G2",
                                "level": "WARN",
                                "message": "missing Safety section",
                            }
                        ],
                        "conflicts": [
                            {
                                "signal": "quote_style",
                                "values": {"single": [], "double": []},
                            }
                        ],
                    },
                }
            ]
        }

        payload = pr_review.build_review(report, default_path="AGENTS.md")

        self.assertEqual(payload["inline_count"], 2)
        self.assertEqual(
            [(comment["path"], comment["line"]) for comment in payload["comments"]],
            [
                ("packages/app/.claude/settings.json", 6),
                ("packages/app/AGENTS.md", 8),
            ],
        )
        self.assertEqual(payload["summary_count"], 2)
        self.assertIn("packages/app/AGENTS.md", payload["body"])
        self.assertIn("conflict/quote_style", payload["body"])
        self.assertIn("- **Package:** packages/app", payload["body"])

    def test_package_conflict_evidence_uses_prefixed_paths(self):
        report = {
            "packages": [
                {
                    "path": "packages/app",
                    "report": {
                        "conflicts": [
                            {
                                "signal": "package_manager",
                                "values": {
                                    "npm": [{"path": "CLAUDE.md", "line": 2}],
                                    "pnpm": [{"path": "AGENTS.md", "line": 4}],
                                },
                            }
                        ]
                    },
                }
            ]
        }

        findings = pr_review.collect_findings(report)

        self.assertEqual(
            findings[0]["evidence"],
            [
                "npm: packages/app/CLAUDE.md:2",
                "pnpm: packages/app/AGENTS.md:4",
            ],
        )

    def test_batch_repo_findings_are_summary_only_without_resolved_path_leak(self):
        report = {
            "repos": [
                {
                    "path": "/private/tmp/work/repo-a",
                    "resolved": "/private/tmp/work/repo-a",
                    "name": "repo-a-package",
                    "report": {
                        "semantic": {
                            "findings": [
                                {
                                    "category": "path",
                                    "level": "MISMATCH",
                                    "path": "AGENTS.md",
                                    "line": 9,
                                    "message": "path mismatch",
                                }
                            ]
                        }
                    },
                },
                {
                    "path": "/private/tmp/work/missing",
                    "resolved": "/private/tmp/work/missing",
                    "error": "not a directory",
                },
            ]
        }

        payload = pr_review.build_review(report, default_path="AGENTS.md")

        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["summary_count"], 1)
        self.assertIn("- **Repository:** repo-a-package (repo-a)", payload["body"])
        self.assertIn("AGENTS.md:9", payload["body"])
        self.assertNotIn("/private/tmp", payload["body"])
        self.assertNotIn("not a directory", payload["body"])

    def test_batch_absolute_finding_path_is_not_rendered(self):
        report = {
            "repos": [
                {
                    "path": "/private/tmp/work/repo-a",
                    "name": "repo-a",
                    "report": {
                        "custom": [
                            {
                                "rule": "custom",
                                "level": "WARN",
                                "path": "/private/tmp/work/repo-a/secret.txt",
                                "message": "custom finding",
                            }
                        ]
                    },
                }
            ]
        }

        payload = pr_review.build_review(report)

        self.assertEqual(payload["summary_count"], 1)
        self.assertIn("- **Repository:** repo-a", payload["body"])
        self.assertNotIn("/private/tmp", payload["body"])
        self.assertNotIn("secret.txt", payload["body"])

    def test_duplicate_report_entries_are_emitted_once_in_input_order(self):
        first = {"check": "D4", "level": "ERROR", "message": "first"}
        second = {"check": "D8", "level": "ERROR", "message": "second"}
        report = {"reports": [{"findings": [first, second]}, {"findings": [first]}]}

        findings = pr_review.collect_findings(report)

        self.assertEqual([finding["message"] for finding in findings], ["first", "second"])

    def test_root_and_package_duplicate_is_emitted_once(self):
        duplicate = {
            "category": "secret",
            "level": "HIGH",
            "path": "packages/app/.claude/settings.json",
            "message": "same root-indexed finding",
        }
        report = {
            "security": [duplicate],
            "packages": [
                {
                    "path": "packages/app",
                    "report": {
                        "security": [
                            {
                                **duplicate,
                                "path": ".claude/settings.json",
                            }
                        ]
                    },
                }
            ],
        }

        findings = pr_review.collect_findings(report)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["path"], "packages/app/.claude/settings.json")

    def test_same_unlocated_conflict_in_two_packages_keeps_both_attributions(self):
        conflict = {
            "signal": "package_manager",
            "values": {"npm": [], "pnpm": []},
        }
        report = {
            "packages": [
                {"path": "packages/a", "report": {"conflicts": [conflict]}},
                {"path": "packages/b", "report": {"conflicts": [conflict]}},
            ]
        }

        findings = pr_review.collect_findings(report)

        self.assertEqual(len(findings), 2)
        self.assertEqual(
            [finding["_review_package"] for finding in findings],
            ["packages/a", "packages/b"],
        )

    def test_non_positive_or_unsafe_locations_never_become_inline(self):
        report = {
            "findings": [
                {"check": "D2", "level": "ERROR", "path": "AGENTS.md", "line": 0, "message": "zero"},
                {"check": "D2", "level": "ERROR", "path": "../outside", "line": 2, "message": "escape"},
                {"check": "D2", "level": "ERROR", "path": "/tmp/absolute", "line": 3, "message": "absolute"},
            ]
        }

        payload = pr_review.build_review(report)

        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["summary_count"], 3)

    def test_body_is_deterministic(self):
        report = {"findings": [{"check": "D4", "level": "ERROR", "message": "m"}]}
        first = pr_review.build_review(report)["body"]
        second = pr_review.build_review(report)["body"]
        self.assertEqual(first, second)

    def test_embedded_newline_in_message_cannot_inject_extra_lines(self):
        # A custom rule plugin's message/suggestion is fully attacker-controlled
        # free text (SEC-01 defense-in-depth); a raw newline must never splice
        # extra lines into the posted comment body.
        report = {
            "findings": [
                {
                    "check": "custom",
                    "level": "ERROR",
                    "message": "evil\n# Fake heading\n![x](http://evil.example/beacon)",
                    "suggestion": "also\nmulti\nline",
                },
            ],
        }
        payload = pr_review.build_review(report)
        # This finding has neither path nor line, so it lands in the summary.
        self.assertEqual(payload["summary_count"], 1)
        self.assertEqual(payload["comments"], [])
        self.assertFalse(any(line.strip() == "# Fake heading" for line in payload["body"].splitlines()))

    def test_embedded_newline_in_path_does_not_break_summary_location(self):
        report = {"findings": [{"check": "custom", "level": "WARN", "path": "x\n# injected", "message": "m"}]}
        payload = pr_review.build_review(report)
        self.assertNotIn("\n# injected", payload["body"])


class CliTests(unittest.TestCase):
    def test_dry_run_prints_valid_json_via_stdin(self):
        report = json.dumps(
            {
                "findings": [
                    {"check": "D2", "level": "ERROR", "path": "a.md", "line": 1, "message": "m", "suggestion": "s"},
                    {"check": "D4", "level": "ERROR", "message": "n"},
                ]
            }
        )
        proc = subprocess.run(
            [sys.executable, str(PR_REVIEW)],
            input=report,
            text=True,
            capture_output=True,
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
                text=True,
                capture_output=True,
            )
        finally:
            Path(path).unlink()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(pr_review.MARKER, json.loads(proc.stdout)["body"])

    def test_dry_run_combines_repeated_report_files_into_one_review(self):
        import tempfile

        paths = []
        try:
            for report in (
                {"security": [{"category": "secret", "level": "HIGH", "message": "scan-only"}]},
                {"findings": [{"check": "D4", "level": "ERROR", "message": "drift-only"}]},
            ):
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
                    json.dump(report, fh)
                    paths.append(fh.name)
            proc = subprocess.run(
                [
                    sys.executable,
                    str(PR_REVIEW),
                    "--report",
                    paths[0],
                    "--report",
                    paths[1],
                ],
                text=True,
                capture_output=True,
            )
        finally:
            for path in paths:
                Path(path).unlink()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["summary_count"], 2)
        self.assertIn("scan-only", payload["body"])
        self.assertIn("drift-only", payload["body"])

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


class PostReviewTests(unittest.TestCase):
    """Cover the network-posting path by mocking the GitHub HTTP call.

    ``post_review`` imports ``urllib.request`` lazily inside the function, so we
    patch ``urllib.request.urlopen`` and capture the ``Request`` object that
    would be sent to GitHub, asserting the correct endpoint, method, headers and
    JSON payload are built.
    """

    def _capture(self, payload, **kwargs):
        import urllib.request
        from unittest import mock

        captured = {}

        class _Resp:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def read(self_inner):
                return b'{"html_url": "https://github.com/o/r/pull/7#review"}'

        def _fake_urlopen(req, *a, **kw):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["data"] = json.loads(req.data.decode("utf-8"))
            captured["headers"] = dict(req.header_items())
            return _Resp()

        with mock.patch.object(urllib.request, "urlopen", _fake_urlopen):
            resp = pr_review.post_review(payload, **kwargs)
        return captured, resp

    def test_post_with_inline_comments_hits_reviews_endpoint(self):
        report = {
            "findings": [
                {"check": "D2", "level": "ERROR", "path": "a.md", "line": 3, "message": "m", "suggestion": "s"},
            ],
            # path-without-line: must be dropped from inline comments so the
            # review is never 422-rejected.
            "security": [{"level": "HIGH", "category": "secret", "path": "b.md", "message": "leak"}],
        }
        payload = pr_review.build_review(report)
        captured, resp = self._capture(
            payload, repo="o/r", pr_number=7, commit_sha="deadbeef", token="tok"
        )

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://api.github.com/repos/o/r/pulls/7/reviews")
        self.assertEqual(captured["data"]["commit_id"], "deadbeef")
        self.assertEqual(captured["data"]["event"], "COMMENT")
        # Exactly one inline comment (the located D2); the path-without-line
        # secret was routed to the summary body, not sent as a comment.
        self.assertEqual(len(captured["data"]["comments"]), 1)
        for comment in captured["data"]["comments"]:
            self.assertIn("path", comment)
            self.assertIn("line", comment)  # 422-avoidance: every comment has a line
            self.assertIsInstance(comment["line"], int)
        # Auth header carries the bearer token.
        headers = {k.lower(): v for k, v in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer tok")
        self.assertEqual(resp.get("html_url"), "https://github.com/o/r/pull/7#review")

    def test_post_without_comments_falls_back_to_issue_comment(self):
        # No located findings -> a single general issue comment carrying the
        # summary body (never the reviews endpoint, so no 422 risk).
        report = {"findings": [{"check": "D4", "level": "ERROR", "message": "no location"}]}
        payload = pr_review.build_review(report)
        self.assertEqual(payload["comments"], [])
        captured, _ = self._capture(
            payload, repo="o/r", pr_number=9, commit_sha="cafe", token="tok"
        )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://api.github.com/repos/o/r/issues/9/comments")
        self.assertIn("body", captured["data"])
        self.assertNotIn("comments", captured["data"])

    def test_inline_review_422_falls_back_to_complete_issue_comment(self):
        import urllib.error
        import urllib.request
        from unittest import mock

        report = {
            "score": 75,
            "grade": "C",
            "findings": [
                {
                    "check": "D2",
                    "level": "ERROR",
                    "path": "AGENTS.md",
                    "line": 99,
                    "message": "Referenced path no longer exists",
                    "suggestion": "Update the canonical instruction.",
                }
            ],
        }
        payload = pr_review.build_review(report)
        requests = []

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"html_url": "https://github.com/o/r/pull/7#issuecomment-1"}'

        def _fake_urlopen(req, *args, **kwargs):
            requests.append(
                {
                    "url": req.full_url,
                    "data": json.loads(req.data.decode("utf-8")),
                }
            )
            if len(requests) == 1:
                raise urllib.error.HTTPError(
                    req.full_url,
                    422,
                    "Unprocessable Entity",
                    hdrs=None,
                    fp=io.BytesIO(b'{"message":"Validation Failed"}'),
                )
            return _Resp()

        with mock.patch.object(urllib.request, "urlopen", _fake_urlopen):
            response = pr_review.post_review(
                payload,
                repo="o/r",
                pr_number=7,
                commit_sha="deadbeef",
                token="tok",
            )

        self.assertEqual(
            [request["url"] for request in requests],
            [
                "https://api.github.com/repos/o/r/pulls/7/reviews",
                "https://api.github.com/repos/o/r/issues/7/comments",
            ],
        )
        fallback_body = requests[1]["data"]["body"]
        self.assertIn(pr_review.MARKER, fallback_body)
        self.assertIn("Referenced path no longer exists", fallback_body)
        self.assertIn("Update the canonical instruction.", fallback_body)
        self.assertIn("75/100 (grade C)", fallback_body)
        self.assertEqual(response["html_url"], "https://github.com/o/r/pull/7#issuecomment-1")

    def test_inline_review_non_422_error_is_not_hidden(self):
        import urllib.error
        import urllib.request
        from unittest import mock

        payload = pr_review.build_review(
            {
                "findings": [
                    {
                        "check": "D2",
                        "level": "ERROR",
                        "path": "AGENTS.md",
                        "line": 2,
                        "message": "bad path",
                    }
                ]
            }
        )
        requests = []

        def _fake_urlopen(req, *args, **kwargs):
            requests.append(req.full_url)
            raise urllib.error.HTTPError(
                req.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=io.BytesIO(b'{"message":"Resource not accessible"}'),
            )

        with mock.patch.object(urllib.request, "urlopen", _fake_urlopen):
            with self.assertRaisesRegex(
                SystemExit,
                r"(?s)403 Forbidden.*Resource not accessible",
            ):
                pr_review.post_review(
                    payload,
                    repo="o/r",
                    pr_number=7,
                    commit_sha="deadbeef",
                    token="tok",
                )

        self.assertEqual(requests, ["https://api.github.com/repos/o/r/pulls/7/reviews"])


if __name__ == "__main__":
    unittest.main()
