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

// Module profiles share the credential quota editor; exercise only offline handlers.
const moduleProfile = { id: 23, name: 'Module fixture', proxy_id: 8, priority: 2, weight: 3, group_name: 'Team', rpm_limit: 5, tpm_limit: 77, max_concurrency: 3, quota_rules: rules, notes: 'note', fields: { storage_state: 'masked••', data: { nested: [true, 4, null] }, count: 7, flag: false, list: [1, '•'], nullable: null } };
const module = { provider_id: 1, manifest: { id: 'codex_cli', name: 'Codex', fields: [{ key: 'storage_state', type: 'password' }, { key: 'data', type: 'textarea', default: {} }, { key: 'count', type: 'number', default: 0 }, { key: 'flag', type: 'text', default: false }, { key: 'list', type: 'textarea', default: [] }, { key: 'nullable', type: 'textarea', default: null }] } };
const moduleState = { console, JSON, Number, Date, Set, Object, selectedModule: module, quotaModels: models, editingProfile: null, savingProfile: false, oauthStarting: false, oauthRef: { current: null }, formName: '', formGroupName: '', formRpm: '', formTpm: '', formMaxConcurrency: '', formQuotas: [], formProxyId: undefined, formPriority: 1, formWeight: 1, formFields: {}, formProfileNotes: '', formError: null, isProfileModalOpen: false, catalogError: false, showPasswordFields: {}, quotaUsage: [], usageError: '', cancelOAuth() {}, updateOAuthSession() {}, setCallbackUrl() {}, fetchProfiles: async () => {}, fetchModules: async () => {} };
for (const name of Object.keys(moduleState)) if (!name.startsWith('set')) moduleState['set' + name[0].toUpperCase() + name.slice(1)] = value => { moduleState[name] = typeof value === 'function' ? value(moduleState[name]) : value; };
let moduleCalls = [];
moduleState.apiRequest = async (url, options = {}) => { moduleCalls.push({ url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : undefined }); return []; };
vm.createContext(moduleState);
vm.runInContext(extract('pages/ModulesPage.tsx', ['openCreateModal', 'openEditModal', 'handleSaveProfile', 'quotaCatalog', 'loadQuotaUsage']), moduleState);
vm.runInContext(extract('components/QuotaEditor.tsx', ['changeQuota']), moduleState);
assert.deepEqual(Array.from(moduleState.quotaCatalog.models), ['google/gemini-fixture']);
moduleState.openEditModal(structuredClone(moduleProfile)); await new Promise(resolve => setImmediate(resolve));
moduleState.changeQuota(0, { requests: 9 });
moduleState.formFields.data = '{"nested":[false,8,null]}';
await moduleState.handleSaveProfile({ preventDefault() {} });
let saved = moduleCalls.find(call => call.method === 'PUT');
assert.equal(saved.url, '/api/admin/modules/codex_cli/profiles/23');
for (const field of ['group_name', 'rpm_limit', 'tpm_limit', 'max_concurrency', 'proxy_id', 'priority', 'weight', 'notes']) assert.equal(saved.body[field], moduleProfile[field]);
assert.equal(saved.body.quota_rules[0].requests, 9); assert.equal(moduleProfile.quota_rules[0].requests, 4);
assert.deepEqual(saved.body.fields, { data: { nested: [false, 8, null] } }, 'Unchanged fields and stale secret masks are never replayed');
assert.equal(saved.body.quota_rules[1].anchor, rules[1].anchor);
moduleCalls = []; moduleState.formFields = { ...moduleState.formFields, storage_state: ' new•secret ', count: '8', flag: 'true', list: '[2,"•"]', nullable: 'null' };
await moduleState.handleSaveProfile({ preventDefault() {} });
assert.deepEqual(moduleCalls[0].body.fields, { storage_state: ' new•secret ', data: { nested: [false, 8, null] }, count: 8, flag: true, list: [2, '•'] });
moduleState.openCreateModal(module); assert.equal(moduleState.formQuotas.length, 0); assert.equal(moduleState.formGroupName, ''); assert.equal(moduleState.formTpm, ''); assert.equal(moduleState.showPasswordFields.storage_state, undefined);
moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} });
assert.equal(moduleCalls[0].method, 'POST'); assert.equal(moduleCalls[0].body.rpm_limit, null); assert.deepEqual(moduleCalls[0].body.fields.data, {});
const session = { status: 'authorized', expiresAt: Date.now() + 60000, proxyId: null, moduleId: 'codex_cli', session_id: 'fixture' };
for (const blocked of [{ ...session, status: 'pending' }, { ...session, expiresAt: 0 }, { ...session, proxyId: 9 }]) {
  moduleCalls = []; moduleState.oauthRef.current = blocked; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.equal(moduleCalls.length, 0);
}
moduleState.oauthRef.current = session; moduleCalls = []; moduleState.formQuotas = rules;
await moduleState.handleSaveProfile({ preventDefault() {} });
assert.equal(moduleCalls[0].url, '/api/admin/modules/codex_cli/oauth/fixture/save'); assert.equal('storage_state' in moduleCalls[0].body.fields, false); assert.deepEqual(moduleCalls[0].body.quota_rules, rules);
moduleState.oauthRef.current = null; moduleState.openEditModal(structuredClone(moduleProfile)); await new Promise(resolve => setImmediate(resolve));
moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.deepEqual(moduleCalls[0].body.fields, {});
moduleState.formFields.count = ''; moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.equal(moduleCalls[0].body.fields.count, 0);
moduleState.formFields.count = '08'; moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.equal(moduleCalls[0].body.fields.count, 8);
moduleState.openEditModal(structuredClone(moduleProfile)); await new Promise(resolve => setImmediate(resolve));
moduleState.formFields.count = 'NaN'; moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.equal(moduleCalls.length, 0);
moduleState.formFields.count = '7'; moduleState.formFields.data = '{invalid'; moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} }); assert.equal(moduleCalls.length, 0); assert.equal(moduleState.isProfileModalOpen, true); assert.ok(moduleState.formError);
assert.equal(fetches, 0);
let confirmed = false; const exportAlerts = [];
moduleState.window = { confirm: message => { assert.ok(message.includes('открытые секреты') && message.includes('SQLite')); return confirmed; } };
moduleState.alert = message => exportAlerts.push(message);
moduleState.apiRequest = async (url, options) => { moduleCalls.push({ url, method: options.method }); return { success: true, relative_path: 'codex_cli/fixture.json' }; };
vm.runInContext(extract('pages/ModulesPage.tsx', ['handleExportProfile']), moduleState);
moduleCalls = []; await moduleState.handleExportProfile(23); assert.equal(moduleCalls.length, 0);
confirmed = true; await moduleState.handleExportProfile(23); assert.equal(moduleCalls[0].url, '/api/admin/modules/codex_cli/profiles/23/export'); assert.ok(exportAlerts[0].includes('не зашифрованы'));
console.log('PASS: module-profile actual create/edit/OAuth/export handlers, shared quota edits, provider-filtered catalog, exact masks/bullets and JSON types, pending/expiry/proxy guards, malformed JSON rejection; zero network.');

const moduleScratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'module-profile-render-'));
let renderedOAuth = null;
const moduleServer = await createServer({ root, configFile: false, cacheDir: moduleScratch, server: { middlewareMode: true }, plugins: [{
  name: 'module-profile-offline-render', enforce: 'pre', transform(code, id) {
    if (!id.endsWith('/pages/ModulesPage.tsx')) return;
    const replace = (anchor, value) => { assert.ok(code.includes(anchor), anchor); code = code.replace(anchor, value); };
    replace('useState<LoadedModule | null>(null)', `useState<LoadedModule | null>(${JSON.stringify(module)})`);
    replace('useState<ModuleProfile | null>(null)', `useState<ModuleProfile | null>(${JSON.stringify(moduleProfile)})`);
    replace('const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);', 'const [isProfileModalOpen, setIsProfileModalOpen] = useState(true);');
    replace('useState<PeriodQuotaRule[]>([])', `useState<PeriodQuotaRule[]>(${JSON.stringify(rules)})`);
    replace('useState<DiscoveredModel[]>([])', `useState<DiscoveredModel[]>(${JSON.stringify(models)})`);
    replace('useState<Record<string, any>>({})', `useState<Record<string, any>>(${JSON.stringify(moduleProfile.fields)})`);
    replace('useState<OAuthSession | null>(null)', `useState<OAuthSession | null>(${JSON.stringify(renderedOAuth)})`);
    return code;
  },
}] });
try {
  const { ModulesPage } = await moduleServer.ssrLoadModule('/src/pages/ModulesPage.tsx');
  const { I18nProvider } = await moduleServer.ssrLoadModule('/src/i18n/context.tsx');
  const html = renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(ModulesPage)));
  assert.ok(html.includes('aria-label="Period quotas"') && html.includes('module-profile-group') && html.includes('Параллельные запросы'));
  assert.ok(html.includes('<input type="password"') && html.includes('masked••'));
  assert.ok(html.includes('&quot;nested&quot;:[true,4,null]'), 'Structured fields render editable JSON, not object coercion');
  const catalog = html.match(/<datalist id="quota-model-options">(.*?)<\/datalist>/)[1];
  assert.equal((catalog.match(/<option/g) || []).length, 1); assert.ok(!catalog.includes('other/model'));
  assert.ok(!html.includes('quota-profile-options')); assert.equal(fetches, 0);
  console.log('PASS: real module modal renders shared quotas, scoped model catalog, group/rate controls, JSON fields and masked password; zero network.');
  renderedOAuth = { ...session, status: 'pending', auth_url: 'https://unit.invalid/authorize?state=synthetic', loopback: false };
  moduleServer.moduleGraph.invalidateAll();
  const { ModulesPage: OAuthPage } = await moduleServer.ssrLoadModule('/src/pages/ModulesPage.tsx');
  const { I18nProvider: OAuthProvider } = await moduleServer.ssrLoadModule('/src/i18n/context.tsx');
  const oauthHtml = renderToStaticMarkup(React.createElement(OAuthProvider, null, React.createElement(OAuthPage)));
  const urlInput = oauthHtml.match(/<input[^>]*id="module-oauth-url"[^>]*>/)?.[0];
  assert.ok(urlInput && /readonly=""/i.test(urlInput) && urlInput.includes(`value="${renderedOAuth.auth_url}"`), urlInput || 'OAuth URL input missing');
  assert.ok(oauthHtml.includes('URL возврата после входа') && oauthHtml.includes('Отменить OAuth'));
  assert.ok(oauthHtml.includes('Ссылка не открывается автоматически') && oauthHtml.includes('статический выходной IP'));
  assert.equal(oauthHtml.includes(`href="${renderedOAuth.auth_url}"`), false, 'Only a copyable URL; no browser-opening link');
  assert.equal(fetches, 0);
  console.log('PASS: actual pending OAuth modal renders a read-only full URL, callback/cancel controls and static-IP guidance; zero network.');
} finally { await moduleServer.close(); fs.rmSync(moduleScratch, { recursive: true, force: true }); }

