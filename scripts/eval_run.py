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

# semantic.py lives in the same scripts/ dir; reuse its canonical ground-truth
# extraction so eval task generation and the scan/drift fact engine agree on the
# same sources (single source of truth) instead of maintaining a divergent copy.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import semantic  # noqa: E402


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
    # A runner may legitimately print a bare JSON scalar/array (e.g. `42`,
    # `"done"`, `[...]`) instead of an object. `key in data` would then raise
    # TypeError (scalars) or silently mis-behave (substring/element checks),
    # aborting the whole eval batch. Only object payloads carry usage fields.
    if not isinstance(data, dict):
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


def _as_pattern_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "must",
    "should",
    "will",
    "have",
    "from",
    "into",
    "your",
    "when",
    "then",
    "than",
    "each",
    "also",
    "such",
    "which",
    "list",
    "explain",
    "describe",
    "mention",
    "answer",
    "correct",
    "correctly",
    "include",
    "including",
    "provide",
    "using",
    "used",
    "note",
    "about",
    "these",
    "there",
    "their",
    "does",
    "what",
    "where",
    "some",
    "only",
    "make",
    "sure",
}


def rubric_keywords(rubric):
    """Extract salient terms an answer should contain from a free-text rubric.

    Prefers explicit signals — backtick-quoted `code`, "double" / 'single' quoted
    phrases — and otherwise falls back to distinctive words (>= 4 chars, minus a
    small stopword list). Deterministic: no LLM required.
    """
    rubric = rubric or ""
    keywords = []
    seen = set()

    def _add(term):
        term = term.strip().lower()
        if term and term not in seen and term not in _STOPWORDS:
            seen.add(term)
            keywords.append(term)

    for m in re.findall(r"`([^`]+)`", rubric):
        _add(m)
    for m in re.findall(r"\"([^\"]+)\"|'([^']+)'", rubric):
        _add(m[0] or m[1])
    if not keywords:
        for word in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_.-]{3,}", rubric):
            _add(word)
    return keywords


# ---------------------------------------------------------------------------
# Task generation from repository facts. Instead of hand-writing tasks.json,
# derive eval tasks from what the repo *actually* declares (package.json
# scripts, lockfiles, .nvmrc, go.mod, pyproject.toml) plus AGENTS.md, so the
# efficacy loop works out of the box on any real repository. Deterministic and
# dependency-free: every generated check is a regex over the ground-truth fact.
# ---------------------------------------------------------------------------

# Lockfiles that unambiguously reveal the package manager (checked in order).
PKG_MANAGER_LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("pnpm-lock.yml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
]

# package.json script name -> human phrasing used in the generated prompt.
SCRIPT_PROMPTS = [
    ("test", "run the test suite"),
    ("lint", "lint the code"),
    ("build", "build the project"),
    ("dev", "start the dev server"),
    ("start", "start the app"),
    ("typecheck", "type-check the project"),
    ("coverage", "run test coverage"),
    ("format", "format the code"),
]

# dependency (package.json) -> canonical label the agent should answer with.
TEST_FRAMEWORK_DEPS = [
    ("vitest", "vitest"),
    ("jest", "jest"),
    ("mocha", "mocha"),
    ("jasmine", "jasmine"),
    ("ava", "ava"),
    ("@playwright/test", "playwright"),
    ("cypress", "cypress"),
]
FORMATTER_DEPS = [
    ("prettier", "prettier"),
    ("@biomejs/biome", "biome"),
    ("eslint", "eslint"),
]

_PROMPT_SUFFIX = " Answer with ONLY the exact command/value, no explanation."


