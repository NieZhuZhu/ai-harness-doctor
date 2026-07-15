#!/usr/bin/env node
'use strict';

// Minimal MCP (Model Context Protocol) stdio server for ai-harness-doctor.
//
// Transport: newline-delimited JSON. Each JSON-RPC 2.0 message is a single line
// terminated by "\n" on both stdin (requests) and stdout (responses). The server
// exposes seven read-only Python capabilities as MCP tools.

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const childProcess = require('child_process');
const runtime = require('./runtime.js');

const PACKAGE_ROOT = path.resolve(__dirname, '..');
const PACKAGE_JSON = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
const PACKAGE_VERSION = PACKAGE_JSON.version;
const SERVER_NAME = 'ai-harness-doctor';
const SUPPORTED_PROTOCOL_VERSIONS = Object.freeze(['2025-11-25', '2024-11-05']);
const LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0];
const LEGACY_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[1];

// JSON-RPC 2.0 error codes.
const PARSE_ERROR = -32700;
const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const INVALID_PARAMS = -32602;
const INTERNAL_ERROR = -32603;

// Tool definitions. Each maps to a Python script under scripts/. `script[0]` is the
// file name; `script.slice(1)` are fixed leading args (e.g. the canonicalize subcommand).
// `booleans` maps an input-schema boolean property to the CLI flag it toggles.
// `resultPolicy` declares which subprocess codes are valid reports and, for
// JSON-capable tools, the minimal report shape used to distinguish findings
// from operational failures. Every MCP tool is deliberately read-only.
const TOOLS = [
  {
    name: 'harness_scan',
    description: 'Scan a repository for AI harness config files (AGENTS.md, CLAUDE.md, .cursorrules, ...) and report inventory, size warnings, overlap and conflict candidates (Phase 0 — Checkup).',
    script: ['scan.py'],
    booleans: { json: '--json' },
    readOnly: true,
    resultPolicy: { reportExitCodes: [0], jsonShape: 'scan', requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
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
    readOnly: true,
    resultPolicy: { reportExitCodes: [0, 1], jsonShape: 'drift', requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
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
    readOnly: true,
    resultPolicy: { reportExitCodes: [0, 1], jsonShape: 'validate', requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
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
    readOnly: true,
    resultPolicy: { reportExitCodes: [0], requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
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
    readOnly: true,
    resultPolicy: { reportExitCodes: [0], requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
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
    readOnly: true,
    resultPolicy: { reportExitCodes: [0], requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
      },
    },
  },
  {
    name: 'harness_explain',
    description: 'Explain the canonical AGENTS.md inheritance chain, diagnostically associated configs, scoped overrides, and conflicts for one target path. Read-only; does not merge or modify instructions.',
    script: ['explain.py'],
    positionals: ['repo', 'target'],
    booleans: { json: '--json' },
    readOnly: true,
    resultPolicy: { reportExitCodes: [0], jsonShape: 'explain', requireRepoDirectory: true },
    inputSchema: {
      type: 'object',
      additionalProperties: false,
      required: ['target'],
      properties: {
        repo: { type: 'string', description: 'Target repository root.', default: '.' },
        target: { type: 'string', description: 'Contained file, directory, or future path to explain.' },
        json: { type: 'boolean', description: 'Emit machine-readable JSON instead of markdown.', default: false },
      },
    },
  },
];

const TOOL_BY_NAME = new Map(TOOLS.map((tool) => [tool.name, tool]));
const TOOL_RESULT_OUTPUT_SCHEMA = Object.freeze({
  type: 'object',
  additionalProperties: false,
  properties: {
    kind: { type: 'string', const: 'ai-harness-doctor/tool-result' },
    exitCode: { type: ['integer', 'null'] },
    ok: { type: 'boolean' },
    status: { type: 'string', enum: ['ok', 'findings', 'error'] },
    // Tool-specific JSON reports are intentionally heterogeneous; an empty
    // schema accepts any JSON value while the envelope remains closed/typed.
    report: {},
  },
  required: ['kind', 'exitCode', 'ok', 'status'],
});

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

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function validateToolArguments(tool, value) {
  if (value === undefined) value = {};
  if (!isPlainObject(value)) {
    return { ok: false, message: `Arguments for ${tool.name} must be an object.` };
  }
  const properties = tool.inputSchema.properties || {};
  for (const key of tool.inputSchema.required || []) {
    if (!Object.prototype.hasOwnProperty.call(value, key)
        || (typeof value[key] === 'string' && !value[key])) {
      return { ok: false, message: `Missing required argument for ${tool.name}: ${key}` };
    }
  }
  for (const key of Object.keys(value)) {
    if (!Object.prototype.hasOwnProperty.call(properties, key)) {
      return { ok: false, message: `Unknown argument for ${tool.name}: ${key}` };
    }
    const expected = properties[key].type;
    if (expected && typeof value[key] !== expected) {
      return { ok: false, message: `Argument ${key} for ${tool.name} must be ${expected}.` };
    }
  }
  return { ok: true, value };
}

// Convert declarative tool positionals + booleans into the Python argv.
// Existing tools default to the historical single `repo` positional; explain
// adds `target` without a command-specific dispatcher branch.
// Build the argv for the Python interpreter from a tool definition + arguments.
function buildScriptArgs(tool, argsObj) {
  const scriptPath = path.join(PACKAGE_ROOT, 'scripts', tool.script[0]);
  const leading = tool.script.slice(1);
  const positionals = (tool.positionals || ['repo']).map((prop) => {
    if (prop === 'repo') {
      return typeof argsObj.repo === 'string' && argsObj.repo.length ? argsObj.repo : '.';
    }
    return argsObj[prop];
  });
  const flags = [];
  for (const [prop, flag] of Object.entries(tool.booleans)) {
    if (argsObj[prop] === true) flags.push(flag);
  }
  return { scriptPath, argv: [scriptPath, ...leading, ...positionals, ...flags] };
}

function explicitJsonReport(tool, argsObj, stdout) {
  if (!tool.resultPolicy.jsonShape || argsObj.json !== true) return { requested: false };
  try {
    return { requested: true, parsed: JSON.parse(stdout) };
  } catch (_) {
    return { requested: true };
  }
}

function hasValidJsonShape(shape, report) {
  if (!isPlainObject(report) || Object.prototype.hasOwnProperty.call(report, 'error')) return false;
  if (shape === 'scan') return Array.isArray(report.files);
  if (shape === 'drift') {
    return typeof report.ok === 'boolean' && Array.isArray(report.findings)
      && typeof report.score === 'number';
  }
  if (shape === 'validate') {
    return typeof report.ok === 'boolean' && Array.isArray(report.findings);
  }
  if (shape === 'explain') {
    return report.schema_version === 1
      && isPlainObject(report.target)
      && Array.isArray(report.canonical_chain)
      && Array.isArray(report.diagnostic_sources)
      && Array.isArray(report.scope_overrides)
      && Array.isArray(report.conflicts);
  }
  return false;
}

function reportHasFindings(shape, report) {
  if (shape === 'scan') {
    const reports = [report, ...(report.packages || []).map((item) => item.report || {})];
    return reports.some((item) => (
      (item.warnings || []).length
      || (item.security || []).length
      || (item.gaps || []).length
      || (item.semantic && item.semantic.findings || []).length
      || (item.conflicts || []).length
      || (item.custom || []).length
    ));
  }
  if (shape === 'drift' || shape === 'validate') return report.findings.length > 0;
  return false;
}

function classifySubprocess(tool, argsObj, result) {
  const stdout = result.stdout || '';
  const stderr = result.stderr || '';
  const exitCode = Number.isInteger(result.status) ? result.status : null;
  const json = explicitJsonReport(tool, argsObj, stdout);
  const validJsonReport = json.requested
    && hasValidJsonShape(tool.resultPolicy.jsonShape, json.parsed);
  const allowedCode = exitCode !== null
    && tool.resultPolicy.reportExitCodes.includes(exitCode);

  let status = 'error';
  if (exitCode === 0 && (!json.requested || validJsonReport)) {
    status = validJsonReport && reportHasFindings(tool.resultPolicy.jsonShape, json.parsed)
      ? 'findings'
      : 'ok';
  } else if (exitCode !== 0 && allowedCode && validJsonReport) {
    // A non-zero code is a valid finding-bearing report only when the caller
    // explicitly requested JSON and the output matches this tool's report
    // contract. Markdown is deliberately not scraped to guess success.
    status = 'findings';
  }

  let text = stdout;
  if (!text && stderr) text = summarizeStderr(stderr);
  const outcome = {
    isError: status === 'error',
    text,
    exitCode,
    status,
  };
  if (json.requested && json.parsed !== undefined) outcome.report = json.parsed;
  return outcome;
}

function errorOutcome(text) {
  return { isError: true, text, exitCode: null, status: 'error' };
}

function resultMetadata(outcome) {
  const metadata = {
    kind: 'ai-harness-doctor/tool-result',
    exitCode: outcome.exitCode,
    ok: outcome.status === 'ok',
    status: outcome.status,
  };
  if (outcome.report !== undefined) metadata.report = outcome.report;
  return metadata;
}

function negotiateProtocolVersion(requested) {
  return SUPPORTED_PROTOCOL_VERSIONS.includes(requested)
    ? requested
    : LATEST_PROTOCOL_VERSION;
}

function validateInitializeParams(params) {
  if (!isPlainObject(params)) return 'initialize params must be an object.';
  if (typeof params.protocolVersion !== 'string' || !params.protocolVersion) {
    return 'initialize params.protocolVersion must be a non-empty string.';
  }
  if (!isPlainObject(params.capabilities)) {
    return 'initialize params.capabilities must be an object.';
  }
  if (!isPlainObject(params.clientInfo)
      || typeof params.clientInfo.name !== 'string'
      || typeof params.clientInfo.version !== 'string') {
    return 'initialize params.clientInfo must contain string name and version.';
  }
  return null;
}

function toolForProtocol(tool, protocolVersion) {
  const wire = {
    name: tool.name,
    description: tool.description,
    inputSchema: tool.inputSchema,
  };
  if (protocolVersion === LATEST_PROTOCOL_VERSION) {
    wire.annotations = {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    };
    wire.outputSchema = TOOL_RESULT_OUTPUT_SCHEMA;
  }
  return wire;
}

function resultForProtocol(outcome, protocolVersion) {
  const metadata = resultMetadata(outcome);
  const result = {
    content: [
      { type: 'text', text: outcome.text },
      { type: 'text', text: JSON.stringify(metadata) },
    ],
    isError: Boolean(outcome.isError),
  };
  if (protocolVersion === LATEST_PROTOCOL_VERSION) {
    result.structuredContent = metadata;
  }
  return result;
}

function callTool(tool, argsObj) {
  const { scriptPath, argv } = buildScriptArgs(tool, argsObj || {});
  if (tool.resultPolicy.requireRepoDirectory) {
    const repo = typeof argsObj.repo === 'string' && argsObj.repo.length ? argsObj.repo : '.';
    try {
      if (!fs.statSync(path.resolve(repo)).isDirectory()) {
        return errorOutcome(`Target repository is not a directory: ${repo}`);
      }
    } catch (_) {
      return errorOutcome(`Target repository is not a directory: ${repo}`);
    }
  }
  const python = resolvePython();
  if (!python) {
    return errorOutcome('Python is required (python3 or python) but was not found on PATH.');
  }
  if (!fs.existsSync(scriptPath)) {
    return errorOutcome(`The packaged script for ${tool.name} was not found.`);
  }
  const timeoutMs = toolTimeoutMs();
  const result = childProcess.spawnSync(python, argv, { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, timeout: timeoutMs });
  if (result.error) {
    if (result.error.code === 'ETIMEDOUT') {
      // Return a clean tool error instead of hanging/throwing. Do not leak argv
      // or internal paths — just report the timeout budget.
      return errorOutcome(`Tool ${tool.name} timed out after ${timeoutMs}ms and was terminated.`);
    }
    const code = result.error.code ? ` (${result.error.code})` : '';
    return errorOutcome(`Failed to run ${tool.name}${code}.`);
  }
  return classifySubprocess(tool, argsObj, result);
}

function handleToolsCall(id, params, session) {
  if (!isPlainObject(params)) {
    sendError(id, INVALID_PARAMS, 'tools/call params must be an object.');
    return;
  }
  const name = params.name;
  const tool = name ? TOOL_BY_NAME.get(name) : undefined;
  if (!tool) {
    sendError(id, INVALID_PARAMS, `Unknown tool: ${name}`);
    return;
  }
  const validation = validateToolArguments(tool, params.arguments);
  if (!validation.ok) {
    sendError(id, INVALID_PARAMS, validation.message);
    return;
  }
  const outcome = callTool(tool, validation.value);
  sendResult(id, resultForProtocol(outcome, session.protocolVersion));
}

function handleRequest(message, session) {
  const { id, method, params } = message;
  const isNotification = id === undefined || id === null;

  if (method === 'notifications/initialized' || method === 'initialized') {
    // Notification: no response.
    return;
  }

  if (method === 'initialize') {
    if (session.initialized) {
      sendError(id, INVALID_REQUEST, 'Server is already initialized.');
      return;
    }
    const problem = validateInitializeParams(params);
    if (problem) {
      sendError(id, INVALID_PARAMS, problem);
      return;
    }
    session.protocolVersion = negotiateProtocolVersion(params.protocolVersion);
    session.initialized = true;
    sendResult(id, {
      protocolVersion: session.protocolVersion,
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
    const tools = TOOLS.map((tool) => toolForProtocol(tool, session.protocolVersion));
    sendResult(id, { tools });
    return;
  }

  if (method === 'tools/call') {
    handleToolsCall(id, params, session);
    return;
  }

  if (isNotification) {
    // Unknown notification: ignore silently per JSON-RPC.
    return;
  }
  sendError(id, METHOD_NOT_FOUND, `Method not found: ${method}`);
}

function main() {
  // Direct calls made by older/lightweight clients before initialize retain the
  // original 2024 wire shape. A valid initialize request selects a version for
  // the remainder of this stdio connection.
  const session = {
    protocolVersion: LEGACY_PROTOCOL_VERSION,
    initialized: false,
  };
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
      handleRequest(message, session);
    } catch (error) {
      sendError(message.id !== undefined ? message.id : null, INTERNAL_ERROR, `Internal error: ${error && error.message}`);
    }
  });
  rl.on('close', () => process.exit(0));
}

if (require.main === module) {
  main();
}

module.exports = {
  LATEST_PROTOCOL_VERSION,
  LEGACY_PROTOCOL_VERSION,
  SUPPORTED_PROTOCOL_VERSIONS,
  TOOLS,
  TOOL_RESULT_OUTPUT_SCHEMA,
  buildScriptArgs,
  classifySubprocess,
  negotiateProtocolVersion,
  resolvePython,
  resultForProtocol,
  toolForProtocol,
  validateInitializeParams,
  validateToolArguments,
};