// A completed request is not proof that an import transaction committed.
const backupState = { JSON, fileContent: { encrypted: true }, passphrase: 'synthetic-backup-password', updateExistingProviders: true, skipDuplicateCredentials: true, autoDiscoverModels: false, onSuccess() { refreshes++; } };
let refreshes = 0, result = null;
backupState.setIsImporting = value => { backupState.importing = value; };
backupState.setErrorMsg = value => { backupState.error = value; };
backupState.setImportResult = value => { backupState.result = value; };
backupState.apiRequest = async (url, options) => {
  assert.equal(url, '/api/admin/backup/import');
  assert.equal(JSON.parse(options.body).auto_discover_models, false);
  return result;
};
vm.createContext(backupState);
vm.runInContext(extract('components/BackupModals.tsx', ['handleExecuteImport']), backupState);
const importCases = [
  { success: false, errors: ['Configuration import failed: synthetic'], title: 'Import Failed', applied: false },
  { success: false, partial: true, errors: ['Model discovery failed: synthetic'], title: 'Import Completed with Warnings', applied: true },
  { success: true, partial: false, errors: [], title: 'Import Completed Successfully!', applied: true },
];
for (const fixture of importCases) {
  result = { imported_providers: 0, updated_providers: 0, skipped_providers: 0, imported_credentials: 0, updated_credentials: 0, skipped_credentials: 0, imported_proxies: 0, discovery_triggered: false, ...fixture };
  const before = refreshes;
  await backupState.handleExecuteImport();
  assert.equal(refreshes - before, fixture.applied ? 1 : 0);
  assert.equal(backupState.result, result); assert.equal(backupState.importing, false);
  const backupScratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'backup-result-render-'));
  const backupServer = await createServer({ root, configFile: false, cacheDir: backupScratch, server: { middlewareMode: true }, plugins: [{
    name: 'backup-result-offline-render', enforce: 'pre', transform(code, id) {
      if (!id.endsWith('/components/BackupModals.tsx')) return;
      const anchor = 'useState<BackupImportResponse | null>(null)';
      assert.ok(code.includes(anchor));
      return code.replace(anchor, `useState<BackupImportResponse | null>(${JSON.stringify(result)})`);
    },
  }] });
  try {
    const { BackupImportModal } = await backupServer.ssrLoadModule('/src/components/BackupModals.tsx');
    const html = renderToStaticMarkup(React.createElement(BackupImportModal, { isOpen: true, onClose() {}, onSuccess() {} }));
    for (const other of importCases) assert.equal(html.includes(other.title), other.title === fixture.title);
    assert.equal(html.includes('Configuration has been applied.'), fixture.applied);
    assert.equal(html.includes('The import was rolled back.'), !fixture.applied);
    assert.equal(html.includes('Close &amp; Refresh'), fixture.applied);
    assert.equal(fetches, 0);
  } finally { await backupServer.close(); fs.rmSync(backupScratch, { recursive: true, force: true }); }
}
backupState.apiRequest = async () => { throw new Error('synthetic transport failure'); };
const before = refreshes; await backupState.handleExecuteImport();
assert.equal(refreshes, before); assert.equal(backupState.error, 'synthetic transport failure'); assert.equal(backupState.importing, false);
console.log('PASS: real backup import handler and render: rollback, partial application, success and transport failure; no false success/refresh and zero network.');