def _load_json_file(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None


def detect_package_manager(root):
    """Best-effort package-manager detection from lockfiles / packageManager."""
    for fname, pm in PKG_MANAGER_LOCKFILES:
        if (root / fname).is_file():
            return pm
    pkg = _load_json_file(root / "package.json")
    if isinstance(pkg, dict):
        field = pkg.get("packageManager")
        if isinstance(field, str):
            m = re.match(r"([A-Za-z]+)@", field)
            if m:
                return m.group(1).lower()
    return None


def generate_tasks(repo_root):
    """Derive a deterministic list of eval tasks from repository facts.

    Returns a list of task dicts in the same shape ``run_tasks`` consumes:
    ``{"id", "prompt", "timeout_s", "check": {"type": "regex", "value": ...}}``.
    Only facts that can be established from files are emitted, so the ground
    truth for every generated check is verifiable without an LLM.
    """
    root = Path(repo_root).resolve()
    tasks = []
    seen = set()

    def add(tid, prompt, pattern, timeout_s=120):
        if tid in seen:
            return
        seen.add(tid)
        tasks.append(
            {
                "id": tid,
                "prompt": prompt + _PROMPT_SUFFIX,
                "timeout_s": timeout_s,
                "check": {"type": "regex", "value": pattern},
            }
        )

    pkg = _load_json_file(root / "package.json")
    pm = detect_package_manager(root)

    if pm:
        add("package-manager", "Which package manager does this repository use?", r"(?i)\b" + re.escape(pm) + r"\b")
        if pm in ("pnpm", "npm", "yarn", "bun"):
            add(
                "install",
                "What is the exact command to install dependencies in this repo?",
                r"(?i)\b" + re.escape(pm) + r"\s+(install|i|add)\b",
            )

    if isinstance(pkg, dict) and isinstance(pkg.get("scripts"), dict):
        scripts = pkg["scripts"]
        runner = pm or "npm"
        for name, phrase in SCRIPT_PROMPTS:
            if name in scripts:
                pattern = r"(?i)\b" + re.escape(runner) + r"\s+(run\s+)?" + re.escape(name) + r"\b"
                add(name, "What is the exact command to " + phrase + "?", pattern)
        deps = {}
        for key in ("dependencies", "devDependencies"):
            block = pkg.get(key)
            if isinstance(block, dict):
                deps.update(block)
        for dep, label in TEST_FRAMEWORK_DEPS:
            if dep in deps:
                add("test-framework", "Which test framework does this repo use?", r"(?i)" + re.escape(label))
                break
        for dep, label in FORMATTER_DEPS:
            if dep in deps:
                add("formatter", "Which code formatter/linter does this repo use?", r"(?i)" + re.escape(label))
                break

    node_major = None
    nvmrc = root / ".nvmrc"
    if nvmrc.is_file():
        m = re.search(r"(\d+)", nvmrc.read_text(encoding="utf-8", errors="replace"))
        if m:
            node_major = m.group(1)
    if node_major is None and isinstance(pkg, dict):
        engines = pkg.get("engines")
        if isinstance(engines, dict) and isinstance(engines.get("node"), str):
            m = re.search(r"(\d+)", engines["node"])
            if m:
                node_major = m.group(1)
    if node_major:
        add("node-version", "Which Node.js major version does this repo target?", r"\b" + re.escape(node_major) + r"\b")

    gomod = root / "go.mod"
    if gomod.is_file():
        text = gomod.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^go\s+(\d+\.\d+)", text, re.M)
        if m:
            add(
                "go-version",
                "Which Go version does this module target (the go directive in go.mod)?",
                r"\b" + re.escape(m.group(1)) + r"\b",
            )
        mm = re.search(r"^module\s+(\S+)", text, re.M)
        if mm:
            add("go-module", "What is the Go module path declared in go.mod?", r"(?i)" + re.escape(mm.group(1)))

    # Python version: reuse the scan/drift fact engine's ground-truth sources
    # (semantic.python_ground_versions) instead of a private pyproject-first
    # heuristic. The two subsystems previously disagreed: eval fixed
    # pyproject's `requires-python` as the golden answer while scan judged the
    # very same value against `.python-version` and reported a MISMATCH, so an
    # agent could be rewarded for an answer the scanner calls wrong. Only emit a
    # golden-answer task when every pinned source agrees on one version; when
    # they conflict there is no unambiguous ground truth (that inconsistency is
    # exactly what the scanner flags), so abstain rather than bake in one side.
    py_grounds = semantic.python_ground_versions(root)
    py_values = {value for _source, value in py_grounds}
    if len(py_values) == 1:
        major, minor = next(iter(py_values))
        add(
            "python-version",
            "Which minimum Python version do this repo's scripts target?",
            r"\b" + re.escape(f"{major}.{minor}") + r"\b",
        )

    agents = root / "AGENTS.md"
    agents_text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    if agents_text and re.search(r"(?i)conventional commit", agents_text):
        add("commit-convention", "Does this repo follow a commit message convention? Which one?", r"(?i)conventional")

    if (root / "src" / "components").is_dir():
        add("components-dir", "In which directory should a new UI component file be created?", r"src/components")

    return tasks


def generate_report(args):
    """Emit an auto-generated tasks.json for the target repo (Phase 3 bootstrap)."""
    tasks = generate_tasks(args.generate)
    content = json.dumps(tasks, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content + "\n", encoding="utf-8")
        print(f"wrote {args.output} ({len(tasks)} tasks generated)")
    else:
        print(content)
    if not tasks:
        print("warning: no facts detected; is this a supported repo (Node/Go/Python + AGENTS.md)?", file=sys.stderr)
    return 0


def builtin_judge(answer, check):
    """Deterministic, dependency-free default judge.

    Grades ``answer`` against the task's ``check`` without any external command:
      - ``expect``: regex pattern(s) that MUST all match (case-insensitive).
      - ``reject``: regex pattern(s) that must NOT match.
      - otherwise: keyword coverage derived from the ``rubric`` / ``criteria`` text,
        passing when coverage >= ``min_score`` (default 0.5).
    Returns the same verdict shape as the external judge, tagged ``judge="builtin"``.
    """
    answer = answer or ""
    expect = _as_pattern_list(check.get("expect"))
    reject = _as_pattern_list(check.get("reject"))
    rubric = check.get("rubric") or check.get("criteria") or ""
    try:
        threshold = float(check.get("min_score", 0.5))
    except (TypeError, ValueError):
        threshold = 0.5

    criteria = []  # (label, satisfied)
    for pat in expect:
        criteria.append((f"expect:{pat}", re.search(pat, answer, re.I) is not None))
    for pat in reject:
        criteria.append((f"reject:{pat}", re.search(pat, answer, re.I) is None))

    keyword_mode = not expect and not reject
    if keyword_mode:
        for kw in rubric_keywords(rubric):
            criteria.append((f"keyword:{kw}", kw in answer.lower()))

    if not criteria:
        return {
            "passed": False,
            "score": 0.0,
            "judge": "builtin",
            "reason": "builtin judge needs `expect`/`reject`/`rubric` to grade; none provided",
        }

    satisfied = sum(1 for _, ok in criteria if ok)
    total = len(criteria)
    score = round(satisfied / total, 4)
    if keyword_mode:
        passed = score >= threshold
    else:
        passed = all(ok for _, ok in criteria)
    unmet = [label for label, ok in criteria if not ok]
    reason = f"builtin judge: {satisfied}/{total} criteria satisfied"
    if unmet:
        reason += "; unmet: " + ", ".join(unmet[:5])
    return {"passed": bool(passed), "score": score, "reason": reason, "judge": "builtin"}


HEALTH_GRADES = [(90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F")]


def health_grade(score):
    for threshold, letter in HEALTH_GRADES:
        if score >= threshold:
            return letter
    return "F"


def _collect_records(data):
    """Return the flat list of task records from a run-tasks or matrix result dict."""
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("agents"), dict):
        records = []
        for agent in data["agents"].values():
            if isinstance(agent, dict):
                records.extend(agent.get("tasks", []) or [])
        return records
    return data.get("tasks", []) or []


def compute_health(data):
    """Compute an automated efficacy health score (0-100) with a letter grade.

    Works on both a single ``run`` result (``{"tasks": [...]}``) and a ``matrix``
    result (``{"agents": {...}}``); the score is the pass rate across every task
    record. Timeouts count as failures.
    """
    records = _collect_records(data)
    total = len(records)
    passed = sum(1 for r in records if r.get("passed"))
    timed_out = sum(1 for r in records if r.get("timed_out"))
    pass_rate = (passed / total) if total else 0.0
    score = round(100 * pass_rate)
    return {
        "score": score,
        "grade": health_grade(score),
        "passed": passed,
        "total": total,
        "timed_out": timed_out,
        "pass_rate": round(pass_rate, 4),
    }


def _round_records(round_result):
    """Return the flat task records for a single round result."""
    if isinstance(round_result, dict):
        return round_result.get("tasks", []) or []
    return []


def aggregate_task_stats(round_results):
    """Per-task pass/fail statistics across N rounds.

    Returns an ordered list (first-seen order) of
    ``{id, runs, passed, failed, timed_out, pass_rate, flaky}``. A task is
    ``flaky`` when it both passes and fails across the rounds (i.e. it is not
    consistently green or consistently red).
    """
    order = []
    seen = {}
    for rr in round_results:
        for rec in _round_records(rr):
            tid = rec.get("id")
            if tid not in seen:
                seen[tid] = {"id": tid, "runs": 0, "passed": 0, "timed_out": 0}
                order.append(tid)
            entry = seen[tid]
            entry["runs"] += 1
            if rec.get("passed"):
                entry["passed"] += 1
            if rec.get("timed_out"):
                entry["timed_out"] += 1
    stats = []
    for tid in order:
        entry = seen[tid]
        entry["failed"] = entry["runs"] - entry["passed"]
        entry["pass_rate"] = round(entry["passed"] / entry["runs"], 4) if entry["runs"] else 0.0
        entry["flaky"] = 0 < entry["passed"] < entry["runs"]
        stats.append(entry)
    return stats


def _round_health_score(round_result):
    health = round_result.get("health") if isinstance(round_result, dict) else None
    if isinstance(health, dict) and "score" in health:
        return health["score"]
    return compute_health(round_result)["score"]


def summarize_rounds(round_results):
    """Aggregate per-round health + per-task flakiness across N rounds.

    Returns ``(task_stats, stats)`` where ``stats`` carries the mean health
    score across rounds, its (population) variance / standard deviation, the
    per-round health scores, and the flaky-task list.
    """
    task_stats = aggregate_task_stats(round_results)
    scores = [_round_health_score(rr) for rr in round_results]
    n = len(scores)
    mean = (sum(scores) / n) if n else 0.0
    variance = (sum((x - mean) ** 2 for x in scores) / n) if n else 0.0
    flaky = [t["id"] for t in task_stats if t["flaky"]]
    stats = {
        "rounds": n,
        "health_scores": scores,
        "mean_health": round(mean, 4),
        "variance": round(variance, 4),
        "stddev": round(variance**0.5, 4),
        "min_health": min(scores) if scores else 0,
        "max_health": max(scores) if scores else 0,
        "flaky_tasks": flaky,
        "flaky_count": len(flaky),
        "task_count": len(task_stats),
    }
    return task_stats, stats


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
            judge_cmd.replace("{answer}", shlex.quote(answer))
            .replace("{rubric}", shlex.quote(rubric))
            .replace("{input}", shlex.quote(handle.name))
        )
        proc = subprocess.run(
            command,
            cwd=str(workdir) if workdir else None,
            text=True,
            capture_output=True,
            shell=True,
            env=env,
            timeout=timeout,
        )
        verdict = parse_judge_output(proc.stdout)
        verdict["exit_code"] = proc.returncode
        return verdict
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# LLM-as-judge (real model APIs, standard library only). When a task uses a
# ``judge`` check and no external ``--judge-cmd`` is supplied, the judge can be
# delegated to a real LLM (OpenAI- or Anthropic-compatible HTTP API) via
# ``--judge-llm``. Every failure mode — no API key, network error, malformed
# response — returns ``None`` so grading gracefully falls back to the built-in
# deterministic keyword judge. No third-party packages: HTTP uses urllib.
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = (
    "You are a strict, fair grader for an AI coding-agent evaluation. You are "
    "given a RUBRIC describing what a correct answer must contain and the "
    "agent's ANSWER. Decide whether the answer satisfies the rubric. Respond "
    "with ONLY a compact JSON object: "
    '{"passed": true|false, "score": <number 0..1>, "reason": "<short>"}.'
)


def _judge_user_prompt(answer, rubric):
    return (
        "RUBRIC:\n" + (rubric or "(no rubric provided)") + "\n\n"
        "ANSWER:\n" + (answer or "(empty answer)") + "\n\n"
        'Return ONLY the JSON verdict, e.g. {"passed": true, "score": 1, "reason": "..."}.'
    )


def _http_post_json(url, headers, payload, timeout):
    """POST ``payload`` as JSON and return the parsed JSON response (stdlib)."""
    import urllib.request

    body = json.dumps(payload).encode("utf-8")
    merged = {"Content-Type": "application/json"}
    merged.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=merged, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_llm_provider(provider):
    """Map ``auto`` to a concrete provider based on available API keys."""
    provider = (provider or "off").lower()
    if provider == "auto":
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "claude"
        return None
    return provider


def llm_judge(answer, rubric, provider="auto", timeout=60, model=None):
    """Grade an answer with a real LLM. Returns a verdict dict or ``None``.

    ``None`` means "unavailable / failed — fall back to the keyword judge":
    no matching API key, an unsupported provider, or any network/parse error.
    A successful verdict has the usual shape plus ``judge="llm:<provider>"``
    and the ``model`` used.
    """
    provider = _resolve_llm_provider(provider)
    if provider not in ("openai", "claude"):
        return None
    try:
        if provider == "openai":
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return None
            base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            used_model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            data = _http_post_json(
                base + "/chat/completions",
                {"Authorization": "Bearer " + key},
                {
                    "model": used_model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": _judge_user_prompt(answer, rubric)},
                    ],
                },
                timeout,
            )
            content = data["choices"][0]["message"]["content"]
        else:  # claude
            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                return None
            base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
            used_model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
            data = _http_post_json(
                base + "/v1/messages",
                {"x-api-key": key, "anthropic-version": "2023-06-01"},
                {
                    "model": used_model,
                    "max_tokens": 512,
                    "temperature": 0,
                    "system": JUDGE_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": _judge_user_prompt(answer, rubric)}],
                },
                timeout,
            )
            blocks = data.get("content", [])
            content = "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    except Exception as exc:  # noqa: BLE001 - any failure must fall back, never crash
        print(f"llm judge ({provider}) failed, falling back to keyword judge: {exc}", file=sys.stderr)
        return None
    verdict = parse_judge_output(content)
    verdict["judge"] = "llm:" + provider
    verdict["model"] = used_model
    return verdict


