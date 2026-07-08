#!/usr/bin/env python3
"""Small pluggable eval harness for before/after AI harness validation."""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def runner_binary(template):
    parts = shlex.split(template)
    return parts[0] if parts else ""


def manual_protocol(binary, tasks_path):
    return f"""Runner binary `{binary}` was not found.

Manual protocol:
1. Open the target repo in your agent tool.
2. For each task in `{tasks_path}`, run the prompt exactly once.
3. Record JSON with shape:
   {{"label":"manual","tasks":[{{"id":"task-id","passed":true,"duration_s":0.0,"exit_code":0,"stdout":"...","answer":"..."}}]}}
4. Compare two result files with: python3 scripts/eval_run.py --compare before.json after.json -o report.md
"""


def maybe_usage(stdout):
    try:
        data = json.loads(stdout)
    except Exception:
        return {}
    usage = {}
    for key in ["usage", "cost", "total_cost_usd", "tokens", "input_tokens", "output_tokens"]:
        if key in data:
            usage[key] = data[key]
    return usage


def timeout_output(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def extract_answer(stdout):
    """Return the normalized text used for grading.

    Claude CLI `--output-format json` emits a JSON envelope whose `result` field is
    the agent answer. Older/manual results may be raw text, so fall back to stdout.
    """
    raw = timeout_output(stdout)
    answer = raw
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    if isinstance(data, dict) and isinstance(data.get("result"), str):
        answer = data["result"]
    return answer.strip().strip("`").strip()


def regex_passes(pattern, answer):
    return re.search(pattern or "", answer or "") is not None


def parse_judge_output(stdout):
    """Parse an LLM-as-judge verdict.

    The judge command MUST print a single JSON object with shape
    ``{"passed": bool, "score": number, "reason": "..."}``. If ``passed`` is
    omitted but a numeric ``score`` is present, a score >= 0.5 counts as a pass.
    A best-effort attempt is made to locate a JSON object embedded in noisier
    output so simple echo-based judges keep working.
    """
    raw = timeout_output(stdout).strip()
    data = None
    try:
        data = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return {"passed": False, "score": None, "reason": "judge output was not valid JSON", "raw": raw}
    passed = data.get("passed")
    score = data.get("score")
    if passed is None and isinstance(score, (int, float)) and not isinstance(score, bool):
        passed = score >= 0.5
    return {"passed": bool(passed), "score": score, "reason": data.get("reason", ""), "raw": raw}


def run_judge(judge_cmd, answer, rubric, workdir, timeout):
    """Invoke a configurable judge command and return its parsed verdict.

    Contract (documented in SKILL.md): the judge command is run through the
    shell with the following inputs available so authors can pick whatever fits:
      - env ``JUDGE_ANSWER``: the produced answer text
      - env ``JUDGE_RUBRIC``: the rubric / criteria string (may be empty)
      - env ``JUDGE_INPUT``: path to a temp JSON file ``{"answer":..., "rubric":...}``
      - template placeholders ``{answer}`` / ``{rubric}`` / ``{input}`` (shell-quoted)
    The command MUST print ``{"passed": bool, "score": number, "reason": "..."}``.
    Raises ``subprocess.TimeoutExpired`` if the judge exceeds ``timeout`` seconds.
    """
    answer = answer or ""
    rubric = rubric or ""
    env = dict(os.environ)
    env["JUDGE_ANSWER"] = answer
    env["JUDGE_RUBRIC"] = rubric
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    try:
        handle.write(json.dumps({"answer": answer, "rubric": rubric}, ensure_ascii=False))
        handle.close()
        env["JUDGE_INPUT"] = handle.name
        command = (
            judge_cmd
            .replace("{answer}", shlex.quote(answer))
            .replace("{rubric}", shlex.quote(rubric))
            .replace("{input}", shlex.quote(handle.name))
        )
        proc = subprocess.run(
            command, cwd=str(workdir) if workdir else None, text=True,
            capture_output=True, shell=True, env=env, timeout=timeout,
        )
        verdict = parse_judge_output(proc.stdout)
        verdict["exit_code"] = proc.returncode
        return verdict
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def grade_answer(task, answer, workdir, judge_cmd=None):
    """Grade an answer for a task, returning ``(passed, judge_info)``.

    Supports ``regex``, ``command`` and ``judge`` check types. ``judge_info`` is
    ``None`` for non-judge checks. Timeouts count as a failure (no exception is
    propagated) so a matrix run keeps going.
    """
    check = task.get("check", {})
    ctype = check.get("type")
    timeout = task.get("timeout_s", 60)
    if ctype == "regex":
        return regex_passes(check.get("value", ""), answer), None
    if ctype == "command":
        try:
            cproc = subprocess.run(check.get("value", ""), cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=timeout)
            return cproc.returncode == 0, None
        except subprocess.TimeoutExpired:
            return False, None
    if ctype == "judge":
        if not judge_cmd:
            return False, {"passed": False, "score": None, "reason": "no --judge-cmd provided"}
        rubric = check.get("rubric") or check.get("criteria") or ""
        try:
            verdict = run_judge(judge_cmd, answer, rubric, workdir, timeout)
        except subprocess.TimeoutExpired:
            return False, {"passed": False, "score": None, "reason": "judge timed out"}
        return verdict["passed"], verdict
    return False, None


def check_task(task, stdout, workdir=None):
    check = task.get("check", {})
    answer = extract_answer(stdout)
    passed = False
    regraded = True
    if check.get("type") == "regex":
        passed = regex_passes(check.get("value", ""), answer)
    elif check.get("type") == "command":
        regraded = False
        if workdir is not None:
            cproc = subprocess.run(check.get("value", ""), cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60))
            passed = cproc.returncode == 0
            regraded = True
    return answer, passed, regraded


