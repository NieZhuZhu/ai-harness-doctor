'use strict';

// Dev-only unit tests for pure helpers exported from cli.js.
// Run with: node --test bin
const { test } = require('node:test');
const assert = require('node:assert');
const { compareVersions, parseInstallArgs } = require('./cli.js');

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
  // Numeric release sorts above alphabetic pre-release segment.
  assert.ok(compareVersions('1.0.0', '1.0.0-alpha') !== 0);
  assert.ok(compareVersions('1.0.0-beta', '1.0.0-alpha') > 0);
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
