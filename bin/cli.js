#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const https = require('https');
const childProcess = require('child_process');

const PACKAGE_ROOT = path.resolve(__dirname, '..');
const PACKAGE_JSON = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, 'package.json'), 'utf8'));
const PACKAGE_VERSION = PACKAGE_JSON.version;
const SKILL_NAME = 'ai-harness-doctor';
const AGENTS = ['claude', 'codex', 'cursor', 'gemini'];
const COMMAND_NAMES = ['harness-doctor', 'harness-scan', 'harness-treat', 'harness-drift', 'harness-eval'];
const MANIFEST_DIR = homePath('.ai-harness-doctor');
const MANIFEST_PATH = path.join(MANIFEST_DIR, 'manifest.json');
const UPDATE_CHECK_URL = 'https://registry.npmjs.org/ai-harness-doctor/latest';
const UPDATE_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000;

function usage() {
  console.log(`AI Harness Doctor

Usage:
  ai-harness-doctor install [--agent claude|codex|cursor|gemini|all] [--project] [--link]
  ai-harness-doctor uninstall [--agent claude|codex|cursor|gemini|all] [--project]
  ai-harness-doctor update
  ai-harness-doctor scan [...args]
  ai-harness-doctor plan [...args]
  ai-harness-doctor stubs [...args]
  ai-harness-doctor drift [...args]
  ai-harness-doctor eval [...args]
  ai-harness-doctor help

Examples:
  npx ai-harness-doctor install
  npx ai-harness-doctor install --agent all --project
  npx ai-harness-doctor@latest update
  npm i -g ai-harness-doctor && ai-harness-doctor install --link
  npx ai-harness-doctor scan .
  npx ai-harness-doctor drift . --strict
`);
}

function parseInstallArgs(argv) {
  let agent = 'claude';
  let project = false;
  let link = false;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--project') {
      project = true;
    } else if (arg === '--link') {
      link = true;
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
  return { agents, project: project ? fs.realpathSync(process.cwd()) : null, link };
}

function fail(message, code = 1) {
  console.error(`ai-harness-doctor: ${message}`);
  process.exit(code);
}

function homePath(...parts) {
  return path.join(os.homedir(), ...parts);
}

