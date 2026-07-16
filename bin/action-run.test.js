'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const childProcess = require('node:child_process');
const actionRun = require('./action-run.js');

const ACTION_RUN = path.join(__dirname, 'action-run.js');

test('legacy args preserve first-line whitespace splitting', () => {
  assert.deepStrictEqual(actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '' }), []);
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '  --a   b\t--c ' }),
    ['--a', 'b', '--c'],
  );
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '--a "x y"' }),
    ['--a', '"x', 'y"'],
  );
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '--a\n--b' }),
    ['--a'],
  );
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '--a\\ value' }),
    ['--a\\', 'value'],
  );
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({ argsJson: '', legacyArgs: '--a\r\n--b' }),
    ['--a\r'],
  );
});

test('structured args preserve exact order, spaces, repeats, and empty values', () => {
  assert.deepStrictEqual(
    actionRun.parseExtraArgs({
      argsJson: JSON.stringify([
        '--baseline',
        '/tmp/repo with spaces/base.json',
        '--rules',
        '',
        '--rules',
        'second',
      ]),
      legacyArgs: '',
    }),
    [
      '--baseline',
      '/tmp/repo with spaces/base.json',
      '--rules',
      '',
      '--rules',
      'second',
    ],
  );
});

test('structured args reject malformed values and conflicting legacy input', () => {
  const invalid = [
    { argsJson: '{', legacyArgs: '' },
    { argsJson: '{}', legacyArgs: '' },
    { argsJson: '[1]', legacyArgs: '' },
    { argsJson: '["line\\nbreak"]', legacyArgs: '' },
    { argsJson: '["line\\rbreak"]', legacyArgs: '' },
    { argsJson: '["nul\\u0000byte"]', legacyArgs: '' },
    { argsJson: '["--strict"]', legacyArgs: '--json' },
  ];
  for (const value of invalid) {
    assert.throws(() => actionRun.parseExtraArgs(value), /Action arguments/);
  }
});

test('structured args enforce UTF-8 and count limits', () => {
  assert.throws(
    () => actionRun.parseExtraArgs({
      argsJson: JSON.stringify(Array.from({ length: 129 }, () => 'x')),
      legacyArgs: '',
    }),
    /Action arguments/,
  );
  assert.throws(
    () => actionRun.parseExtraArgs({
      argsJson: JSON.stringify(['界'.repeat(6000)]),
      legacyArgs: '',
    }),
    /Action arguments/,
  );
  assert.throws(
    () => actionRun.parseExtraArgs({
      argsJson: JSON.stringify(['界'.repeat(22000)]),
      legacyArgs: '',
    }),
    /Action arguments/,
  );
});

test('runCli executes exact argv without a shell and streams stdout to SARIF', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'action-run-'));
  try {
    const sarif = path.join(tmp, 'result.sarif');
    let observed;
    const status = actionRun.runCli({
      cli: ACTION_RUN,
      sarifFile: sarif,
      command: 'drift',
      repoPath: '/tmp/repo with spaces',
      argsJson: '["--baseline","/tmp/repo with spaces/base.json","--check-baseline"]',
      legacyArgs: '',
    }, {
      spawnSync(command, args, options) {
        observed = { command, args, options };
        fs.writeSync(options.stdio[1], '{"version":"2.1.0"}');
        return { status: 9, signal: null, error: null };
      },
    });

    assert.strictEqual(status, 9);
    assert.strictEqual(observed.command, process.execPath);
    assert.deepStrictEqual(observed.args, [
      ACTION_RUN,
      'drift',
      '/tmp/repo with spaces',
      '--sarif',
      '--baseline',
      '/tmp/repo with spaces/base.json',
      '--check-baseline',
    ]);
    assert.strictEqual(observed.options.shell, false);
    assert.strictEqual(observed.options.stdio[0], 'ignore');
    assert.strictEqual(observed.options.stdio[2], 'inherit');
    assert.strictEqual(fs.readFileSync(sarif, 'utf8'), '{"version":"2.1.0"}');
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCli rejects invalid arguments before spawning', () => {
  let calls = 0;
  assert.throws(
    () => actionRun.runCli({
      cli: '/action/bin/cli.js',
      sarifFile: '/tmp/result.sarif',
      command: 'scan',
      repoPath: '.',
      argsJson: '{',
      legacyArgs: '',
    }, {
      spawnSync() {
        calls += 1;
      },
    }),
    /Action arguments/,
  );
  assert.strictEqual(calls, 0);
});

test('runCli validates command and maps spawn failures to operational errors', () => {
  assert.throws(
    () => actionRun.runCli({
      cli: '/action/bin/cli.js',
      sarifFile: '/tmp/result.sarif',
      command: 'eval',
      repoPath: '.',
    }),
    /Action runner/,
  );

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'action-run-errors-'));
  try {
    const base = {
      cli: '/action/bin/cli.js',
      sarifFile: path.join(tmp, 'result.sarif'),
      command: 'scan',
      repoPath: '.',
    };
    assert.throws(
      () => actionRun.runCli(base, {
        spawnSync: () => ({ status: null, signal: 'SIGTERM', error: null }),
      }),
      /Action runner/,
    );
    assert.throws(
      () => actionRun.runCli(base, {
        spawnSync: () => ({ status: null, signal: null, error: new Error('ENOENT') }),
      }),
      /Action runner/,
    );
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('runCli closes the SARIF descriptor on success and spawn failure', () => {
  for (const result of [
    { status: 0, signal: null, error: null },
    { status: null, signal: null, error: new Error('ENOENT') },
  ]) {
    const events = [];
    const fsApi = {
      statSync() {
        return { isFile: () => true };
      },
      openSync(file, mode) {
        events.push(['open', file, mode]);
        return 42;
      },
      closeSync(descriptor) {
        events.push(['close', descriptor]);
      },
    };
    const invoke = () => actionRun.runCli({
      cli: '/action/bin/cli.js',
      sarifFile: '/tmp/result.sarif',
      command: 'scan',
      repoPath: '.',
    }, {
      fs: fsApi,
      spawnSync: () => result,
    });

    if (result.error) assert.throws(invoke, /Action runner/);
    else assert.strictEqual(invoke(), 0);
    assert.deepStrictEqual(events, [
      ['open', '/tmp/result.sarif', 'w'],
      ['close', 42],
    ]);
  }
});

test('CLI entrypoint maps validation and spawn failures without echoing input', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'action-run-main-'));
  try {
    const sentinel = 'do-not-echo-this-value';
    const malformed = childProcess.spawnSync(
      process.execPath,
      [ACTION_RUN, '/missing/cli.js', path.join(tmp, 'bad.sarif'), 'scan', '.'],
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          INPUT_ARGS: '',
          INPUT_ARGS_JSON: `{"secret":"${sentinel}"}`,
        },
      },
    );
    assert.strictEqual(malformed.status, 2);
    assert.match(malformed.stderr, /Action arguments error/);
    assert.doesNotMatch(malformed.stderr, new RegExp(sentinel));

    const missingCli = childProcess.spawnSync(
      process.execPath,
      [ACTION_RUN, '/missing/cli.js', path.join(tmp, 'missing.sarif'), 'scan', '.'],
      {
        encoding: 'utf8',
        env: { ...process.env, INPUT_ARGS: '', INPUT_ARGS_JSON: '' },
      },
    );
    assert.strictEqual(missingCli.status, 1);
    assert.match(missingCli.stderr, /Action runner error/);
    assert.doesNotMatch(missingCli.stderr, /ENOENT/);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});
