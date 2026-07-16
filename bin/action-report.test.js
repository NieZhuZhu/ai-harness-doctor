'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const report = require('./action-report.js');

function document(command, results, extra = {}) {
  return {
    version: '2.1.0',
    runs: [{
      tool: { driver: { name: 'ai-harness-doctor' } },
      results,
      properties: {
        aiHarnessDoctor: {
          command,
          findingCount: results.length,
          errorCount: results.filter((item) => item.level === 'error').length,
          warningCount: results.filter((item) => item.level === 'warning').length,
          noteCount: results.filter((item) => !['error', 'warning'].includes(item.level)).length,
          ...extra,
        },
      },
    }],
  };
}

test('parseSarif exposes scan counts and status', () => {
  const parsed = report.parseSarif(document('scan', [
    { level: 'error' },
    { level: 'warning' },
    { level: 'note' },
  ]), 'scan');
  assert.deepStrictEqual(
    {
      status: parsed.status,
      findingCount: parsed.findingCount,
      errorCount: parsed.errorCount,
      warningCount: parsed.warningCount,
      noteCount: parsed.noteCount,
      legacy: parsed.legacy,
    },
    {
      status: 'findings',
      findingCount: 3,
      errorCount: 1,
      warningCount: 1,
      noteCount: 1,
      legacy: false,
    },
  );
});

test('parseSarif exposes drift health', () => {
  const parsed = report.parseSarif(document('drift', [], {
    ok: true,
    score: 100,
    grade: 'A',
  }), 'drift');
  assert.strictEqual(parsed.status, 'ok');
  assert.strictEqual(parsed.score, '100');
  assert.strictEqual(parsed.grade, 'A');
  assert.strictEqual(parsed.ok, true);
});

test('legacy npm SARIF derives counts without fabricating drift health', () => {
  const parsed = report.parseSarif({
    version: '2.1.0',
    runs: [{
      tool: { driver: { name: 'ai-harness-doctor' } },
      results: [{ level: 'error' }, {}],
    }],
  }, 'drift');
  assert.strictEqual(parsed.findingCount, 2);
  assert.strictEqual(parsed.errorCount, 1);
  assert.strictEqual(parsed.noteCount, 1);
  assert.strictEqual(parsed.grade, '');
  assert.strictEqual(parsed.legacy, true);
});

test('producer counts must match SARIF results', () => {
  const data = document('scan', [{ level: 'error' }]);
  data.runs[0].properties.aiHarnessDoctor.findingCount = 0;
  assert.throws(() => report.parseSarif(data, 'scan'), /findingCount does not match/);
});

test('producer command must match Action command', () => {
  assert.throws(() => report.parseSarif(document('scan', []), 'drift'), /command does not match/);
});

test('SARIF must come from ai-harness-doctor', () => {
  const data = document('scan', []);
  data.runs[0].tool.driver.name = 'other-tool';
  assert.throws(() => report.parseSarif(data, 'scan'), /not produced by ai-harness-doctor/);
});

test('output path cannot inject environment-file lines', () => {
  const parsed = report.parseSarif(document('scan', []), 'scan');
  assert.throws(() => report.outputLines(parsed, 'safe.sarif\nstatus=ok'), /must be one line/);
});

test('summary escapes markdown cells and includes drift health', () => {
  assert.strictEqual(report.markdownCell('a|b\nc'), 'a\\|b c');
  const markdown = report.summaryMarkdown({
    command: 'drift',
    status: 'findings',
    findingCount: 1,
    errorCount: 1,
    warningCount: 0,
    noteCount: 0,
    score: '72',
    grade: 'C',
    legacy: false,
  });
  assert.match(markdown, /AI Harness Doctor/);
  assert.match(markdown, /72\/100 \(grade C\)/);
});

test('run writes outputs and summary environment files', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'action-report-'));
  try {
    const sarif = path.join(tmp, 'result.sarif');
    const output = path.join(tmp, 'output');
    const summary = path.join(tmp, 'summary');
    fs.writeFileSync(sarif, JSON.stringify(document('scan', [])));
    fs.writeFileSync(output, '');
    fs.writeFileSync(summary, '');
    report.run(['node', 'action-report.js', sarif, 'scan'], {
      GITHUB_OUTPUT: output,
      GITHUB_STEP_SUMMARY: summary,
    });
    assert.match(fs.readFileSync(output, 'utf8'), /status=ok/);
    assert.match(fs.readFileSync(output, 'utf8'), /finding-count=0/);
    assert.match(fs.readFileSync(summary, 'utf8'), /No active findings/);
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});

test('run rejects malformed SARIF and missing environment files', () => {
  assert.throws(
    () => report.run(['node', 'action-report.js', 'missing.sarif', 'scan'], {}),
    /GITHUB_OUTPUT is required/,
  );
});

test('run rejects malformed SARIF before writing environment files', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'action-report-bad-'));
  try {
    const sarif = path.join(tmp, 'result.sarif');
    const output = path.join(tmp, 'output');
    const summary = path.join(tmp, 'summary');
    fs.writeFileSync(sarif, '{bad');
    fs.writeFileSync(output, '');
    fs.writeFileSync(summary, '');
    assert.throws(
      () => report.run(['node', 'action-report.js', sarif, 'scan'], {
        GITHUB_OUTPUT: output,
        GITHUB_STEP_SUMMARY: summary,
      }),
      /could not read valid SARIF/,
    );
    assert.strictEqual(fs.readFileSync(output, 'utf8'), '');
    assert.strictEqual(fs.readFileSync(summary, 'utf8'), '');
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
});