def grade_answer(task, answer, workdir, judge_cmd=None, default_judge=True, judge_llm="off"):
    """Grade an answer for a task, returning ``(passed, judge_info)``.

    Supports ``regex``, ``command`` and ``judge`` check types. ``judge_info`` is
    ``None`` for non-judge checks. Timeouts count as a failure (no exception is
    propagated) so a matrix run keeps going.

    For ``judge`` checks an external ``--judge-cmd`` takes priority; otherwise,
    when ``judge_llm`` names/auto-detects a provider, a real LLM grades the
    answer. Any LLM failure (no key, network, parse) transparently falls back to
    the deterministic built-in judge (:func:`builtin_judge`) so judge checks
    always work. Pass ``default_judge=False`` to restore the legacy "requires
    --judge-cmd" behavior.
    """
    check = task.get("check", {})
    ctype = check.get("type")
    timeout = task.get("timeout_s", 60)
    if ctype == "regex":
        return regex_passes(check.get("value", ""), answer), None
    if ctype == "command":
        try:
            cproc = subprocess.run(
                check.get("value", ""), cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=timeout
            )
            return cproc.returncode == 0, None
        except subprocess.TimeoutExpired:
            return False, None
    if ctype == "judge":
        rubric = check.get("rubric") or check.get("criteria") or ""
        if judge_cmd:
            try:
                verdict = run_judge(judge_cmd, answer, rubric, workdir, timeout)
            except subprocess.TimeoutExpired:
                return False, {"passed": False, "score": None, "reason": "judge timed out"}
            return verdict["passed"], verdict
        if judge_llm and judge_llm != "off":
            verdict = llm_judge(answer, rubric, provider=judge_llm, timeout=timeout, model=check.get("model"))
            if verdict is not None:
                return verdict["passed"], verdict
        if default_judge:
            verdict = builtin_judge(answer, check)
            return verdict["passed"], verdict
        return False, {"passed": False, "score": None, "reason": "no --judge-cmd provided"}
    return False, None


