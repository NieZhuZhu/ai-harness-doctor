"""Consistency guard for the benchmark corpus (benchmark/corpus/).

The corpus is a set of well-known open-source repositories pinned as shallow
git submodules and scanned with ``scan.py --repos-file``. Three artifacts must
never drift apart: the submodule declarations (``.gitmodules``), the scan input
(``benchmark/corpus/repos.txt``), and the committed scan results
(``benchmark/corpus/results/corpus-scan.json``). Everything here reads only
committed metadata, so the suite stays green on checkouts that never ran
``git submodule update`` (CI does not initialize submodules).
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scan  # noqa: E402

GITMODULES = ROOT / ".gitmodules"
REPOS_TXT = ROOT / "benchmark" / "corpus" / "repos.txt"
RESULTS_JSON = ROOT / "benchmark" / "corpus" / "results" / "corpus-scan.json"
CORPUS_README = ROOT / "benchmark" / "corpus" / "README.md"
CORPUS_PREFIX = "benchmark/corpus/repos/"


def gitmodules_entries():
    """Parse ``.gitmodules`` into ``{path: {key: value}}`` (stdlib only)."""
    entries = {}
    current = None
    for line in GITMODULES.read_text(encoding="utf-8").splitlines():
        section = re.match(r'^\[submodule "(?P<name>[^"]+)"\]$', line.strip())
        if section:
            current = {}
            entries[section.group("name")] = current
            continue
        if current is None:
            continue
        kv = re.match(r"^(?P<key>[a-zA-Z]+)\s*=\s*(?P<value>.+)$", line.strip())
        if kv:
            current[kv.group("key")] = kv.group("value").strip()
    return {props["path"]: props for props in entries.values() if "path" in props}


class BenchmarkCorpusConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.modules = gitmodules_entries()
        self.corpus_modules = {
            path: props for path, props in self.modules.items() if path.startswith(CORPUS_PREFIX)
        }
        self.repos = scan.read_repos_file(REPOS_TXT)

    def test_corpus_has_at_least_ten_pinned_repositories(self):
        self.assertGreaterEqual(len(self.corpus_modules), 10)

    def test_every_corpus_submodule_is_shallow_https_github(self):
        for path, props in self.corpus_modules.items():
            self.assertEqual(props.get("shallow"), "true", f"{path} must set shallow = true")
            self.assertRegex(
                props.get("url", ""),
                r"^https://github\.com/[^/]+/[^/]+(\.git)?$",
                f"{path} must point at a public https GitHub URL",
            )

    def test_repos_file_matches_gitmodules(self):
        self.assertEqual(sorted(self.repos), sorted(self.corpus_modules))

    def test_repos_file_entries_stay_inside_the_corpus(self):
        for entry in self.repos:
            self.assertTrue(entry.startswith(CORPUS_PREFIX), entry)
            self.assertNotIn("..", entry)

    def test_committed_results_cover_exactly_the_corpus(self):
        payload = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["repo_count"], len(self.repos))
        self.assertEqual(payload["summary"]["error_count"], 0)
        self.assertEqual(
            sorted(repo["path"] for repo in payload["repos"]),
            sorted(self.repos),
        )
        for repo in payload["repos"]:
            self.assertNotIn("error", repo, f"{repo['path']} could not be scanned")

    def test_committed_results_are_host_independent(self):
        raw = RESULTS_JSON.read_text(encoding="utf-8")
        md = (RESULTS_JSON.parent / "corpus-scan.md").read_text(encoding="utf-8")
        self.assertNotIn('"resolved"', raw, "strip machine-local resolved paths before committing")
        for marker in ("/Users/", "/home/", "C:\\\\"):
            self.assertNotIn(marker, raw)
            self.assertNotIn(marker, md)

    def test_corpus_readme_documents_every_repository(self):
        text = CORPUS_README.read_text(encoding="utf-8")
        for entry in self.repos:
            name = entry.rsplit("/", 1)[-1]
            self.assertIn(f"`{name}`", text, f"corpus README must document {name}")


EVALS_DIR = ROOT / "benchmark" / "corpus" / "evals"
EVAL_RESULTS = [
    "results-before.json",
    "results-before-run2.json",
    "results-after.json",
    "results-after-run2.json",
]


class RealRepoEvalConsistencyTests(unittest.TestCase):
    """Guard every committed real-repo before/after eval under evals/.

    Like the corpus guard above, this reads only committed files: for each
    eval directory the task pack, the four persisted result files, and the
    eval README must agree with each other and stay host-independent, so a
    future re-run cannot silently commit data that contradicts the documented
    result (null or positive alike).
    """

    def eval_dirs(self):
        dirs = sorted(d for d in EVALS_DIR.iterdir() if d.is_dir())
        self.assertGreaterEqual(len(dirs), 1, "at least one committed eval expected")
        return dirs

    def test_task_packs_are_well_formed(self):
        for d in self.eval_dirs():
            tasks = json.loads((d / "tasks.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(tasks), 10, d.name)
            ids = [task["id"] for task in tasks]
            self.assertEqual(len(ids), len(set(ids)), f"{d.name}: task ids must be unique")
            for task in tasks:
                self.assertEqual(task["check"]["type"], "regex", f"{d.name}:{task['id']}")
                re.compile(task["check"]["value"])

    def test_results_cover_exactly_the_task_pack(self):
        for d in self.eval_dirs():
            tasks = json.loads((d / "tasks.json").read_text(encoding="utf-8"))
            expected_ids = sorted(task["id"] for task in tasks)
            for name in EVAL_RESULTS:
                payload = json.loads((d / "results" / name).read_text(encoding="utf-8"))
                self.assertTrue(payload["label"].startswith(f"{d.name}-"), f"{d.name}:{name}")
                self.assertEqual(
                    sorted(t["id"] for t in payload["tasks"]), expected_ids, f"{d.name}:{name}"
                )
                for record in payload["tasks"]:
                    self.assertFalse(record["timed_out"], f"{d.name}:{name}:{record['id']}")

    def test_committed_eval_artifacts_are_host_independent(self):
        for d in self.eval_dirs():
            files = [d / "tasks.json", d / "README.md", d / "results" / "report.md"]
            files += [d / "results" / name for name in EVAL_RESULTS]
            for path in files:
                raw = path.read_text(encoding="utf-8")
                for marker in ("/Users/", "/home/", "C:\\", "/private/tmp"):
                    self.assertNotIn(marker, raw, f"{d.name}:{path.name}")

    def test_readme_pass_counts_match_committed_results(self):
        for d in self.eval_dirs():
            readme = (d / "README.md").read_text(encoding="utf-8")
            for side in ("before", "after"):
                passed = 0
                total = 0
                for name in EVAL_RESULTS:
                    if f"-{side}" not in name:
                        continue
                    payload = json.loads((d / "results" / name).read_text(encoding="utf-8"))
                    passed += sum(1 for t in payload["tasks"] if t["passed"])
                    total += len(payload["tasks"])
                self.assertIn(
                    f"| {side} | {passed}/{total} |",
                    readme,
                    f"{d.name}: README table row for `{side}` must match the committed results",
                )

    def test_readme_documents_the_pinned_commit(self):
        for d in self.eval_dirs():
            readme = (d / "README.md").read_text(encoding="utf-8")
            pin = re.search(r"`([0-9a-f]{40})`", readme)
            self.assertIsNotNone(pin, f"{d.name}: eval README must state the pinned commit")


if __name__ == "__main__":
    unittest.main()