def run_tasks(args):
    tasks_path = Path(args.tasks)
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    binary = runner_binary(args.runner)
    if binary and shutil.which(binary) is None:
        print(manual_protocol(binary, args.tasks), file=sys.stderr)
        return 127
    workdir = Path(args.workdir).resolve()
    results = {"label": args.label, "workdir": str(workdir), "tasks": []}
    for task in tasks:
        prompt = task["prompt"]
        command = args.runner.replace("{prompt}", shlex.quote(prompt))
        start = time.time()
        try:
            proc = subprocess.run(command, cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60))
        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start, 3)
            stdout = timeout_output(exc.stdout)
            results["tasks"].append({
                "id": task["id"], "passed": False, "timed_out": True, "duration_s": duration,
                "exit_code": None, "stdout": stdout, "answer": extract_answer(stdout), "stderr": timeout_output(exc.stderr),
                "usage": {},
            })
            continue
        duration = round(time.time() - start, 3)
        check = task.get("check", {})
        passed = False
        judge_info = None
        answer = extract_answer(proc.stdout)
        if check.get("type") == "regex":
            passed = regex_passes(check.get("value", ""), answer)
        elif check.get("type") == "command":
            try:
                cproc = subprocess.run(check.get("value", ""), cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60))
            except subprocess.TimeoutExpired as exc:
                duration = round(time.time() - start, 3)
                results["tasks"].append({
                    "id": task["id"], "passed": False, "timed_out": True, "duration_s": duration,
                    "exit_code": None, "stdout": proc.stdout, "answer": answer, "stderr": timeout_output(exc.stderr),
                    "usage": maybe_usage(proc.stdout),
                })
                continue
            passed = cproc.returncode == 0
        elif check.get("type") == "judge":
            passed, judge_info = grade_answer(task, answer, workdir, args.judge_cmd)
        record = {
            "id": task["id"], "passed": passed, "timed_out": False, "duration_s": duration,
            "exit_code": proc.returncode, "stdout": proc.stdout, "answer": answer, "stderr": proc.stderr,
            "usage": maybe_usage(proc.stdout),
        }
        if judge_info is not None:
            record["judge"] = judge_info
        results["tasks"].append(record)
    output = Path(args.output) if args.output else Path(f"results-{args.label}.json")
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0