def _run_round(tasks, args, workdir):
    """Run every task once and return the list of graded task records."""
    records = []
    for task in tasks:
        prompt = task["prompt"]
        command = args.runner.replace("{prompt}", shlex.quote(prompt))
        start = time.time()
        try:
            proc = subprocess.run(
                command, cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60)
            )
        except subprocess.TimeoutExpired as exc:
            duration = round(time.time() - start, 3)
            stdout = timeout_output(exc.stdout)
            records.append(
                {
                    "id": task["id"],
                    "passed": False,
                    "timed_out": True,
                    "duration_s": duration,
                    "exit_code": None,
                    "stdout": stdout,
                    "answer": extract_answer(stdout),
                    "stderr": timeout_output(exc.stderr),
                    "usage": {},
                }
            )
            continue
        duration = round(time.time() - start, 3)
        answer = extract_answer(proc.stdout)
        passed, judge_info = grade_answer(
            task,
            answer,
            workdir,
            args.judge_cmd,
            not args.no_default_judge,
            judge_llm=getattr(args, "judge_llm", "off"),
        )
        record = {
            "id": task["id"],
            "passed": passed,
            "timed_out": False,
            "duration_s": duration,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "answer": answer,
            "stderr": proc.stderr,
            "usage": maybe_usage(proc.stdout),
        }
        if judge_info is not None:
            record["judge"] = judge_info
        records.append(record)
    return records


