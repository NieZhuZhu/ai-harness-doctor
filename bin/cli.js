#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const https = require('https');
const crypto = require('crypto');
const childProcess = require('child_process');
const runtime = require('./runtime.js');

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
  ai-harness-doctor draft [...args]
  ai-harness-doctor validate [...args]
  ai-harness-doctor stubs [...args]
  ai-harness-doctor drift [...args]
  ai-harness-doctor review [...args]
  ai-harness-doctor eval [...args]
  ai-harness-doctor mcp
  ai-harness-doctor doctor [--self-test] [--json]
  ai-harness-doctor guard [target-repo] [--apply] [--remove] [--provider github|gitlab|codebase|auto]
  ai-harness-doctor help

Examples:
  npx ai-harness-doctor install
  npx ai-harness-doctor install --agent all --project
  npx ai-harness-doctor@latest update
  npm i -g ai-harness-doctor && ai-harness-doctor install --link
  npx ai-harness-doctor scan .
  npx ai-harness-doctor draft . -o AGENTS.md   # fact-derived starter AGENTS.md instead of an empty skeleton
  npx ai-harness-doctor validate .
  npx ai-harness-doctor drift . --strict
  npx ai-harness-doctor review --report drift-report.json   # dry-run by default; add --post for GitHub
  npx ai-harness-doctor doctor --self-test   # verify the Node + Python runtime is ready
  npx ai-harness-doctor guard . --apply
  npx ai-harness-doctor mcp   # start the MCP stdio server (JSON-RPC over newline-delimited JSON)
  npx ai-harness-doctor guard . --apply --provider gitlab
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
  let home = os.homedir();
  try {
    home = fs.realpathSync(home);
  } catch (_) {
    home = path.resolve(home);
  }
  return path.join(home, ...parts);
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

function contentDigest(content) {
  return crypto.createHash('sha256').update(content).digest('hex');
}

