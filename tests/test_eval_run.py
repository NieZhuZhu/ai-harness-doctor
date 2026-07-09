import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from shlex import quote as shlex_quote

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "scripts" / "eval_run.py"

sys.path.insert(0, str(ROOT / "scripts"))
import eval_run  # noqa: E402


class EvalRunTests(unittest.TestCase):
    def test_run_tasks_and_compare(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            (workdir / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            tasks = Path(td) / "tasks.json"
            tasks.write_text(json.dumps([
                {"id": "regex", "prompt": "hello", "check": {"type": "regex", "value": "ok hello"}, "timeout_s": 10},
                {"id": "command", "prompt": "world", "check": {"type": "command", "value": "test -f AGENTS.md"}, "timeout_s": 10},
            ]), encoding="utf-8")
            before = Path(td) / "before.json"
            after = Path(td) / "after.json"
            runner = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            for label, out in [("before", before), ("after", after)]:
                proc = subprocess.run([sys.executable, str(EVAL), "--tasks", str(tasks), "--label", label, "--workdir", str(workdir), "--runner", runner, "-o", str(out)], text=True, capture_output=True)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                data = json.loads(out.read_text(encoding="utf-8"))
                self.assertTrue(all(t["passed"] for t in data["tasks"]))
                self.assertEqual(data["tasks"][0]["answer"], "ok hello")
            report = Path(td) / "report.md"
            proc = subprocess.run([sys.executable, str(EVAL), "--compare", str(before), str(after), "-o", str(report)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            text = report.read_text(encoding="utf-8")
            self.assertIn("before", text)
            self.assertIn("after", text)

    def test_runner_timeout_records_task_and_continues(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(json.dumps([
                {"id": "hang", "prompt": "sleep", "timeout_s": 1},
            ]), encoding="utf-8")
            output = Path(td) / "results.json"
            runner = "python3 -c \"import time;time.sleep(5)\""
            proc = subprocess.run([sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "timeout", "--workdir", str(workdir), "--runner", runner, "-o", str(output)], text=True, capture_output=True)
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
            tasks.write_text(json.dumps([
                {"id": "dev", "prompt": "dev", "check": {"type": "regex", "value": r"^pnpm\s+(run\s+)?dev\b"}, "timeout_s": 10},
            ]), encoding="utf-8")
            output = Path(td) / "results.json"
            runner = f"{sys.executable} -c \"import json; print(json.dumps({{'type':'result','result':'  '+chr(96)+'pnpm dev'+chr(96)+'  ','usage':{{}}}}))\""

            proc = subprocess.run([sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "envelope", "--workdir", str(workdir), "--runner", runner, "-o", str(output)], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(data["tasks"][0]["passed"])
            self.assertEqual(data["tasks"][0]["answer"], "pnpm dev")

    def test_regrade_flips_stored_false_to_true_after_regex_fix(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td) / "tasks.json"
            tasks.write_text(json.dumps([
                {"id": "format", "prompt": "format", "check": {"type": "regex", "value": r"(?i)prettier"}, "timeout_s": 10},
            ]), encoding="utf-8")
            results = Path(td) / "results.json"
            results.write_text(json.dumps({
                "label": "stored",
                "tasks": [{
                    "id": "format",
                    "passed": False,
                    "duration_s": 1.23,
                    "usage": {"total_cost_usd": 0.01},
                    "stdout": json.dumps({"type": "result", "result": "`Prettier`"}),
                }],
            }), encoding="utf-8")

            proc = subprocess.run([sys.executable, str(EVAL), "--regrade", str(results), "--tasks", str(tasks), "-o", str(results)], text=True, capture_output=True)
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
            tasks.write_text(json.dumps([
                {"id": "regex", "prompt": "hello", "check": {"type": "regex", "value": "ok hello"}, "timeout_s": 10},
                {"id": "command", "prompt": "world", "check": {"type": "command", "value": "test -f AGENTS.md"}, "timeout_s": 10},
            ]), encoding="utf-8")
            report = Path(td) / "matrix.md"
            matrix_json = Path(td) / "matrix.json"
            runner_ok = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            runner_bad = f"{sys.executable} -c \"print('nope')\""
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--workdir", str(workdir),
                "--runner-cmd", f"good={runner_ok}", "--runner-cmd", f"bad={runner_bad}",
                "--matrix-report", str(report), "--matrix-json", str(matrix_json),
            ], text=True, capture_output=True)
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
            tasks.write_text(json.dumps([
                {"id": "regex", "prompt": "hello", "check": {"type": "regex", "value": "ok hello"}, "timeout_s": 10},
            ]), encoding="utf-8")
            matrix_file = Path(td) / "agents.json"
            runner_ok = f"{sys.executable} -c \"import sys; print('ok '+sys.argv[1])\" {{prompt}}"
            matrix_file.write_text(json.dumps({"alpha": runner_ok}), encoding="utf-8")
            report = Path(td) / "matrix.md"
            matrix_json = Path(td) / "matrix.json"
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--workdir", str(workdir),
                "--matrix", str(matrix_file), "--matrix-report", str(report), "--matrix-json", str(matrix_json),
            ], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(matrix_json.read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["alpha"]["passed"], 1)

    def test_judge_check_passes_with_passing_judge_and_fails_with_failing_judge(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(json.dumps([
                {"id": "judged", "prompt": "explain", "check": {"type": "judge", "rubric": "must be correct"}, "timeout_s": 10},
            ]), encoding="utf-8")
            runner = f"{sys.executable} -c \"print('the answer')\""

            pass_judge = "printf '{\"passed\":true,\"score\":1.0,\"reason\":\"ok\"}'"
            out_pass = Path(td) / "pass.json"
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "pass", "--workdir", str(workdir),
                "--runner", runner, "--judge-cmd", pass_judge, "-o", str(out_pass),
            ], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out_pass.read_text(encoding="utf-8"))
            record = data["tasks"][0]
            self.assertTrue(record["passed"])
            self.assertEqual(record["judge"]["score"], 1.0)
            self.assertTrue(record["judge"]["passed"])

            fail_judge = "printf '{\"passed\":false,\"score\":0.0,\"reason\":\"bad\"}'"
            out_fail = Path(td) / "fail.json"
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "fail", "--workdir", str(workdir),
                "--runner", runner, "--judge-cmd", fail_judge, "-o", str(out_fail),
            ], text=True, capture_output=True)
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
            tasks.write_text(json.dumps([
                {"id": "judged", "prompt": "explain", "check": {"type": "judge", "rubric": "mention-foo"}, "timeout_s": 10},
            ]), encoding="utf-8")
            runner = f"{sys.executable} -c \"print('foo answer')\""
            # The judge passes only if the answer contains the rubric-required token.
            judge = (
                f"{sys.executable} -c \"import os,json;"
                "a=os.environ['JUDGE_ANSWER'];r=os.environ['JUDGE_RUBRIC'];"
                "ok='foo' in a and r=='mention-foo';"
                "print(json.dumps({'passed':ok,'score':1.0 if ok else 0.0}))\""
            )
            out = Path(td) / "res.json"
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "envjudge", "--workdir", str(workdir),
                "--runner", runner, "--judge-cmd", judge, "-o", str(out),
            ], text=True, capture_output=True)
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

    def test_run_tasks_command_check_timeout_records_non_crashing_fail(self):
        # End-to-end: a command check that times out is a fail, and run_tasks
        # still emits the full record (does not crash, keeps timed_out field).
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks = Path(td) / "tasks.json"
            tasks.write_text(json.dumps([
                {"id": "slow", "prompt": "x", "check": {"type": "command", "value": "sleep 5"}, "timeout_s": 0.1},
            ]), encoding="utf-8")
            output = Path(td) / "results.json"
            runner = f"{sys.executable} -c \"print('done')\""
            proc = subprocess.run([sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "slow", "--workdir", str(workdir), "--runner", runner, "-o", str(output)], text=True, capture_output=True)
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
        data = {"agents": {"a": {"tasks": [{"passed": True}, {"passed": True}]},
                           "b": {"tasks": [{"passed": False}, {"passed": True}]}}}
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
            tasks.write_text(json.dumps([
                {"id": "j", "prompt": "x", "check": {"type": "judge", "expect": ["never-there"]}, "timeout_s": 10},
            ]), encoding="utf-8")
            output = Path(td) / "results.json"
            runner = f"{sys.executable} -c \"print('unrelated')\""
            base = [sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "h", "--workdir", str(workdir), "--runner", runner, "--judge-llm", "off", "-o", str(output)]
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
            results.write_text(json.dumps({"tasks": [{"passed": True}, {"passed": True}]}), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(EVAL), "--score", str(results), "--json"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["score"], 100)
            gated = subprocess.run([sys.executable, str(EVAL), "--score", str(results), "--fail-under", "100"], text=True, capture_output=True)
            self.assertEqual(gated.returncode, 0)


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
        tasks.write_text(json.dumps([
            {"id": "stable", "prompt": "stable", "check": {"type": "regex", "value": "^ok$"}, "timeout_s": 10},
            {"id": "flaky", "prompt": "flaky", "check": {"type": "regex", "value": "^ok$"}, "timeout_s": 10},
        ]), encoding="utf-8")
        runner = f"{sys.executable} {shlex_quote(str(runner_py))} {{prompt}}"
        return tasks, runner

    def test_rounds_produces_task_stats_and_summary(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "repo"
            workdir.mkdir()
            tasks, runner = self._write_scenario(td)
            output = Path(td) / "results.json"
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "multi",
                "--workdir", str(workdir), "--runner", runner, "--rounds", "2", "-o", str(output),
            ], text=True, capture_output=True)
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
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "single",
                "--workdir", str(workdir), "--runner", runner, "-o", str(output),
            ], text=True, capture_output=True)
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
            proc = subprocess.run([
                sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "one",
                "--workdir", str(workdir), "--runner", runner, "--rounds", "1", "-o", str(output),
            ], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("round_results", data)
            self.assertIn("tasks", data)

    def test_stats_subcommand_reads_existing_multi_round_file(self):
        with tempfile.TemporaryDirectory() as td:
            multi = Path(td) / "multi.json"
            multi.write_text(json.dumps({
                "round_results": [
                    {"round": 1, "tasks": [{"id": "a", "passed": True}, {"id": "b", "passed": True}]},
                    {"round": 2, "tasks": [{"id": "a", "passed": True}, {"id": "b", "passed": False}]},
                ]
            }), encoding="utf-8")
            proc = subprocess.run([sys.executable, str(EVAL), "--stats", str(multi), "--json"], text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["stats"]["flaky_tasks"], ["b"])
            self.assertEqual(out["stats"]["health_scores"], [100, 50])
            self.assertEqual(out["health"]["score"], 75)

    def test_stats_fail_under_gate(self):
        with tempfile.TemporaryDirectory() as td:
            multi = Path(td) / "multi.json"
            multi.write_text(json.dumps({
                "round_results": [
                    {"round": 1, "tasks": [{"id": "a", "passed": False}]},
                ]
            }), encoding="utf-8")
            gated = subprocess.run([sys.executable, str(EVAL), "--stats", str(multi), "--fail-under", "50"], text=True, capture_output=True)
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
        (repo / "package.json").write_text(json.dumps({
            "packageManager": "pnpm@9.0.0",
            "engines": {"node": ">=20"},
            "scripts": {"test": "vitest run", "lint": "eslint .", "build": "tsc", "dev": "vite"},
            "devDependencies": {"vitest": "^1", "prettier": "^3"},
        }), encoding="utf-8")
        (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
        (repo / "AGENTS.md").write_text("# Overview\nUse Conventional Commits.\n", encoding="utf-8")
        (repo / "go.mod").write_text("module github.com/acme/widget\n\ngo 1.22\n", encoding="utf-8")
        return repo

    def test_generate_tasks_from_repo_facts(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self._make_repo(td)
            tasks = eval_run.generate_tasks(repo)
            by_id = {t["id"]: t for t in tasks}
            # Ground-truth facts become tasks.
            for tid in ["package-manager", "install", "test", "lint", "build", "dev",
                        "test-framework", "formatter", "node-version", "go-version",
                        "go-module", "commit-convention", "components-dir"]:
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
                [sys.executable, str(EVAL), "--generate", str(repo), "-o", str(out)],
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data), 10)
            self.assertTrue(all("prompt" in t and "check" in t for t in data))

    def test_detect_package_manager(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "yarn.lock").write_text("", encoding="utf-8")
            self.assertEqual(eval_run.detect_package_manager(repo), "yarn")

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
            tasks.write_text(json.dumps([
                {"id": "r", "prompt": "hi", "check": {"type": "regex", "value": "ok hi"}, "timeout_s": 10},
            ]), encoding="utf-8")
            runner = f"{sys.executable} -c \"print('ok hi')\""
            store = Path(td) / "baseline.json"
            base = [sys.executable, str(EVAL), "--tasks", str(tasks), "--label", "run1",
                    "--workdir", str(workdir), "--runner", runner, "-o", str(Path(td) / "r1.json"),
                    "--baseline", str(store), "--save-baseline"]
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
            trend = subprocess.run([sys.executable, str(EVAL), "--trend", str(store)],
                                   text=True, capture_output=True)
            self.assertEqual(trend.returncode, 0, trend.stderr)
            self.assertIn("Eval baseline trend", trend.stdout)

    def test_check_regression_gate_exits_6(self):
        with tempfile.TemporaryDirectory() as td:
            # Prior baseline recorded a high score.
            store = Path(td) / "baseline.json"
            store.write_text(json.dumps([{"label": "good", "score": 100, "grade": "A"}]), encoding="utf-8")
            # A results file that scores 0 (nothing passed).
            results = Path(td) / "results.json"
            results.write_text(json.dumps({
                "label": "bad",
                "tasks": [{"id": "x", "passed": False, "timed_out": False}],
            }), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(EVAL), "--score", str(results),
                 "--baseline", str(store), "--check-regression", "--regression-threshold", "5"],
                text=True, capture_output=True)
            self.assertEqual(proc.returncode, 6, proc.stdout + proc.stderr)
            self.assertIn("REGRESSION", proc.stdout)


if __name__ == "__main__":
    unittest.main()