// Lingling pools use the real profile save handler and native registry controls.
const poolModule = { provider_id: 1, manifest: { id: 'lingling', name: 'Lingling', fields: [
  { key: 'transport_mode', label: 'Транспорт', type: 'select', default: 'tor', options: [{ value: 'tor', label: 'Tor' }, { value: 'proxy', label: 'Прокси' }, { value: 'mixed', label: 'Tor + прокси' }] },
  { key: 'proxy_ids', label: 'Прокси', type: 'textarea', default: [] },
  { key: 'proxy_policy', label: 'Режим пула', type: 'select', default: 'balance', options: [{ value: 'balance', label: 'Балансировка' }, { value: 'priority', label: 'По приоритету' }] },
  { key: 'lanes', label: 'Tor lanes', type: 'number', default: 5 },
] } };
moduleState.selectedModule = poolModule;
moduleState.apiRequest = async (url, options = {}) => { moduleCalls.push({ url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : undefined }); return []; };
moduleState.openCreateModal(poolModule); moduleState.formFields = { transport_mode: 'proxy', proxy_policy: 'priority', proxy_ids: [2, 1] };
moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} });
assert.deepEqual(Array.from(moduleCalls[0].body.fields.proxy_ids), [2, 1]);
assert.equal(moduleCalls[0].body.fields.transport_mode, 'proxy');
assert.equal(moduleCalls[0].body.fields.proxy_policy, 'priority');
assert.equal(moduleCalls[0].body.proxy_id, null);
const poolProfile = { ...moduleProfile, module_id: 'lingling', proxy_id: null, fields: { transport_mode: 'proxy', proxy_policy: 'priority', proxy_ids: [2, 1] } };
moduleState.openEditModal(poolProfile); await new Promise(resolve => setImmediate(resolve));
moduleState.formFields = { ...moduleState.formFields, proxy_ids: [1, 2] };
moduleCalls = []; await moduleState.handleSaveProfile({ preventDefault() {} });
assert.deepEqual(Array.from(moduleCalls[0].body.fields.proxy_ids), [1, 2]);
assert.equal('transport_mode' in moduleCalls[0].body.fields, false, 'Unchanged transport is not replayed');
for (const mode of ['tor', 'proxy', 'mixed']) {
  const poolScratch = fs.mkdtempSync(path.join(process.env.TMPDIR || os.tmpdir(), 'lingling-pool-render-'));
  const poolServer = await createServer({ root, configFile: false, cacheDir: poolScratch, server: { middlewareMode: true }, plugins: [{
    name: 'lingling-pool-offline-render', enforce: 'pre', transform(code, id) {
      if (!id.endsWith('/pages/ModulesPage.tsx')) return;
      const replace = (anchor, value) => { assert.ok(code.includes(anchor), anchor); code = code.replace(anchor, value); };
      replace('useState<LoadedModule | null>(null)', `useState<LoadedModule | null>(${JSON.stringify(poolModule)})`);
      replace('const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);', 'const [isProfileModalOpen, setIsProfileModalOpen] = useState(true);');
      replace('useState<Proxy[]>([])', 'useState<Proxy[]>([{id:1,name:"First",scheme:"socks5",enabled:true},{id:2,name:"Second",scheme:"http",enabled:true},{id:3,name:"Disabled",scheme:"http",enabled:false}])');
      replace('useState<Record<string, any>>({})', `useState<Record<string, any>>(${JSON.stringify({ transport_mode: mode, proxy_policy: 'priority', proxy_ids: [2, 1], lanes: 5 })})`);
      return code;
    },
  }] });
  try {
    const { ModulesPage } = await poolServer.ssrLoadModule('/src/pages/ModulesPage.tsx');
    const { I18nProvider } = await poolServer.ssrLoadModule('/src/i18n/context.tsx');
    const html = renderToStaticMarkup(React.createElement(I18nProvider, null, React.createElement(ModulesPage)));
    assert.ok(html.includes('Прямого выхода нет') || html.includes('прямого выхода нет'));
    assert.equal(html.includes('aria-label="Пул прокси Lingling"'), mode !== 'tor');
    assert.equal(html.includes('Tor lanes'), mode !== 'proxy');
    if (mode !== 'tor') {
      assert.ok(html.includes('1. Second') && html.includes('2. First'));
      assert.ok(html.includes('aria-label="Поднять прокси 1"') && html.includes('aria-label="Убрать прокси 2"'));
      assert.ok(html.includes('type="checkbox" disabled=""'), 'Disabled registry entry cannot be newly selected');
    }
    assert.equal(fetches, 0);
  } finally { await poolServer.close(); fs.rmSync(poolScratch, { recursive: true, force: true }); }
}
console.log('PASS: Lingling Tor/proxy/mixed actual modal, ordered registry controls, disabled exits, no Direct label, typed pool create/edit payload; zero network.');

