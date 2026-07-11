#!/usr/bin/env node
'use strict';

// Minimal MCP (Model Context Protocol) stdio server for ai-harness-doctor.
//
// Transport: newline-delimited JSON. Each JSON-RPC 2.0 message is a single line
// terminated by "\n" on both stdin (requests) and stdout (responses). The server
// exposes the core Python capabilities (scan / drift / validate / plan) as MCP tools.

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const childProcess = require('child_process');
const runtime = require('./runtime.js');

const PACKAGE_ROOT = path.resolve(__dirname, '..');
const PACKAGE_JSON = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
const PACKAGE_VERSION = PACKAGE_JSON.version;
const SERVER_NAME = 'ai-harness-doctor';
const PROTOCOL_VERSION = '2024-11-05';

// JSON-RPC 2.0 error codes.
const PARSE_ERROR = -32700;
const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const INVALID_PARAMS = -32602;
const INTERNAL_ERROR = -32603;

// Tool definitions. Each maps to a Python script under scripts/. `script[0]` is the
// file name; `script.slice(1)` are fixed leading args (e.g. the canonicalize subcommand).
// `booleans` maps an input-schema boolean property to the CLI flag it toggles.
const TOOLS = [
  {
    name: 'harness_scan',
    description: 'Scan a repository for AI harness config files (AGENTS.md, CLAUDE.md, .cursorrules, ...) and report inventory, size warnings, overlap and conflict candidates (Phase 0 — Checkup).',
    script: ['scan.py'],
    booleans: { json: '--json' },
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
        json: { type: 'boolean', description: 'Emit machine-readable JSON instead of markdown.', default: false },
      },
    },
  },
  {
    name: 'harness_drift',
    description: 'Run the read-only drift guard over a canonical AGENTS.md and its stubs (Phase 2 — Follow-up).',
    script: ['check_drift.py'],
    booleans: { json: '--json', strict: '--strict' },
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
        json: { type: 'boolean', description: 'Emit machine-readable JSON instead of markdown.', default: false },
        strict: { type: 'boolean', description: 'Treat NOTICE-level findings as errors.', default: false },
      },
    },
  },
  {
    name: 'harness_validate',
    description: 'Validate the canonicalization state of AGENTS.md and tool stubs (Phase 1 — Treat validation).',
    script: ['canonicalize.py', '--validate'],
    booleans: { json: '--json' },
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
        json: { type: 'boolean', description: 'Emit machine-readable JSON instead of text.', default: false },
      },
    },
  },
  {
    name: 'harness_plan',
    description: 'Generate a merge-plan skeleton for consolidating scattered configs into AGENTS.md (Phase 1 — Treat planning).',
    script: ['canonicalize.py', '--plan'],
    booleans: {},
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
      },
    },
  },
  {
    name: 'harness_stubs',
    description: 'Preview downgrading existing tool config files (CLAUDE.md, .cursorrules, ...) to minimal AGENTS.md pointer stubs (Phase 1 — Treat). Read-only: always a dry-run diff preview, never writes to the repository. Requires AGENTS.md to already exist.',
    script: ['canonicalize.py', '--write-stubs'],
    booleans: {},
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
      },
    },
  },
  {
    name: 'harness_eval_generate',
    description: 'Auto-generate a benchmark task set from repository facts (AGENTS.md content plus detected build/test commands) for the Phase 3 — Efficacy eval harness. Read-only: prints the generated tasks as JSON without writing a file or running any agent/LLM calls.',
    script: ['eval_run.py', '--generate'],
    booleans: {},
    inputSchema: {
      type: 'object',
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
      },
    },
  },
];

const TOOL_BY_NAME = new Map(TOOLS.map((tool) => [tool.name, tool]));

