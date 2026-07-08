import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "bin" / "mcp-server.js"


class McpServerTests(unittest.TestCase):
    def _exchange(self, messages, cwd=None, env=None):
        """Send newline-delimited JSON messages to the MCP server and parse responses."""
        payload = "".join(json.dumps(m) + "\n" for m in messages)
        proc = subprocess.run(
            ["node", str(SERVER)],
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

    def test_initialize_list_and_call_scan(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n\nUse pnpm install.\n", encoding="utf-8")

            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "harness_scan", "arguments": {"repo": str(repo), "json": True}}},
            ]
            responses = self._exchange(messages)

            by_id = {r.get("id"): r for r in responses if "id" in r}
            # notifications/initialized must NOT produce a response.
            self.assertEqual(len(responses), 3)

            init = by_id[1]["result"]
            self.assertEqual(init["protocolVersion"], "2024-11-05")
            self.assertIn("tools", init["capabilities"])
            self.assertEqual(init["serverInfo"]["name"], "ai-harness-doctor")
            self.assertTrue(init["serverInfo"]["version"])

            tools = by_id[2]["result"]["tools"]
            names = {t["name"] for t in tools}
            self.assertEqual(names, {"harness_scan", "harness_drift", "harness_validate", "harness_plan"})
            for tool in tools:
                self.assertEqual(tool["inputSchema"]["type"], "object")
                self.assertIn("repo", tool["inputSchema"]["properties"])

            call = by_id[3]["result"]
            self.assertFalse(call.get("isError"))
            self.assertEqual(call["content"][0]["type"], "text")
            scan = json.loads(call["content"][0]["text"])
            self.assertTrue(any(f["path"] == "AGENTS.md" for f in scan["files"]))

    def test_call_drift_returns_text(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Project overview\n", encoding="utf-8")
            messages = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "harness_drift", "arguments": {"repo": str(repo)}}},
            ]
            responses = self._exchange(messages)
            by_id = {r.get("id"): r for r in responses if "id" in r}
            text = by_id[2]["result"]["content"][0]["text"]
            self.assertIn("Drift Guard Report", text)

    def test_unknown_method_and_tool_produce_errors(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "does/not/exist"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "no_such_tool"}},
        ]
        responses = self._exchange(messages)
        by_id = {r.get("id"): r for r in responses if "id" in r}
        self.assertEqual(by_id[1]["error"]["code"], -32601)
        self.assertEqual(by_id[2]["error"]["code"], -32602)


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
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "harness_scan", "arguments": {"repo": str(repo)}}},
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


if __name__ == "__main__":
    unittest.main()
