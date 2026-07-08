'use strict';

// Unit tests for the shared Python runtime resolver. A fake `spawn` lets us
// simulate a present / missing / Python-2 interpreter without touching PATH.
const { test } = require('node:test');
const assert = require('node:assert');
const runtime = require('./runtime.js');

// Build a fake spawnSync that answers the `-c <version snippet>` probe based on
// a map of interpreter name -> version string (or null to simulate "not found").
function fakeSpawn(table) {
  return (command, args) => {
    void args;
    if (!(command in table)) return { error: new Error('ENOENT'), status: null, stdout: '' };
    const version = table[command];
    if (version === null) return { error: new Error('ENOENT'), status: null, stdout: '' };
    return { error: null, status: 0, stdout: version };
  };
}

test('pythonCandidates honors env overrides first, then defaults, de-duped', () => {
  const candidates = runtime.pythonCandidates({ AI_HARNESS_DOCTOR_PYTHON: '/opt/py', PYTHON: 'python3' });
  assert.deepStrictEqual(candidates, ['/opt/py', 'python3', 'python']);
});

test('pythonCandidates falls back to python3, python with empty env', () => {
  assert.deepStrictEqual(runtime.pythonCandidates({}), ['python3', 'python']);
});

test('findPython returns the first usable Python 3', () => {
  const spawn = fakeSpawn({ python3: '3.11.9', python: '2.7.18' });
  const found = runtime.findPython({}, spawn);
  assert.strictEqual(found.ok, true);
  assert.strictEqual(found.command, 'python3');
  assert.strictEqual(found.version, '3.11.9');
});

test('findPython skips Python 2 and finds a later Python 3', () => {
  // `python` resolves to Python 2 first; env override is absent; python3 is 3.x.
  const spawn = fakeSpawn({ python: '2.7.18', python3: '3.10.0' });
  const found = runtime.findPython({}, spawn);
  assert.strictEqual(found.ok, true);
  assert.strictEqual(found.command, 'python3');
});

test('findPython rejects a Python 2 only environment', () => {
  const spawn = fakeSpawn({ python3: null, python: '2.7.18' });
  const found = runtime.findPython({}, spawn);
  assert.strictEqual(found.ok, false);
  assert.deepStrictEqual(found.tried, ['python3', 'python']);
});

test('findPython reports a miss when no interpreter is present', () => {
  const spawn = fakeSpawn({});
  const found = runtime.findPython({}, spawn);
  assert.strictEqual(found.ok, false);
  assert.deepStrictEqual(found.tried, ['python3', 'python']);
});

test('findPython prefers the env-pinned interpreter', () => {
  const spawn = fakeSpawn({ '/opt/py/bin/python': '3.12.1', python3: '3.9.0' });
  const found = runtime.findPython({ AI_HARNESS_DOCTOR_PYTHON: '/opt/py/bin/python' }, spawn);
  assert.strictEqual(found.ok, true);
  assert.strictEqual(found.command, '/opt/py/bin/python');
  assert.strictEqual(found.version, '3.12.1');
});

test('probePython tolerates a throwing spawn', () => {
  const throwingSpawn = () => { throw new Error('spawn blew up'); };
  assert.strictEqual(runtime.probePython('python3', throwingSpawn), null);
});

test('pythonMissingMessage is actionable and mentions the override env var', () => {
  const message = runtime.pythonMissingMessage(['python3', 'python']);
  assert.match(message, /Python 3 is required/);
  assert.match(message, /Tried: python3, python\./);
  assert.match(message, /AI_HARNESS_DOCTOR_PYTHON/);
  // No raw stack-trace markers.
  assert.doesNotMatch(message, /at .*\(.*:\d+:\d+\)/);
});