function fileDigest(file) {
  try {
    const stat = fs.lstatSync(file);
    if (!stat.isFile()) return null;
    return contentDigest(fs.readFileSync(file));
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function outputMap(outputs) {
  return new Map((outputs || []).filter((item) => item && typeof item.path === 'string').map((item) => [item.path, item]));
}

function managedFileContent(src, playbook) {
  const raw = fs.readFileSync(src);
  if (playbook === undefined) return raw;
  return Buffer.from(replacePlaybook(raw.toString('utf8'), playbook), 'utf8');
}

function writeOwnedFile(src, dest, previous, playbook, mutationRoot) {
  assertSafeMutationPath(mutationRoot || os.homedir(), dest);
  const content = managedFileContent(src, playbook);
  const desiredDigest = contentDigest(content);
  const prior = previous.get(dest);
  let currentDigest = null;
  try {
    const stat = fs.lstatSync(dest);
    if (!stat.isFile()) {
      return { path: dest, status: prior ? 'modified-preserved' : 'manual-merge', managed: prior || null };
    }
    currentDigest = fileDigest(dest);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (currentDigest !== null && !prior) {
    return { path: dest, status: 'manual-merge', managed: null };
  }
  if (currentDigest !== null && currentDigest !== desiredDigest && (!prior || currentDigest !== prior.digest)) {
    return { path: dest, status: prior ? 'modified-preserved' : 'manual-merge', managed: prior || null };
  }
  ensureDir(path.dirname(dest));
  if (currentDigest !== desiredDigest) fs.writeFileSync(dest, content);
  return {
    path: dest,
    status: currentDigest === desiredDigest ? 'unchanged' : (currentDigest === null ? 'created' : 'updated'),
    managed: { path: dest, kind: 'file', digest: desiredDigest },
  };
}

function payloadSources() {
  const files = [];
  function walk(src, rel) {
    for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
      if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue;
      const from = path.join(src, entry.name);
      const childRel = path.join(rel, entry.name);
      if (entry.isDirectory()) walk(from, childRel);
      else if (entry.isFile()) files.push([from, childRel]);
    }
  }
  files.push([path.join(PACKAGE_ROOT, 'SKILL.md'), 'SKILL.md']);
  for (const name of ['scripts', 'references', 'assets']) walk(path.join(PACKAGE_ROOT, name), name);
  return files;
}

function removeEmptyParents(start, stop) {
  let current = path.dirname(start);
  const boundary = path.resolve(stop);
  while (current.startsWith(`${boundary}${path.sep}`) || current === boundary) {
    if (current === boundary) break;
    try {
      fs.rmdirSync(current);
    } catch (_) {
      break;
    }
    current = path.dirname(current);
  }
}

function syncPayload(dest, previousOutputs, mutationRoot) {
  const root = mutationRoot || os.homedir();
  assertSafeMutationPath(root, path.dirname(dest));
  const previous = outputMap(previousOutputs);
  const rows = [];
  const outputs = [];
  const desired = new Set();
  try {
    const stat = fs.lstatSync(dest);
    if (stat.isSymbolicLink()) {
      const prior = previous.get(dest);
      const currentTarget = readSymlinkTarget(dest);
      if (!prior || prior.kind !== 'link' || prior.target !== currentTarget) {
        fail(`Refusing to replace unowned payload link: ${dest}`);
      }
      fs.unlinkSync(dest);
      rows.push({ path: dest, status: 'link-retired' });
    } else if (!stat.isDirectory()) {
      fail(`Refusing to replace non-directory payload path: ${dest}`);
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  assertSafeMutationPath(root, dest);
  for (const [src, rel] of payloadSources()) {
    const target = path.join(dest, rel);
    desired.add(target);
    const result = writeOwnedFile(src, target, previous, undefined, mutationRoot);
    rows.push({ path: target, status: result.status });
    if (result.managed) outputs.push(result.managed);
  }
  for (const prior of previous.values()) {
    if (prior.kind !== 'file' || desired.has(prior.path) || !prior.path.startsWith(`${dest}${path.sep}`)) continue;
    if (fileDigest(prior.path) === prior.digest) {
      fs.unlinkSync(prior.path);
      removeEmptyParents(prior.path, dest);
      rows.push({ path: prior.path, status: 'removed-stale' });
    } else {
      outputs.push(prior);
      rows.push({ path: prior.path, status: 'modified-preserved' });
    }
  }
  return { rows, outputs };
}

function directoryMatchesOwnedFiles(directory, previousOutputs) {
  const expected = new Map(
    (previousOutputs || [])
      .filter((output) => output.kind === 'file' && output.path.startsWith(`${directory}${path.sep}`))
      .map((output) => [output.path, output.digest])
  );
  if (!expected.size) return false;
  const actual = [];
  function walk(current) {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const child = path.join(current, entry.name);
      if (entry.isDirectory()) {
        if (!walk(child)) return false;
      } else if (entry.isFile()) {
        actual.push(child);
      } else {
        return false;
      }
    }
    return true;
  }
  try {
    if (!fs.lstatSync(directory).isDirectory() || !walk(directory)) return false;
  } catch (_) {
    return false;
  }
  return actual.length === expected.size && actual.every((file) => expected.get(file) === fileDigest(file));
}

function readManifest() {
  try {
    const parsed = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
    if (!parsed || typeof parsed !== 'object') throw new Error('bad manifest');
    if (!Array.isArray(parsed.installs)) parsed.installs = [];
    if (typeof parsed.schemaVersion !== 'number') parsed.schemaVersion = 1;
    if (typeof parsed.lastUpdateCheck !== 'number') parsed.lastUpdateCheck = 0;
    if (typeof parsed.version !== 'string') parsed.version = PACKAGE_VERSION;
    return parsed;
  } catch (_) {
    return { schemaVersion: 2, version: PACKAGE_VERSION, lastUpdateCheck: 0, installs: [] };
  }
}

function writeManifest(manifest) {
  ensureDir(MANIFEST_DIR);
  manifest.schemaVersion = 2;
  fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
}

function sameInstall(a, b) {
  return (
    a.agent === b.agent &&
    (a.project || null) === (b.project || null) &&
    (a.agent !== 'cursor' || (a.targetRoot || null) === (b.targetRoot || null))
  );
}

function recordInstalls(records, manifest) {
  manifest = manifest || readManifest();
  for (const record of records) {
    const idx = manifest.installs.findIndex((item) => sameInstall(item, record));
    if (idx >= 0) manifest.installs[idx] = record;
    else manifest.installs.push(record);
  }
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
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

function compareIdentifiers(a, b) {
  // Compare two dot-separated identifier lists (used for both the main version
  // and the pre-release). Numeric identifiers compare numerically; when either
  // side is non-numeric fall back to ASCII string comparison.
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const va = a[i] === undefined ? 0 : a[i];
    const vb = b[i] === undefined ? 0 : b[i];
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

function comparePreRelease(a, b) {
  // SemVer §11: identifiers are compared left to right. Numeric identifiers
  // always have LOWER precedence than alphanumeric ones. A larger set of
  // pre-release fields (with all preceding fields equal) has higher precedence.
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    if (a[i] === undefined) return -1;
    if (b[i] === undefined) return 1;
    const va = a[i];
    const vb = b[i];
    const aNum = typeof va === 'number';
    const bNum = typeof vb === 'number';
    if (aNum && bNum) {
      if (va !== vb) return va > vb ? 1 : -1;
    } else if (aNum !== bNum) {
      // Numeric < alphanumeric.
      return aNum ? -1 : 1;
    } else {
      const sa = String(va);
      const sb = String(vb);
      if (sa !== sb) return sa > sb ? 1 : -1;
    }
  }
  return 0;
}

function compareVersions(a, b) {
  // Split off SemVer build metadata ('+...', ignored for precedence) and the
  // pre-release tag (everything after the first '-') from the main version.
  const parse = (v) => {
    const [core, pre] = String(v).split('+')[0].split(/-(.*)/s);
    const toParts = (s) => s.split('.').map((part) => (/^\d+$/.test(part) ? Number(part) : part));
    return {
      main: toParts(core),
      pre: pre === undefined || pre === '' ? [] : toParts(pre),
    };
  };
  const pa = parse(a);
  const pb = parse(b);

  // 1) Compare the main version (major.minor.patch...) first.
  const mainCmp = compareIdentifiers(pa.main, pb.main);
  if (mainCmp !== 0) return mainCmp;

  // 2) Main versions equal: a normal release outranks a pre-release of the same
  //    version, so `1.0.0` > `1.0.0-alpha` (SemVer §11.3).
  if (pa.pre.length === 0 && pb.pre.length === 0) return 0;
  if (pa.pre.length === 0) return 1;
  if (pb.pre.length === 0) return -1;

  // 3) Both are pre-releases: compare their identifiers.
  return comparePreRelease(pa.pre, pb.pre);
}

function maybeCheckForUpdate() {
  try {
    if (process.env.AI_HARNESS_DOCTOR_NO_UPDATE_CHECK === '1') return;
    // Internal testability hook: bypass only the TTY and 24h throttle gates.
    const force = process.env.AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK === '1';
    if (!force && !process.stderr.isTTY) return;
    const manifest = readManifest();
    const now = Date.now();
    if (!force && now - manifest.lastUpdateCheck < UPDATE_CHECK_INTERVAL_MS) return;
    manifest.lastUpdateCheck = now;
    writeManifest(manifest);

    // Internal testability hook: override the registry base URL used for checks.
    const updateUrl = process.env.AI_HARNESS_DOCTOR_REGISTRY
      ? new URL('ai-harness-doctor/latest', process.env.AI_HARNESS_DOCTOR_REGISTRY).toString()
      : UPDATE_CHECK_URL;
    const transport = updateUrl.startsWith('http:') ? http : https;

    let done = false;
    let timeout;
    const finish = () => {
      if (done) return;
      done = true;
      if (timeout) clearTimeout(timeout);
    };
    const safe = (fn) => (...args) => {
      try {
        return fn(...args);
      } catch (_) {
        finish();
        return undefined;
      }
    };
    const req = transport.get(updateUrl, safe((res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', safe((chunk) => {
        body += chunk;
        if (body.length > 4096) req.destroy();
      }));
      res.on('end', safe(() => {
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
      }));
    }));
    req.on('socket', safe((socket) => {
      socket.unref();
    }));
    req.on('error', safe(() => finish()));
    timeout = setTimeout(safe(() => {
      finish();
      req.destroy();
    }), 1500);
    timeout.unref();
  } catch (_) {
    // The update nudge must never crash or delay the main command.
  }
}

function replacePlaybook(content, playbook) {
  const token = '\\{\\{' + 'PLAYBOOK' + '\\}\\}';
  return content.replace(new RegExp(token, 'g'), playbook);
}

function installAdapterDir(srcDir, destDir, playbook, previousOutputs, mutationRoot) {
  assertSafeMutationPath(mutationRoot || os.homedir(), destDir);
  ensureDir(destDir);
  const previous = outputMap(previousOutputs);
  const rows = [];
  const outputs = [];
  for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const src = path.join(srcDir, entry.name);
    const dest = path.join(destDir, entry.name);
    const result = writeOwnedFile(src, dest, previous, playbook, mutationRoot);
    rows.push({ path: dest, status: result.status });
    if (result.managed) outputs.push(result.managed);
  }
  return { rows, outputs };
}

function installGemini(playbook, project, previousOutputs) {
  void project;
  const dest = homePath('.gemini', 'commands', 'harness');
  return installAdapterDir(
    path.join(PACKAGE_ROOT, 'adapters', 'gemini', 'harness'),
    dest,
    playbook,
    previousOutputs,
    os.homedir()
  );
}

