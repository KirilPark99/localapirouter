import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import vm from 'node:vm';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'package.json'));
const React = require('react');
const ts = require('typescript');
const { renderToStaticMarkup } = require('react-dom/server');
const { createServer } = await import(path.join(root, 'node_modules/vite/dist/node/index.js'));
const scratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'credential-quota-check-'));
let language = 'ru', empty = false, fetches = 0;
globalThis.localStorage = { getItem: key => key === 'myairouter_lang' ? language : null };
globalThis.fetch = () => { fetches++; throw new Error('No network allowed'); };
const rules = [
  { id: 'a'.repeat(32), enabled: true, scope: 'model', model: 'google/gemini-fixture', period: 'day', requests: 4, tokens: 1000, usd: 1 },
  { id: 'b'.repeat(32), enabled: true, scope: 'key', period: 'custom', duration_seconds: 90, anchor: '2026-10-08T00:00:00.123Z', requests: 2 },
  { id: 'c'.repeat(32), enabled: false, scope: 'key', period: 'interval', start: '2026-10-08T00:00:00.123Z', end: '2026-10-09T00:00:00.456Z', tokens: 500 },
];
const credential = { id: 17, provider_id: 1, provider_name: 'Google', name: 'Offline credential', masked_key: 'fixture', status: 'HEALTHY', group_name: 'Team', proxy_id: 8, priority: 2, weight: 3, rpm_limit: 5, notes: 'note', discovered_models_count: 1, quota_rules: rules, metadata: { preserved: true }, model_restrictions: ['google/gemini-fixture'], tpm_limit: 77, max_concurrency: 3 };
const providers = [{ id: 1, name: 'Google', slug: 'google', auth_type: 'bearer', configuration: {} }, { id: 2, name: 'Other', slug: 'other', auth_type: 'none', configuration: {} }];
const models = [{ provider_id: 1, canonical_slug: 'google/gemini-fixture' }, { provider_id: 1, canonical_slug: 'google/gemini-fixture' }, { provider_id: 2, canonical_slug: 'other/model' }];
const usage = [{ rule_id: rules[0].id, active: true, start: '2026-10-08T00:00:00Z', end: '2026-10-09T00:00:00Z', used: { requests: 1, tokens: 30, usd: .00005 }, remaining: { requests: 3, tokens: 970, usd: .99995 } }];
const server = await createServer({ root, configFile: false, cacheDir: scratch, server: { middlewareMode: true }, plugins: [{
  name: 'credential-quota-regression-state', enforce: 'pre', transform(code, id) {
    if (!id.endsWith('/pages/CredentialsPage.tsx')) return;
    const replace = (anchor, value) => { assert.ok(code.includes(anchor), anchor); code = code.replace(anchor, value); };
    replace('useState<Credential[]>([])', `useState<Credential[]>(${JSON.stringify([{ ...credential, quota_rules: empty ? [] : rules }])})`);
    replace('useState<Provider[]>([])', `useState<Provider[]>(${JSON.stringify(providers)})`);
    replace('const [loading, setLoading] = useState(true);', 'const [loading, setLoading] = useState(false);');
    replace('const [isModalOpen, setIsModalOpen] = useState(false);', 'const [isModalOpen, setIsModalOpen] = useState(true);');
    replace('useState<Credential | null>(null)', `useState<Credential | null>(${JSON.stringify(credential)})`);
    replace('useState<PeriodQuotaRule[]>([])', `useState<PeriodQuotaRule[]>(${JSON.stringify(empty ? [] : rules)})`);
    replace('useState<PeriodQuotaUsage[]>([])', `useState<PeriodQuotaUsage[]>(${JSON.stringify(usage)})`);
    replace('useState<DiscoveredModel[]>([])', `useState<DiscoveredModel[]>(${JSON.stringify(models)})`);
    return code;
  },
}] });
try {
  const { CredentialsPage } = await server.ssrLoadModule('/src/pages/CredentialsPage.tsx');
  const { I18nProvider } = await server.ssrLoadModule('/src/i18n/context.tsx');
  const render = () => renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(CredentialsPage)));
  let html = render();
  for (const label of ['Лимиты запросов, токенов и расходов', 'Добавить лимит', 'Весь ключ провайдера', 'Израсходовано', 'Осталось', 'Своя длительность', 'Интервал дат', 'локального кеша']) assert.ok(html.includes(label), label);
  const form = html.slice(html.indexOf('<form'), html.indexOf('</form>'));
  assert.ok(form.indexOf('aria-label="Period quotas"') < form.indexOf('<select disabled=""'), 'Quota block must be first, before locked provider');
  assert.equal((html.match(/aria-label="Quota \d (requests|tokens|usd)"/g) || []).length, 9);
  assert.ok(!form.includes('value="profile"') && !form.includes('quota-profile-options'), 'No virtual-profile credential scopes');
  const catalog = form.match(/<datalist id="quota-model-options">(.*?)<\/datalist>/)[1];
  assert.equal((catalog.match(/<option/g) || []).length, 1, 'Catalog deduped and provider-filtered');
  assert.ok(catalog.includes('google/gemini-fixture') && !catalog.includes('other/model'));
  assert.ok(html.slice(0, html.indexOf('<form')).includes('Запросы: 4'), 'Existing credential table shows limit summary');
  assert.equal((form.match(/<select[^>]*disabled=""/g) || []).length, 7, 'Provider and saved rule identities locked');
  for (const button of form.match(/<button[^>]*>/g)) assert.ok(button.includes('type="button"') || button.includes('type="submit"'), button);
  language = 'en'; html = render(); assert.ok(html.includes('Entire provider credential') && html.includes('Every actual upstream dispatch'));
  language = 'de'; html = render(); assert.ok(html.includes('Every actual upstream dispatch'), 'Untranslated locale defaults to English');
  empty = true; server.moduleGraph.invalidateAll();
  const { CredentialsPage: EmptyPage } = await server.ssrLoadModule('/src/pages/CredentialsPage.tsx');
  const { I18nProvider: FreshProvider } = await server.ssrLoadModule('/src/i18n/context.tsx');
  html = renderToStaticMarkup(React.createElement(FreshProvider, null, React.createElement(EmptyPage)));
  assert.ok(html.includes('Add limit') && html.includes('No period limits'));
  assert.equal(fetches, 0);
  console.log('PASS: credential RU/EN/fallback, quota-first actual modal, empty state, native provider-filtered catalog, no profiles, locked identities, usage and visible table summary; zero network.');
} finally { await server.close(); fs.rmSync(scratch, { recursive: true, force: true }); }