function targetPath(project, ...parts) {
  return path.join(project || process.cwd(), ...parts);
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function removePath(target) {
  fs.rmSync(target, { recursive: true, force: true });
}

function removeLinkOrPath(target) {
  try {
    const stat = fs.lstatSync(target);
    if (stat.isSymbolicLink()) fs.unlinkSync(target);
    else removePath(target);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
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

function readManifest() {
  try {
    const parsed = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
    if (!parsed || typeof parsed !== 'object') throw new Error('bad manifest');
    if (!Array.isArray(parsed.installs)) parsed.installs = [];
    if (typeof parsed.lastUpdateCheck !== 'number') parsed.lastUpdateCheck = 0;
    if (typeof parsed.version !== 'string') parsed.version = PACKAGE_VERSION;
    return parsed;
  } catch (_) {
    return { version: PACKAGE_VERSION, lastUpdateCheck: 0, installs: [] };
  }
}

function writeManifest(manifest) {
  ensureDir(MANIFEST_DIR);
  fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

function sameInstall(a, b) {
  return a.agent === b.agent && (a.project || null) === (b.project || null);
}

function recordInstalls(agents, project, link, manifest) {
  manifest = manifest || readManifest();
  const now = new Date().toISOString();
  for (const agent of agents) {
    const record = { agent, project: project || null, link: Boolean(link), installedAt: now };
    const idx = manifest.installs.findIndex((item) => sameInstall(item, record));
    if (idx >= 0) manifest.installs[idx] = record;
    else manifest.installs.push(record);
  }
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
}

function removeInstallRecords(agents, project) {
  const manifest = readManifest();
  manifest.installs = manifest.installs.filter((item) => !agents.includes(item.agent) || (item.project || null) !== (project || null));
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
}

function skillFrontmatterNamesThisPackage(skillPath) {
  try {
    const content = fs.readFileSync(skillPath, 'utf8');
    return /^---\s*[\s\S]*?^name:\s*ai-harness-doctor\s*$/m.test(content);
  } catch (_) {
    return false;
  }
}

function isOurPayloadDirectory(target) {
  try {
    const stat = fs.statSync(target);
    return stat.isDirectory() && skillFrontmatterNamesThisPackage(path.join(target, 'SKILL.md'));
  } catch (_) {
    return false;
  }
}

function ensureLinkAllowed() {
  const marker = `${path.sep}_npx${path.sep}`;
  const normalized = `${PACKAGE_ROOT}${path.sep}`;
  if (normalized.includes(marker) || /[\\/]_npx[\\/]/.test(normalized)) {
    fail('--link requires a persistent install: npm i -g ai-harness-doctor');
  }
}

function symlinkDirectory(src, dest) {
  ensureDir(path.dirname(dest));
  fs.symlinkSync(src, dest, process.platform === 'win32' ? 'junction' : 'dir');
}

function linkPayload(dest) {
  ensureLinkAllowed();
  try {
    const stat = fs.lstatSync(dest);
    if (stat.isSymbolicLink()) {
      fs.unlinkSync(dest);
    } else if (stat.isDirectory() && isOurPayloadDirectory(dest)) {
      removePath(dest);
    } else {
      fail(`Refusing to replace non-ai-harness-doctor path: ${dest}`);
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  symlinkDirectory(PACKAGE_ROOT, dest);
}

function compareVersions(a, b) {
  const pa = String(a).split(/[.-]/).map((part) => (/^\d+$/.test(part) ? Number(part) : part));
  const pb = String(b).split(/[.-]/).map((part) => (/^\d+$/.test(part) ? Number(part) : part));
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const va = pa[i] === undefined ? 0 : pa[i];
    const vb = pb[i] === undefined ? 0 : pb[i];
    if (typeof va === 'number' && typeof vb === 'number') {
      if (va !== vb) return va > vb ? 1 : -1;
    } else {
      const sa = String(va);
      const sb = String(vb);
      if (sa !== sb) return sa > sb ? 1 : -1;
    }
  }
  return 0;
}

function maybeCheckForUpdate() {
  if (process.env.AI_HARNESS_DOCTOR_NO_UPDATE_CHECK === '1') return;
  if (!process.stderr.isTTY) return;
  const manifest = readManifest();
  const now = Date.now();
  if (now - manifest.lastUpdateCheck < UPDATE_CHECK_INTERVAL_MS) return;
  manifest.lastUpdateCheck = now;
  writeManifest(manifest);

  let done = false;
  const finish = () => {
    done = true;
  };
  const req = https.get(UPDATE_CHECK_URL, { timeout: 1500 }, (res) => {
    let body = '';
    res.setEncoding('utf8');
    res.on('data', (chunk) => {
      body += chunk;
      if (body.length > 4096) req.destroy();
    });
    res.on('end', () => {
      if (done) return;
      finish();
      try {
        const remote = JSON.parse(body).version;
        if (remote && compareVersions(remote, PACKAGE_VERSION) > 0) {
          console.error(`Update available ${PACKAGE_VERSION} → ${remote} — run: npx ai-harness-doctor@latest update`);
        }
      } catch (_) {
        // Best effort only.
      }
    });
  });
  req.on('socket', (socket) => socket.unref());
  req.on('timeout', () => req.destroy());
  req.on('error', () => finish());
  req.end();
  req.unref();
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
  return project ? path.join(project, '.ai-harness-doctor') : homePath('.ai-harness-doctor');
}

function neutralLinkPath(project) {
  return project ? path.join(project, '.ai-harness-doctor', 'payload') : homePath('.ai-harness-doctor', 'payload');
}

function claudeSkillPath(project) {
  return project ? path.join(project, '.claude', 'skills', SKILL_NAME) : homePath('.claude', 'skills', SKILL_NAME);
}

function claudeCommandDir(project) {
  return project ? path.join(project, '.claude', 'commands') : homePath('.claude', 'commands');
}

function installClaude(project, link) {
  const skillDir = claudeSkillPath(project);
  if (link) linkPayload(skillDir);
  else copyPayload(skillDir);
  return [skillDir, ...installClaudeCommands(project)];
}

function installClaudeCommands(project) {
  const commandDir = claudeCommandDir(project);
  ensureDir(commandDir);
  const installed = [];
  for (const name of COMMAND_NAMES) {
    const file = `${name}.md`;
    const dest = path.join(commandDir, file);
    copyFile(path.join(PACKAGE_ROOT, 'commands', file), dest);
    installed.push(dest);
  }
  return installed;
}

function readSymlinkTarget(target) {
  try {
    const stat = fs.lstatSync(target);
    if (!stat.isSymbolicLink()) return null;
    const link = fs.readlinkSync(target);
    return path.resolve(path.dirname(target), link);
  } catch (_) {
    return null;
  }
}

function installOne(agent, project, neutralPayload, link) {
  if (agent === 'claude') return installClaude(project, link);
  if (agent === 'codex') {
    return [neutralPayload, ...installAdapterDir(path.join(PACKAGE_ROOT, 'adapters', 'codex'), homePath('.codex', 'prompts'), neutralPayload)];
  }
  if (agent === 'gemini') {
    return [neutralPayload, ...installGemini(neutralPayload, project)];
  }
  if (agent === 'cursor') {
    if (!fs.existsSync(targetPath(project, '.git')) && !fs.existsSync(targetPath(project, 'package.json'))) {
      console.error('Note: Cursor commands are project-level; run this from the target project directory if needed.');
    }
    return [neutralPayload, ...installAdapterDir(path.join(PACKAGE_ROOT, 'adapters', 'cursor'), targetPath(project, '.cursor', 'commands'), neutralPayload)];
  }
  fail(`Unsupported agent: ${agent}`);
}

function printSummary(action, rows) {
  console.log(`\n${action} summary:`);
  const hasStatus = rows.some((row) => row.status);
  console.log(hasStatus ? '| Agent | Status | Path |' : '| Agent | Path |');
  console.log(hasStatus ? '|---|---|---|' : '|---|---|');
  for (const row of rows) {
    if (hasStatus) console.log(`| ${row.agent} | ${row.status || ''} | ${row.path} |`);
    else console.log(`| ${row.agent} | ${row.path} |`);
  }
}

function install(argv) {
  const { agents, project, link } = parseInstallArgs(argv);
  if (link) ensureLinkAllowed();
  const manifest = readManifest();
  let neutralPayload = null;
  if (agents.some((agent) => agent !== 'claude')) {
    if (link) {
      const payloadLink = neutralLinkPath(project);
      linkPayload(payloadLink);
      // Non-Claude adapters point directly at the package root so a global npm update
      // changes the playbook immediately; the payload symlink is left for discovery.
      neutralPayload = PACKAGE_ROOT;
    } else {
      neutralPayload = neutralPayloadPath(project);
      copyPayload(neutralPayload);
    }
  }
  const rows = [];
  for (const agent of agents) {
    for (const target of installOne(agent, project, neutralPayload, link)) rows.push({ agent, path: target });
  }
  recordInstalls(agents, project, link, manifest);
  printSummary('Install', rows);
  if (link) console.log('\nLinked install: run `npm update -g ai-harness-doctor` to update the payload everywhere.');
}

function uninstall(argv) {
  const { agents, project } = parseInstallArgs(argv);
  const rows = [];
  if (agents.includes('claude')) {
    const skillDir = claudeSkillPath(project);
    removeLinkOrPath(skillDir);
    rows.push({ agent: 'claude', path: skillDir });
    for (const name of COMMAND_NAMES) {
      const target = path.join(claudeCommandDir(project), `${name}.md`);
      removeLinkOrPath(target);
      rows.push({ agent: 'claude', path: target });
    }
  }
  if (agents.some((agent) => agent !== 'claude')) {
    const neutral = neutralPayloadPath(project);
    const link = neutralLinkPath(project);
    removeLinkOrPath(link);
    if (neutral !== MANIFEST_DIR || project) removeLinkOrPath(neutral);
    else {
      for (const name of ['SKILL.md', 'scripts', 'references', 'assets']) removeLinkOrPath(path.join(neutral, name));
    }
    rows.push({ agent: 'payload', path: neutral });
  }
  if (agents.includes('codex')) {
    for (const name of COMMAND_NAMES) {
      const target = homePath('.codex', 'prompts', `${name}.md`);
      removeLinkOrPath(target);
      rows.push({ agent: 'codex', path: target });
    }
  }
  if (agents.includes('cursor')) {
    for (const name of COMMAND_NAMES) {
      const target = targetPath(project, '.cursor', 'commands', `${name}.md`);
      removeLinkOrPath(target);
      rows.push({ agent: 'cursor', path: target });
    }
  }
  if (agents.includes('gemini')) {
    const dir = homePath('.gemini', 'commands', 'harness');
    for (const name of ['doctor', 'scan', 'treat', 'drift', 'eval']) {
      const target = path.join(dir, `${name}.toml`);
      removeLinkOrPath(target);
      rows.push({ agent: 'gemini', path: target });
    }
  }
  removeInstallRecords(agents, project);
  printSummary('Uninstall', rows);
}

function updateInstalled() {
  const manifest = readManifest();
  if (!manifest.installs.length) {
    console.log('No ai-harness-doctor installs found. Run `ai-harness-doctor install` first.');
    return;
  }
  console.log(`Deploying ai-harness-doctor ${PACKAGE_VERSION}`);
  const rows = [];
  for (const record of manifest.installs) {
    const project = record.project || null;
    let neutralPayload = null;
    if (record.link) {
      const status = 'refreshed pointers (payload follows npm update -g)';
      if (record.agent === 'claude') {
        for (const target of installClaudeCommands(project)) rows.push({ agent: record.agent, status, path: target });
      } else {
        const payloadLink = neutralLinkPath(project);
        neutralPayload = readSymlinkTarget(payloadLink) || PACKAGE_ROOT;
        for (const target of installOne(record.agent, project, neutralPayload, false)) rows.push({ agent: record.agent, status, path: target });
      }
      continue;
    }
    if (record.agent !== 'claude') {
      neutralPayload = neutralPayloadPath(project);
      copyPayload(neutralPayload);
    }
    const status = `deployed ${PACKAGE_VERSION}`;
    for (const target of installOne(record.agent, project, neutralPayload, false)) {
      rows.push({ agent: record.agent, status, path: target });
    }
  }
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
  printSummary('Update', rows);
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
  maybeCheckForUpdate();
  if (command === 'install') return install(rest);
  if (command === 'uninstall') return uninstall(rest);
  if (command === 'update') return updateInstalled();
  if (['scan', 'plan', 'stubs', 'drift', 'eval'].includes(command)) return runScript(command, rest);
  fail(`Unknown command: ${command}`);
}

main();
