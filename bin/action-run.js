#!/usr/bin/env node
'use strict';

const MAX_ARGS = 128;
const MAX_ARG_BYTES = 16 * 1024;
const MAX_JSON_BYTES = 64 * 1024;

const childProcess = require('node:child_process');
const fs = require('node:fs');

class ActionArgumentsError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ActionArgumentsError';
  }
}

function argumentError(message) {
  throw new ActionArgumentsError(`Action arguments error: ${message}`);
}

function parseExtraArgs({ argsJson = '', legacyArgs = '' } = {}) {
  argsJson = String(argsJson || '');
  legacyArgs = String(legacyArgs || '');
  if (argsJson && legacyArgs) argumentError('args and args-json are mutually exclusive');
  if (!argsJson) {
    const firstLine = legacyArgs.split('\n', 1)[0];
    const trimmed = firstLine.replace(/^[ \t]+|[ \t]+$/g, '');
    return trimmed ? trimmed.split(/[ \t]+/) : [];
  }
  if (Buffer.byteLength(argsJson, 'utf8') > MAX_JSON_BYTES) {
    argumentError('args-json exceeds 64 KiB');
  }
  let value;
  try {
    value = JSON.parse(argsJson);
  } catch (_) {
    argumentError('args-json must be valid JSON');
  }
  if (!Array.isArray(value)) argumentError('args-json must contain an array');
  if (value.length > MAX_ARGS) argumentError('args-json exceeds 128 items');
  for (const item of value) {
    if (typeof item !== 'string') argumentError('every args-json item must be a string');
    if (/[\0\r\n]/.test(item)) argumentError('args-json items must not contain NUL/CR/LF');
    if (Buffer.byteLength(item, 'utf8') > MAX_ARG_BYTES) {
      argumentError('one args-json item exceeds 16 KiB');
    }
  }
  return value;
}

class ActionRunnerError extends Error {
  constructor(message) {
    super(message);
    this.name = 'ActionRunnerError';
  }
}

function runnerError(message) {
  throw new ActionRunnerError(`Action runner error: ${message}`);
}

function buildCliArgs({ command, repoPath, extraArgs = [] }) {
  if (!['scan', 'drift'].includes(command)) {
    runnerError('command must be scan or drift');
  }
  if (typeof repoPath !== 'string' || /[\0\r\n]/.test(repoPath)) {
    runnerError('repository path must be one line');
  }
  return [command, repoPath, '--sarif', ...extraArgs];
}

function runCli(config, deps = {}) {
  const spawnSync = deps.spawnSync || childProcess.spawnSync;
  const fsApi = deps.fs || fs;
  const extraArgs = parseExtraArgs({
    argsJson: config.argsJson,
    legacyArgs: config.legacyArgs,
  });
  const args = buildCliArgs({
    command: config.command,
    repoPath: config.repoPath,
    extraArgs,
  });
  if (typeof config.cli !== 'string' || !config.cli) runnerError('CLI path is required');
  try {
    if (!fsApi.statSync(config.cli).isFile()) runnerError('CLI path is unavailable');
  } catch (error) {
    if (error instanceof ActionRunnerError) throw error;
    runnerError('CLI path is unavailable');
  }
  if (typeof config.sarifFile !== 'string' || /[\0\r\n]/.test(config.sarifFile)) {
    runnerError('SARIF path must be one line');
  }
  let descriptor;
  try {
    descriptor = fsApi.openSync(config.sarifFile, 'w');
    const result = spawnSync(
      process.execPath,
      [config.cli, ...args],
      {
        env: process.env,
        shell: false,
        stdio: ['ignore', descriptor, 'inherit'],
      },
    );
    if (result.error) runnerError('could not start the CLI');
    if (!Number.isInteger(result.status)) runnerError('CLI terminated without an exit code');
    return result.status;
  } catch (error) {
    if (error instanceof ActionArgumentsError || error instanceof ActionRunnerError) throw error;
    runnerError('could not execute the CLI');
  } finally {
    if (descriptor !== undefined) {
      try {
        fsApi.closeSync(descriptor);
      } catch (_) {
        // A close failure must not hide the primary execution result/error.
      }
    }
  }
}

function main(argv = process.argv, env = process.env) {
  const [cli, sarifFile, command, repoPath] = argv.slice(2);
  if (!cli || !sarifFile || !command || repoPath === undefined) {
    runnerError('usage: action-run.js CLI SARIF_FILE scan|drift REPO');
  }
  return runCli({
    cli,
    sarifFile,
    command,
    repoPath,
    argsJson: env.INPUT_ARGS_JSON || '',
    legacyArgs: env.INPUT_ARGS || '',
  });
}

if (require.main === module) {
  try {
    process.exitCode = main();
  } catch (error) {
    console.error(`ai-harness-doctor ${error.message}`);
    process.exitCode = error instanceof ActionArgumentsError ? 2 : 1;
  }
}

module.exports = {
  ActionArgumentsError,
  ActionRunnerError,
  buildCliArgs,
  main,
  parseExtraArgs,
  runCli,
};