def regrade(args):
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    task_map = {task["id"]: task for task in tasks}
    results = json.loads(Path(args.regrade).read_text(encoding="utf-8"))
    for record in results.get("tasks", []):
        task = task_map.get(record.get("id"))
        answer = extract_answer(record.get("stdout", ""))
        record["answer"] = answer
        if not task:
            record["regraded"] = False
            continue
        check = task.get("check", {})
        if check.get("type") == "regex":
            record["passed"] = regex_passes(check.get("value", ""), answer)
            record["regraded"] = True
        elif check.get("type") == "command":
            record["regraded"] = False
        else:
            record["regraded"] = False
    output = Path(args.output) if args.output else Path(args.regrade)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    return 0


def compare(args):
    before = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
    after = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
    bmap = {t["id"]: t for t in before.get("tasks", [])}
    amap = {t["id"]: t for t in after.get("tasks", [])}
    ids = sorted(set(bmap) | set(amap))
    lines = ["# Phase 3 — Efficacy Comparison Report", "", f"Before label: `{before.get('label')}`", f"After label: `{after.get('label')}`", "", "| Task | Before | After | Duration Δ(s) | Usage |", "|---|---:|---:|---:|---|"]
    before_pass = after_pass = 0
    for tid in ids:
        b, a = bmap.get(tid, {}), amap.get(tid, {})
        before_pass += 1 if b.get("passed") else 0
        after_pass += 1 if a.get("passed") else 0
        delta = round((a.get("duration_s") or 0) - (b.get("duration_s") or 0), 3)
        usage = json.dumps(a.get("usage") or b.get("usage") or {}, ensure_ascii=False)
        lines.append(f"| `{tid}` | {b.get('passed')} | {a.get('passed')} | {delta} | `{usage}` |")
    lines.extend(["", f"Summary: pass rate {before_pass}/{len(ids)} → {after_pass}/{len(ids)}; delta {after_pass - before_pass} tasks."])
    content = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")
    return 0


def parse_named_runners(pairs):
    """Parse repeatable ``NAME=CMD`` runner specs into an ordered dict."""
    runners = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--runner-cmd must be NAME=CMD, got: {pair}")
        name, cmd = pair.split("=", 1)
        name = name.strip()
        if not name or not cmd.strip():
            raise SystemExit(f"--runner-cmd must be NAME=CMD, got: {pair}")
        runners[name] = cmd
    return runners


def load_matrix(args):
    """Build an ordered {agent_name: runner_template} mapping from --matrix + --runner-cmd."""
    runners = {}
    if args.matrix:
        data = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("agents"), dict):
            data = data["agents"]
        if not isinstance(data, dict):
            raise SystemExit("--matrix file must map agent name -> runner command template")
        for name, cmd in data.items():
            runners[str(name)] = cmd
    runners.update(parse_named_runners(args.runner_cmd))
    return runners


def run_task_with_runner(runner, task, workdir, judge_cmd):
    """Run a single task under a single runner and return a graded record."""
    prompt = task["prompt"]
    command = runner.replace("{prompt}", shlex.quote(prompt))
    start = time.time()
    try:
        proc = subprocess.run(command, cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60))
    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - start, 3)
        stdout = timeout_output(exc.stdout)
        return {
            "id": task["id"], "passed": False, "timed_out": True, "duration_s": duration,
            "exit_code": None, "answer": extract_answer(stdout), "usage": {},
        }
    duration = round(time.time() - start, 3)
    answer = extract_answer(proc.stdout)
    passed, judge_info = grade_answer(task, answer, workdir, judge_cmd)
    record = {
        "id": task["id"], "passed": passed, "timed_out": False, "duration_s": duration,
        "exit_code": proc.returncode, "answer": answer, "usage": maybe_usage(proc.stdout),
    }
    if judge_info is not None:
        record["judge"] = judge_info
    return record


