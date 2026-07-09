'use strict';

// Dev-only unit tests for pure helpers exported from cli.js.
// Run with: node --test bin
const { test } = require('node:test');
const assert = require('node:assert');
const path = require('path');
const os = require('os');
const fs = require('fs');
const childProcess = require('child_process');
const { compareVersions, parseInstallArgs, SCRIPT_COMMANDS, runtimeChecks, parseDoctorArgs } = require('./cli.js');

const CLI = path.join(__dirname, 'cli.js');

test('compareVersions orders semver numerically', () => {
  assert.ok(compareVersions('1.2.0', '1.1.9') > 0);
  assert.ok(compareVersions('1.1.9', '1.2.0') < 0);
  assert.strictEqual(compareVersions('1.2.3', '1.2.3'), 0);
});

test('compareVersions treats missing components as zero', () => {
  assert.strictEqual(compareVersions('1.2', '1.2.0'), 0);
  assert.ok(compareVersions('1.2.1', '1.2') > 0);
});

test('compareVersions handles pre-release tags', () => {
  // CORR-09: a pre-release is LOWER than its associated normal release, so
  // `1.0.0` > `1.0.0-alpha` and `1.0.0-alpha` < `1.0.0` (SemVer §11.3).
  assert.ok(compareVersions('1.0.0', '1.0.0-alpha') > 0);
  assert.ok(compareVersions('1.0.0-alpha', '1.0.0') < 0);
  assert.strictEqual(compareVersions('1.0.0-alpha', '1.0.0-alpha'), 0);
  // Alphabetic identifiers compare lexically.
  assert.ok(compareVersions('1.0.0-beta', '1.0.0-alpha') > 0);
  // SemVer §11.4 precedence chain: alpha < alpha.1 < alpha.beta < beta < beta.2
  // < beta.11 < rc.1 < release.
  assert.ok(compareVersions('1.0.0-alpha.1', '1.0.0-alpha') > 0); // larger set wins
  assert.ok(compareVersions('1.0.0-alpha.beta', '1.0.0-alpha.1') > 0); // alphanumeric > numeric
  assert.ok(compareVersions('1.0.0-beta.11', '1.0.0-beta.2') > 0); // numeric compares numerically
  assert.ok(compareVersions('1.0.0-rc.1', '1.0.0-beta.11') > 0);
  assert.ok(compareVersions('1.0.0', '1.0.0-rc.1') > 0);
  // A pre-release on a higher main version still outranks a lower release.
  assert.ok(compareVersions('1.0.1-alpha', '1.0.0') > 0);
  // Build metadata is ignored for precedence.
  assert.strictEqual(compareVersions('1.0.0+build.5', '1.0.0'), 0);
});

test('parseInstallArgs returns sensible defaults', () => {
  const result = parseInstallArgs([]);
  assert.deepStrictEqual(result.agents, ['claude']);
  assert.strictEqual(result.project, null);
  assert.strictEqual(result.link, false);
});

test('parseInstallArgs expands --agent all to every agent', () => {
  const result = parseInstallArgs(['--agent', 'all']);
  assert.deepStrictEqual(result.agents, ['claude', 'codex', 'cursor', 'gemini']);
});

test('parseInstallArgs accepts --agent=<value> and --link', () => {
  const result = parseInstallArgs(['--agent=codex', '--link']);
  assert.deepStrictEqual(result.agents, ['codex']);
  assert.strictEqual(result.link, true);
});

test('SCRIPT_COMMANDS maps every Python-backed subcommand to a script', () => {
  assert.deepStrictEqual(Object.keys(SCRIPT_COMMANDS).sort(), ['drift', 'eval', 'plan', 'scan', 'stubs', 'validate']);
  for (const spec of Object.values(SCRIPT_COMMANDS)) {
    assert.ok(spec[0].endsWith('.py'), `expected a .py script, got ${spec[0]}`);
  }
});

test('parseDoctorArgs accepts --self-test and --json', () => {
  assert.deepStrictEqual(parseDoctorArgs([]), { asJson: false });
  assert.deepStrictEqual(parseDoctorArgs(['--self-test']), { asJson: false });
  assert.deepStrictEqual(parseDoctorArgs(['--json']), { asJson: true });
  assert.deepStrictEqual(parseDoctorArgs(['--self-test', '--json']), { asJson: true });
});

test('runtimeChecks reports python ok with an injected present interpreter', () => {
  const spawn = () => ({ error: null, status: 0, stdout: '3.11.9' });
  const checks = runtimeChecks({}, spawn);
  const python = checks.find((c) => c.name === 'python');
  assert.strictEqual(python.ok, true);
  assert.match(python.detail, /Python 3\.11\.9/);
  // Every shipped Python engine + the MCP server should be present in the repo.
  assert.ok(checks.filter((c) => c.name.startsWith('script:')).every((c) => c.ok));
  assert.ok(checks.find((c) => c.name === 'mcp-server').ok);
});

test('runtimeChecks flags python as FAIL when the runtime is missing', () => {
  const spawn = () => ({ error: new Error('ENOENT'), status: null, stdout: '' });
  const checks = runtimeChecks({}, spawn);
  const python = checks.find((c) => c.name === 'python');
  assert.strictEqual(python.ok, false);
  assert.match(python.detail, /not found/);
});

// Integration: the dispatcher must fail with a clean, actionable message (not a
// raw stack trace) when no Python interpreter is on PATH. We build a temp bin
// dir that exposes only `node` so `python3`/`python` cannot be resolved.
test('dispatcher fails cleanly when Python runtime is missing', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ahd-nopy-'));
  try {
    const nodeLink = path.join(tmp, 'node');
    fs.symlinkSync(process.execPath, nodeLink);
    const result = childProcess.spawnSync(process.execPath, [CLI, 'scan', '.'], {
      encoding: 'utf8',
      env: { ...process.env, PATH: tmp, AI_HARNESS_DOCTOR_PYTHON: '', PYTHON: '', AI_HARNESS_DOCTOR_NO_UPDATE_CHECK: '1' },
    });
    assert.strictEqual(result.status, 1);
    assert.match(result.stderr, /Python 3 is required but was not found/);
    assert.match(result.stderr, /AI_HARNESS_DOCTOR_PYTHON/);
    // Should not leak a Node stack trace.
    assert.doesNotMatch(result.stderr, /at Object\.<anonymous>|node:internal/);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('doctor --self-test exits non-zero when Python is missing', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ahd-nopy-'));
  try {
    fs.symlinkSync(process.execPath, path.join(tmp, 'node'));
    const result = childProcess.spawnSync(process.execPath, [CLI, 'doctor', '--self-test'], {
      encoding: 'utf8',
      env: { ...process.env, PATH: tmp, AI_HARNESS_DOCTOR_PYTHON: '', PYTHON: '', AI_HARNESS_DOCTOR_NO_UPDATE_CHECK: '1' },
    });
    assert.strictEqual(result.status, 1);
    assert.match(result.stdout, /python \| FAIL/);
    assert.match(result.stdout, /Some runtime checks FAILED/);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('doctor --json reports ok with the real runtime present', () => {
  const result = childProcess.spawnSync(process.execPath, [CLI, 'doctor', '--json'], {
    encoding: 'utf8',
    env: { ...process.env, AI_HARNESS_DOCTOR_NO_UPDATE_CHECK: '1' },
  });
  assert.strictEqual(result.status, 0, result.stderr);
  const report = JSON.parse(result.stdout);
  assert.strictEqual(report.ok, true);
  assert.ok(Array.isArray(report.checks));
});
