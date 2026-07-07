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


if __name__ == "__main__":
    unittest.main()
