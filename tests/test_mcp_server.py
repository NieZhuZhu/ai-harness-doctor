import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "bin" / "mcp-server.js"
NODE = shutil.which("node") or "node"
DRIFT = ROOT / "scripts" / "check_drift.py"
CANONICALIZE = ROOT / "scripts" / "canonicalize.py"
LATEST_PROTOCOL = "2025-11-25"
LEGACY_PROTOCOL = "2024-11-05"


class McpServerTests(unittest.TestCase):
    def _exchange(self, messages, cwd=None, env=None):
        """Send newline-delimited JSON messages to the MCP server and parse responses."""
        payload = "".join(json.dumps(m) + "\n" for m in messages)
        proc = subprocess.run(
            [NODE, str(SERVER)],
            input=payload,
            text=True,
            capture_output=True,
            cwd=str(cwd) if cwd else None,
            env=env,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        responses = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            responses.append(json.loads(line))
        return responses

    def _initialize(self, request_id=100, version=LATEST_PROTOCOL):
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "ai-harness-doctor-tests", "version": "1.0.0"},
            },
        }

    def _call(self, name, arguments=None, env=None, protocol=LATEST_PROTOCOL):
        params = {"name": name}
        if arguments is not None:
            params["arguments"] = arguments
        messages = []
        if protocol is not None:
            messages.extend(
                [
                    self._initialize(version=protocol),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                ]
            )
        messages.append(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": params}
        )
        responses = self._exchange(messages, env=env)
        return next(response for response in responses if response.get("id") == 1)

    def _metadata(self, result):
        self.assertEqual(len(result["content"]), 2)
        self.assertEqual(result["content"][1]["type"], "text")
        metadata = json.loads(result["content"][1]["text"])
        self.assertEqual(metadata["kind"], "ai-harness-doctor/tool-result")
        self.assertIn(metadata["status"], {"ok", "findings", "error"})
        self.assertEqual(result["structuredContent"], metadata)
        self.assertIsInstance(metadata["ok"], bool)
        self.assertTrue(metadata["exitCode"] is None or isinstance(metadata["exitCode"], int))
        return metadata

    def _complete_repo(self, root):
        (root / "src").mkdir()
        (root / ".github" / "workflows").mkdir(parents=True)
        (root / ".github" / "workflows" / "harness-drift.yml").write_text(
            "name: drift\n",
            encoding="utf-8",
        )
        (root / ".github" / "workflows" / "harness-checkup.yml").write_text(
            "name: checkup\n",
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text(
            "# Project overview\nDemo.\n\n"
            "# Build & test\nRun `npm test`.\n\n"
            "# Conventions\nKeep changes small.\n\n"
            "# Testing requirements\nTest behavior changes.\n\n"
            "# Safety\nDo not commit secrets.\n\n"
            "# Commit & PR\nUse Conventional Commits.\n",
            encoding="utf-8",
        )
        (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (root / "package.json").write_text(
            json.dumps({"scripts": {"test": "echo ok"}, "packageManager": "npm@10.0.0"}),
            encoding="utf-8",
        )
        (root / "package-lock.json").write_text(
            json.dumps({"name": "fixture", "lockfileVersion": 3}),
            encoding="utf-8",
        )

    def test_initialize_list_and_call_scan(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n\nUse pnpm install.\n", encoding="utf-8")

            messages = [
                self._initialize(request_id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "harness_scan", "arguments": {"repo": str(repo), "json": True}},
                },
            ]
            responses = self._exchange(messages)

            by_id = {r.get("id"): r for r in responses if "id" in r}
            # notifications/initialized must NOT produce a response.
            self.assertEqual(len(responses), 3)

            init = by_id[1]["result"]
            self.assertEqual(init["protocolVersion"], LATEST_PROTOCOL)
            self.assertIn("tools", init["capabilities"])
            self.assertEqual(init["serverInfo"]["name"], "ai-harness-doctor")
            self.assertTrue(init["serverInfo"]["version"])

            tools = by_id[2]["result"]["tools"]
            names = {t["name"] for t in tools}
            self.assertEqual(
                names,
                {
                    "harness_scan",
                    "harness_drift",
                    "harness_validate",
                    "harness_plan",
                    "harness_stubs",
                    "harness_eval_generate",
                    "harness_explain",
                },
            )
            for tool in tools:
                self.assertEqual(tool["inputSchema"]["type"], "object")
                self.assertFalse(tool["inputSchema"]["additionalProperties"])
                self.assertIn("repo", tool["inputSchema"]["properties"])
                self.assertEqual(
                    tool["annotations"],
                    {
                        "readOnlyHint": True,
                        "destructiveHint": False,
                        "idempotentHint": True,
                        "openWorldHint": False,
                    },
                )
                schema = tool["outputSchema"]
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                self.assertEqual(
                    set(schema["required"]),
                    {"kind", "exitCode", "ok", "status"},
                )

            call = by_id[3]["result"]
            self.assertFalse(call.get("isError"))
            self.assertEqual(call["content"][0]["type"], "text")
            scan = json.loads(call["content"][0]["text"])
            self.assertTrue(any(f["path"] == "AGENTS.md" for f in scan["files"]))
            metadata = self._metadata(call)
            self.assertEqual(metadata["exitCode"], 0)
            self.assertEqual(metadata["status"], "findings")
            self.assertFalse(metadata["ok"])
            self.assertEqual(metadata["report"], scan)

    def test_protocol_negotiation_and_legacy_wire_shape(self):
        for requested, expected in (
            (LATEST_PROTOCOL, LATEST_PROTOCOL),
            (LEGACY_PROTOCOL, LEGACY_PROTOCOL),
            ("2099-01-01", LATEST_PROTOCOL),
        ):
            with self.subTest(requested=requested):
                responses = self._exchange([self._initialize(version=requested)])
                self.assertEqual(
                    responses[0]["result"]["protocolVersion"],
                    expected,
                )

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            responses = self._exchange(
                [
                    self._initialize(request_id=1, version=LEGACY_PROTOCOL),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "harness_drift",
                            "arguments": {"repo": str(repo)},
                        },
                    },
                ]
            )
            by_id = {response.get("id"): response for response in responses}
            for tool in by_id[2]["result"]["tools"]:
                self.assertNotIn("annotations", tool)
                self.assertNotIn("outputSchema", tool)
            legacy_result = by_id[3]["result"]
            self.assertNotIn("structuredContent", legacy_result)
            metadata = json.loads(legacy_result["content"][1]["text"])
            self.assertEqual(metadata["kind"], "ai-harness-doctor/tool-result")

            # Pre-initialize direct calls retain the historical 2024 wire shape.
            direct = self._call(
                "harness_drift",
                {"repo": str(repo)},
                protocol=None,
            )["result"]
            self.assertNotIn("structuredContent", direct)
            self.assertEqual(len(direct["content"]), 2)

    def test_malformed_and_duplicate_initialize_are_protocol_errors(self):
        malformed = [
            {},
            {
                "protocolVersion": LATEST_PROTOCOL,
                "capabilities": [],
                "clientInfo": {"name": "test", "version": "1"},
            },
            {
                "protocolVersion": LATEST_PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "test"},
            },
        ]
        for index, params in enumerate(malformed, 1):
            with self.subTest(params=params):
                response = self._exchange(
                    [
                        {
                            "jsonrpc": "2.0",
                            "id": index,
                            "method": "initialize",
                            "params": params,
                        }
                    ]
                )[0]
                self.assertEqual(response["error"]["code"], -32602)

        responses = self._exchange(
            [
                self._initialize(request_id=1),
                self._initialize(request_id=2),
            ]
        )
        by_id = {response.get("id"): response for response in responses}
        self.assertEqual(by_id[1]["result"]["protocolVersion"], LATEST_PROTOCOL)
        self.assertEqual(by_id[2]["error"]["code"], -32600)

    def test_call_drift_returns_text(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            messages = [
                self._initialize(request_id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "harness_drift", "arguments": {"repo": str(repo)}},
                },
            ]
            responses = self._exchange(messages)
            by_id = {r.get("id"): r for r in responses if "id" in r}
            call = by_id[2]["result"]
            text = call["content"][0]["text"]
            self.assertIn("Drift Guard Report", text)
            metadata = self._metadata(call)
            self.assertEqual(metadata, {
                "kind": "ai-harness-doctor/tool-result",
                "exitCode": 0,
                "ok": True,
                "status": "ok",
            })

    def test_all_seven_tools_return_exit_metadata_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            self._complete_repo(repo)
            calls = [
                ("harness_scan", {"repo": str(repo), "json": True}),
                ("harness_drift", {"repo": str(repo), "json": True}),
                ("harness_validate", {"repo": str(repo), "json": True}),
                ("harness_plan", {"repo": str(repo)}),
                ("harness_stubs", {"repo": str(repo)}),
                ("harness_eval_generate", {"repo": str(repo)}),
                ("harness_explain", {"repo": str(repo), "target": "src/future.py", "json": True}),
            ]
            for name, arguments in calls:
                with self.subTest(tool=name):
                    response = self._call(name, arguments)
                    result = response["result"]
                    self.assertFalse(result["isError"], result["content"][0]["text"])
                    metadata = self._metadata(result)
                    self.assertEqual(metadata["exitCode"], 0)
                    self.assertEqual(metadata["status"], "ok")
                    self.assertTrue(metadata["ok"])
                    if arguments.get("json"):
                        self.assertIn("report", metadata)
                    else:
                        self.assertNotIn("report", metadata)

    def test_all_seven_tools_reject_a_nonexistent_target_before_spawning(self):
        with tempfile.TemporaryDirectory() as td:
            missing = str(Path(td) / "does-not-exist")
            for name in (
                "harness_scan",
                "harness_drift",
                "harness_validate",
                "harness_plan",
                "harness_stubs",
                "harness_eval_generate",
                "harness_explain",
            ):
                with self.subTest(tool=name):
                    arguments = {"repo": missing}
                    if name == "harness_explain":
                        arguments["target"] = "src/future.py"
                    response = self._call(name, arguments)
                    result = response["result"]
                    self.assertTrue(result["isError"])
                    text = result["content"][0]["text"]
                    self.assertIn("not a directory", text)
                    self.assertNotIn("Traceback", text)
                    self.assertNotIn("scripts/", text)
                    metadata = self._metadata(result)
                    self.assertIsNone(metadata["exitCode"])
                    self.assertEqual(metadata["status"], "error")
                    self.assertFalse(metadata["ok"])

    def test_explain_requires_target_and_rejects_bad_arguments(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("Use npm.\n", encoding="utf-8")
            cases = (
                {"repo": str(repo)},
                {"repo": str(repo), "target": 42},
                {"repo": str(repo), "target": "src/x.py", "unknown": True},
            )
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    response = self._call("harness_explain", arguments)
                    self.assertEqual(response["error"]["code"], -32602)

    def test_declarative_arguments_preserve_old_argv_and_order_targets(self):
        script = (
            "const m=require('./bin/mcp-server.js');"
            "const byName=new Map(m.TOOLS.map(t=>[t.name,t]));"
            "console.log(JSON.stringify({"
            "scan:m.buildScriptArgs(byName.get('harness_scan'),{repo:'/repo',json:true}).argv.slice(1),"
            "eval:m.buildScriptArgs(byName.get('harness_eval_generate'),"
            "{repo:'/repo',target:'packages/api/x.py'}).argv.slice(1),"
            "explain:m.buildScriptArgs(byName.get('harness_explain'),"
            "{repo:'/repo',target:'src/x.py',json:true}).argv.slice(1)"
            "}));"
        )
        proc = subprocess.run(
            [NODE, "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        argv = json.loads(proc.stdout)
        self.assertEqual(argv["scan"], ["/repo", "--json"])
        self.assertEqual(
            argv["eval"],
            ["--generate", "/repo", "--target", "packages/api/x.py"],
        )
        self.assertEqual(argv["explain"], ["/repo", "src/x.py", "--json"])

    def test_explain_returns_same_nested_json_scope_as_cli(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("Use npm.\n", encoding="utf-8")
            nested = repo / "packages" / "api"
            nested.mkdir(parents=True)
            (nested / "AGENTS.md").write_text("Use pnpm.\n", encoding="utf-8")
            arguments = {
                "repo": str(repo),
                "target": "packages/api/src/future.py",
                "json": True,
            }
            response = self._call("harness_explain", arguments)
            result = response["result"]
            report = json.loads(result["content"][0]["text"])
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["effective_scope"], "packages/api")
            self.assertFalse(result["isError"])
            metadata = self._metadata(result)
            self.assertEqual(metadata["status"], "ok")
            self.assertEqual(metadata["report"], report)

            direct = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "explain.py"),
                    str(repo),
                    arguments["target"],
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(report, json.loads(direct.stdout))

            markdown = self._call(
                "harness_explain",
                {"repo": str(repo), "target": arguments["target"]},
            )["result"]
            self.assertIn("Canonical instruction chain", markdown["content"][0]["text"])
            self.assertFalse(markdown["isError"])

    def test_json_drift_findings_are_report_outcomes_not_tool_errors(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text(
                "# Project overview\nSee `missing/path`.\n",
                encoding="utf-8",
            )
            direct = subprocess.run(
                [sys.executable, str(DRIFT), str(repo), "--json"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(direct.returncode, 1, direct.stdout + direct.stderr)

            response = self._call(
                "harness_drift",
                {"repo": str(repo), "json": True},
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            report = json.loads(result["content"][0]["text"])
            self.assertFalse(report["ok"])
            self.assertTrue(any(f["check"] == "D2" for f in report["findings"]))
            metadata = self._metadata(result)
            self.assertEqual(metadata["exitCode"], direct.returncode)
            self.assertEqual(metadata["status"], "findings")
            self.assertFalse(metadata["ok"])
            self.assertEqual(metadata["report"], report)

    def test_json_validation_findings_are_report_outcomes_not_tool_errors(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\nDemo.\n", encoding="utf-8")
            direct = subprocess.run(
                [sys.executable, str(CANONICALIZE), "--validate", str(repo), "--json"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(direct.returncode, 1, direct.stdout + direct.stderr)

            response = self._call(
                "harness_validate",
                {"repo": str(repo), "json": True},
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            report = json.loads(result["content"][0]["text"])
            self.assertFalse(report["ok"])
            self.assertTrue(any(f["check"] == "SECTION" for f in report["findings"]))
            metadata = self._metadata(result)
            self.assertEqual(metadata["exitCode"], direct.returncode)
            self.assertEqual(metadata["status"], "findings")
            self.assertFalse(metadata["ok"])
            self.assertEqual(metadata["report"], report)

    def test_provisional_draft_validation_is_a_finding_not_tool_error(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            draft = subprocess.run(
                [
                    sys.executable,
                    str(CANONICALIZE),
                    "--draft",
                    str(repo),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(draft.returncode, 0, draft.stderr)
            (repo / "AGENTS.md").write_text(draft.stdout, encoding="utf-8")

            response = self._call(
                "harness_validate",
                {"repo": str(repo), "json": True},
            )
            result = response["result"]
            report = json.loads(result["content"][0]["text"])
            metadata = self._metadata(result)

            self.assertFalse(result["isError"])
            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    finding["check"] == "DRAFT_REVIEW"
                    for finding in report["findings"]
                )
            )
            self.assertEqual(metadata["exitCode"], 1)
            self.assertEqual(metadata["status"], "findings")
            self.assertFalse(metadata["ok"])
            self.assertEqual(metadata["report"], report)

    def test_exit_zero_notice_report_still_has_findings_status(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            self._complete_repo(repo)
            (repo / "AGENTS.md").write_text(
                (repo / "AGENTS.md").read_text(encoding="utf-8") + ("x" * 13000),
                encoding="utf-8",
            )
            response = self._call(
                "harness_drift",
                {"repo": str(repo), "json": True},
            )
            result = response["result"]
            self.assertFalse(result["isError"])
            report = json.loads(result["content"][0]["text"])
            self.assertTrue(report["ok"])
            self.assertTrue(any(f["level"] == "NOTICE" for f in report["findings"]))
            metadata = self._metadata(result)
            self.assertEqual(metadata["exitCode"], 0)
            self.assertEqual(metadata["status"], "findings")
            self.assertFalse(metadata["ok"])
            self.assertEqual(metadata["report"], report)

    def test_nonzero_markdown_is_conservatively_a_tool_error(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text(
                "# Project overview\nSee `missing/path`.\n",
                encoding="utf-8",
            )
            response = self._call("harness_drift", {"repo": str(repo)})
            result = response["result"]
            self.assertTrue(result["isError"])
            self.assertIn("D2", result["content"][0]["text"])
            metadata = self._metadata(result)
            self.assertEqual(metadata["exitCode"], 1)
            self.assertEqual(metadata["status"], "error")
            self.assertFalse(metadata["ok"])
            self.assertNotIn("report", metadata)

    def test_call_stubs_previews_without_writing(self):
        # DIRECTION-02: expose canonicalize.py --write-stubs over MCP, always as
        # a dry-run preview (never --apply), so it stays a read-only capability.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            (repo / "CLAUDE.md").write_text("Old CLAUDE instructions, not yet a stub.\n", encoding="utf-8")
            messages = [
                self._initialize(request_id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "harness_stubs", "arguments": {"repo": str(repo)}},
                },
            ]
            responses = self._exchange(messages)
            by_id = {r.get("id"): r for r in responses if "id" in r}
            call = by_id[2]["result"]
            self.assertFalse(call.get("isError"))
            text = call["content"][0]["text"]
            self.assertIn("CLAUDE.md", text)
            metadata = self._metadata(call)
            self.assertEqual(metadata["exitCode"], 0)
            self.assertTrue(metadata["ok"])
            # The file on disk must be untouched — this tool must never --apply.
            self.assertEqual(
                (repo / "CLAUDE.md").read_text(encoding="utf-8"), "Old CLAUDE instructions, not yet a stub.\n"
            )

    def test_call_eval_generate_returns_tasks_json(self):
        # DIRECTION-02: expose eval_run.py --generate over MCP as a read-only
        # bootstrap for the Phase 3 Efficacy harness (no file written, no agent
        # or LLM calls made).
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Build & test\nRun `npm test`.\n", encoding="utf-8")
            (repo / "package.json").write_text('{"scripts": {"test": "echo ok"}}', encoding="utf-8")
            messages = [
                self._initialize(request_id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "harness_eval_generate", "arguments": {"repo": str(repo)}},
                },
            ]
            responses = self._exchange(messages)
            by_id = {r.get("id"): r for r in responses if "id" in r}
            call = by_id[2]["result"]
            self.assertFalse(call.get("isError"))
            tasks = json.loads(call["content"][0]["text"])
            self.assertTrue(tasks)
            self.assertTrue(all("prompt" in t and "check" in t for t in tasks))
            metadata = self._metadata(call)
            self.assertEqual(metadata["exitCode"], 0)
            self.assertTrue(metadata["ok"])
            # Never writes a file — no -o/--output flag is ever passed over MCP.
            self.assertEqual({p.name for p in repo.iterdir()}, {"AGENTS.md", "package.json"})

    def test_call_eval_generate_target_returns_nested_scope_tasks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("Use Conventional Commits.\n", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            package = repo / "packages" / "api"
            package.mkdir(parents=True)
            (package / "AGENTS.md").write_text("Use package commands.\n", encoding="utf-8")
            (package / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"test:api": "vitest run"},
                        "devDependencies": {"vitest": "^3"},
                    }
                ),
                encoding="utf-8",
            )
            target = "packages/api/src/future.py"
            response = self._call(
                "harness_eval_generate",
                {"repo": str(repo), "target": target},
            )
            result = response["result"]
            tasks = json.loads(result["content"][0]["text"])

            self.assertFalse(result["isError"])
            self.assertTrue(tasks)
            self.assertTrue(all(task["scope"] == "packages/api" for task in tasks))
            self.assertTrue(all(task["target"] == target for task in tasks))
            self.assertIn(
                "scope:packages%2Fapi:test:api",
                {task["id"] for task in tasks},
            )
            self.assertEqual(self._metadata(result)["status"], "ok")

    def test_eval_generate_target_rejects_wrong_types_and_unknown_properties(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("Use npm.\n", encoding="utf-8")
            for arguments in (
                {"repo": str(repo), "target": 42},
                {"repo": str(repo), "target": "src/x.py", "unknown": True},
            ):
                with self.subTest(arguments=arguments):
                    response = self._call("harness_eval_generate", arguments)
                    self.assertEqual(response["error"]["code"], -32602)

    def test_unknown_method_and_tool_produce_errors(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "does/not/exist"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "no_such_tool"}},
        ]
        responses = self._exchange(messages)
        by_id = {r.get("id"): r for r in responses if "id" in r}
        self.assertEqual(by_id[1]["error"]["code"], -32601)
        self.assertEqual(by_id[2]["error"]["code"], -32602)

    def test_invalid_tool_arguments_return_invalid_params_without_spawning(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            marker = base / "python-was-probed"
            fake_python = base / "fake-python"
            fake_python.write_text(
                f"#!/bin/sh\nprintf invoked > {marker!s}\nexit 1\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = dict(os.environ)
            env["AI_HARNESS_DOCTOR_PYTHON"] = str(fake_python)
            messages = [
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "harness_scan", "arguments": "not-an-object"},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "harness_scan", "arguments": {"repo": 42}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "harness_drift", "arguments": {"strict": "yes"}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "harness_scan", "arguments": {"typo": True}},
                },
            ]
            responses = self._exchange(messages, env=env)
            self.assertEqual(len(responses), 4)
            for response in responses:
                self.assertEqual(response["error"]["code"], -32602)
            self.assertIn("must be an object", responses[0]["error"]["message"])
            self.assertIn("must be string", responses[1]["error"]["message"])
            self.assertIn("must be boolean", responses[2]["error"]["message"])
            self.assertIn("Unknown argument", responses[3]["error"]["message"])
            self.assertFalse(marker.exists(), "invalid arguments must fail before resolving/spawning Python")

    def test_missing_python_returns_machine_visible_tool_error(self):
        env = dict(os.environ)
        env.pop("AI_HARNESS_DOCTOR_PYTHON", None)
        env.pop("PYTHON", None)
        with tempfile.TemporaryDirectory() as td:
            env["PATH"] = td
            response = self._call("harness_scan", {}, env=env)
        result = response["result"]
        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("Python is required", text)
        self.assertNotIn("Traceback", text)
        metadata = self._metadata(result)
        self.assertIsNone(metadata["exitCode"])
        self.assertEqual(metadata["status"], "error")
        self.assertFalse(metadata["ok"])

    def test_malformed_json_report_is_a_tool_error_even_with_exit_zero(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = base / "repo"
            repo.mkdir()
            fake_python = base / "fake-python"
            fake_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then\n"
                "  printf '3.11.9'\n"
                "  exit 0\n"
                "fi\n"
                "printf 'not-json'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = dict(os.environ)
            env["AI_HARNESS_DOCTOR_PYTHON"] = str(fake_python)

            response = self._call(
                "harness_drift",
                {"repo": str(repo), "json": True},
                env=env,
            )
            result = response["result"]
            self.assertTrue(result["isError"])
            self.assertEqual(result["content"][0]["text"], "not-json")
            metadata = self._metadata(result)
            self.assertEqual(metadata["exitCode"], 0)
            self.assertEqual(metadata["status"], "error")
            self.assertFalse(metadata["ok"])
            self.assertNotIn("report", metadata)

    def test_tool_call_times_out_cleanly(self):
        # With a 1ms budget, spawning the Python interpreter always exceeds the
        # timeout, so the tool must return a clean JSON-RPC tool error (isError)
        # rather than hanging, crashing, or leaking a traceback.
        env = dict(os.environ)
        env["AHD_TOOL_TIMEOUT_MS"] = "1"
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            messages = [
                self._initialize(request_id=1),
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "harness_scan", "arguments": {"repo": str(repo)}},
                },
            ]
            responses = self._exchange(messages, env=env)
            by_id = {r.get("id"): r for r in responses if "id" in r}
            call = by_id[2]["result"]
            self.assertTrue(call.get("isError"))
            text = call["content"][0]["text"]
            self.assertIn("timed out", text)
            # No raw traceback / internal path leakage.
            self.assertNotIn("Traceback", text)
            self.assertNotIn("scripts/scan.py", text)
            metadata = self._metadata(call)
            self.assertIsNone(metadata["exitCode"])
            self.assertEqual(metadata["status"], "error")
            self.assertFalse(metadata["ok"])


if __name__ == "__main__":
    unittest.main()
