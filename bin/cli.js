#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const childProcess = require('child_process');

const PACKAGE_ROOT = path.resolve(__dirname, '..');
const SKILL_NAME = 'ai-harness-doctor';
const AGENTS = ['claude', 'codex', 'cursor', 'gemini'];
const COMMAND_NAMES = ['harness-doctor', 'harness-scan', 'harness-treat', 'harness-drift', 'harness-eval'];

function usage() {
  console.log(`AI Harness Doctor

Usage:
  ai-harness-doctor install [--agent claude|codex|cursor|gemini|all] [--project]
  ai-harness-doctor uninstall [--agent claude|codex|cursor|gemini|all] [--project]
  ai-harness-doctor scan [...args]
  ai-harness-doctor plan [...args]
  ai-harness-doctor stubs [...args]
  ai-harness-doctor drift [...args]
  ai-harness-doctor eval [...args]
  ai-harness-doctor help

Examples:
  npx ai-harness-doctor install
  npx ai-harness-doctor install --agent all --project
  npx ai-harness-doctor scan .
  npx ai-harness-doctor drift . --strict
`);
}

function parseInstallArgs(argv) {
  let agent = 'claude';
  let project = false;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--project') {
      project = true;
    } else if (arg === '--agent') {
      if (!argv[i + 1]) fail('Missing value after --agent');
      agent = argv[i + 1];
      i += 1;
    } else if (arg.startsWith('--agent=')) {
      agent = arg.slice('--agent='.length);
    } else {
      fail(`Unknown option: ${arg}`);
    }
  }
  const agents = agent === 'all' ? AGENTS : [agent];
  for (const item of agents) {
    if (!AGENTS.includes(item)) fail(`Unsupported agent: ${item}`);
  }
  return { agents, project };
}

function fail(message, code = 1) {
  console.error(`ai-harness-doctor: ${message}`);
  process.exit(code);
}

function homePath(...parts) {
  return path.join(os.homedir(), ...parts);
}

function projectPath(...parts) {
  return path.join(process.cwd(), ...parts);
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function removePath(target) {
  fs.rmSync(target, { recursive: true, force: true });
}

function copyFile(src, dest) {
  ensureDir(path.dirname(dest));
  fs.copyFileSync(src, dest);
}

function copyDir(src, dest) {
  removePath(dest);
  ensureDir(dest);
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDir(from, to);
    else if (entry.isFile()) copyFile(from, to);
  }
}

function copyPayload(dest) {
  removePath(dest);
  ensureDir(dest);
  for (const name of ['SKILL.md']) copyFile(path.join(PACKAGE_ROOT, name), path.join(dest, name));
  for (const name of ['scripts', 'references', 'assets']) copyDir(path.join(PACKAGE_ROOT, name), path.join(dest, name));
}

function replacePlaybook(content, playbook) {
  const token = '\\{\\{' + 'PLAYBOOK' + '\\}\\}';
  return content.replace(new RegExp(token, 'g'), playbook);
}

function installAdapterDir(srcDir, destDir, playbook) {
  ensureDir(destDir);
  const installed = [];
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const src = path.join(srcDir, entry.name);
    const dest = path.join(destDir, entry.name);
    const content = replacePlaybook(fs.readFileSync(src, 'utf8'), playbook);
    fs.writeFileSync(dest, content, 'utf8');
    installed.push(dest);
  }
  return installed;
}

function installGemini(playbook, project) {
  void project;
  const dest = homePath('.gemini', 'commands', 'harness');
  return installAdapterDir(path.join(PACKAGE_ROOT, 'adapters', 'gemini', 'harness'), dest, playbook);
}

function neutralPayloadPath(project) {
  return project ? projectPath('.ai-harness-doctor') : homePath('.ai-harness-doctor');
}

function claudeSkillPath(project) {
  return project ? projectPath('.claude', 'skills', SKILL_NAME) : homePath('.claude', 'skills', SKILL_NAME);
}

function claudeCommandDir(project) {
  return project ? projectPath('.claude', 'commands') : homePath('.claude', 'commands');
}

function installClaude(project) {
  const skillDir = claudeSkillPath(project);
  copyPayload(skillDir);
  const commandDir = claudeCommandDir(project);
  ensureDir(commandDir);
  const installed = [skillDir];
  for (const name of COMMAND_NAMES) {
    const file = `${name}.md`;
    const dest = path.join(commandDir, file);
    copyFile(path.join(PACKAGE_ROOT, 'commands', file), dest);
    installed.push(dest);
  }
  return installed;
}