// Extract the real shared start handler: creating a session must never open a browser.
for (const moduleId of ['codex_cli', 'grok_builder_cli', 'agy_cli']) {
  for (const proxyId of [undefined, 8]) {
    let opens = 0;
    const oauthCalls = [];
    const oauth = {
      URL, Date, JSON, selectedModule: { manifest: { id: moduleId } },
      supportsBrowserOAuth: true, oauthStarting: false, savingProfile: false,
      formProxyId: proxyId, oauthGeneration: { current: 0 }, session: null,
      window: { open() { opens++; return { opener: null, closed: false, close() {}, location: { replace() {} } }; } },
      cancelOAuth() { oauth.oauthGeneration.current++; oauth.session = null; },
      updateOAuthSession(value) { oauth.session = value; },
      setOAuthStarting(value) { oauth.oauthStarting = value; },
      setFormError(value) { oauth.error = value; },
      async apiRequest(url, options) {
        oauthCalls.push({ url, method: options.method, body: options.body && JSON.parse(options.body) });
        return { session_id: 'synthetic-session', auth_url: 'https://unit.invalid/authorize?state=synthetic', loopback: true, status: 'pending', expires_in: 600 };
      },
    };
    vm.createContext(oauth);
    vm.runInContext(extract('pages/ModulesPage.tsx', ['handleStartOAuth']), oauth);
    await oauth.handleStartOAuth();
    assert.equal(opens, 0, `${moduleId} must only return the URL, never open a tab`);
    assert.equal(oauthCalls.length, 1);
    assert.equal(oauthCalls[0].url, `/api/admin/modules/${moduleId}/oauth/start`);
    assert.equal(oauthCalls[0].body.proxy_id, proxyId ?? null);
    assert.equal(oauth.session.auth_url, 'https://unit.invalid/authorize?state=synthetic');
    assert.equal(oauth.session.proxyId, proxyId ?? null);
    assert.equal(oauth.oauthStarting, false);
    assert.equal(oauth.error, null);
  }
}
assert.equal(fetches, 0);
console.log('PASS: actual Codex/Grok/Antigravity OAuth start handlers return URLs with unchanged proxy binding and zero browser opens; zero network.');
