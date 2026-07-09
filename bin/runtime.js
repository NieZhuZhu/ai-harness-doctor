'use strict';

// Single source of truth for locating the Python 3 runtime that backs the
// Python engines under scripts/. Both the CLI dispatcher (bin/cli.js) and the
// MCP server (bin/mcp-server.js) resolve Python through this module so the
// discovery order, the "must be Python 3" check, and the remediation message
// stay identical across every entrypoint.

const childProcess = require('child_process');

// Environment variables (in priority order) that pin a specific interpreter.
// A user can set AI_HARNESS_DOCTOR_PYTHON=/path/to/python3 to override discovery.
const PYTHON_ENV_VARS = ['AI_HARNESS_DOCTOR_PYTHON', 'PYTHON'];

// Prints "<major>.<minor>.<micro>" on both Python 2 and Python 3, so we can
// probe the interpreter and reject Python 2 rather than failing later with a
// confusing syntax error from inside a script.
const PY_VERSION_SNIPPET = 'import sys; sys.stdout.write("%d.%d.%d" % sys.version_info[:3])';

function defaultSpawn(command, args) {
  return childProcess.spawnSync(command, args, { encoding: 'utf8' });
}

// Ordered, de-duplicated list of interpreter names/paths to probe.
function pythonCandidates(env = process.env) {
  const seen = new Set();
  const candidates = [];
  const add = (value) => {
    if (value && !seen.has(value)) {
      seen.add(value);
      candidates.push(value);
    }
  };
  for (const name of PYTHON_ENV_VARS) add(env[name]);
  add('python3');
  add('python');
  return candidates;
}

// Probe a single candidate. Returns { command, version } when it is a usable
// Python 3, or null otherwise (missing, not executable, or Python 2).
function probePython(candidate, spawn = defaultSpawn) {
  let result;
  try {
    result = spawn(candidate, ['-c', PY_VERSION_SNIPPET]);
  } catch (_) {
    return null;
  }
  if (!result || result.error || result.status !== 0) return null;
  const version = String(result.stdout || '').trim();
  const major = Number.parseInt(version.split('.')[0], 10);
  if (!Number.isInteger(major) || major < 3) return null;
  return { command: candidate, version };
}

// Resolve a usable Python 3 interpreter.
//   { ok: true, command, version }  on success
//   { ok: false, tried: [...] }     when nothing usable was found
function findPython(env = process.env, spawn = defaultSpawn) {
  const tried = [];
  for (const candidate of pythonCandidates(env)) {
    tried.push(candidate);
    const info = probePython(candidate, spawn);
    if (info) return { ok: true, command: info.command, version: info.version };
  }
  return { ok: false, tried };
}

// Actionable, single-message error (no raw stack traces) for a missing runtime.
function pythonMissingMessage(tried) {
  const list = tried && tried.length ? tried : ['python3', 'python'];
  return [
    'Python 3 is required but was not found.',
    `Tried: ${list.join(', ')}.`,
    'Fix: install Python 3 from https://www.python.org/downloads/ and ensure it is on your PATH,',
    'or point ai-harness-doctor at a specific interpreter with AI_HARNESS_DOCTOR_PYTHON=/path/to/python3.',
  ].join('\n');
}

module.exports = {
  PYTHON_ENV_VARS,
  PY_VERSION_SNIPPET,
  pythonCandidates,
  probePython,
  findPython,
  pythonMissingMessage,
};