function extract(file, wanted) {
  const source = fs.readFileSync(root + '/src/' + file, 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const names = new Set(wanted), snippets = [];
  function visit(node) {
    if (ts.isVariableStatement(node)) for (const declaration of node.declarationList.declarations) {
      const name = declaration.name.getText(ast);
      if (names.has(name)) { snippets.push('var ' + declaration.getText(ast) + ';'); names.delete(name); }
    }
    ts.forEachChild(node, visit);
  }
  visit(ast); assert.equal(names.size, 0, [...names].join(', '));
  return ts.transpileModule(snippets.join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None } }).outputText;
}
let stored = structuredClone(credential), calls = [], alerts = [];
const state = { console, JSON, Number, Date, Set, parseInt, providers, quotaModels: models, formProviderId: 1, formQuotas: [], quotaUsage: [], usageError: '', editingCred: null, formName: '', formGroupName: '', formApiKey: '', formProxyId: undefined, formPriority: 1, formWeight: 1, formRpm: '', formNotes: '', isKeyless: false, isModalOpen: false, alert: message => alerts.push(message), loadData: async () => {} };
for (const name of Object.keys(state)) state['set' + name[0].toUpperCase() + name.slice(1)] = value => { state[name] = typeof value === 'function' ? value(state[name]) : value; };
state.apiRequest = async (url, options = {}) => {
  const body = options.body ? JSON.parse(options.body) : undefined;
  calls.push({ url, method: options.method || 'GET', body });
  if (url.endsWith('/usage')) return structuredClone(usage);
  stored = { ...stored, ...body }; return structuredClone(stored);
};
vm.createContext(state);
vm.runInContext(extract('pages/CredentialsPage.tsx', ['openCreateModal', 'openEditModal', 'loadQuotaUsage', 'handleProviderChange', 'handleSave', 'quotaCatalog']), state);
vm.runInContext(extract('components/QuotaEditor.tsx', ['changeQuota']), state);
assert.deepEqual(Array.from(state.quotaCatalog.models), ['google/gemini-fixture']);
state.openEditModal(structuredClone(credential)); await new Promise(resolve => setImmediate(resolve));
assert.equal(calls[0].url, '/api/admin/credentials/17/usage'); assert.equal(state.quotaUsage[0].rule_id, rules[0].id);
state.changeQuota(0, { requests: 9, usd: .25, enabled: false }); assert.equal(credential.quota_rules[0].requests, 4);
state.formApiKey = '   ';
await state.handleSave({ preventDefault() {} });
const put = calls.find(call => call.method === 'PUT');
assert.equal(put.url, '/api/admin/credentials/17');
assert.equal(put.body.quota_rules[0].requests, 9); assert.equal(put.body.quota_rules[0].usd, .25); assert.equal(put.body.quota_rules[0].enabled, false);
assert.equal(put.body.quota_rules[0].id, rules[0].id);
for (const field of ['anchor', 'start', 'end']) assert.equal(put.body.quota_rules[field === 'anchor' ? 1 : 2][field], rules[field === 'anchor' ? 1 : 2][field], 'Exact UTC identity retained');
assert.equal('api_key' in put.body, false, 'Blank secret must not reset credential');
assert.equal('provider_id' in put.body, false, 'Provider identity remains locked');
for (const field of ['group_name', 'proxy_id', 'priority', 'weight', 'rpm_limit', 'notes']) assert.equal(put.body[field], credential[field]);
for (const field of ['metadata', 'model_restrictions', 'tpm_limit', 'max_concurrency']) { assert.equal(field in put.body, false); assert.deepEqual(stored[field], credential[field]); }
assert.equal(state.isModalOpen, false);
state.openCreateModal(1, ' New group '); assert.equal(state.formQuotas.length, 0); assert.equal(state.quotaUsage.length, 0); assert.equal(state.editingCred, null);
state.formName = 'Created fixture'; state.formApiKey = ' synthetic '; state.formQuotas = [rules[1], rules[2]].map(({ id: _id, ...rule }) => rule);
await state.handleSave({ preventDefault() {} });
const post = calls.find(call => call.method === 'POST');
assert.equal(post.url, '/api/admin/credentials'); assert.equal(post.body.provider_id, 1); assert.equal(post.body.api_key, 'synthetic'); assert.equal(post.body.group_name, 'New group'); assert.deepEqual(post.body.quota_rules, state.formQuotas);
state.openCreateModal(2); assert.equal(state.isKeyless, true); state.handleProviderChange(1); assert.equal(state.isKeyless, false);
state.openEditModal(structuredClone(credential)); await new Promise(resolve => setImmediate(resolve));
state.formApiKey = ' replacement '; await state.handleSave({ preventDefault() {} }); assert.equal(calls.at(-1).body.api_key, 'replacement');
state.openEditModal(structuredClone(credential)); await new Promise(resolve => setImmediate(resolve));
state.apiRequest = async () => { throw new Error('synthetic rejection'); };
await state.handleSave({ preventDefault() {} }); assert.equal(alerts.at(-1), 'synthetic rejection'); assert.equal(state.isModalOpen, true);
await state.loadQuotaUsage(17); assert.equal(state.usageError, 'synthetic rejection');
assert.equal(fetches, 0);
console.log('PASS: actual credential create/edit/error/usage and shared-editor change handlers; exact UTC rules, empty/replacement secrets, keyless/provider behavior, groups/proxy/metadata/restrictions preserved; zero network.');
