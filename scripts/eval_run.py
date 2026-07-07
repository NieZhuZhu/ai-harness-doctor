#!/usr/bin/env python3
"""Small pluggable eval harness for before/after AI harness validation."""

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
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
   {{"label":"manual","tasks":[{{"id":"task-id","passed":true,"duration_s":0.0,"exit_code":0,"stdout":"..."}}]}}
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
            results["tasks"].append({
                "id": task["id"], "passed": False, "timed_out": True, "duration_s": duration,
                "exit_code": None, "stdout": timeout_output(exc.stdout), "stderr": timeout_output(exc.stderr),
                "usage": {},
            })
            continue
        duration = round(time.time() - start, 3)
        check = task.get("check", {})
        passed = False
        if check.get("type") == "regex":
            passed = re.search(check.get("value", ""), proc.stdout or "") is not None
        elif check.get("type") == "command":
            try:
                cproc = subprocess.run(check.get("value", ""), cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60))
            except subprocess.TimeoutExpired as exc:
                duration = round(time.time() - start, 3)
                results["tasks"].append({
                    "id": task["id"], "passed": False, "timed_out": True, "duration_s": duration,
                    "exit_code": None, "stdout": timeout_output(exc.stdout), "stderr": timeout_output(exc.stderr),
                    "usage": maybe_usage(proc.stdout),
                })
                continue
            passed = cproc.returncode == 0
        results["tasks"].append({
            "id": task["id"], "passed": passed, "timed_out": False, "duration_s": duration,
            "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
            "usage": maybe_usage(proc.stdout),
        })
    output = Path(args.output) if args.output else Path(f"results-{args.label}.json")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run or compare AI harness eval tasks.")
    parser.add_argument("--tasks")
    parser.add_argument("--label")
    parser.add_argument("--workdir")
    parser.add_argument("--runner", default="claude -p {prompt} --output-format json")
    parser.add_argument("-o", "--output")
    parser.add_argument("--compare", nargs=2)
    args = parser.parse_args(argv)
    if args.compare:
        return compare(args)
    required = [args.tasks, args.label, args.workdir]
    if not all(required):
        parser.error("--tasks, --label and --workdir are required unless --compare is used")
    return run_tasks(args)


if __name__ == "__main__":
    sys.exit(main())