def run_tasks(args):
    tasks_path = Path(args.tasks)
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    binary = runner_binary(args.runner)
    if binary and shutil.which(binary) is None:
        print(manual_protocol(binary, args.tasks), file=sys.stderr)
        return 127
    workdir = Path(args.workdir).resolve()
    rounds = args.rounds if args.rounds and args.rounds > 1 else 1

    if rounds == 1:
        # Single-round default: byte-compatible with the previous output shape.
        results = {"label": args.label, "workdir": str(workdir), "tasks": _run_round(tasks, args, workdir)}
        results["health"] = compute_health(results)
        output = Path(args.output) if args.output else Path(f"results-{args.label}.json")
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {output}")
        health = results["health"]
        print(
            f"health score: {health['score']}/100 (grade {health['grade']}), "
            f"{health['passed']}/{health['total']} tasks passed"
        )
        rc = apply_baseline(args, health, workdir)
        if args.fail_under is not None and health["score"] < args.fail_under:
            print(f"health score {health['score']} is below --fail-under {args.fail_under}", file=sys.stderr)
            return rc or 5
        return rc

    # Multi-round: run the task set N times, then aggregate per-task stats.
    round_results = []
    for i in range(rounds):
        recs = _run_round(tasks, args, workdir)
        rr = {"round": i + 1, "tasks": recs}
        rr["health"] = compute_health(rr)
        round_results.append(rr)
    task_stats, stats = summarize_rounds(round_results)
    results = {
        "label": args.label,
        "workdir": str(workdir),
        "rounds": rounds,
        "round_results": round_results,
        "task_stats": task_stats,
        "stats": stats,
    }
    # Overall health = pass rate across every task record from every round.
    all_records = {"tasks": [rec for rr in round_results for rec in rr["tasks"]]}
    results["health"] = compute_health(all_records)
    output = Path(args.output) if args.output else Path(f"results-{args.label}.json")
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    print(render_stats_summary(stats, results["health"]), end="")
    rc = apply_baseline(args, results["health"], workdir)
    if args.fail_under is not None and results["health"]["score"] < args.fail_under:
        print(f"health score {results['health']['score']} is below --fail-under {args.fail_under}", file=sys.stderr)
        return rc or 5
    return rc


def render_stats_summary(stats, overall_health=None):
    """Human-readable multi-round summary block."""
    lines = []
    lines.append(f"ran {stats['rounds']} round(s) over {stats['task_count']} task(s)")
    if overall_health is not None:
        lines.append(
            f"overall health score: {overall_health['score']}/100 (grade {overall_health['grade']}), "
            f"{overall_health['passed']}/{overall_health['total']} task-runs passed"
        )
    lines.append(
        f"mean per-round health: {stats['mean_health']}/100 "
        f"(stddev {stats['stddev']}, variance {stats['variance']}, "
        f"min {stats['min_health']}, max {stats['max_health']})"
    )
    lines.append(f"per-round health scores: {stats['health_scores']}")
    if stats["flaky_tasks"]:
        lines.append(f"flaky tasks ({stats['flaky_count']}): {', '.join(stats['flaky_tasks'])}")
    else:
        lines.append("flaky tasks: none")
    return "\n".join(lines) + "\n"


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
    lines = [
        "# Phase 3 — Efficacy Comparison Report",
        "",
        f"Before label: `{before.get('label')}`",
        f"After label: `{after.get('label')}`",
        "",
        "| Task | Before | After | Duration Δ(s) | Usage |",
        "|---|---:|---:|---:|---|",
    ]
    before_pass = after_pass = 0
    for tid in ids:
        b, a = bmap.get(tid, {}), amap.get(tid, {})
        before_pass += 1 if b.get("passed") else 0
        after_pass += 1 if a.get("passed") else 0
        delta = round((a.get("duration_s") or 0) - (b.get("duration_s") or 0), 3)
        usage = json.dumps(a.get("usage") or b.get("usage") or {}, ensure_ascii=False)
        lines.append(f"| `{tid}` | {b.get('passed')} | {a.get('passed')} | {delta} | `{usage}` |")
    lines.extend(
        [
            "",
            f"Summary: pass rate {before_pass}/{len(ids)} → {after_pass}/{len(ids)}; "
            f"delta {after_pass - before_pass} tasks.",
        ]
    )
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


