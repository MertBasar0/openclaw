// External proof utility only. It never launches/stops a Gateway or an app.
// Product mutations use the normal sessions.create/patch RPC owners, not storage writes.
import fs from 'node:fs';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const SOURCE_HEAD = '19b8bfa3823eed877b7e630e57fb9f669a1a5671';
const SESSION_KEYS = {
  inherited: 'agent:main:proof-inherited',
  'explicit-off': 'agent:main:proof-explicit-off',
};
const SESSION_LABELS = {
  inherited: 'Inherited proof',
  'explicit-off': 'Explicit Off proof',
};
const [mode, ...argv] = process.argv.slice(2);
const args = {};
for (let i = 0; i < argv.length; i += 2) {
  if (!argv[i]?.startsWith('--') || !argv[i + 1] || argv[i + 1].startsWith('--')) {
    throw new Error('Expected --name value options.');
  }
  args[argv[i].slice(2)] = argv[i + 1];
}
if (!['prepare', 'seed', 'inherit', 'off', 'high-on', 'record-state'].includes(mode)) {
  throw new Error('Modes: prepare, seed, inherit, off, high-on, record-state.');
}
if (process.platform !== 'darwin' || process.env.GITHUB_ACTIONS !== 'true'
  || process.env.RUNNER_OS !== 'macOS'
  || process.env.GITHUB_REPOSITORY?.toLowerCase() !== 'mertbasar0/openclaw') {
  throw new Error('Execution requires the authorized MertBasar0/openclaw macOS Actions runner.');
}
if (!args.root || !path.isAbsolute(args.root) || !process.env.RUNNER_TEMP) {
  throw new Error('Supply an absolute --root beneath RUNNER_TEMP.');
}
const root = path.resolve(args.root);
const runnerTemp = fs.realpathSync(process.env.RUNNER_TEMP);
const rootParent = fs.realpathSync(path.dirname(root));
if (!(rootParent === runnerTemp || rootParent.startsWith(`${runnerTemp}${path.sep}`))) {
  throw new Error('The task root parent must resolve beneath RUNNER_TEMP.');
}
const pathsFile = path.join(root, 'paths.json');
const writeJson = (file, value, exclusive = false) => fs.writeFileSync(
  file, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600, flag: exclusive ? 'wx' : 'w' },
);
const stamp = () => new Date().toISOString();
let paths;

if (mode === 'prepare') {
  if (!args.repo || !path.isAbsolute(args.repo)) throw new Error('prepare requires --repo.');
  const repo = fs.realpathSync(args.repo);
  const git = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: repo, encoding: 'utf8' });
  if (git.status !== 0 || git.stdout.trim() !== SOURCE_HEAD) {
    throw new Error('Gateway source HEAD does not match the reviewed PR head.');
  }
  const port = Number(args.port ?? '29683');
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Invalid port.');
  // A fresh directory prevents accidental reuse of a live or previous task installation.
  fs.mkdirSync(root, { mode: 0o700 });
  const area = (name) => {
    const base = path.join(root, name);
    const value = {
      home: path.join(base, 'home'), state: path.join(base, 'state'),
      config: path.join(base, 'openclaw.json'), workspace: path.join(base, 'workspace'),
      temp: path.join(base, 'tmp'),
    };
    for (const dir of [base, value.home, value.state, value.workspace, value.temp]) {
      fs.mkdirSync(dir, { mode: 0o700 });
    }
    value.env = {
      HOME: value.home, OPENCLAW_HOME: value.home, OPENCLAW_STATE_DIR: value.state,
      OPENCLAW_CONFIG_PATH: value.config, TMPDIR: value.temp,
      XDG_CONFIG_HOME: path.join(value.home, '.config'),
      XDG_CACHE_HOME: path.join(value.home, '.cache'),
      XDG_DATA_HOME: path.join(value.home, '.local', 'share'),
    };
    return value;
  };
  paths = {
    schemaVersion: 1, createdAt: stamp(), sourceHead: SOURCE_HEAD, repo, root, port,
    url: `ws://127.0.0.1:${port}`, gateway: area('gateway'), app: area('app'),
    evidence: path.join(root, 'evidence'), sessionKeys: SESSION_KEYS,
  };
  fs.mkdirSync(paths.evidence, { mode: 0o700 });
  const token = randomBytes(32).toString('hex');
  writeJson(paths.gateway.config, {
    gateway: { mode: 'local', bind: 'loopback', port, auth: { mode: 'token', token } },
    agents: {
      defaults: {
        workspace: paths.gateway.workspace, thinkingDefault: 'high', verboseDefault: 'on',
        // This catalog model supports both Off and High on the built-in runtime.
        // No model request is sent; a default without Off cannot serve the explicit-Off control.
        model: 'openai/gpt-5.4',
        models: { 'openai/gpt-5.4': { agentRuntime: { id: 'openclaw' } } },
      },
      // Sole-agent ownership is inferred. A default boolean is a retired migration input.
      entries: { main: {} },
    },
    cron: { enabled: false }, discovery: { mdns: { mode: 'off' } },
  }, true);
  writeJson(paths.app.config, {
    gateway: { mode: 'remote', remote: { transport: 'direct', url: paths.url, token } },
  }, true);
  writeJson(pathsFile, paths, true);
  writeJson(path.join(paths.evidence, 'preparation.json'), {
    sourceHead: SOURCE_HEAD, createdAt: paths.createdAt, port, transport: 'loopback',
    authentication: 'private generated token', gatewayMode: 'local', appMode: 'remote/direct',
    configuredDefaults: { thinking: 'high', verbose: 'on' },
    configuredModel: 'openai/gpt-5.4', configuredRuntime: 'openclaw',
    credentialsPublished: false, inferenceRequested: false,
  }, true);
  console.log(JSON.stringify({ mode, prepared: true, pathsFile, evidence: paths.evidence }));
  process.exit(0);
}