function installOne(agent, project, neutralPayload) {
  if (agent === 'claude') return installClaude(project);
  if (agent === 'codex') {
    return [neutralPayload, ...installAdapterDir(path.join(PACKAGE_ROOT, 'adapters', 'codex'), homePath('.codex', 'prompts'), neutralPayload)];
  }
  if (agent === 'gemini') {
    return [neutralPayload, ...installGemini(neutralPayload, project)];
  }
  if (agent === 'cursor') {
    if (!fs.existsSync(projectPath('.git')) && !fs.existsSync(projectPath('package.json'))) {
      console.error('Note: Cursor commands are project-level; run this from the target project directory if needed.');
    }
    return [neutralPayload, ...installAdapterDir(path.join(PACKAGE_ROOT, 'adapters', 'cursor'), projectPath('.cursor', 'commands'), neutralPayload)];
  }
  fail(`Unsupported agent: ${agent}`);
}

function printSummary(action, rows) {
  console.log(`\n${action} summary:`);
  console.log('| Agent | Path |');
  console.log('|---|---|');
  for (const row of rows) console.log(`| ${row.agent} | ${row.path} |`);
}

function install(argv) {
  const { agents, project } = parseInstallArgs(argv);
  let neutralPayload = null;
  if (agents.some((agent) => agent !== 'claude')) {
    neutralPayload = neutralPayloadPath(project);
    copyPayload(neutralPayload);
  }
  const rows = [];
  for (const agent of agents) {
    for (const target of installOne(agent, project, neutralPayload)) rows.push({ agent, path: target });
  }
  printSummary('Install', rows);
}

function uninstall(argv) {
  const { agents, project } = parseInstallArgs(argv);
  const rows = [];
  if (agents.includes('claude')) {
    const skillDir = claudeSkillPath(project);
    removePath(skillDir);
    rows.push({ agent: 'claude', path: skillDir });
    for (const name of COMMAND_NAMES) {
      const target = path.join(claudeCommandDir(project), `${name}.md`);
      removePath(target);
      rows.push({ agent: 'claude', path: target });
    }
  }
  if (agents.some((agent) => agent !== 'claude')) {
    const neutral = neutralPayloadPath(project);
    removePath(neutral);
    rows.push({ agent: 'payload', path: neutral });
  }
  if (agents.includes('codex')) {
    for (const name of COMMAND_NAMES) {
      const target = homePath('.codex', 'prompts', `${name}.md`);
      removePath(target);
      rows.push({ agent: 'codex', path: target });
    }
  }
  if (agents.includes('cursor')) {
    for (const name of COMMAND_NAMES) {
      const target = projectPath('.cursor', 'commands', `${name}.md`);
      removePath(target);
      rows.push({ agent: 'cursor', path: target });
    }
  }
  if (agents.includes('gemini')) {
    const dir = homePath('.gemini', 'commands', 'harness');
    for (const name of ['doctor', 'scan', 'treat', 'drift', 'eval']) {
      const target = path.join(dir, `${name}.toml`);
      removePath(target);
      rows.push({ agent: 'gemini', path: target });
    }
  }
  printSummary('Uninstall', rows);
}

function resolvePython() {
  for (const candidate of ['python3', 'python']) {
    const found = childProcess.spawnSync(candidate, ['--version'], { stdio: 'ignore' });
    if (!found.error && found.status === 0) return candidate;
  }
  fail('Python is required. Install python3 or python and retry.');
}

function runScript(command, argv) {
  const mapping = {
    scan: ['scan.py'],
    plan: ['canonicalize.py', '--plan'],
    stubs: ['canonicalize.py', '--write-stubs'],
    drift: ['check_drift.py'],
    eval: ['eval_run.py'],
  };
  const spec = mapping[command];
  if (!spec) fail(`Unknown command: ${command}`);
  const python = resolvePython();
  const script = path.join(PACKAGE_ROOT, 'scripts', spec[0]);
  if (!fs.existsSync(script)) fail(`Script not found: ${script}`);
  const result = childProcess.spawnSync(python, [script, ...spec.slice(1), ...argv], { stdio: 'inherit' });
  if (result.error) fail(result.error.message);
  process.exit(result.status === null ? 1 : result.status);
}

function main() {
  const [command, ...rest] = process.argv.slice(2);
  if (!command || command === 'help' || command === '--help' || command === '-h') {
    usage();
    return;
  }
  if (command === 'install') return install(rest);
  if (command === 'uninstall') return uninstall(rest);
  if (['scan', 'plan', 'stubs', 'drift', 'eval'].includes(command)) return runScript(command, rest);
  fail(`Unknown command: ${command}`);
}

main();
