import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from argparse import Namespace
from pathlib import Path
from shlex import quote as shlex_quote

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "scripts" / "eval_run.py"

sys.path.insert(0, str(ROOT / "scripts"))
import eval_run  # noqa: E402
import explain  # noqa: E402


class TaskSchemaPreflightTests(unittest.TestCase):
    def _valid_task(self):
        return {
            "id": "task",
            "prompt": "answer",
            "check": {"type": "regex", "value": "^ok$"},
            "timeout_s": 10,
        }

    def test_valid_task_preserves_additive_metadata(self):
        task = self._valid_task()
        task.update({"scope": "packages/api", "target": "packages/api/x.py", "future": {"x": 1}})
        tasks = [task]

        self.assertIs(eval_run.validate_tasks(tasks), tasks)
        self.assertEqual(tasks[0]["future"], {"x": 1})

    def test_invalid_task_fields_fail_with_safe_indexed_diagnostics(self):
        cases = [
            ("root", {}, "tasks file must contain a JSON array"),
            ("object", [42], "task 0 must be an object"),
            ("id-missing", [{**self._valid_task(), "id": None}], "field `id`"),
            ("id-empty", [{**self._valid_task(), "id": "  "}], "field `id`"),
            (
                "id-duplicate",
                [self._valid_task(), {**self._valid_task(), "prompt": "second"}],
                "task 1 field `id` must be unique",
            ),
            ("prompt-missing", [{**self._valid_task(), "prompt": None}], "field `prompt`"),
            ("prompt-empty", [{**self._valid_task(), "prompt": ""}], "field `prompt`"),
            ("check-object", [{**self._valid_task(), "check": "regex"}], "field `check`"),
            (
                "check-type",
                [{**self._valid_task(), "check": {"type": "unknown"}}],
                "field `check.type`",
            ),
            (
                "regex-value",
                [{**self._valid_task(), "check": {"type": "regex", "value": 42}}],
                "field `check.value`",
            ),
            (
                "command-value",
                [{**self._valid_task(), "check": {"type": "command"}}],
                "field `check.value`",
            ),
            ("timeout-bool", [{**self._valid_task(), "timeout_s": True}], "field `timeout_s`"),
            ("timeout-zero", [{**self._valid_task(), "timeout_s": 0}], "field `timeout_s`"),
            ("timeout-nan", [{**self._valid_task(), "timeout_s": float("nan")}], "field `timeout_s`"),
            (
                "judge-rubric",
                [{**self._valid_task(), "check": {"type": "judge", "rubric": []}}],
                "field `check.rubric`",
            ),
            (
                "judge-expect",
                [{**self._valid_task(), "check": {"type": "judge", "expect": ["ok", 1]}}],
                "field `check.expect`",
            ),
            (
                "judge-min-score",
                [{**self._valid_task(), "check": {"type": "judge", "min_score": 2}}],
                "field `check.min_score`",
            ),
            (
                "evidence-array",
                [{**self._valid_task(), "evidence": "package.json"}],
                "field `evidence` must be an array",
            ),
            (
                "evidence-entry",
                [{**self._valid_task(), "evidence": [""]}],
                "field `evidence` entries must be non-empty strings",
            ),
        ]
        for name, tasks, expected in cases:
            with self.subTest(name=name):
                with self.assertRaises(eval_run.TaskFileError) as caught:
                    eval_run.validate_tasks(tasks)
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("answer", str(caught.exception))

    def test_valid_judge_field_shapes(self):
        for value in ("one", ["one", "two"]):
            with self.subTest(value=value):
                task = self._valid_task()
                task["check"] = {
                    "type": "judge",
                    "rubric": "be correct",
                    "criteria": "name ok",
                    "expect": value,
                    "reject": value,
                    "min_score": 0.5,
                    "model": "model-name",
                }
                self.assertEqual(eval_run.validate_tasks([task]), [task])

    def test_task_file_errors_hide_path_and_content(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "secret-task-name.json"
            path.write_text("{not-json", encoding="utf-8")

            with self.assertRaises(eval_run.TaskFileError) as caught:
                eval_run.load_tasks_file(path)

            message = str(caught.exception)
            self.assertIn(path.name, message)
            self.assertNotIn(str(Path(td).resolve()), message)
            self.assertNotIn("not-json", message)

    def test_malformed_later_task_has_zero_side_effects_in_all_run_modes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workdir = root / "repo"
            workdir.mkdir()
            marker = root / "runner-called"
            tasks = root / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        self._valid_task(),
                        {
                            "id": "broken",
                            "check": {"type": "regex", "value": "ok"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            runner = (
                f"{sys.executable} -c "
                f"\"from pathlib import Path; Path({str(marker)!r}).write_text('ran')\""
            )
            cases = [
                (
                    "single",
                    [
                        "--tasks", str(tasks), "--label", "x", "--workdir", str(workdir),
                        "--runner", runner, "-o", str(root / "single.json"),
                    ],
                    [root / "single.json"],
                ),
                (
                    "multi",
                    [
                        "--tasks", str(tasks), "--label", "x", "--workdir", str(workdir),
                        "--runner", runner, "--rounds", "2", "-o", str(root / "multi.json"),
                    ],
                    [root / "multi.json"],
                ),
                (
                    "matrix",
                    [
                        "--tasks", str(tasks), "--workdir", str(workdir),
                        "--runner-cmd", f"one={runner}",
                        "--matrix-json", str(root / "matrix.json"),
                        "--matrix-report", str(root / "matrix.md"),
                    ],
                    [root / "matrix.json", root / "matrix.md"],
                ),
            ]
            for name, argv, outputs in cases:
                with self.subTest(name=name):
                    marker.unlink(missing_ok=True)
                    for output in outputs:
                        output.unlink(missing_ok=True)
                    proc = subprocess.run(
                        [sys.executable, str(EVAL), *argv],
                        text=True,
                        capture_output=True,
                    )
                    self.assertEqual(proc.returncode, 2)
                    self.assertIn("task error: task 1 field `prompt`", proc.stderr)
                    self.assertNotIn("Traceback", proc.stderr)
                    self.assertFalse(marker.exists())
                    self.assertTrue(all(not output.exists() for output in outputs))

    def test_regrade_rejects_malformed_tasks_before_output_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks.json"
            tasks.write_text(
                json.dumps([{"id": "broken", "prompt": "x", "check": None}]),
                encoding="utf-8",
            )
            result = root / "result.json"
            original = '{"tasks":[]}\n'
            result.write_text(original, encoding="utf-8")

            proc = subprocess.run(
                [
                    sys.executable, str(EVAL), "--regrade", str(result),
                    "--tasks", str(tasks),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn("task error: task 0 field `check`", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(result.read_text(encoding="utf-8"), original)

    def test_strict_score_validates_current_task_schema(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workdir = root / "repo"
            workdir.mkdir()
            tasks = root / "tasks.json"
            tasks.write_text(
                json.dumps([{"id": "broken", "prompt": "x", "check": {"type": "nope"}}]),
                encoding="utf-8",
            )
            result = root / "result.json"
            result.write_text(
                json.dumps({"tasks": [{"id": "broken", "passed": True}]}),
                encoding="utf-8",
            )

            strict = subprocess.run(
                [
                    sys.executable, str(EVAL), "--score", str(result),
                    "--tasks", str(tasks), "--workdir", str(workdir),
                    "--require-current-evidence",
                ],
                text=True,
                capture_output=True,
            )
            legacy = subprocess.run(
                [sys.executable, str(EVAL), "--score", str(result)],
                text=True,
                capture_output=True,
            )

            self.assertEqual(strict.returncode, 2)
            self.assertIn("task error: task 0 field `check.type`", strict.stderr)
            self.assertNotIn("Traceback", strict.stderr)
            self.assertEqual(legacy.returncode, 0, legacy.stderr)

    def test_prepare_evidence_uses_already_validated_tasks(self):
        task = self._valid_task()
        task["evidence"] = []
        args = Namespace(evidence=[])
        with tempfile.TemporaryDirectory() as td:
            tasks_path = Path(td) / "tasks.json"
            tasks_path.write_text(json.dumps([task]), encoding="utf-8")
            validated = eval_run.load_tasks_file(tasks_path)

            self.assertIsNone(
                eval_run.prepare_evidence_manifest(
                    args,
                    tasks_path,
                    Path(td),
                    tasks=validated,
                )
            )


class EvalRunTests(unittest.TestCase):
    def test_run_tasks_and_compare(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "regex",
                            "prompt": "hello",
                            "check": {"type": "regex", "value": "ok hello"},
                            "timeout_s": 10,
                        },
                        {
                            "id": "command",
                            "prompt": "world",
                            "check": {"type": "command", "value": "test -f AGENTS.md"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            before = Path(td) / "before.json"
            after = Path(td) / "after.json"
            runner = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            for label, out in [("before", before), ("after", after)]:
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(EVAL),
                        "--tasks",
                        str(tasks),
                        "--label",
                        label,
                        "--workdir",
                        str(workdir),
                        "--runner",
                        runner,
                        "-o",
                        str(out),
                    ],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                data = json.loads(out.read_text(encoding="utf-8"))
                self.assertTrue(all(t["passed"] for t in data["tasks"]))
                self.assertEqual(data["tasks"][0]["answer"], "ok hello")
            report = Path(td) / "report.md"
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--compare", str(before), str(after), "-o", str(report)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            text = report.read_text(encoding="utf-8")
            self.assertIn("before", text)
            self.assertIn("after", text)

    def test_runner_timeout_records_task_and_continues(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "hang",
                            "prompt": "sleep",
                            "check": {"type": "regex", "value": "never"},
                            "timeout_s": 1,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            output = Path(td) / "results.json"
            runner = 'python3 -c "import time;time.sleep(5)"'
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "timeout",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(data["tasks"]), 1)
            self.assertFalse(data["tasks"][0]["passed"])
            self.assertTrue(data["tasks"][0]["timed_out"])
            self.assertIsNone(data["tasks"][0]["exit_code"])

    def test_json_envelope_result_is_extracted_and_normalized(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "dev",
                            "prompt": "dev",
                            "check": {"type": "regex", "value": r"^pnpm\s+(run\s+)?dev\b"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            output = Path(td) / "results.json"
            runner = (
                f'{sys.executable} -c "import json; '
                "print(json.dumps({'type':'result',"
                "'result':'  '+chr(96)+'pnpm dev'+chr(96)+'  ',"
                "'usage':{}}))\""
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "envelope",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["tasks"][0]["passed"])
            self.assertEqual(data["tasks"][0]["answer"], "pnpm dev")

    def test_regrade_flips_stored_false_to_true_after_regex_fix(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "format",
                            "prompt": "format",
                            "check": {"type": "regex", "value": r"(?i)prettier"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            results = Path(td) / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "label": "stored",
                        "tasks": [
                            {
                                "id": "format",
                                "passed": False,
                                "duration_s": 1.23,
                                "usage": {"total_cost_usd": 0.01},
                                "stdout": json.dumps({"type": "result", "result": "`Prettier`"}),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, str(EVAL), "--regrade", str(results), "--tasks", str(tasks), "-o", str(results)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(results.read_text(encoding="utf-8"))
            record = data["tasks"][0]
            self.assertTrue(record["passed"])
            self.assertTrue(record["regraded"])
            self.assertEqual(record["answer"], "Prettier")
            self.assertEqual(record["duration_s"], 1.23)
            self.assertEqual(record["usage"], {"total_cost_usd": 0.01})

    def test_matrix_run_across_two_runners_produces_report_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "regex",
                            "prompt": "hello",
                            "check": {"type": "regex", "value": "ok hello"},
                            "timeout_s": 10,
                        },
                        {
                            "id": "command",
                            "prompt": "world",
                            "check": {"type": "command", "value": "test -f AGENTS.md"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            report = Path(td) / "matrix.md"
            matrix_json = Path(td) / "matrix.json"
            runner_ok = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            runner_bad = f"{sys.executable} -c \"print('nope')\""
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--runner-cmd",
                    f"good={runner_ok}",
                    "--runner-cmd",
                    f"bad={runner_bad}",
                    "--matrix-report",
                    str(report),
                    "--matrix-json",
                    str(matrix_json),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

            text = report.read_text(encoding="utf-8")
            self.assertIn("Eval Matrix Report", text)
            self.assertIn("good", text)
            self.assertIn("bad", text)
            self.assertIn("Per-agent pass rate", text)
            self.assertIn("| `regex` |", text)

            data = json.loads(matrix_json.read_text(encoding="utf-8"))
            self.assertEqual(set(data["agents"].keys()), {"good", "bad"})
            self.assertEqual(data["summary"]["good"]["passed"], 2)
            self.assertEqual(data["summary"]["good"]["total"], 2)
            # `bad` fails the regex task but passes the command task (AGENTS.md exists).
            self.assertEqual(data["summary"]["bad"]["passed"], 1)

    def test_matrix_from_matrix_file(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "regex",
                            "prompt": "hello",
                            "check": {"type": "regex", "value": "ok hello"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            matrix_file = Path(td) / "agents.json"
            runner_ok = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            matrix_file.write_text(json.dumps({"alpha": runner_ok}), encoding="utf-8")
            report = Path(td) / "matrix.md"
            matrix_json = Path(td) / "matrix.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--matrix",
                    str(matrix_file),
                    "--matrix-report",
                    str(report),
                    "--matrix-json",
                    str(matrix_json),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(matrix_json.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["alpha"]["passed"], 1)

    def test_judge_check_passes_with_passing_judge_and_fails_with_failing_judge(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "judged",
                            "prompt": "explain",
                            "check": {"type": "judge", "rubric": "must be correct"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            runner = f"{sys.executable} -c \"print('the answer')\""

            pass_judge = 'printf \'{"passed":true,"score":1.0,"reason":"ok"}\''
            out_pass = Path(td) / "pass.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "pass",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "--judge-cmd",
                    pass_judge,
                    "-o",
                    str(out_pass),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out_pass.read_text(encoding="utf-8"))
            record = data["tasks"][0]
            self.assertTrue(record["passed"])
            self.assertEqual(record["judge"]["score"], 1.0)
            self.assertTrue(record["judge"]["passed"])

            fail_judge = 'printf \'{"passed":false,"score":0.0,"reason":"bad"}\''
            out_fail = Path(td) / "fail.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "fail",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "--judge-cmd",
                    fail_judge,
                    "-o",
                    str(out_fail),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out_fail.read_text(encoding="utf-8"))
            record = data["tasks"][0]
            self.assertFalse(record["passed"])
            self.assertFalse(record["judge"]["passed"])

    def test_judge_receives_answer_and_rubric_via_env(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "judged",
                            "prompt": "explain",
                            "check": {"type": "judge", "rubric": "mention-foo"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            runner = f"{sys.executable} -c \"print('foo answer')\""
            # The judge passes only if the answer contains the rubric-required token.
            judge = (
                f'{sys.executable} -c "import os,json;'
                "a=os.environ['JUDGE_ANSWER'];r=os.environ['JUDGE_RUBRIC'];"
                "ok='foo' in a and r=='mention-foo';"
                "print(json.dumps({'passed':ok,'score':1.0 if ok else 0.0}))\""
            )
            out = Path(td) / "res.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "envjudge",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "--judge-cmd",
                    judge,
                    "-o",
                    str(out),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(data["tasks"][0]["passed"])

    def test_command_check_timeout_is_graded_as_non_crashing_fail(self):
        # grade_answer must swallow a slow `command` check and return a plain
        # fail (passed=False) without raising subprocess.TimeoutExpired.
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            task = {
                "id": "slow-check",
                "prompt": "x",
                "check": {"type": "command", "value": "sleep 5"},
                "timeout_s": 0.1,
            }
            passed, judge_info = eval_run.grade_answer(task, "answer", workdir, None)
            self.assertFalse(passed)
            self.assertIsNone(judge_info)

    def test_command_check_does_not_allow_shell_injection(self):
        # SEC-04: a `command` check is untrusted task data. Shell metacharacters
        # must NOT spawn extra commands — the injected `touch pwned` must never
        # create a file, even though the leading `true` "succeeds".
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            sentinel = workdir / "pwned"
            task = {
                "id": "inject",
                "prompt": "x",
                "check": {"type": "command", "value": f"true; touch {sentinel}"},
                "timeout_s": 5,
            }
            passed, judge_info = eval_run.grade_answer(task, "answer", workdir, None)
            # `true; touch ...` tokenizes to argv ["true", ";", "touch", ...];
            # `true` ignores its args and exits 0, but no shell ran the `touch`.
            self.assertFalse(sentinel.exists(), "shell injection executed the payload")
            self.assertIsNone(judge_info)

    def test_command_check_legitimate_command_still_passes(self):
        # A plain, well-formed command still works via shlex.split + argv exec.
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            (workdir / "AGENTS.md").write_text("x", encoding="utf-8")
            task = {
                "id": "ok",
                "prompt": "x",
                "check": {"type": "command", "value": "test -f AGENTS.md"},
                "timeout_s": 5,
            }
            passed, judge_info = eval_run.grade_answer(task, "answer", workdir, None)
            self.assertTrue(passed)
            self.assertIsNone(judge_info)

    def test_runner_prompt_with_shell_metacharacters_is_not_executed(self):
        # SEC-04: the runner template substitutes {prompt} with shlex.quote, so a
        # prompt full of shell metacharacters cannot break out of the runner
        # command and run an injected payload.
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            sentinel = workdir / "pwned"
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "inject",
                            "prompt": f"hi; touch {sentinel}",
                            "check": {"type": "regex", "value": ".*"},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            output = Path(td) / "results.json"
            runner = "echo {prompt}"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--runner",
                    runner,
                    "--label",
                    "inject",
                    "--workdir",
                    str(workdir),
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertFalse(sentinel.exists(), "prompt shell injection executed the payload")

    def test_run_tasks_command_check_timeout_records_non_crashing_fail(self):
        # End-to-end: a command check that times out is a fail, and run_tasks
        # still emits the full record (does not crash, keeps timed_out field).
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "slow",
                            "prompt": "x",
                            "check": {"type": "command", "value": "sleep 30"},
                            # Wide margin so timing is deterministic under CI load:
                            # the runner (a shell echo) finishes in milliseconds while
                            # the check (sleep 30) always exceeds the 1s budget.
                            "timeout_s": 1,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            output = Path(td) / "results.json"
            runner = "echo done"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "slow",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            record = data["tasks"][0]
            self.assertFalse(record["passed"])
            self.assertFalse(record["timed_out"])
            self.assertEqual(record["exit_code"], 0)
            self.assertIn("answer", record)


class MaybeUsageTests(unittest.TestCase):
    def test_object_payload_extracts_known_usage_keys(self):
        out = json.dumps({"result": "ok", "usage": {"input_tokens": 3}, "cost": 0.01, "other": 1})
        self.assertEqual(eval_run.maybe_usage(out), {"usage": {"input_tokens": 3}, "cost": 0.01})

    def test_non_json_returns_empty(self):
        self.assertEqual(eval_run.maybe_usage("plain text answer"), {})

    def test_bare_scalar_does_not_crash(self):
        # A runner printing a bare JSON scalar must not raise TypeError and abort
        # the whole eval batch; it simply carries no usage.
        for payload in ("42", "3.14", '"just a string"', "true", "null"):
            self.assertEqual(eval_run.maybe_usage(payload), {})

    def test_bare_array_does_not_crash(self):
        self.assertEqual(eval_run.maybe_usage('["usage", "cost"]'), {})


class BuiltinJudgeTests(unittest.TestCase):
    def test_expect_all_must_match(self):
        v = eval_run.builtin_judge("has canonical AGENTS.md", {"expect": ["canonical", "AGENTS.md"]})
        self.assertTrue(v["passed"])
        self.assertEqual(v["score"], 1.0)
        self.assertEqual(v["judge"], "builtin")

    def test_expect_missing_one_fails(self):
        v = eval_run.builtin_judge("has canonical only", {"expect": ["canonical", "drift"]})
        self.assertFalse(v["passed"])
        self.assertEqual(v["score"], 0.5)

    def test_reject_pattern_present_fails(self):
        v = eval_run.builtin_judge("this has a TODO", {"expect": ["this"], "reject": ["TODO"]})
        self.assertFalse(v["passed"])

    def test_rubric_keyword_coverage(self):
        check = {"rubric": "must mention `AGENTS.md` and `drift`"}
        good = eval_run.builtin_judge("AGENTS.md prevents drift", check)
        self.assertTrue(good["passed"])
        bad = eval_run.builtin_judge("nothing relevant here", check)
        self.assertFalse(bad["passed"])

    def test_no_criteria_is_unpassable(self):
        v = eval_run.builtin_judge("anything", {"type": "judge"})
        self.assertFalse(v["passed"])
        self.assertIn("needs", v["reason"])

    def test_grade_answer_uses_builtin_judge_without_cmd(self):
        task = {"id": "j", "check": {"type": "judge", "expect": ["ok"]}}
        passed, info = eval_run.grade_answer(task, "ok answer", ".", None)
        self.assertTrue(passed)
        self.assertEqual(info["judge"], "builtin")

    def test_grade_answer_legacy_no_default_judge(self):
        task = {"id": "j", "check": {"type": "judge", "expect": ["ok"]}}
        passed, info = eval_run.grade_answer(task, "ok answer", ".", None, default_judge=False)
        self.assertFalse(passed)
        self.assertIn("no --judge-cmd", info["reason"])


class HealthScoreTests(unittest.TestCase):
    def test_compute_health_from_tasks(self):
        data = {"tasks": [{"passed": True}, {"passed": False}, {"passed": True}, {"passed": True}]}
        health = eval_run.compute_health(data)
        self.assertEqual(health["passed"], 3)
        self.assertEqual(health["total"], 4)
        self.assertEqual(health["score"], 75)
        self.assertEqual(health["grade"], "C")

    def test_compute_health_from_matrix(self):
        data = {
            "agents": {
                "a": {"tasks": [{"passed": True}, {"passed": True}]},
                "b": {"tasks": [{"passed": False}, {"passed": True}]},
            }
        }
        health = eval_run.compute_health(data)
        self.assertEqual(health["total"], 4)
        self.assertEqual(health["score"], 75)

    def test_grade_boundaries(self):
        self.assertEqual(eval_run.health_grade(90), "A")
        self.assertEqual(eval_run.health_grade(89), "B")
        self.assertEqual(eval_run.health_grade(0), "F")

    def test_run_tasks_emits_health_and_fail_under_gate(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "j",
                            "prompt": "x",
                            "check": {"type": "judge", "expect": ["never-there"]},
                            "timeout_s": 10,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            output = Path(td) / "results.json"
            runner = f"{sys.executable} -c \"print('unrelated')\""
            base = [
                sys.executable,
                str(EVAL),
                "--tasks",
                str(tasks),
                "--label",
                "h",
                "--workdir",
                str(workdir),
                "--runner",
                runner,
                "--judge-llm",
                "off",
                "-o",
                str(output),
            ]
            proc = subprocess.run(base, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("health", data)
            self.assertEqual(data["health"]["score"], 0)
            gated = subprocess.run(base + ["--fail-under", "50"], text=True, capture_output=True)
            self.assertEqual(gated.returncode, 5, gated.stdout)

    def test_score_subcommand_reads_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            results = Path(td) / "r.json"
            results.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {"id": "one", "passed": True},
                            {"id": "two", "passed": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--score", str(results), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["score"], 100)
            gated = subprocess.run(
                [sys.executable, str(EVAL), "--score", str(results), "--fail-under", "100"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(gated.returncode, 0)


class StoredResultIntegrityTests(unittest.TestCase):
    def _run_score(self, path, *extra):
        return subprocess.run(
            [
                sys.executable,
                str(EVAL),
                "--score",
                str(path),
                *extra,
            ],
            text=True,
            capture_output=True,
        )

    def test_forged_health_cannot_pass_threshold_or_mutate_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = root / "forged.json"
            result.write_text(
                json.dumps(
                    {
                        "tasks": [
                            {
                                "id": "failed",
                                "passed": False,
                                "timed_out": False,
                            }
                        ],
                        "health": {
                            "score": 100,
                            "grade": "A",
                            "passed": 1,
                            "total": 1,
                            "timed_out": 0,
                            "pass_rate": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            baseline = root / "baseline.json"

            proc = self._run_score(
                result,
                "--fail-under",
                "80",
                "--json",
                "--baseline",
                str(baseline),
                "--save-baseline",
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn(
                "result error: result health field `score` does not match",
                proc.stderr,
            )
            self.assertEqual(proc.stdout, "")
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(baseline.exists())

    def test_malformed_tasks_fail_with_or_without_forged_health(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, health in (
                ("with-health", {"score": 100}),
                ("without-health", None),
            ):
                with self.subTest(name=name):
                    result = root / f"{name}.json"
                    payload = {"tasks": "not-a-list"}
                    if health is not None:
                        payload["health"] = health
                    result.write_text(json.dumps(payload), encoding="utf-8")

                    proc = self._run_score(result, "--json")

                    self.assertEqual(proc.returncode, 2)
                    self.assertIn("result error: tasks must be an array", proc.stderr)
                    self.assertEqual(proc.stdout, "")
                    self.assertNotIn("Traceback", proc.stderr)

    def test_result_record_schema_and_ambiguity_fail_closed(self):
        cases = [
            ("root", [], "result file must contain a JSON object"),
            ("missing-family", {}, "exactly one primary result family"),
            (
                "ambiguous",
                {"tasks": [], "agents": {}},
                "exactly one primary result family",
            ),
            ("record-object", {"tasks": [1]}, "record 0 must be an object"),
            (
                "id",
                {"tasks": [{"id": "", "passed": True}]},
                "field `id` must be a non-empty string",
            ),
            (
                "duplicate",
                {
                    "tasks": [
                        {"id": "same", "passed": True},
                        {"id": "same", "passed": False},
                    ]
                },
                "field `id` must be unique",
            ),
            (
                "passed",
                {"tasks": [{"id": "x", "passed": 1}]},
                "field `passed` must be a boolean",
            ),
            (
                "timed-out",
                {"tasks": [{"id": "x", "passed": False, "timed_out": 0}]},
                "field `timed_out` must be a boolean",
            ),
            (
                "rounds",
                {"round_results": "bad"},
                "round_results must be an array",
            ),
            (
                "round-object",
                {"round_results": [1]},
                "round_results entry 0 must be an object",
            ),
            (
                "round-tasks",
                {"round_results": [{}]},
                "must contain `tasks`",
            ),
            ("agents", {"agents": []}, "agents must be an object"),
            (
                "agent-object",
                {"agents": {"one": []}},
                "agents entry 0 must be an object",
            ),
            (
                "agent-tasks",
                {"agents": {"one": {}}},
                "must contain `tasks`",
            ),
            (
                "health-object",
                {
                    "tasks": [{"id": "x", "passed": True}],
                    "health": "great",
                },
                "health must be an object",
            ),
            (
                "health-grade",
                {
                    "tasks": [{"id": "x", "passed": True}],
                    "health": {"score": 100, "grade": "F"},
                },
                "health field `grade` does not match",
            ),
        ]
        for name, payload, expected in cases:
            with self.subTest(name=name):
                with self.assertRaises(eval_run.ResultFileError) as caught:
                    eval_run.validate_result(payload)
                self.assertIn(expected, str(caught.exception))

    def test_historical_partial_health_and_additive_fields_are_compatible(self):
        data = {
            "label": "historical",
            "tasks": [
                {"id": "one", "passed": True, "future": {"x": 1}},
                {"id": "two", "passed": False},
            ],
            "health": {
                "score": 50,
                "grade": "F",
                "passed": 1,
                "total": 2,
                "legacy": "preserved",
            },
        }

        result = eval_run.validate_result(data)

        self.assertIs(result["data"], data)
        self.assertEqual(result["health"]["score"], 50)
        self.assertEqual(result["health"]["timed_out"], 0)
        self.assertEqual(data["health"]["legacy"], "preserved")

    def test_multi_round_and_matrix_health_is_derived_from_all_records(self):
        multi = {
            "round_results": [
                {
                    "round": 1,
                    "tasks": [{"id": "x", "passed": True}],
                    "health": {"score": 100, "grade": "A"},
                },
                {
                    "round": 2,
                    "tasks": [{"id": "x", "passed": False}],
                    "health": {"score": 0, "grade": "F"},
                },
            ],
            "health": {"score": 50, "passed": 1, "total": 2},
        }
        matrix = {
            "agents": {
                "one": {"tasks": [{"id": "x", "passed": True}]},
                "two": {"tasks": [{"id": "x", "passed": False}]},
            },
            "health": {"score": 50, "passed": 1, "total": 2},
        }

        self.assertEqual(eval_run.validate_result(multi)["health"]["score"], 50)
        self.assertEqual(eval_run.validate_result(matrix)["health"]["score"], 50)

        multi["round_results"][1]["health"]["score"] = 100
        with self.assertRaises(eval_run.ResultFileError) as caught:
            eval_run.validate_result(multi)
        self.assertIn("round_results entry 1 health field `score`", str(caught.exception))

    def test_ids_repeat_across_rounds_and_agents_but_not_within_one_array(self):
        multi = {
            "round_results": [
                {"tasks": [{"id": "same", "passed": True}]},
                {"tasks": [{"id": "same", "passed": False}]},
            ]
        }
        matrix = {
            "agents": {
                "one": {"tasks": [{"id": "same", "passed": True}]},
                "two": {"tasks": [{"id": "same", "passed": False}]},
            }
        }

        self.assertEqual(eval_run.validate_result(multi)["health"]["total"], 2)
        self.assertEqual(eval_run.validate_result(matrix)["health"]["total"], 2)

    def test_stats_keeps_legacy_bare_round_list_compatibility(self):
        with tempfile.TemporaryDirectory() as td:
            rounds = Path(td) / "rounds.json"
            rounds.write_text(
                json.dumps(
                    [
                        {"tasks": [{"id": "x", "passed": True}]},
                        {"tasks": [{"id": "x", "passed": False}]},
                    ]
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--stats",
                    str(rounds),
                    "--json",
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["health"]["score"], 50)

    def test_invalid_compare_and_regrade_do_not_write_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            invalid = root / "invalid.json"
            invalid.write_text(
                json.dumps({"tasks": [{"id": "x", "passed": "yes"}]}),
                encoding="utf-8",
            )
            valid = root / "valid.json"
            valid.write_text(
                json.dumps({"tasks": [{"id": "x", "passed": True}]}),
                encoding="utf-8",
            )
            report = root / "compare.md"
            compare = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--compare",
                    str(invalid),
                    str(valid),
                    "-o",
                    str(report),
                ],
                text=True,
                capture_output=True,
            )

            tasks = root / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "x",
                            "prompt": "x",
                            "check": {"type": "regex", "value": "x"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            regraded = root / "regraded.json"
            regrade = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(invalid),
                    "--tasks",
                    str(tasks),
                    "-o",
                    str(regraded),
                ],
                text=True,
                capture_output=True,
            )

            for proc in (compare, regrade):
                self.assertEqual(proc.returncode, 2)
                self.assertIn("result error:", proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(report.exists())
            self.assertFalse(regraded.exists())

    def test_regrade_validates_result_before_evidence_hash_or_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            invalid = root / "invalid.json"
            invalid.write_text(
                json.dumps({"tasks": [{"id": "x", "passed": "yes"}]}),
                encoding="utf-8",
            )
            tasks = root / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "x",
                            "prompt": "x",
                            "check": {"type": "regex", "value": "x"},
                            "evidence": ["missing-secret-evidence.txt"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            output = root / "output.json"

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(invalid),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(root),
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn("result error:", proc.stderr)
            self.assertNotIn("missing-secret-evidence", proc.stderr)
            self.assertFalse(output.exists())

    def test_result_file_error_hides_absolute_path_and_content(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "secret-result-name.json"
            path.write_text("{private-content", encoding="utf-8")

            with self.assertRaises(eval_run.ResultFileError) as caught:
                eval_run.load_result_file(path)

            message = str(caught.exception)
            self.assertIn(path.name, message)
            self.assertNotIn(str(Path(td).resolve()), message)
            self.assertNotIn("private-content", message)


class EvidenceFingerprintTests(unittest.TestCase):
    def _fixture(self, td):
        root = Path(td)
        workdir = root / "repo"
        workdir.mkdir()
        agents = workdir / "AGENTS.md"
        agents.write_text("# Project overview\nDemo.\n", encoding="utf-8")
        tasks = root / "tasks.json"
        tasks.write_text(
            json.dumps(
                [
                    {
                        "id": "answer",
                        "prompt": "answer",
                        "check": {"type": "regex", "value": "^ok$"},
                        "timeout_s": 10,
                    }
                ]
            ),
            encoding="utf-8",
        )
        runner = f"{sys.executable} -c \"print('ok')\""
        return workdir, agents, tasks, runner

    def _run_with_evidence(self, td):
        workdir, agents, tasks, runner = self._fixture(td)
        output = Path(td) / "results.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(EVAL),
                "--tasks",
                str(tasks),
                "--label",
                "evidence",
                "--workdir",
                str(workdir),
                "--runner",
                runner,
                "--evidence",
                "AGENTS.md",
                "-o",
                str(output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return workdir, agents, tasks, output

    def test_manifest_is_deterministic_relative_and_deduped(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, agents, tasks, _runner = self._fixture(td)
            first = eval_run.build_evidence_manifest(
                tasks,
                ["AGENTS.md", str(agents), "AGENTS.md"],
                workdir,
            )
            second = eval_run.build_evidence_manifest(tasks, [str(agents)], workdir)
            self.assertEqual(first, second)
            self.assertEqual(first["schemaVersion"], 1)
            self.assertEqual(first["tasks"]["path"], "tasks.json")
            self.assertEqual([item["path"] for item in first["files"]], ["AGENTS.md"])
            self.assertRegex(first["tasks"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertNotIn(str(Path(td).resolve()), json.dumps(first))

    def test_task_declared_and_explicit_evidence_are_unioned_automatically(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("instructions\n", encoding="utf-8")
            (workdir / "package.json").write_text('{"scripts":{"test":"ok"}}\n', encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "test",
                            "prompt": "test",
                            "check": {"type": "regex", "value": "ok"},
                            "evidence": ["package.json", "package.json"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            manifest = eval_run.build_evidence_manifest(
                tasks,
                ["AGENTS.md"],
                workdir,
            )

            self.assertTrue(manifest["taskEvidence"])
            self.assertEqual(
                [item["path"] for item in manifest["files"]],
                ["AGENTS.md", "package.json"],
            )

    def test_task_evidence_rejects_malformed_escape_and_external_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            workdir = base / "repo"
            workdir.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            linked = workdir / "linked.txt"
            try:
                linked.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")

            bad_values = [
                "not-a-list",
                [""],
                [42],
                ["../outside.txt"],
                ["linked.txt"],
            ]
            for declared in bad_values:
                with self.subTest(declared=declared):
                    tasks = base / "tasks.json"
                    tasks.write_text(
                        json.dumps(
                            [
                                {
                                    "id": "bad",
                                    "prompt": "bad",
                                    "check": {"type": "regex", "value": "x"},
                                    "evidence": declared,
                                }
                            ]
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ValueError) as caught:
                        eval_run.build_evidence_manifest(tasks, [], workdir)
                    message = str(caught.exception)
                    self.assertNotIn(str(base.resolve()), message)
                    if declared == ["../outside.txt"]:
                        self.assertIn("../outside.txt", message)
                    elif declared == ["linked.txt"]:
                        self.assertIn("linked.txt", message)

    def test_invalid_task_evidence_fails_before_runner_executes(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            marker = Path(td) / "runner-executed"
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "bad",
                            "prompt": "bad",
                            "check": {"type": "regex", "value": "ok"},
                            "evidence": ["../outside.txt"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            runner = (
                f"{sys.executable} -c "
                f"\"from pathlib import Path; Path({str(marker)!r}).write_text('ran')\""
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "preflight",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                ],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("evidence path escapes workdir: ../outside.txt", proc.stderr)
            self.assertFalse(marker.exists())

    def test_directory_evidence_binds_type_not_recursive_contents(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            components = workdir / "src" / "components"
            components.mkdir(parents=True)
            child = components / "Button.tsx"
            child.write_text("v1\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "components",
                            "prompt": "where",
                            "check": {"type": "regex", "value": "src/components"},
                            "evidence": ["src/components"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            first = eval_run.build_evidence_manifest(tasks, [], workdir)
            child.write_text("v2\n", encoding="utf-8")
            second = eval_run.build_evidence_manifest(tasks, [], workdir)
            self.assertEqual(first, second)
            self.assertEqual(
                first["files"],
                [{"path": "src/components", "kind": "directory"}],
            )

            child.unlink()
            components.rmdir()
            (workdir / "src" / "components").write_text("now a file\n", encoding="utf-8")
            changed = eval_run.build_evidence_manifest(tasks, [], workdir)
            self.assertNotEqual(first["files"], changed["files"])

    def test_directory_evidence_strict_score_detects_missing_and_type_change(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            components = workdir / "src" / "components"
            components.mkdir(parents=True)
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "components",
                            "prompt": "where",
                            "check": {"type": "regex", "value": "src/components"},
                            "evidence": ["src/components"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            result = Path(td) / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "tasks": [{"id": "components", "passed": True}],
                        "health": {
                            "score": 100,
                            "grade": "A",
                            "passed": 1,
                            "total": 1,
                            "timed_out": 0,
                        },
                        "evidence": eval_run.build_evidence_manifest(tasks, [], workdir),
                    }
                ),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(EVAL),
                "--score",
                str(result),
                "--tasks",
                str(tasks),
                "--workdir",
                str(workdir),
                "--require-current-evidence",
            ]
            current = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(current.returncode, 0, current.stderr)

            components.rmdir()
            missing = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(missing.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("evidence path does not exist: src/components", missing.stderr)

            components.write_text("now a file\n", encoding="utf-8")
            changed = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(changed.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("evidence changed: src/components", changed.stderr)

    def test_contained_symlink_evidence_keeps_lexical_path(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            shared = workdir / "shared"
            shared.mkdir(parents=True)
            (shared / "package.json").write_text("{}\n", encoding="utf-8")
            try:
                (workdir / "package.json").symlink_to(shared / "package.json")
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "package",
                            "prompt": "package",
                            "check": {"type": "regex", "value": "x"},
                            "evidence": ["package.json"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            manifest = eval_run.build_evidence_manifest(tasks, [], workdir)

            self.assertEqual(manifest["files"][0]["path"], "package.json")

    def test_run_result_is_stamped_only_when_explicitly_requested(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, _agents, tasks, runner = self._fixture(td)
            legacy = Path(td) / "legacy.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "legacy",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "-o",
                    str(legacy),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertNotIn("evidence", json.loads(legacy.read_text(encoding="utf-8")))

        with tempfile.TemporaryDirectory() as td:
            _workdir, _agents, _tasks, stamped = self._run_with_evidence(td)
            data = json.loads(stamped.read_text(encoding="utf-8"))
            self.assertEqual(data["evidence"]["files"][0]["path"], "AGENTS.md")
            self.assertEqual(data["health"]["score"], 100)

    def test_current_evidence_passes_and_changed_inputs_exit_seven(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, agents, tasks, output = self._run_with_evidence(td)
            command = [
                sys.executable,
                str(EVAL),
                "--score",
                str(output),
                "--tasks",
                str(tasks),
                "--workdir",
                str(workdir),
                "--evidence",
                "AGENTS.md",
                "--require-current-evidence",
                "--fail-under",
                "100",
            ]
            current = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)

            agents.write_text("# Project overview\nChanged.\n", encoding="utf-8")
            changed_agents = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(changed_agents.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("evidence changed: AGENTS.md", changed_agents.stderr)
            self.assertNotIn("Changed.", changed_agents.stderr)

            agents.write_text("# Project overview\nDemo.\n", encoding="utf-8")
            tasks.write_text(tasks.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            changed_tasks = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(changed_tasks.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("tasks changed: tasks.json", changed_tasks.stderr)

    def test_legacy_schema_v1_manifest_keeps_explicit_only_verification(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            agents = workdir / "AGENTS.md"
            agents.write_text("instructions\n", encoding="utf-8")
            (workdir / "package.json").write_text("{}\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "legacy",
                            "prompt": "legacy",
                            "check": {"type": "regex", "value": "ok"},
                            "evidence": ["package.json"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            # Simulate a schema-v1 result stamped before task-level evidence
            # became executable. The historical manifest contains only the
            # explicit AGENTS.md source and has no additive taskEvidence marker.
            legacy_manifest = eval_run._build_evidence_manifest(
                tasks,
                ["AGENTS.md"],
                workdir,
            )
            result = Path(td) / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "tasks": [{"id": "legacy", "passed": True}],
                        "health": {
                            "score": 100,
                            "grade": "A",
                            "passed": 1,
                            "total": 1,
                            "timed_out": 0,
                        },
                        "evidence": legacy_manifest,
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--score",
                    str(result),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--evidence",
                    "AGENTS.md",
                    "--require-current-evidence",
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_generated_task_fact_change_exits_seven_without_repeating_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            package = repo / "packages" / "api"
            package.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (package / "AGENTS.md").write_text("Use API commands.\n", encoding="utf-8")
            manifest = package / "package.json"
            manifest.write_text(
                json.dumps(
                    {
                        "scripts": {"test:api": "vitest run"},
                        "devDependencies": {"vitest": "1"},
                    }
                ),
                encoding="utf-8",
            )
            tasks = Path(td) / "tasks.json"
            generated = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--generate",
                    str(repo),
                    "--target",
                    "packages/api/src/x.py",
                    "-o",
                    str(tasks),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(generated.returncode, 0, generated.stderr)
            task_rows = json.loads(tasks.read_text(encoding="utf-8"))
            raw = Path(td) / "raw.json"
            raw.write_text(
                json.dumps(
                    {
                        "label": "manual",
                        "tasks": [
                            {"id": task["id"], "stdout": "pnpm"}
                            for task in task_rows
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = Path(td) / "result.json"
            regraded = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(raw),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(repo),
                    "-o",
                    str(result),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(regraded.returncode, 0, regraded.stderr)
            stored = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(
                [item["path"] for item in stored["evidence"]["files"]],
                [
                    "packages/api/package.json",
                    "pnpm-lock.yaml",
                ],
            )
            score = [
                sys.executable,
                str(EVAL),
                "--score",
                str(result),
                "--tasks",
                str(tasks),
                "--workdir",
                str(repo),
                "--require-current-evidence",
            ]
            current = subprocess.run(score, text=True, capture_output=True)
            self.assertEqual(current.returncode, 0, current.stderr)

            manifest.write_text(
                json.dumps(
                    {
                        "scripts": {"test:api": "jest"},
                        "devDependencies": {"jest": "1"},
                    }
                ),
                encoding="utf-8",
            )
            stale = subprocess.run(score, text=True, capture_output=True)
            self.assertEqual(stale.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("evidence changed: packages/api/package.json", stale.stderr)

    def test_strict_mode_rejects_unstamped_legacy_result(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, _agents, tasks, _runner = self._fixture(td)
            result = Path(td) / "legacy.json"
            result.write_text(
                json.dumps({"tasks": [{"id": "answer", "passed": True}]}),
                encoding="utf-8",
            )
            strict = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--score",
                    str(result),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--evidence",
                    "AGENTS.md",
                    "--require-current-evidence",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(strict.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("no evidence manifest", strict.stderr)

            legacy = subprocess.run(
                [sys.executable, str(EVAL), "--score", str(result)],
                text=True,
                capture_output=True,
            )
            self.assertEqual(legacy.returncode, 0, legacy.stderr)

    def test_strict_mode_fails_closed_on_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, _agents, tasks, _runner = self._fixture(td)
            result = Path(td) / "malformed.json"
            result.write_text(
                json.dumps(
                    {
                        "tasks": [{"id": "answer", "passed": True}],
                        "evidence": {
                            "schemaVersion": 1,
                            "tasks": "not-an-object",
                            "files": None,
                        },
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--score",
                    str(result),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--evidence",
                    "AGENTS.md",
                    "--require-current-evidence",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, eval_run.EVIDENCE_STALE_EXIT)
            self.assertIn("malformed tasks evidence", proc.stderr)
            self.assertIn("malformed evidence file list", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)

    def test_evidence_escape_and_external_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workdir, _agents, tasks, runner = self._fixture(td)
            outside = root / "outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            link = workdir / "linked.md"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported on this platform")
            for evidence in ("../outside.md", "linked.md"):
                with self.subTest(evidence=evidence):
                    proc = subprocess.run(
                        [
                            sys.executable,
                            str(EVAL),
                            "--tasks",
                            str(tasks),
                            "--label",
                            "unsafe",
                            "--workdir",
                            str(workdir),
                            "--runner",
                            runner,
                            "--evidence",
                            evidence,
                            "-o",
                            str(root / "unsafe.json"),
                        ],
                        text=True,
                        capture_output=True,
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn("escapes workdir", proc.stderr)
                    self.assertNotIn("outside\n", proc.stderr)

    def test_matrix_and_regrade_results_are_stamped(self):
        with tempfile.TemporaryDirectory() as td:
            workdir, _agents, tasks, runner = self._fixture(td)
            matrix = Path(td) / "matrix.json"
            report = Path(td) / "matrix.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--runner-cmd",
                    f"one={runner}",
                    "--matrix-json",
                    str(matrix),
                    "--matrix-report",
                    str(report),
                    "--evidence",
                    "AGENTS.md",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("evidence", json.loads(matrix.read_text(encoding="utf-8")))

            raw = Path(td) / "raw.json"
            raw.write_text(
                json.dumps(
                    {
                        "label": "manual",
                        "tasks": [{"id": "answer", "stdout": "ok", "passed": False}],
                    }
                ),
                encoding="utf-8",
            )
            regraded = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(raw),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--evidence",
                    "AGENTS.md",
                    "-o",
                    str(raw),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(regraded.returncode, 0, regraded.stdout + regraded.stderr)
            data = json.loads(raw.read_text(encoding="utf-8"))
            self.assertTrue(data["tasks"][0]["passed"])
            self.assertIn("evidence", data)

    def test_generated_task_evidence_stamps_single_multi_matrix_and_regrade(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "fact.txt").write_text("ok\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "answer",
                            "prompt": "answer",
                            "check": {"type": "regex", "value": "^ok$"},
                            "timeout_s": 10,
                            "evidence": ["fact.txt"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            runner = f"{sys.executable} -c \"print('ok')\""
            single = Path(td) / "single.json"
            multi = Path(td) / "multi.json"
            for extra, output in (([], single), (["--rounds", "2"], multi)):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(EVAL),
                        "--tasks",
                        str(tasks),
                        "--label",
                        "generated",
                        "--workdir",
                        str(workdir),
                        "--runner",
                        runner,
                        *extra,
                        "-o",
                        str(output),
                    ],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)

            matrix = Path(td) / "matrix.json"
            report = Path(td) / "matrix.md"
            matrix_proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "--runner-cmd",
                    f"one={runner}",
                    "--matrix-json",
                    str(matrix),
                    "--matrix-report",
                    str(report),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(matrix_proc.returncode, 0, matrix_proc.stderr)

            raw = Path(td) / "raw.json"
            raw.write_text(
                json.dumps({"tasks": [{"id": "answer", "stdout": "ok"}]}),
                encoding="utf-8",
            )
            regraded = Path(td) / "regraded.json"
            regrade_proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(raw),
                    "--tasks",
                    str(tasks),
                    "--workdir",
                    str(workdir),
                    "-o",
                    str(regraded),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(regrade_proc.returncode, 0, regrade_proc.stderr)

            for output in (single, multi, matrix, regraded):
                with self.subTest(output=output):
                    manifest = json.loads(output.read_text(encoding="utf-8"))["evidence"]
                    self.assertEqual(
                        [item["path"] for item in manifest["files"]],
                        ["fact.txt"],
                    )

    def test_regrade_task_evidence_requires_workdir_with_clear_error(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {
                            "id": "answer",
                            "prompt": "answer",
                            "check": {"type": "regex", "value": "^ok$"},
                            "evidence": ["fact.txt"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            raw = Path(td) / "raw.json"
            raw.write_text(
                json.dumps({"tasks": [{"id": "answer", "stdout": "ok"}]}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--regrade",
                    str(raw),
                    "--tasks",
                    str(tasks),
                ],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(
                "evidence error: --workdir is required for task-declared evidence",
                proc.stderr,
            )
            self.assertNotIn("Traceback", proc.stderr)


class MultiRoundStatsTests(unittest.TestCase):
    """Deterministic multi-round runs: one stable task, one flaky task."""

    def _write_scenario(self, td):
        # A runner that keeps a per-prompt counter file so behaviour is fully
        # deterministic across rounds: `stable` always passes; `flaky` passes on
        # the first round and fails on every later round.
        runner_py = Path(td) / "runner.py"
        runner_py.write_text(
            "import sys, os\n"
            "prompt = sys.argv[1]\n"
            "state = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'count-' + prompt + '.txt')\n"
            "count = int(open(state).read()) if os.path.exists(state) else 0\n"
            "open(state, 'w').write(str(count + 1))\n"
            "if prompt == 'flaky' and count > 0:\n"
            "    print('no')\n"
            "else:\n"
            "    print('ok')\n",
            encoding="utf-8",
        )
        tasks = Path(td) / "tasks.json"
        tasks.write_text(
            json.dumps(
                [
                    {"id": "stable", "prompt": "stable", "check": {"type": "regex", "value": "^ok$"}, "timeout_s": 10},
                    {"id": "flaky", "prompt": "flaky", "check": {"type": "regex", "value": "^ok$"}, "timeout_s": 10},
                ]
            ),
            encoding="utf-8",
        )
        runner = f"{sys.executable} {shlex_quote(str(runner_py))} {{prompt}}"
        return tasks, runner

    def test_rounds_produces_task_stats_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks, runner = self._write_scenario(td)
            output = Path(td) / "results.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "multi",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "--rounds",
                    "2",
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(data["rounds"], 2)
            self.assertEqual(len(data["round_results"]), 2)
            stats_by_id = {t["id"]: t for t in data["task_stats"]}
            self.assertEqual(stats_by_id["stable"]["runs"], 2)
            self.assertEqual(stats_by_id["stable"]["passed"], 2)
            self.assertFalse(stats_by_id["stable"]["flaky"])
            self.assertEqual(stats_by_id["flaky"]["runs"], 2)
            self.assertEqual(stats_by_id["flaky"]["passed"], 1)
            self.assertEqual(stats_by_id["flaky"]["failed"], 1)
            self.assertEqual(stats_by_id["flaky"]["pass_rate"], 0.5)
            self.assertTrue(stats_by_id["flaky"]["flaky"])
            stats = data["stats"]
            self.assertEqual(stats["rounds"], 2)
            self.assertEqual(stats["health_scores"], [100, 50])
            self.assertEqual(stats["mean_health"], 75.0)
            self.assertEqual(stats["stddev"], 25.0)
            self.assertEqual(stats["flaky_tasks"], ["flaky"])
            self.assertEqual(stats["flaky_count"], 1)
            # Overall health is the pass rate across all task-runs (3/4).
            self.assertEqual(data["health"]["score"], 75)
            self.assertIn("flaky tasks (1): flaky", proc.stdout)

    def test_single_round_default_output_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks, runner = self._write_scenario(td)
            output = Path(td) / "results.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "single",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            # Legacy shape: top-level tasks + health, no rounds/stats keys.
            self.assertIn("tasks", data)
            self.assertIn("health", data)
            self.assertNotIn("rounds", data)
            self.assertNotIn("round_results", data)
            self.assertNotIn("stats", data)

    def test_rounds_one_is_single_round(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks, runner = self._write_scenario(td)
            output = Path(td) / "results.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--tasks",
                    str(tasks),
                    "--label",
                    "one",
                    "--workdir",
                    str(workdir),
                    "--runner",
                    runner,
                    "--rounds",
                    "1",
                    "-o",
                    str(output),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("round_results", data)
            self.assertIn("tasks", data)

    def test_stats_subcommand_reads_existing_multi_round_file(self):
        with tempfile.TemporaryDirectory() as td:
            multi = Path(td) / "multi.json"
            multi.write_text(
                json.dumps(
                    {
                        "round_results": [
                            {"round": 1, "tasks": [{"id": "a", "passed": True}, {"id": "b", "passed": True}]},
                            {"round": 2, "tasks": [{"id": "a", "passed": True}, {"id": "b", "passed": False}]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--stats", str(multi), "--json"], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["stats"]["flaky_tasks"], ["b"])
            self.assertEqual(out["stats"]["health_scores"], [100, 50])
            self.assertEqual(out["health"]["score"], 75)

    def test_stats_fail_under_gate(self):
        with tempfile.TemporaryDirectory() as td:
            multi = Path(td) / "multi.json"
            multi.write_text(
                json.dumps(
                    {
                        "round_results": [
                            {"round": 1, "tasks": [{"id": "a", "passed": False}]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            gated = subprocess.run(
                [sys.executable, str(EVAL), "--stats", str(multi), "--fail-under", "50"], text=True, capture_output=True
            )
            self.assertEqual(gated.returncode, 5, gated.stdout)

    def test_summarize_rounds_unit(self):
        round_results = [
            {"tasks": [{"id": "a", "passed": True}, {"id": "b", "passed": True}]},
            {"tasks": [{"id": "a", "passed": False}, {"id": "b", "passed": True}]},
        ]
        task_stats, stats = eval_run.summarize_rounds(round_results)
        by_id = {t["id"]: t for t in task_stats}
        self.assertTrue(by_id["a"]["flaky"])
        self.assertFalse(by_id["b"]["flaky"])
        self.assertEqual(stats["mean_health"], 75.0)
        self.assertEqual(stats["min_health"], 50)
        self.assertEqual(stats["max_health"], 100)
        self.assertEqual(stats["flaky_tasks"], ["a"])


class _EnvGuard:
    """Context manager that temporarily sets/clears LLM API-key env vars."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = {}

    def __enter__(self):
        import os as _os

        for key, value in self.overrides.items():
            self.saved[key] = _os.environ.get(key)
            if value is None:
                _os.environ.pop(key, None)
            else:
                _os.environ[key] = value
        return self

    def __exit__(self, *exc):
        import os as _os

        for key, value in self.saved.items():
            if value is None:
                _os.environ.pop(key, None)
            else:
                _os.environ[key] = value
        return False


class GenerateTasksTests(unittest.TestCase):
    def _make_repo(self, td):
        repo = Path(td) / "repo"
        (repo / "src" / "components").mkdir(parents=True)
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "pnpm@9.0.0",
                    "engines": {"node": ">=20"},
                    "scripts": {"test": "vitest run", "lint": "eslint .", "build": "tsc", "dev": "vite"},
                    "devDependencies": {"vitest": "^1", "prettier": "^3"},
                }
            ),
            encoding="utf-8",
        )
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
        (repo / ".python-version").write_text("3.12\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text("# Overview\nUse Conventional Commits.\n", encoding="utf-8")
        (repo / "go.mod").write_text("module github.com/acme/widget\n\ngo 1.22\n", encoding="utf-8")
        return repo

    def test_generate_tasks_from_repo_facts(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(td)
            tasks = eval_run.generate_tasks(repo)
            by_id = {t["id"]: t for t in tasks}
            # Ground-truth facts become tasks.
            for tid in [
                "package-manager",
                "install",
                "test",
                "lint",
                "build",
                "dev",
                "test-framework",
                "formatter",
                "node-version",
                "go-version",
                "go-module",
                "commit-convention",
                "components-dir",
            ]:
                self.assertIn(tid, by_id, tid)
            # Every generated check is a regex over the true value.
            self.assertTrue(eval_run.regex_passes(by_id["install"]["check"]["value"], "pnpm install"))
            self.assertTrue(eval_run.regex_passes(by_id["test"]["check"]["value"], "pnpm test"))
            self.assertTrue(eval_run.regex_passes(by_id["node-version"]["check"]["value"], "Node 20"))
            self.assertTrue(eval_run.regex_passes(by_id["go-version"]["check"]["value"], "1.22"))
            self.assertTrue(eval_run.regex_passes(by_id["go-module"]["check"]["value"], "github.com/acme/widget"))
            self.assertFalse(eval_run.regex_passes(by_id["install"]["check"]["value"], "npm install"))
            for t in tasks:
                self.assertEqual(t["check"]["type"], "regex")

    def test_generate_cli_writes_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(td)
            out = Path(td) / "tasks.json"
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--generate", str(repo), "-o", str(out)], text=True, capture_output=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data), 10)
            self.assertTrue(all("prompt" in t and "check" in t for t in data))

    def test_detect_package_manager(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "yarn.lock").write_text("", encoding="utf-8")
            self.assertEqual(eval_run.detect_package_manager(repo), "yarn")

    def test_root_generation_ignores_external_fact_symlinks_without_leaking(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            outside = base / "outside"
            repo.mkdir()
            outside.mkdir()
            sentinel = "outside-only-command"
            (outside / "package.json").write_text(
                json.dumps(
                    {
                        "packageManager": "yarn@4.0.0",
                        "scripts": {"test": sentinel},
                        "devDependencies": {"jest": "1"},
                    }
                ),
                encoding="utf-8",
            )
            (outside / ".nvmrc").write_text("99\n", encoding="utf-8")
            (outside / "AGENTS.md").write_text("Use Conventional Commits.\n", encoding="utf-8")
            for name in ("package.json", ".nvmrc", "AGENTS.md"):
                try:
                    (repo / name).symlink_to(outside / name)
                except (OSError, NotImplementedError):
                    self.skipTest("file symlinks unsupported")

            tasks = eval_run.generate_tasks(repo)
            serialized = json.dumps(tasks)
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--generate", str(repo)],
                text=True,
                capture_output=True,
            )

            self.assertEqual(tasks, [])
            self.assertNotIn(sentinel, serialized)
            self.assertNotIn(str(base.resolve()), serialized)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout), [])
            self.assertNotIn(sentinel, proc.stdout + proc.stderr)
            self.assertNotIn(str(base.resolve()), proc.stdout + proc.stderr)

    def test_root_generation_supports_contained_fact_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            shared = repo / "shared"
            shared.mkdir()
            (shared / "package.json").write_text(
                json.dumps(
                    {
                        "packageManager": "pnpm@9.0.0",
                        "scripts": {"test": "vitest run"},
                    }
                ),
                encoding="utf-8",
            )
            (shared / ".nvmrc").write_text("20\n", encoding="utf-8")
            (shared / "AGENTS.md").write_text("Use Conventional Commits.\n", encoding="utf-8")
            for name in ("package.json", ".nvmrc", "AGENTS.md"):
                try:
                    (repo / name).symlink_to(shared / name)
                except (OSError, NotImplementedError):
                    self.skipTest("file symlinks unsupported")

            ids = {task["id"] for task in eval_run.generate_tasks(repo)}

            self.assertTrue({"package-manager", "install", "test", "node-version", "commit-convention"} <= ids)

    def test_scoped_generation_preserves_contained_symlink_evidence_path(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td).resolve()
            package = repo / "packages" / "api"
            shared = repo / "shared"
            package.mkdir(parents=True)
            shared.mkdir()
            (repo / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (package / "AGENTS.md").write_text("Use local commands.\n", encoding="utf-8")
            (shared / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest"}}),
                encoding="utf-8",
            )
            try:
                (package / "package.json").symlink_to(shared / "package.json")
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")

            tasks = eval_run.generate_tasks(repo, target="packages/api/src/x.py")
            test_task = next(task for task in tasks if task["id"].endswith(":test"))

            self.assertEqual(test_task["evidence"], ["packages/api/package.json"])

    def test_root_generation_abstains_from_command_tasks_on_competing_lockfiles(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"test": "vitest run"},
                        "devDependencies": {"vitest": "1"},
                    }
                ),
                encoding="utf-8",
            )
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (repo / "package-lock.json").write_text("{}\n", encoding="utf-8")

            ids = {task["id"] for task in eval_run.generate_tasks(repo)}

            self.assertNotIn("package-manager", ids)
            self.assertNotIn("install", ids)
            self.assertNotIn("test", ids)
            self.assertIn("test-framework", ids)

    def test_root_generation_uses_contained_package_manager_field_without_lockfile(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "package.json").write_text(
                json.dumps({"packageManager": "yarn@4.0.0", "scripts": {"test": "jest"}}),
                encoding="utf-8",
            )

            by_id = {task["id"]: task for task in eval_run.generate_tasks(repo)}

            self.assertTrue(eval_run.regex_passes(by_id["package-manager"]["check"]["value"], "yarn"))
            self.assertTrue(eval_run.regex_passes(by_id["test"]["check"]["value"], "yarn test"))

    def test_python_version_task_uses_unified_ground_truth(self):
        # When every pinned source agrees, emit the golden-answer task using the
        # same sources the scan/drift fact engine reads (semantic.python_ground_versions).
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / ".python-version").write_text("3.12\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n', encoding="utf-8")
            by_id = {t["id"]: t for t in eval_run.generate_tasks(repo)}
            self.assertIn("python-version", by_id)
            self.assertTrue(eval_run.regex_passes(by_id["python-version"]["check"]["value"], "Python 3.12"))
            self.assertFalse(eval_run.regex_passes(by_id["python-version"]["check"]["value"], "Python 3.11"))

    def test_python_version_task_abstains_on_conflicting_sources(self):
        # `.python-version` and pyproject `requires-python` disagreeing means the
        # repo has no unambiguous ground truth (the scanner reports this as a
        # MISMATCH). eval must not bake in one side as the golden answer.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / ".python-version").write_text("3.12\n", encoding="utf-8")
            (repo / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n', encoding="utf-8")
            by_id = {t["id"]: t for t in eval_run.generate_tasks(repo)}
            self.assertNotIn("python-version", by_id)

    def _make_scoped_repo(self, td):
        repo = Path(td) / "repo"
        (repo / "packages" / "api" / "src").mkdir(parents=True)
        (repo / "packages" / "web" / "src").mkdir(parents=True)
        (repo / "AGENTS.md").write_text(
            "# Conventions\nUse Conventional Commits.\n",
            encoding="utf-8",
        )
        (repo / "package.json").write_text(
            json.dumps(
                {
                    "packageManager": "pnpm@9.0.0",
                    "engines": {"node": ">=20"},
                    "scripts": {"test": "root-only"},
                    "devDependencies": {"jest": "^30"},
                }
            ),
            encoding="utf-8",
        )
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
        (repo / ".python-version").write_text("3.12\n", encoding="utf-8")
        api = repo / "packages" / "api"
        (api / "AGENTS.md").write_text("# API\nUse package-local commands.\n", encoding="utf-8")
        (api / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"test:api": "vitest run", "lint": "eslint ."},
                    "devDependencies": {"vitest": "^3", "eslint": "^9"},
                }
            ),
            encoding="utf-8",
        )
        web = repo / "packages" / "web"
        (web / "AGENTS.md").write_text("# Web\nUse web commands.\n", encoding="utf-8")
        (web / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"test:web": "jest"},
                    "devDependencies": {"jest": "^30"},
                }
            ),
            encoding="utf-8",
        )
        return repo

    def test_target_generation_uses_effective_scope_local_facts_and_safe_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_scoped_repo(td)
            target = "packages/api/src/future.py"

            root_tasks = eval_run.generate_tasks(repo)
            scoped_tasks = eval_run.generate_tasks(repo, target=target)
            by_id = {task["id"]: task for task in scoped_tasks}

            # Legacy root task IDs and facts stay unchanged.
            self.assertIn("test", {task["id"] for task in root_tasks})
            self.assertIn("test-framework", {task["id"] for task in root_tasks})
            self.assertTrue(eval_run.regex_passes(
                next(task for task in root_tasks if task["id"] == "test-framework")["check"]["value"],
                "jest",
            ))

            prefix = "scope:packages%2Fapi:"
            for suffix in (
                "package-manager",
                "install",
                "test:api",
                "lint",
                "test-framework",
                "formatter",
                "node-version",
                "python-version",
                "commit-convention",
            ):
                self.assertIn(prefix + suffix, by_id)
            self.assertNotIn(prefix + "test", by_id)
            self.assertTrue(
                eval_run.regex_passes(by_id[prefix + "test:api"]["check"]["value"], "pnpm test:api")
            )
            self.assertTrue(
                eval_run.regex_passes(by_id[prefix + "test-framework"]["check"]["value"], "vitest")
            )
            self.assertFalse(
                eval_run.regex_passes(by_id[prefix + "test-framework"]["check"]["value"], "jest")
            )
            for task in scoped_tasks:
                self.assertEqual(task["scope"], "packages/api")
                self.assertEqual(task["target"], target)
                self.assertTrue(all(not Path(path).is_absolute() for path in task["evidence"]))
                self.assertNotIn("packages/web", json.dumps(task))
            self.assertEqual(
                by_id[prefix + "test:api"]["evidence"],
                ["packages/api/package.json"],
            )
            self.assertEqual(
                by_id[prefix + "package-manager"]["evidence"],
                ["package.json", "pnpm-lock.yaml"],
            )
            self.assertEqual(
                by_id[prefix + "commit-convention"]["evidence"],
                ["AGENTS.md", "packages/api/AGENTS.md"],
            )
            self.assertEqual(
                by_id[prefix + "python-version"]["evidence"],
                [".python-version"],
            )

    def test_target_generation_matches_explain_scope_and_keeps_siblings_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_scoped_repo(td)
            api_target = "packages/api/src/future.py"
            web_target = "packages/web/src/future.py"

            api = eval_run.generate_tasks(repo, target=api_target)
            web = eval_run.generate_tasks(repo, target=web_target)
            api_scope = explain.build_explanation(repo, api_target)["effective_scope"]
            web_scope = explain.build_explanation(repo, web_target)["effective_scope"]

            self.assertEqual({task["scope"] for task in api}, {api_scope})
            self.assertEqual({task["scope"] for task in web}, {web_scope})
            self.assertTrue(all(task["id"].startswith("scope:packages%2Fapi:") for task in api))
            self.assertTrue(all(task["id"].startswith("scope:packages%2Fweb:") for task in web))
            self.assertFalse({task["id"] for task in api} & {task["id"] for task in web})

    def test_target_package_manager_prefers_local_lock_then_local_field(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_scoped_repo(td)
            package = repo / "packages" / "api"
            package_json = json.loads((package / "package.json").read_text())
            package_json["packageManager"] = "yarn@4.0.0"
            (package / "package.json").write_text(json.dumps(package_json), encoding="utf-8")
            target = "packages/api/src/future.py"

            local = {
                task["id"]: task
                for task in eval_run.generate_tasks(repo, target=target)
            }
            prefix = "scope:packages%2Fapi:"
            self.assertTrue(
                eval_run.regex_passes(
                    local[prefix + "package-manager"]["check"]["value"],
                    "yarn",
                )
            )
            self.assertEqual(
                local[prefix + "package-manager"]["evidence"],
                ["packages/api/package.json"],
            )

            (package / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            locked = {
                task["id"]: task
                for task in eval_run.generate_tasks(repo, target=target)
            }
            self.assertTrue(
                eval_run.regex_passes(
                    locked[prefix + "package-manager"]["check"]["value"],
                    "pnpm",
                )
            )
            self.assertEqual(
                locked[prefix + "package-manager"]["evidence"],
                ["packages/api/pnpm-lock.yaml"],
            )
            self.assertIn(prefix + "install", locked)
            self.assertIn(prefix + "test:api", locked)

            (package / "package-lock.json").write_text("{}\n", encoding="utf-8")
            ambiguous_ids = {
                task["id"]
                for task in eval_run.generate_tasks(repo, target=target)
            }
            self.assertNotIn(prefix + "package-manager", ambiguous_ids)
            self.assertNotIn(prefix + "install", ambiguous_ids)
            self.assertNotIn(prefix + "test:api", ambiguous_ids)
            self.assertIn(prefix + "test-framework", ambiguous_ids)

    def test_root_effective_target_preserves_legacy_generation_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(td)
            self.assertEqual(
                eval_run.generate_tasks(repo),
                eval_run.generate_tasks(repo, target="src/future.py"),
            )

    def test_scoped_id_percent_encodes_separator_and_punctuation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            scope = repo / "packages" / "api v2"
            scope.mkdir(parents=True)
            (repo / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (scope / "AGENTS.md").write_text("Use local commands.\n", encoding="utf-8")
            (scope / "package.json").write_text(
                json.dumps({"scripts": {"test": "vitest run"}}),
                encoding="utf-8",
            )

            tasks = eval_run.generate_tasks(
                repo,
                target="packages/api v2/src/future.py",
            )

            self.assertTrue(tasks)
            self.assertTrue(
                all(task["id"].startswith("scope:packages%2Fapi%20v2:") for task in tasks)
            )

    def test_target_rejects_escape_external_symlink_and_excluded_subtree(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = self._make_scoped_repo(td)
            outside = base / "outside"
            outside.mkdir()
            try:
                (repo / "escape").symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported")

            for target in ("../outside/x.py", "escape/x.py", "node_modules/pkg/x.js"):
                with self.subTest(target=target):
                    with self.assertRaises(ValueError):
                        eval_run.generate_tasks(repo, target=target)

    def test_target_cli_writes_scoped_tasks_and_target_requires_generate(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_scoped_repo(td)
            out = Path(td) / "tasks.json"
            target = "packages/api/src/future.py"
            generated = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--generate",
                    str(repo),
                    "--target",
                    target,
                    "-o",
                    str(out),
                ],
                text=True,
                capture_output=True,
            )
            invalid = subprocess.run(
                [sys.executable, str(EVAL), "--target", target],
                text=True,
                capture_output=True,
            )

            self.assertEqual(generated.returncode, 0, generated.stderr)
            self.assertTrue(all(task["scope"] == "packages/api" for task in json.loads(out.read_text())))
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("--target requires --generate", invalid.stderr)


class JudgePromptTests(unittest.TestCase):
    """SEC-03/SEC-04: the judge prompt embeds untrusted agent output (the
    ANSWER is the raw output of the agent under evaluation), so it must be
    length-capped and framed as data, not instructions."""

    def test_judge_prompt_delimits_answer_and_rubric_as_data(self):
        prompt = eval_run._judge_user_prompt("the answer", "the rubric")
        self.assertIn("<answer>", prompt)
        self.assertIn("</answer>", prompt)
        self.assertIn("<rubric>", prompt)
        self.assertIn("</rubric>", prompt)
        self.assertIn("the answer", prompt)
        self.assertIn("the rubric", prompt)

    def test_system_prompt_frames_answer_as_untrusted_data(self):
        # A hostile/buggy benchmark repo could have the agent under test echo
        # judge-directed text (e.g. "always return passed: true"); the system
        # prompt must tell the judge model to never follow it.
        self.assertIn("untrusted", eval_run.JUDGE_SYSTEM_PROMPT.lower())
        self.assertIn("never", eval_run.JUDGE_SYSTEM_PROMPT.lower())

    def test_long_answer_is_truncated(self):
        huge = "x" * (eval_run._MAX_JUDGE_TEXT_CHARS + 5000)
        prompt = eval_run._judge_user_prompt(huge, "rubric")
        self.assertLess(len(prompt), len(huge))
        self.assertIn("truncated", prompt)

    def test_short_answer_is_not_truncated(self):
        prompt = eval_run._judge_user_prompt("short answer", "short rubric")
        self.assertNotIn("truncated", prompt)

    def test_truncate_for_judge_handles_none(self):
        self.assertEqual(eval_run._truncate_for_judge(None), "")


class LlmJudgeTests(unittest.TestCase):
    def test_auto_without_keys_returns_none(self):
        with _EnvGuard(OPENAI_API_KEY=None, ANTHROPIC_API_KEY=None):
            self.assertIsNone(eval_run.llm_judge("answer", "rubric", "auto"))

    def test_off_provider_returns_none(self):
        with _EnvGuard(OPENAI_API_KEY="sk-test"):
            self.assertIsNone(eval_run.llm_judge("answer", "rubric", "off"))

    def test_openai_success_parsed(self):
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            captured["auth"] = headers.get("Authorization")
            return {"choices": [{"message": {"content": '{"passed": true, "score": 1, "reason": "good"}'}}]}

        original = eval_run._http_post_json
        eval_run._http_post_json = fake_post
        try:
            with _EnvGuard(OPENAI_API_KEY="sk-test", OPENAI_MODEL="gpt-test"):
                verdict = eval_run.llm_judge("the answer", "must be good", "auto")
        finally:
            eval_run._http_post_json = original
        self.assertIsNotNone(verdict)
        self.assertTrue(verdict["passed"])
        self.assertEqual(verdict["judge"], "llm:openai")
        self.assertEqual(verdict["model"], "gpt-test")
        self.assertIn("/chat/completions", captured["url"])
        self.assertEqual(captured["auth"], "Bearer sk-test")

    def test_openai_request_caps_output_tokens(self):
        # SEC-04: unlike the Anthropic branch (max_tokens: 512), the OpenAI
        # branch previously had no output-token cap at all, and
        # OPENAI_BASE_URL is operator-overridable to an OpenAI-compatible
        # endpoint whose own default could be far larger.
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": '{"passed": true, "score": 1, "reason": "ok"}'}}]}

        original = eval_run._http_post_json
        eval_run._http_post_json = fake_post
        try:
            with _EnvGuard(OPENAI_API_KEY="sk-test"):
                eval_run.llm_judge("the answer", "the rubric", "auto")
        finally:
            eval_run._http_post_json = original
        self.assertEqual(captured["payload"].get("max_tokens"), 512)

    def test_claude_success_parsed(self):
        def fake_post(url, headers, payload, timeout):
            self.assertIn("/v1/messages", url)
            self.assertEqual(headers.get("x-api-key"), "ak-test")
            return {"content": [{"type": "text", "text": '{"passed": false, "score": 0, "reason": "no"}'}]}

        original = eval_run._http_post_json
        eval_run._http_post_json = fake_post
        try:
            with _EnvGuard(OPENAI_API_KEY=None, ANTHROPIC_API_KEY="ak-test"):
                verdict = eval_run.llm_judge("x", "y", "claude")
        finally:
            eval_run._http_post_json = original
        self.assertIsNotNone(verdict)
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["judge"], "llm:claude")

    def test_network_error_falls_back_to_none(self):
        def boom(url, headers, payload, timeout):
            raise RuntimeError("network down")

        original = eval_run._http_post_json
        eval_run._http_post_json = boom
        try:
            with _EnvGuard(OPENAI_API_KEY="sk-test"):
                self.assertIsNone(eval_run.llm_judge("x", "y", "openai"))
        finally:
            eval_run._http_post_json = original

    def test_grade_answer_prefers_llm_then_falls_back(self):
        task = {"id": "j", "check": {"type": "judge", "expect": ["ok"]}, "timeout_s": 5}
        # LLM available -> its verdict wins over the keyword judge.
        original = eval_run.llm_judge
        eval_run.llm_judge = lambda *a, **k: {"passed": True, "score": 1.0, "reason": "llm", "judge": "llm:openai"}
        try:
            passed, info = eval_run.grade_answer(task, "no keyword here", ".", None, judge_llm="auto")
        finally:
            eval_run.llm_judge = original
        self.assertTrue(passed)
        self.assertEqual(info["judge"], "llm:openai")
        # LLM unavailable (returns None) -> keyword judge fallback.
        eval_run.llm_judge = lambda *a, **k: None
        try:
            passed, info = eval_run.grade_answer(task, "ok answer", ".", None, judge_llm="auto")
        finally:
            eval_run.llm_judge = original
        self.assertTrue(passed)
        self.assertEqual(info["judge"], "builtin")


class ProcessHygieneTests(unittest.TestCase):
    """CORR-07: a timeout must kill the WHOLE process group, not just the top
    shell, so no grandchild survives as an orphan."""

    def test_run_subprocess_kills_grandchildren_on_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            pidfile = Path(td) / "child.pid"
            # sh (the child) backgrounds a `sleep` (a grandchild) and records its
            # pid, then waits. With plain subprocess.run+timeout only sh would be
            # killed and the sleep would leak; run_subprocess must killpg the
            # whole session so the sleep dies too.
            cmd = f"sleep 30 & echo $! > {shlex_quote(str(pidfile))}; wait"
            with self.assertRaises(subprocess.TimeoutExpired):
                eval_run.run_subprocess(cmd, shell=True, timeout=1)
            # Let the OS deliver the signals and reap.
            deadline = time.time() + 5
            child_pid = int(pidfile.read_text().strip())
            alive = True
            while time.time() < deadline:
                try:
                    os.kill(child_pid, 0)
                except (ProcessLookupError, OSError):
                    alive = False
                    break
                time.sleep(0.1)
            self.assertFalse(alive, "grandchild process leaked past the timeout")

    def test_run_subprocess_returns_completed_process_normally(self):
        proc = eval_run.run_subprocess("echo hi", shell=True, timeout=10)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "hi")


class DeterministicGradingDefaultTests(unittest.TestCase):
    """CORR-08: the default grader is the deterministic built-in judge. An
    ambient API key must NOT silently reroute grading to a real LLM."""

    def test_grade_answer_off_ignores_present_api_key(self):
        task = {"id": "j", "check": {"type": "judge", "expect": ["ok"]}, "timeout_s": 5}
        called = {"llm": False}

        def _boom(*a, **k):
            called["llm"] = True
            return {"passed": True, "score": 1.0, "reason": "llm", "judge": "llm:openai"}

        original = eval_run.llm_judge
        eval_run.llm_judge = _boom
        old_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-fake-should-be-ignored"
        try:
            passed, info = eval_run.grade_answer(task, "ok answer", ".", None, judge_llm="off")
        finally:
            eval_run.llm_judge = original
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key
        self.assertFalse(called["llm"], "judge_llm='off' must never call the LLM judge")
        self.assertTrue(passed)
        self.assertEqual(info["judge"], "builtin")

    def test_cli_default_does_not_route_to_llm_even_with_api_key(self):
        # End-to-end: no --judge-llm flag + a present API key must still grade
        # deterministically (default is 'off'), never invoking the LLM judge.
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("# overview\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [{"id": "j", "prompt": "p", "check": {"type": "judge", "expect": ["ok"]}, "timeout_s": 10}]
                ),
                encoding="utf-8",
            )
            out = Path(td) / "res.json"
            runner = f"{sys.executable} -c \"print('ok answer')\""

            called = {"llm": False}

            def _boom(*a, **k):
                called["llm"] = True
                return {"passed": True, "score": 1.0, "reason": "llm", "judge": "llm:openai"}

            original = eval_run.llm_judge
            eval_run.llm_judge = _boom
            old_key = os.environ.get("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = "sk-fake-should-be-ignored"
            try:
                rc = eval_run.main(
                    [
                        "--tasks",
                        str(tasks),
                        "--workdir",
                        str(workdir),
                        "--label",
                        "x",
                        "--runner",
                        runner,
                        "-o",
                        str(out),
                    ]
                )
            finally:
                eval_run.llm_judge = original
                if old_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = old_key
            self.assertEqual(rc, 0)
            self.assertFalse(called["llm"], "default --judge-llm must not call a real LLM")
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["tasks"][0]["judge"]["judge"], "builtin")


class BaselineTests(unittest.TestCase):
    def test_detect_regression_unit(self):
        store = [{"label": "a", "score": 90}, {"label": "b", "score": 88}]
        reg = eval_run.detect_regression(store, 80, 5)
        self.assertTrue(reg["regressed"])
        self.assertEqual(reg["prev_score"], 88)
        self.assertEqual(reg["delta"], -8)
        # Within threshold -> not a regression.
        self.assertFalse(eval_run.detect_regression(store, 85, 5)["regressed"])
        # No prior score -> None.
        self.assertIsNone(eval_run.detect_regression([], 80, 5))

    def test_save_baseline_appends_and_trend_renders(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("# overview\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(
                json.dumps(
                    [
                        {"id": "r", "prompt": "hi", "check": {"type": "regex", "value": "ok hi"}, "timeout_s": 10},
                    ]
                ),
                encoding="utf-8",
            )
            runner = f"{sys.executable} -c \"print('ok hi')\""
            store = Path(td) / "baseline.json"
            base = [
                sys.executable,
                str(EVAL),
                "--tasks",
                str(tasks),
                "--label",
                "run1",
                "--workdir",
                str(workdir),
                "--runner",
                runner,
                "-o",
                str(Path(td) / "r1.json"),
                "--baseline",
                str(store),
                "--save-baseline",
            ]
            self.assertEqual(subprocess.run(base, text=True, capture_output=True).returncode, 0)
            self.assertEqual(len(json.loads(store.read_text(encoding="utf-8"))), 1)
            # Second run appends a new snapshot.
            base2 = list(base)
            base2[base2.index("run1")] = "run2"
            base2[base2.index(str(Path(td) / "r1.json"))] = str(Path(td) / "r2.json")
            self.assertEqual(subprocess.run(base2, text=True, capture_output=True).returncode, 0)
            data = json.loads(store.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["score"], 100)
            # Trend report renders the history.
            trend = subprocess.run([sys.executable, str(EVAL), "--trend", str(store)], text=True, capture_output=True)
            self.assertEqual(trend.returncode, 0, trend.stderr)
            self.assertIn("Eval baseline trend", trend.stdout)

    def test_check_regression_gate_exits_6(self):
        with tempfile.TemporaryDirectory() as td:
            # Prior baseline recorded a high score.
            store = Path(td) / "baseline.json"
            store.write_text(json.dumps([{"label": "good", "score": 100, "grade": "A"}]), encoding="utf-8")
            # A results file that scores 0 (nothing passed).
            results = Path(td) / "results.json"
            results.write_text(
                json.dumps(
                    {
                        "label": "bad",
                        "tasks": [{"id": "x", "passed": False, "timed_out": False}],
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    str(EVAL),
                    "--score",
                    str(results),
                    "--baseline",
                    str(store),
                    "--check-regression",
                    "--regression-threshold",
                    "5",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 6, proc.stdout + proc.stderr)
            self.assertIn("REGRESSION", proc.stdout)


if __name__ == "__main__":
    unittest.main()
