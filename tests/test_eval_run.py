import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "scripts" / "eval_run.py"


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


if __name__ == "__main__":
    unittest.main()