paths = JSON.parse(fs.readFileSync(pathsFile, 'utf8'));
if (paths.root !== root || paths.sourceHead !== SOURCE_HEAD || fs.realpathSync(root) !== root) {
  throw new Error('Unexpected task metadata or redirected task root.');
}
const selected = args.session ?? 'inherited';
if (!Object.hasOwn(SESSION_KEYS, selected)) throw new Error('Unknown proof session.');
const label = args.label ?? `${mode}-${Date.now()}`;
if (!/^[A-Za-z0-9_-]{1,90}$/.test(label)) throw new Error('Use a safe --label.');
const receipt = { mode, label, sourceHead: SOURCE_HEAD, startedAt: stamp(), calls: [] };
const receiptFile = path.join(paths.evidence, `${label}.json`);
if (fs.existsSync(receiptFile)) throw new Error('Evidence label already exists; use a new label.');
const privateConfig = JSON.parse(fs.readFileSync(paths.gateway.config, 'utf8'));
const token = privateConfig.gateway.auth.token;
const sanitize = (text) => String(text ?? '').split(token).join('<private-test-token>')
  .split(root).join('<task-root>');
const rpcEnv = { ...process.env };
// Prevent ambient profile/provider/Gateway credentials from entering the disposable proof.
for (const key of Object.keys(rpcEnv)) {
  if (/^(ACTIONS_|OPENCLAW_|CLAWDBOT_|MOLTBOT_|OPENAI_|ANTHROPIC_|GEMINI_|GOOGLE_API_|AWS_|AZURE_|GROQ_|MISTRAL_|COHERE_|XAI_)/.test(key)
    || /(?:^|_)(?:API_KEY|ACCESS_TOKEN|AUTH_TOKEN|SECRET|PASSWORD)$/.test(key)
    || key === 'GH_TOKEN' || key === 'GITHUB_TOKEN' || key === 'NODE_OPTIONS') delete rpcEnv[key];
}
Object.assign(rpcEnv, paths.gateway.env, { NO_COLOR: '1', FORCE_COLOR: '0' });
function rpc(method, params) {
  const call = { method, params, startedAt: stamp() };
  receipt.calls.push(call);
  const result = spawnSync('pnpm', [
    '--silent', 'openclaw', 'gateway', 'call', method,
    '--port', String(paths.port), '--expect-url', paths.url,
    '--params', JSON.stringify(params), '--timeout', '60000', '--json',
  ], { cwd: paths.repo, env: rpcEnv, encoding: 'utf8', timeout: 120000, maxBuffer: 8 * 1024 * 1024 });
  call.completedAt = stamp();
  call.exitCode = result.status;
  if (result.status !== 0 || result.error) {
    call.error = sanitize(result.stderr || result.error?.message || 'CLI failed').slice(-5000);
    throw new Error(`${method} failed; see the sanitized receipt.`);
  }
  try { return JSON.parse(result.stdout.trim()); }
  catch {
    call.error = 'CLI stdout was not a single JSON result; no raw output was retained.';
    throw new Error(`${method}: invalid JSON response.`);
  }
}
function patch(session, thinkingLevel, verboseLevel) {
  const result = rpc('sessions.patch', { key: SESSION_KEYS[session], thinkingLevel, verboseLevel });
  if (result.ok === false) throw new Error('sessions.patch returned ok=false.');
}
function state() {
  const result = rpc('sessions.list', { includeUnknown: true });
  if (!Array.isArray(result.sessions)) throw new Error('sessions.list did not return sessions.');
  const rows = Object.entries(SESSION_KEYS).map(([name, key]) => {
    const row = result.sessions.find((entry) => entry.key === key);
    if (!row) throw new Error(`Missing proof session: ${name}.`);
    return {
      name, key, sessionId: row.sessionId, label: row.label, displayName: row.displayName,
      thinkingLevel: row.thinkingLevel ?? null, verboseLevel: row.verboseLevel ?? null,
      serverThinkingDefault: row.thinkingDefault ?? null,
      hasActiveRun: row.hasActiveRun ?? null, activeRunIds: row.activeRunIds ?? [],
      configuredInheritedDefaults: { thinking: 'high', verbose: 'on' },
      // The server exposes thinkingDefault; verbose default here is configuration evidence,
      // not a fabricated server effectiveVerboseLevel field or inference result.
      inferredVerboseSettingFromConfig: row.verboseLevel ?? 'on',
    };
  });
  if (rows.some((row) => row.hasActiveRun === true || row.activeRunIds.length > 0)) {
    throw new Error('An unexpected active run appeared; stop the display-only proof.');
  }
  return { defaults: { serverThinkingDefault: result.defaults?.thinkingDefault ?? null }, rows };
}
try {
  if (mode === 'seed') {
    for (const [name, key] of Object.entries(SESSION_KEYS)) {
      const created = rpc('sessions.create', { key, label: SESSION_LABELS[name], displayName: SESSION_LABELS[name] });
      receipt.calls.at(-1).result = {
        ok: created.ok, key: created.key, sessionId: created.sessionId,
        runStarted: created.runStarted,
      };
      if (created.ok !== true || created.runStarted !== false || created.key !== key) {
        throw new Error('Session creation did not confirm display-only creation.');
      }
    }
    patch('inherited', null, null);
    patch('explicit-off', 'off', 'off');
  } else if (mode === 'inherit') patch(selected, null, null);
  else if (mode === 'off') patch(selected, 'off', 'off');
  else if (mode === 'high-on') patch(selected, 'high', 'on');
  receipt.state = state();
  if (mode === 'seed') {
    const inherited = receipt.state.rows.find((row) => row.name === 'inherited');
    const off = receipt.state.rows.find((row) => row.name === 'explicit-off');
    if (inherited.thinkingLevel !== null || inherited.verboseLevel !== null
      || off.thinkingLevel !== 'off' || off.verboseLevel !== 'off') {
      throw new Error('Seeded preference overrides did not persist as requested.');
    }
  }
  receipt.completedAt = stamp();
  receipt.status = 'passed';
  receipt.inferenceRequested = false;
  writeJson(receiptFile, receipt, true);
  console.log(JSON.stringify({ mode, status: receipt.status, receiptFile, state: receipt.state }));
} catch (error) {
  receipt.completedAt = stamp();
  receipt.status = 'failed';
  receipt.error = sanitize(error.message);
  writeJson(receiptFile, receipt, true);
  console.error(receipt.error);
  process.exitCode = 1;
}