def run_task_with_runner(runner, task, workdir, judge_cmd, default_judge=True, judge_llm="off"):
    """Run a single task under a single runner and return a graded record."""
    prompt = task["prompt"]
    command = runner.replace("{prompt}", shlex.quote(prompt))
    start = time.time()
    try:
        proc = subprocess.run(
            command, cwd=str(workdir), text=True, capture_output=True, shell=True, timeout=task.get("timeout_s", 60)
        )
    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - start, 3)
        stdout = timeout_output(exc.stdout)
        return {
            "id": task["id"],
            "passed": False,
            "timed_out": True,
            "duration_s": duration,
            "exit_code": None,
            "answer": extract_answer(stdout),
            "usage": {},
        }
    duration = round(time.time() - start, 3)
    answer = extract_answer(proc.stdout)
    passed, judge_info = grade_answer(task, answer, workdir, judge_cmd, default_judge, judge_llm=judge_llm)
    record = {
        "id": task["id"],
        "passed": passed,
        "timed_out": False,
        "duration_s": duration,
        "exit_code": proc.returncode,
        "answer": answer,
        "usage": maybe_usage(proc.stdout),
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
    lines.extend(
        ["", "## Per-agent pass rate", "", "| Agent | Runner | Pass | Total | Pass rate |", "|---|---|---:|---:|---:|"]
    )
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
        agent_records[name] = [
            run_task_with_runner(
                runner,
                task,
                workdir,
                args.judge_cmd,
                not args.no_default_judge,
                judge_llm=getattr(args, "judge_llm", "off"),
            )
            for task in tasks
        ]
    summary = {}
    for name, recs in agent_records.items():
        total = len(recs)
        passed = sum(1 for r in recs if r.get("passed"))
        summary[name] = {"passed": passed, "total": total, "pass_rate": round(passed / total, 4) if total else 0.0}
    matrix = {
        "workdir": str(workdir),
        "agents": {
            name: {"runner": runners[name], "tasks": recs, "summary": summary[name]}
            for name, recs in agent_records.items()
        },
        "summary": summary,
    }
    matrix["health"] = compute_health(matrix)
    json_out = Path(args.matrix_json) if args.matrix_json else Path("matrix-results.json")
    json_out.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    report_out = (
        Path(args.matrix_report)
        if args.matrix_report
        else (Path(args.output) if args.output else Path("matrix-report.md"))
    )
    report_out.write_text(render_matrix(tasks, agent_records, runners), encoding="utf-8")
    print(f"wrote {json_out}")
    print(f"wrote {report_out}")
    health = matrix["health"]
    print(
        f"health score: {health['score']}/100 (grade {health['grade']}), "
        f"{health['passed']}/{health['total']} tasks passed"
    )
    rc = apply_baseline(args, health, workdir)
    if args.fail_under is not None and health["score"] < args.fail_under:
        print(f"health score {health['score']} is below --fail-under {args.fail_under}", file=sys.stderr)
        return rc or 5
    return rc


def score_report(args):
    """One-click health score from an existing results / matrix JSON file."""
    data = json.loads(Path(args.score).read_text(encoding="utf-8"))
    health = data.get("health") if isinstance(data, dict) else None
    if not isinstance(health, dict) or "score" not in health:
        health = compute_health(data)
    if args.as_json:
        print(json.dumps(health, ensure_ascii=False, indent=2))
    else:
        print(f"Health score: {health['score']}/100 (grade {health['grade']})")
        print(f"{health['passed']}/{health['total']} tasks passed; {health.get('timed_out', 0)} timed out")
    workdir = Path(args.workdir).resolve() if getattr(args, "workdir", None) else None
    rc = apply_baseline(args, health, workdir)
    if args.fail_under is not None and health["score"] < args.fail_under:
        print(f"health score {health['score']} is below --fail-under {args.fail_under}", file=sys.stderr)
        return rc or 5
    return rc


def stats_report(args):
    """Aggregate multi-round statistics from an existing results JSON file.

    Accepts a multi-round file produced by ``--rounds`` (has ``round_results``)
    or a bare list of round result objects. Re-computes the per-task flakiness
    and per-round health summary so old result files can be analysed offline.
    """
    data = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("round_results"), list):
        round_results = data["round_results"]
    elif isinstance(data, list):
        round_results = data
    elif isinstance(data, dict) and isinstance(data.get("tasks"), list):
        # A single-round result file: treat it as one round.
        round_results = [data]
    else:
        raise SystemExit(
            "--stats file must contain 'round_results', a list of rounds, or a single-round 'tasks' result"
        )
    task_stats, stats = summarize_rounds(round_results)
    overall = compute_health({"tasks": [rec for rr in round_results for rec in _round_records(rr)]})
    if args.as_json:
        print(json.dumps({"task_stats": task_stats, "stats": stats, "health": overall}, ensure_ascii=False, indent=2))
    else:
        print(render_stats_summary(stats, overall), end="")
    workdir = Path(args.workdir).resolve() if getattr(args, "workdir", None) else None
    rc = apply_baseline(args, overall, workdir)
    if args.fail_under is not None and overall["score"] < args.fail_under:
        print(f"health score {overall['score']} is below --fail-under {args.fail_under}", file=sys.stderr)
        return rc or 5
    return rc


