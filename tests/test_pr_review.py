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
    def test_tail_security_finding_is_delivered_without_secret_value(self):
        report = {
            "analysis_limits": [
                {
                    "path": "AGENTS.md",
                    "bytes": 50000,
                    "analyzed_bytes": 32768,
                    "security_scanned_bytes": 50000,
                    "affected": ["conflicts", "overlaps", "scope_overrides", "semantic"],
                }
            ],
            "security": [
                {
                    "level": "HIGH",
                    "category": "secret",
                    "path": "AGENTS.md",
                    "message": "Possible GitHub token committed in AGENTS.md",
                }
            ],
        }

        payload = pr_review.build_review(report)

        self.assertEqual(payload["summary_count"], 1)
        self.assertIn("Possible GitHub token", payload["body"])
        self.assertNotIn("ghp_", payload["body"])

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

    def test_nested_drift_finding_uses_its_own_path_over_default(self):
        report = {
            "findings": [
                {
                    "check": "D1",
                    "level": "ERROR",
                    "path": "packages/api/AGENTS.md",
                    "line": 4,
                    "message": "Unknown script `removed-script`",
                    "suggestion": "Update the package instructions.",
                },
            ]
        }
        payload = pr_review.build_review(report, default_path="AGENTS.md")
        self.assertEqual(payload["inline_count"], 1)
        self.assertEqual(payload["comments"][0]["path"], "packages/api/AGENTS.md")
        self.assertEqual(payload["comments"][0]["line"], 4)
        self.assertIn("`packages/api/AGENTS.md:4`", payload["comments"][0]["body"])

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

    def test_applicability_warning_is_attributed_inline(self):
        report = {
            "applicability_warnings": [
                {
                    "category": "ignored",
                    "level": "WARN",
                    "path": ".cursor/rules/legacy.md",
                    "line": 1,
                    "message": "Structured rule is ignored.",
                    "suggestion": "Rename it to .mdc.",
                }
            ]
        }

        payload = pr_review.build_review(report)

        self.assertEqual(payload["inline_count"], 1)
        self.assertEqual(
            pr_review.finding_label(pr_review.collect_findings(report)[0]),
            "applicability/ignored",
        )
        self.assertEqual(
            payload["comments"][0]["path"],
            ".cursor/rules/legacy.md",
        )
        self.assertIn("Rename it to .mdc.", payload["comments"][0]["body"])

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
        self.assertEqual(payload["summary_count"], 2)
        self.assertIn("- **Repository:** repo-a-package (repo-a)", payload["body"])
        self.assertIn("- **Repository:** missing", payload["body"])
        self.assertIn("AGENTS.md:9", payload["body"])
        self.assertIn("Listed repository was not scanned.", payload["body"])
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

    def _run_api(self, payload, handler, **kwargs):
        import urllib.request
        from unittest import mock

        requests = []

        class _Resp:
            def __init__(self, data, headers=None):
                self.data = data
                self.headers = headers or {}

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps(self.data).encode("utf-8")

        def _fake_urlopen(req, *a, **kw):
            request = {
                "url": req.full_url,
                "method": req.get_method(),
                "data": json.loads(req.data.decode("utf-8")) if req.data else None,
                "headers": dict(req.header_items()),
            }
            requests.append(request)
            response = handler(request, len(requests))
            if isinstance(response, Exception):
                raise response
            data, headers = response if isinstance(response, tuple) else (response, {})
            return _Resp(data, headers)

        with mock.patch.object(urllib.request, "urlopen", _fake_urlopen):
            resp = pr_review.post_review(payload, **kwargs)
        return requests, resp

    @staticmethod
    def _http_error(url, code, reason):
        import urllib.error

        return urllib.error.HTTPError(
            url,
            code,
            reason,
            hdrs=None,
            fp=io.BytesIO(json.dumps({"message": reason}).encode("utf-8")),
        )

    def test_clean_rerun_updates_owned_user_summary_instead_of_posting_another(self):
        payload = pr_review.build_review({"findings": []})
        existing = {
            "id": 41,
            "body": pr_review.MARKER + "\nold",
            "created_at": "2026-01-01T00:00:00Z",
            "user": {"id": 7, "node_id": "U_maintainer", "login": "maintainer"},
            "html_url": "https://github.com/o/r/pull/9#issuecomment-41",
        }

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/9/comments?per_page=100&page=1"):
                return [existing]
            if request["url"].endswith("/issues/comments/41"):
                self.assertEqual(request["method"], "PATCH")
                self.assertEqual(request["data"]["body"], payload["body"])
                return {**existing, "body": payload["body"]}
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=9,
            commit_sha="cafe",
            token="tok",
        )

        self.assertEqual([request["method"] for request in requests], ["POST", "GET", "PATCH"])
        self.assertEqual(response["id"], 41)

    def test_first_post_creates_summary_when_no_owned_marker_exists(self):
        payload = pr_review.build_review({"findings": []})
        foreign = {
            "id": 10,
            "body": pr_review.MARKER + "\nforeign",
            "created_at": "2026-01-01T00:00:00Z",
            "user": {"id": 99, "node_id": "U_foreign", "login": "someone-else"},
        }

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/9/comments?per_page=100&page=1"):
                return [foreign]
            if request["url"].endswith("/issues/9/comments"):
                self.assertEqual(request["method"], "POST")
                return {
                    "id": 42,
                    "body": request["data"]["body"],
                    "html_url": "https://github.com/o/r/pull/9#issuecomment-42",
                }
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=9,
            commit_sha="cafe",
            token="tok",
        )

        self.assertEqual([request["method"] for request in requests], ["POST", "GET", "POST"])
        self.assertEqual(response["id"], 42)

    def test_unknown_identity_creates_without_listing_or_patching(self):
        payload = pr_review.build_review({"findings": []})

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return self._http_error(request["url"], 403, "Forbidden")
            if request["url"].endswith("/issues/9/comments"):
                self.assertEqual(request["method"], "POST")
                return {
                    "id": 42,
                    "html_url": "https://github.com/o/r/pull/9#issuecomment-42",
                }
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=9,
            commit_sha="cafe",
            token="tok",
        )

        self.assertEqual([request["method"] for request in requests], ["POST", "POST"])
        self.assertEqual(response["id"], 42)
        self.assertFalse(any(request["method"] == "PATCH" for request in requests))

    def test_app_identity_updates_newest_owned_duplicate_on_later_page(self):
        payload = pr_review.build_review({"findings": []})
        fillers = [
            {
                "id": index,
                "body": "ordinary",
                "created_at": f"2026-01-01T00:00:{index % 60:02d}Z",
                "user": {
                    "id": index,
                    "node_id": f"U_{index}",
                    "login": f"user-{index}",
                },
            }
            for index in range(100)
        ]
        owned_old = {
            "id": 201,
            "body": pr_review.MARKER + "\nold duplicate",
            "created_at": "2026-02-01T00:00:00Z",
            "user": {
                "id": 41898282,
                "node_id": "BOT_actions",
                "login": "github-actions[bot]",
            },
            "performed_via_github_app": {"id": 15368, "slug": "github-actions"},
        }
        owned_new = {
            "id": 202,
            "body": pr_review.MARKER + "\nnew duplicate",
            "created_at": "2026-02-02T00:00:00Z",
            "user": {
                "id": 41898282,
                "node_id": "BOT_actions",
                "login": "github-actions[bot]",
            },
            "performed_via_github_app": {"id": 15368, "slug": "github-actions"},
        }

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {
                    "data": {
                        "viewer": {
                            "id": "BOT_actions",
                            "login": "github-actions[bot]",
                        }
                    }
                }
            if request["url"].endswith("/comments?per_page=100&page=1"):
                return (
                    fillers,
                    {"Link": '<https://evil.example/steal>; rel="next"'},
                )
            if request["url"].endswith("/comments?per_page=100&page=2"):
                return [owned_old, owned_new]
            if request["url"].endswith("/issues/comments/202"):
                self.assertEqual(request["method"], "PATCH")
                return {**owned_new, "body": request["data"]["body"]}
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=7,
            commit_sha="deadbeef",
            token="tok",
        )

        self.assertEqual(response["id"], 202)
        self.assertFalse(any("evil.example" in request["url"] for request in requests))
        self.assertFalse(any(request["url"].endswith("/issues/comments/201") for request in requests))

    def test_comment_scan_fails_closed_after_bounded_pages(self):
        payload = pr_review.build_review({"findings": []})
        full_page = [
            {
                "id": index,
                "body": "ordinary",
                "created_at": "2026-01-01T00:00:00Z",
                "user": {
                    "id": index,
                    "node_id": f"U_{index}",
                    "login": f"user-{index}",
                },
            }
            for index in range(100)
        ]

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if "/issues/9/comments?per_page=100&page=" in request["url"]:
                return full_page
            self.fail(f"unexpected request: {request}")

        with self.assertRaisesRegex(SystemExit, "comment scan exceeded 1000 entries"):
            self._run_api(
                payload,
                handler,
                repo="o/r",
                pr_number=9,
                commit_sha="cafe",
                token="tok",
            )

    def test_malformed_comment_list_fails_without_writing(self):
        payload = pr_review.build_review({"findings": []})
        requests = []

        def handler(request, _count):
            requests.append(request)
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/9/comments?per_page=100&page=1"):
                return {"unexpected": "object"}
            self.fail(f"unexpected request: {request}")

        with self.assertRaisesRegex(SystemExit, "non-list comment payload"):
            self._run_api(
                payload,
                handler,
                repo="o/r",
                pr_number=9,
                commit_sha="cafe",
                token="tok",
            )
        self.assertFalse(
            any(
                request["method"] in {"POST", "PATCH"}
                and request["url"] != "https://api.github.com/graphql"
                for request in requests
            )
        )

    def test_post_with_inline_comments_upserts_summary_then_posts_marker_free_review(self):
        report = {
            "findings": [
                {"check": "D2", "level": "ERROR", "path": "a.md", "line": 3, "message": "m", "suggestion": "s"},
            ],
            "security": [{"level": "HIGH", "category": "secret", "path": "b.md", "message": "leak"}],
        }
        payload = pr_review.build_review(report)
        summary = {
            "id": 42,
            "html_url": "https://github.com/o/r/pull/7#issuecomment-42",
        }

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/7/comments?per_page=100&page=1"):
                return []
            if request["url"].endswith("/issues/7/comments"):
                return summary
            if request["url"].endswith("/pulls/7/reviews"):
                self.assertEqual(request["method"], "POST")
                self.assertNotIn(pr_review.MARKER, request["data"].get("body", ""))
                self.assertEqual(len(request["data"]["comments"]), 1)
                return {"html_url": "https://github.com/o/r/pull/7#review"}
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=7,
            commit_sha="deadbeef",
            token="tok",
        )

        self.assertEqual(response, summary)
        review = requests[-1]
        self.assertEqual(review["data"]["commit_id"], "deadbeef")
        self.assertEqual(review["data"]["event"], "COMMENT")
        for comment in review["data"]["comments"]:
            self.assertIn("path", comment)
            self.assertIn("line", comment)
            self.assertIsInstance(comment["line"], int)
        headers = {key.lower(): value for key, value in review["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer tok")

    def test_inline_review_422_uses_already_upserted_summary_without_duplicate(self):
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
        summary = {"id": 42, "html_url": "https://github.com/o/r/pull/7#issuecomment-42"}

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/7/comments?per_page=100&page=1"):
                return []
            if request["url"].endswith("/issues/7/comments"):
                return summary
            if request["url"].endswith("/pulls/7/reviews"):
                return self._http_error(request["url"], 422, "Validation Failed")
            self.fail(f"unexpected request: {request}")

        requests, response = self._run_api(
            payload,
            handler,
            repo="o/r",
            pr_number=7,
            commit_sha="deadbeef",
            token="tok",
        )

        self.assertEqual(response, summary)
        summary_writes = [
            request
            for request in requests
            if request["method"] in {"POST", "PATCH"} and "/issues/" in request["url"]
        ]
        self.assertEqual(len(summary_writes), 1)
        self.assertIn("Referenced path no longer exists", summary_writes[0]["data"]["body"])

    def test_inline_review_non_422_error_is_not_hidden(self):
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

        def handler(request, _count):
            if request["url"] == "https://api.github.com/graphql":
                return {"data": {"viewer": {"id": "U_maintainer", "login": "maintainer"}}}
            if request["url"].endswith("/issues/7/comments?per_page=100&page=1"):
                return []
            if request["url"].endswith("/issues/7/comments"):
                return {"id": 42, "html_url": "https://github.com/o/r/pull/7#issuecomment-42"}
            if request["url"].endswith("/pulls/7/reviews"):
                return self._http_error(request["url"], 403, "Resource not accessible")
            self.fail(f"unexpected request: {request}")

        with self.assertRaisesRegex(SystemExit, r"(?s)403 Resource not accessible"):
            self._run_api(
                payload,
                handler,
                repo="o/r",
                pr_number=7,
                commit_sha="deadbeef",
                token="tok",
            )


if __name__ == "__main__":
    unittest.main()
