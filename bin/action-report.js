#!/usr/bin/env node
'use strict';

// Turn one ai-harness-doctor SARIF document into GitHub Action outputs and a
// human-readable Job Summary. Node 16 standard library only. The current
// bundled producer supplies run.properties.aiHarnessDoctor; an explicit
// `version:` override may point to an older published package, so legacy SARIF
// remains compatible by deriving counts from standard results (health stays
// unavailable rather than fabricated).

const fs = require('node:fs');
const path = require('node:path');

const LEVELS = new Set(['error', 'warning', 'note']);

function fail(message) {
  const error = new Error(message);
  error.name = 'ActionReportError';
  throw error;
}

function nonNegativeInteger(value, name) {
  if (!Number.isInteger(value) || value < 0) fail(`invalid SARIF ${name}`);
  return value;
}

function derivedCounts(results) {
  const counts = { errorCount: 0, warningCount: 0, noteCount: 0 };
  for (const result of results) {
    if (!result || typeof result !== 'object' || Array.isArray(result)) {
      fail('invalid SARIF result');
    }
    const level = LEVELS.has(result.level) ? result.level : 'note';
    counts[`${level}Count`] += 1;
  }
  return { findingCount: results.length, ...counts };
}

function parseSarif(data, expectedCommand) {
  if (!['scan', 'drift'].includes(expectedCommand)) {
    fail(`unsupported Action command: ${expectedCommand}`);
  }
  if (!data || data.version !== '2.1.0' || !Array.isArray(data.runs) || data.runs.length !== 1) {
    fail('invalid ai-harness-doctor SARIF document');
  }
  const run = data.runs[0];
  if (!run || typeof run !== 'object' || !Array.isArray(run.results)) {
    fail('invalid ai-harness-doctor SARIF run');
  }
  const driver = run.tool && run.tool.driver;
  if (!driver || driver.name !== 'ai-harness-doctor') {
    fail('SARIF was not produced by ai-harness-doctor');
  }
  const counts = derivedCounts(run.results);
  const producer = run.properties && run.properties.aiHarnessDoctor;
  let score = '';
  let grade = '';
  let ok;
  let legacy = true;

  if (producer !== undefined) {
    if (!producer || typeof producer !== 'object' || Array.isArray(producer)) {
      fail('invalid ai-harness-doctor SARIF producer metadata');
    }
    if (producer.command !== expectedCommand) fail('SARIF command does not match Action command');
    for (const key of ['findingCount', 'errorCount', 'warningCount', 'noteCount']) {
      nonNegativeInteger(producer[key], key);
      if (producer[key] !== counts[key]) fail(`SARIF ${key} does not match results`);
    }
    if (expectedCommand === 'drift') {
      if (typeof producer.ok !== 'boolean') fail('invalid drift health status');
      if (typeof producer.score !== 'number' || !Number.isFinite(producer.score)) {
        fail('invalid drift health score');
      }
      if (typeof producer.grade !== 'string' || !producer.grade) fail('invalid drift health grade');
      ok = producer.ok;
      score = String(producer.score);
      grade = producer.grade;
    }
    legacy = false;
  }

  return {
    command: expectedCommand,
    status: counts.findingCount === 0 ? 'ok' : 'findings',
    ...counts,
    ok,
    score,
    grade,
    legacy,
  };
}

function outputLines(report, sarifFile) {
  if (/[\r\n]/.test(sarifFile)) fail('SARIF output path must be one line');
  return [
    `sarif-file=${sarifFile}`,
    `status=${report.status}`,
    `finding-count=${report.findingCount}`,
    `error-count=${report.errorCount}`,
    `warning-count=${report.warningCount}`,
    `note-count=${report.noteCount}`,
    `health-score=${report.score}`,
    `health-grade=${report.grade}`,
  ].join('\n') + '\n';
}

function markdownCell(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/\|/g, '\\|').replace(/\r?\n/g, ' ');
}

function summaryMarkdown(report) {
  const status = report.status === 'ok' ? '✅ No active findings' : `⚠️ ${report.findingCount} active finding(s)`;
  const rows = [
    ['Command', `\`${report.command}\``],
    ['Status', status],
    ['Findings', String(report.findingCount)],
    ['Severity', `${report.errorCount} error · ${report.warningCount} warning · ${report.noteCount} note`],
  ];
  if (report.command === 'drift' && report.grade) {
    rows.push(['Health', `${report.score}/100 (grade ${report.grade})`]);
  } else if (report.command === 'drift' && report.legacy) {
    rows.push(['Health', 'Unavailable from the selected legacy npm version']);
  }
  return [
    '## AI Harness Doctor',
    '',
    '| Field | Result |',
    '|---|---|',
    ...rows.map(([field, value]) => `| ${markdownCell(field)} | ${markdownCell(value)} |`),
    '',
  ].join('\n');
}

function run(argv = process.argv, env = process.env) {
  const sarifFile = argv[2];
  const expectedCommand = argv[3];
  if (!sarifFile || !expectedCommand) fail('usage: action-report.js SARIF_FILE scan|drift');
  if (!env.GITHUB_OUTPUT) fail('GITHUB_OUTPUT is required');
  if (!env.GITHUB_STEP_SUMMARY) fail('GITHUB_STEP_SUMMARY is required');
  let data;
  try {
    data = JSON.parse(fs.readFileSync(sarifFile, 'utf8'));
  } catch (_) {
    fail(`could not read valid SARIF: ${path.basename(sarifFile)}`);
  }
  const report = parseSarif(data, expectedCommand);
  fs.appendFileSync(env.GITHUB_OUTPUT, outputLines(report, sarifFile), 'utf8');
  fs.appendFileSync(env.GITHUB_STEP_SUMMARY, summaryMarkdown(report), 'utf8');
  return report;
}

if (require.main === module) {
  try {
    run();
  } catch (error) {
    console.error(`ai-harness-doctor Action report error: ${error.message}`);
    process.exit(2);
  }
}

module.exports = {
  derivedCounts,
  markdownCell,
  outputLines,
  parseSarif,
  run,
  summaryMarkdown,
};