# ---------------------------------------------------------------------------
# Baseline persistence + trend / regression tracking. A baseline "store" is a
# JSON list of health snapshots (append-only history). After any run you can
# --save-baseline to record the current health, and --check-regression to gate
# on a drop versus the most recent prior snapshot. --trend renders the history.
# Everything is standard library only and degrades gracefully on missing files.
# ---------------------------------------------------------------------------


def _now_iso():
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_meta(workdir):
    """Best-effort ``{commit, branch}`` for the target repo (None on failure)."""
    meta = {"commit": None, "branch": None}
    if not workdir:
        return meta
    try:
        commit = subprocess.run(
            ["git", "-C", str(workdir), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        if commit.returncode == 0:
            meta["commit"] = commit.stdout.strip()[:12] or None
        branch = subprocess.run(
            ["git", "-C", str(workdir), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=10
        )
        if branch.returncode == 0:
            meta["branch"] = branch.stdout.strip() or None
    except Exception:  # noqa: BLE001 - git metadata is optional
        pass
    return meta


def load_baseline_store(path):
    """Load a baseline history file into a list; empty list if absent/invalid."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("baselines"), list):
        return data["baselines"]
    return []


def save_baseline_store(path, store):
    Path(path).write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_baseline_entry(label, health, workdir=None):
    entry = {
        "timestamp": _now_iso(),
        "label": label,
        "score": health.get("score"),
        "grade": health.get("grade"),
        "passed": health.get("passed"),
        "total": health.get("total"),
        "timed_out": health.get("timed_out", 0),
        "pass_rate": health.get("pass_rate"),
    }
    if workdir:
        entry["git"] = git_meta(workdir)
    return entry


def detect_regression(store, current_score, threshold):
    """Compare ``current_score`` to the most recent prior snapshot in the store.

    Returns ``None`` when there is no comparable prior score, otherwise a dict
    describing the delta and whether it is a regression (drop >= threshold).
    """
    prior = [e for e in store if isinstance(e.get("score"), (int, float))]
    if not prior:
        return None
    prev = prior[-1]
    prev_score = prev["score"]
    delta = round(current_score - prev_score, 2)
    return {
        "prev_score": prev_score,
        "current_score": current_score,
        "delta": delta,
        "regressed": (prev_score - current_score) >= threshold,
        "threshold": threshold,
        "prev_label": prev.get("label"),
        "prev_timestamp": prev.get("timestamp"),
    }


def render_regression(reg):
    arrow = "▼" if reg["delta"] < 0 else ("▲" if reg["delta"] > 0 else "=")
    status = "REGRESSION" if reg["regressed"] else "ok"
    return (
        f"baseline compare: {reg['prev_score']} -> {reg['current_score']} "
        f"({arrow} {reg['delta']:+g}) vs `{reg['prev_label']}` "
        f"[{status}, threshold {reg['threshold']:g}]\n"
    )


def render_trend(store):
    """Render a markdown trend table over the baseline history."""
    lines = ["# Eval baseline trend", ""]
    if not store:
        lines.append("_No baseline snapshots recorded yet._")
        return "\n".join(lines) + "\n"
    lines.append("| # | Timestamp | Label | Score | Grade | Δ | Commit | Regression |")
    lines.append("|---:|---|---|---:|---|---:|---|---|")
    prev_score = None
    for i, e in enumerate(store, 1):
        score = e.get("score")
        if isinstance(score, (int, float)) and isinstance(prev_score, (int, float)):
            delta = round(score - prev_score, 2)
            delta_str = f"{delta:+g}"
            regressed = "⚠️" if delta < 0 else ""
        else:
            delta_str = "—"
            regressed = ""
        commit = (e.get("git") or {}).get("commit") or "—"
        lines.append(
            f"| {i} | {e.get('timestamp', '—')} | `{e.get('label', '—')}` | "
            f"{score if score is not None else '—'} | {e.get('grade', '—')} | "
            f"{delta_str} | `{commit}` | {regressed} |"
        )
        if isinstance(score, (int, float)):
            prev_score = score
    scores = [e.get("score") for e in store if isinstance(e.get("score"), (int, float))]
    if scores:
        lines.extend(["", f"Snapshots: {len(store)}; latest score {scores[-1]}; min {min(scores)}, max {max(scores)}."])
    return "\n".join(lines) + "\n"


def apply_baseline(args, health, workdir=None):
    """Handle --check-regression (against the existing store) then --save-baseline.

    Regression is checked BEFORE appending so the current run is compared to the
    prior history. Returns a process exit code (6 on regression, else 0).
    """
    if not getattr(args, "baseline", None):
        return 0
    store = load_baseline_store(args.baseline)
    rc = 0
    if getattr(args, "check_regression", False):
        reg = detect_regression(store, health["score"], args.regression_threshold)
        if reg is None:
            print("no prior baseline snapshot to compare against; skipping regression check")
        else:
            print(render_regression(reg), end="")
            if reg["regressed"]:
                print(
                    f"eval regression: score dropped {reg['prev_score']} -> {reg['current_score']} "
                    f"(>= --regression-threshold {args.regression_threshold:g})",
                    file=sys.stderr,
                )
                rc = 6
    if getattr(args, "save_baseline", False):
        label = getattr(args, "label", None) or health.get("label") or "baseline"
        store.append(make_baseline_entry(label, health, workdir))
        save_baseline_store(args.baseline, store)
        print(f"appended baseline snapshot to {args.baseline} ({len(store)} total)")
    return rc


def trend_report(args):
    """Standalone: render the trend of an existing baseline store."""
    store = load_baseline_store(args.trend)
    if args.as_json:
        print(json.dumps(store, ensure_ascii=False, indent=2))
    else:
        print(render_trend(store), end="")
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
    parser.add_argument(
        "--judge-cmd",
        dest="judge_cmd",
        help="Command template for LLM-as-judge checks (see SKILL.md for the contract).",
    )
    parser.add_argument("--matrix", help="JSON file mapping agent name -> runner command template.")
    parser.add_argument(
        "--runner-cmd",
        dest="runner_cmd",
        action="append",
        default=[],
        help="Repeatable NAME=CMD runner for the eval matrix.",
    )
    parser.add_argument("--matrix-report", dest="matrix_report", help="Output path for the markdown matrix report.")
    parser.add_argument("--matrix-json", dest="matrix_json", help="Output path for the matrix JSON results.")
    parser.add_argument(
        "--no-default-judge",
        dest="no_default_judge",
        action="store_true",
        help="Disable the built-in judge; judge checks then require --judge-cmd (legacy behavior).",
    )
    parser.add_argument("--score", help="Print an automated health score for an existing results / matrix JSON file.")
    parser.add_argument(
        "--stats",
        help="Aggregate multi-round statistics (flakiness, mean/variance) from an existing results JSON file.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Run the task set N times and aggregate per-task flakiness + per-round health stats (default 1).",
    )
    parser.add_argument(
        "--fail-under",
        dest="fail_under",
        type=float,
        default=None,
        help="Exit 5 when the health score is below this value (0-100).",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Emit machine-readable JSON (used by --score)."
    )
    parser.add_argument(
        "--generate",
        metavar="REPO",
        help="Auto-generate a tasks.json from repository facts (AGENTS.md + code structure) instead of running.",
    )
    parser.add_argument(
        "--judge-llm",
        dest="judge_llm",
        choices=["off", "auto", "openai", "claude"],
        default="auto",
        help=(
            "LLM-as-judge provider for judge checks without --judge-cmd: 'auto' uses "
            "OpenAI/Claude when an API key is set and otherwise falls back to the "
            "keyword judge (default auto)."
        ),
    )
    parser.add_argument(
        "--judge-model",
        dest="judge_model",
        default=None,
        help="Override the LLM judge model name (else OPENAI_MODEL/ANTHROPIC_MODEL or a built-in default).",
    )
    parser.add_argument("--baseline", help="Baseline history JSON file for trend/regression tracking.")
    parser.add_argument(
        "--save-baseline",
        dest="save_baseline",
        action="store_true",
        help="Append the current run's health as a snapshot to --baseline.",
    )
    parser.add_argument(
        "--check-regression",
        dest="check_regression",
        action="store_true",
        help="Exit 6 when the current score drops >= --regression-threshold below the latest --baseline snapshot.",
    )
    parser.add_argument(
        "--regression-threshold",
        dest="regression_threshold",
        type=float,
        default=5.0,
        help="Regression gate: score drop (points) that counts as a regression (default 5).",
    )
    parser.add_argument("--trend", help="Render the trend of an existing --baseline-style history file and exit.")
    args = parser.parse_args(argv)
    if args.judge_model:
        # A model override is expressed through the check's optional "model"
        # field; expose it via env so llm_judge picks it up for both providers.
        os.environ.setdefault("OPENAI_MODEL", args.judge_model)
        os.environ.setdefault("ANTHROPIC_MODEL", args.judge_model)
    if args.generate:
        return generate_report(args)
    if args.trend:
        return trend_report(args)
    if args.score:
        return score_report(args)
    if args.stats:
        return stats_report(args)
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