// Hard cap on how long a single Python tool subprocess may run. Without this,
// a script that blocks (e.g. drift/scan walking a huge or symlink-looped tree)
// would wedge the stdio server with no way to cancel. Overridable via env for
// tests and slow environments.
function toolTimeoutMs() {
  const raw = Number(process.env.AHD_TOOL_TIMEOUT_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : 60000;
}

// Keep raw Python stderr/tracebacks from leaking verbatim to the MCP client;
// trim to a short, single-message summary (info-leak hardening).
function summarizeStderr(stderr) {
  const cleaned = String(stderr || '').trim();
  if (!cleaned) return '';
  const lines = cleaned.split(/\r?\n/).filter((l) => l.trim().length);
  const last = lines.length ? lines[lines.length - 1] : cleaned;
  return last.length > 300 ? `${last.slice(0, 300)}…` : last;
}

function resolvePython() {
  // Delegate to the shared runtime resolver so the MCP server and the CLI agree
  // on discovery order and the "must be Python 3" check. Returns null on miss.
  const found = runtime.findPython();
  return found.ok ? found.command : null;
}

function writeMessage(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function sendResult(id, result) {
  writeMessage({ jsonrpc: '2.0', id, result });
}

function sendError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  writeMessage({ jsonrpc: '2.0', id, error });
}

// Build the argv for the Python interpreter from a tool definition + arguments.
function buildScriptArgs(tool, argsObj) {
  const scriptPath = path.join(PACKAGE_ROOT, 'scripts', tool.script[0]);
  const leading = tool.script.slice(1);
  const repo = typeof argsObj.repo === 'string' && argsObj.repo.length ? argsObj.repo : '.';
  const flags = [];
  for (const [prop, flag] of Object.entries(tool.booleans)) {
    if (argsObj[prop] === true) flags.push(flag);
  }
  return { scriptPath, argv: [scriptPath, ...leading, repo, ...flags] };
}

function callTool(tool, argsObj) {
  const python = resolvePython();
  if (!python) {
    return { isError: true, text: 'Python is required (python3 or python) but was not found on PATH.' };
  }
  const { scriptPath, argv } = buildScriptArgs(tool, argsObj || {});
  if (!fs.existsSync(scriptPath)) {
    return { isError: true, text: `Script not found: ${scriptPath}` };
  }
  const timeoutMs = toolTimeoutMs();
  const result = childProcess.spawnSync(python, argv, { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, timeout: timeoutMs });
  if (result.error) {
    if (result.error.code === 'ETIMEDOUT') {
      // Return a clean tool error instead of hanging/throwing. Do not leak argv
      // or internal paths — just report the timeout budget.
      return { isError: true, text: `Tool ${tool.name} timed out after ${timeoutMs}ms and was terminated.` };
    }
    return { isError: true, text: `Failed to run ${tool.name}: ${result.error.message}` };
  }
  const stdout = result.stdout || '';
  const stderr = result.stderr || '';
  // Some tools (e.g. drift) return a non-zero exit code to signal findings; that is not a
  // transport error. Surface the output as tool content and let the caller interpret it.
  let text = stdout;
  if (!text && stderr) text = summarizeStderr(stderr);
  return { isError: false, text, exitCode: result.status };
}

function handleToolsCall(id, params) {
  const name = params && params.name;
  const tool = name ? TOOL_BY_NAME.get(name) : undefined;
  if (!tool) {
    sendError(id, INVALID_PARAMS, `Unknown tool: ${name}`);
    return;
  }
  const outcome = callTool(tool, (params && params.arguments) || {});
  sendResult(id, {
    content: [{ type: 'text', text: outcome.text }],
    isError: Boolean(outcome.isError),
  });
}

function handleRequest(message) {
  const { id, method, params } = message;
  const isNotification = id === undefined || id === null;

  if (method === 'notifications/initialized' || method === 'initialized') {
    // Notification: no response.
    return;
  }

  if (method === 'initialize') {
    sendResult(id, {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: { name: SERVER_NAME, version: PACKAGE_VERSION },
    });
    return;
  }

  if (method === 'ping') {
    sendResult(id, {});
    return;
  }

  if (method === 'tools/list') {
    const tools = TOOLS.map((tool) => ({
      name: tool.name,
      description: tool.description,
      inputSchema: tool.inputSchema,
    }));
    sendResult(id, { tools });
    return;
  }

  if (method === 'tools/call') {
    handleToolsCall(id, params);
    return;
  }

  if (isNotification) {
    // Unknown notification: ignore silently per JSON-RPC.
    return;
  }
  sendError(id, METHOD_NOT_FOUND, `Method not found: ${method}`);
}

function main() {
  const rl = readline.createInterface({ input: process.stdin, terminal: false });
  rl.on('line', (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let message;
    try {
      message = JSON.parse(trimmed);
    } catch (_) {
      sendError(null, PARSE_ERROR, 'Parse error: invalid JSON');
      return;
    }
    if (!message || typeof message !== 'object' || message.jsonrpc !== '2.0' || typeof message.method !== 'string') {
      sendError(message && message.id !== undefined ? message.id : null, INVALID_REQUEST, 'Invalid Request');
      return;
    }
    try {
      handleRequest(message);
    } catch (error) {
      sendError(message.id !== undefined ? message.id : null, INTERNAL_ERROR, `Internal error: ${error && error.message}`);
    }
  });
  rl.on('close', () => process.exit(0));
}

if (require.main === module) {
  main();
}

module.exports = { TOOLS, buildScriptArgs, resolvePython };