function neutralPayloadPath(project) {
  return project ? path.join(project, '.ai-harness-doctor', 'payload') : homePath('.ai-harness-doctor', 'payload');
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

function installClaude(project, link, previousOutputs) {
  const skillDir = claudeSkillPath(project);
  if (link) {
    const linked = syncOwnedLink(skillDir, PACKAGE_ROOT, previousOutputs, project || os.homedir());
    const commands = installClaudeCommands(project, previousOutputs);
    return {
      rows: [...linked.rows, ...commands.rows],
      outputs: [...linked.outputs, ...commands.outputs],
    };
  }
  const mutationRoot = project || os.homedir();
  const payload = syncPayload(skillDir, previousOutputs, mutationRoot);
  const commands = installClaudeCommands(project, previousOutputs);
  return {
    rows: [...payload.rows, ...commands.rows],
    outputs: [...payload.outputs, ...commands.outputs],
  };
}

function installClaudeCommands(project, previousOutputs) {
  const commandDir = claudeCommandDir(project);
  const mutationRoot = project || os.homedir();
  const previous = outputMap(previousOutputs);
  const rows = [];
  const outputs = [];
  for (const name of COMMAND_NAMES) {
    const file = `${name}.md`;
    const dest = path.join(commandDir, file);
    const result = writeOwnedFile(
      path.join(PACKAGE_ROOT, 'commands', file),
      dest,
      previous,
      undefined,
      mutationRoot
    );
    rows.push({ path: dest, status: result.status });
    if (result.managed) outputs.push(result.managed);
  }
  return { rows, outputs };
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

function expectedFileOutput(src, dest, playbook) {
  return { path: dest, kind: 'file', digest: contentDigest(managedFileContent(src, playbook)) };
}

function legacyPayloadOutputs(project) {
  const legacyRoot = project ? path.join(project, '.ai-harness-doctor') : MANIFEST_DIR;
  const outputs = [];
  for (const [src, rel] of payloadSources()) {
    const expected = expectedFileOutput(src, path.join(legacyRoot, rel));
    if (fileDigest(expected.path) === expected.digest) outputs.push(expected);
  }
  return outputs;
}

function legacyOutputsForRecord(record) {
  if (Array.isArray(record.outputs)) return record.outputs;
  const project = record.project || null;
  const outputs = [];
  if (record.agent === 'claude') {
    const skillDir = claudeSkillPath(project);
    if (record.link) {
      const target = readSymlinkTarget(skillDir);
      if (target) outputs.push({ path: skillDir, kind: 'link', target });
    } else {
      for (const [src, rel] of payloadSources()) {
        const expected = expectedFileOutput(src, path.join(skillDir, rel));
        if (fileDigest(expected.path) === expected.digest) outputs.push(expected);
      }
    }
    for (const name of COMMAND_NAMES) {
      const file = `${name}.md`;
      const expected = expectedFileOutput(
        path.join(PACKAGE_ROOT, 'commands', file),
        path.join(claudeCommandDir(project), file)
      );
      if (fileDigest(expected.path) === expected.digest) outputs.push(expected);
    }
    return outputs;
  }
  const oldPayload = project ? path.join(project, '.ai-harness-doctor') : MANIFEST_DIR;
  outputs.push(...legacyPayloadOutputs(project));
  let srcDir;
  let destDir;
  if (record.agent === 'cursor') {
    srcDir = path.join(PACKAGE_ROOT, 'adapters', 'cursor');
    destDir = targetPath(project, '.cursor', 'commands');
  } else if (record.agent === 'codex') {
    srcDir = path.join(PACKAGE_ROOT, 'adapters', 'codex');
    destDir = homePath('.codex', 'prompts');
  } else if (record.agent === 'gemini') {
    srcDir = path.join(PACKAGE_ROOT, 'adapters', 'gemini', 'harness');
    destDir = homePath('.gemini', 'commands', 'harness');
  }
  if (srcDir) {
    for (const entry of fs.readdirSync(srcDir, { withFileTypes: true })) {
      if (!entry.isFile()) continue;
      const expected = expectedFileOutput(
        path.join(srcDir, entry.name),
        path.join(destDir, entry.name),
        oldPayload
      );
      if (fileDigest(expected.path) === expected.digest) outputs.push(expected);
    }
  }
  return outputs;
}

function pathIsWithin(candidate, root) {
  const relative = path.relative(path.resolve(root), path.resolve(candidate));
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function cursorRootFromOutput(outputPath) {
  const marker = `${path.sep}.cursor${path.sep}commands${path.sep}`;
  const index = path.resolve(outputPath).lastIndexOf(marker);
  return index === -1 ? null : path.resolve(outputPath).slice(0, index);
}

function effectiveCursorRoot(record) {
  if (record.targetRoot) return path.resolve(record.targetRoot);
  if (record.project) return path.resolve(record.project);
  const cursorOutput = (record.outputs || []).find(
    (output) => output.kind === 'file' && cursorRootFromOutput(output.path)
  );
  return cursorOutput ? cursorRootFromOutput(cursorOutput.path) : null;
}

function adapterOutputPaths(agent, project, targetRoot) {
  if (agent === 'cursor') {
    const root = targetRoot || project || process.cwd();
    return new Set(COMMAND_NAMES.map((name) => targetPath(root, '.cursor', 'commands', `${name}.md`)));
  }
  if (agent === 'codex') {
    return new Set(COMMAND_NAMES.map((name) => homePath('.codex', 'prompts', `${name}.md`)));
  }
  if (agent === 'gemini') {
    return new Set(['doctor', 'scan', 'treat', 'drift', 'eval'].map(
      (name) => homePath('.gemini', 'commands', 'harness', `${name}.toml`)
    ));
  }
  return new Set();
}

function outputAllowedForRecord(record, output) {
  if (!output || typeof output.path !== 'string' || !['file', 'link'].includes(output.kind)) return false;
  const project = record.project || null;
  const outputPath = path.resolve(output.path);
  if (record.agent === 'claude') {
    const skillDir = claudeSkillPath(project);
    if (output.kind === 'link') return outputPath === path.resolve(skillDir);
    if (pathIsWithin(outputPath, skillDir)) return true;
    return COMMAND_NAMES.some(
      (name) => outputPath === path.resolve(claudeCommandDir(project), `${name}.md`)
    );
  }
  const payload = neutralPayloadPath(project);
  if (output.kind === 'link' && outputPath === path.resolve(payload)) return true;
  if (output.kind === 'file' && pathIsWithin(outputPath, payload)) return true;
  const legacyRoot = project ? path.join(project, '.ai-harness-doctor') : MANIFEST_DIR;
  if (output.kind === 'file') {
    if (outputPath === path.resolve(legacyRoot, 'SKILL.md')) return true;
    for (const name of ['scripts', 'references', 'assets']) {
      if (pathIsWithin(outputPath, path.join(legacyRoot, name))) return true;
    }
  }
  return output.kind === 'file' && adapterOutputPaths(
    record.agent,
    project,
    record.agent === 'cursor' ? effectiveCursorRoot(record) : null
  ).has(outputPath);
}

function recordWithOutputs(record) {
  return {
    ...record,
    outputs: legacyOutputsForRecord(record).filter((output) => outputAllowedForRecord(record, output)),
  };
}

function outputKey(output) {
  return `${output.kind}:${output.path}`;
}

function mutationRootForRecord(record, output) {
  const home = homePath();
  if (pathIsWithin(output.path, home)) return home;
  if (record.project) return record.project;
  if (record.agent === 'cursor') return effectiveCursorRoot(record);
  return home;
}

function removeOwnedOutput(record, output) {
  const root = mutationRootForRecord(record, output);
  if (!root) return 'modified-preserved';
  if (output.kind === 'link') {
    assertSafeMutationPath(root, path.dirname(output.path));
    if (readSymlinkTarget(output.path) === output.target) {
      fs.unlinkSync(output.path);
      return 'removed';
    }
    return 'modified-preserved';
  }
  assertSafeMutationPath(root, output.path);
  if (output.kind === 'file' && fileDigest(output.path) === output.digest) {
    fs.unlinkSync(output.path);
    return 'removed';
  }
  return 'modified-preserved';
}

function cleanupBoundary(record, output) {
  const project = record.project || null;
  const payload = record.agent === 'claude' ? claudeSkillPath(project) : neutralPayloadPath(project);
  if (pathIsWithin(output.path, payload)) {
    return record.agent === 'claude'
      ? path.dirname(payload)
      : (project ? path.join(project, '.ai-harness-doctor') : MANIFEST_DIR);
  }
  if (record.agent !== 'claude') {
    const legacyRoot = project ? path.join(project, '.ai-harness-doctor') : MANIFEST_DIR;
    for (const name of ['scripts', 'references', 'assets']) {
      if (pathIsWithin(output.path, path.join(legacyRoot, name))) return legacyRoot;
    }
  }
  return path.dirname(output.path);
}

function cleanupUnreferencedOutputs(previousRecords, nextRecords) {
  const keep = new Set(nextRecords.flatMap((record) => record.outputs || []).map(outputKey));
  const keptLinks = nextRecords
    .flatMap((record) => record.outputs || [])
    .filter((output) => output.kind === 'link')
    .map((output) => output.path);
  const seen = new Set();
  const rows = [];
  for (const record of previousRecords) {
    for (const output of record.outputs || []) {
      const key = outputKey(output);
      if (keep.has(key) || seen.has(key)) continue;
      if (keptLinks.some((link) => output.path.startsWith(`${link}${path.sep}`))) continue;
      seen.add(key);
      const status = removeOwnedOutput(record, output);
      rows.push({ path: output.path, status });
      if (status === 'removed') {
        removeEmptyParents(output.path, cleanupBoundary(record, output));
      }
    }
  }
  return rows;
}

function syncOwnedLink(dest, target, previousOutputs, mutationRoot) {
  const root = mutationRoot || os.homedir();
  assertSafeMutationPath(root, path.dirname(dest));
  const previous = outputMap(previousOutputs);
  const prior = previous.get(dest);
  const currentTarget = readSymlinkTarget(dest);
  if (currentTarget === target) {
    return { rows: [{ path: dest, status: 'unchanged' }], outputs: [{ path: dest, kind: 'link', target }] };
  }
  if (currentTarget && (!prior || currentTarget !== prior.target)) {
    return {
      rows: [{ path: dest, status: prior ? 'modified-preserved' : 'manual-merge' }],
      outputs: prior ? [prior] : [],
    };
  }
  if (fs.existsSync(dest) && !currentTarget) {
    if (directoryMatchesOwnedFiles(dest, previousOutputs)) {
      removePath(dest);
    } else {
      return {
        rows: [{
          path: dest,
          status: (previousOutputs || []).length ? 'modified-preserved' : 'manual-merge',
        }],
        outputs: (previousOutputs || []).filter(
          (output) => output.path === dest || output.path.startsWith(`${dest}${path.sep}`)
        ),
      };
    }
  }
  if (currentTarget) fs.unlinkSync(dest);
  assertSafeMutationPath(root, dest);
  symlinkDirectory(target, dest);
  return { rows: [{ path: dest, status: 'linked' }], outputs: [{ path: dest, kind: 'link', target }] };
}

function installOne(agent, project, neutralPayload, link, previousOutputs, targetRoot) {
  if (agent === 'claude') return installClaude(project, link, previousOutputs);
  if (agent === 'codex') {
    return installAdapterDir(
      path.join(PACKAGE_ROOT, 'adapters', 'codex'),
      homePath('.codex', 'prompts'),
      neutralPayload,
      previousOutputs,
      os.homedir()
    );
  }
  if (agent === 'gemini') {
    return installGemini(neutralPayload, project, previousOutputs);
  }
  if (agent === 'cursor') {
    if (!fs.existsSync(targetPath(project, '.git')) && !fs.existsSync(targetPath(project, 'package.json'))) {
      console.error('Note: Cursor commands are project-level; run this from the target project directory if needed.');
    }
    return installAdapterDir(
      path.join(PACKAGE_ROOT, 'adapters', 'cursor'),
      targetPath(targetRoot || project, '.cursor', 'commands'),
      neutralPayload,
      previousOutputs,
      targetRoot || project || process.cwd()
    );
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
  const parsed = parseInstallArgs(argv);
  let { agents } = parsed;
  const { project, link } = parsed;
  if (link) ensureLinkAllowed();
  const manifest = readManifest();
  const previousRecords = manifest.installs.map(recordWithOutputs);
  const cursorTargetRoot = agents.includes('cursor')
    ? fs.realpathSync(project || process.cwd())
    : null;
  const matchesRequest = (record, agent) => {
    if (record.agent !== agent || (record.project || null) !== (project || null)) return false;
    if (agent !== 'cursor') return true;
    return effectiveCursorRoot(record) === cursorTargetRoot;
  };
  if (agents.some((agent) => agent !== 'claude')) {
    const sharedAgents = previousRecords
      .filter(
        (record) =>
          record.agent !== 'claude' &&
          (record.project || null) === (project || null) &&
          (record.agent !== 'cursor' || effectiveCursorRoot(record) === cursorTargetRoot) &&
          Boolean(record.link) !== Boolean(link)
      )
      .map((record) => record.agent);
    agents = [...new Set([...agents, ...sharedAgents])];
  }
  const untouchedRecords = previousRecords.filter(
    (record) => !agents.some((agent) => matchesRequest(record, agent))
  );
  const previousByAgent = new Map(
    previousRecords
      .filter((record) => agents.some((agent) => matchesRequest(record, agent)))
      .map((record) => [record.agent, record])
  );
  let neutralPayload = null;
  let payloadResult = { rows: [], outputs: [] };
  if (agents.some((agent) => agent !== 'claude')) {
    if (link) {
      const payloadLink = neutralLinkPath(project);
      const priorOutputs = previousRecords
        .filter((record) => record.agent !== 'claude' && (record.project || null) === (project || null))
        .flatMap((record) => record.outputs || []);
      payloadResult = syncOwnedLink(payloadLink, PACKAGE_ROOT, priorOutputs, project || os.homedir());
      // Non-Claude adapters point directly at the package root so a global npm update
      // changes the playbook immediately; the payload symlink is left for discovery.
      neutralPayload = PACKAGE_ROOT;
    } else {
      neutralPayload = neutralPayloadPath(project);
      const priorOutputs = previousRecords
        .filter((record) => record.agent !== 'claude' && (record.project || null) === (project || null))
        .flatMap((record) => record.outputs || []);
      payloadResult = syncPayload(neutralPayload, priorOutputs, project || os.homedir());
    }
  }
  const rows = [];
  const newRecords = [];
  for (const agent of agents) {
    const previous = previousByAgent.get(agent);
    const targetRoot = agent === 'cursor' ? cursorTargetRoot : null;
    const installed = installOne(
      agent,
      project,
      neutralPayload,
      link,
      previous ? previous.outputs : [],
      targetRoot
    );
    for (const row of installed.rows) rows.push({ agent, ...row });
    const outputs = [
      ...(agent === 'claude' ? [] : payloadResult.outputs),
      ...installed.outputs,
    ];
    newRecords.push({
      agent,
      project: project || null,
      ...(targetRoot ? { targetRoot } : {}),
      link: Boolean(link),
      installedAt: new Date().toISOString(),
      outputs,
    });
  }
  for (const row of payloadResult.rows) rows.unshift({ agent: 'payload', ...row });
  const nextRecords = [...untouchedRecords, ...newRecords];
  for (const row of cleanupUnreferencedOutputs(previousRecords, nextRecords)) {
    rows.push({ agent: 'cleanup', ...row });
  }
  manifest.installs = nextRecords;
  recordInstalls([], manifest);
  printSummary('Install', rows);
  if (link) console.log('\nLinked install: run `npm update -g ai-harness-doctor` to update the payload everywhere.');
}

function uninstall(argv) {
  const { agents, project } = parseInstallArgs(argv);
  const manifest = readManifest();
  const previousRecords = manifest.installs.map(recordWithOutputs);
  const cursorTargetRoot = agents.includes('cursor')
    ? fs.realpathSync(project || process.cwd())
    : null;
  const matchesRequest = (record, agent) => {
    if (record.agent !== agent || (record.project || null) !== (project || null)) return false;
    if (agent !== 'cursor') return true;
    return effectiveCursorRoot(record) === cursorTargetRoot;
  };
  const removedRecords = previousRecords.filter(
    (record) => agents.some((agent) => matchesRequest(record, agent))
  );
  const remainingRecords = previousRecords.filter(
    (record) => !agents.some((agent) => matchesRequest(record, agent))
  );
  const rows = [];
  const keep = new Set(remainingRecords.flatMap((record) => record.outputs || []).map(outputKey));
  const seen = new Set();
  const preservedRecords = [];
  for (const record of removedRecords) {
    const preservedOutputs = [];
    for (const output of record.outputs || []) {
      const key = outputKey(output);
      if (keep.has(key) || seen.has(key)) continue;
      seen.add(key);
      const status = removeOwnedOutput(record, output);
      rows.push({ agent: record.agent, path: output.path, status });
      if (status === 'modified-preserved') preservedOutputs.push(output);
      if (status === 'removed') {
        removeEmptyParents(output.path, cleanupBoundary(record, output));
      }
    }
    if (preservedOutputs.length) {
      preservedRecords.push({ ...record, orphaned: true, outputs: preservedOutputs });
    }
  }
  manifest.installs = [...remainingRecords, ...preservedRecords];
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
  printSummary('Uninstall', rows);
}

function updateInstalled() {
  const manifest = readManifest();
  if (!manifest.installs.length) {
    console.log('No ai-harness-doctor installs found. Run `ai-harness-doctor install` first.');
    return;
  }
  console.log(`Deploying ai-harness-doctor ${PACKAGE_VERSION}`);
  const previousRecords = manifest.installs.map(recordWithOutputs);
  const rows = [];
  const nextRecords = [];
  const payloadCache = new Map();
  for (const record of previousRecords) {
    if (record.orphaned) {
      nextRecords.push(record);
      rows.push({ agent: record.agent, status: 'orphaned-preserved', path: record.outputs[0]?.path || '(none)' });
      continue;
    }
    const project = record.project || null;
    let neutralPayload = null;
    let payloadResult = { rows: [], outputs: [] };
    if (record.link) {
      const status = 'refreshed pointers (payload follows npm update -g)';
      if (record.agent === 'claude') {
        const installed = installClaude(project, true, record.outputs);
        rows.push(...installed.rows.map((row) => ({ agent: record.agent, status: row.status || status, path: row.path })));
        nextRecords.push({ ...record, installedAt: new Date().toISOString(), outputs: installed.outputs });
      } else {
        const payloadLink = neutralLinkPath(project);
        const cacheKey = `link:${payloadLink}`;
        if (!payloadCache.has(cacheKey)) {
          const shared = previousRecords
            .filter((item) => item.link && item.agent !== 'claude' && (item.project || null) === (project || null))
            .flatMap((item) => item.outputs || []);
          payloadCache.set(
            cacheKey,
            syncOwnedLink(payloadLink, PACKAGE_ROOT, shared, project || os.homedir())
          );
        }
        payloadResult = payloadCache.get(cacheKey);
        neutralPayload = PACKAGE_ROOT;
        const installed = installOne(
          record.agent,
          project,
          neutralPayload,
          true,
          record.outputs,
          record.targetRoot || null
        );
        rows.push(...installed.rows.map((row) => ({ agent: record.agent, status: row.status || status, path: row.path })));
        nextRecords.push({
          ...record,
          installedAt: new Date().toISOString(),
          outputs: [...payloadResult.outputs, ...installed.outputs],
        });
      }
      continue;
    }
    if (record.agent !== 'claude') {
      neutralPayload = neutralPayloadPath(project);
      const cacheKey = `copy:${neutralPayload}`;
      if (!payloadCache.has(cacheKey)) {
        const shared = previousRecords
          .filter((item) => !item.link && item.agent !== 'claude' && (item.project || null) === (project || null))
          .flatMap((item) => item.outputs || []);
        payloadCache.set(cacheKey, syncPayload(neutralPayload, shared, project || os.homedir()));
      }
      payloadResult = payloadCache.get(cacheKey);
    }
    const installed = installOne(
      record.agent,
      project,
      neutralPayload,
      false,
      record.outputs,
      record.targetRoot || null
    );
    rows.push(...installed.rows.map((row) => ({ agent: record.agent, status: row.status, path: row.path })));
    nextRecords.push({
      ...record,
      installedAt: new Date().toISOString(),
      outputs: [...(record.agent === 'claude' ? [] : payloadResult.outputs), ...installed.outputs],
    });
  }
  for (const result of payloadCache.values()) {
    rows.unshift(...result.rows.map((row) => ({ agent: 'payload', ...row })));
  }
  rows.push(...cleanupUnreferencedOutputs(previousRecords, nextRecords).map((row) => ({ agent: 'cleanup', ...row })));
  manifest.installs = nextRecords;
  manifest.version = PACKAGE_VERSION;
  writeManifest(manifest);
  printSummary('Update', rows);
}

// Single source of truth for the Python-backed subcommands: command name -> the
// script file plus any fixed leading args. Both the dispatcher and `doctor
// --self-test` iterate this map so they can never disagree about what exists.
const SCRIPT_COMMANDS = {
  scan: ['scan.py'],
  plan: ['canonicalize.py', '--plan'],
  draft: ['canonicalize.py', '--draft'],
  validate: ['canonicalize.py', '--validate'],
  stubs: ['canonicalize.py', '--write-stubs'],
  drift: ['check_drift.py'],
  review: ['pr_review.py'],
  eval: ['eval_run.py'],
};

function resolvePython() {
  const found = runtime.findPython();
  if (found.ok) return found.command;
  // Clean, actionable message — never a raw stack trace.
  fail(runtime.pythonMissingMessage(found.tried));
}

function runScript(command, argv) {
  const spec = SCRIPT_COMMANDS[command];
  if (!spec) fail(`Unknown command: ${command}`);
  const python = resolvePython();
  const script = path.join(PACKAGE_ROOT, 'scripts', spec[0]);
  if (!fs.existsSync(script)) fail(`Script not found: ${script}`);
  const result = childProcess.spawnSync(python, [script, ...spec.slice(1), ...argv], { stdio: 'inherit' });
  if (result.error) fail(result.error.message);
  process.exit(result.status === null ? 1 : result.status);
}

// Runtime self-test rows: Node, the resolved Python interpreter, and every
// Python engine + the MCP server file. `env`/`spawn` are injectable for tests.
function runtimeChecks(env = process.env, spawn) {
  const checks = [];
  checks.push({ name: 'node', ok: true, detail: process.version });
  const py = runtime.findPython(env, spawn);
  checks.push(py.ok
    ? { name: 'python', ok: true, detail: `${py.command} (Python ${py.version})` }
    : { name: 'python', ok: false, detail: `not found (tried ${py.tried.join(', ')})` });
  for (const [command, spec] of Object.entries(SCRIPT_COMMANDS)) {
    const script = path.join(PACKAGE_ROOT, 'scripts', spec[0]);
    const present = fs.existsSync(script);
    checks.push({ name: `script:${command}`, ok: present, detail: present ? spec[0] : `missing ${spec[0]}` });
  }
  const mcp = path.join(__dirname, 'mcp-server.js');
  const mcpPresent = fs.existsSync(mcp);
  checks.push({ name: 'mcp-server', ok: mcpPresent, detail: mcpPresent ? 'mcp-server.js' : 'missing mcp-server.js' });
  return checks;
}

function parseDoctorArgs(argv) {
  let asJson = false;
  for (const arg of argv) {
    if (arg === '--self-test') continue; // default action; accepted for clarity
    else if (arg === '--json') asJson = true;
    else fail(`Unknown option: ${arg}`);
  }
  return { asJson };
}

function doctor(argv) {
  const { asJson } = parseDoctorArgs(argv);
  const checks = runtimeChecks();
  const ok = checks.every((check) => check.ok);
  if (asJson) {
    console.log(JSON.stringify({ ok, version: PACKAGE_VERSION, node: process.version, checks }, null, 2));
  } else {
    console.log(`ai-harness-doctor self-test (v${PACKAGE_VERSION})`);
    console.log('| Check | Status | Detail |');
    console.log('|---|---|---|');
    for (const check of checks) console.log(`| ${check.name} | ${check.ok ? 'ok' : 'FAIL'} | ${check.detail} |`);
    if (ok) {
      console.log('\nAll runtime checks passed.');
    } else {
      console.log('\nSome runtime checks FAILED.');
      console.log(runtime.pythonMissingMessage(runtime.findPython().tried));
    }
  }
  process.exit(ok ? 0 : 1);
}

function parseGuardArgs(argv) {
  let target = '.';
  let apply = false;
  let remove = false;
  let provider = 'auto';
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--apply') apply = true;
    else if (arg === '--remove') remove = true;
    else if (arg === '--provider') { provider = argv[i + 1]; i += 1; }
    else if (arg.startsWith('--provider=')) provider = arg.slice('--provider='.length);
    else if (arg.startsWith('--')) fail(`Unknown option: ${arg}`);
    else target = arg;
  }
  const allowed = ['auto', 'github', 'gitlab', 'codebase'];
  if (!allowed.includes(provider)) fail(`Unknown provider: ${provider} (expected ${allowed.join(', ')})`);
  return { target: path.resolve(process.cwd(), target), apply, remove, provider };
}

// CI provider adapter layer: each provider maps to a set of [repoRelativePath,
// templateName] pairs under assets/guard/. The pre-commit hook and the AGENTS.md
// maintenance contract are provider-agnostic and installed for every provider.
const GUARD_CI_FILES = {
  github: [
    ['.github/workflows/harness-drift.yml', 'harness-drift.yml'],
    ['.github/workflows/harness-checkup.yml', 'harness-checkup.yml'],
  ],
  gitlab: [
    ['.gitlab/harness-ci.yml', 'gitlab/harness-ci.yml'],
  ],
  codebase: [
    ['.harness-ci/harness-guard.sh', 'codebase/harness-guard.sh'],
    ['.harness-ci/README.md', 'codebase/README.md'],
    ['.codebase/pipelines/harness-guard.yaml', 'codebase/harness-guard.yaml'],
  ],
};

const GUARD_PROVIDER_NOTES = {
  gitlab: 'Add `include: { local: .gitlab/harness-ci.yml }` to your .gitlab-ci.yml to activate the drift/checkup jobs.',
  codebase: 'Installed `.codebase/pipelines/harness-guard.yaml` (change=drift, cron=checkup) wired to `.harness-ci/harness-guard.sh`. Register the cron schedule in Codebase CI \u2192 Schedules; the runner must have `ai-harness-doctor` pre-installed or npm pointed at the internal mirror. See .harness-ci/README.md.',
};

function detectProvider(target) {
  if (fs.existsSync(path.join(target, '.gitlab-ci.yml'))) return 'gitlab';
  const remote = (commandOutput('git', ['remote', 'get-url', 'origin'], target) || '').toLowerCase();
  if (remote) {
    if (remote.includes('github')) return 'github';
    if (remote.includes('gitlab')) return 'gitlab';
    // Any other enterprise git host (e.g. internal Codebase) → portable script.
    return 'codebase';
  }
  return 'github';
}

function guardTemplate(name) {
  return fs.readFileSync(path.join(PACKAGE_ROOT, 'assets', 'guard', name), 'utf8');
}

// Marker embedded in every managed guard template. Presence signals a file is
// (or was) tool-managed; byte-identity to the shipped template signals it is
// pristine and therefore safe to remove/overwrite without losing user edits.
const GUARD_MARKER = 'ai-harness-doctor:guard';

// Map every repo-relative CI file name (across all providers) to its template,
// so remove/re-install can compare on-disk content against what we would ship.
const GUARD_CI_TEMPLATE_BY_NAME = (() => {
  const map = new Map();
  for (const files of Object.values(GUARD_CI_FILES)) {
    for (const [name, template] of files) map.set(name, template);
  }
  return map;
})();

function isPristineManaged(currentContent, templateContent) {
  if (currentContent == null) return false;
  return currentContent === templateContent;
}

// Remove the exact shipped guard template block from a hand-extended hook,
// preserving any user-authored content around it. Returns null when the shipped
// block is not present contiguously (so the caller can avoid destroying it).
function stripGuardBlock(content, template) {
  const idx = content.indexOf(template);
  if (idx === -1) return null;
  return content.slice(0, idx) + content.slice(idx + template.length);
}

function commandOutput(command, args, cwd) {
  const result = childProcess.spawnSync(command, args, { cwd, encoding: 'utf8' });
  if (result.error || result.status !== 0) return null;
  return String(result.stdout || '').trim();
}

function isGitRepo(target) {
  return commandOutput('git', ['rev-parse', '--is-inside-work-tree'], target) === 'true';
}

function gitPath(target, gitRelativePath) {
  const output = commandOutput('git', ['rev-parse', '--git-path', gitRelativePath], target);
  if (!output) return path.join(target, '.git', gitRelativePath);
  return path.isAbsolute(output) ? output : path.join(target, output);
}

function gitCommonDir(target) {
  const output = commandOutput('git', ['rev-parse', '--git-common-dir'], target);
  if (!output) fail(`Cannot resolve git directory for ${target}`);
  const absolute = path.isAbsolute(output) ? output : path.join(target, output);
  return fs.realpathSync(absolute);
}

function assertSafeMutationPath(root, target) {
  const base = fs.realpathSync(root);
  const absolute = path.resolve(target);
  const relative = path.relative(base, absolute);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
    fail(`Refusing unsafe mutation outside ${base}: ${absolute}`);
  }
  let current = base;
  for (const part of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    try {
      if (fs.lstatSync(current).isSymbolicLink()) {
        fail(`Refusing unsafe mutation through symlink: ${current}`);
      }
    } catch (error) {
      if (error.code === 'ENOENT') break;
      throw error;
    }
  }
  return absolute;
}

function readTextIfExists(file) {
  try {
    return fs.readFileSync(file, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function trailingWhitespaceState(content) {
  const match = content.match(/[ \t\r\n]*$/);
  return match ? match[0] : '';
}

function encodeTrailingWhitespace(content) {
  return Buffer.from(trailingWhitespaceState(content), 'utf8').toString('base64');
}

function decodeTrailingWhitespace(encoded) {
  try {
    return Buffer.from(encoded || '', 'base64').toString('utf8');
  } catch (_) {
    return '';
  }
}

function guardSnippet() {
  return guardTemplate('pre-commit.sh');
}

function replaceMaintenanceContract(content, contract) {
  const start = '<!-- ai-harness-doctor:maintenance-contract:start -->';
  const end = '<!-- ai-harness-doctor:maintenance-contract:end -->';
  const statePrefix = '<!-- ai-harness-doctor:maintenance-contract:trailing-base64:';
  const pattern = new RegExp(`${escapeRegExp(start)}[\\s\\S]*?${escapeRegExp(end)}`);
  if (pattern.test(content)) return content.replace(pattern, contract.trimEnd());
  const trailing = trailingWhitespaceState(content);
  const body = content.slice(0, content.length - trailing.length);
  const state = `${statePrefix}${encodeTrailingWhitespace(content)} -->`;
  const prefix = body ? `${body}\n\n` : '';
  return `${prefix}${state}\n${contract.trimEnd()}\n`;
}

function removeMaintenanceContract(content) {
  const start = '<!-- ai-harness-doctor:maintenance-contract:start -->';
  const end = '<!-- ai-harness-doctor:maintenance-contract:end -->';
  const statePrefix = '<!-- ai-harness-doctor:maintenance-contract:trailing-base64:';
  const statePattern = `${escapeRegExp(statePrefix)}([A-Za-z0-9+/=]*) -->`;
  const recordedPattern = new RegExp(`(?:\\n\\n)?${statePattern}\\n${escapeRegExp(start)}[\\s\\S]*?${escapeRegExp(end)}\\n?`);
  if (recordedPattern.test(content)) {
    return content.replace(recordedPattern, (_match, encoded) => decodeTrailingWhitespace(encoded));
  }
  const pattern = new RegExp(`\\n?${escapeRegExp(start)}[\\s\\S]*?${escapeRegExp(end)}\\n?`);
  return content.replace(pattern, '\n').replace(/\n{3,}/g, '\n\n');
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function shortPreview(content) {
  if (content === null) return '(absent)';
  const lines = content.trimEnd().split('\n');
  const shown = lines.slice(0, 12).join('\n');
  return lines.length > 12 ? `${shown}\n...` : shown;
}

function describeChange(change) {
  console.log(`\n### ${change.action}: ${change.path}`);
  if (change.note) console.log(change.note);
  if (change.manualSnippet) {
    console.log('\nManual merge snippet:');
    console.log('```sh');
    console.log(change.manualSnippet.trimEnd());
    console.log('```');
    return;
  }
  console.log('Before:');
  console.log('```');
  console.log(shortPreview(change.before));
  console.log('```');
  console.log('After:');
  console.log('```');
  console.log(shortPreview(change.after));
  console.log('```');
}

function plannedGuardInstallChanges(target, provider) {
  const changes = [];
  const marker = '# ai-harness-doctor:guard';
  const hookPath = gitPath(target, 'hooks/pre-commit');
  assertSafeMutationPath(gitCommonDir(target), hookPath);
  const hookBefore = readTextIfExists(hookPath);
  const hookAfter = guardTemplate('pre-commit.sh');
  if (hookBefore !== null && !hookBefore.includes(marker)) {
    changes.push({
      action: 'manual-merge',
      path: hookPath,
      before: hookBefore,
      after: hookBefore,
      note: 'Existing pre-commit hook has no ai-harness-doctor marker; leaving it unchanged.',
      manualSnippet: guardSnippet(),
      write: false,
    });
  } else if (hookBefore !== hookAfter) {
    changes.push({ action: hookBefore === null ? 'create' : 'overwrite', path: hookPath, before: hookBefore, after: hookAfter, mode: 0o755, write: true });
  }

  for (const [name, template] of GUARD_CI_FILES[provider]) {
    const file = path.join(target, name);
    assertSafeMutationPath(target, file);
    const before = readTextIfExists(file);
    const after = guardTemplate(template);
    const mode = name.endsWith('.sh') ? 0o755 : undefined;
    if (before === after) continue;
    // Refuse to clobber a user-edited CI file that carries no guard marker:
    // mirror the pre-commit "manual-merge" behavior and leave it untouched.
    if (before !== null && !before.includes(GUARD_MARKER)) {
      changes.push({
        action: 'manual-merge',
        path: file,
        before,
        after: before,
        note: `Existing ${name} has no ai-harness-doctor marker; leaving it unchanged.`,
        manualSnippet: after,
        write: false,
      });
      continue;
    }
    changes.push({ action: before === null ? 'create' : 'overwrite', path: file, before, after, write: true, ...(mode ? { mode } : {}) });
  }

  const agentsPath = path.join(target, 'AGENTS.md');
  assertSafeMutationPath(target, agentsPath);
  const agentsBefore = fs.readFileSync(agentsPath, 'utf8');
  const agentsAfter = replaceMaintenanceContract(agentsBefore, guardTemplate('maintenance-contract.md'));
  if (agentsBefore !== agentsAfter) changes.push({ action: 'update', path: agentsPath, before: agentsBefore, after: agentsAfter, write: true });
  return changes;
}

function plannedGuardRemoveChanges(target) {
  const changes = [];
  const marker = '# ai-harness-doctor:guard';
  const hookPath = gitPath(target, 'hooks/pre-commit');
  assertSafeMutationPath(gitCommonDir(target), hookPath);
  const hookBefore = readTextIfExists(hookPath);
  const hookTemplate = guardTemplate('pre-commit.sh');
  if (hookBefore !== null && hookBefore.includes(marker)) {
    if (isPristineManaged(hookBefore, hookTemplate)) {
      // Pristine managed hook — safe to delete outright.
      changes.push({ action: 'remove', path: hookPath, before: hookBefore, after: null, remove: true });
    } else {
      const stripped = stripGuardBlock(hookBefore, hookTemplate);
      if (stripped === null) {
        // Marker present but the shipped block was hand-modified; do not destroy.
        changes.push({ action: 'skip', path: hookPath, before: hookBefore, after: hookBefore, note: 'Pre-commit hook was hand-modified; leaving it in place. Remove the ai-harness-doctor guard lines manually if desired.' });
      } else if (stripped.trim() === '') {
        // Nothing but the guard block remained — remove the now-empty hook.
        changes.push({ action: 'remove', path: hookPath, before: hookBefore, after: null, remove: true });
      } else {
        // User-merged hook: strip only the guard block, keep the rest.
        changes.push({ action: 'strip', path: hookPath, before: hookBefore, after: stripped, write: true, mode: 0o755 });
      }
    }
  }

  // Remove CI files from every known provider so `guard --remove` cleans up
  // regardless of which provider originally installed them. Only delete a file
  // when it is byte-identical to the shipped template; otherwise leave the
  // user-edited file untouched and report it as skipped.
  const ciNames = new Set();
  for (const files of Object.values(GUARD_CI_FILES)) for (const [name] of files) ciNames.add(name);
  for (const name of ciNames) {
    const file = path.join(target, name);
    assertSafeMutationPath(target, file);
    const before = readTextIfExists(file);
    if (before === null) continue;
    const template = guardTemplate(GUARD_CI_TEMPLATE_BY_NAME.get(name));
    if (isPristineManaged(before, template)) {
      changes.push({ action: 'remove', path: file, before, after: null, remove: true });
    } else {
      changes.push({ action: 'skip', path: file, before, after: before, note: `${name} was edited after install; leaving it in place. Remove it manually if desired.` });
    }
  }

  const agentsPath = path.join(target, 'AGENTS.md');
  assertSafeMutationPath(target, agentsPath);
  const agentsBefore = fs.readFileSync(agentsPath, 'utf8');
  const agentsAfter = removeMaintenanceContract(agentsBefore);
  if (agentsBefore !== agentsAfter) changes.push({ action: 'update', path: agentsPath, before: agentsBefore, after: agentsAfter, write: true });
  return changes;
}

function applyGuardChanges(changes, target, hookPath) {
  const gitRoot = gitCommonDir(target);
  for (const change of changes) {
    assertSafeMutationPath(change.path === hookPath ? gitRoot : target, change.path);
  }
  for (const change of changes) {
    assertSafeMutationPath(change.path === hookPath ? gitRoot : target, change.path);
    if (change.remove) {
      removePath(change.path);
    } else if (change.write) {
      ensureDir(path.dirname(change.path));
      fs.writeFileSync(change.path, change.after, { encoding: 'utf8', mode: change.mode || 0o644 });
      if (change.mode) fs.chmodSync(change.path, change.mode);
    }
  }
}

function guard(argv) {
  const parsed = parseGuardArgs(argv);
  const { apply, remove, provider } = parsed;
  if (!fs.existsSync(parsed.target) || !fs.statSync(parsed.target).isDirectory()) {
    fail(`Target is not a directory: ${parsed.target}`);
  }
  const target = fs.realpathSync(parsed.target);
  if (!isGitRepo(target)) fail(`Target must be a git repo: ${target}`);
  assertSafeMutationPath(target, path.join(target, 'AGENTS.md'));
  if (!fs.existsSync(path.join(target, 'AGENTS.md'))) fail('run the treat phase first');

  const resolvedProvider = provider === 'auto' ? detectProvider(target) : provider;
  const changes = remove ? plannedGuardRemoveChanges(target) : plannedGuardInstallChanges(target, resolvedProvider);
  console.log(`Guard ${remove ? 'remove' : 'install'} plan for ${target}`);
  if (!remove) console.log(`CI provider: ${resolvedProvider}${provider === 'auto' ? ' (auto-detected)' : ''}`);
  console.log(apply ? 'Mode: apply' : 'Mode: dry-run (use --apply to write)');
  if (!changes.length) console.log('\nNo changes needed.');
  for (const change of changes) describeChange(change);
  if (!remove && GUARD_PROVIDER_NOTES[resolvedProvider]) console.log(`\nNote: ${GUARD_PROVIDER_NOTES[resolvedProvider]}`);
  if (apply) {
    applyGuardChanges(changes, target, gitPath(target, 'hooks/pre-commit'));
    console.log(`\nApplied ${changes.filter((change) => change.write || change.remove).length} change(s).`);
  } else {
    console.log('\nDry-run only; no files written.');
  }
}

function runMcpServer() {
  // Launch the MCP stdio server, inheriting stdio so the parent process becomes the
  // transport. JSON-RPC 2.0 messages are exchanged as newline-delimited JSON.
  const server = path.join(__dirname, 'mcp-server.js');
  if (!fs.existsSync(server)) fail(`MCP server not found: ${server}`);
  const result = childProcess.spawnSync(process.execPath, [server], { stdio: 'inherit' });
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
  if (command === 'guard') return guard(rest);
  if (command === 'mcp') return runMcpServer();
  if (command === 'doctor') return doctor(rest);
  if (Object.prototype.hasOwnProperty.call(SCRIPT_COMMANDS, command)) return runScript(command, rest);
  fail(`Unknown command: ${command}`);
}

// Only run the CLI when executed directly (e.g. `node bin/cli.js ...` or via the
// installed bin). When required as a module (e.g. from unit tests) we export the
// pure helpers instead of executing, so importing does not change CLI behavior.
if (require.main === module) {
  main();
}

module.exports = { compareVersions, parseInstallArgs, SCRIPT_COMMANDS, runtimeChecks, parseDoctorArgs };