def render_matrix(tasks, agent_records, runners):
    """Render a markdown matrix report: rows=tasks, cols=agents, plus pass-rate summary."""
    names = list(agent_records.keys())
    header = "| Task | " + " | ".join(names) + " |"
    divider = "|---|" + "".join(["---|" for _ in names])
    lines = ["# Eval Matrix Report", "", header, divider]
    maps = {name: {r["id"]: r for r in recs} for name, recs in agent_records.items()}
    for task in tasks:
        tid = task["id"]
        cells = []
        for name in names:
            record = maps[name].get(tid, {})
            if record.get("timed_out"):
                mark = "⏱ timeout"
            elif record.get("passed"):
                mark = "✅ pass"
            else:
                mark = "❌ fail"
            cells.append(f"{mark} ({record.get('duration_s', 0)}s)")
        lines.append(f"| `{tid}` | " + " | ".join(cells) + " |")
    lines.extend(["", "## Per-agent pass rate", "", "| Agent | Runner | Pass | Total | Pass rate |", "|---|---|---:|---:|---:|"])
    for name in names:
        recs = agent_records[name]
        total = len(recs)
        passed = sum(1 for r in recs if r.get("passed"))
        rate = round(100.0 * passed / total, 1) if total else 0.0
        runner = runners.get(name, "")
        lines.append(f"| `{name}` | `{runner}` | {passed} | {total} | {rate}% |")
    return "\n".join(lines) + "\n"


def run_matrix(args, runners):
    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    workdir = Path(args.workdir).resolve()
    agent_records = {}
    for name, runner in runners.items():
        binary = runner_binary(runner)
        if binary and shutil.which(binary) is None:
            print(manual_protocol(binary, args.tasks), file=sys.stderr)
            return 127
        agent_records[name] = [run_task_with_runner(runner, task, workdir, args.judge_cmd) for task in tasks]
    summary = {}
    for name, recs in agent_records.items():
        total = len(recs)
        passed = sum(1 for r in recs if r.get("passed"))
        summary[name] = {"passed": passed, "total": total, "pass_rate": round(passed / total, 4) if total else 0.0}
    matrix = {
        "workdir": str(workdir),
        "agents": {name: {"runner": runners[name], "tasks": recs, "summary": summary[name]} for name, recs in agent_records.items()},
        "summary": summary,
    }
    json_out = Path(args.matrix_json) if args.matrix_json else Path("matrix-results.json")
    json_out.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out = Path(args.matrix_report) if args.matrix_report else (Path(args.output) if args.output else Path("matrix-report.md"))
    report_out.write_text(render_matrix(tasks, agent_records, runners), encoding="utf-8")
    print(f"wrote {json_out}")
    print(f"wrote {report_out}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run or compare AI harness eval tasks.")
    parser.add_argument("--tasks")
    parser.add_argument("--label")
    parser.add_argument("--workdir")
    parser.add_argument("--runner", default="claude -p {prompt} --output-format json")
    parser.add_argument("-o", "--output")
    parser.add_argument("--compare", nargs=2)
    parser.add_argument("--regrade")
    parser.add_argument("--judge-cmd", dest="judge_cmd", help="Command template for LLM-as-judge checks (see SKILL.md for the contract).")
    parser.add_argument("--matrix", help="JSON file mapping agent name -> runner command template.")
    parser.add_argument("--runner-cmd", dest="runner_cmd", action="append", default=[], help="Repeatable NAME=CMD runner for the eval matrix.")
    parser.add_argument("--matrix-report", dest="matrix_report", help="Output path for the markdown matrix report.")
    parser.add_argument("--matrix-json", dest="matrix_json", help="Output path for the matrix JSON results.")
    args = parser.parse_args(argv)
    if args.compare:
        return compare(args)
    if args.regrade:
        if not args.tasks:
            parser.error("--tasks is required with --regrade")
        return regrade(args)
    if args.matrix or args.runner_cmd:
        if not (args.tasks and args.workdir):
            parser.error("--tasks and --workdir are required for a matrix run")
        runners = load_matrix(args)
        if not runners:
            parser.error("no runners defined; provide --matrix FILE and/or --runner-cmd NAME=CMD")
        return run_matrix(args, runners)
    required = [args.tasks, args.label, args.workdir]
    if not all(required):
        parser.error("--tasks, --label and --workdir are required unless --compare is used")
    return run_tasks(args)


if __name__ == "__main__":
    sys.exit(main())
